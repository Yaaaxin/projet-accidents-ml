"""Mécanismes connus : rareté, décalages et dépendance intra-département."""
import json

import numpy as np
import pandas as pd

from .conformal import allocate, prediction_sets
from .data import BASE, RESULTS, write_json


def draw(rng, n, target=False, rupture=False, correlated=False):
    g = rng.choice(8, n, p=np.arange(1, 9) / 36)
    x = rng.normal(size=n) + target * (.8 + g / 7)
    p_model = 1 / (1 + np.exp(3 - 1.2 * x))
    eta = -3 + 1.2 * x + np.linspace(-1.8, 1.3, 8)[g]
    if rupture:
        eta += 2.5 - 2 * x
    if correlated:
        eta += rng.normal(0, 1.5, 8)[g]
    y = (rng.random(n) < 1 / (1 + np.exp(-eta))).astype(int)
    return p_model, y, g.astype(str)


def main():
    cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    rows = []
    for repeat in range(cfg["simulation_repeats"]):
        for condition in ["echangeable", "decalage_source_cible", "rupture_calibration_test", "correlation_regionale"]:
            rng = np.random.default_rng(81000 + repeat)
            ps, ys, gs = draw(rng, 3000)
            pa, ya, ga = draw(rng, 5000, target=condition != "echangeable", correlated=condition == "correlation_regionale")
            pt, yt, gt = draw(rng, 4000, target=condition != "echangeable", rupture=condition == "rupture_calibration_test",
                              correlated=condition == "correlation_regionale")
            def record(method, budget, sets, cells):
                covered = sets[np.arange(len(yt)), yt]
                rows.append(dict(repeat=repeat, condition=condition, method=method, budget=budget,
                    coverage=float(covered.mean()), fatal_coverage=float(covered[yt == 1].mean()),
                    mean_size=float(sets.sum(axis=1).mean()), singleton_rate=float((sets.sum(axis=1) == 1).mean()),
                    fatal_cells_infinite=sum(c["class"] == 1 and c["infinite"] for c in cells)))
            for mode in ["pooled", "class"]:
                sets, cells = prediction_sets(ps, ys, pt, mode=mode)
                record("source_" + mode, 0, sets, cells)
            for budget in [120, 600]:
                for policy in cfg["policies"]:
                    selected, yc, pilot, quota = allocate(ga, budget, policy, repeat, lambda idx: ya[idx], ys.mean(), pilot_per_group=3)
                    sets, cells = prediction_sets(pa[selected], yc, pt, mode="group_class", cal_g=ga[selected], test_g=gt)
                    record(policy, budget, sets, cells)
        if (repeat + 1) % 20 == 0:
            print("Simulation", repeat + 1, flush=True)
            pd.DataFrame(rows).to_csv(RESULTS / "simulation_trials.csv", index=False)
    frame = pd.DataFrame(rows)
    measures = ["coverage", "fatal_coverage", "mean_size", "singleton_rate", "fatal_cells_infinite"]
    frame.groupby(["condition", "method", "budget"])[measures].agg(["mean", "std"]).to_csv(RESULTS / "simulation_summary.csv")
    write_json(RESULTS / "simulation_dgp.json", {"seed": "81000 + répétition", "repetitions": cfg["simulation_repeats"],
       "groups": 8, "source_n": 3000, "adaptation_n": 5000, "test_n": 4000, "budgets": [120, 600],
       "pilot_per_group": 3, "alpha": .1, "score": "sigmoid(-3+1.2*x)",
       "group_probability": "(g+1)/36 ; g=0,...,7", "true_logit": "-3+1.2*x+linspace(-1.8,1.3,8)[g]",
       "target_x_shift": "0.8+g/7", "rupture_logit_increment": "2.5-2*x, test seulement",
       "correlation": "effet N(0,1.5²) commun aux accidents du département, indépendant entre adaptation et test"})


if __name__ == "__main__":
    main()
