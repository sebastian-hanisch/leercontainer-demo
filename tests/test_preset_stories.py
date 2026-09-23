"""Abnahme der Presets an ECHTEN Daten: jede Geschichte trägt im Mittel über POPULATION_INSTANCES
Instanzen (Seeds 0..N-1) UND an der EINEN Instanz, die das Preset zeigt; der gezeigte Seed ist typisch
(mittlere Vorlaufzeit zwischen dem 10. und 90. Perzentil), nicht der schönste Einzelfall."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import lcr_constants as C  # noqa: E402
import lcr_evaluation as E  # noqa: E402
import lcr_scenario as SC  # noqa: E402
import lcr_stories as ST  # noqa: E402

NAMES = list(C.PRESETS)
_POP = {}


def params(name):
    p = C.PRESETS[name]
    return E.Params(p["n_ports"], p["n_periods"], p["speed"], p["sigma"], p["penalty"], p["k"])


def population(name):
    if name not in _POP:
        _POP[name] = E.sample(params(name), C.POPULATION_INSTANCES)
    return _POP[name]


@pytest.mark.parametrize("name", NAMES)
def test_story_holds_on_average_over_the_population(name):
    for ok, text in ST.criteria(name, population(name)):
        assert ok, f"{name}: {text}"


@pytest.mark.parametrize("name", NAMES)
def test_story_holds_at_the_instance_the_preset_shows(name):
    seed = C.PRESETS[name]["seed"]
    shown = E.instance_result(params(name), seed)
    for ok, text in ST.criteria(name, [shown]):
        assert ok, f"{name}: {text}"


def test_the_preset_seed_lies_outside_the_population():
    assert all(preset["seed"] >= C.POPULATION_INSTANCES for preset in C.PRESETS.values())


@pytest.mark.parametrize("name", NAMES)
def test_the_shown_instance_is_typical_for_every_key_markup(name):
    """Der Aufschlag der gezeigten Instanz liegt zwischen dem 10. und 90. Perzentil der Population -
    das Preset zeigt den typischen Fall, nicht den günstigsten."""
    seed = C.PRESETS[name]["seed"]
    shown = E.instance_result(params(name), seed)
    pop = population(name)
    for n, k in ST.TYPICAL:
        if n != name:
            continue
        values = sorted(E.markup_pct(r.costs[min(k, len(r.costs) - 1)], r.exact) for r in pop)
        lo, hi = values[int(0.1 * len(values))], values[int(0.9 * len(values)) - 1]
        got = E.markup_pct(shown.costs[min(k, len(shown.costs) - 1)], shown.exact)
        assert lo <= got <= hi, (name, k, got, (lo, hi))


@pytest.mark.parametrize("name", NAMES)
def test_the_shown_instance_has_a_typical_mean_lead(name):
    """Auch die mittlere Vorlaufzeit der gezeigten Instanz soll typisch sein (siehe
    tools/tune_presets.py: sonst könnte z. B. "Lange Route" zufällig eine kurze Vorlaufzeit zeigen,
    obwohl die Kostenkriterien noch erfüllt sind)."""
    p = params(name)
    leads = sorted(SC.mean_lead(E.make_instance(p, seed)) for seed in range(200))
    n = len(leads)
    lo, hi = leads[n // 10], leads[9 * n // 10 - 1]
    shown_lead = SC.mean_lead(E.make_instance(p, C.PRESETS[name]["seed"]))
    assert lo <= shown_lead <= hi, (name, shown_lead, (lo, hi))


def test_criteria_are_not_trivially_true_for_the_wrong_preset():
    """Die Geschichten unterscheiden sich: an den Daten eines anderen Presets kippt mindestens ein
    Kriterium (sonst wären die Presets austauschbar)."""
    assert not all(ok for ok, _ in ST.criteria("Kurze Route", population("Lange Route")))
    assert not all(ok for ok, _ in ST.criteria("Lange Route", population("Kurze Route")))
    assert not all(ok for ok, _ in ST.criteria("Standard", population("Teures Notleasing")))


def test_the_population_reproduces_the_pre_measurement_within_margin():
    """Basis-Preset: gemessen in messreihe_ecr/sweep_data.json (Seeds 0-59, P=5 T=10 speed=22 sigma=3
    penalty=200): k=0 Aufschlag +153,4 %, k=4 Aufschlag +5,2 % (siehe ERGEBNIS.md). Unsere Population
    nutzt eine andere Stichprobengröße (40 statt 60 Instanzen) - Reproduktion nur auf grobe Marge."""
    pop = population("Standard")
    assert E.mean_markup(pop, 0) == pytest.approx(153.4, abs=40.0)
    assert E.mean_markup(pop, 4) == pytest.approx(5.2, abs=5.0)
