#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generator für bundling/evidence.json (Fähigkeit 2 - Intelligente Kombination).

Alle Zitate sind VERBATIM aus den am 21.10.2026 geöffneten Quellen (inkl. Umlauten).
IDs E1..E19 sind stabil und deckungsgleich mit docs/EVIDENCE_SPLIT_BOOKING.md.
"""
import json
import os

EV = []


def ev(eid, claim, publisher, title, date, url, quote, strength, supports,
       quantified, caveats, counters=None, verified=True):
    d = {
        "id": eid,
        "claim": claim,
        "source_publisher": publisher,
        "source_title": title,
        "source_date": date,
        "source_url": url,
        "quote": quote,
        "strength": strength,
        "supports": supports,
        "quantified": quantified,
        "caveats": caveats,
        "verified": verified,
    }
    if counters:
        d["counters"] = counters
    EV.append(d)


def q(metric, value, unit):
    return {"metric": metric, "value": value, "unit": unit}


NULLQ = q(None, None, None)

# ---------------------------------------------------------------- E1
ev(
    "E1",
    "Zwei getrennte Einwegtickets können deutlich günstiger sein als ein Round-Trip; KAYAK beziffert das "
    "potenzielle Sparpotenzial auf bis zu 30 % international und 29 % domestic.",
    "KAYAK (Booking Holdings), Pressemitteilung via PR Newswire",
    "KAYAK Unwraps the 2026 Holiday Travel Sweet Spots and Savings",
    "2026-10-02",
    "https://www.prnewswire.com/news-releases/kayak-unwraps-the-2026-holiday-travel-sweet-spots-and-savings-302897217.html",
    "Rethinking the traditional round trip could pay off when it comes to ways to save this holiday season. "
    "Piecing together two one-way tickets could cut airfare by as much as 30% internationally and 29% domestically.\n\n"
    "The biggest potential savings when booking two one way trips include Simpson Bay, St. Maarten at 30%, "
    "Liberia, Costa Rica at 23%, and Lima, Peru at 20%. Domestically, Washington, D.C. leads at 29%, "
    "followed by Chicago at 28% and San Diego at 22%.",
    "strong",
    ["separate_roundtrip", "mixed_airlines"],
    q("max potential airfare saving, international routes", 30, "percent"),
    "Maximales Sparpotenzial JE Route (Best Case), US-lastig, Feiertagssaison 2026; kein Mittelwert, keine "
    "Wahrscheinlichkeit, keine Euro-Angabe, keine europäische Route. KAYAK-Methodik (Blog 12.10.2026): "
    "'Prices may vary, and savings cannot be guaranteed. Percentages for changes in pricing are approximate.' "
    "Verifiziert am 2026-10-21.",
)

# ---------------------------------------------------------------- E2
ev(
    "E2",
    "Der ökonomische Mechanismus ist real: Airlines bepreisen Segmente separat, deshalb können zwei Einwegtickets "
    "günstiger als ein Round-Trip sein.",
    "KAYAK (Travel Hacker Blog)",
    "What is a Hacker Fare? How to use one-way flights to save money.",
    "2026-05-08",
    "https://www.kayak.com/news/hacker-fare/",
    "A Hacker Fare is a round-trip flight built from two one-way tickets, sometimes on different airlines. "
    "KAYAK finds these for you, only when and where it can save you time or money.\n\n"
    "Due to various airline pricing strategies, sometimes two one-way flights cost less than a regular round-trip. "
    "So no, it's not magic. It's just a smarter match that can beat the regular round-trip price on some searches.\n\n"
    "Hacker Fares can be cheaper than a round-trip ticket. KAYAK only shows Hacker Fares when and where they can "
    "actually save you time or money, but two one-way flights do not always beat a regular round-trip.",
    "strong",
    ["separate_roundtrip", "mixed_airlines"],
    NULLQ,
    "KAYAK zeigt Hacker Fares nur an, wenn sie gewinnen - Existenz-, aber kein Universalitätsbeleg. "
    "Belegt die Mechanik, keine Häufigkeit und keine Preisgröße.",
)

# ---------------------------------------------------------------- E3
ev(
    "E3",
    "Getrennte Tickets sind rechtlich unverbundene Tickets: bei Ausfall oder Änderung eines Flugs muss die andere "
    "Airline den Passagier auf dem zweiten Ticket nicht unterstützen.",
    "KAYAK (offizielle Hilfe-Dokumentation)",
    "Pricing and Price Alerts - Abschnitt 'What's a Hacker Fare? / Important things to know'",
    "2026-10-21",
    "https://www.kayak.com/c/help/pricing/",
    "Since you're booking separate tickets, each one follows its own rules:\n"
    "- Baggage fees differ: Each airline has its own baggage policies and fees\n"
    "- Change and refund policies vary: What applies to your outbound flight may not apply to your return\n"
    "- Tickets are independent: If one flight is canceled or changed, the other airline isn't obligated to "
    "accommodate you on the other ticket\n"
    "- Check-in requirements differ: Each airline has its own check-in times and requirements",
    "strong",
    ["separate_roundtrip", "mixed_airlines"],
    NULLQ,
    "Kein Publikationsdatum auf der Seite; Abrufdatum 2026-10-21. Belegt die Haftungslücke, nicht die Preislichkeit.",
)

# ---------------------------------------------------------------- E4
ev(
    "E4",
    "EU-Recht: Bei getrennt gebuchten Hin-/Rückflügen mit verschiedenen Airlines wird bei Annullierung des "
    "Hinflugs NUR der annullierte Flug erstattet; der Ausgleichsanspruch bei verpasstem Anschluss besteht nur bei "
    "einer einzigen Reservierung.",
    "Europäische Kommission / Your Europe",
    "Air passenger rights / Fluggastrechte",
    "2026-10-21",
    "https://europa.eu/youreurope/citizens/travel/passenger-rights/air/index_en.htm",
    "If you booked an outbound and a return flight separately with different airlines and the outbound flight is "
    "cancelled, reimbursement is only due for the cancelled flight.\n\n"
    "However, if the outbound and return flights are operated by different airlines, but were part of a single "
    "reservation, in the event that the outbound flight was cancelled, you have the following rights: Compensation "
    "- A choice between the reimbursement of your entire ticket (outbound and return flights) or re-routing on another "
    "flight for the outbound flight\n\n"
    "You have a right to compensation if: your flights were booked as part of a single reservation and EU air passenger "
    "rights apply and the delay to your arrival time was not caused by extraordinary circumstances",
    "strong",
    ["separate_roundtrip", "mixed_airlines"],
    NULLQ,
    "Kein Publikationsdatum auf der Seite; Abrufdatum 2026-10-21. Belegt die Rechtslage, nicht die Preislichkeit.",
)

# ---------------------------------------------------------------- E5
ev(
    "E5",
    "Getrennte Tickets: kein Gepäckdurchgang, geringere Hilfsbereitschaft bei verpassten Anschlüssen, doppelte "
    "Änderungs-/Stornogebühren gegenüber einem Ticket.",
    "Travelers United (US-Verbraucher-NGO)",
    "5 considerations before booking separate tickets for a round trip",
    "2014-10-07",
    "https://www.travelersunited.org/5-considerations-before-booking-separate-tickets-for-a-round-trip/",
    "With two tickets airlines may not check your luggage through to a connecting flight, and they are less likely to "
    "help with missed connections. In this case, flying with separate tickets can be dangerous.\n\n"
    "The advantage of a single ticket that is written with both sections of the round trip is that there is only one "
    "change fee if travelers change the whole thing. Plus, a passenger will only pay one penalty to reuse the ticket if "
    "the trip is canceled completely. Whereas, two or more tickets have two or more fees.",
    "medium",
    ["separate_roundtrip", "mixed_airlines"],
    q("change/storno fees, two separate tickets vs. one ticket", 2, "count_minimum"),
    "Datierung 2014 - nur für die Risiko- und Kostenstruktur herangezogen, nicht für Marktdaten. "
    "Der Absatz zu den zwei Gebühren ist zugleich eine Gegenposition (Paketvorteil).",
)

# ---------------------------------------------------------------- E6  (counter)
ev(
    "E6",
    "Gegenposition: Round-Trip-Tickets sind MEIST günstiger als zwei Einwegtickets; bei internationalen Routen "
    "kann der Round-Trip deutlich günstiger sein.",
    "KAYAK (Travel Hacker Blog)",
    "What's cheaper? Round-trip vs. one-way flights compared.",
    "2026-07-29",
    "https://www.kayak.com/news/round-trip-vs-one-way-flights/",
    "For domestic flights, the cost of a round-trip ticket is generally the same as two one-way tickets.\n"
    "- Return tickets are generally cheaper for international flights, but if time is important to you it can be worth "
    "checking two direct one-ways.\n\n"
    "It is generally believed that buying two one-way tickets is more expensive than buying a round-trip ticket.\n\n"
    "As you can see, yes, the rumors are true, and round-trip tickets are usually less expensive than two one-way "
    "tickets. However, the difference can be quite small.",
    "strong",
    ["separate_roundtrip"],
    q("price gap New York - London: two one-ways vs. return ticket", 119, "USD"),
    "Stichprobe von nur 2 Domestic- und 2 International-Routen; kein Mittelwert, keine Häufigkeitsverteilung, "
    "USD-Basis. Widerspricht einer universellen Aussage 'getrennt ist günstiger'. Die Preistabelle steht "
    "verbatim in additional_quote.",
    counters="separate_roundtrip",
)
EV[-1]["additional_quote"] = (
    "Route | Total for 2 one-way tickets | Total for a return ticket\n"
    "San Francisco to New York | $364 | $363\n"
    "LA to Honolulu | $332 | $331\n"
    "LA to Tokyo, Japan | $879 | $896\n"
    "New York to London, England | $637 | $518\n\n"
    "Note all prices mentioned in this article were checked and compared on June 30, 2026 for flights from "
    "Sep 6 – 13, 2026."
)

# ---------------------------------------------------------------- E7
ev(
    "E7",
    "Gemischt-Airlines (Hin- und Rückflug bei verschiedenen Airlines) sind ein bewusst bewerbtes Produkt und laut "
    "Anbieter in der Regel preisgünstiger als ein Round-Trip.",
    "KAYAK (Travel Hacker Blog)",
    "What is a Hacker Fare? How to use one-way flights to save money.",
    "2026-05-08",
    "https://www.kayak.com/news/hacker-fare/",
    "Sometimes you'll fly out with one airline and home with another. Other times, it's the same airline, but they have "
    "you in the system as two one-way flights.\n\n"
    "Either way, you'll get there and back, usually paying less than you would for a regular round-trip flight.\n\n"
    "Departure ticket: One-way ticket from New York JFK to Paris CDG booked with Air France\n"
    "Return ticket: One-way ticket from Paris ORY to New York JFK booked with French Bee\n\n"
    "If you book a Hacker Fare you might take a different airline home than the one you took to your destination, or you "
    "might fly the same airline both ways on two separate one-way tickets.",
    "strong",
    ["mixed_airlines", "separate_roundtrip"],
    NULLQ,
    "Anbieter-Aussage ohne offengelegte Stichprobe; 'usually paying less' wird durch E6 desselben Anbieters für "
    "internationale Routen relativiert. Enthält zusätzlich den Risikohinweis der Seite: 'With a Hacker Fare you're "
    "managing two separate bookings, so delays, cancellations and changes become more complicated.'",
)

# ---------------------------------------------------------------- E8
ev(
    "E8",
    "Der Ausgang zwischen Ein-Ticket- und getrennter Buchung hängt von Route und Airlines ab; 'mix and match' "
    "verschiedener Airlines ist ein expliziter Preisvorteil-Mechanismus.",
    "KAYAK (Travel Hacker Blog)",
    "How to book multi-city flights on KAYAK?",
    "2026-05-12",
    "https://www.kayak.com/news/multi-city-flights/",
    "Is it cheaper to book multi-city flights or separate one-way tickets? It depends on the route and airlines. "
    "Multi-city bookings can save money by combining segments, but sometimes separate one-way tickets are cheaper if "
    "airlines are promoting specific destinations. Use KAYAK's price comparison feature to check both options.\n\n"
    "Advantages to multi-city flights\n"
    "- Potentially save on airfare by combining multiple destinations into a single ticket.\n"
    "- Definitely save on baggage fees by checking your luggage only once\n"
    "- Gain time by avoiding unnecessary layovers or connections.\n"
    "- Explore more destinations by adding extra legs to your trip.\n"
    "- Customize your trip according to your preferences and interests.\n"
    "- Mix and match different airlines and airports to find great deals.",
    "medium",
    ["mixed_airlines", "separate_roundtrip", "flight_plus_hotel"],
    NULLQ,
    "FAQ-Aussage ohne Stichprobe; keine Zahlen. Enthält zugleich eine Gegenposition (Gepäckdurchgang, Zeitgewinn "
    "beim Ein-Ticket).",
)

# ---------------------------------------------------------------- E9
ev(
    "E9",
    "Produktdefinition: 'Hacker Fare' = zwei getrennte Einwegtickets, oft von verschiedenen Airlines, mit explizitem "
    "Preisziel - tragfähige Zitiergrundlage für die mixed-airlines-Aussage.",
    "KAYAK (offizielle Hilfe-Dokumentation)",
    "Pricing and Price Alerts - Abschnitt 'What's a Hacker Fare?'",
    "2026-10-21",
    "https://www.kayak.com/c/help/pricing/",
    "A Hacker Fare is when KAYAK combines two separate one-way tickets (often from different airlines) instead of a "
    "traditional round-trip booking. The goal is simple: find you cheaper prices and more flight time options than "
    "you'd get with a single round-trip ticket.",
    "strong",
    ["mixed_airlines", "separate_roundtrip"],
    NULLQ,
    "Kein Publikationsdatum auf der Seite; Abrufdatum 2026-10-21. Belegt die Produktdefinition, keine Häufigkeit.",
)

# ---------------------------------------------------------------- E10
ev(
    "E10",
    "Marktstruktur Deutschland: 49,4 % der vor Reiseantritt gebuchten Reiseausgaben laufen über Veranstalter/"
    "Pauschale, 39,9 % direkt bei den Leistungsträgern (Airlines, Hotels), 10,7 % über Produktportale mit nur einer "
    "Produktart. Einzelbuchung ist strukturell eine relevante Größe.",
    "Deutscher Reiseverband (DRV)",
    "Der deutsche Reisemarkt - Zahlen und Fakten 2026 (S. 6)",
    "2026-03-01",
    "https://www.drv.de/public/Downloads_2026/26-02-27_Zahlen_und_Fakten_2026_final.pdf",
    "Marktstruktur im deutschen Touristikmarkt 2025\n"
    "43,4 (49,4%) Veranstalter / Reisebüros - Buchungen von Veranstalterreisen\n"
    "9,4 (10,7%) Produktportale und sonstige Websites, auf denen nur eine Produktart angeboten wird "
    "(z.B. Hotel-, Flug-, Mietwagenportale)\n"
    "35,1 (39,9%) Leistungsträger online & offline - Airlines, Bahn-, Mietwagenunternehmen, Hotels, Fernbusunternehmen, "
    "Event-Veranstalter etc.\n"
    "Ausgaben in Milliarden Euro\n"
    "Quelle: MobilitätsMonitor von YouGov (Vor Reiseantritt gebuchte Leistungen für Urlaubs- und Privatreisen mit mind. "
    "einer Übernachtung)\n\n"
    "Für den vorab vor Reiseantritt gebuchten mehrtägigen Urlaub haben die Bundesbürger die neue Rekordsumme von "
    "87,9 Mrd. Euro ausgegeben.",
    "strong",
    ["flight_plus_hotel"],
    q("share of pre-trip booked German travel spend via Veranstalterreisen (packages)", 49.4, "percent"),
    "Belegt die Marktverteilung der Buchungswege, KEINE Preisdifferenz. Erlaubt keine Aussage 'Pauschale sind teurer' "
    "und keine x-%-Aussage zum Kostenvorteil der Einzelbuchung. Datenjahr 2025, Berichtsstand März 2026.",
)

# ---------------------------------------------------------------- E11
ev(
    "E11",
    "Rechtlicher Nachteil der getrennten Buchung: kein Sicherungsschein/Insolvenzschutz, kein Veranstalter-Haftungsdach; "
    "jeder Mangel muss beim jeweiligen Einzelanbieter reklamiert werden.",
    "Europäisches Verbraucherzentrum Deutschland (Zentrum für Europäischen Verbraucherschutz e. V., ECC-Net)",
    "Ihre Rechte kurz und knapp (Broschüre Pauschalreise)",
    "2020-12-01",
    "https://www.evz.de/app/uploads/sites/3/2026/03/reiserecht-pauschalreise.pdf",
    "SIE HABEN KEINE PAUSCHALREISE GEBUCHT, WENN …\n"
    "✓ Sie selbst die Leistungen unabhängig voneinander, bei unterschiedlichen Anbietern buchen und bezahlen. Beispiel: den "
    "Flug bei der Airline, den Mietwagen beim Vermieter. In diesem Fall sind Sie nicht gegen die Insolvenz der Airline "
    "oder des Vermieters abgesichert.\n\n"
    "✓ Bei Zahlungsunfähigkeit der Airline / des Hotels muss Sie der Reiseveranstalter auf seine Kosten auf einen "
    "anderen Flug / ein anderes Hotel umbuchen, sofern Flug oder Hotel Teil der Pauschalreise sind.\n\n"
    "Haben Sie keine Pauschalreise gebucht, müssen Sie sich bei Mängeln immer an das Unternehmen wenden, das die "
    "Leistung erbracht hat.",
    "medium",
    ["flight_plus_hotel", "separate_roundtrip"],
    NULLQ,
    "Inhaltsstand Dezember 2020 (URL-Pfad 2026) - Datierung als Schwäche; die Novellierung Richtlinie (EU) 2026/1024 "
    "(E17/E18) ist noch nicht in nationale Umsetzung. Für die Struktur des Pauschalreisenschutzes weiterhin "
    "aussagekräftig.",
)

# ---------------------------------------------------------------- E12
ev(
    "E12",
    "Umbuchung: Bei Pauschalreisen gilt eine als angemessen angesehene Umbuchungsgebühr-Pauschale von bis zu 30 EUR pro "
    "Reise; bei getrennt gebuchten Flügen ist die Umbuchung nur mit Zustimmung der Airline zuständig, bei "
    "Billigfliegern übermäßig teuer oder ausgeschlossen, und Einzeltickets sind in der Regel nicht übertragbar.",
    "Verbraucherzentrale (Gemeinschaftsredaktion der Verbraucherzentralen)",
    "Umbuchung von Reisen: nur mit OK des Veranstalters",
    "2025-11-25",
    "https://www.verbraucherzentrale.de/wissen/reise-mobilitaet/urlaub-buchen/umbuchung-von-reisen-nur-mit-ok-des-veranstalters-10428",
    "Wer bei einer gebuchten Pauschalreise aus persönlichen Gründen nachträglich auf ein anderes Ziel oder einen "
    "alternativen Termin ausweichen will bzw. muss, ist auf die Kulanz des Reiseveranstalters angewiesen. Stimmt "
    "dieser zu, können allerdings Umbuchungsgebühren anfallen - sofern in den allgemeinen Reisebedingungen (AGB) "
    "vorgesehen. Als angemessen gilt eine Pauschale von bis zu 30 Euro pro Reise, da eine Umbuchung immer mit "
    "einigem Verwaltungsaufwand verbunden ist.\n\n"
    "Umbuchung von Individualreisen Flug: Möchte der Fluggast zu einer anderen Zeit oder zu einem anderen Ziel "
    "fliegen, muss die Fluggesellschaft zustimmen. Meist werden nur Flüge, die zu regulären Preisen gebucht wurden, "
    "kostenlos umgebucht. Bei Sonderangeboten und Billigfliegern sind Umbuchungen häufig übermäßig teuer oder "
    "sogar vertraglich ausgeschlossen. Auch ist es Individualreisenden in der Regel verwehrt, das Ticket auf eine "
    "andere Person zu übertragen. Denn fast alle Flugscheine - insbesondere solche zu verbilligten Konditionen - "
    "enthalten den Vermerk \"nicht übertragbar\" (\"not endorsable\").\n\n"
    "Auch bei Hotelzimmern oder Ferienwohnungen ist eine Umbuchung immer vom Einverständnis des Hotelbetreibers bzw. "
    "Mieters abhängig.",
    "strong",
    ["flight_plus_hotel", "separate_roundtrip"],
    q("reasonable package rebooking flat fee per trip", 30, "EUR"),
    "Belegt Gebühren UND Zustimmungsvorbehalte. Wichtig: die 30-EUR-Pauschale belegt, dass es Gebühren auch beim "
    "Paket gibt - sie ist kein Beleg für Umbuchbarkeit.",
)

# ---------------------------------------------------------------- E13
ev(
    "E13",
    "Stornokosten beim Paket: Reiseveranstalter vereinbaren vertraglich pauschalierte Rücktrittsent-schädigungen mit "
    "zeitabhängigen Prozentsätzen in den AGB - der konkrete Mechanismus, warum Storno bei einem Paket teuer ist.",
    "Bundesministerium der Justiz und für Verbraucherschutz (BMJV)",
    "Pauschalreiserecht (Broschüre), S. 32",
    "2025-11-01",
    "https://www.bmjv.de/SharedDocs/Publikationen/DE/Broschueren/Pauschalreiserecht.pdf?__blob=publicationFile&v=6",
    "Rücktritt vor Reisebeginn durch Reisende oder Reiseveranstalterunternehmen\n"
    "Vor Reisebeginn können Reisende jederzeit vom Vertrag zurücktreten (§ 651h BGB). Dieses Recht ist an "
    "keine Voraussetzungen geknüpft, allerdings kann das Reiseveranstalterunternehmen eine angemessene "
    "Entschädigung verlangen, die häufig auch als „Rücktrittsgebühr“ bezeichnet wird. Das "
    "Reiseveranstalterunternehmen kann mit Reisenden vertraglich eine Pauschalierung der angemessenen "
    "Entschädigung vereinbaren. Meist werden hierfür in den Allgemeinen Geschäftsbedingungen des "
    "Veranstaltungsunternehmens unterschiedliche Prozentsätze vorgesehen, die sich insbesondere nach der jeweiligen "
    "Zeitspanne zwischen Rücktrittserklärung und Reisebeginn richten. Willkürliche Festsetzungen sind unzulässig, "
    "vielmehr müssen die Entschädigungspauschalen den Bemessungskriterien folgen, die im Gesetz festgelegt sind und "
    "durch die Rechtsprechung weiter aus gestaltet werden.",
    "strong",
    ["flight_plus_hotel"],
    NULLQ,
    "Das Ministerium nennt bewusst KEINE konkreten Prozentsätze (die stehen in den AGB der Veranstalter). Keine "
    "Euro-Angabe für eine konkrete Stornogebühr ableitbar. Stand November 2025.",
)

# ---------------------------------------------------------------- E14  (counter)
ev(
    "E14",
    "Gegenposition zur Aufschlags-These: Die einzige gefundene belastbare Vergleichsstudie zeigt für Paketbuchungen "
    "eine rund 30 % höhere durchschnittliche Hotel-ADR und eine 2,6-fach höhere Abbruchquote bei "
    "Standalone-Buchungen - Pakete sind also nicht durchgehend teurer, und Einzelbuchungen sind nicht durchgehend "
    "günstiger.",
    "PhocusWire (Jill Menze), über Expedia-Group-Daten; verifiziert über Wayback-Snapshot",
    "Package bookings drive higher ADR, have longer booking windows",
    "2018-07-18",
    "https://web.archive.org/web/20220529031913/https://www.phocuswire.com/Expedia-Group-package-booking",
    "Analyzing data on package bookings vs. standalone hotel bookings, Expedia Group found that for full year 2017, "
    "package bookings delivered higher average daily rates and had longer booking windows, particularly internationally. "
    "Overall, ADR for package bookings compared to standalone bookings was higher at about 30% premium, and the booking "
    "window for package bookings was about one month longer. Cancelations for standalone bookings were 2.6 times higher "
    "than for package bookings.\n\n"
    "Cancelations are also less likely because in package bookings - which in addition to hotels can include flights "
    "and car rentals - the hotel reservation is often tied to a nonrefundable flight.\n\n"
    "Expedia says one possible reason package bookings deliver a higher ADR is because hotels that offer steep room "
    "discounts in package bookings may succeed in upselling customers on room type, due to the overall perceived value.",
    "medium",
    ["flight_plus_hotel"],
    q("ADR premium of package bookings vs. standalone hotel bookings", 30, "percent"),
    "Vendor-eigene Daten mit Eigeninteresse am Paketgeschäft; Datenjahr 2017, Veröffentlichung 2018 (alt). Die "
    "ADR-Differenz ist ein Selektionsbefund (längere Aufenthalte, teurere Kategorien) und KEIN Nachweis eines "
    "Veranstalter-Aufschlags. Direktseite lieferte 403; Volltext über Wayback-Snapshot verifiziert.",
    counters="flight_plus_hotel",
)

# ---------------------------------------------------------------- E15  (counter)
ev(
    "E15",
    "Gegenposition: 32 % der befragten Konsumenten nennen den Rabatt für eine Paketbuchung einen der attraktivsten "
    "Buchungsanreize - Pakete werden als Preis-Deal positioniert, nicht zwingend als Aufschlag.",
    "Expedia Group",
    "Traveler Value Index 2023 (PDF), S. 32, Fußnote 29: 'Expedia Group, Traveler Value Index: Spring 2022 Outlook'",
    "2023-01-01",
    "https://go2.advertising.expedia.com/rs/185-EIA-216/images/Expedia_Group_Media_Solutions_Traveler_Value_Index_2023.pdf",
    "Most appealing deals to consumers when they book travel: A complimentary add-on (free parking, free checked bag) / "
    "A discount for booking 4-12 weeks in advance / A discount for booking a package (ex: a flight and vacation rental "
    "together) / A discount for booking last minute / A discount for a longer trip or stay / A discount for booking "
    "through a mobile app / A discount for booking travel to/in a specific location / A discount if you are a member of "
    "the travel provider's loyalty program - 33% 33% 32% 22% 22% 21% 20% 17%",
    "medium",
    ["flight_plus_hotel"],
    q("share of consumers naming a package-booking discount among most appealing deals", 32, "percent"),
    "Vendor-Umfrage mit Paket-Verkaufsinteresse; Erhebung Spring 2022, Veröffentlichung 2023 (Daten nicht ganz "
    "aktuell). Die Prozentwerte stehen in der Grafik in derselben Reihenfolge wie die Deals; "
    "'A discount for booking a package' = 32 %.",
    counters="flight_plus_hotel",
)

# ---------------------------------------------------------------- E16  (counter)
ev(
    "E16",
    "Paketvorteile rechtlich belegt: Haftungsdach des Veranstalters, Insolvenzabsicherung, Beistandpflicht, kostenlose "
    "Behebung von Mängeln, Übertragbarkeit auf eine andere Person. Für separat gebuchte Leistungen und bestimmte "
    "Arten von Geschäftsreisen gilt der Pauschalreisenschutz nicht.",
    "Europäische Kommission / Your Europe",
    "Pauschalreisen und verbundene Reiseleistungen",
    "2026-10-21",
    "https://europa.eu/youreurope/citizens/travel/holidays/package-travel/index_de.htm",
    "Der Veranstalter ist beispielsweise dazu verpflichtet, Sie vor Abschluss des Vertrags umfassend zu informieren, er "
    "haftet für die ordnungsgemäße Durchführung der pauschal gebuchten Reiseleistungen und muss eine "
    "Insolvenzabsicherung gewährleisten. Diese Rechte können Sie in Anspruch nehmen, wenn Sie Ihre Pauschalreise "
    "online oder vor Ort bei einem Reiseveranstalter, einem Reisebüro oder einem anderen Unternehmer gebucht haben, "
    "der als Reiseveranstalter auftritt. Für „verbundene Reiseleistungen“ gelten weniger weit reichende Rechte.\n\n"
    "Diese Vorschriften gelten nicht für eigenständige Reiseleistungen (Flug oder Unterkunft, die separat gebucht "
    "werden), bestimmte Arten von Geschäftsreisen, Pauschalreisen, die auf der Grundlage einer Rahmenvereinbarung "
    "gelegentlich und ohne Gewinnabsicht einer begrenzten Zahl von Reisenden angeboten werden, sowie Pauschalreisen, "
    "die weniger als 24 Stunden dauern und die keine Unterbringung einschließen.\n\n"
    "Der Reiseveranstalter ist für die ordnungsgemäße Durchführung aller in Ihrem Pauschalpaket enthaltenen "
    "Reiseleistungen verantwortlich. Kann eine Reiseleistung nicht wie vereinbart durchgeführt werden, etwa weil ein "
    "Dienstleistungserbringer eine vereinbarte Leistung nicht oder nicht in der vereinbarten Form erbringen kann "
    "(z. B. Beförderung zum Bestimmungsort/Ort der Abreise, Art der Unterbringung, von Ihnen gebuchte Führung), muss "
    "der Reiseveranstalter das Problem ohne Mehrkosten für Sie beheben.\n\n"
    "Geraten Sie während Ihrer Pauschalreise in Schwierigkeiten (z. B. Gesundheitsprobleme oder Verlust des "
    "Reisepasses), ist der Veranstalter verpflichtet, Beistand zu leisten, etwa indem er Ihnen Informationen über "
    "Gesundheitsdienste oder konsularischen Beistand bereitstellt oder Ihnen hilft, Ersatzreisearrangements zu "
    "treffen.\n\n"
    "Übertragung der Pauschalreise auf eine andere Person: Dies ist unter bestimmten Voraussetzungen möglich. "
    "Allerdings kann Ihnen der Reiseveranstalter in einem solchen Fall Gebühren in Höhe der zur Übertragung des "
    "Vertrags tatsächlich angefallenen Kosten berechnen.",
    "strong",
    ["flight_plus_hotel"],
    NULLQ,
    "Kein Publikationsdatum auf der Seite; Abrufdatum 2026-10-21. Die Seite beschreibt die geltende Richtlinie "
    "(EU) 2015/2302; die Novellierung 2026/1024 (E17/E18) ist noch nicht umgesetzt.",
    counters="flight_plus_hotel",
)

# ---------------------------------------------------------------- E17  (counter)
ev(
    "E17",
    "Paketvorteile werden rechtlich VERSTÄRKT, nicht abgebaut: Das EU-Parlament hat am 12.03.2026 die Novelle der "
    "Pauschalreisereichtlinie angenommen (537 Ja, 2 Nein, 24 Enthaltungen) - Insolvenzschutz, Voucher-Regeln und "
    "kostenfreies Storno bei höherer Gewalt werden ausgebaut.",
    "Europäisches Parlament (Pressemitteilung, IMCO-Ausschuss)",
    "Package travel: Parliament greenlights new rules to protect holidaymakers",
    "2026-03-12",
    "https://www.europarl.europa.eu/news/en/press-room/20260306IPR37536/package-travel-parliament-greenlights-new-rules-to-protect-holidaymakers",
    "On Thursday MEPs gave the green light to revised rules on package travel, enhancing protection for holidaymakers "
    "by drawing lessons from the pandemic and high-profile bankruptcies.\n\n"
    "If the trip organiser goes bankrupt, clients will have to be refunded for cancelled services from the insolvency "
    "guarantee within 6 months (9 months for very complex bankruptcies). The standard 14-day deadline for refunds for "
    "trip cancellation will remain unchanged.\n\n"
    "Parliament adopted the directive by 537 votes in favour and 2 against, with 24 abstentions.\n\n"
    "After the vote, Parliament's rapporteur for the file Alex Agius Saliba (S&D, MT) said: \"These updated rules will "
    "protect consumers when something goes wrong with their package holiday. In the case of extraordinary "
    "circumstances that affect any part of their trip, travellers will be able to cancel with a full refund. The "
    "acceptance of vouchers by consumers will remain voluntary, and they can request their money back instead. Travel "
    "companies will have the obligation to respond to complaints within 60 days and robust insolvency protection will "
    "ensure that when a bankruptcy occurs the financial loss is not shifted on families.\"\n\n"
    "EU countries will have 28 months from the date of entry into force to transpose the new rules into national "
    "legislation and a further 6 months to start applying the new provisions.",
    "strong",
    ["flight_plus_hotel"],
    q("EP votes in favour of the revised Package Travel Directive", 537, "votes"),
    "Erste Lesung; Inkrafttreten und nationale Umsetzung (28 Monate + 6 Monate Anwendungsfrist) stehen aus. "
    "Bis dahin gilt die RL (EU) 2015/2302.",
    counters="flight_plus_hotel",
)

# ---------------------------------------------------------------- E18  (counter)
ev(
    "E18",
    "Rechtsakt-Daten: Richtlinie (EU) 2026/1024 vom 29.04.2026, veröffentlicht am 08.05.2026 - der Paketvorteil "
    "beruht auf aktuellem EU-Recht und wird zusätzlich durch die 25-%-Anzahlungsgrenze verschärft.",
    "Europäisches Parlament (Legislative Train)",
    "Revision of the package travel Directive",
    "2026-10-21",
    "https://www.europarl.europa.eu/legislative-train/theme-supporting-people-strengthening-our-societies-and-our-social-model/file-revision-of-the-package-travel-directive",
    "The agreement was adopted as Parliament's first reading position on 12 March 2026 with 537 votes in favour, two "
    "against and 24 abstentions. It was adopted by the Council unanimously on 30 March 2026. The directive was then "
    "signed on 29 April 2026 and published as Directive (EU) 2026/1024 on 8 May 2026.\n\n"
    "It simplified the definitions of package travel and linked travel arrangement and prevented retailers from "
    "requiring a downpayment higher than 25 % of the total price of the package, with certain exceptions.",
    "strong",
    ["flight_plus_hotel"],
    q("maximum downpayment for a travel package under Directive (EU) 2026/1024", 25, "percent"),
    "Sekundäre legislative Datenbank des EP (laufend aktualisiert); Abrufdatum 2026-10-21.",
    counters="flight_plus_hotel",
)

# ---------------------------------------------------------------- E19  (counter)
ev(
    "E19",
    "Paketvorteile UND Nachteile in der Ausnahmesituation: Bei Pauschalreise gilt Rücktrittsrecht mit voller "
    "Erstattung bei höherer Gewalt; bei getrennt gebuchten Leistungen muss nicht erbrachte Leistung nicht bezahlt "
    "werden, man hängt aber an der Kulanz des Anbieters und zahlt Stornoentgelt - und Reiserücktritts-/"
    "Reiseabbruchversicherungen decken höhere Gewalt regelmäßig NICHT ab.",
    "Verbraucherzentrale (Gemeinschaftsredaktion der Verbraucherzentralen)",
    "Urlaub stornieren oder abbrechen: Ihre Rechte bei Katastrophen und Krieg",
    "2026-08-03",
    "https://www.verbraucherzentrale.de/wissen/reise-mobilitaet/unterwegs-sein/urlaub-stornieren-oder-abbrechen-ihre-rechte-bei-katastrophen-und-krieg-10380",
    "Haben Sie Leistungen wie Flug und Unterkunft separat gebucht, brauchen Sie die Leistung dann nicht zu bezahlen, "
    "wenn sie nicht erbracht werden kann. Das kann der Fall sein, wenn ein Luftraum oder das Gebiet, in dem die "
    "Unterkunft liegt, gesperrt sind.\n\n"
    "Solange eine individuell gebuchte Unterkunft zugänglich und ohne Gesundheitsgefahr bewohnbar ist, sind Sie auf "
    "die Kulanz des Anbieters angewiesen und müssen mit einem Stornoentgelt rechnen, wenn Sie von der Reise "
    "absehen möchten.\n\n"
    "Bei unvermeidbaren, außergewöhnlichen Umständen wie Waldbränden hilft eine Reiserücktritts- oder "
    "Reiseabbruchversicherung in der Regel nicht, da ein solches Ereignis vertraglich meist nicht als Rücktritts- "
    "beziehungsweise Abbruchgrund vereinbart ist. Diese Versicherungen decken typischerweise andere Risiken ab, etwa "
    "eine Erkrankung vor oder während der Reise, einen erheblichen Schaden am Eigentum der versicherten Person oder den "
    "Tod eines nahen Angehörigen.",
    "strong",
    ["flight_plus_hotel", "separate_roundtrip"],
    NULLQ,
    "Belegt die Interrupt-Insurance-Caveat explizit: Reiseabbruchversicherungen decken höhere Gewalt NICHT - sie sind "
    "kein Argument für das Paket.",
    counters="flight_plus_hotel",
)

# ---------------------------------------------------------------- assembly
evidence = [e for e in EV if e["id"] not in {"E6", "E14", "E15", "E16", "E17", "E18", "E19"}]
counter_evidence = [e for e in EV if e["id"] in {"E6", "E14", "E15", "E16", "E17", "E18", "E19"}]

gap_notes = (
    "1) KEINE Häufigkeitsaussage: Die einzige große Split-Zahl (E1, bis 30 % / 29 %) ist ein Maximalwert JE ROUTE "
    "in der US-Feiertagssaison 2026 - kein Mittelwert, keine Wahrscheinlichkeit ('in x % der Fälle'), keine "
    "Euro-Angabe, keine europäische Route. Eine Runtime-Logik darf daraus KEINE x-%-Aussage ableiten.\n"
    "2) 'Getrennt ist IN DER REGEL günstiger' ist NICHT gedeckt: E6 (gleicher Vendor, gleiche Methodik) misst, dass "
    "Round-Trips MEIST günstiger sind und bei internationalen Routen teurer sein können; E14/E15 stützen die "
    "Gegenrichtung (höhere ADR für Pakete, 32 % sehen Paket-Rabatt als Top-Deal).\n"
    "3) FÜR FLUG+HOTEL GETRENNT VS. PAUSCHAL gibt es in dieser Recherche KEINEN belastbaren Prozent-/Eurobeleg. "
    "E10 belegt ausschließlich die MARKTVERTEILUNG der Buchungswege (49,4 % Veranstalter / 39,9 % Leistungsträger / "
    "10,7 % Produktportale), keine Preisdifferenz. Wer eine deutsche Prozentzahl 'Pauschale sind x % teurer' "
    "zitieren will, hat hier keinen Beleg - die Aussage darf in der Runtime nicht als Fakt erscheinen.\n"
    "4) KEIN AUFSCHLAGSNACHWEIS: Die ~30 % ADR-Differenz in E14 ist ein Selektionsbefund (Paketkunden = längere "
    "Aufenthalte, teurere Kategorien); der Artikel selbst nennt die Ursache als Upselling-Nutzen, nicht als Marge des "
    "Veranstalters.\n"
    "5) KEINE Luftfahrtverbands-Quelle (IATA/BDL/VDR) und keine DRV-Publikation quantifiziert den Split-Buchungs-Vorteil "
    "mit Häufigkeit oder Preis.\n"
    "6) KEINE europäischen oder EUR-spezifischen Split-Preiszahlen; E1/E6 sind USD-basiert und US-lastig.\n"
    "7) KEIN Primärbeleg zu 'Interrupt-Insurance' als Paketvorteil: E19 belegt das Gegenteil (Reiseabbruchversicherungen "
    "decken höhere Gewalt regelmäßig nicht). Ob eine Interrupt-Versicherung gerade Pauschalreisen bevorzugt, ist "
    "nicht belegt.\n"
    "8) Gepäckdurchgang ist nur als NICHT-MONETÄRER Vorteil des Ein-Tickets belegt (E8 'checking your luggage only "
    "once'; E5 kein Durchgang bei getrennten Tickets) - kein Euro-Beleg.\n"
    "9) Datierung: E5 (2014), E14 (Daten 2017 / Veröffentlichung 2018) und E15 (Daten 2022) sind alt und tragen "
    "nur Struktur-, nicht Aktualitätsaussagen; E11 (Stand 2020) liegt vor der Novellierung 2026/1024.\n"
    "10) NICHT VERIFIZIERT UND NICHT VERWENDET: (a) FUR 'Reiseanalyse 2026 - Erste ausgewählte Ergebnisse' "
    "(Spiegel Oberösterreich-Tourismus, https://www.oberoesterreich-tourismus.at/fileadmin/user_upload/"
    "oberoesterreich-tourismus/Dokumente/Marktforschung/Reise-Analyse-2026_ErsteErgebnisse_Zusammenfassung.pdf) - "
    "Server-Timeout bei allen Download-Versuchen; der Suchindex nennt 'Knapp 50 % […] Pauschal-/Bausteinreise' und "
    "'34,2 % Einzelbuchungen von Unterkünften', diese Zahlen sind NICHT verifiziert und werden NICHT verwendet. "
    "(b) btw-Pressemitteilung vom 18.03.2026 zu Geschäftsreisen (Connection refused) - der Geschäftsreisen-Ausschluss "
    "wird stattdessen über E16 belegt. (c) Mize-Blog mit der 30-%-ADR-Aussage ohne Primärbeleg. (d) Skyscanner-Guide "
    "(nur JS-renderbar). (e) REISE & PREISE 'Test Pauschal- vs. Individualreise' (Preiserhebung 13.-15.05.2011) - "
    "inhaltlich lesbar und relevant ('bis zu 30 Prozent', 'durchschnittlich 15 Prozent'), aber nicht aktuell und daher "
    "kein Beleg.\n"
    "11) EMPFOHLENE LOGIK-AUSRICHTUNG: statt 'getrennt ist günstiger' -> 'vergleiche live Round-Trip vs. 2x Einweg vs. "
    "Multi-City vs. Paket und nenne die konkreten Preisunterschiede'; Split nur empfehlen, wenn kein Anschlussschutz, "
    "kein Gepäckdurchgang und keine Umbuchbarkeit benötigt wird; Paket empfehlen bei Insolvenzschutz, Beistand, "
    "Übertragbarkeit, kostenfreiem Storno bei höherer Gewalt (E16-E19); Geschäftsreisen gesondert prüfen, da der "
    "Pauschalreisenschutz für bestimmte Geschäftsreisen nicht gilt (E16)."
)

out = {
    "generated_at": "2026-10-21T18:15:00+02:00",
    "topic": "Getrennte Buchungen vs. Paket (Pauschale) - Fähigkeit 2 'Intelligente Kombination'",
    "language": "de",
    "method": (
        "Web-Recherche am 2026-10-21. Jede als Beleg geführte Quelle wurde tatsächlich geöffnet und im Volltext "
        "gelesen (PDFs heruntergeladen und per pdfminer extrahiert; eine per 403 blockierte Seite über den "
        "Wayback-Snapshot verifiziert). Nicht öffenbare Quellen sind unter gap_notes als 'nicht verifiziert' gelistet "
        "und werden nicht als Beleg verwendet. Zitate sind verbatim. IDs E1-E19 sind stabil und deckungsgleich mit "
        "docs/EVIDENCE_SPLIT_BOOKING.md."
    ),
    "supports_vocabulary": {
        "separate_roundtrip": "Zwei getrennte Einwegtickets statt eines Round-Trip-Tickets",
        "mixed_airlines": "Hin- und Rückflug bei unterschiedlichen Airlines (open jaw / Hacker Fare)",
        "flight_plus_hotel": "Flug und Hotel getrennt statt als Pauschalpaket",
    },
    "evidence": evidence,
    "counter_evidence": counter_evidence,
    "gap_notes": gap_notes,
}

here = os.path.dirname(os.path.abspath(__file__))
target = os.path.join(os.path.dirname(here), "bundling", "evidence.json")
with open(target, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
    f.write("\n")
print("written:", target)
print("evidence:", [e["id"] for e in evidence])
print("counter_evidence:", [e["id"] for e in counter_evidence])
