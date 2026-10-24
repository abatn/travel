#!/usr/bin/env python3
"""Weboberfläche des Reise-Agent-Systems (FastAPI + Jinja2).

Start:
    python3 -m uvicorn ui.app:app --host 127.0.0.1 --port 8077
    # oder: bash ui/start.sh

Alle Reiselogik kommt aus den vorhandenen Modulen (providers/runner.py,
bundling/compare.py, alerts/watcher.py) - siehe ui/service.py.
Buchen: die Oberfläche fuehrt zum Anbieter (Buchungslink); eine Zahl- oder
Ticketfunktion hat das System bewusst nicht (siehe README).
"""
from __future__ import annotations

import html as html_lib
import os
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import FastAPI, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
import sys  # noqa: E402

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "seo"))
import service  # noqa: E402
import meta as seo_meta  # noqa: E402
import jsonld as seo_jsonld  # noqa: E402
import pages as seo_pages  # noqa: E402
import routes_cache  # noqa: E402
import sitemap as seo_sitemap  # noqa: E402
import legal_config  # noqa: E402
import i18n as i18n_core  # noqa: E402

app = FastAPI(title="Reise-Agent UI", version="1.2",
              docs_url=None, redoc_url=None, openapi_url=None)   # S6: keine API-Docs
app.add_middleware(GZipMiddleware, minimum_size=500)
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))

@app.middleware("http")
async def _i18n_middleware(request, call_next):
    """Sprache auflösen (Query/Cookie/Header), Cookie setzen, Cache steuern."""
    lang = i18n_core.resolve(request)
    request.state.lang = lang
    response = await call_next(request)
    response.headers["Content-Language"] = lang
    if i18n_core.swatch_update_needed(request, lang):
        response.set_cookie(i18n_core.COOKIE, lang, max_age=31536000,
                            samesite="lax", path="/")
    if request.url.path in ("/", "/impressum", "/datenschutz", "/llms.txt",
                            "/.well-known/agent-payments.json", "/capabilities"):
        response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
        response.headers["Vary"] = "Cookie, Accept-Language"
    return response



@app.middleware("http")
async def seo_headers(request: Request, call_next):
    """Cache-Regeln: statische Dateien lange, HTML kurz (Preise ändern sich)."""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "public, max-age=86400")
    elif path.startswith("/alarms"):
        # S10: private Inhalte nicht cachen
        response.headers["Cache-Control"] = "private, no-store"
    elif response.headers.get("content-type", "").startswith("text/html"):
        response.headers.setdefault("Cache-Control", "public, max-age=60, must-revalidate")
    if path.startswith("/api/") or path == "/health":
        # S13: zweite Ebene gegen Indexierung technischer Endpunkte
        response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


# --- M2: x402-Preis-Attestierungen ----------------------------------------
# Optional: benoetigt x402 (siehe attest/README.md). Fehlt das Paket, laeuft
# die UI unveraendert weiter; /api/attest ist dann nicht vorhanden.
ATTEST_ENABLED = False
try:
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from attest.routes import install as _install_attest  # noqa: E402

    ATTEST_ENABLED = _install_attest(app)
except Exception as _attest_exc:  # noqa: BLE001
    print(f"[attest] deaktiviert: {_attest_exc}")


def _base(request: Request) -> str:
    """Absolute Basis-URL (für kanonische Links, Sitemap, JSON-LD).

    S1: Vorrang hat SITE_URL (z. B. https://reise.example) - hinter Proxy/CDN ist
    request.base_url sonst intern (http, falscher Host). Fallback nur für Dev.
    """
    configured = os.environ.get("SITE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    return str(request.base_url).rstrip("/")


def _render(request: Request, template: str, context: dict, meta: dict,
            jsonld: list | None = None, status_code: int = 200):
    lang = getattr(request.state, "lang", i18n_core.DEFAULT)
    meta = dict(meta)
    meta["lang"] = lang
    meta["og_locale"] = {"de": "de_DE", "en": "en_US", "fr": "fr_FR",
                         "es": "es_ES", "ar": "ar_AR"}.get(lang, "de_DE")
    ctx = {"request": request, "meta": meta,
           "jsonld": [seo_jsonld.to_script_tag(x) for x in (jsonld or []) if x],
           "t": i18n_core.translator(lang), "lang": lang,
           "dir": i18n_core.direction(lang),
           "supported_langs": i18n_core.SUPPORTED,
           "i18n_js": i18n_core.load(lang)}
    ctx.update(context)
    return templates.TemplateResponse(request, template, ctx, status_code=status_code)


def _fmt(value, currency: str | None = None) -> str:
    if value is None:
        return "nicht verfügbar"
    try:
        text = f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(value)
    return f"{text} {currency}" if currency else text


def _safe_url(url: str | None) -> str | None:
    """Nur http(s)-Links uebernehmen (kein javascript:/data:)."""
    if not url:
        return None
    url = str(url).strip()
    if url.startswith("https://") or url.startswith("http://"):
        return url
    return None


templates.env.filters["money"] = _fmt
templates.env.globals["safe_url"] = _safe_url


def _asset_v(name: str) -> str:
    """Cache-Busting: Änderungszeit der Datei als ?v=..."""
    try:
        return str(int(os.path.getmtime(os.path.join(HERE, "static", name))))
    except Exception:
        return "1"


templates.env.globals["asset_v"] = _asset_v


@app.get("/", response_class=HTMLResponse)
def search_form(request: Request):
    today = date.today()
    base = _base(request)
    meta = seo_meta.build(
        "Flüge, Hotels, Fähren, Kreuzfahrten – Reise-Agent",
        ("Live-Preise aus über 20 Quellen für Flüge, Hotels, Fähren und Kreuzfahrten. "
         "Endpreis, Steuerstatus und Quellenlage transparent – ohne Anmeldung."),
        "/", base_url=base)
    return _render(request, "search.html", {
        "categories": service.CATEGORIES,
        "labels": service.CATEGORY_LABELS,
        "default_depart": (today + timedelta(days=7)).isoformat(),
        "default_return": (today + timedelta(days=9)).isoformat(),
        "status": service.source_status(),
        "landing_links": [(slug, cfg["h1"]) for slug, cfg in seo_pages.CATEGORIES.items()],
    }, meta, [
        seo_jsonld.website(base),
        seo_jsonld.organization(base),
        seo_jsonld.breadcrumb(base, [("Start", "/")]),
    ])


def _route_entries(category_key: str, slug: str) -> list[dict]:
    out = []
    for data in routes_cache.list_routes(category_key):
        f = routes_cache.facts(data)
        out.append({"slug": (data.get("_route") or "").lower(),
                    "origin": data.get("origin"), "destination": data.get("destination"),
                    "origin_name": data.get("origin_name"),
                    "destination_name": data.get("destination_name"),
                    "date": (data.get("generated_at") or "")[:10],
                    "cheapest": f.get("min_price"), "currency": f.get("currency"),
                    "data": data})
    return out


def _offers_for_view(data: dict | None) -> list[dict]:
    """Zwischengespeicherte Angebote für die Anzeige (mit Affiliate-Prüfung)."""
    if not data:
        return []
    out = []
    for o in (data.get("offers") or [])[:10]:
        link = service.decorate_link(o.get("url")) or {}
        out.append({**o,
                    "url": link.get("url") or o.get("url"),
                    "affiliate": bool(link.get("affiliate")),
                    "verified": bool(link.get("verified"))})
    return out


def _landing(request: Request, slug: str):
    page = seo_pages.CATEGORIES[slug]
    base = _base(request)
    routes = _route_entries(page["key"], slug)
    newest = routes[0]["data"] if routes else None
    # S2: Kategorieseite ist ein Hub - keine Preistabelle (sonst 85 % Duplicate
    # mit der Routenseite). Preise stehen nur auf der Routenseite.
    offers_all = _offers_for_view(newest)
    offers = []
    generated = (newest or {}).get("generated_at")
    stale = bool(newest and (routes_cache.age_hours(newest) or 0) > 24)
    tz_offset = 0
    if generated:
        try:
            tz_offset = int(datetime.fromisoformat(generated).utcoffset().total_seconds() // 3600)
        except Exception:
            tz_offset = 0
    route_label = (f"{newest.get('origin')} → {newest.get('destination')}"
                   if newest else None)
    meta = seo_meta.for_landing(base, slug, page)
    breadcrumb = seo_jsonld.breadcrumb(base, [("Start", "/"), (page["h1"], f"/{slug}")])
    blocks = [breadcrumb, seo_jsonld.faq(page["faq"])]
    # Kein Offer-JSON-LD auf der Kategorieseite (keine Preise im HTML).
    return _render(request, "landing.html", {
        "slug": slug, "page": page, "offers": offers, "offers_total": len(offers_all),
        "routes": routes, "facts": {},
        "generated_at": (generated or "")[:19].replace("T", " "),
        "tz_offset": tz_offset, "stale": stale, "route": bool(newest),
        "route_label": route_label,
        "preset": page.get("presets", {}),
        "action_label": f"Jetzt {page['h1'].lower()}",
        "default_depart": (date.today() + timedelta(days=7)).isoformat(),
        "default_return": (date.today() + timedelta(days=9)).isoformat(),
        "other_categories": [(s, c) for s, c in seo_pages.CATEGORIES.items() if s != slug],
        "affiliate": service.affiliate_info(),
    }, meta, blocks)


@app.get("/preisvergleich", response_class=HTMLResponse)
def overview_page(request: Request):
    base = _base(request)
    meta = seo_meta.build(seo_pages.OVERVIEW_TITLE, seo_pages.OVERVIEW_DESCRIPTION,
                          f"/{seo_pages.OVERVIEW_SLUG}", base_url=base)
    cats = [(slug, cfg) for slug, cfg in seo_pages.CATEGORIES.items()]
    return _render(request, "overview.html", {
        "categories": cats, "default_depart": (date.today() + timedelta(days=7)).isoformat(),
        "default_return": (date.today() + timedelta(days=9)).isoformat(),
    }, meta, [seo_jsonld.website(base), seo_jsonld.organization(base),
              seo_jsonld.breadcrumb(base, [("Start", "/"),
                                           ("Preisvergleich", f"/{seo_pages.OVERVIEW_SLUG}")])])


for _slug in seo_pages.CATEGORIES:
    def _make(slug=_slug):
        def view(request: Request):
            return _landing(request, slug)
        return view
    app.add_api_route(f"/{_slug}", _make(), methods=["GET"], response_class=HTMLResponse)


def _route_view(request: Request, slug: str, route: str):
    page = seo_pages.CATEGORIES[slug]
    data = routes_cache.load(page["key"], route.upper())
    if not data:
        return HTMLResponse("Für diese Strecke liegen noch keine Preise vor – "
                            "starte eine Suche auf der Kategorieseite.", status_code=404)
    base = _base(request)
    origin_label = data.get("origin_name") or data.get("origin")
    destination_label = data.get("destination_name") or data.get("destination")
    meta = seo_meta.for_route(base, slug, route.lower(), origin_label, destination_label)
    route_age = routes_cache.age_hours(data)
    if route_age is None or route_age > seo_sitemap.STALE_ROUTE_HOURS:
        meta["robots"] = "noindex,follow"      # veraltete Preise nicht indexieren
    label = f"{origin_label} → {destination_label}"
    offers = _offers_for_view(data)
    price_offers = [{"name": o.get("provider") or o.get("name"), "price": o.get("price"),
                     "currency": o.get("currency"), "provider": o.get("provider"),
                     "url": o.get("url"), "route": label, "category": page["h1"]}
                    for o in offers]
    generated = data.get("generated_at") or ""
    stale = (routes_cache.age_hours(data) or 0) > 24
    tz_offset = 0
    try:
        tz_offset = int(datetime.fromisoformat(generated).utcoffset().total_seconds() // 3600)
    except Exception:
        tz_offset = 0
    return _render(request, "landing.html", {
        "slug": slug, "page": {**page, "h1": label,
                               "intro": (f"Aktuelle Preise für {label}. Die Angaben stammen aus dem "
                                         f"letzten Suchlauf; der Preis beim Anbieter ist verbindlich.")},
        "offers": offers, "routes": [], "facts": routes_cache.facts(data),
        "generated_at": generated[:19].replace("T", " "),
        "tz_offset": tz_offset, "stale": stale, "route": True, "route_label": label,
        "preset": {"origin": data.get("origin"), "destination": data.get("destination"),
                   "categories": [page["key"]]},
        "action_label": f"Neue Preise für diese Strecke",
        "default_depart": (date.today() + timedelta(days=7)).isoformat(),
        "default_return": (date.today() + timedelta(days=9)).isoformat(),
        "other_categories": [(s, c) for s, c in seo_pages.CATEGORIES.items() if s != slug],
        "affiliate": service.affiliate_info(),
    }, meta, [
        seo_jsonld.breadcrumb(base, [("Start", "/"), (page["h1"], f"/{slug}"),
                                     (label, f"/{slug}/{route.lower()}")]),
        seo_jsonld.offer_list(base, f"/{slug}/{route.lower()}", price_offers),
        seo_jsonld.aggregate_offer(base, f"/{slug}/{route.lower()}", price_offers),
        seo_jsonld.faq(page["faq"]),
    ])


for _rslug in seo_pages.CATEGORIES:
    def _make_route(slug=_rslug):
        def view(request: Request, route: str):
            return _route_view(request, slug, route)
        return view
    app.add_api_route(f"/{_rslug}/{{route}}", _make_route(), methods=["GET"],
                      response_class=HTMLResponse)


def _legal_data() -> dict:
    """Betreiberangaben laden (ui/legal.yaml). Fehlende Angaben werden nicht erfunden."""
    return legal_config.load()


def _e(value) -> str:
    return html_lib.escape(str(value or ""))


def _legal_page(request: Request, kind: str):
    data = _legal_data()
    b = data.get("betreiber") or {}
    d = data.get("datenschutz") or {}
    configured = legal_config.is_complete(data, kind)
    missing = legal_config.missing(data, kind)
    lang = getattr(request.state, "lang", i18n_core.DEFAULT)
    title = i18n_core.t(lang, "legal.imprint" if kind == "impressum" else "legal.privacy")
    meta = seo_meta.build(
        f"{title} – Reise-Agent",
        ("Anbieterkennzeichnung nach § 5 DDG." if kind == "impressum"
         else "Informationen zur Verarbeitung personenbezogener Daten nach Art. 13 DSGVO."),
        f"/{kind}", base_url=_base(request),
        robots="index,follow" if configured else "noindex,follow")

    content = ""
    if configured and kind == "impressum":
        ust = str(b.get("umsatzsteuer_id") or "").strip()
        ust_html = (
            "<p>Umsatzsteuer-Identifikationsnummer: keine vorhanden.</p>"
            if ust.lower() == "keine"
            else f"<p>Steuer-/Umsatzsteuer-Identifikationsnummer: {_e(ust)}</p>"
        )
        register = ""
        if b.get("registergericht") or b.get("registernummer"):
            register = (f"<p>Registergericht: {_e(b.get('registergericht'))}<br>"
                        f"Registernummer: {_e(b.get('registernummer'))}</p>")
        content = (
            f"<p><b>{_e(b.get('name'))}</b><br>{_e(b.get('strasse'))}<br>"
            f"{_e(b.get('plz_ort'))}<br>{_e(b.get('land'))}</p>"
            f"<p>E-Mail: <a href=\"mailto:{_e(b.get('email'))}\">{_e(b.get('email'))}</a>"
            + (f"<br>Telefon: {_e(b.get('telefon'))}" if b.get("telefon") else "")
            + "</p>"
            + ust_html
            + register
            + f"<p>Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV: "
              f"{_e(b.get('verantwortlich'))}</p>"
            + "<p>Wir vermitteln Reiseleistungen (keine Reiseveranstaltung). Der Vertrag über "
              "jede Leistung kommt ausschließlich mit dem jeweiligen Anbieter zustande.</p>"
            + "<p>Wir sind nicht bereit und nicht verpflichtet, an Streitbeilegungsverfahren "
              "vor einer Verbraucherschlichtungsstelle teilzunehmen.</p>"
        )
    elif configured and kind == "datenschutz":
        verarbeiter = str(d.get("auftragsverarbeiter") or "").strip()
        content = (
            "<p><b>Verantwortlich im Sinne der DSGVO</b><br>"
            f"{_e(b.get('name'))}<br>{_e(b.get('strasse'))}<br>{_e(b.get('plz_ort'))}<br>"
            f"{_e(b.get('land'))}<br>E-Mail: {_e(b.get('kontakt_datenschutz') or b.get('email'))}</p>"
            f"<p><b>Hosting:</b> {_e(d.get('hosting'))}. Server-Logs werden "
            f"{_e(d.get('aufbewahrung_logs'))} gespeichert (Rechtsgrundlage: Art. 6 Abs. 1 "
            "lit. f DSGVO – Sicherheit und Stabilität des Angebots).</p>"
            "<p><b>Zwecke und Rechtsgrundlagen:</b> Suchanfragen und Preisvergleiche "
            "(Art. 6 Abs. 1 lit. b DSGVO), technischer Betrieb und Logs (lit. f), "
            "Preisalarme und E-Mails nur mit Einwilligung (lit. a), gesetzliche "
            "Aufbewahrung (lit. c).</p>"
            "<p><b>Empfänger:</b> Hosting-Dienstleister, E-Mail-Dienstleister, "
            "Affiliate-Netzwerke beim Klick auf einen Buchungslink sowie der x402-Facilitator "
            "zur Zahlungsabwicklung."
            + (f" Weitere Auftragsverarbeiter: {_e(verarbeiter)}." if verarbeiter else "")
            + "</p>"
            "<p><b>x402-Zahlungen:</b> Bei einer Preis-Attestierung wird eine USDC-Zahlung "
            "auf einer öffentlichen Blockchain abgewickelt. Dabei sind Wallet-Adresse, Betrag "
            "und Transaktionshash öffentlich und dauerhaft einsehbar. Wir speichern zur "
            "Buchhaltung zusätzlich Rechnungsdaten (Betrag, Datum, Tx-Hash, Leistung).</p>"
            "<p><b>Affiliate-Links:</b> Beim Klick auf einen Buchungslink wird der Anbieter "
            "aufgerufen; dort gelten dessen Datenschutzbestimmungen. Wir setzen keine eigenen "
            "Marketing-Cookies.</p>"
            "<p><b>Speicherdauer:</b> Logs gemäß oben; Rechnungs- und Buchhaltungsdaten nach "
            "den gesetzlichen Aufbewahrungsfristen (§ 147 AO, in der Regel 8–10 Jahre).</p>"
            "<p><b>Ihre Rechte:</b> Auskunft, Berichtigung, Löschung, Einschränkung, "
            "Datenübertragbarkeit und Widerspruch (Art. 15–21 DSGVO). Eine erteilte "
            "Einwilligung können Sie jederzeit widerrufen.</p>"
            f"<p><b>Beschwerde:</b> {_e(d.get('aufsichtsbehoerde'))}</p>"
            f"<p><b>Stand:</b> {_e(d.get('stand'))}</p>"
        )
    return templates.TemplateResponse(request, "legal.html", {
        "request": request, "meta": meta, "jsonld": [], "title": title,
        "configured": configured, "content": content, "missing": missing,
        "t": i18n_core.translator(lang), "lang": lang,
        "dir": i18n_core.direction(lang),
        "supported_langs": i18n_core.SUPPORTED,
        "i18n_js": i18n_core.load(lang),
        "asset_v": _asset_v})


@app.get("/impressum", response_class=HTMLResponse)
def impressum(request: Request):
    return _legal_page(request, "impressum")


@app.get("/datenschutz", response_class=HTMLResponse)
def datenschutz(request: Request):
    return _legal_page(request, "datenschutz")


@app.get("/sitemap.xml")
def sitemap_xml(request: Request):
    legal = _legal_data()
    extra: list[str] = []
    if legal_config.is_complete(legal, "impressum"):
        extra.append("/impressum")
    if legal_config.is_complete(legal, "datenschutz"):
        extra.append("/datenschutz")
    xml = seo_sitemap.build(_base(request), extra_paths=extra)
    return Response(content=xml, media_type="application/xml",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt(request: Request):
    return PlainTextResponse(seo_sitemap.robots(_base(request)),
                             headers={"Cache-Control": "public, max-age=3600"})


@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt(request: Request):
    """Maschinenlesbare Kurzbeschreibung für Agenten (llms.txt)."""
    path = os.path.join(ROOT, "llms.txt")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError:
        return PlainTextResponse("llms.txt fehlt.\n", status_code=404)
    text = text.replace("{{BASE_URL}}", _base(request))
    try:
        from attest.config import load_settings as _load_attest_settings

        attest_settings = _load_attest_settings()
        text = (text
                .replace("{{PRICE}}", attest_settings.price.lstrip("$€").strip())
                .replace("{{NETWORK}}", attest_settings.network)
                .replace("{{ASSET}}", attest_settings.resolved_asset())
                .replace("{{PAY_TO}}", attest_settings.pay_to))
    except Exception:  # noqa: BLE001
        pass
    contact = str(((legal_config.load().get("betreiber") or {}).get("email")) or "").strip()
    text = text.replace("{{CONTACT_EMAIL}}", contact or "siehe /impressum")
    lang = getattr(request.state, "lang", i18n_core.DEFAULT)
    if lang != "de":
        intro = (
            f"# Reise-Agent ({i18n_core.t(lang, 'lang.name.' + lang)})\n\n"
            f"> {i18n_core.t(lang, 'discovery.description')}\n\n"
            f"> {i18n_core.t(lang, 'legal.notice')}\n\n---\n\n"
        )
        text = intro + text
    return PlainTextResponse(text, media_type="text/plain; charset=utf-8",
                             headers={"Cache-Control": "public, max-age=300"})


@app.post("/api/search")
async def api_search(request: Request):
    form = await request.form()
    params = {
        "origin": (form.get("origin") or "BER").strip(),
        "destination": (form.get("destination") or "FCO").strip(),
        "city": (form.get("city") or form.get("destination") or "").strip(),
        "depart_date": (form.get("depart_date") or "").strip(),
        "return_date": (form.get("return_date") or "").strip(),
        "adults": int(form.get("adults") or 1),
        "children": int(form.get("children") or 0),
        "currency": (form.get("currency") or "EUR").strip().upper(),
        "max_stops": (form.get("max_stops") or "one_stop").strip(),
        "hotel_stars": int(form.get("hotel_stars") or 4),
        "budget": float(form.get("budget") or 0) or None,
        "categories": [c for c in (form.getlist("categories") or ["flights"])],
        "ferry_origin": (form.get("ferry_origin") or "").strip(),
        "ferry_destination": (form.get("ferry_destination") or "").strip(),
        "cruise_origin": (form.get("cruise_origin") or "").strip(),
        "cruise_destination": (form.get("cruise_destination") or "").strip(),
        "timeout_seconds": float(form.get("timeout_seconds") or 0) or None,
    }
    if not params["categories"]:
        params["categories"] = ["flights"]
    job = service.start_search(params)
    return JSONResponse({"job_id": job.id, "status_url": f"/api/jobs/{job.id}"})


@app.get("/api/jobs/{job_id}")
async def api_job(job_id: str):
    job = service.get_job(job_id)
    if not job:
        return JSONResponse({"error": "unbekannter Lauf"}, status_code=404)
    return JSONResponse(job.snapshot())


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_page(request: Request, job_id: str):
    job = service.get_job(job_id)
    if not job:
        meta = seo_meta.build("Suchergebnisse – Reise-Agent",
                              "Dieser Suchlauf ist nicht mehr vorhanden. Starte eine neue Suche.",
                              f"/jobs/{job_id}", base_url=_base(request),
                              robots="noindex,nofollow")
        return _render(request, "search.html", {
            "categories": service.CATEGORIES, "labels": service.CATEGORY_LABELS,
            "default_depart": date.today().isoformat(),
            "default_return": (date.today() + timedelta(days=2)).isoformat(),
            "status": service.source_status(), "error": "unbekannter Lauf",
            "landing_links": []}, meta, status_code=404)
    snap = job.snapshot()
    base = _base(request)
    meta = seo_meta.for_job(base, job_id)
    # JSON-LD für die tatsächlich angezeigten Angebote (Seite selbst ist noindex)
    offers_ld = []
    for cat, data in (snap.get("categories") or {}).items():
        for it in (data.get("top") or [])[:5]:
            offers_ld.append({"name": it.get("provider") or it.get("name"),
                              "price": it.get("price"), "currency": it.get("currency"),
                              "provider": it.get("provider"),
                              "route": f"{snap['params'].get('origin')} – "
                                       f"{snap['params'].get('destination')}",
                              "category": service.CATEGORY_LABELS.get(cat, cat)})
    blocks = [seo_jsonld.breadcrumb(base, [("Start", "/"), ("Suchergebnisse", f"/jobs/{job_id}")])]
    if offers_ld:
        blocks += [seo_jsonld.offer_list(base, f"/jobs/{job_id}", offers_ld),
                   seo_jsonld.aggregate_offer(base, f"/jobs/{job_id}", offers_ld)]
    live_rows = []
    for cat, data in (snap.get("categories") or {}).items():
        for prov in (data.get("providers") or []):
            live_rows.append({"category": cat, **prov})
    live_rows.sort(key=lambda r: (str(r.get("category")), str(r.get("source"))))
    return _render(request, "results.html", {
        "job": snap, "labels": service.CATEGORY_LABELS,
        "affiliate": service.affiliate_info(),
        "resolved": snap.get("resolved") or {},
        "live_rows": live_rows}, meta, blocks)


@app.get("/jobs/{job_id}/detail/{category}/{index}", response_class=HTMLResponse)
def detail_page(request: Request, job_id: str, category: str, index: int):
    data = service.job_result(job_id, category)
    if not data:
        return HTMLResponse("Kein Ergebnis fuer diese Kategorie.", status_code=404)
    ranked = data.get("ranked") or []
    if index < 0 or index >= len(ranked):
        return HTMLResponse("Angebot nicht gefunden.", status_code=404)
    item = ranked[index]
    providers = {p.get("source"): p for p in data.get("providers", [])}
    plaus = data.get("price_plausibility") or {}
    link = service.decorate_link(item.get("booking_url"))
    base = _base(request)
    meta = seo_meta.for_job(base, job_id)
    offer_ld = seo_jsonld.offer_list(base, f"/jobs/{job_id}", [{
        "name": item.get("provider") or item.get("name"),
        "price": item.get("all_in") if item.get("all_in") is not None else item.get("price"),
        "currency": item.get("currency"), "provider": item.get("provider"),
        "url": (link or {}).get("url"),
        "route": f"{item.get('name') or ''}".strip() or "Angebot",
        "category": service.CATEGORY_LABELS.get(category, category)}])
    return _render(request, "detail.html", {
        "item": item, "category": category, "index": index,
        "provider_status": providers.get(item.get("source")),
        "plausibility": plaus, "labels": service.CATEGORY_LABELS,
        "link": link, "affiliate": service.affiliate_info(),
        "job_id": job_id, "currency": data.get("context", {}).get("currency")},
        meta, [b for b in [offer_ld] if b])


@app.get("/alarms", response_class=HTMLResponse)
def alarms_page(request: Request):
    alarms = service.list_alarms()
    states = {a["id"]: service.alarm_state(a) for a in alarms}
    base = _base(request)
    meta = seo_meta.build("Preisalarme – Reise-Agent",
                          "Preisalarm für Flüge, Hotels, Fähren und Kreuzfahrten einrichten: "
                          "Budget, Tiefpunkt und Preissturz überwachen.",
                          "/alarms", base_url=base, robots="noindex,nofollow")
    return _render(request, "alarms.html", {
        "alarms": alarms, "states": states,
        "categories": service.CATEGORIES, "labels": service.CATEGORY_LABELS}, meta)


@app.post("/alarms")
async def alarm_create(request: Request):
    form = await request.form()
    alarm = {
        "id": uuid.uuid4().hex[:8],
        "name": (form.get("name") or "Preisalarm").strip(),
        "category": (form.get("category") or "flights").strip(),
        "origin": (form.get("origin") or "").strip(),
        "destination": (form.get("destination") or "").strip(),
        "depart_date": (form.get("depart_date") or "").strip(),
        "return_date": (form.get("return_date") or "").strip(),
        "adults": int(form.get("adults") or 1),
        "currency": (form.get("currency") or "EUR").strip().upper(),
        "budget": float(form.get("budget") or 0) or None,
        "budget_scope": (form.get("budget_scope") or "per_person").strip(),
        "trough_enabled": bool(form.get("trough_enabled")),
        "trough_mode": (form.get("trough_mode") or "median_x").strip(),
        "trough_factor": float(form.get("trough_factor") or 0.95),
        "lookback_days": int(form.get("lookback_days") or 7),
        "min_observations": int(form.get("min_observations") or 2),
        "drop_enabled": bool(form.get("drop_enabled")),
        "drop_percent": float(form.get("drop_percent") or 10),
        "cooldown_hours": float(form.get("cooldown_hours") or 24),
    }
    service.save_alarm(alarm)
    return RedirectResponse(url=f"/alarms/{alarm['id']}", status_code=303)


@app.get("/alarms/{alarm_id}", response_class=HTMLResponse)
def alarm_page(request: Request, alarm_id: str):
    alarms = service.list_alarms()
    alarm = next((a for a in alarms if a["id"] == alarm_id), None)
    if not alarm:
        return HTMLResponse("Alarm nicht gefunden.", status_code=404)
    meta = seo_meta.build(f"Alarm: {alarm.get('name')} – Reise-Agent",
                          "Detailansicht eines Preisalarms mit Verlauf und ausgelösten Alarmen.",
                          f"/alarms/{alarm_id}", base_url=_base(request),
                          robots="noindex,nofollow")
    return _render(request, "alarm.html", {
        "alarm": alarm, "state": service.alarm_state(alarm),
        "labels": service.CATEGORY_LABELS}, meta)


@app.post("/alarms/{alarm_id}/run")
async def alarm_run(request: Request, alarm_id: str):
    alarms = service.list_alarms()
    alarm = next((a for a in alarms if a["id"] == alarm_id), None)
    if not alarm:
        return HTMLResponse("Alarm nicht gefunden.", status_code=404)
    result = service.run_watcher(alarm)
    return RedirectResponse(url=f"/alarms/{alarm_id}", status_code=303)


@app.get("/api/resolve")
async def api_resolve(text: str, category: str = "flights"):
    """Eingabe auflösen (für Prüfung und Anzeige)."""
    return JSONResponse(service.resolve_place(text, category))


@app.get("/api/resolve/suggest")
async def api_resolve_suggest(q: str, category: str = "flights", limit: int = 8):
    """Vorschläge für die Autocomplete."""
    return JSONResponse({"suggestions": service.place_suggestions(q, category, limit)})


@app.get("/api/affiliate")
async def api_affiliate():
    """Welche Partnerprogramme sind konfiguriert (ohne IDs preiszugeben)."""
    return JSONResponse(service.affiliate_info())


@app.get("/api/status")
async def api_status():
    return JSONResponse(service.source_status())


@app.get("/health")
async def health():
    return JSONResponse({"ok": True, "service": "reise-agent-ui"})
