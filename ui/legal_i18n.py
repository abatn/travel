"""Mehrsprachige Rechtstexte für Impressum und Datenschutz.

Die Funktionen bauen das HTML, das ``ui/app.py`` bisher fest auf Deutsch
erzeugte. Alle Texte kommen aus ``i18n/locales/<lang>.legal.json``; die
Betreiberangaben stammen unverändert aus ``ui/legal.yaml`` und werden vor der
Ausgabe escaped. Es werden keine Angaben ergänzt oder erfunden.

Vertrag der Funktionen::

    imprint_html(lang, t, esc, data) -> str
    privacy_html(lang, t, esc, data) -> str

``t`` ist ``t(key, **params)``, ``esc`` eine HTML-Escape-Funktion und ``data``
das geladene Dict mit den Blöcken ``betreiber`` und ``datenschutz``.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

__all__ = ["imprint_html", "privacy_html"]

_RTL = {"ar"}
_T = Callable[..., str]
_Esc = Callable[[Any], str]


def _text(value: Any) -> str:
    """Getrimmter String; ``None`` und fehlende Werte werden zu ``""``."""
    return str(value or "").strip()


def _block(data: Any, key: str) -> Mapping[str, Any]:
    """Sicherer Zugriff auf einen Unterblock aus ``legal.yaml``."""
    block = data.get(key) if isinstance(data, Mapping) else None
    return block if isinstance(block, Mapping) else {}


def _label(text: str, esc: _Esc) -> str:
    """Hebt ein führendes Label (bis zum ersten Doppelpunkt) hervor.

    Der Doppelpunkt selbst bleibt im Label, damit auch Sprachen mit
    Leerzeichen vor dem Doppelpunkt (Französisch) korrekt bleiben. Texte ohne
    Label oder mit leerem Rest werden unverändert escaped.
    """
    head, sep, tail = text.partition(":")
    if sep and tail.strip():
        return f"<b>{esc(head + sep)}</b>{esc(tail)}"
    return esc(text)


def _paragraph(html: str) -> str:
    return f"<p>{html}</p>"


def _address_lines(
    block: Mapping[str, Any], esc: _Esc, *, bold_name: bool = False
) -> list[str]:
    """Anschriftzeilen in fester Reihenfolge, leere Felder entfallen."""
    lines: list[str] = []
    name = _text(block.get("name"))
    if name:
        lines.append(f"<b>{esc(name)}</b>" if bold_name else esc(name))
    for key in ("strasse", "plz_ort", "land"):
        value = _text(block.get(key))
        if value:
            lines.append(esc(value))
    return lines


def _wrap(html: str, lang: str, esc: _Esc) -> str:
    """Rahmen mit Sprach- und Leserichtungsangabe (Arabisch ist RTL)."""
    direction = "rtl" if lang in _RTL else "ltr"
    return (
        f'<div class="legal-text" lang="{esc(lang)}" dir="{direction}">'
        f"{html}</div>"
    )


def imprint_html(lang: str, t: _T, esc: _Esc, data: Any) -> str:
    """Impressum als HTML (Anbieterkennzeichnung, § 5 DDG)."""
    b = _block(data, "betreiber")
    parts: list[str] = []

    address = _address_lines(b, esc, bold_name=True)
    if address:
        parts.append(_paragraph("<br>".join(address)))

    email = _text(b.get("email"))
    phone = _text(b.get("telefon"))
    contact: list[str] = []
    if email:
        contact.append(
            f'{esc(t("legal.imprint.email"))} '
            f'<a href="mailto:{esc(email)}">{esc(email)}</a>'
        )
    if phone:
        contact.append(f'{esc(t("legal.imprint.phone"))} {esc(phone)}')
    if contact:
        parts.append(_paragraph("<br>".join(contact)))

    ust = _text(b.get("umsatzsteuer_id"))
    if ust:
        if ust.lower() == "keine":
            parts.append(_paragraph(_label(t("legal.imprint.ust_none"), esc)))
        else:
            parts.append(
                _paragraph(_label(t("legal.imprint.ust", id=ust), esc))
            )

    court = _text(b.get("registergericht"))
    number = _text(b.get("registernummer"))
    register: list[str] = []
    if court:
        register.append(_label(t("legal.imprint.court", court=court), esc))
    if number:
        register.append(
            _label(t("legal.imprint.register_no", number=number), esc)
        )
    if register:
        parts.append(_paragraph("<br>".join(register)))

    responsible = _text(b.get("verantwortlich"))
    if responsible:
        parts.append(
            _paragraph(
                _label(t("legal.imprint.responsible", name=responsible), esc)
            )
        )

    parts.append(_paragraph(esc(t("legal.imprint.agency"))))
    parts.append(_paragraph(esc(t("legal.imprint.dispute"))))

    return _wrap("".join(parts), lang, esc)


def privacy_html(lang: str, t: _T, esc: _Esc, data: Any) -> str:
    """Datenschutzerklärung als HTML (Information nach Art. 13 DSGVO)."""
    b = _block(data, "betreiber")
    d = _block(data, "datenschutz")
    parts: list[str] = []

    address = _address_lines(b, esc, bold_name=False)
    contact_email = _text(d.get("kontakt_datenschutz")) or _text(
        b.get("email")
    )
    responsible: list[str] = [f"<b>{esc(t('legal.privacy.responsible'))}</b>"]
    responsible.extend(address)
    if contact_email:
        responsible.append(
            f'{esc(t("legal.imprint.email"))} {esc(contact_email)}'
        )
    parts.append(_paragraph("<br>".join(responsible)))

    host = _text(d.get("hosting"))
    retention_logs = _text(d.get("aufbewahrung_logs"))
    if host and retention_logs:
        parts.append(
            _paragraph(
                _label(
                    t(
                        "legal.privacy.hosting",
                        host=host,
                        retention=retention_logs,
                    ),
                    esc,
                )
            )
        )

    parts.append(
        _paragraph(_label(t("legal.privacy.purposes"), esc))
    )

    recipients = _label(t("legal.privacy.recipients"), esc)
    processors = _text(d.get("auftragsverarbeiter"))
    if processors:
        recipients += " " + _label(
            t("legal.privacy.processors", list=processors), esc
        )
    parts.append(_paragraph(recipients))

    parts.append(_paragraph(_label(t("legal.privacy.x402"), esc)))
    parts.append(_paragraph(_label(t("legal.privacy.affiliate"), esc)))
    parts.append(_paragraph(_label(t("legal.privacy.retention"), esc)))
    parts.append(_paragraph(_label(t("legal.privacy.rights"), esc)))

    authority = _text(d.get("aufsichtsbehoerde"))
    if authority:
        parts.append(
            _paragraph(_label(t("legal.privacy.complaint", authority=authority), esc))
        )

    updated = _text(d.get("stand"))
    if updated:
        parts.append(
            _paragraph(_label(t("legal.privacy.updated", date=updated), esc))
        )

    return _wrap("".join(parts), lang, esc)
