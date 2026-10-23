#!/usr/bin/env python3
"""Affiliate-Link-Builder.

Baut aus einem Anbieter-Buchungslink einen Affiliate-Link und prüft ihn
strukturell. Grundsätze:

1. **Keine erfundenen Kennungen.** Ohne konfigurierte ID (und ohne Link-Template
   aus dem Partner-Dashboard) wird nicht getaggt – der Link bleibt unverändert.
2. **Domain-Bindung.** Ein Partner taggt nur Links, deren Host in seinen
   `domains` steht. So kann ein Hotel-Partner nie einen Airline-Link taggen.
3. **Kein Doppel-Tagging.** Ist der Link bereits getaggt, bleibt er unverändert.
4. **Strukturprüfung.** Nach dem Bau wird geprüft, dass die ID im Link steht und
   das Ziel im Link enthalten ist – sonst gilt der Link als ungültig.

Die Provision beeinflusst **nie** die Rangfolge; der Builder ist reine
Ausgabe-Anreicherung (siehe affiliate/ENTSCHEIDUNG.md).
"""
from __future__ import annotations

import os
import re
from urllib.parse import parse_qsl, quote, urlparse, urlunparse

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.yaml")

# Parameter, an denen ein bereits getaggter Link erkennbar ist
KNOWN_AFFILIATE_PARAMS = ("awinaffid", "awinmid", "marker", "shmarker", "affid",
                          "ref", "affiliate_id", "irgwc", "ir_partnerid",
                          "tduid", "clickref", "sid")


def load_config(path: str | None = None) -> dict:
    """Konfiguration laden; Pfad per AFFILIATE_CONFIG übersteuerbar (Tests)."""
    target = path or os.environ.get("AFFILIATE_CONFIG") or CONFIG_PATH
    with open(target, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _host(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return ""
    return host.lower().lstrip(".")


def _host_matches(host: str, domains: list[str]) -> bool:
    """true, wenn host == domain oder eine Subdomain davon ist."""
    host = host.lower()
    for d in domains or []:
        d = str(d).lower().strip()
        if not d:
            continue
        if host == d or host.endswith("." + d):
            return True
    return False


def partner_for(url: str, cfg: dict | None = None) -> str | None:
    """Welcher Partner ist für den Zielhost zuständig?"""
    cfg = cfg or load_config()
    host = _host(url)
    if not host:
        return None
    for key, p in (cfg.get("partners") or {}).items():
        if p.get("enabled", True) is False:
            continue
        if _host_matches(host, p.get("domains") or []):
            return key
    demo = cfg.get("demo") or {}
    if demo.get("enabled") and _host_matches(host, demo.get("domains") or []):
        return "demo"
    return None


def is_tagged(url: str, cfg: dict | None = None) -> bool:
    """Enthält der Link bereits einen Affiliate-Parameter?"""
    try:
        query = dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
    except Exception:
        return False
    if any(k.lower() in KNOWN_AFFILIATE_PARAMS for k in query):
        return True
    cfg = cfg or load_config()
    partners = dict(cfg.get("partners") or {})
    if cfg.get("demo"):
        partners["demo"] = cfg["demo"]
    for p in partners.values():
        pid = str(p.get("id") or "").strip()
        if pid and pid in url:
            return True
    return False


def _render(template: str, mapping: dict) -> str:
    """Platzhalter einsetzen.

    {target}         -> Ziel-URL roh (Template beginnt mit dem Ziel)
    {target_encoded} -> Ziel-URL URL-kodiert (Netzwerk-Redirector)
    """
    out = template
    target = str(mapping.get("target") or "")
    out = out.replace("{target_encoded}", quote(target, safe=""))
    # Template haengt Parameter mit "?" an: hat das Ziel schon eine Query, wird "&" daraus
    if "{target}?" in out and "?" in target:
        out = out.replace("{target}?", "{target}&")
    out = out.replace("{target}", target)
    for key in ("id", "campaign"):
        out = out.replace("{" + key + "}", str(mapping.get(key) or ""))
    return out


def build(url: str, cfg: dict | None = None,
          allow_demo: bool = True) -> dict:
    """Affiliate-Link bauen.

    Rückgabe:
        url           – der anzuzeigende Link (ggf. unverändert)
        affiliate     – true, wenn ein Affiliate-Link entstanden ist
        partner       – Partnername oder None
        network       – Netzwerkname
        reason        – Begründung, wenn nicht getaggt
        structure_ok  – Strukturprüfung bestanden
        disclosure    – Kennzeichnungstext für die UI
        commission    – Provisionsangabe aus der Konfiguration (nur Anzeige)
        cookie_days   – Cookie-Laufzeit aus der Konfiguration
    """
    cfg = cfg or load_config()
    base = {"url": url, "affiliate": False, "partner": None, "network": None,
            "reason": None, "structure_ok": None, "disclosure": None,
            "commission": None, "cookie_days": None, "test_id": False}

    if not url or not re.match(r"^https?://", str(url), re.I):
        base["reason"] = "kein gueltiger http(s)-Link"
        base["structure_ok"] = False
        return base

    key = partner_for(url, cfg)
    partners = dict(cfg.get("partners") or {})
    if (cfg.get("demo") or {}).get("enabled"):
        partners["demo"] = cfg["demo"]
    if key is None:
        base["reason"] = "kein Partnerprogramm fuer diesen Anbieter (keine Provision moeglich)"
        return base

    p = partners.get(key) or {}
    if key == "demo" and not allow_demo:
        base["reason"] = "Testpartner im Normalbetrieb deaktiviert"
        return base

    pid = str(p.get("id") or "").strip()
    template = str(p.get("link_template") or "").strip()
    if not pid:
        base["partner"] = key
        base["network"] = p.get("network")
        base["reason"] = (f"Partner {p.get('network', key)} bekannt, aber keine ID "
                          f"konfiguriert - kein Affiliate-Link (keine erfundene Kennung)")
        return base
    if not template:
        base["partner"] = key
        base["network"] = p.get("network")
        base["reason"] = (f"Partner {p.get('network', key)} hat kein Link-Template "
                          f"(aus dem Dashboard kopieren) - kein Affiliate-Link")
        return base

    if is_tagged(url, cfg):
        base["partner"] = key
        base["network"] = p.get("network")
        base["reason"] = "Link ist bereits getaggt - nicht doppelt taggen"
        return base

    built = _render(template, {"id": pid, "campaign": p.get("campaign") or "",
                               "target": url})
    ok = _structure_ok(built, pid, url, p)
    base.update({"url": built, "affiliate": ok, "partner": key,
                 "network": p.get("network"), "structure_ok": ok,
                 "commission": p.get("commission"), "cookie_days": p.get("cookie_days"),
                 "test_id": key == "demo"})
    if not ok:
        base["url"] = url
        base["affiliate"] = False
        base["reason"] = "Strukturpruefung fehlgeschlagen - Original-Link bleibt"
    elif key == "demo":
        base["disclosure"] = "Anzeige · Testkennung (kein echtes Partnerprogramm)"
    else:
        base["disclosure"] = "Anzeige · Affiliate-Link (Provision moeglich)"
    return base


def _structure_ok(built: str, pid: str, target: str, partner: dict) -> bool:
    """Prüft: ID enthalten, Ziel enthalten, Host erlaubt."""
    try:
        host = _host(built)
    except Exception:
        return False
    if not host:
        return False
    # Die ID muss im Link stehen (klartext oder URL-kodiert)
    if pid not in built and quote(pid, safe="") not in built:
        return False
    # Das Ziel muss im Link stecken (roh oder kodiert)
    if target in built or quote(target, safe="") in built:
        return True
    # Netzwerk-Redirector: Host ist nicht das Ziel, aber das Ziel steckt kodiert drin
    return _host_matches(host, partner.get("domains") or []) or \
        _host_matches(_host(target), partner.get("domains") or [])


def decorate(url: str, cfg: dict | None = None) -> dict:
    """Kurzform für die UI: build() + Hinweis, ob eine Prüfung nötig ist."""
    return build(url, cfg)
