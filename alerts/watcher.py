#!/usr/bin/env python3
"""Preiswächter: beobachtet Preise über mehrere Quellen und Kategorien (Flüge, Hotels,
Fähren, Kreuzfahrten) und alarmiert nur bei Regelerfüllung (Nutzerbudget, Tiefpunkt oder
Preissturz gegenüber der Hochwasser-Marke).

Der Wächter ist quellen- und kategorien-agnostisch: welche Anbieter und welche Kategorien
beobachtet werden, steht in der Konfiguration; der Abruf läuft über denselben
Provider-Runner wie die Suche.

Nutzung:
    python3 alerts/watcher.py --config alerts/alert_config.example.yaml --once
    python3 alerts/watcher.py --config ... --check      # nur Zustand, nichts schreiben
    python3 alerts/watcher.py --config ... --report     # Historie auswerten
    python3 alerts/watcher.py --config ... --loop       # interner Scheduler (Container)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "providers"))

import yaml  # noqa: E402
from runner import load_registry, run  # noqa: E402

from history_db import make_store  # noqa: E402
from notify import channels_of, send_one  # noqa: E402

SCOPES = {"flights", "hotels", "ferries", "cruises"}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def append_jsonl(path: str, record: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def trim_history(path: str, keep: int) -> None:
    """Historie begrenzen (Ringpuffer) - die Datei waechst sonst unbegrenzt."""
    if keep <= 0 or not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as fh:
            lines = [ln for ln in fh if ln.strip()]
    except Exception:
        return
    if len(lines) <= keep:
        return
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.writelines(lines[-keep:])
    except Exception:
        pass


_TS_RE = re.compile(r'"ts"\s*:\s*"(\d{4}-\d{2}-\d{2})')


def read_jsonl(path: str, since: datetime | None = None) -> list[dict]:
    """Liest JSONL; bei `since` wird grob ueber das Datum vorgefiltert (ohne JSON-Parsen).

    Der Zeitfilter laeuft vor dem Parsen: bei vielen Zeilen kostet das Parsen aller
    Zeilen den Groessteil der Laufzeit, das Wegfiltern faellt dagegen kaum ins Gewicht.
    """
    if not os.path.exists(path):
        return []
    out = []
    since_date = since.date().isoformat() if since is not None else None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if since_date is not None:
                m = _TS_RE.search(line)
                if m and m.group(1) < since_date:
                    continue        # eindeutig aelter als das Fenster -> nicht parsen
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if since is not None:
                try:
                    ts = datetime.fromisoformat(rec.get("ts", ""))
                except Exception:
                    continue
                if ts < since:
                    continue
            out.append(rec)
    return out


def load_json_safe(path: str) -> Any:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


# --------------------------------------------------------------- Konfiguration
def categories_of(cfg: dict) -> list[str]:
    req = cfg.get("request") or {}
    cats = req.get("categories") or ([req["category"]] if req.get("category") else [])
    return [str(c).strip() for c in cats if str(c).strip()]


def request_for(cfg: dict, category: str) -> dict:
    """Anfragekontext einer Kategorie (global + kategorie-spezifisch)."""
    req = dict(cfg.get("request") or {})
    req.pop("categories", None)
    per = (cfg.get("requests") or {}).get(category) or {}
    req.update(per)
    req["category"] = category
    return req


def rules_for(cfg: dict, category: str) -> dict:
    """Regeln: global + Überschreibung je Kategorie."""
    rules = dict(cfg.get("rules") or {})
    rules.update((cfg.get("rules_by_category") or {}).get(category) or {})
    return rules


# --------------------------------------------------------------- Native Signale
def render_ctx(cmd: list, req: dict) -> list:
    out = []
    for c in cmd:
        s = str(c)
        for k, v in req.items():
            s = s.replace("{" + k + "}", "" if v is None else str(v))
        out.append(s)
    return out


def native_watch_state(cfg: dict, req: dict) -> dict:
    """Zustand + Historie des nativen trvl-Wächters für die Route (falls vorhanden)."""
    origin, dest = req.get("origin"), req.get("destination")
    if not origin or not dest:
        return {}
    bin_path = (cfg.get("native_watch") or {}).get("binary", "/home/batnini/.local/bin/trvl")
    try:
        proc = subprocess.run([bin_path, "watch", "list", "--format", "json"],
                              capture_output=True, text=True, timeout=90)
        watches = json.loads(proc.stdout) if proc.returncode == 0 else []
    except Exception:
        return {}
    if not isinstance(watches, list):
        return {}
    match = next((w for w in watches
                  if w.get("origin") == origin and w.get("destination") == dest), None)
    if not match:
        return {}
    state = {"watch_id": match.get("id"), "below_price": match.get("below_price"),
             "last_price": match.get("last_price"), "lowest_price": match.get("lowest_price"),
             "baseline_price": match.get("baseline_price"),
             "alert_drop_pct": match.get("alert_drop_pct"),
             "last_alerted_price": match.get("last_alerted_price"),
             "last_check": match.get("last_check")}
    try:
        proc = subprocess.run([bin_path, "watch", "history", str(match.get("id")), "--format", "json"],
                              capture_output=True, text=True, timeout=90)
        hist = json.loads(proc.stdout) if proc.returncode == 0 else []
        if isinstance(hist, list):
            state["history"] = [h for h in hist if isinstance(h, dict)]
    except Exception:
        state["history"] = []
    return state


def native_watch_sync(cfg: dict, req: dict) -> dict:
    """Optional: nativen trvl-Wächter anlegen/aktualisieren (Schwellwert = Budget)."""
    nw = cfg.get("native_watch") or {}
    if not nw.get("enabled"):
        return {}
    cmd = render_ctx([str(c) for c in nw.get("command", [])], req)
    if not cmd:
        return {}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=nw.get("timeout", 120))
        return {"command": " ".join(cmd), "exit_code": proc.returncode,
                "stdout": proc.stdout[:800], "stderr": proc.stderr[:400]}
    except Exception as exc:
        return {"command": " ".join(cmd), "error": str(exc)[:200]}


def context_commands(cfg: dict, req: dict) -> dict:
    ctx: dict[str, Any] = {}
    for entry in (cfg.get("context_commands") or []):
        cmd = entry.get("command") if isinstance(entry, dict) else entry
        if not cmd:
            continue
        name = entry.get("name") if isinstance(entry, dict) else os.path.basename(cmd[0])
        cmd = render_ctx(cmd, req)
        try:
            proc = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                                  timeout=entry.get("timeout", 120) if isinstance(entry, dict) else 120)
            ctx[name] = {"exit_code": proc.returncode, "stdout": proc.stdout[:4000]}
        except Exception as exc:
            ctx[name] = {"error": str(exc)[:200]}
    return ctx


# --------------------------------------------------------------- Snapshot
def snapshot(cfg: dict, category: str) -> dict:
    """Preisbeobachtung über alle Quellen einer Kategorie (parallel)."""
    reg = load_registry(cfg.get("registry") or os.path.join(ROOT, "providers", "registry.yaml"))
    req = request_for(cfg, category)
    req.pop("category", None)
    only = (cfg.get("providers_by_category") or {}).get(category) or cfg.get("providers") or None
    result = run(reg, category, req, only=only, rank_by=cfg.get("rank_by"))
    cheapest = result.get("cheapest") or {}
    per_source = {}
    for p in result.get("providers", []):
        per_source[p["source"]] = {"status": p["status"], "items": p["items"],
                                   "error": p["error"], "elapsed_s": p["elapsed_s"]}
    snap = {
        "ts": now_iso(),
        "category": category,
        "request": req,
        "price": cheapest.get("price"),
        "all_in": cheapest.get("all_in"),
        "currency": cheapest.get("currency"),
        "source": cheapest.get("source"),
        "name": cheapest.get("name"),
        "provider": cheapest.get("provider"),
        "price_scope": cheapest.get("price_scope"),
        "price_scope_confidence": cheapest.get("price_scope_confidence"),
        "bag_breakdown": cheapest.get("bag_breakdown"),
        "booking_url": cheapest.get("booking_url"),
        "per_source": per_source,
        "totals": result.get("totals"),
        "context": context_commands(cfg, req),
    }
    sync = native_watch_sync(cfg, req)
    if sync:
        snap.setdefault("context", {})["native_watch_sync"] = sync
    return snap


def history_store(cfg: dict):
    """Ablage der Beobachtungshistorie: JSONL (Standard) oder SQLite.

    SQLite lohnt sich ab ~1000 Punkten (Index auf Kategorie/Zeit), JSONL bleibt
    die Wahl fuer kleine Verlaeufe und fuer grep-freundliche Nachweise.
    """
    state_cfg = cfg.get("state") or {}
    backend = str(state_cfg.get("history_backend", "jsonl")).lower()
    path = state_cfg.get("history", os.path.join(HERE, "state", "history.jsonl"))
    db_path = state_cfg.get("history_db", os.path.join(os.path.dirname(path), "history.db"))
    return make_store(backend, path, db_path)


def effective_price(snap: dict, rules: dict) -> float | None:
    """Vergleichspreis: Endpreis (inkl. Gepäck/Steuern), wenn vorhanden, sonst Basispreis."""
    if rules.get("use") == "price" or snap.get("all_in") is None:
        return snap.get("price")
    return snap.get("all_in")


# --------------------------------------------------------------- Regeln
def evaluate(cfg: dict, snap: dict, rules: dict) -> dict:
    state_cfg = cfg.get("state") or {}
    hist_path = state_cfg.get("history", os.path.join(HERE, "state", "history.jsonl"))
    alerts_path = state_cfg.get("alerts", os.path.join(HERE, "state", "alerts.jsonl"))
    last_path = state_cfg.get("last_alert", os.path.join(HERE, "state", "last_alert.json"))
    category = snap.get("category", "default")

    lookback = int(rules.get("trough", {}).get("lookback_days", 7))
    since = datetime.now(timezone.utc) - timedelta(days=lookback)
    store = history_store(cfg)
    try:
        history = store.read(since=since, category=category)
    except Exception:
        history = [h for h in read_jsonl(hist_path, since) if h.get("category") == category]
    native = native_watch_state(cfg, snap.get("request") or {})
    # Native Provider-Historie als zusaetzliche Beobachtungen
    for point in (native.get("history") or []):
        price = point.get("price")
        if price is None:
            continue
        try:
            ts = datetime.fromisoformat(str(point.get("timestamp", "")).replace("Z", "+00:00"))
        except Exception:
            continue
        if ts < since:
            continue
        history.append({"ts": ts.isoformat(), "effective_price": float(price),
                        "source": "native_trvl_watch", "native": True})
    prices = [h.get("effective_price") for h in history if h.get("effective_price") is not None]
    cur = effective_price(snap, rules)
    adults = (snap.get("request") or {}).get("adults") or 1
    try:
        adults = max(1, int(adults))
    except Exception:
        adults = 1
    triggered: list[dict] = []
    min_obs = int(rules.get("trough", {}).get("min_observations", 0))

    # ---- Budget (je Person oder fuer die ganze Reise)
    budget = rules.get("budget")
    if budget is not None and cur is not None:
        scope = rules.get("budget_scope", "per_person")
        threshold = float(budget)
        compare_value = cur if scope == "per_person" else cur * adults
        if compare_value <= threshold:
            triggered.append({"rule": "budget", "threshold": threshold, "current": cur,
                              "compared_value": round(compare_value, 2), "scope": scope,
                              "text": f"Preis {cur} {snap.get('currency')} "
                                      f"({'je Person' if scope == 'per_person' else 'gesamt'}: "
                                      f"{round(compare_value, 2)}) liegt "
                                      f"{'unter/auf' if compare_value <= threshold else 'ueber'} "
                                      f"dem Budget {threshold} {snap.get('currency')}"})

    # ---- Tiefpunkt gegen eine Referenz aus dem Beobachtungsfenster
    trough = rules.get("trough") or {}
    if (trough.get("enabled", True) and cur is not None and prices
            and len(prices) >= min_obs):
        mode = trough.get("mode", "min_over_lookback")
        factor = float(trough.get("factor", 1.0))
        min_drop_pct = float(trough.get("min_drop_pct", 0))
        median = statistics.median(prices)
        if mode == "median_x":
            reference = median * factor
        elif mode == "percentile":
            reference = _percentile(prices, float(trough.get("percentile", 10)))
        else:
            reference = min(prices) * (1 + factor / 100.0)
        if cur <= reference:
            drop = ((median - cur) / median * 100) if median else 0.0
            if drop >= min_drop_pct:
                triggered.append({"rule": "trough", "mode": mode, "reference": round(reference, 2),
                                  "median": round(median, 2), "current": cur,
                                  "drop_vs_median_pct": round(drop, 1),
                                  "text": f"Tiefpunkt: {cur} {snap.get('currency')} <= Referenz "
                                          f"{round(reference, 2)} (Median {round(median, 2)}, "
                                          f"{round(drop, 1)} % unter Median)"})

    # ---- Preissturz gegen die Hochwasser-Marke (persistiert, je Kategorie)
    state_blob = load_json_safe(last_path) or {}
    per_cat = state_blob.get("categories") or {}
    cat_state = per_cat.get(category) or {}
    baseline = cat_state.get("baseline")
    try:
        baseline = float(baseline) if baseline is not None else None
    except Exception:
        baseline = None
    window_max = max(prices) if prices else None
    baseline = max([v for v in (baseline, window_max) if v is not None], default=None)
    drop_rule = rules.get("drop_pct") or {}
    if drop_rule.get("enabled") and cur is not None and baseline:
        need = float(drop_rule.get("percent", 5))
        threshold = baseline * (1 - need / 100.0)
        if cur <= threshold:
            drop = (baseline - cur) / baseline * 100 if baseline else 0.0
            triggered.append({"rule": "drop_pct", "baseline": round(baseline, 2),
                              "threshold": round(threshold, 2), "current": cur,
                              "drop_pct": round(drop, 1),
                              "text": f"Preissturz: {cur} {snap.get('currency')} ist {round(drop, 1)} % "
                                      f"unter der Hochwasser-Marke {round(baseline, 2)} "
                                      f"(Schwelle {need} %)"})

    # ---- Coverage-Gate: Datenlage pruefen, bevor geschichtsabhaengige Regeln feuern
    # (Muster aus der Benchmark-Recherche: bei Ausfall mehrerer Quellen kann der
    #  Median aus einer voellig anderen Preisspanne stammen und trotzdem ausloesen)
    cov_cfg = rules.get("coverage") or {}
    per_source = snap.get("per_source") or {}
    ok_sources = sum(1 for v in per_source.values()
                      if isinstance(v, dict) and v.get("status") == "ok")
    total_sources = len(per_source)
    coverage = {
        "observations": len(prices),
        "distinct_sources": len({h.get("source") for h in history if h.get("source")}),
        "latest_ts": max((str(h.get("ts")) for h in history if h.get("ts")), default=None),
        "providers_ok": ok_sources,
        "providers_total": total_sources,
        "success_ratio": (ok_sources / total_sources) if total_sources else None,
        "problems": [],
    }
    min_sources = int(cov_cfg.get("min_sources", 0) or 0)
    if min_sources and coverage["distinct_sources"] < min_sources:
        coverage["problems"].append(
            f"nur {coverage['distinct_sources']} Quellen im Fenster (gefordert: {min_sources})")
    max_age = float(cov_cfg.get("max_snapshot_age_hours", 0) or 0)
    if max_age and coverage["latest_ts"]:
        try:
            age_h = ((datetime.now(timezone.utc)
                      - datetime.fromisoformat(coverage["latest_ts"])).total_seconds() / 3600.0)
        except Exception:
            age_h = None
        if age_h is not None and age_h > max_age:
            coverage["problems"].append(
                f"juengster Wert {round(age_h, 1)} h alt (erlaubt: {max_age} h)")
    min_ratio = float(cov_cfg.get("min_success_ratio", 0) or 0)
    if (min_ratio and coverage["success_ratio"] is not None
            and coverage["success_ratio"] < min_ratio):
        coverage["problems"].append(
            f"nur {round(coverage['success_ratio'] * 100)} % der Quellen im letzten Lauf "
            f"erfolgreich (gefordert: {round(min_ratio * 100)} %)")
    if coverage["problems"]:
        kept = []
        for t in triggered:
            if t.get("rule") in ("trough", "drop_pct"):
                t["suppressed_by_coverage"] = "; ".join(coverage["problems"])
                continue
            kept.append(t)
        triggered = kept

    # ---- Cooldown + Preis-Dedup
    cooldown_h = float(rules.get("cooldown_hours", 24))
    improvement_pct = float(rules.get("alert_on_improvement_pct", 3))
    last = cat_state or None
    suppressed = False
    if triggered and last and last.get("price") is not None:
        try:
            last_ts = datetime.fromisoformat(last.get("ts", ""))
        except Exception:
            last_ts = None
        if last_ts and (datetime.now(timezone.utc) - last_ts) < timedelta(hours=cooldown_h):
            last_price = float(last["price"])
            if cur is None:
                suppressed = True
            else:
                better = (last_price - cur) / last_price * 100 if last_price else 0
                if better < improvement_pct:
                    suppressed = True
                else:
                    triggered[0]["note"] = (f"Cooldown ueberschrieben: Preis sank um "
                                            f"{round(better, 1)} % gegenueber letztem Alarm")
    if triggered and last and last.get("price") is not None and cur is not None:
        if abs(cur - float(last["price"])) < 0.01:
            triggered = []
            suppressed = True

    return {"triggered": triggered, "suppressed": suppressed, "coverage": coverage,
            "history_size": len(prices), "median": statistics.median(prices) if prices else None,
            "min": min(prices) if prices else None, "baseline": baseline,
            "native_watch": native,
            "history_path": hist_path, "alerts_path": alerts_path, "last_alert_path": last_path,
            "category": category}


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


# ------------------------------------------------------- Alarmzustellung (Outbox)
# Muster aus der Benchmark-Recherche (flight-finder): ein Alarm wird nicht direkt
# "feuer-und-vergessen" verschickt, sondern zuerst in einer Outbox abgelegt.
# Dadurch geht kein Alarm verloren (erneuter Versuch im naechsten Zyklus) und ein
# doppelt ausgeloester Alarm erzeugt genau eine Zustellung (Idempotenz-Schluessel).
# Aendert sich die Regel zwischen Ausloesung und Zustellung, wird der Alarm
# verworfen statt unter der alten Regel verschickt (Revisions-Fencing).


def rule_revision(rules: dict) -> str:
    """Kurz-Hash der Regel-Fassung - jede Regelaenderung aendert die Revision."""
    blob = json.dumps(rules, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def target_hash(req: dict) -> str:
    """Hash der Anfrage (Route, Daten, Personen) - derselbe Preis fuer eine andere
    Reise ist ein anderes Ereignis."""
    keys = ("origin", "destination", "depart_date", "return_date", "adults",
            "children", "currency", "category")
    blob = "|".join(str((req or {}).get(k, "")) for k in keys)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def event_key(category: str, rule: str, price, revision: str, target: str) -> str:
    """Idempotenz-Schluessel: gleiche Regel + gleicher Preis + gleiche Reise
    => gleicher Schluessel => nur eine Zustellung."""
    try:
        price_part = f"{float(price):.2f}"
    except Exception:
        price_part = ""
    raw = "|".join([category, rule, price_part, revision, target])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def load_pending(path: str) -> list[dict]:
    return read_jsonl(path) or []


def save_pending(path: str, entries: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")


def deliver(cfg: dict, entry: dict) -> tuple[str, str | None]:
    """Zustellung eines Outbox-Eintrags an alle konfigurierten Kanaele.

    Rueckgabe: (status, fehler) mit status in acked | failed | skipped.
    Der Status je Kanal steht in `entry["deliveries"]` - dadurch kann ein
    fehlgeschlagener Kanal einzeln erneut versucht werden, ohne die anderen
    erneut zu belasten.
    """
    channels = channels_of(cfg)
    if not channels:
        return "skipped", "kein Alarmkanal konfiguriert"
    secret = (cfg.get("notify") or {}).get("secret")
    alert = entry.get("alert") or {}
    deliveries = entry.get("deliveries") or {}
    all_ok = True
    any_failed = False
    for ch in channels:
        name = ch.get("name") or ch.get("type")
        prev = deliveries.get(name) or {}
        if prev.get("status") == "acked":
            continue                      # dieser Kanal hat den Alarm schon bekommen
        ok, err = send_one(ch, alert, secret)
        deliveries[name] = {"status": "acked" if ok else "failed", "error": err,
                            "type": ch.get("type"),
                            "attempts": int(prev.get("attempts", 0)) + 1,
                            "last_try": now_iso()}
        if ok:
            pass
        else:
            all_ok = False
            any_failed = True
    entry["deliveries"] = deliveries
    if all_ok:
        return "acked", None
    if any_failed:
        failed = [n for n, d in deliveries.items() if d.get("status") != "acked"]
        return "failed", "Kanäle nicht zugestellt: " + ", ".join(failed)
    return "acked", None


def _next_attempt(attempts: int, cfg: dict) -> str:
    """Backoff fuer erneute Zustellversuche (5/15/60 min)."""
    backoff = (cfg.get("state") or {}).get("delivery_backoff_minutes") or [5, 15, 60]
    idx = max(0, min(int(attempts) - 1, len(backoff) - 1))
    return (datetime.now(timezone.utc)
            + timedelta(minutes=float(backoff[idx]))).isoformat(timespec="seconds")


def enqueue_alert(cfg: dict, pending_path: str, alert: dict, revision: str) -> str:
    """Alarm in die Outbox legen und zustellen (idempotent)."""
    if not channels_of(cfg):
        return "no_channel"       # kein Kanal konfiguriert -> nichts zu zustellen
    pending = load_pending(pending_path)
    key = alert.get("event_key")
    existing = None
    for e in pending:
        if e.get("event_key") == key:
            existing = e
            break
    if existing is not None:
        if existing.get("status") == "acked":
            return "dedup"          # bereits zugestellt -> nicht erneut senden
        # vorhandenen Eintrag fortschreiben: bereits zugestellte Kanaele bleiben
        # zugestellt, offene Kanaele werden erneut versucht
        existing["alert"] = alert
        existing["rule_revision"] = revision
        existing["status"] = "pending"
        existing["next_attempt_at"] = now_iso()
        entry = existing
    else:
        entry = {"event_key": key, "rule_revision": revision,
                 "category": alert.get("category"), "created_at": now_iso(),
                 "attempts": 0, "status": "pending", "next_attempt_at": now_iso(),
                 "alert": alert}
        pending.append(entry)
    save_pending(pending_path, pending)
    trim_pending(pending_path, int((cfg.get("state") or {}).get("pending_max_entries", 500)))
    status, err = deliver(cfg, entry)
    entry["status"] = status
    entry["attempts"] = int(entry.get("attempts", 0)) + 1
    if status == "acked":
        entry["delivered_at"] = now_iso()
        entry["next_attempt_at"] = None
    else:
        entry["error"] = err
        entry["next_attempt_at"] = _next_attempt(entry["attempts"], cfg)
    save_pending(pending_path, pending)
    return status


def retry_pending(cfg: dict, pending_path: str) -> int:
    """Offene Zustellungen erneut versuchen (vor dem eigentlichen Regelwerk).

    Wurde die Regel zwischenzeitlich geaendert, wird der Alarm verworfen
    (Revisions-Fencing) - sonst koennte ein Alarm nach einer Regelaenderung
    unter der alten Regel zugestellt werden.
    """
    entries = load_pending(pending_path)
    if not entries:
        return 0
    now = datetime.now(timezone.utc)
    changed = 0
    for e in entries:
        if e.get("status") in ("acked", "skipped", "discarded", "no_channel"):
            continue
        nxt = e.get("next_attempt_at")
        if nxt:
            try:
                if datetime.fromisoformat(nxt) > now:
                    continue
            except Exception:
                pass
        cur_rev = rule_revision(rules_for(cfg, e.get("category", "")))
        if e.get("rule_revision") and cur_rev != e["rule_revision"]:
            e["status"] = "discarded"
            e["discarded_reason"] = (f"Regel geaendert (Revision {e['rule_revision']} -> {cur_rev})")
            e["next_attempt_at"] = None
            changed += 1
            continue
        status, err = deliver(cfg, e)
        e["status"] = status
        e["attempts"] = int(e.get("attempts", 0)) + 1
        e["last_try"] = now_iso()
        if status == "acked":
            e["delivered_at"] = now_iso()
            e["next_attempt_at"] = None
        else:
            e["error"] = err
            e["next_attempt_at"] = _next_attempt(e["attempts"], cfg)
        changed += 1
    if changed:
        save_pending(pending_path, entries)
    return changed


def trim_pending(path: str, keep: int) -> None:
    """Outbox begrenzen: nur die letzten `keep` Eintraege behalten."""
    if keep <= 0 or not os.path.exists(path):
        return
    entries = load_pending(path)
    if len(entries) <= keep:
        return
    save_pending(path, entries[-keep:])


def notify(cfg: dict, alert: dict) -> None:
    """Direktzustellung (ohne Outbox) - bleibt fuer Aufrufe ausserhalb des Regelwerks."""
    cmd = (cfg.get("notify") or {}).get("command") or []
    if not cmd:
        return
    payload = json.dumps(alert, ensure_ascii=False)
    try:
        subprocess.run([str(c) for c in cmd], input=payload, text=True,
                       timeout=(cfg.get("notify") or {}).get("timeout", 30))
    except Exception as exc:
        print(f"[watcher] notify fehlgeschlagen: {exc}", file=sys.stderr)


def save_state(path: str, per_category: dict) -> None:
    blob = load_json_safe(path) or {}
    blob["categories"] = per_category
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(blob, fh, ensure_ascii=False, indent=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=3600)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    state_cfg = cfg.get("state") or {}
    hist_path = state_cfg.get("history", os.path.join(HERE, "state", "history.jsonl"))
    alerts_path = state_cfg.get("alerts", os.path.join(HERE, "state", "alerts.jsonl"))
    last_path = state_cfg.get("last_alert", os.path.join(HERE, "state", "last_alert.json"))
    cats = categories_of(cfg)

    if args.report:
        store = history_store(cfg)
        try:
            history = store.read()
        except Exception:
            history = read_jsonl(hist_path)
        per_cat: dict[str, dict] = {}
        for h in history:
            cat = h.get("category", "default")
            prices = [x.get("effective_price") for x in history
                      if x.get("category") == cat and x.get("effective_price") is not None]
            per_cat[cat] = {"snapshots": sum(1 for x in history if x.get("category") == cat),
                            "min": min(prices) if prices else None,
                            "max": max(prices) if prices else None,
                            "median": statistics.median(prices) if prices else None}
        print(json.dumps({"categories": per_cat, "last": history[-1] if history else None},
                         ensure_ascii=False, indent=1))
        return 0

    def one_pass() -> int:
        # offene Zustellungen zuerst nachholen (durable Outbox)
        pending_path = state_cfg.get("pending",
                                     os.path.join(HERE, "state", "alerts_pending.jsonl"))
        retried = retry_pending(cfg, pending_path)
        if retried:
            print(f"[watcher] {retried} offene Alarmzustellung(en) erneut versucht")
        per_category = load_json_safe(last_path) or {}
        per_category = per_category.get("categories") or {}
        out_all = []
        for cat in cats:
            rules = rules_for(cfg, cat)
            snap = snapshot(cfg, cat)
            snap["effective_price"] = effective_price(snap, rules)
            verdict = evaluate(cfg, snap, rules)
            if not args.check:
                store = history_store(cfg)
                try:
                    store.append(snap)
                    store.prune(int((cfg.get("state") or {}).get("history_max_entries", 5000)))
                except Exception as exc:
                    # Ablage defekt -> auf JSONL zurueckfallen, Daten gehen nicht verloren
                    print(f"[watcher] Historie-Ablage defekt ({exc}) - schreibe nach JSONL",
                          file=sys.stderr)
                    append_jsonl(hist_path, snap)
                    trim_history(hist_path,
                                 int((cfg.get("state") or {}).get("history_max_entries", 5000)))
            out = {"category": cat, "snapshot": snap,
                   "rules": {k: v for k, v in verdict.items()
                             if k not in ("history_path", "alerts_path", "last_alert_path")}}
            out_all.append(out)
            if verdict["triggered"] and not verdict["suppressed"] and not args.check:
                for trg in verdict["triggered"]:
                    alert = {"ts": now_iso(), "category": cat,
                             "request": snap.get("request"), "rule": trg["rule"],
                             "price": snap.get("effective_price"), "currency": snap.get("currency"),
                             "price_scope": snap.get("price_scope"),
                             "source": snap.get("source"), "name": snap.get("name"),
                             "booking_url": snap.get("booking_url"), "details": trg}
                    revision = rule_revision(rules)
                    alert["rule_revision"] = revision
                    alert["event_key"] = event_key(cat, trg["rule"], alert["price"],
                                                   revision, target_hash(snap.get("request")))
                    append_jsonl(verdict["alerts_path"], alert)
                    status = enqueue_alert(cfg, pending_path, alert, revision)
                    if status not in ("acked", "dedup"):
                        print(f"[watcher] Zustellung offen ({status}): "
                              f"{alert.get('event_key')}", file=sys.stderr)
                    per_category[cat] = {"ts": alert["ts"], "price": alert["price"],
                                         "rule": trg["rule"],
                                         "baseline": max([v for v in (verdict.get("baseline"),
                                                                    alert["price"]) if v is not None],
                                                         default=None)}
                    print(f"[watcher] ALARM ({cat}/{trg['rule']}): {trg['text']}")
                save_state(verdict["last_alert_path"], per_category)
            else:
                reason = "Cooldown" if verdict["suppressed"] else "keine Regel erfüllt"
                cov = verdict.get("coverage") or {}
                hint = ""
                if cov.get("problems"):
                    hint = " | Datenlage dünn: " + "; ".join(cov["problems"])
                print(f"[watcher] kein Alarm ({cat}): {reason}{hint} | aktuell "
                      f"{snap.get('effective_price')} {snap.get('currency')} "
                      f"(Quelle {snap.get('source')}), Historie {verdict['history_size']} Punkte, "
                      f"Median {verdict['median']}")
            if args.check:
                print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    if args.loop:
        # Scheduler mit Jitter: feste Pausen erzeugen sonst gleiche Lastspitzen auf allen
        # Instanzen (Muster aus der Benchmark-Recherche: flight-finder 3 h ± 150 s).
        jitter_pct = float((cfg.get("schedule") or {}).get("jitter_pct", 10))
        while True:
            one_pass()
            span = max(1, int(args.interval * (1 + (random.random() - 0.5) * 2 * jitter_pct / 100.0)))
            print(f"[watcher] naechster Durchlauf in {span} s")
            time.sleep(span)
    return one_pass()


if __name__ == "__main__":
    raise SystemExit(main())
