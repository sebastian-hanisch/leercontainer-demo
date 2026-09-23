"""Preset-Abstimmung: trägt die Geschichte jedes Presets im MITTEL über viele Instanzen, und an dem
einen Seed, den das Preset zeigt?

Aufruf (im Projektordner): ./venv/Scripts/python.exe tools/tune_presets.py <modus>
  population   Grundgesamtheit (Seeds 0..POPULATION-1): Mittelwert-Kriterien aller Presets
  seeds        je Seed ab POPULATION: welche Presets tragen an diesem Seed, wie nah am Median

Grundsatz (aus den Hafen-Demos): den Seed nicht nach dem schönsten Einzelfall wählen, sondern nahe
am Median der Population; der Preset-Seed liegt AUSSERHALB der Grundgesamtheit (Seeds ab POPULATION).
Alles ist deterministisch (kein Löser mit Zeitgrenze): die Ergebnisse hängen nicht vom Rechner ab."""
import math
import statistics
import sys

sys.path.insert(0, ".")
import lcr_constants as C
import lcr_evaluation as E
import lcr_scenario as SC
import lcr_stories as ST

NAMES = list(C.PRESETS)
POPULATION = C.POPULATION_INSTANCES
SEED_SEARCH = range(POPULATION, POPULATION + 800)


def params(name):
    p = C.PRESETS[name]
    return E.Params(p["n_ports"], p["n_periods"], p["speed"], p["sigma"], p["penalty"], p["k"])


def cmd_population():
    for name in NAMES:
        res = E.sample(params(name), POPULATION)
        print(f"\n### {name}")
        for ok, text in ST.criteria(name, res):
            print(("  OK   " if ok else "  FAIL ") + text)
        print("  Kennzahlen:", {k: round(v, 2) for k, v in ST.key_values(name, res).items()})


def _lead_band(p, sample_size=200):
    """(10., 90. Perzentil) der mittleren Vorlaufzeit über Instanzen mit diesen Einstellungen - der
    gezeigte Seed soll auch bei der Vorlaufzeit typisch sein, nicht nur bei den Kosten-Kriterien
    (sonst zeigt z. B. "Lange Route" zufällig eine untypisch kurze Vorlaufzeit)."""
    leads = sorted(SC.mean_lead(E.make_instance(p, seed)) for seed in range(sample_size))
    n = len(leads)
    return leads[n // 10], leads[9 * n // 10 - 1]


def cmd_seeds():
    for name in NAMES:
        p = params(name)
        pop = E.sample(p, POPULATION)
        ks = [k for n, k in ST.TYPICAL if n == name]
        med = {k: statistics.median(E.markup_pct(r.costs[min(k, len(r.costs) - 1)], r.exact) for r in pop) for k in ks}
        lead_lo, lead_hi = _lead_band(p)
        best = None
        holds_count = 0
        for seed in SEED_SEARCH:
            r = E.instance_result(p, seed)
            if not all(ok for ok, _ in ST.criteria(name, [r])):
                continue
            holds_count += 1
            if not (lead_lo <= r.mean_lead <= lead_hi):
                continue
            score = sum(abs(math.log(abs(E.markup_pct(r.costs[min(k, len(r.costs) - 1)], r.exact)) + 1) - math.log(abs(med[k]) + 1)) for k in ks)
            if best is None or score < best[0]:
                best = (score, seed, r)
        print(f"\n### {name}: trägt an {holds_count} von {len(SEED_SEARCH)} Seeds (Suchbereich {SEED_SEARCH.start}..{SEED_SEARCH.stop - 1}); Vorlaufzeit-Band {lead_lo:.1f}-{lead_hi:.1f}")
        if best:
            score, seed, r = best
            print(f"  bester Seed (typische Vorlaufzeit {r.mean_lead:.2f}, nächster am Median): {seed}  Abstand {score:.3f}")
            for k in ks:
                print(f"    k={k}: {E.markup_pct(r.costs[min(k, len(r.costs) - 1)], r.exact):+.1f} %  (Median Population: {med[k]:+.1f} %)")
        else:
            print("  KEIN Seed im Suchbereich mit typischer Vorlaufzeit erfüllt alle Kriterien - Kriterien, Suchbereich oder Vorlaufzeit-Band prüfen.")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "population"
    {"population": cmd_population, "seeds": cmd_seeds}.get(mode, lambda: sys.exit(__doc__))()
