#!/usr/bin/env python3
"""Alarmzustellung über mehrere Kanäle (Muster aus der Benchmark-Recherche).

Der Konkurrent (flight-finder) verschickt Alarme über sechs Kanäle, mit einer
dauerhaften Warteschlange, erneuten Versuchen und HMAC-Signatur. Wir setzen das
um - aber ohne den Fremd-Dienst:

Kanäle (je Kanal eigener Status in der Warteschlange):
* ``command``  - beliebiges Kommando, bekommt den Alarm als JSON auf stdin
* ``webhook``  - HTTP POST (JSON), optional HMAC-SHA256-signiert
* ``slack``    - Webhook im Slack-Format (Textblock)
* ``ntfy``     - Push-Server (Topic-URL)
* ``gotify``   - Push-Server (Token-URL)
* ``telegram`` - Bot-API (Token + Chat-ID)
* ``email``    - SMTP (eigener Absender, Betreff, Text)

Die Signatur wird als ``X-Signature: sha256=<hex>`` und ``X-Timestamp`` gesetzt;
der Empfänger kann damit prüfen, dass die Meldung unverändert ist und nicht
von einem Dritten stammt (Replay-Schutz über den Zeitstempel).

Konfiguration (Beispiel):
    notify:
      secret: "<HMAC-Schluessel>"
      channels:
        - {type: webhook, url: "https://example.org/hook", secret: "<eigener Schluessel>"}
        - {type: command, command: ["/usr/local/bin/alarm", "--json"]}
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import smtplib
import subprocess
import time
from email.message import EmailMessage

try:
    import requests  # noqa: F401
except Exception:  # pragma: no cover
    requests = None


def sign_payload(payload: bytes, secret: str, timestamp: str | None = None) -> dict:
    """HMAC-SHA256-Signatur + Zeitstempel für Webhook-ähnliche Kanäle."""
    ts = timestamp or str(int(time.time()))
    mac = hmac.new(secret.encode("utf-8"), payload + ts.encode("utf-8"), hashlib.sha256)
    return {"X-Signature": "sha256=" + mac.hexdigest(), "X-Timestamp": ts}


def _http_post(url: str, payload: dict, headers: dict | None = None, timeout: int = 15) -> tuple[bool, str | None]:
    if requests is None:
        return False, "requests ist nicht installiert"
    try:
        resp = requests.post(url, json=payload, headers=headers or {}, timeout=timeout)
    except Exception as exc:
        return False, str(exc)[:200]
    if resp.status_code >= 300:
        return False, f"HTTP {resp.status_code}: {(resp.text or '')[:120]}"
    return True, None


def send_one(channel: dict, alert: dict, global_secret: str | None = None) -> tuple[bool, str | None]:
    """Ein Kanal: (ok, fehler)."""
    ctype = str(channel.get("type", "command")).lower()
    secret = channel.get("secret") or global_secret
    try:
        if ctype == "command":
            cmd = [str(c) for c in (channel.get("command") or [])]
            if not cmd:
                return False, "kein Kommando konfiguriert"
            proc = subprocess.run(cmd, input=json.dumps(alert, ensure_ascii=False),
                                  text=True, timeout=int(channel.get("timeout", 30)),
                                  capture_output=True)
            if proc.returncode != 0:
                return False, f"exit {proc.returncode}: {(proc.stderr or '')[:160]}"
            return True, None

        if ctype in ("webhook", "slack", "ntfy", "gotify", "telegram"):
            url = channel.get("url")
            if not url:
                return False, "keine URL konfiguriert"
            headers = dict(channel.get("headers") or {})
            body = alert
            if ctype == "slack":
                body = {"text": (channel.get("text")
                                 or f"Preis-Alarm {alert.get('category')}: "
                                    f"{alert.get('price')} {alert.get('currency')} "
                                    f"({alert.get('rule')})")}
            elif ctype == "telegram":
                url = f"https://api.telegram.org/bot{channel.get('token')}/sendMessage"
                body = {"chat_id": channel.get("chat_id"),
                        "text": (channel.get("text")
                                 or f"Preis-Alarm {alert.get('category')}: "
                                    f"{alert.get('price')} {alert.get('currency')}")}
            elif ctype == "gotify":
                body = (channel.get("text")
                        or f"Preis-Alarm {alert.get('category')}: "
                           f"{alert.get('price')} {alert.get('currency')}")
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            if secret:
                headers.update(sign_payload(raw, str(secret)))
            ok, err = _http_post(url, body, headers, int(channel.get("timeout", 15)))
            return ok, err

        if ctype == "email":
            msg = EmailMessage()
            msg["Subject"] = (channel.get("subject")
                              or f"Preis-Alarm {alert.get('category')}: {alert.get('price')}")
            msg["From"] = channel.get("from") or "waechter@localhost"
            msg["To"] = channel.get("to") or ""
            msg.set_content(json.dumps(alert, ensure_ascii=False, indent=1))
            host = channel.get("host") or "localhost"
            port = int(channel.get("port", 25))
            try:
                with smtplib.SMTP(host, port, timeout=int(channel.get("timeout", 20))) as smtp:
                    if channel.get("starttls"):
                        smtp.starttls()
                    if channel.get("user"):
                        smtp.login(channel["user"], channel.get("password") or "")
                    smtp.send_message(msg)
            except Exception as exc:
                return False, str(exc)[:200]
            return True, None

        return False, f"unbekannter Kanal-Typ {ctype!r}"
    except Exception as exc:  # pragma: no cover - Schutzschirm
        return False, str(exc)[:200]


def channels_of(cfg: dict) -> list[dict]:
    """Kanäle aus der Konfiguration (alte Form 'notify.command' bleibt gültig)."""
    notify = cfg.get("notify") or {}
    channels = list(notify.get("channels") or [])
    if notify.get("command"):
        channels.append({"type": "command", "name": "command",
                         "command": notify["command"],
                         "timeout": notify.get("timeout", 30)})
    out = []
    for i, ch in enumerate(channels):
        ch = dict(ch)
        ch.setdefault("name", ch.get("type", f"kanal{i}"))
        out.append(ch)
    return out


def send_all(cfg: dict, alert: dict) -> dict:
    """Alle Kanäle bedienen. Rückgabe je Kanal: {'status': ..., 'error': ...}."""
    notify = cfg.get("notify") or {}
    secret = notify.get("secret")
    result = {}
    for ch in channels_of(cfg):
        ok, err = send_one(ch, alert, secret)
        result[ch["name"]] = {"status": "acked" if ok else "failed",
                              "error": err,
                              "type": ch.get("type")}
    return result
