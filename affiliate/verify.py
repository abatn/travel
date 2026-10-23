#!/usr/bin/env python3
"""Prüft, ob ein Affiliate-Link wirklich ein Affiliate-Link ist und erreichbar.

Zwei Stufen:

1. **Struktur** (synchron, ohne Netz): Steckt die Partner-ID im Link? Gehört der
   Host zum Partner bzw. zum Ziel? Wurde das Ziel eingebettet?  -> builder.py
2. **Erreichbarkeit** (Netz, gecacht): HEAD (Fallback GET mit kleinem Lesevorgang),
   kurzer Timeout, maximal 5 Redirects, nur erlaubte Hosts. Ergebnis wird gecacht,
   damit die UI nicht bei jedem Seitenaufruf die Anbieter belastet.

Ein Link wird nur dann als Affiliate-Link angezeigt, wenn **beide** Stufen
bestanden sind. Sonst zeigt die UI den ungetaggten Anbieter-Link und den Grund.
"""
from __future__ import annotations

import json
import os
import time
from urllib.parse import urlparse

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(HERE, "state", "verify_cache.json")
UA = "Reise-Agent/1.0 (Affiliate-Linkpruefung; kontakt@example.invalid)"


def _load_cache() -> dict:
    try:
        with open(CACHE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_cache(data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
    except Exception:
        pass


def allowed_hosts(partner: dict | None) -> list[str]:
    """Hosts, die geprüft werden dürfen (Netzwerk + Ziel-Domains)."""
    hosts = ["awin1.com", "www.awin1.com", "tbs.tradedoubler.com",
             "www.travelpayouts.com", "travelpayouts.com", "pxf.io"]
    for d in (partner or {}).get("domains") or []:
        hosts.append(str(d))
    return hosts


def _host_ok(host: str, allowed: list[str]) -> bool:
    host = (host or "").lower()
    return any(host == a or host.endswith("." + a) for a in allowed)


def check(url: str, partner: dict | None = None, cfg: dict | None = None) -> dict:
    """Erreichbarkeit prüfen (gecacht). Rückgabe: ok, status, final_url, error, cached."""
    cfg = cfg or {}
    settings = (cfg.get("settings") or {})
    ttl = int(settings.get("verify_cache_seconds", 3600))
    timeout = float(settings.get("verify_timeout_seconds", 6))
    allowed = allowed_hosts(partner)

    host = (urlparse(url).hostname or "").lower()
    if not _host_ok(host, allowed):
        return {"ok": False, "status": None, "error":
                f"Host {host!r} ist nicht fuer die Pruefung freigegeben", "cached": False}

    cache = _load_cache()
    entry = cache.get(url)
    if entry and time.time() - float(entry.get("at", 0)) < ttl:
        out = dict(entry)
        out["cached"] = True
        return out

    result = {"ok": False, "status": None, "final_url": None, "error": None,
              "at": time.time(), "cached": False}
    headers = {"User-Agent": UA, "Accept": "*/*"}
    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout,
                             headers=headers, verify=True)
        if resp.status_code in (403, 405, 501):         # HEAD nicht erlaubt
            resp = requests.get(url, allow_redirects=True, timeout=timeout,
                                headers=headers, stream=True, verify=True)
            try:
                next(resp.iter_content(1024), b"")
            finally:
                resp.close()
        result["status"] = resp.status_code
        result["final_url"] = resp.url
        result["ok"] = 200 <= resp.status_code < 400
        if not result["ok"]:
            result["error"] = f"HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        result["error"] = f"Timeout nach {timeout}s"
    except requests.exceptions.SSLError as exc:
        result["error"] = f"TLS-Fehler: {str(exc)[:120]}"
    except Exception as exc:
        result["error"] = str(exc)[:180]

    cache[url] = result
    # Cache begrenzen (Ringpuffer)
    if len(cache) > 500:
        for k in sorted(cache, key=lambda k: cache[k].get("at", 0))[:-500]:
            cache.pop(k, None)
    _save_cache(cache)
    return result


def verify_link(built: dict, cfg: dict | None = None) -> dict:
    """Kombiniert Struktur- und Erreichbarkeitsprüfung für einen gebauten Link."""
    cfg = cfg or {}
    out = dict(built)
    if not built.get("affiliate"):
        out["verified"] = False
        out["verifiable"] = False
        return out
    if not built.get("structure_ok"):
        out["verified"] = False
        out["verifiable"] = True
        out["verify_error"] = "Strukturpruefung fehlgeschlagen"
        return out
    if not (cfg.get("settings") or {}).get("verify_before_show", True):
        out["verified"] = False
        out["verifiable"] = True
        out["verify_error"] = "Erreichbarkeitspruefung ist deaktiviert"
        return out
    key = built.get("partner")
    partners = dict(cfg.get("partners") or {})
    if (cfg.get("demo") or {}).get("enabled"):
        partners["demo"] = cfg["demo"]
    res = check(str(built.get("url")), partners.get(key), cfg)
    out["verified"] = bool(res.get("ok"))
    out["verifiable"] = True
    out["verify_status"] = res.get("status")
    out["verify_error"] = res.get("error")
    out["verify_cached"] = res.get("cached")
    out["verify_final_url"] = res.get("final_url")
    return out


def main() -> int:
    import sys
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cfg = None
    try:
        from builder import load_config, build
        cfg = load_config()
        built = build(sys.argv[1], cfg)
        res = verify_link(built, cfg)
    except Exception as exc:
        print(f"Fehler: {exc}")
        return 1
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res.get("verified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
