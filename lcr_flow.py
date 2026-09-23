"""Min-Cost-Flow-Kern: sukzessive kürzeste (erweiternde) Wege via Dijkstra + Potentiale (Johnson-
Technik). Unverändert übernommen aus messreihe_ecr/ecr.py (Welle 1 Seefracht-Linie) - dort bereits
gegen Handinstanzen und Konsistenzchecks verifiziert (check.py, 120+25 Instanzen, 0 Abweichungen).

Das Ausgangsnetz hat nur nichtnegative Kosten (0, Haltekosten, Transportkosten, Notleasing-Strafe),
daher starten die Potentiale bei 0; danach bleiben die reduzierten Kosten stets nichtnegativ, Dijkstra
ist also nach der ersten Runde weiter korrekt anwendbar. Bewusst NICHT die SPFA/Bellman-Ford-Variante
(Warteschlange) genommen: die entartet auf diesem Kantentyp (viele Rückkanten werden nach
Augmentierungen negativ) schon bei kleinen Instanzen zu unbrauchbarer Laufzeit (real erlebt, siehe
messreihe_ecr/ERGEBNIS.md) - dieser Punkt ist der wichtigste Fallstrick dieser Demo."""
import heapq
import math

INF = 10 ** 9


class MinCostFlow:
    """Sukzessive kürzeste Wege via Dijkstra + Potentiale."""

    def __init__(self, n):
        self.n = n
        self.graph = [[] for _ in range(n)]  # graph[u] = Liste von [to, cap_rest, cost, rev_index]
        self.h = [0] * n  # Potentiale

    def add_edge(self, fr, to, cap, cost):
        self.graph[fr].append([to, cap, cost, len(self.graph[to])])
        self.graph[to].append([fr, 0, -cost, len(self.graph[fr]) - 1])
        return fr, len(self.graph[fr]) - 1  # Handle zum späteren Auslesen des Flusses

    def flow_on(self, handle, orig_cap):
        fr, idx = handle
        return orig_cap - self.graph[fr][idx][1]

    def _dijkstra(self, s):
        n = self.n
        dist = [math.inf] * n
        prev_node = [-1] * n
        prev_edge = [-1] * n
        dist[s] = 0
        pq = [(0, s)]
        visited = [False] * n
        while pq:
            du, u = heapq.heappop(pq)
            if visited[u]:
                continue
            visited[u] = True
            for i, e in enumerate(self.graph[u]):
                to, cap, cost, _ = e
                if cap <= 0 or visited[to]:
                    continue
                reduced = cost + self.h[u] - self.h[to]
                nd = du + reduced
                if nd < dist[to]:
                    dist[to] = nd
                    prev_node[to] = u
                    prev_edge[to] = i
                    heapq.heappush(pq, (nd, to))
        return dist, prev_node, prev_edge

    def solve(self, s, t, maxf):
        total_cost = 0
        flow = 0
        while flow < maxf:
            dist, prev_node, prev_edge = self._dijkstra(s)
            if dist[t] == math.inf:
                raise RuntimeError("kein Weg mehr gefunden - Fehlmengen-Kante hätte das verhindern sollen")
            for v in range(self.n):
                if dist[v] < math.inf:
                    self.h[v] += dist[v]
            real_dist_t = self.h[t] - self.h[s]  # = tatsächliche (unreduzierte) Kosten des Weges
            d = maxf - flow
            v = t
            while v != s:
                d = min(d, self.graph[prev_node[v]][prev_edge[v]][1])
                v = prev_node[v]
            v = t
            while v != s:
                e = self.graph[prev_node[v]][prev_edge[v]]
                e[1] -= d
                self.graph[v][e[3]][1] += d
                v = prev_node[v]
            flow += d
            total_cost += d * real_dist_t
        return total_cost, flow


def solve_window(inst, window_start, window_end, held_stock, pending_in, hold_cost, rate, penalty):
    """Ein Min-Cost-Flow über Knoten (Hafen, t) für t in [window_start, window_end].
    held_stock: Bestand je Hafen JETZT (wird bei window_start mit eingespeist).
    pending_in: dict (hafen, t) -> Menge, bereits unterwegs, landet automatisch bei t.
    Gibt zurück: (gesamtkosten_fenster, transport_ab_window_start dict[(p,q)]->menge,
                   haltemenge_ab_window_start dict[p]->menge, fehlmenge_bei_window_start dict[p]->menge)"""
    P, dist, lead = inst["p"], inst["dist"], inst["lead"]
    times = list(range(window_start, window_end + 1))
    idx = {}
    for t in times:
        for p in range(P):
            idx[(p, t)] = len(idx)
    n = len(idx) + 2
    SRC, SNK = n - 2, n - 1
    mcf = MinCostFlow(n)

    hold_handles = {}
    transport_handles = {}
    shortfall_handles = {}
    demand_total = 0

    # Netto-Einspeisung je Knoten
    inj = {(p, t): inst["b"][p][t] for p in range(P) for t in times}
    for p in range(P):
        inj[(p, window_start)] += held_stock[p]
    for (p, t), qty in pending_in.items():
        if (p, t) in inj:
            inj[(p, t)] += qty

    for (p, t), value in inj.items():
        node = idx[(p, t)]
        if value > 0:
            mcf.add_edge(SRC, node, value, 0)
        elif value < 0:
            mcf.add_edge(node, SNK, -value, 0)
            h = mcf.add_edge(SRC, node, -value, penalty)
            shortfall_handles[(p, t)] = (h, -value)
            demand_total += -value

    for t in times:
        if t + 1 <= window_end:
            for p in range(P):
                h = mcf.add_edge(idx[(p, t)], idx[(p, t + 1)], INF, hold_cost)
                if t == window_start:
                    hold_handles[p] = (h, INF)
        for p in range(P):
            for q in range(P):
                if p == q:
                    continue
                arr = t + lead[p][q]
                if arr <= window_end:
                    h = mcf.add_edge(idx[(p, t)], idx[(q, arr)], INF, rate * dist[p][q])
                    if t == window_start:
                        transport_handles[(p, q)] = (h, INF)

    cost, flow = mcf.solve(SRC, SNK, demand_total)
    assert flow == demand_total

    transport_out = {pq: mcf.flow_on(h, cap) for pq, (h, cap) in transport_handles.items()}
    hold_out = {p: mcf.flow_on(h, cap) for p, (h, cap) in hold_handles.items()}
    shortfall_now = {p: mcf.flow_on(h, cap) for (p, t), (h, cap) in shortfall_handles.items() if t == window_start}
    return cost, transport_out, hold_out, shortfall_now
