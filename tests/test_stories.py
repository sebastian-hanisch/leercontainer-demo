"""Abnahmekriterien der Presets (lcr_stories.criteria) an KÜNSTLICHEN Werten geprüft: jedes einzelne
Kriterium muss knapp über seiner Schwelle erfüllt sein und knapp darunter kippen - unabhängig von den
echten Messdaten. Ergänzt `test_preset_stories.py` (das an echten Daten prüft, ob die Geschichten
tragen) um die in der Preset-Disziplin des Portfolios geforderte Schwellen-Prüfung."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import lcr_stories as ST  # noqa: E402

N_PERIODS = 10


class _Fake:
    pass


def fake(exact=1000.0, **markups):
    """Ein InstanceResult-Double: `costs[9]` = exact (volle Vorschau), jedes übergebene kN=markup_pct
    (z. B. k0=140) setzt `costs[N]` entsprechend, alle übrigen k bleiben exakt am Optimum (Markup 0 %)."""
    r = _Fake()
    costs = [exact] * N_PERIODS
    for key, pct in markups.items():
        k = int(key[1:])          # "k0" -> 0, "k4" -> 4, ...
        costs[k] = exact * (1.0 + pct / 100.0)
    r.costs = costs
    r.exact = exact
    return r


def _ok(name, results, index):
    return ST.criteria(name, results)[index][0]


# ---------------------------------------------------------------------------------------------------
# Standard: k=0 >= 140 %, k=4 <= 7 %, volle Vorschau exakt (<= 0,01 %)
# ---------------------------------------------------------------------------------------------------
def test_standard_k0_threshold_tips_at_140_percent():
    assert _ok("Standard", [fake(k0=140.5, k4=0)], 0) is True
    assert _ok("Standard", [fake(k0=139.5, k4=0)], 0) is False


def test_standard_k4_threshold_tips_at_7_percent():
    assert _ok("Standard", [fake(k0=200, k4=6.5)], 1) is True
    assert _ok("Standard", [fake(k0=200, k4=7.5)], 1) is False


def test_standard_full_lookahead_threshold_tips_at_0_01_percent():
    r_ok = fake(k0=200, k4=0)
    r_ok.costs[9] = r_ok.exact * 1.00005          # 0,005 % Abstand
    assert _ok("Standard", [r_ok], 2) is True
    r_bad = fake(k0=200, k4=0)
    r_bad.costs[9] = r_bad.exact * 1.001          # 0,1 % Abstand
    assert _ok("Standard", [r_bad], 2) is False


# ---------------------------------------------------------------------------------------------------
# Kurze Route: k=3 <= 10 %, k=0 >= 170 %
# ---------------------------------------------------------------------------------------------------
def test_kurze_route_k3_threshold_tips_at_10_percent():
    assert _ok("Kurze Route", [fake(k3=9.5, k0=200)], 0) is True
    assert _ok("Kurze Route", [fake(k3=10.5, k0=200)], 0) is False


def test_kurze_route_k0_threshold_tips_at_170_percent():
    assert _ok("Kurze Route", [fake(k3=0, k0=170.5)], 1) is True
    assert _ok("Kurze Route", [fake(k3=0, k0=169.5)], 1) is False


# ---------------------------------------------------------------------------------------------------
# Lange Route: k=3 >= 20 %, k=6 < 3 %
# ---------------------------------------------------------------------------------------------------
def test_lange_route_k3_threshold_tips_at_20_percent():
    assert _ok("Lange Route", [fake(k3=20.5, k6=0)], 0) is True
    assert _ok("Lange Route", [fake(k3=19.5, k6=0)], 0) is False


def test_lange_route_k6_threshold_tips_at_3_percent():
    assert _ok("Lange Route", [fake(k3=100, k6=2.5)], 1) is True
    assert _ok("Lange Route", [fake(k3=100, k6=3.5)], 1) is False


# ---------------------------------------------------------------------------------------------------
# Unruhiges Aufkommen: k=0 >= 170 %, k=4 <= 10 %
# ---------------------------------------------------------------------------------------------------
def test_unruhig_k0_threshold_tips_at_170_percent():
    assert _ok("Unruhiges Aufkommen", [fake(k0=170.5, k4=0)], 0) is True
    assert _ok("Unruhiges Aufkommen", [fake(k0=169.5, k4=0)], 0) is False


def test_unruhig_k4_threshold_tips_at_10_percent():
    assert _ok("Unruhiges Aufkommen", [fake(k0=200, k4=9.5)], 1) is True
    assert _ok("Unruhiges Aufkommen", [fake(k0=200, k4=10.5)], 1) is False


# ---------------------------------------------------------------------------------------------------
# Teures Notleasing: k=0 >= 200 %, k=4 <= 12 %
# ---------------------------------------------------------------------------------------------------
def test_teuer_k0_threshold_tips_at_200_percent():
    assert _ok("Teures Notleasing", [fake(k0=200.5, k4=0)], 0) is True
    assert _ok("Teures Notleasing", [fake(k0=199.5, k4=0)], 0) is False


def test_teuer_k4_threshold_tips_at_12_percent():
    assert _ok("Teures Notleasing", [fake(k0=300, k4=11.5)], 1) is True
    assert _ok("Teures Notleasing", [fake(k0=300, k4=12.5)], 1) is False


def test_unknown_preset_name_raises():
    with pytest.raises(KeyError):
        ST.criteria("Nicht existent", [fake()])


def test_key_values_returns_only_this_presets_entries():
    values = ST.key_values("Standard", [fake(k0=150, k4=5)])
    assert set(values) == {0, 4}
    assert values[0] == pytest.approx(150.0) and values[4] == pytest.approx(5.0)
