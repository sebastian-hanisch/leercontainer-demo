"""Abnahmekriterien der Presets (Detailplan plan_ecr.html, Abschnitt 7): welche Geschichte erzählt
jedes Beispielszenario, und woran erkennt man, dass sie trägt?

Einzige Quelle für `tools/tune_presets.py` (Abstimmung) und `tests/test_preset_stories.py` (Abnahme).
Jedes Kriterium ist eine Aussage über den mittleren Aufschlag (Markup) eines Vorschau-Fensters k gegen
das Optimum, entweder über eine POPULATION von Instanzen (`results` = viele `InstanceResult`) oder über
den EINEN gezeigten Seed (`results` = eine Liste mit einem `InstanceResult`) - dieselbe Funktion für
beide, wie in der Preset-Disziplin des Portfolios gefordert ("Kriterien an der Grundgesamtheit UND am
gezeigten Seed")."""
import lcr_evaluation as E

# Kennzahlen, an denen "typisch" gemessen wird: (Preset, k) -> der Aufschlag bei diesem k soll beim
# gezeigten Seed zwischen dem 10. und 90. Perzentil der Population liegen.
TYPICAL = (
    ("Standard", 0), ("Standard", 4),
    ("Kurze Route", 0), ("Kurze Route", 3),
    ("Lange Route", 3), ("Lange Route", 6),
    ("Unruhiges Aufkommen", 0), ("Unruhiges Aufkommen", 4),
    ("Teures Notleasing", 0), ("Teures Notleasing", 4),
)


def criteria(name, results):
    """Kriterien für ein Preset über `results` (Liste von InstanceResult, ein oder viele Elemente).
    Rückgabe: Liste (erfüllt, Text)."""
    if name == "Standard":
        k0, k4 = E.mean_markup(results, 0), E.mean_markup(results, 4)
        kmax = E.mean_markup(results, len(results[0].costs) - 1)
        return [(k0 >= 140, f"k=0 Aufschlag >= 140 %: {k0:+.1f} %"),
                (k4 <= 7, f"k=4 Aufschlag <= 7 %: {k4:+.1f} %"),
                (abs(kmax) <= 0.01, f"volle Vorschau exakt gleich dem Optimum (<= 0,01 %): {kmax:+.4f} %")]
    if name == "Kurze Route":
        k3, k0 = E.mean_markup(results, 3), E.mean_markup(results, 0)
        return [(k3 <= 10, f"k=3 Aufschlag <= 10 %: {k3:+.1f} %"),
                (k0 >= 170, f"k=0 Aufschlag >= 170 %: {k0:+.1f} %")]
    if name == "Lange Route":
        k3, k6 = E.mean_markup(results, 3), E.mean_markup(results, 6)
        return [(k3 >= 20, f"k=3 Aufschlag >= 20 %: {k3:+.1f} %"),
                (k6 < 3, f"k=6 Aufschlag < 3 %: {k6:+.1f} %")]
    if name == "Unruhiges Aufkommen":
        k0, k4 = E.mean_markup(results, 0), E.mean_markup(results, 4)
        return [(k0 >= 170, f"k=0 Aufschlag >= 170 %: {k0:+.1f} %"),
                (k4 <= 10, f"k=4 Aufschlag <= 10 %: {k4:+.1f} %")]
    if name == "Teures Notleasing":
        k0, k4 = E.mean_markup(results, 0), E.mean_markup(results, 4)
        return [(k0 >= 200, f"k=0 Aufschlag >= 200 %: {k0:+.1f} %"),
                (k4 <= 12, f"k=4 Aufschlag <= 12 %: {k4:+.1f} %")]
    raise KeyError(name)


def key_values(name, results):
    """Die Kennzahlen dieses Presets aus TYPICAL als {k: mittlerer Aufschlag}."""
    return {k: E.mean_markup(results, k) for n, k in TYPICAL if n == name}
