"""Fehler-Einbau-Test: baut einzelne Fehler in die Module ein und prueft, ob die Tests (ohne AppTests,
die sind zu langsam fuer 20+ Mutanten) sie finden.

Aufruf (im Projektordner): ./venv/Scripts/python.exe tools/mutation_check.py [Teilstring des Dateinamens]
Jeder Mutant ersetzt genau eine Stelle; Ueberlebende sind entweder gleichwertig (kein sichtbarer
Unterschied) oder eine Luecke der Tests. Die Kopie liegt in einem temporaeren Ordner;
PYTHONDONTWRITEBYTECODE=1, damit veralteter Bytecode keine Ueberlebenden vortaeuscht; Quelltexte als
LF (Windows-Python schreibt sonst CRLF und die Zeichenketten unten finden nichts)."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
TIMEOUT = 240

MUTANTS = [
    # lcr_flow.py
    ("lcr_flow.py", "if cap <= 0 or visited[to]:", "if cap < 0 or visited[to]:"),
    ("lcr_flow.py", "reduced = cost + self.h[u] - self.h[to]", "reduced = cost - self.h[u] + self.h[to]"),
    ("lcr_flow.py", "if nd < dist[to]:", "if nd <= dist[to]:"),
    ("lcr_flow.py", "d = min(d, self.graph[prev_node[v]][prev_edge[v]][1])", "d = max(d, self.graph[prev_node[v]][prev_edge[v]][1])"),
    ("lcr_flow.py", "e[1] -= d", "e[1] += d"),
    ("lcr_flow.py", "if value > 0:", "if value >= 0:"),
    ("lcr_flow.py", "elif value < 0:", "elif value <= 0:"),
    ("lcr_flow.py", "if t + 1 <= window_end:", "if t + 1 < window_end:"),
    ("lcr_flow.py", "arr = t + lead[p][q]\n                if arr <= window_end:", "arr = t + lead[p][q]\n                if arr < window_end:"),
    ("lcr_flow.py", "if p == q:\n                    continue", "if p >= q:\n                    continue"),
    # lcr_scenario.py
    ("lcr_scenario.py", "return [[0 if i == j else max(1, round(dist[i][j] / speed)) for j in range(n)] for i in range(n)]", "return [[0 if i == j else max(1, round(dist[i][j] / speed) - 1) for j in range(n)] for i in range(n)]"),
    ("lcr_scenario.py", "if n_ports < 3:", "if n_ports < 2:"),
    ("lcr_scenario.py", "if n_periods < 2:", "if n_periods < 1:"),
    ("lcr_scenario.py", "b = [[round(v - correction) for v in row] for row in b]", "b = [[round(v) for v in row] for row in b]"),
    # lcr_rolling.py
    ("lcr_rolling.py", "window_end = min(t + k, T - 1)", "window_end = min(t + k, T)"),
    ("lcr_rolling.py", "if arr == t + 1:", "if arr == t:"),
    ("lcr_rolling.py", "elif arr > t + 1:", "elif arr >= t + 1:"),
    ("lcr_rolling.py", "if arr < T:\n                pending[(q, arr)] = pending.get((q, arr), 0.0) + qty", "if arr <= T:\n                pending[(q, arr)] = pending.get((q, arr), 0.0) + qty"),
    ("lcr_rolling.py", "pending_now = {key: v for key, v in pending.items() if key[1] <= window_end}", "pending_now = {key: v for key, v in pending.items() if key[1] < window_end}"),
    # lcr_evaluation.py
    ("lcr_evaluation.py", "avg_cost = statistics.fmean(r.costs[min(k, len(r.costs) - 1)] for r in results)", "avg_cost = statistics.fmean(r.costs[k] for r in results)"),
    ("lcr_evaluation.py", "return markup_pct(avg_cost, avg_exact)", "return markup_pct(avg_exact, avg_cost)"),
    ("lcr_evaluation.py", "return 100.0 * (cost - exact) / exact if exact else 0.0", "return 100.0 * (cost - exact) / cost if exact else 0.0"),
    ("lcr_evaluation.py", "kind = \"unclear\" if diff == 0 else (\"better\" if diff < 0 else \"worse\")", "kind = \"unclear\" if diff == 0 else (\"better\" if diff > 0 else \"worse\")"),
    ("lcr_evaluation.py", "kind = \"unclear\" if abs(diff) <= C.VERDICT_Z * se else", "kind = \"unclear\" if abs(diff) < C.VERDICT_Z * se else"),
    ("lcr_evaluation.py", "return min(inst[\"T\"] - 1, max(0, round(C.K_STAR_FACTOR * lead)))", "return min(inst[\"T\"] - 1, max(0, round(lead)))"),
    ("lcr_evaluation.py", "if k < lead:\n        kind = \"too_short\"", "if k <= lead:\n        kind = \"too_short\""),
    ("lcr_evaluation.py", "elif gap < C.NEAR_OPTIMAL_PCT:", "elif gap <= C.NEAR_OPTIMAL_PCT:"),
    ("lcr_evaluation.py", "return statistics.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else 0.0", "return statistics.stdev(d) / len(d) if len(d) > 1 else 0.0"),
    # lcr_presets.py
    ("lcr_presets.py", "return max(0, min(int(k), k_max(int(n_periods))))", "return min(int(k), k_max(int(n_periods)))"),
    ("lcr_presets.py", "return max(0, n_periods - 1)", "return max(0, n_periods)"),
    ("lcr_presets.py", "value = spec.lo + round((value - spec.lo) / spec.step) * spec.step", "value = spec.lo + int((value - spec.lo) / spec.step) * spec.step"),
    ("lcr_presets.py", "return min(n_periods - 1, max(1, round(C.K_STAR_FACTOR * approx_lead)))", "return min(n_periods - 1, max(1, round(approx_lead)))"),
    # lcr_stories.py
    ("lcr_stories.py", "(k0 >= 140,", "(k0 > 140,"),
    ("lcr_stories.py", "(k4 <= 7,", "(k4 < 7,"),
    ("lcr_stories.py", "(k3 <= 10,", "(k3 < 10,"),
    ("lcr_stories.py", "(k0 >= 170, f\"k=0 Aufschlag >= 170 %: {k0:+.1f} %\")]\n    if name == \"Lange Route\":", "(k0 > 170, f\"k=0 Aufschlag >= 170 %: {k0:+.1f} %\")]\n    if name == \"Lange Route\":"),
    ("lcr_stories.py", "(k3 >= 20,", "(k3 > 20,"),
    ("lcr_stories.py", "(k6 < 3,", "(k6 <= 3,"),
    ("lcr_stories.py", "(k0 >= 200,", "(k0 > 200,"),
    ("lcr_stories.py", "(k4 <= 12,", "(k4 < 12,"),
]


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="lcr_mut_"))
    for f in ROOT.glob("*.py"):
        shutil.copy(f, tmp / f.name)
    shutil.copytree(ROOT / "tests", tmp / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    for f in tmp.glob("*.py"):
        f.write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    survivors, errors, killed = [], [], 0
    for n, (name, old, new) in enumerate(MUTANTS, 1):
        if only and only not in name:
            continue
        path = tmp / name
        original = path.read_bytes().decode("utf-8")
        if original.count(old) != 1:
            errors.append((n, name, old[:60], original.count(old)))
            continue
        path.write_bytes(original.replace(old, new).encode("utf-8"))
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "tests", "--ignore=tests/test_app.py"], cwd=tmp, env=env, capture_output=True, text=True, timeout=TIMEOUT)
            survived = r.returncode == 0
        except subprocess.TimeoutExpired:
            survived = False                    # Endlosschleife gilt als gefunden
            print(f"[{n:3d}] Zeitueberschreitung (als gefunden gezaehlt)  {name}", flush=True)
        path.write_bytes(original.encode("utf-8"))
        if survived:
            survivors.append((n, name, old[:70], new[:70]))
            print(f"[{n:3d}] UEBERLEBT  {name}: {old[:60]!r} -> {new[:60]!r}", flush=True)
        else:
            killed += 1
            print(f"[{n:3d}] gefunden  {name}", flush=True)
    print(f"\n{killed} gefunden, {len(survivors)} ueberlebt, {len(errors)} Fehler in der Mutantenliste")
    for e in errors:
        print("  FEHLER (Stelle nicht eindeutig gefunden):", e)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
