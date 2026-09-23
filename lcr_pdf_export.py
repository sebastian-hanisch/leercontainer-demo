"""PDF-Export des Ergebnisses (fpdf2, Helvetica-Kernschrift, nur Text und Tabellen).

Die Kernschriften kennen nur Latin-1: Umlaute sind erlaubt, aber "-" (Gedankenstrich), "-" (Minuszeichen),
"EUR"-Zeichen, Sigma, >=, <=, Emoji usw. lassen fpdf2 abstürzen. Deshalb läuft jeder Text durch
pdf_text(); Ausprägungen erscheinen mit ihren Kurznamen ohne Emoji."""
import time

import lcr_constants as C
import lcr_evaluation as E

_REPLACEMENTS = {
    "–": "-", "—": "-", "‑": "-", "−": "-", "Σ": "Summe", "σ": "sigma", "≥": ">=", "≤": "<=", "→": "->", "≈": "ca.", "€": "EUR", "±": "+-",
    "·": "-", """: '"', """: '"', "„": '"', "'": "'", "'": "'", "⚠️": "(!)", "⚠": "(!)", "✅": "", "ℹ️": "", "🙈": "", "👀": "", "🔮": "", "📦": "", "📐": "",
}


def pdf_text(text):
    """Text für die Helvetica-Kernschrift: bekannte Sonderzeichen ersetzen, den Rest Latin-1-sicher machen."""
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


def short_name(key):
    return C.MODE_SHORT[key]


def diagnosis_text(diag):
    """Die bedingte Meldung der App als Satz ohne Emoji."""
    if diag.kind == "too_short":
        return (f"Die eingestellte Vorschau (k={diag.configured_k}) ist kürzer als die mittlere Vorlaufzeit ({diag.mean_lead:.1f} Perioden): "
               f"mindestens auf die Vorlaufzeit erhöhen, sonst bleibt Notleasing kaum vermeidbar. Abstand zum Optimum: {diag.gap_pct:.1f} %.")
    if diag.kind == "near_optimal":
        return f"Mit k={diag.configured_k} liegt der Abstand zum Optimum bei {diag.gap_pct:.1f} % - kaum noch Luft nach oben, mehr Vorschau lohnt sich kaum."
    return f"Mit k={diag.configured_k} liegt der Abstand zum Optimum bei {diag.gap_pct:.1f} %."


def verdict_text(v, label, unit="Kosten"):
    if v.kind == "better":
        amount = f"{abs(v.pct):.0f} % weniger" if v.pct is not None else f"{abs(v.diff):.0f} weniger"
        return f"{label}: im Mittel {amount} {unit} ({v.diff:+.0f} je Instanz, Standardfehler {v.se:.0f})."
    if v.kind == "worse":
        amount = f"{v.pct:.0f} % mehr" if v.pct is not None else f"{v.diff:.0f} mehr"
        return f"{label}: im Mittel {amount} {unit} ({v.diff:+.0f} je Instanz, Standardfehler {v.se:.0f})."
    return f"{label}: kein klarer Unterschied (Differenz {v.diff:+.0f} {unit}, Standardfehler {v.se:.0f})."


def generate_lcr_pdf(p, seed, inst, outcomes, diag, k_star, sample=None, costs=None, compress=True):
    """Ergebnis der aktuellen Einstellung als PDF: Szenario, Ausprägungsvergleich, Diagnose, Kosten-
    über-k-Kurve, Urteil über die Stichprobe, Hinweise zum Modell.

    `p`: E.Params; `outcomes`: die drei Outcomes (einer Instanz); `diag`: E.Diagnosis; `sample`:
    Tupel von InstanceResult oder None; `costs`: Kosten-über-k-Kurve dieser Instanz oder None."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    by_key = {o.key: o for o in outcomes}
    reactive, configured, full = by_key[C.MODE_REACTIVE], by_key[C.MODE_CONFIGURED], by_key[C.MODE_FULL]

    pdf = FPDF()
    pdf.set_compression(compress)
    pdf.add_page()

    def line(text, height=7, width=0):
        pdf.cell(width, height, pdf_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def heading(text):
        pdf.set_font("Helvetica", "B", 12)
        line(text, 8)
        pdf.set_font("Helvetica", "", 10)

    def pairs(rows):
        for label, value in rows:
            pdf.cell(75, 6, pdf_text(label), border=0)
            line(value, 6)

    def table(headers, widths, rows):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(230, 230, 230)
        for header, width in zip(headers, widths):
            pdf.cell(width, 7, pdf_text(header), border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(7)
        pdf.set_font("Helvetica", "", 9)
        for row in rows:
            for value, width in zip(row, widths):
                pdf.cell(width, 7, pdf_text(str(value)), border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.ln(7)

    def keep_together(height):
        if pdf.get_y() + height > pdf.h - pdf.b_margin:
            pdf.add_page()

    def note(text, size=8):
        pdf.set_font("Helvetica", "I", size)
        pdf.set_text_color(110, 110, 110)
        pdf.multi_cell(0, 5, pdf_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)

    pdf.set_font("Helvetica", "B", 16)
    line("Leercontainer-Repositionierung: Wie weit vorausschauen?", 10)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    line(f"Erstellt: {time.strftime('%d.%m.%Y %H:%M')}  -  sebastianhanisch.net", 6)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    heading("Szenario")
    pairs([("Häfen / Perioden", f"{p.n_ports} / {p.n_periods}"), ("Schiffsgeschwindigkeit", f"{p.speed} (mittlere Vorlaufzeit {diag.mean_lead:.2f} Perioden)"),
           ("Volatilität des Aufkommens", str(p.sigma)), ("Notleasing-Kosten je Container", str(p.penalty)),
           ("Vorschau-Fenster k / Faustregel k*", f"{configured.k} / {k_star}"), ("Seed", str(seed))])
    pdf.ln(3)

    heading("Zusammenfassung")
    note(diagnosis_text(diag), 9)
    pairs([(short_name(o.key), f"Gesamtkosten {o.result.total:,.0f}, davon Notleasing {o.result.shortfall_cost:,.0f}".replace(",", ".")) for o in outcomes])
    pdf.ln(3)

    heading("Vergleich der Vorschau (diese Instanz)")
    rows = []
    for o in outcomes:
        r = o.result
        gap = 100.0 * (r.total - full.result.total) / full.result.total if full.result.total else 0.0
        rows.append([short_name(o.key), o.k, f"{r.total:,.0f}".replace(",", "."), f"{r.shortfall_cost:,.0f}".replace(",", "."),
                     f"{r.transport + r.hold:,.0f}".replace(",", "."), f"{gap:.1f}"])
    table(["Ausprägung", "k", "Gesamtkosten", "Notleasing", "Transport+Halten", "Abstand Opt. (%)"], [38, 12, 32, 30, 38, 32], rows)
    pdf.ln(3)

    if costs is not None:
        keep_together(90)
        heading("Kosten über dem Vorschau-Fenster")
        exact = costs[-1]
        table(["k", "Gesamtkosten", "Abstand zum Optimum (%)"], [20, 40, 60],
              [[k, f"{c:,.0f}".replace(",", "."), f"{E.markup_pct(c, exact):.1f}"] for k, c in enumerate(costs)])
        note(f"Faustregel k* = {k_star} (ca. 1,6-fache mittlere Vorlaufzeit). k={len(costs) - 1} ist die volle Vorschau = das Optimum, kein separater Exakt-Algorithmus.")
        pdf.ln(3)

    if sample is not None:
        keep_together(70)
        heading("Urteil über die Stichprobe")
        v1 = E.verdict(sample, "configured", "reactive")
        v2 = E.verdict(sample, "configured", "exact")
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, pdf_text("- " + verdict_text(v1, "Eingestellte Vorschau gegen rein reaktiv")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.multi_cell(0, 5, pdf_text("- " + verdict_text(v2, "Eingestellte Vorschau gegen das Optimum")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        note(f"Basis: {len(sample)} Instanzen (Seeds 0-{len(sample) - 1}, nicht der eingestellte Seed) mit den eingestellten Werten. Klar heisst: Unterschied größer als zwei "
             "Standardfehler der gepaarten Differenz.")
        pdf.ln(3)

    keep_together(70)
    heading("Hinweise zum Modell")
    pdf.set_font("Helvetica", "", 9)
    for text in [
        "Zeit-Raum-Netz aus Häfen und Perioden; Haltekanten (Lagerkosten je Periode), Transportkanten (distanzabhängige Kosten, Vorlaufzeit = Distanz/Geschwindigkeit) und eine "
        "Fehlmengen-/Notleasing-Kante statt harter Bilanzpflicht - dadurch immer lösbar.",
        "Die Vorschau ist innerhalb des Fensters perfekt (kein Prognosefehler): das misst den Wert von Information, nicht Robustheit gegen Prognoseunschärfe.",
        "Kein struktureller Dauerüberschuss/-mangel (Summe 0 je Instanz); Transport- und Lagerkapazität unbegrenzt; Vorlaufzeiten deterministisch.",
        "Min-Cost-Flow mit Dijkstra und Potentialen (Johnson-Technik); dieselbe Rechnung für alle drei Ausprägungen, nur mit unterschiedlichem Vorschau-Fenster.",
        "Alle Zahlen sind Größenordnungen aus einem vereinfachten Modell, keine Messung an echten Reedereidaten.",
    ]:
        pdf.multi_cell(0, 5, pdf_text("- " + text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())
