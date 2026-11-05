"""Quantiles conformes et allocation indépendante des étiquettes de calibration."""
import math

import numpy as np


def quantile(scores, alpha=.1):
    scores = np.asarray(scores, dtype=float)
    if not 0 < alpha < 1 or not np.isfinite(scores).all():
        raise ValueError("Scores ou niveau invalides")
    k = math.ceil((len(scores) + 1) * (1 - alpha) - 1e-12)
    return float(np.partition(scores, k - 1)[k - 1]) if k <= len(scores) else np.inf


def prediction_sets(cal_p, cal_y, test_p, alpha=.1, mode="pooled", cal_g=None, test_g=None):
    cal_p, cal_y, test_p = map(np.asarray, [cal_p, cal_y, test_p])
    if not np.isin(cal_y, [0, 1]).all():
        raise ValueError("Étiquette de calibration inconnue")
    scores = np.where(cal_y == 1, 1 - cal_p, cal_p)
    test_scores = np.column_stack([test_p, 1 - test_p])
    q = np.full((len(test_p), 2), np.inf)
    cells = []
    if mode == "pooled":
        q[:] = quantile(scores, alpha)
        cells.append({"group": "source", "class": "all", "n": len(scores), "infinite": bool(np.isinf(q[0, 0]))})
    elif mode in ["class", "group_class"]:
        groups = np.unique(test_g) if mode == "group_class" else ["source"]
        for g in groups:
            ci = np.asarray(cal_g) == g if mode == "group_class" else np.ones(len(cal_y), dtype=bool)
            ti = np.asarray(test_g) == g if mode == "group_class" else np.ones(len(test_p), dtype=bool)
            for y in [0, 1]:
                values = scores[ci & (cal_y == y)]
                threshold = quantile(values, alpha)
                q[ti, y] = threshold
                cells.append({"group": str(g), "class": y, "n": len(values), "infinite": bool(np.isinf(threshold))})
    else:
        raise ValueError(mode)
    return test_scores <= q, cells


def weighted_sets(cal_p, cal_y, test_p, cal_w, test_w, alpha=.1):
    """Atome du point test placé à +infini, comme dans le quantile pondéré."""
    scores = np.where(np.asarray(cal_y) == 1, 1 - np.asarray(cal_p), cal_p)
    order = np.argsort(scores)
    scores, weights = scores[order], np.asarray(cal_w)[order]
    if np.any(weights <= 0) or np.any(np.asarray(test_w) <= 0):
        raise ValueError("Poids strictement positifs requis")
    cumulative = np.cumsum(weights)
    k = np.searchsorted(cumulative, (1 - alpha) * (weights.sum() + np.asarray(test_w)), side="left")
    q = np.r_[scores, np.inf][k]
    return np.column_stack([test_p, 1 - np.asarray(test_p)]) <= q[:, None]


def quotas(capacities, budget, weights, variance_objective=False):
    """Allocation entière sous capacités ; gain marginal exact pour somme a_g/n_g."""
    capacities = np.asarray(capacities, dtype=int)
    weights = np.asarray(weights, dtype=float)
    if budget > capacities.sum() or budget < 0 or np.any(weights <= 0):
        raise ValueError("Budget ou poids non réalisables")
    n = np.zeros(len(capacities), dtype=int)
    for step in range(budget):
        if variance_objective:
            with np.errstate(divide="ignore"):
                priority = np.where(n == 0, np.inf, weights / (n * (n + 1)))
        else:
            priority = (step + 1) * weights / weights.sum() - n
        priority[n >= capacities] = -np.inf
        n[np.argmax(priority)] += 1
    return n


def allocate(groups, budget, policy, seed, oracle, historical_rate, pilot_per_group=5, prior_strength=20):
    """L'oracle ne reçoit que les indices acquis ; le pilot n'est jamais réutilisé."""
    groups = np.asarray(groups)
    names = np.unique(groups)
    rng = np.random.default_rng(seed)
    pools = [rng.permutation(np.flatnonzero(groups == g)) for g in names]
    pilot = np.array([], dtype=int)
    p = np.full(len(names), historical_rate, dtype=float)
    if policy == "pilot_variance":
        counts = np.array([min(pilot_per_group, len(pool)) for pool in pools])
        pilot = np.concatenate([pool[:k] for pool, k in zip(pools, counts)])
        if len(pilot) > budget:
            raise ValueError("Budget insuffisant pour le pilot")
        yp = np.asarray(oracle(pilot))
        for i, g in enumerate(names):
            selected = groups[pilot] == g
            p[i] = (np.sum(yp[selected] == 1) + prior_strength * historical_rate) / (selected.sum() + prior_strength)
        p = np.clip(p, .005, .5)
        pools = [pool[k:] for pool, k in zip(pools, counts)]
    caps = np.array(list(map(len, pools)))
    if policy == "proportional":
        weights = np.maximum(caps, 1)
    elif policy == "uniform":
        weights = np.ones(len(names))
    elif policy == "pilot_variance":
        weights = 1 / p
    else:
        raise ValueError(policy)
    n = quotas(caps, budget - len(pilot), weights, variance_objective=policy == "pilot_variance")
    selected = np.concatenate([pool[:k] for pool, k in zip(pools, n)])
    yc = np.asarray(oracle(selected))
    if len(np.unique(np.r_[pilot, selected])) != budget:
        raise AssertionError("Coût ou indépendance pilot/calibration incorrects")
    records = [{"group": str(g), "quota": int(k), "estimated_observed_fatal_rate": float(rate),
                "pilot_n": int(np.sum(groups[pilot] == g))} for g, k, rate in zip(names, n, p)]
    return selected, yc, pilot, records
