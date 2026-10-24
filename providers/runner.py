#!/usr/bin/env python3
"""Dynamische Provider-Abdeckung: fragt alle in der Registry konfigurierten Quellen
parallel ab, normalisiert die Antworten und liefert die günstigsten Optionen.

Neue Quelle hinzufügen = Eintrag in `providers/registry.yaml` (kein Code).
Nutzung:
    python3 providers/runner.py --registry providers/registry.yaml \\
        --category flights --origin BER --destination FCO \\
        --depart-date 2026-10-31 --return-date 2026-11-02 --adults 1 --currency EUR
    python3 providers/runner.py --request request.json --category hotels
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import math
import os
import random
import re
import subprocess
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml  # noqa: E402
from normalize import (dedupe, get_path, normalize_expanded,  # noqa: E402
                     normalize_item, parse_markdown_table, parse_text_prices, rank_key)
from mcp_http import MCPHttpClient  # noqa: E402
from score import score_offers  # noqa: E402
from plausibility import screen as plausibility_screen, message_for_source, message_global  # noqa: E402
from mcp_stdio import MCPStdioClient  # noqa: E402
from rights import filter_providers  # noqa: E402


# ---------------------------------------------------------------- Registry
def load_registry(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def render(value: Any, ctx: dict) -> Any:
    """Ersetzt {platzhalter} in Strings; dicts/lists werden rekursiv gerendert."""
    if isinstance(value, str):
        out = value
        for k, v in ctx.items():
            token = "{" + k + "}"
            if token in out:
                out = out.replace(token, "" if v is None else str(v))
        # unaufgelöste Platzhalter (z. B. "{children}") -> Wert weglassen
        if re.fullmatch(r"\{[A-Za-z_][A-Za-z0-9_]*\}", out):
            return None
        return out
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            rv = render(v, ctx)
            if rv is None:
                continue  # nicht gesetzte Platzhalter weglassen (Tool-Defaults greifen)
            out[k] = rv
        return out
    if isinstance(value, list):
        return [render(v, ctx) for v in value]
    return value


# ---------------------------------------------------------------- Ausführung
def coerce_params(params: Any, coerce: dict | None) -> Any:
    """Typkonvertierung nach Registry-Angabe (z. B. hotel_class: [4] statt ['4'])."""
    if not coerce or not isinstance(params, dict):
        return params
    out = dict(params)
    for key, kind in coerce.items():
        if key not in out or out[key] is None:
            continue
        val = out[key]
        try:
            if kind == "int":
                out[key] = int(val)
            elif kind == "int_list":
                out[key] = [int(v) for v in (val if isinstance(val, list) else [val])]
            elif kind == "float":
                out[key] = float(val)
            elif kind == "bool":
                out[key] = str(val).strip().lower() in ("1", "true", "yes", "on")
            elif kind == "str_list":
                out[key] = [str(v) for v in (val if isinstance(val, list) else [val])]
        except (TypeError, ValueError):
            pass
    # rekursiv in verschachtelte Strukturen (z. B. occupancies[].adults)
    for key, val in list(out.items()):
        if isinstance(val, dict):
            out[key] = coerce_params(val, coerce)
        elif isinstance(val, list):
            out[key] = [coerce_params(v, coerce) if isinstance(v, dict) else v for v in val]
    return out


# ---------------------------------------------------------- Circuit Breaker
# Eine Quelle, die kurzfristig gesperrt hat (429/Timeout), wird fuer eine
# Abklingzeit uebersprungen - das schont das Kontingent und beschleunigt den Lauf.
BREAKER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "breakers.json")


CALLS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "last_call.json")
QUOTA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "quota.json")


def load_quotas() -> dict:
    try:
        with open(QUOTA_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_quotas(data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(QUOTA_FILE), exist_ok=True)
        with open(QUOTA_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
    except Exception:
        pass


def effective_quota(spec: dict, quotas: dict | None = None) -> int | None:
    """Aktuelles Kontingent der Quelle (adaptiv, nie groesser als konfiguriert)."""
    base = spec.get("max_calls_per_hour")
    if not base:
        return None
    quotas = quotas if quotas is not None else load_quotas()
    cur = (quotas.get(spec["id"]) or {}).get("quota")
    try:
        cur = int(cur)
    except Exception:
        cur = int(base)
    return max(1, min(int(base), cur))


def quota_adjust(spec: dict, quotas: dict, throttled: bool) -> None:
    """Kontingent anpassen: halbieren bei Drosselung, x1.5 nach Erholung."""
    base = spec.get("max_calls_per_hour")
    if not base:
        return
    entry = quotas.get(spec["id"]) or {"quota": int(base), "streak": 0}
    try:
        cur = int(entry.get("quota", base))
    except Exception:
        cur = int(base)
    if throttled:
        cur = max(1, cur // 2)
        entry["streak"] = 0
    else:
        entry["streak"] = int(entry.get("streak", 0)) + 1
        if entry["streak"] >= 3:              # erst nach drei guten Laeufen aufdrehen
            cur = min(int(base), int(math.ceil(cur * 1.5)))
            entry["streak"] = 0
    entry["quota"] = max(1, min(int(base), cur))
    entry["base"] = int(base)
    entry["updated_at"] = time.time()
    quotas[spec["id"]] = entry
    save_quotas(quotas)


def calls_path() -> str:
    """Pfad der Aufrufhistorie (fuer Tests uebersteuerbar)."""
    return os.environ.get("TRVL_CALLS_FILE") or CALLS_FILE


def load_calls() -> dict:
    try:
        with open(calls_path(), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def note_call(spec: dict) -> None:
    """Merkt sich, wann eine Quelle zuletzt abgefragt wurde (Governor/Kontingent)."""
    data = load_calls()
    entry = data.get(spec["id"]) or {}
    recent = [t for t in (entry.get("recent") or []) if t > time.time() - 3600]
    recent.append(time.time())
    data[spec["id"]] = {"ts": time.time(), "recent": recent[-60:]}
    path = calls_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
    except Exception:
        pass


def breaker_path() -> str:
    return os.environ.get("TRVL_BREAKER_FILE") or BREAKER_FILE


def load_breakers() -> dict:
    try:
        with open(breaker_path(), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_breakers(state: dict) -> None:
    path = breaker_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=1)
    except Exception:
        pass


def breaker_open(spec: dict, state: dict, cooldown_s: float) -> tuple[bool, str | None]:
    """Ist der Breaker fuer diese Quelle offen?"""
    entry = (state.get(spec["id"]) or {})
    until = entry.get("open_until")
    if not until:
        return False, None
    try:
        left = float(until) - time.time()
    except Exception:
        return False, None
    if left > 0:
        return True, (f"Circuit Breaker offen (noch {int(left)} s) - letzte Ursache: "
                      f"{entry.get('last_error', 'unbekannt')[:120]}")
    return False, None


def breaker_trip(spec: dict, state: dict, error: str, cooldown_s: float) -> None:
    entry = state.get(spec["id"]) or {}
    fails = int(entry.get("fails", 0)) + 1
    # exponentielles Fenster: jeder weitere Fehlversuch verlaengert die Sperre
    window = min(cooldown_s * (2 ** (fails - 1)), 3600)
    state[spec["id"]] = {"fails": fails, "open_until": time.time() + window,
                         "last_error": error[:200], "opened_at": time.time()}


def breaker_reset(spec: dict, state: dict) -> None:
    state.pop(spec["id"], None)


def is_transient(error: str) -> bool:
    """Ist der Fehler ein Raten-Limit/Temporaerfehler (nicht ein Defekt der Quelle)?"""
    t = (error or "").lower()
    return any(m in t for m in ("429", "rate limit", "too many requests", "timeout",
                                "timed out", "503", "502", "500", "cooling down",
                                "temporarily unavailable", "connection reset", "eof occurred"))


def fx_rate(base: str, quote: str) -> dict:
    """Belegter Wechselkurs (keyless, mit Quelle und Zeitstempel) - sonst None."""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
        from fx import get_rate  # type: ignore
        return get_rate(base, quote)
    except Exception as exc:
        return {"base": base, "quote": quote, "rate": None, "error": str(exc)[:200]}


def _call_transport(spec: dict, transport: str, ctx: dict, timeout: float) -> Any:
    """Ruft die Quelle einmal ab - je Transport der passende Weg."""
    if transport == "mcp_stdio":
        client = MCPStdioClient(list(spec["command"]), name=spec["id"], timeout=timeout)
        try:
            return client.call_tool(spec["tool"],
                                   coerce_params(render(spec.get("params", {}), ctx), spec.get("coerce")),
                                   timeout=timeout)
        finally:
            client.close()
    if transport == "mcp_http":
        client = MCPHttpClient(spec["url"], name=spec["id"], timeout=timeout,
                               headers=spec.get("headers"))
        return client.call_tool(spec["tool"],
                                coerce_params(render(spec.get("params", {}), ctx), spec.get("coerce")),
                                timeout=timeout)
    if transport == "cli":
        cmd = [str(x) for x in render(spec.get("command", []), ctx)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(f"exit {proc.returncode}: {proc.stderr.strip()[:200]}")
        return json.loads(proc.stdout)
    if transport == "http":
        return _http_query(spec, ctx, timeout)
    raise RuntimeError(f"unbekannter Transport {transport!r}")


def query_provider(spec: dict, ctx: dict, timeout: float,
                   reg_defaults: dict | None = None, breakers: dict | None = None) -> dict:
    started = time.time()
    transport = spec.get("transport", "mcp_stdio")
    defaults = reg_defaults or {}
    cb = defaults.get("circuit_breaker", {}) or {}
    cooldown = float(cb.get("cooldown_seconds", 900))
    retries = int(cb.get("retries", 2))
    base_backoff = float(cb.get("backoff_seconds", 3))
    if breakers is None:
        breakers = load_breakers()
    open_now, reason = breaker_open(spec, breakers, cooldown)
    if open_now:
        return {"source": spec["id"], "status": "skipped", "error": reason,
                "items": [], "elapsed_s": 0.0, "provider_status": None}
    # Kontingent je Quelle und Stunde (Muster tau2-bench: Kapazitaetslimit pro Provider)
    quota = effective_quota(spec)
    if quota:
        calls = load_calls().get(spec["id"]) or {}
        hour_ago = time.time() - 3600
        recent = [t for t in (calls.get("recent") or []) if t > hour_ago]
        if len(recent) >= int(quota):
            return {"source": spec["id"], "status": "skipped",
                    "error": f"Kontingent erschoepft: {len(recent)}/{int(quota)} Aufrufe in der "
                             f"letzten Stunde - Quelle wird nicht belastet",
                    "items": [], "elapsed_s": 0.0, "provider_status": None}
    # Governor: eine Quelle, die gerade abgefragt wurde, nicht sofort erneut fragen
    min_interval = float(spec.get("min_interval_seconds", 0) or 0)
    if min_interval > 0:
        last = (load_calls().get(spec["id"]) or {}).get("ts")
        if last:
            left = min_interval - (time.time() - float(last))
            if left > 0:
                return {"source": spec["id"], "status": "skipped",
                        "error": f"Rate-Limit-Governor: Quelle wurde vor {int(left)} s "
                                 f"abgefragt (min. Abstand {int(min_interval)} s)",
                        "items": [], "elapsed_s": 0.0, "provider_status": None}
    try:
        payload = _call_transport(spec, transport, ctx, timeout)
        note_call(spec)
        if spec.get("max_calls_per_hour"):
            quota_adjust(spec, load_quotas(), throttled=False)
    except Exception as exc:
        error = str(exc)
        # Raten-Limit/Temporaerfehler: mit Backoff + Jitter erneut versuchen
        attempt = 0
        while is_transient(error) and attempt < retries:
            attempt += 1
            delay = base_backoff * (2 ** attempt) * (0.7 + 0.6 * random.random())
            time.sleep(delay)
            try:
                payload = _call_transport(spec, transport, ctx, timeout)
                breaker_reset(spec, breakers)
                save_breakers(breakers)
                note_call(spec)
                quota_adjust(spec, load_quotas(), throttled=False)
                break
            except Exception as exc2:
                error = str(exc2)
                if is_transient(error):
                    quota_adjust(spec, load_quotas(), throttled=True)
        else:
            # Nur echte Quellenfehler sperren. Ein Eingabefehler (ungültiger Ort,
            # fehlendes Datum) ist kein Ausfall der Quelle - und darf sie nicht
            # für Minuten blockieren.
            if is_transient(error):
                breaker_trip(spec, breakers, error, cooldown)
                save_breakers(breakers)
            return {"source": spec["id"], "status": "error", "error": error[:400],
                    "items": [], "elapsed_s": round(time.time() - started, 2),
                    "retries": attempt, "provider_status": None}

    payload = _expand_json_strings(payload)
    followup = spec.get("followup")
    if followup and followup.get("mode") == "batch":
        # Sammel-Follow-up: IDs aller Seeds in EINEM Aufruf (z. B. Raten je Hotel)
        seeds = get_path(payload, followup.get("seed_path", "data"), None)
        if not isinstance(seeds, list):
            seeds = []
        id_field = followup.get("ids_field", "id")
        ids = [s.get(id_field) for s in seeds if isinstance(s, dict) and s.get(id_field)]
        args: dict[str, Any] = {}
        for key, tpl in (followup.get("args_template") or {}).items():
            if tpl == "{ids}":
                args[key] = ids[: int(followup.get("max_items", 5))]
            else:
                args[key] = render(tpl, ctx)
        args = coerce_params(args, spec.get("coerce"))
        try:
            payload = _call_tool(spec.get("transport", "mcp_http"), spec, followup["tool"], args, timeout)
        except Exception as exc:
            breaker_trip(spec, breakers, str(exc), cooldown)
            save_breakers(breakers)
            return {"source": spec["id"], "status": "error",
                    "error": f"Follow-up fehlgeschlagen: {str(exc)[:300]}",
                    "items": [], "elapsed_s": round(time.time() - started, 2),
                    "provider_status": None}
        # Suchtreffer (Hotelname, Koordinaten) mit der Ratenantwort verschmelzen
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            seed_by_id = {s.get(id_field): s for s in seeds if isinstance(s, dict)}
            merged_items = []
            for item in payload["data"]:
                if not isinstance(item, dict):
                    continue
                seed = seed_by_id.get(item.get("hotelId")) or seed_by_id.get(item.get("id")) or {}
                combined = dict(seed)
                combined.update(item)
                merged_items.append(combined)
            payload = {**payload, "data": merged_items}
    elif followup:
        items = _run_followup(spec, followup, payload, ctx, timeout)
        return {"source": spec["id"], "status": "ok", "error": None, "items": items,
                "elapsed_s": round(time.time() - started, 2), "dropped_zero_price": 0,
                "provider_status": None}
    extract = spec.get("extract", {}) or {}
    items_path = extract.get("items_path")
    raw_items = get_path(payload, items_path, None)
    if isinstance(raw_items, str):
        try:
            raw_items = json.loads(raw_items)
        except Exception:
            raw_items = None
    if raw_items is None and isinstance(payload, dict):
        raw_items = payload.get("flights") or payload.get("hotels") or payload.get("results")
    if isinstance(raw_items, str):
        try:
            raw_items = json.loads(raw_items)
        except Exception:
            raw_items = None
    if not isinstance(raw_items, list):
        raw_items = []
    # Rueckfallebene: Manche Server antworten je nach Aufruf strukturiert, mal nur
    # als Text. Ohne Rueckfall wuerde das als "0 Angebote" enden (terminal != fertig).
    fallback = extract.get("fallback")
    if fallback and not raw_items:
        text = payload.get("__raw_text__", "") if isinstance(payload, dict) else str(payload)
        if fallback.get("parser") == "table":
            fb_items = parse_markdown_table(text, fallback.get("table", {}), spec["id"],
                                          spec.get("category", "unknown"))
            raw_items = fb_items
            if fb_items:
                items = [normalize_item(it, fallback, spec["id"], spec.get("category", "unknown"))
                         for it in fb_items]
                items = [it for it in items if it.get("price") is not None]
                return {"source": spec["id"], "status": "ok", "error": None, "items": items,
                        "elapsed_s": round(time.time() - started, 2), "dropped_zero_price": 0,
                        "extraction": "fallback_table", "provider_status": None}
    if extract.get("parser") == "text":
        text = payload.get("__raw_text__", "") if isinstance(payload, dict) else str(payload)
        items = parse_text_prices(text, extract.get("text", {}), spec["id"],
                                 spec.get("category", "unknown"))
        return {"source": spec["id"], "status": "ok", "error": None, "items": items,
                "elapsed_s": round(time.time() - started, 2), "dropped_zero_price": 0,
                "provider_status": None}
    if extract.get("parser") == "table":
        if isinstance(payload, dict):
            text = payload.get("__raw_text__") or ""
        else:
            text = payload if isinstance(payload, str) else str(payload)
        if re.search(r"rate.?limit|error\s*1015|access denied|forbidden|too many requests",
                     text, re.I):
            return {"source": spec["id"], "status": "error",
                    "error": f"Antwort ist eine Fehlerseite: {text.strip()[:220]}",
                    "items": [], "elapsed_s": round(time.time() - started, 2),
                    "provider_status": None}
        items = parse_markdown_table(text, extract.get("table", {}), spec["id"],
                                    spec.get("category", "unknown"))
        return {"source": spec["id"], "status": "ok", "error": None, "items": items,
                "elapsed_s": round(time.time() - started, 2), "dropped_zero_price": 0,
                "provider_status": None}
    expand = extract.get("expand")
    items: list[dict] = []
    if expand:
        raw_path = expand.get("path", "rates")
        path_parts = raw_path if isinstance(raw_path, list) else [raw_path]
        for parent in raw_items:
            if not isinstance(parent, dict):
                continue
            for leaf in _expand_leaves(parent, path_parts):
                items.append(normalize_expanded(parent, leaf, expand, spec["id"],
                                               spec.get("category", "unknown")))
    else:
        items = [normalize_item(it, extract, spec["id"], spec.get("category", "unknown"))
                 for it in raw_items if isinstance(it, dict)]
    items = [it for it in items if it.get("price") is not None]
    # Preis-0-Eintraege sind Platzhalter (kein buchbarer Preis) -> verwerfen
    zero_before = len(items)
    items = [it for it in items if (it.get("price") or 0) > 0 or spec.get("allow_zero_price", False)]
    dropped_zero = zero_before - len(items)
    fallback_ccy = ctx.get("currency") or (reg_defaults.get("currency") if reg_defaults else None)
    adults = ctx.get("adults")
    try:
        adults = max(1, int(adults))
    except Exception:
        adults = 1
    scope = spec.get("price_scope", "per_person")
    scope_confidence = spec.get("price_scope_confidence", "confirmed")
    nights = ctx.get("nights")
    if nights is None:
        try:
            from datetime import date as _d
            nights = (_d.fromisoformat(str(ctx["return_date"])) -
                      _d.fromisoformat(str(ctx["depart_date"]))).days
        except Exception:
            nights = 1
    try:
        nights = max(1, int(nights))
    except Exception:
        nights = 1
    for it in items:
        if not it.get("currency"):
            it["currency"] = fallback_ccy
        # Preis auf eine vergleichbare Basis bringen: pro Person.
        raw = it.get("price_raw", it.get("price"))
        it["price_scope"] = scope
        it["price_scope_confidence"] = scope_confidence
        it["rankable"] = scope_confidence != "unverified"
        it["price_total"] = raw
        if scope == "total" and raw is not None:
            it["price"] = raw / adults          # Gesamtpreis -> je Person
            it["price_per_person"] = it["price"]
            it["price_total"] = raw
        elif scope == "per_stay" and raw is not None:
            it["price"] = raw / nights          # Aufenthaltssumme -> je Nacht
            it["price_per_night"] = it["price"]
            it["price_total"] = raw
        else:
            it["price"] = raw
            it["price_per_person"] = raw
            it["price_total"] = raw * adults if raw is not None else None
    return {"source": spec["id"], "status": "ok", "error": None, "items": items,
            "elapsed_s": round(time.time() - started, 2),
            "dropped_zero_price": dropped_zero,
            "provider_status": _provider_status(payload)}


def _run_followup(spec: dict, followup: dict, payload: Any, ctx: dict, timeout: float) -> list[dict]:
    """Zweiter Aufruf je Erstangebot (z. B. Suche -> Raten/Detail holen).

    Erwartet wird eine Antwort mit `results`/`hotels`/`items`; pro Element wird der
    Follow-up-Parameter aus `args_template` gesetzt ({item.<feld>} + Kontext) und die
    Antwort des Follow-ups als Angebot übernommen.
    """
    transport = spec.get("transport", "mcp_http")
    tool = followup.get("tool")
    tmpl = followup.get("args_template") or {}
    extract = spec.get("extract", {}) or {}
    seed_path = followup.get("seed_path", "results")
    seeds = get_path(payload, seed_path, None)
    if not isinstance(seeds, list):
        seeds = payload.get("hotels") if isinstance(payload, dict) else None
    if not isinstance(seeds, list):
        return []
    out: list[dict] = []
    for seed in seeds[: int(followup.get("max_items", 5))]:
        if not isinstance(seed, dict):
            continue
        args = {}
        for key, tpl in tmpl.items():
            val = tpl
            if isinstance(val, str):
                if val.startswith("{item."):
                    val = seed.get(val[6:-1])
                else:
                    for ck, cv in ctx.items():
                        val = val.replace("{" + ck + "}", "" if cv is None else str(cv))
            args[key] = val
        try:
            resp = _call_tool(transport, spec, tool, args, timeout)
        except Exception:
            continue
        if not isinstance(resp, dict):
            continue
        merged = dict(seed)
        merged.update(resp if isinstance(resp, dict) else {})
        item = normalize_item(merged, extract, spec["id"], spec.get("category", "unknown"))
        if item.get("price") is not None:
            out.append(item)
    return out


def _call_tool(transport: str, spec: dict, tool: str, args: dict, timeout: float) -> Any:
    if transport == "mcp_stdio":
        client = MCPStdioClient(list(spec["command"]), name=spec["id"], timeout=timeout)
        try:
            return client.call_tool(tool, args, timeout=timeout)
        finally:
            client.close()
    if transport == "mcp_http":
        client = MCPHttpClient(spec["url"], name=spec["id"], timeout=timeout,
                               headers=spec.get("headers"))
        return client.call_tool(tool, args, timeout=timeout)
    raise RuntimeError(f"followup nicht unterstützt für Transport {transport!r}")


def _expand_leaves(parent: dict, path_parts: list[str]) -> list[dict]:
    """Mehrebenen-Expansion: Hotel -> roomTypes[] -> rates[]."""
    if not path_parts:
        return [parent]
    part = path_parts[0]
    children = get_path(parent, part, None)
    if not isinstance(children, list):
        return []
    out: list[dict] = []
    for child in children:
        if isinstance(child, dict):
            out.extend(_expand_leaves(child, path_parts[1:]))
    return out


def _expand_json_strings(payload: Any, _depth: int = 0) -> Any:
    """Hüllen, die JSON als String enthalten, werden einmalig eingepackt."""
    if _depth > 3:
        return payload
    if isinstance(payload, dict):
        out = {}
        for k, v in payload.items():
            if isinstance(v, str) and v.strip()[:1] in "{[":
                try:
                    v = json.loads(v)
                except Exception:
                    pass
            out[k] = _expand_json_strings(v, _depth + 1)
        return out
    if isinstance(payload, list):
        return [_expand_json_strings(v, _depth + 1) for v in payload]
    return payload


def _provider_status(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return None
    for key in ("provider_statuses", "provider_status"):
        if key in payload:
            return payload[key]
    return None


def _http_query(spec: dict, ctx: dict, timeout: float) -> Any:
    import requests
    url = render(spec["url"], ctx)
    method = spec.get("method", "GET").upper()
    headers = {k: render(v, ctx) for k, v in (spec.get("headers") or {}).items()}
    params = {k: render(v, ctx) for k, v in (spec.get("params") or {}).items()
              if render(v, ctx) is not None}
    body = spec.get("body")
    body = render(body, ctx) if body else None
    resp = requests.request(method, url, headers=headers, params=params, json=body,
                            timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------- Runner
def _categories(spec: dict) -> list[str]:
    """Kategorie(n) einer Quelle - String oder Liste."""
    cat = spec.get("category")
    if isinstance(cat, list):
        return [str(c) for c in cat]
    return [str(cat)]


def run(reg: dict, category: str, ctx: dict, only: list[str] | None = None,
        rank_by: str | None = None, progress=None) -> dict:
    """category darf eine einzelne Kategorie oder eine kommagetrennte Liste sein.

    `progress(category, provider_result)` wird nach jeder abgeschlossenen Quelle
    aufgerufen (fuer die Webober: Live-Anzeige der Quellenlage). Ohne Callback
    verhaelt sich die Funktion exakt wie bisher.
    """
    cats = [c.strip() for c in str(category).split(",") if c.strip()]
    if len(cats) > 1:
        parts = [run(reg, c, ctx, only=only, rank_by=rank_by) for c in cats]
        merged_items: list[dict] = []
        providers: list[dict] = []
        for part in parts:
            merged_items.extend(part.get("ranked") or [])
            providers.extend(part.get("providers") or [])
        merged_items.sort(key=lambda it: rank_key(
            it, rank_by or (reg.get("defaults", {}) or {}).get("rank_by", "price"), 1))
        rankable = [it for it in merged_items if it.get("rankable", True)]
        return {
            "category": ",".join(cats),
            "requested_at": parts[0].get("requested_at"),
            "context": parts[0].get("context"),
            "providers": providers,
            "totals": {"providers": len(providers),
                        "ok": sum(1 for p in providers if p["status"] == "ok"),
                        "failed": sum(1 for p in providers if p["status"] != "ok"),
                        "items": len(merged_items)},
            "ranked": rankable[:50],
            "ranked_unverified_scope": [it for it in merged_items if not it.get("rankable", True)][:10],
            "cheapest": rankable[0] if rankable else None,
            "note_price_scope": parts[0].get("note_price_scope"),
            "per_category": {c: {"totals": p["totals"], "cheapest": p["cheapest"]} for c, p in zip(cats, parts)},
        }

    defaults = reg.get("defaults", {}) or {}
    timeout = float(ctx.get("_timeout") or defaults.get("timeout_seconds", 180))
    workers = int(defaults.get("max_workers", 8))
    candidates = [s for s in reg.get("providers", [])
                  if category in _categories(s) and s.get("enabled", True)
                  and (not only or s.get("id") in only)]
    # Quellenrechte: gesperrte Quellen (z. B. Google-Scraper) nicht anzeigen.
    specs = filter_providers(candidates)
    results: list[dict] = []
    with futures.ThreadPoolExecutor(max_workers=workers) as pool:
        fut_map = {pool.submit(query_provider, s, ctx, timeout, defaults): s for s in specs}
        for fut in futures.as_completed(fut_map):
            res = fut.result()
            results.append(res)
            if progress is not None:
                try:
                    progress(category, res)
                except Exception:
                    pass          # Fortschritt darf den Lauf nie beeintraechtigen
    results.sort(key=lambda r: r["source"])

    all_items: list[dict] = []
    for r in results:
        all_items.extend(r["items"])

    # ---- Plausibilitaetspruefung: kaputte Preise (z. B. 0,01 EUR) duerfen nicht
    # in den Vergleich. Betroffene Angebote werden verworfen, die Quelle wird als
    # korrupt gemeldet und ihre uebrigen Tarife ebenfalls nicht verwendet.
    plaus_cfg = (defaults.get("plausibility") or {})
    plaus = plausibility_screen(all_items, plaus_cfg, category) if plaus_cfg.get("enabled", True) else {
        "rejected": [], "corrupt": {}, "kept_sources": [], "median": None, "sources_compared": 0}
    if plaus["rejected"]:
        corrupt_sources = set(plaus["corrupt"].keys())
        for r in results:
            if r["source"] in corrupt_sources:
                r["status"] = "corrupt"
                r["error"] = message_for_source(r["source"], plaus["corrupt"][r["source"]])
                r["items"] = []          # Angebote dieser Quelle nicht verwenden
        all_items = [it for it in all_items if it.get("source") not in corrupt_sources]
    merged = dedupe(all_items)
    # Multi-Kriterien-Score je Angebot (Gates als Ausschluss, Gewichte aus der Registry)
    score_cfg = (defaults.get("scoring") or {})
    if score_cfg.get("enabled", True):
        score_offers(merged, score_cfg, ctx.get("score_profile") or defaults.get("score_profile"))
    # Waehrungen angleichen: ohne belegten Kurs wird NICHT umgerechnet (Kennzeichnung folgt)
    target_ccy = str(ctx.get("currency") or defaults.get("currency") or "EUR").upper()
    fx_used: dict[str, dict] = {}
    for it in merged:
        ccy = str(it.get("currency") or "").upper()
        if not ccy:
            # Quelle liefert kein Waehrungsfeld -> Zielwaehrung der Anfrage annehmen
            it["currency_original"] = it.get("currency")
            it["currency"] = target_ccy
            it["currency_inferred"] = True
            continue
        if ccy == target_ccy:
            it["currency_original"] = it.get("currency")
            continue
        rate_info = fx_used.get(ccy)
        if rate_info is None:
            rate_info = fx_rate(ccy, target_ccy)
            fx_used[ccy] = rate_info
        factor = rate_info.get("rate")
        if factor:
            it["price_original"] = it.get("price")
            it["price_total_original"] = it.get("price_total")
            if it.get("price") is not None:
                it["price"] = it["price"] * factor
            if it.get("all_in") is not None:
                it["all_in"] = it["all_in"] * factor
            if it.get("price_total") is not None:
                it["price_total"] = it["price_total"] * factor
            it["currency"] = target_ccy
            it["fx_rate"] = factor
            it["fx_source"] = rate_info.get("source")
            it["fx_converted_from"] = ccy
        else:
            it["currency_comparable"] = False
            it["fx_error"] = rate_info.get("error")
    try:
        from datetime import date as _d
        _nights = (_d.fromisoformat(str(ctx.get("return_date"))) -
                   _d.fromisoformat(str(ctx.get("depart_date")))).days
    except Exception:
        _nights = 1
    merged.sort(key=lambda it: rank_key(it, rank_by or defaults.get("rank_by", "price"), _nights))
    # Angebote mit unbestätigter Preisbasis werden ausgewiesen, aber nicht als
    # "günstigste" gewertet (sonst würde ein ungeklärter Preis den Vergleich bestimmen).
    rankable = [it for it in merged if it.get("rankable", True)]
    cheapest = rankable[0] if rankable else None
    # Kontingent je Quelle fuer die Ausgabe (aus der Registry, adaptiv berechnet)
    quota_by_source = {}
    for spec in specs:
        if spec.get("max_calls_per_hour"):
            quota_by_source[spec["id"]] = effective_quota(spec)
    return {
        "category": category,
        "requested_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "context": {k: v for k, v in ctx.items() if not k.startswith("_")},
        "providers": [{"source": r["source"], "status": r["status"], "error": r["error"],
                       "items": len(r["items"]), "elapsed_s": r["elapsed_s"],
                       "retries": r.get("retries", 0),
                       "quota_per_hour": quota_by_source.get(r["source"]),
                       "currency": (r.get("items_sample") or {}).get("currency"),
                       "dropped_zero_price": r.get("dropped_zero_price", 0)} for r in results],
            "scoring": {"profile": ctx.get("score_profile") or defaults.get("score_profile"),
                        "weights": (defaults.get("scoring") or {}).get("weights", {})},
            "price_plausibility": {
                "checked": bool(plaus_cfg.get("enabled", True)),
                "category": category,
                "floor": plaus.get("floor"),
                "market_median": plaus.get("median"),
                "sources_compared": plaus.get("sources_compared"),
                "rejected": plaus.get("rejected", []),
                "corrupt_sources": sorted(plaus.get("corrupt", {}).keys()),
                "message": message_global(plaus.get("rejected", []), plaus.get("corrupt", {})),
            },
        "totals": {"providers": len(results),
                    "ok": sum(1 for r in results if r["status"] == "ok"),
                    "failed": sum(1 for r in results if r["status"] != "ok"),
                    "items": len(merged)},
        "ranked": rankable[:25],
        "ranked_unverified_scope": [it for it in merged if not it.get("rankable", True)][:10],
        "cheapest": cheapest,
        "note_price_scope": {
            "per_person": "Preise je Person (für Flüge)",
            "total": "Preis für alle Reisenden (Summe der Personen)",
            "per_night": "Preis je Nacht und Zimmer (Hotels)",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                        "registry.yaml"))
    ap.add_argument("--category", required=True,
                    help="flights | hotels | ferries | cruises – oder kommagetrennt (flights,hotels)")
    ap.add_argument("--request", help="JSON-Datei mit dem Kontext (alternativ zu --origin ...)")
    ap.add_argument("--only", nargs="*", help="nur diese Provider-IDs abfragen")
    ap.add_argument("--rank-by", choices=["price", "all_in", "score", "value"])
    ap.add_argument("--out", help="Ergebnis als JSON in Datei schreiben")
    ap.add_argument("--score-profile", choices=["budget", "comfort"], default=None,
                    help="Gewichtungsprofil des Angebots-Scores")
    for key, default in (("origin", None), ("destination", None), ("depart-date", None),
                         ("return-date", None), ("adults", None), ("children", None),
                         ("currency", "EUR"), ("hotel-stars", None), ("max-stops", "one_stop"),
                         ("query", None), ("nights", None), ("city", None)):
        ap.add_argument(f"--{key}", default=default)
    args = ap.parse_args()

    reg = load_registry(args.registry)
    ctx: dict[str, Any] = {}
    if args.request:
        ctx.update(json.load(open(args.request, encoding="utf-8")))
    mapping = {"origin": args.origin, "destination": args.destination,
               "score_profile": args.score_profile,
               "depart_date": args.depart_date, "return_date": args.return_date,
               "adults": args.adults, "children": args.children, "currency": args.currency,
               "hotel_stars": args.hotel_stars, "max_stops": args.max_stops,
               "query": args.query, "nights": args.nights, "city": args.city}
    for k, v in mapping.items():
        if v is not None and k not in ctx:
            ctx[k] = v
    ctx = {k: v for k, v in ctx.items() if v is not None}
    # Standardwerte, damit Kommandozeilen (CLI-Quellen) keine leeren Argumente bekommen
    ctx.setdefault("children", 0)

    out = run(reg, args.category, ctx, only=args.only, rank_by=args.rank_by)
    text = json.dumps(out, ensure_ascii=False, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
