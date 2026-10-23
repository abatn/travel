#!/usr/bin/env python3
"""Adapter-Schicht der Webober.

Grundsatz: die Webober erfindet **keine** Reiselogik. Sie ruft die vorhandenen
Bausteine auf und reicht deren Ergebnisse durch:

* Suche       -> `providers/runner.py` (`run()`)
* Bündelung   -> `bundling/compare.py` (`compare()`)
* Alarms      -> `alerts/watcher.py` (als Unterprozess mit `--once`)
* Preise, Endpreise, Steuerstatus, Plausibilität, Währungsumrechnung, Quellenstatus
                -> kommen unverändert aus diesen Modulen

Der Adapter kennt also nur: Parameter aus dem Formular in ein Kontext-Objekt
uebersetzen, Aufrufe starten, Ergebnisse speichern, Zustand fuer die Anzeige
bereitstellen.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "providers"))
sys.path.insert(0, os.path.join(ROOT, "bundling"))
sys.path.insert(0, os.path.join(ROOT, "alerts"))

# ------------------------------------------------------------------ Affiliate
def affiliate_info() -> dict:
    """Kurzinfo für die UI: welche Partner sind konfiguriert (ohne IDs)."""
    cfg = affiliate_config()
    partners = []
    for key, p in (cfg.get("partners") or {}).items():
        partners.append({"key": key, "network": p.get("network"),
                         "categories": p.get("categories"),
                         "configured": bool(str(p.get("id") or "").strip()
                                            and str(p.get("link_template") or "").strip()),
                         "cookie_days": p.get("cookie_days"),
                         "commission": p.get("commission")})
    demo = cfg.get("demo") or {}
    return {"partners": partners,
            "demo_active": bool(demo.get("enabled")),
            "disclosure_short": legal.DISCLOSURE_SHORT,
            "disclosure_long": legal.DISCLOSURE_LONG,
            "legal_notice": legal.LEGAL_NOTICE,
            "bundle_notice": legal.BUNDLE_NOTICE,
            "no_payment_note": legal.NO_PAYMENT_NOTE}


def decorate_link(url: str | None) -> dict | None:
    """Buchungslink mit Affiliate-Kennung versehen und prüfen.

    Es wird nie eine Kennung erfunden: ohne konfigurierte ID bleibt der Link
    unverändert und `affiliate` ist false.
    """
    if not url:
        return None
    cfg = affiliate_config()
    built = affiliate_build(str(url), cfg)
    info = verify_link(built, cfg)
    info["disclosure"] = legal.disclosure_for(info)
    info["attrs"] = legal.link_attributes(info)
    return info


def resolve_place(text: str, category: str = "flights") -> dict:
    """Öffentlicher Resolver für die UI."""
    try:
        return places.resolve(text, category)
    except Exception as exc:                      # pragma: no cover
        return {"ok": False, "input": text, "category": category,
                "reason": f"Resolver-Fehler: {exc}"}


def place_suggestions(text: str, category: str = "flights", limit: int = 8) -> list[dict]:
    try:
        return places.suggestions(text, category, int(limit))
    except Exception:
        return []


# ------------------------------------------------------------------ Jobs

STATE = os.path.join(HERE, "state")
JOBS_DIR = os.path.join(STATE, "jobs")
ALARMS_DIR = os.path.join(STATE, "alarms")
REGISTRY = os.path.join(ROOT, "providers", "registry.yaml")

for _d in (STATE, JOBS_DIR, ALARMS_DIR):
    os.makedirs(_d, exist_ok=True)

CATEGORIES = ("flights", "hotels", "ferries", "cruises")
CATEGORY_LABELS = {"flights": "Flüge", "hotels": "Hotels",
                   "ferries": "Fähren", "cruises": "Kreuzfahrten"}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


import yaml  # noqa: E402

from runner import load_registry, run  # noqa: E402
from compare import compare  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "affiliate"))
sys.path.insert(0, os.path.join(ROOT, "seo"))
sys.path.insert(0, os.path.join(ROOT, "resolver"))
import resolver as places  # noqa: E402
import routes_cache  # noqa: E402
from builder import build as affiliate_build, load_config as affiliate_config  # noqa: E402
from verify import verify_link  # noqa: E402
import legal  # noqa: E402
class Job:
    """Ein Suchlauf im Hintergrund (die Suche dauert je Kategorie bis ~2 Minuten)."""

    def __init__(self, params: dict):
        self.id = uuid.uuid4().hex[:12]
        self.params = params
        self.state = "running"
        self.error = None
        self.started_at = now_iso()
        self.finished_at = None
        self.categories: dict[str, dict] = {}
        self.comparison = None
        self.resolved: dict = {}
        self.lock = threading.RLock()      # reentrant: snapshot() darf im Lock gerufen werden
        self.last_snapshot: dict = {}

    def snapshot(self) -> dict:
        acquired = self.lock.acquire(timeout=5)
        if not acquired:
            # Ein haelt den Lock fest: die Oberflaeche nicht blockieren
            return dict(self.last_snapshot)
        try:
            snap = {
                "job_id": self.id,
                "state": self.state,
                "error": self.error,
                "params": self.params,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "categories": self.categories,
                "comparison": self.comparison,
                "resolved": self.resolved,
            }
            self.last_snapshot = snap
            return snap
        finally:
            self.lock.release()


JOBS: dict[str, Job] = {}


def _job_dir(job_id: str) -> str:
    return os.path.join(JOBS_DIR, job_id)


def _save_result(job: Job, category: str, data: dict) -> None:
    path = os.path.join(_job_dir(job.id), f"{category}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)


def _load_result(job_id: str, category: str) -> dict | None:
    path = os.path.join(_job_dir(job_id), f"{category}.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _expected_sources(reg: dict) -> dict[str, list[str]]:
    """Aktive Quellen je Kategorie (für die Anzeige vor dem ersten Ergebnis)."""
    by_cat: dict[str, list[str]] = {}
    for spec in reg.get("providers", []):
        if not spec.get("enabled", True):
            continue
        catspec = spec.get("category")
        for c in (catspec if isinstance(catspec, list) else [catspec]):
            if c:
                by_cat.setdefault(str(c), []).append(spec["id"])
    return {k: sorted(v) for k, v in by_cat.items()}


def start_search(params: dict) -> Job:
    """Suchlauf starten (Hintergrundthread) und die Job-ID zurueckgeben.

    Die Quellenliste wird **synchron** angelegt, bevor der Thread startet: Die
    Ergebnisseite wird wenige Millisekunden später geladen und muss alle Quellen
    bereits kennen (sonst bleibt sie leer, bis man neu lädt).
    """
    job = Job(params)
    JOBS[job.id] = job
    os.makedirs(_job_dir(job.id), exist_ok=True)
    cats = [c for c in params.get("categories") or [] if c in CATEGORIES] or ["flights"]
    try:
        by_cat = _expected_sources(load_registry(REGISTRY))
        for cat in cats:
            job.categories[cat] = {
                "state": "running",
                "providers": [{"source": sid, "status": "waiting", "items": 0,
                               "elapsed_s": None, "error": None}
                              for sid in by_cat.get(cat, [])],
                "cheapest": None, "items": 0,
            }
    except Exception:
        pass
    thread = threading.Thread(target=_run_job, args=(job,), daemon=True)
    thread.start()
    return job


def _place_error(label_a: str, text_a: str, res_a: dict,
                 label_b: str | None = None, text_b: str = "", res_b: dict | None = None) -> str:
    """Klare Meldung mit Vorschlägen statt „0 Angebote“."""
    parts = []
    for label, text, res in ((label_a, text_a, res_a), (label_b, text_b, res_b)):
        if not label or res is None or res.get("ok"):
            continue
        alt = ", ".join(f"{a['label']}" for a in (res.get("alternatives") or [])[:3])
        hint = f" Meintest du: {alt}?" if alt else ""
        parts.append(f"{label} „{text}“ nicht gefunden.{hint}")
    return " ".join(parts) or "Ort nicht auflösbar."


def _resolved_params(category: str, p: dict) -> tuple[dict | None, dict]:
    """Orte je Kategorie auflösen.

    Rückgabe: (fehler_text | None, aufgelöste Parameter)
    """
    if category == "flights":
        o = places.resolve(p.get("origin"), "flights")
        d = places.resolve(p.get("destination"), "flights")
        resolved = {"origin": o, "destination": d}
        if not o["ok"] or not d["ok"]:
            return _place_error("Abflug", p.get("origin"), o,
                                "Ziel", p.get("destination"), d), resolved
        return None, {"origin": o["code"], "destination": d["code"], "_resolved": resolved}
    if category == "hotels":
        city = p.get("city") or p.get("destination")
        d = places.resolve(city, "hotels")
        resolved = {"destination": d}
        if not d["ok"]:
            return _place_error("Ort", city, d), resolved
        return None, {"city": d["city"], "_resolved": resolved}
    if category == "ferries":
        o = places.resolve(p.get("ferry_origin") or p.get("origin"), "ferries")
        d = places.resolve(p.get("ferry_destination") or p.get("destination"), "ferries")
        resolved = {"origin": o, "destination": d}
        if not o["ok"] or not d["ok"]:
            return _place_error("Abfahrtshafen", p.get("ferry_origin") or p.get("origin"), o,
                                "Zielhafen", p.get("ferry_destination") or p.get("destination"), d), resolved
        return None, {"origin": o["name"], "destination": d["name"],
                      "_resolved": resolved}
    # cruises: Reedereien erwarten den 3-stelligen Hafen-Code
    o = places.resolve(p.get("cruise_origin") or p.get("origin"), "cruises")
    d = places.resolve(p.get("cruise_destination") or p.get("destination"), "cruises")
    resolved = {"origin": o, "destination": d}
    if not o["ok"]:
        return _place_error("Einschiffungshafen",
                            p.get("cruise_origin") or p.get("origin"), o), resolved
    return None, {"origin": o["code"], "destination": d["code"] if d["ok"] else "",
                  "_resolved": resolved}


def _run_job(job: Job) -> None:
    p = job.params
    reg = load_registry(REGISTRY)
    cats = [c for c in p.get("categories") or [] if c in CATEGORIES]
    if not cats:
        cats = ["flights"]
    timeout = float(p.get("timeout_seconds") or 0) or None

    # Quellenliste je Kategorie vorab in den Job schreiben: Die Ergebnisseite zeigt
    # damit sofort alle Quellen mit Status "wartet" - die Höhe bleibt konstant.
    by_cat: dict[str, list[str]] = {}
    for spec in reg.get("providers", []):
        if not spec.get("enabled", True):
            continue
        catspec = spec.get("category")
        names = catspec if isinstance(catspec, list) else [catspec]
        for c in names:
            if c:
                by_cat.setdefault(str(c), []).append(spec["id"])
    for cat in cats:
        job.categories[str(cat)] = {
            "state": "running",
            "providers": [{"source": sid, "status": "waiting", "items": 0,
                           "elapsed_s": None, "error": None}
                          for sid in sorted(by_cat.get(cat, []))],
            "cheapest": None, "items": 0,
        }

    def ctx_for(category: str, rp: dict) -> dict:
        ctx = {"currency": p.get("currency") or "EUR",
               "adults": int(p.get("adults") or 1),
               "children": int(p.get("children") or 0)}
        if timeout:
            ctx["_timeout"] = timeout
        if category == "flights":
            ctx["origin"] = rp.get("origin")
            ctx["destination"] = rp.get("destination")
            ctx["depart_date"] = p.get("depart_date")
            ctx["return_date"] = p.get("return_date")
            ctx["max_stops"] = p.get("max_stops") or "one_stop"
        elif category == "hotels":
            city = rp.get("city")
            ctx["destination"] = city
            ctx["city"] = city
            ctx["query"] = f"hotels near {city} city centre"
            ctx["depart_date"] = p.get("depart_date")
            ctx["return_date"] = p.get("return_date")
            ctx["hotel_stars"] = p.get("hotel_stars")
        elif category == "ferries":
            ctx["origin"] = rp.get("origin")
            ctx["destination"] = rp.get("destination")
            ctx["depart_date"] = p.get("depart_date")
            ctx["return_date"] = p.get("return_date")
        elif category == "cruises":
            ctx["origin"] = rp.get("origin")
            ctx["destination"] = rp.get("destination")
            ctx["depart_date"] = p.get("depart_date")
            ctx["return_date"] = p.get("return_date")
        return ctx

    def progress(category: str, res: dict) -> None:
        with job.lock:
            cat = job.categories.setdefault(category, {
                "state": "running", "providers": [], "cheapest": None, "items": 0})
            entry = {"source": res.get("source"), "status": res.get("status"),
                     "error": res.get("error"), "items": len(res.get("items") or []),
                     "elapsed_s": res.get("elapsed_s")}
            rows = [p for p in cat["providers"] if p.get("source") != entry["source"]]
            rows.append(entry)
            cat["providers"] = sorted(rows, key=lambda x: str(x.get("source")))

    threads = []
    for category in cats:
        def work(cat: str = category):
            error, rp = _resolved_params(cat, p)
            with job.lock:
                job.resolved[cat] = rp.get("_resolved", {})
            if error:
                with job.lock:
                    job.categories[cat] = {
                        "state": "error", "providers": [], "cheapest": None, "items": 0,
                        "error": error, "place_error": True,
                        "place_resolution": rp.get("_resolved", {}),
                    }
                return
            try:
                data = run(reg, cat, ctx_for(cat, rp), progress=progress)
            except Exception as exc:                     # pragma: no cover
                with job.lock:
                    job.categories[cat] = {"state": "error", "providers": [],
                                           "cheapest": None, "items": 0,
                                           "error": str(exc)[:300]}
                return
            _save_result(job, cat, data)
            top = [{"price": it.get("price"), "currency": it.get("currency"),
                    "all_in": it.get("all_in"), "provider": it.get("provider"),
                    "name": it.get("name"), "source": it.get("source"),
                    "stops": it.get("stops"), "booking_url": it.get("booking_url")}
                   for it in (data.get("ranked") or [])[:12]]
            with job.lock:
                job.categories[cat] = {
                    "state": "done",
                    "providers": [{"source": r.get("source"), "status": r.get("status"),
                                   "error": r.get("error"), "items": r.get("items") or 0,
                                   "elapsed_s": r.get("elapsed_s")}
                                  for r in data.get("providers", [])],
                    "cheapest": data.get("cheapest"),
                    "items": len(data.get("ranked") or []),
                    "totals": data.get("totals"),
                    "top": top,
                    "place_resolution": rp.get("_resolved", {}),
                    "price_plausibility": data.get("price_plausibility"),
                    "data_quality": data.get("data_quality"),
                }
        t = threading.Thread(target=work, daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    # Bündelung: vorhandene compare()-Logik, nichts eigene
    try:
        nights = int(p.get("nights") or 0)
        if not nights and p.get("depart_date") and p.get("return_date"):
            from datetime import date
            nights = (date.fromisoformat(str(p["return_date"]))
                      - date.fromisoformat(str(p["depart_date"]))).days
        result = compare(_load_result(job.id, "flights"), _load_result(job.id, "hotels"),
                         None, None, adults=int(p.get("adults") or 1), nights=max(nights, 1),
                         currency=p.get("currency") or "EUR",
                         cruises=_load_result(job.id, "cruises"),
                         ferries=_load_result(job.id, "ferries"))
        with job.lock:
            job.comparison = result
    except Exception as exc:                              # pragma: no cover
        with job.lock:
            job.comparison = {"error": str(exc)[:300]}

    # SEO: letzte Angebote je Route cachen (nur für indexierbare Routenseiten)
    try:
        for cat, data in list(job.categories.items()):
            if data.get("state") != "done":
                continue
            result = _load_result(job.id, cat) or {}
            if not result.get("ranked"):
                continue
            origin = p.get("ferry_origin") or p.get("cruise_origin") or p.get("origin")
            destination = (p.get("ferry_destination") or p.get("cruise_destination")
                           or p.get("destination"))
            if cat == "hotels":
                # Hotels sind ortsbezogen, keine Strecke -> die Kategorieseite genügt
                continue
            if origin and destination:
                routes_cache.save(cat, origin, destination, result.get("ranked"),
                                  {k: v for k, v in p.items() if k != "categories"})
    except Exception:
        pass

    with job.lock:
        job.state = "done"
        job.finished_at = now_iso()
    snap = job.snapshot()          # erst nach dem Lock holen (kein Deadlock)
    try:
        with open(os.path.join(_job_dir(job.id), "job.json"), "w", encoding="utf-8") as fh:
            json.dump(snap, fh, ensure_ascii=False, indent=1)
    except Exception:
        pass


def get_job(job_id: str) -> Job | None:
    return JOBS.get(job_id)


def job_result(job_id: str, category: str) -> dict | None:
    """Roher Runner-Ergebnis-Json einer Kategorie (fuer die Detailansicht)."""
    return _load_result(job_id, category)


# ------------------------------------------------------------------ Alarme
def alarm_config(alarm: dict) -> dict:
    """Wächter-Konfiguration aus einem Alarm-Datensatz bauen.

    Die Regelwerk-Logik bleibt beim Wächter: hier entsteht nur die Konfiguration
    (Budget, Tiefpunkt-Regel, Preissturz, Cooldown, Kategorie und Route).
    """
    folder = os.path.join(ALARMS_DIR, alarm["id"])
    os.makedirs(folder, exist_ok=True)
    rules = {
        "use": "all_in",
        "budget": float(alarm.get("budget") or 0),
        "budget_scope": alarm.get("budget_scope") or "per_person",
        "trough": {"enabled": bool(alarm.get("trough_enabled")),
                   "lookback_days": int(alarm.get("lookback_days") or 7),
                   "mode": alarm.get("trough_mode") or "median_x",
                   "factor": float(alarm.get("trough_factor") or 0.95),
                   "min_observations": int(alarm.get("min_observations") or 2)},
        "drop_pct": {"enabled": bool(alarm.get("drop_enabled")),
                     "percent": float(alarm.get("drop_percent") or 10)},
        "cooldown_hours": float(alarm.get("cooldown_hours") or 24),
        "alert_on_improvement_pct": float(alarm.get("improvement_pct") or 3),
        "coverage": {"min_sources": int(alarm.get("min_sources") or 1),
                     "max_snapshot_age_hours": float(alarm.get("max_age_hours") or 12),
                     "min_success_ratio": float(alarm.get("min_success_ratio") or 0.5)},
    }
    cfg = {
        "registry": REGISTRY,
        "request": {"category": alarm.get("category") or "flights",
                    "origin": alarm.get("origin"), "destination": alarm.get("destination"),
                    "depart_date": alarm.get("depart_date"),
                    "return_date": alarm.get("return_date"),
                    "adults": int(alarm.get("adults") or 1),
                    "currency": alarm.get("currency") or "EUR",
                    "max_stops": alarm.get("max_stops") or "one_stop"},
        "rules": rules,
        "state": {"history": os.path.join(folder, "history.jsonl"),
                  "alerts": os.path.join(folder, "alerts.jsonl"),
                  "last_alert": os.path.join(folder, "last_alert.json"),
                  "pending": os.path.join(folder, "alerts_pending.jsonl"),
                  "history_max_entries": 5000,
                  "delivery_backoff_minutes": [5, 15, 60]},
        "notify": {"channels": [], "secret": "", "command": [], "timeout": 30},
    }
    if alarm.get("category") == "hotels":
        cfg["request"]["city"] = alarm.get("destination")
    path = os.path.join(folder, "watcher.yaml")
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, allow_unicode=True, sort_keys=False)
    return {"config": path, "folder": folder}


def save_alarm(alarm: dict) -> dict:
    """Alarm speichern (Konfiguration + Metadaten)."""
    folder = os.path.join(ALARMS_DIR, alarm["id"])
    os.makedirs(folder, exist_ok=True)
    paths = alarm_config(alarm)
    alarm["config_path"] = paths["config"]
    alarm["created_at"] = alarm.get("created_at") or now_iso()
    alarm["folder"] = folder
    with open(os.path.join(folder, "alarm.json"), "w", encoding="utf-8") as fh:
        json.dump(alarm, fh, ensure_ascii=False, indent=1)
    return alarm


def list_alarms() -> list[dict]:
    out = []
    for name in sorted(os.listdir(ALARMS_DIR)):
        path = os.path.join(ALARMS_DIR, name, "alarm.json")
        try:
            with open(path, encoding="utf-8") as fh:
                out.append(json.load(fh))
        except Exception:
            continue
    return out


def run_watcher(alarm: dict) -> dict:
    """Wächter einmal laufen lassen (Unterprozess des vorhandenen Moduls)."""
    cfg = alarm.get("config_path")
    if not cfg or not os.path.exists(cfg):
        return {"ok": False, "error": "Konfiguration fehlt"}
    cmd = [sys.executable, os.path.join(ROOT, "alerts", "watcher.py"),
           "--config", cfg, "--once"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900,
                              cwd=ROOT)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}
    return {"ok": proc.returncode == 0, "returncode": proc.returncode,
            "stdout": proc.stdout.strip()[-4000:], "stderr": proc.stderr.strip()[-1500:]}


def alarm_state(alarm: dict) -> dict:
    """Zustand des Alarms: Verlauf, letzte Alarme, Coverage."""
    folder = alarm.get("folder") or os.path.join(ALARMS_DIR, alarm.get("id", ""))
    def read_jsonl(name: str) -> list[dict]:
        path = os.path.join(folder, name)
        out = []
        if not os.path.exists(path):
            return out
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            out.append(json.loads(line))
                        except Exception:
                            continue
        except Exception:
            return out
        return out
    history = read_jsonl("history.jsonl")
    alerts = read_jsonl("alerts.jsonl")
    pending = read_jsonl("alerts_pending.jsonl")
    last = None
    try:
        with open(os.path.join(folder, "last_alert.json"), encoding="utf-8") as fh:
            last = json.load(fh)
    except Exception:
        last = None
    prices = [h.get("effective_price") for h in history if h.get("effective_price") is not None]
    median = None
    if prices:
        srt = sorted(prices)
        mid = len(srt) // 2
        median = srt[mid] if len(srt) % 2 else (srt[mid - 1] + srt[mid]) / 2
    return {"history": history[-50:], "history_size": len(history), "alerts": alerts[-20:],
            "pending": pending[-20:], "last_alert": (last or {}).get("categories", {}).get(
                alarm.get("category") or "flights"), "median": median,
            "min": min(prices) if prices else None, "max": max(prices) if prices else None}


# ------------------------------------------------------------------ Status
def source_status() -> dict:
    """Welche Quellen sind in der Registry aktiv, welche sind deaktiviert."""
    reg = load_registry(REGISTRY)
    by_cat: dict[str, list[dict]] = {}
    for p in reg.get("providers", []):
        cat = p.get("category") or "unknown"
        by_cat.setdefault(cat, []).append({
            "id": p.get("id"), "enabled": p.get("enabled", True),
            "transport": p.get("transport"), "note": (p.get("note") or "")[:160],
            "price_scope": p.get("price_scope"),
        })
    breakers = {}
    try:
        with open(os.path.join(ROOT, "providers", "state", "breakers.json"), encoding="utf-8") as fh:
            breakers = json.load(fh)
    except Exception:
        breakers = {}
    now = time.time()
    for cat, items in by_cat.items():
        for it in items:
            b = breakers.get(it["id"]) or {}
            until = b.get("open_until")
            it["blocked_until"] = (datetime.fromtimestamp(until).astimezone().isoformat(
                timespec="seconds") if until and until > now else None)
            it["last_error"] = b.get("last_error")
    return {"categories": by_cat,
            "labels": CATEGORY_LABELS,
            "generated_at": now_iso()}
