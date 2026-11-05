"""Évaluation à l'accident et intervalles descriptifs par blocs départementaux."""
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss


def evaluate(y, p, sets, departments, bootstrap=1000, seed=782):
    y, p, sets, departments = map(np.asarray, [y, p, sets, departments])
    if not np.isin(y, [0, 1]).all():
        raise ValueError("Le test doit exclure les étiquettes indéterminées")
    covered = sets[np.arange(len(y)), y.astype(int)]
    sizes = sets.sum(axis=1)
    records = []
    for g in np.unique(departments):
        mask = departments == g
        fatal = mask & (y == 1)
        records.append({"department": str(g), "n": int(mask.sum()), "fatal_n": int(fatal.sum()),
                        "covered_n": int(covered[mask].sum()), "fatal_covered_n": int(covered[fatal].sum()),
                        "coverage": float(covered[mask].mean()),
                        "fatal_coverage": float(covered[fatal].mean()) if fatal.any() else None,
                        "mean_size": float(sizes[mask].mean()), "singleton_rate": float((sizes[mask] == 1).mean()),
                        "empty_rate": float((sizes[mask] == 0).mean()), "small_fatal_n": bool(fatal.sum() < 20)})
    regions = pd.DataFrame(records)
    result = {"test_n": len(y), "fatal_n": int(y.sum()), "prevalence": float(y.mean()),
              "coverage": float(covered.mean()), "fatal_coverage": float(covered[y == 1].mean()),
              "mean_size": float(sizes.mean()), "singleton_rate": float((sizes == 1).mean()),
              "empty_rate": float((sizes == 0).mean()), "average_precision": float(average_precision_score(y, p)),
              "brier": float(brier_score_loss(y, p)),
              "macro_department_coverage": float(regions.coverage.mean()),
              "min_department_coverage": float(regions.coverage.min()),
              "departments_below_90": int((regions.coverage < .9).sum()),
              "departments_small_fatal_n": int(regions.small_fatal_n.sum())}
    if bootstrap:
        rng = np.random.default_rng(seed)
        take = rng.integers(len(regions), size=(bootstrap, len(regions)))
        for name, num, den in [("coverage", regions.covered_n, regions.n),
                               ("fatal_coverage", regions.fatal_covered_n, regions.fatal_n)]:
            a, b = num.to_numpy()[take].sum(axis=1), den.to_numpy()[take].sum(axis=1)
            ratios = a[b > 0] / b[b > 0]
            lo, hi = np.quantile(ratios, [.025, .975])
            result[name + "_block_low"], result[name + "_block_high"] = float(lo), float(hi)
    return result, records
