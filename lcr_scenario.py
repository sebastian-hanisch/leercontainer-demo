"""Szenario: Häfen, Distanzen, Vorlaufzeiten, Netto-Einspeisung je Periode.

Erzeugung bitgleich zu messreihe_ecr/ecr.py (make_ports, dist_matrix, lead_matrix, make_instance) -
nur die Reglernamen sind an die App angepasst (n_ports statt p, n_periods statt T, sigma statt
sigma_noise, speed bleibt speed). sigma_bias ist ein fester Modellparameter (siehe lcr_constants),
kein Regler: er bestimmt nur, wie ungleich die Häfen im Mittel sind, nicht die Instanz-zu-Instanz-
Streuung, die der Volatilitäts-Regler steuert."""
import math
import random
import statistics

import lcr_constants as C


def make_ports(n_ports, seed):
    rng = random.Random(seed)
    return [(rng.uniform(0, 100), rng.uniform(0, 100)) for _ in range(n_ports)]


def dist_matrix(coords):
    n = len(coords)
    d = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                d[i][j] = math.hypot(coords[i][0] - coords[j][0], coords[i][1] - coords[j][1])
    return d


def lead_matrix(dist, speed):
    n = len(dist)
    return [[0 if i == j else max(1, round(dist[i][j] / speed)) for j in range(n)] for i in range(n)]


def make_instance(n_ports, n_periods, seed, sigma=C.SIGMA_DEFAULT, speed=C.SPEED_DEFAULT, sigma_bias=C.SIGMA_BIAS):
    """b[hafen][t]: Nettoaufkommen (positiv = freiwerdende Leercontainer, negativ = Bedarf). Jeder
    Hafen bekommt eine feste Import-/Export-Neigung (bias), je Periode + Rauschen (Stärke = sigma);
    am Ende auf Summe 0 zentriert (kein globaler Ueberschuss/Mangel über den Horizont - siehe die
    Annahmen in Abschnitt 2 des Detailplans)."""
    if n_ports < 3:
        raise ValueError("Mindestens 3 Häfen nötig.")
    if n_periods < 2:
        raise ValueError("Mindestens 2 Perioden nötig.")
    rng = random.Random(seed)
    coords = make_ports(n_ports, seed)
    dist = dist_matrix(coords)
    lead = lead_matrix(dist, speed)
    bias = [rng.uniform(-sigma_bias, sigma_bias) for _ in range(n_ports)]
    b = [[bias[i] + rng.gauss(0, sigma) for _ in range(n_periods)] for i in range(n_ports)]
    total = sum(sum(row) for row in b)
    correction = total / (n_ports * n_periods)
    b = [[round(v - correction) for v in row] for row in b]
    return dict(p=n_ports, T=n_periods, coords=coords, dist=dist, lead=lead, b=b)


def mean_lead(inst):
    """Mittlere Vorlaufzeit über alle geordneten Hafenpaare (p != q)."""
    p, lead = inst["p"], inst["lead"]
    leads = [lead[i][j] for i in range(p) for j in range(p) if i != j]
    return statistics.fmean(leads)


def net_by_port(inst):
    """Netto-Ueberschuss (positiv) bzw. -Bedarf (negativ) je Hafen, summiert über den GANZEN
    Horizont - für die Uebersichtskarte (Ueberschusshafen/Mangelhafen), nicht für eine Periode."""
    return [sum(row) for row in inst["b"]]
