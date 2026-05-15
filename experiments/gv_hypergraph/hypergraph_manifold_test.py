import csv
from pathlib import Path
import numpy as np

from gvai.universal_scalar import GVEvidence, gv_scalar

OUT_CSV = Path("reports/gv_hypergraph/hypergraph_manifold_cases.csv")
OUT_MD = Path("reports/gv_hypergraph/HYPERGRAPH_MANIFOLD_RESULT.md")

SEED = 42
STEPS = 140
NODES = 18


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def corr(a, b):
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)

    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0

    return float(np.corrcoef(a, b)[0, 1])


def pca_first_component(matrix):
    x = np.array(matrix, dtype=float)
    x = x - x.mean(axis=0)

    u, s, vt = np.linalg.svd(x, full_matrices=False)

    scores = x @ vt[0]
    explained = (s[0] ** 2) / np.sum(s ** 2)

    return scores, explained, vt[0], s


def graph_features(adj):
    n = adj.shape[0]
    degrees = adj.sum(axis=1)

    edge_count = float(adj.sum() / 2.0)
    possible = n * (n - 1) / 2.0
    density = edge_count / possible if possible else 0.0

    visited = set()
    components = 0

    for start in range(n):
        if start in visited:
            continue

        components += 1
        stack = [start]
        visited.add(start)

        while stack:
            node = stack.pop()
            neighbors = np.where(adj[node] > 0)[0]
            for nb in neighbors:
                if int(nb) not in visited:
                    visited.add(int(nb))
                    stack.append(int(nb))

    # cycle rank / first Betti number approximation for undirected graph:
    # beta1 = E - V + C
    beta0 = components
    beta1 = max(0.0, edge_count - n + components)

    fragmentation = clamp01((components - 1) / max(1, n - 1))
    avg_degree = float(np.mean(degrees))

    return {
        "density": density,
        "beta0": float(beta0),
        "beta1": float(beta1),
        "fragmentation": fragmentation,
        "avg_degree": avg_degree,
    }


def simulate():
    rng = np.random.default_rng(SEED)

    # Start moderately connected.
    adj = np.zeros((NODES, NODES), dtype=float)

    for i in range(NODES):
        for j in range(i + 1, NODES):
            if rng.random() < 0.22:
                adj[i, j] = 1
                adj[j, i] = 1

    rows = []

    local_adaptation = np.zeros(NODES)
    hidden_global_strain = 0.0
    resource = 1.0

    for t in range(STEPS):
        mild_stress = 0.0

        # Local antifragility: repeated mild stress improves local recovery.
        if 15 <= t <= 70 and t % 5 == 0:
            mild_stress = 0.12
            local_adaptation += 0.018

            # successful local adaptation forms more local loops
            for _ in range(3):
                i, j = rng.integers(0, NODES, size=2)
                if i != j:
                    adj[i, j] = 1
                    adj[j, i] = 1

        # Hidden slow variable: global strain accumulates after local success.
        if t > 45:
            hidden_global_strain += 0.006
            resource -= 0.004

        # Topology collapse: after strain threshold, long-range edges disappear.
        if t > 85 and hidden_global_strain > 0.25:
            hidden_global_strain += 0.012
            resource -= 0.010

            for _ in range(4):
                i, j = rng.integers(0, NODES, size=2)
                if i != j:
                    adj[i, j] = 0
                    adj[j, i] = 0

        resource = clamp01(resource)
        hidden_global_strain = clamp01(hidden_global_strain)

        gf = graph_features(adj)

        local_recovery = clamp01(0.72 + float(np.mean(local_adaptation)) - mild_stress * 0.3)
        local_persistence = clamp01(0.82 + float(np.mean(local_adaptation)) * 0.6 - mild_stress * 0.2)
        local_directional = clamp01(0.84 + float(np.mean(local_adaptation)) * 0.4 - mild_stress * 0.2)
        local_volatility = clamp01(0.15 + mild_stress + rng.normal(0, 0.015))

        local_gv = gv_scalar(GVEvidence(
            recovery_strength=local_recovery,
            persistence=local_persistence,
            directional_degradation=local_directional,
            volatility_penalty=local_volatility,
        ))

        global_recovery = clamp01(resource)
        global_persistence = clamp01(1.0 - hidden_global_strain)
        global_directional = clamp01(resource - hidden_global_strain * 0.30)
        global_volatility = clamp01(0.20 + hidden_global_strain + gf["fragmentation"])

        global_gv = gv_scalar(GVEvidence(
            recovery_strength=global_recovery,
            persistence=global_persistence,
            directional_degradation=global_directional,
            volatility_penalty=global_volatility,
        ))

        # scalar attempt: average local/global
        combined_gv = round((local_gv + global_gv) / 2.0, 6)

        rows.append({
            "time": t,
            "local_gv": round(local_gv, 6),
            "global_gv": round(global_gv, 6),
            "combined_gv": combined_gv,
            "local_recovery": round(local_recovery, 6),
            "local_persistence": round(local_persistence, 6),
            "local_directional": round(local_directional, 6),
            "local_volatility": round(local_volatility, 6),
            "resource": round(resource, 6),
            "hidden_global_strain": round(hidden_global_strain, 6),
            "density": round(gf["density"], 6),
            "beta0_components": round(gf["beta0"], 6),
            "beta1_cycles": round(gf["beta1"], 6),
            "fragmentation": round(gf["fragmentation"], 6),
            "avg_degree": round(gf["avg_degree"], 6),
            "local_global_gap": round(local_gv - global_gv, 6),
        })

    return rows


def analyze(rows):
    gv = [r["combined_gv"] for r in rows]

    base_matrix = []
    topology_matrix = []
    full_matrix = []

    for r in rows:
        base_vec = [
            r["local_recovery"],
            r["local_persistence"],
            r["local_directional"],
            1.0 - r["local_volatility"],
            r["resource"],
            1.0 - r["hidden_global_strain"],
        ]

        topo_vec = [
            r["density"],
            1.0 - r["fragmentation"],
            r["avg_degree"] / max(1.0, NODES - 1),
            1.0 / (1.0 + r["beta0_components"]),
            1.0 / (1.0 + r["beta1_cycles"]),
        ]

        base_matrix.append(base_vec)
        topology_matrix.append(topo_vec)
        full_matrix.append(base_vec + topo_vec)

    base_pc1, base_explained, _, base_s = pca_first_component(base_matrix)
    topo_pc1, topo_explained, _, topo_s = pca_first_component(topology_matrix)
    full_pc1, full_explained, _, full_s = pca_first_component(full_matrix)

    if corr(gv, base_pc1) < 0:
        base_pc1 = -base_pc1
    if corr(gv, topo_pc1) < 0:
        topo_pc1 = -topo_pc1
    if corr(gv, full_pc1) < 0:
        full_pc1 = -full_pc1

    base_alignment = corr(gv, base_pc1)
    topo_alignment = corr(gv, topo_pc1)
    full_alignment = corr(gv, full_pc1)

    max_gap = max(abs(r["local_global_gap"]) for r in rows)
    late = [r for r in rows if r["time"] >= 105]

    late_local = float(np.mean([r["local_gv"] for r in late]))
    late_global = float(np.mean([r["global_gv"] for r in late]))
    late_fragmentation = float(np.mean([r["fragmentation"] for r in late]))
    late_cycles = float(np.mean([r["beta1_cycles"] for r in late]))

    # hostile classification
    if full_explained >= 0.75 and full_alignment >= 0.85:
        result = "GV_SCALAR_SURVIVES_HYPERGRAPH_TEST"
    elif base_alignment >= 0.85 and topo_alignment < 0.70:
        result = "GV_BASE_AXIS_SURVIVES_TOPOLOGY_BREAKS"
    elif full_explained < 0.70:
        result = "RECOVERABILITY_REQUIRES_MULTI_AXIS_GEOMETRY"
    else:
        result = "GV_PARTIAL_OR_INCONCLUSIVE"

    return {
        "result": result,
        "base_pc1_explained": round(float(base_explained), 6),
        "topology_pc1_explained": round(float(topo_explained), 6),
        "full_pc1_explained": round(float(full_explained), 6),
        "gv_base_pc1_corr": round(float(base_alignment), 6),
        "gv_topology_pc1_corr": round(float(topo_alignment), 6),
        "gv_full_pc1_corr": round(float(full_alignment), 6),
        "max_local_global_gap": round(float(max_gap), 6),
        "late_local_gv": round(late_local, 6),
        "late_global_gv": round(late_global, 6),
        "late_fragmentation": round(late_fragmentation, 6),
        "late_beta1_cycles": round(late_cycles, 6),
    }


def main():
    rows = simulate()
    metrics = analyze(rows)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    OUT_MD.write_text(f'''# GV Hypergraph / Manifold Adversarial Result

## Purpose

Attack scalar GV with topology evolution and hidden delayed collapse.

## Result

`{metrics["result"]}`

## Metrics

| Metric | Value |
|---|---:|
| base PC1 explained variance | {metrics["base_pc1_explained"]} |
| topology PC1 explained variance | {metrics["topology_pc1_explained"]} |
| full PC1 explained variance | {metrics["full_pc1_explained"]} |
| GV correlation with base PC1 | {metrics["gv_base_pc1_corr"]} |
| GV correlation with topology PC1 | {metrics["gv_topology_pc1_corr"]} |
| GV correlation with full PC1 | {metrics["gv_full_pc1_corr"]} |
| max local-global gap | {metrics["max_local_global_gap"]} |
| late local GV | {metrics["late_local_gv"]} |
| late global GV | {metrics["late_global_gv"]} |
| late fragmentation | {metrics["late_fragmentation"]} |
| late beta1 cycles | {metrics["late_beta1_cycles"]} |

## Interpretation

If GV aligns with base recoverability but not topology, scalar GV may be incomplete.

If full PC1 remains dominant and GV aligns with it, scalar GV survives this first topology attack.

If full PC1 collapses, recoverability likely requires multi-axis geometry.

## Scientific line

This does not prove GV universal.

It tests whether scalar GV survives topology evolution, hidden strain, and hypergraph fragmentation.
''', encoding="utf-8")

    print(metrics)
    print(f"wrote {OUT_CSV}")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
