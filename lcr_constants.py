"""Konstanten der Leercontainer-Repositionierungs-Demo (Welle 1 Seefracht-Linie).

Modell und Zahlen aus messreihe_ecr/ (siehe seefracht-planung/plan_ecr.html, ERGEBNIS.md). Presets
werden mit tools/tune_presets.py gegen die Abnahmekriterien in lcr_stories.py geprüft; die Seeds
hier sind das Ergebnis dieser Abstimmung (siehe tools/PRESET_SWEEP.md)."""

# --- Regler -------------------------------------------------------------------------------------------
N_PORTS_RANGE, N_PORTS_DEFAULT = (3, 8), 5
N_PERIODS_RANGE, N_PERIODS_DEFAULT = (6, 14), 10
SPEED_RANGE, SPEED_DEFAULT, SPEED_STEP = (10, 40), 22, 5
SIGMA_RANGE, SIGMA_DEFAULT = (1, 7), 3
PENALTY_RANGE, PENALTY_DEFAULT, PENALTY_STEP = (50, 800), 200, 50
SEED_RANGE, SEED_DEFAULT = (0, 9999), 0
# k (Vorschau-Fenster) hat eine BERECHNETE Obergrenze (Perioden - 1); die Spezifikationsgrenze hier
# ist die weiteste mögliche (N_PERIODS_RANGE[1] - 1), der Regler in der App begrenzt auf Perioden-1.
K_RANGE = (0, N_PERIODS_RANGE[1] - 1)

# --- feste Modellparameter (aus messreihe_ecr, keine Regler) ------------------------------------------
SIGMA_BIAS = 8.0        # Stärke der Import-/Export-Neigung je Hafen (die Volatilität steuert nur das Rauschen je Periode)
HOLD_COST = 0.3         # Kosten je Container und Periode am Lager
RATE = 1.0              # Transportkosten je Container und Distanzeinheit
K_STAR_FACTOR = 1.6     # Faustregel k* ~= 1,6 x mittlere Vorlaufzeit (siehe ERGEBNIS.md)

# --- Auswertung -----------------------------------------------------------------------------------------
SAMPLE_INSTANCES = 30       # Instanzen je Urteil im Kernabschnitt (Plan Abschnitt 6)
POPULATION_INSTANCES = 40   # Instanzen für die Preset-Abnahme (Plan Abschnitt 7: 30-60 Instanzen;
                             # 40 reproduziert exakt die Stichprobengröße der Vorab-Messreihe
                             # für die Vorlaufzeit-/Volatilitäts-/Notleasing-Varianten, siehe ERGEBNIS.md)
VERDICT_Z = 2.0              # klar ab mehr als VERDICT_Z Standardfehlern der gepaarten Differenz
NEAR_OPTIMAL_PCT = 2.0        # Abstand zum Optimum, ab dem "kaum noch Luft nach oben" gilt
SHORT_PREVIEW_PCT = 100.0     # zu-kurze Vorschau: Meldung greift zusätzlich, wenn k < mittlere Vorlaufzeit

# --- Ausprägungen: die eine Reglerfamilie Vorschau-Fenster k (Plan Abschnitt 3) ------------------------
MODE_REACTIVE, MODE_CONFIGURED, MODE_FULL = "reactive", "configured", "full"
MODE_KEYS = (MODE_REACTIVE, MODE_CONFIGURED, MODE_FULL)
MODE_LABELS = {
    MODE_REACTIVE: "🙈 Rein reaktiv (k=0)",
    MODE_CONFIGURED: "👀 Eingestellte Vorschau (k)",
    MODE_FULL: "🔮 Volle Vorschau (Optimum)",
}
MODE_SHORT = {MODE_REACTIVE: "Rein reaktiv", MODE_CONFIGURED: "Eingestellt", MODE_FULL: "Volle Vorschau"}
MODE_DESCRIPTIONS = {
    MODE_REACTIVE: "Kennt nur die gerade abgelaufene Periode, keine Vorausplanung. Jeder Bedarf, der nicht schon jetzt gedeckt ist, zahlt die volle Notleasing-Strafe. "
                   "Die Referenz aller Vergleiche in dieser Demo: die Kosten des Nichtwissens.",
    MODE_CONFIGURED: "Plant bei jeder Periode exakt über das Fenster [t, t+k], führt nur die bei t abgehenden Entscheidungen aus und rollt einen Schritt weiter. "
                     "Dieselbe Rechnung wie bei rein reaktiv und voller Vorschau, nur mit einem mittleren Fenster - die kluge Mitte.",
    MODE_FULL: "Kennt den ganzen Planungshorizont von der ersten Periode an = das exakte Optimum. Kein eigener Exakt-Algorithmus: derselbe Löser, nur mit maximalem Fenster.",
}
BASELINE = MODE_REACTIVE

# --- Darstellung ----------------------------------------------------------------------------------------
MODE_COLORS = {MODE_REACTIVE: "#c0392b", MODE_CONFIGURED: "#2a6fb0", MODE_FULL: "#2e7d4f"}
SURPLUS_COLOR = "#2a6fb0"
DEFICIT_COLOR = "#c0392b"
TRANSPORT_LINE_COLOR = "#5b6b80"
SHORTFALL_RING_COLOR = "#c0392b"
MARKER_LINE_COLOR = "#808895"
EXACT_LINE_COLOR = "#2e7d4f"
CHART_HEIGHT = 380
MAP_HEIGHT = 460

# --- Presets (Plan Abschnitt 7; Seeds >= POPULATION_INSTANCES, per tools/tune_presets.py abgestimmt) ----
PRESETS = {
    "Standard": dict(n_ports=5, n_periods=10, speed=22, sigma=3, penalty=200, k=4, seed=636),
    "Kurze Route": dict(n_ports=5, n_periods=10, speed=40, sigma=3, penalty=200, k=3, seed=1119),
    "Lange Route": dict(n_ports=5, n_periods=10, speed=10, sigma=3, penalty=200, k=3, seed=1111),
    "Unruhiges Aufkommen": dict(n_ports=5, n_periods=10, speed=22, sigma=7, penalty=200, k=4, seed=991),
    "Teures Notleasing": dict(n_ports=5, n_periods=10, speed=22, sigma=3, penalty=800, k=4, seed=1006),
}
