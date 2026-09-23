# Leercontainer-Repositionierung: Wie weit vorausschauen? – Streamlit-Demo

*(noch nicht deployed)*

Interaktive Fall-Demo zur **Leercontainer-Repositionierung** einer Reederei: nach dem Löschen ist ein Container leer, an Überschusshäfen stapeln sich leere Boxen, an Mangelhäfen fehlen sie für neue
Ladung. Die Demo beantwortet: **Wie weit muss eine Reederei vorausschauen (in Perioden), um nah am wirtschaftlichen Optimum zu bleiben, statt rein reaktiv zu planen oder den ganzen
Planungshorizont sehen zu müssen?**

Teil des Portfolios für die Website „Sebastian Hanisch – Operations Research und Machine Learning", **Welle 1 der neuen Seefracht-Linie** (Schwesterlinie zur Hafen-Linie). Vehikel: ein
Zeit-Raum-Netz aus Häfen und Perioden, gelöst als Min-Cost-Flow; koppelt inhaltlich an `freight_demo` (Hafenwahl je Sendung bestimmt die Container-Nachfrage je Hafen), ohne technische Abhängigkeit
zwischen den Repos.

## Warum dieses Problem

Reine Reaktion (nur die gerade abgelaufene Periode kennen) ist in der Standardinstanz massiv teurer als das Optimum – kein Grenzfall, robust über fünf unabhängige Messreihen (Vorlaufzeit,
Volatilität, Notleasing-Preis, Hafenzahl, siehe `seefracht-planung/messreihe_ecr/ERGEBNIS.md`). Aber die Lücke schließt sich schnell: schon bei einer Vorschau von etwa der 1,5- bis 2-fachen
mittleren Vorlaufzeit liegt der Rest-Abstand unter 5 %, **nicht erst bei voller Horizontsicht**. Der Aufhänger ist deshalb **wie weit** vorausschauen, nicht **ob**.

## Modell

Zeit-Raum-Netz aus *P* Häfen × *T* Perioden. Jeder Hafen hat eine Netto-Einspeisung je Periode (positiv = freiwerdende Leercontainer, negativ = Bedarf), über den Horizont auf Summe 0 zentriert.
Haltekanten (ein Hafen zur nächsten Periode) kosten wenig; Transportkanten (ein Hafen zu einem anderen) kosten distanzabhängig und brauchen eine Vorlaufzeit = Distanz/Geschwindigkeit (aufgerundet
auf mindestens 1 Periode) – nichts fließt rückwärts in der Zeit. Eine Notleasing-Kante ersetzt eine harte Bilanzpflicht: unbefriedigter Bedarf löst eine feste Strafe je Container aus, realistisch
als kurzfristiges Zumieten/Chartern gedeutet – das Modell ist dadurch immer lösbar. Formal im Expander „📐 Mathematische Formulierung" der App.

## Methodik – eine Reglerfamilie: das Vorschau-Fenster k

Anders als bei den meisten Hafen-Demos gibt es hier **eine stetige Familie über einen einzigen Parameter** k, keine drei qualitativ verschiedenen Regeln:

- **🙈 Rein reaktiv (k=0)**: kennt nur die gerade abgelaufene Periode – die Referenz aller Vergleiche.
- **👀 Eingestellte Vorschau (k)**: plant bei jeder Periode denselben Min-Cost-Flow, aber nur über das Fenster [t, t+k]; führt nur die dort abgehenden Entscheidungen aus, rollt weiter.
- **🔮 Volle Vorschau (k=Perioden−1)**: kennt von Anfang an den ganzen Horizont = das exakte Optimum. **Kein separater Exakt-Algorithmus**: derselbe Löser, nur mit maximalem Fenster.

**Min-Cost-Flow-Löser**: sukzessive kürzeste Wege via Dijkstra mit Potentialen (Johnson-Technik), unverändert aus `messreihe_ecr/ecr.py` übernommen. Eine erste SPFA/Warteschlangen-Bellman-Ford-
Variante degenerierte auf dieser Kantenstruktur (viele negative Restkanten nach Augmentierungen) schon bei kleinen Instanzen zu unbrauchbarer Laufzeit – der wichtigste Fallstrick dieser Demo, siehe
`ERGEBNIS.md`.

## Befunde (gemessen, keine Behauptungen)

Standardinstanz (5 Häfen, 10 Perioden, Geschwindigkeit 22, Volatilität 3, Notleasing 200); Population = 40 Instanzen (Seeds 0–39), Verhältnis der Mittelwerte (siehe `tools/PRESET_SWEEP.md`).

| Frage | Befund | Test |
|---|---|---|
| Wie teuer ist reine Reaktion? | k=0 kostet **+156 %** gegenüber dem Optimum in der Standardinstanz (Population 40 Instanzen); über die vier Presets mit einem k=0-Kriterium zwischen +156 % und +234 % | `test_preset_stories.py`, `test_evaluation.py` |
| Wie schnell schließt sich die Lücke? | Bei k=4 (≈1,6× mittlere Vorlaufzeit) nur noch **+5,2 %** Aufschlag in der Standardinstanz | `test_preset_stories.py` |
| Skaliert die nötige Vorschau mit der Vorlaufzeit oder mit T? | Mit der Vorlaufzeit: kurze Routen brauchen ab k≈3 kaum noch Vorschau (+8,3 % bei k=3), lange Routen erst ab k≈6 (+2,6 % bei k=6) – nie bei fast dem ganzen Horizont | `test_preset_stories.py` |
| Ist mehr Vorschau je verschlechternd? | Nein: Monotonie über 25 Zufallsinstanzen ausnahmslos bestätigt, 0 Verletzungen | `test_rolling.py::test_monotonicity_more_lookahead_never_hurts` |
| Reproduziert die volle Vorschau ab t=0 den einmaligen globalen Solve? | Ja, bitgleich über 45 Zufallsinstanzen (3 Hafenzahlen × 15 Seeds) | `test_rolling.py::test_full_lookahead_from_start_matches_single_global_solve` |
| Ist Kausalität hart? | Ja: Überschuss vor Bedarf kostet nur Transport (110 in der Handinstanz); Überschuss nach Bedarf erzwingt die volle Notleasing-Strafe (1000) – keine Vorschau kann das reparieren | `test_flow.py`, `test_rolling.py::test_unreachable_demand_forces_full_penalty_regardless_of_lookahead` |
| Wie schnell löst ein einzelnes Fenster? | Standardgröße wenige Millisekunden; größte Instanz (8 Häfen × 14 Perioden) rund 25–30 ms (siehe Befunde/Korrekturen unten) | manuell gemessen, AP 0 |

## Befunde und Korrekturen gegenüber dem Plan

- **Rechenzeit-Behauptung des Plans korrigiert.** Der Detailplan nennt „unter 5 ms" für die größte Instanz (8 Häfen × 14 Perioden). Nachgemessen (AP 0) liegt ein einzelner Min-Cost-Flow-Solve dort
  bei rund 25–30 ms; nur bei der **Standardgröße** (5 Häfen × 10 Perioden) stimmt „unter 5 ms" (gemessen 2,3–4,0 ms). Die App-Texte nennen jetzt beide Zahlen statt einer pauschalen Behauptung –
  weiterhin schnell genug für eine Live-Berechnung ohne Knopf, aber die ursprüngliche Zahl war zu optimistisch für den Reglerrand.
- **Preset-Population auf 40 statt 30–60 Instanzen festgelegt.** Die Plan-Schwellen (Abschnitt 7) reproduzieren exakt die Zahlen aus `messreihe_ecr/sweep.py`, das für die Vorlaufzeit-/
  Volatilitäts-/Notleasing-Varianten `range(40)` verwendet (nur die Basis-Messreihe nutzte 60). Eine erste Probe mit 60 Instanzen ließ das Kriterium „Lange Route, k=6 < 3 %" knapp kippen
  (+3,1 % statt +2,6 %) – mit 40 Instanzen reproduzieren alle fünf Presets die Plan-Zahlen mit Marge. Siehe `tools/PRESET_SWEEP.md`.
- **Preset-Seed-Suche um ein Vorlaufzeit-Typizitätsband ergänzt.** Ein reiner Kosten-Kriterien-Filter hätte für „Lange Route" einen Seed mit einer für seine eigene Familie untypisch kurzen
  mittleren Vorlaufzeit zulassen können (gefunden: Seed 248, Vorlaufzeit 2,9 Perioden gegen einen Populationsmedian von 5,2). `tools/tune_presets.py` verlangt jetzt zusätzlich, dass die
  Vorlaufzeit der gezeigten Instanz zwischen dem 10. und 90. Perzentil ihrer eigenen Population liegt.
- **`mean_markup` misst das Verhältnis der Mittelwerte, nicht den Mittelwert der Einzel-Aufschläge.** Naiv gemittelte Einzel-Prozentwerte verzerren stark, sobald eine Instanz ein kleines Optimum
  hat (ein kleiner Nenner bläst den eigenen Prozentwert auf); die Methode folgt jetzt `messreihe_ecr/sweep.py`s eigener `report()`-Funktion (Differenz der Mittelwerte, nicht Mittel der
  Differenzen) und reproduziert damit die Plan-Zahlen exakt.

## Ehrliche Grenzen

- Die Vorschau ist **perfekt** innerhalb des Fensters (kein Prognosefehler) – das misst den **Wert von Information**, nicht Robustheit gegen Prognoseunschärfe.
- **Kein struktureller Dauerüberschuss/-mangel** (Summe 0 je Instanz); echte globale Ungleichgewichte (z. B. ein starkes Export-Import-Ungleichgewicht einer Region) sind nicht modelliert.
- **Transport- und Lagerkapazität sind unbegrenzt** (kein Wettbewerb mit bezahlter Fracht um Schiffsraum, keine Yard-Grenze).
- **Vorlaufzeiten sind deterministisch** (keine Fahrzeitschwankung).
- Kostenparameter (Haltekosten, Transportrate, Notleasing-Strafe) sind illustrativ, nicht an echten Frachtraten kalibriert.
- Die Heuristik plant selbst im Fenster exakt (derselbe Min-Cost-Flow, nur mit kürzerem Horizont) – das isoliert sauber den Informationswert, misst aber **nicht**, wie viel eine einfache
  Faustregel-Heuristik (z. B. „nächstgelegener Überschusshafen zuerst") zusätzlich verliert.

## Tests

`python -m pytest tests/ -v` – 237 Tests, rund 3 Minuten. Zusammensetzung:

- **Szenario** (`test_scenario.py`): Häfen, Distanzen, Vorlaufzeit-Matrix, Netto-Einspeisung (Determinismus, Summe nahe 0), Fehlerfälle (zu wenige Häfen/Perioden).
- **Min-Cost-Flow** (`test_flow.py`): Handinstanzen aus `messreihe_ecr/check.py` (Kausalität – Überschuss vor/nach Bedarf), Flusserhaltung, k=0 ohne jede Kante.
- **Rollierender Horizont** (`test_rolling.py`): volle Vorschau ab t=0 = einmaliger globaler Solve (45 Instanzen), Monotonie über k (25 Instanzen), Randfälle (kein Bedarf, unerreichbarer Bedarf,
  minimale Hafenzahl, eine Periode), aufgezeichnete Schritte gegen die Aggregatwerte.
- **Auswertung** (`test_evaluation.py`): Kosten-über-k-Kurve gegen Direktrechnung, Monotonie, Verhältnis-der-Mittelwerte-Methode an einem Kontrastbeispiel, Urteil in drei Zuständen und genau an
  der Schwelle, Faustregel k*, Diagnose in drei Zuständen.
- **Regler** (`test_presets.py`): Permalink-Parsing/-Klemmen/-Runden, berechnete Grenze des Vorschau-Fensters, Presets, Seed-Knopf.
- **Presets** (`test_preset_stories.py`): Geschichte im Mittel von 40 Instanzen UND am gezeigten Seed; der gezeigte Seed liegt außerhalb der Population und ist typisch (Kosten-Aufschlag UND
  mittlere Vorlaufzeit je zwischen dem 10. und 90. Perzentil); Kriterien sind nicht trivial erfüllt für ein falsches Preset; Reproduktion der Vorab-Messreihe. Zusätzlich (`test_stories.py`):
  jedes einzelne Abnahmekriterium an künstlichen Werten, die genau an seiner Schwelle kippen.
- **Figuren** (`test_visualization.py`): Kosten-Kurve, Vergleichskurve, Hafenkarte (Farben, Pfeile je Transport, Notleasing-Ring) – alle Achsen fest.
- **PDF** (`test_pdf_export.py`): Sonderzeichen-Bereinigung (fpdf2 stürzt bei „–", „€", Emoji ab), Inhalt für jede Diagnose-Art, Randfälle (kleinste/größte Instanz).
- **End-to-End** (`test_app.py`, AppTest): Skelett und Footer, jedes Preset, Permalink mit berechneter Grenze, alle Regler an Min und Max, die bedingte Meldung in allen drei Zuständen, Urteil in
  allen Zuständen, Vergleichstabelle, PDF, Texte.

Zusätzlich ein Fehler-Einbau-Test (`tools/mutation_check.py`, 40 Mutanten über `lcr_flow`, `lcr_scenario`, `lcr_rolling`, `lcr_evaluation`, `lcr_presets`, `lcr_stories`): **34 gefunden, 6 überlebt,
0 Fehler in der Mutantenliste.** Alle sechs Überlebenden sind gleichwertig (kein sichtbarer Unterschied im Verhalten):

- Zwei betreffen Knoten mit Netto-Einspeisung genau 0 (`value > 0` → `>=`, `elif value < 0` → `<=`): der dabei zusätzlich eingefügte Graph-Kante hat Kapazität 0 und trägt nie Fluss.
- Eine betrifft die Dijkstra-Tie-Break-Regel (`nd < dist[to]` → `<=`): ändert bei gleicher Distanz höchstens, welcher von mehreren gleich teuren Wegen gewählt wird, nie die Kosten.
- Zwei betreffen die Pending-Buchhaltung in `lcr_rolling.py` (`arr > t + 1` → `>=`, `arr < T` → `<=`): die erste ist durch die vorangehende `if`-Verzweigung bereits ausgeschlossen, die zweite
  legt einen Eintrag für eine Periode an, die die äußere Schleife nie erreicht (beides tote Fälle, kein Verhaltensunterschied).
- Eine betrifft die Klarheitsschwelle des Urteils genau bei zwei Standardfehlern (`<=` → `<`): eine Gleitkomma-Grenze, die sich nicht bit-exakt und zugleich robust testen lässt (derselbe
  akzeptierte Fall wie in `reefer-demo`).

## Dateistruktur

| Datei | Inhalt | Herkunft |
|---|---|---|
| `app.py` | Streamlit-Hauptablauf: Presets, Sidebar, Hauptansicht, Kernabschnitt, Vergleich, Texte | neu |
| `lcr_constants.py` | Regler-Grenzen, `PRESETS`, Ausprägungen, Farben, feste Modellparameter | neu |
| `lcr_presets.py` | `SETTING_SPECS`, Permalink (mit Vorschau-Begrenzung), Presets, Seed-Knopf | Muster `rfr_presets.py` |
| `lcr_scenario.py` | Häfen, Distanzen, Vorlaufzeiten, Netto-Einspeisung je Periode | `messreihe_ecr/ecr.py`, umbenannt |
| `lcr_flow.py` | Min-Cost-Flow (Dijkstra + Potentiale) über ein Fenster | `messreihe_ecr/ecr.py`, unverändert übernommen |
| `lcr_rolling.py` | Rollierender Horizont mit Vorschau k, Buchhaltung, Schritt-Aufzeichnung | `messreihe_ecr/ecr.py`, um `record=True` erweitert |
| `lcr_evaluation.py` | Stichprobe, Kosten-über-k-Kurve, gepaarte Urteile, Faustregel, Diagnose | Muster `rfr_evaluation.py` |
| `lcr_visualization.py` | Hafenkarte, Kosten-Kurve, Vergleichskurve (alle Achsen fest) | Muster `rfr_visualization.py` |
| `lcr_ui_panel.py` | Kennzahlen (2×2) und Karte je Ausprägung | Muster `rfr_ui_panel.py` |
| `lcr_pdf_export.py` | PDF-Export (`fpdf2`, Sonderzeichen-Bereinigung) | Muster `rfr_pdf_export.py` |
| `lcr_stories.py` | Abnahmekriterien der Presets | Muster `rfr_stories.py` |
| `tools/tune_presets.py`, `tools/PRESET_SWEEP.md` | Preset-Abstimmung und ihr Bericht | neu |
| `tools/mutation_check.py` | Fehler-Einbau-Test | neu |
| `tests/` | siehe oben | neu |

## Bewusst nicht umgesetzt (mögliche Erweiterungen)

- **Prognoseunschärfe im Vorschau-Fenster** (Rauschen auf die im Fenster sichtbaren Werte statt perfekter Sicht).
- **Struktureller Dauerüberschuss/-mangel** als eigener Regler (feste globale Schieflage statt Summe 0 je Instanz).
- **Kapazitätsgrenzen** auf Transportkanten (Schiffsraum) oder Häfen (Yard).
- **Vorlaufzeit-Schwankung** statt deterministischer Vorlaufzeit.
- **Vergleich gegen eine einfache Faustregel-Heuristik** (z. B. „nächstgelegener Überschusshafen zuerst") statt nur gegen sich selbst mit kürzerem Fenster.
- **Exakter Löser als eigener Tab**: nicht nötig – die volle Vorschau (k=Perioden−1) IST bereits die exakte Referenz, explizit im Text statt in einem separaten Tab.

## Verwandte Demos mit demselben mathematischen Modell

Verschiedene Themen im Portfolio teilen (fast) dasselbe Modell. Vor einer neuen Demo-Idee deshalb das
Modell vergleichen, nicht die Kulisse (Stand 2026-09-23):

- **Rückladungen finden / Leerfahrten im Straßengüterverkehr reduzieren** ist derselbe Bestandsausgleich im Zeit-Raum-Netz
  mit Lkw statt Containern (Min-Cost-Flow, Vorschau-Fenster). Als Dopplung verworfen. Ob der Befund "Vorschau von etwa dem
  1,5- bis 2-Fachen der Vorlaufzeit genügt" dort ebenfalls gilt, ist eine Vermutung, nicht gemessen. Ein VRP mit
  Rückladungen (Backhauls) auf Tourenebene wäre ein Routing-Modell, kein Fluss.

## Lokal ausführen

```bash
pip install -r requirements-dev.txt
streamlit run app.py
```

Tests: `python -m pytest tests/ -v`. Preset-Abstimmung: `python tools/tune_presets.py population|seeds`. Fehler-Einbau: `python tools/mutation_check.py`.

---

Gebaut mit Streamlit, Plotly und fpdf2.
