"""Simulation contrôlée des effets régionaux et du coût du pilot."""
import json
import platform
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import sklearn
from scipy.special import expit
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from .audit import AUDIT_PRIVATE, AUDIT_RESULTS, enhanced_evaluate, expected_shortfall, fingerprint
from .conformal import allocate, prediction_sets, quotas
from .data import BASE, write_json
from .download import digest

SIMULATION_STRESS_BUDGET = 2400


def simulation_fingerprint():
    value = fingerprint()
    value["audit_simulation.py"] = digest(BASE / "audit_simulation.py")
    value["stress_budget"] = SIMULATION_STRESS_BUDGET
    return value


def population(rng, n, regions, x_shift=0.0, effects=None, coefficients=(1.35, -0.65)):
    group = rng.integers(regions, size=n)
    x = rng.normal(size=(n, 2))
    x[:, 0] += x_shift
    regional = np.zeros(regions) if effects is None else np.asarray(effects)
    eta = -4.0 + coefficients[0] * x[:, 0] + coefficients[1] * x[:, 1] + regional[group]
    probability = expit(eta)
    y = rng.binomial(1, probability)
    return x, y, group.astype(str), probability


def condition_parameters(condition, rng, regions):
    zeros = np.zeros(regions)
    if condition == "exchangeable":
        return dict(x_shift=0.0, adapt_effect=zeros, test_effect=zeros, coefficients=(1.35, -0.65))
    if condition == "covariate_shift":
        return dict(x_shift=0.8, adapt_effect=zeros, test_effect=zeros, coefficients=(1.35, -0.65))
    if condition == "shared_region_effect":
        effect = rng.normal(0, 1.0, regions)
        return dict(x_shift=0.25, adapt_effect=effect, test_effect=effect, coefficients=(1.35, -0.65))
    if condition == "changed_region_effect":
        return dict(x_shift=0.25, adapt_effect=rng.normal(0, 1.0, regions),
                    test_effect=rng.normal(0, 1.0, regions), coefficients=(1.35, -0.65))
    if condition == "global_concept_drift":
        return dict(x_shift=0.25, adapt_effect=zeros, test_effect=zeros, coefficients=(0.55, 0.55))
    raise ValueError(condition)


def true_rate_allocation(groups, rates, budget, policy, seed, pilot_per_group=5):
    """Allocation oracle de simulation ; les taux viennent du mécanisme connu."""
    groups = np.asarray(groups)
    names = np.unique(groups)
    rng = np.random.default_rng(seed)
    pools = [rng.permutation(np.flatnonzero(groups == group)) for group in names]
    pilot = np.array([], dtype=int)
    if policy == "oracle_true_variance_costed":
        counts = np.array([min(pilot_per_group, len(pool)) for pool in pools])
        pilot = np.concatenate([pool[:count] for pool, count in zip(pools, counts)])
        pools = [pool[count:] for pool, count in zip(pools, counts)]
    elif policy not in ["oracle_true_variance", "oracle_true_equal_fatal"]:
        raise ValueError(policy)
    remaining = budget - len(pilot)
    if remaining < 0:
        raise ValueError("Budget inférieur au coût du pilot")
    capacities = np.array([len(pool) for pool in pools])
    inverse = 1 / np.array([rates[str(group)] for group in names])
    variance = policy != "oracle_true_equal_fatal"
    allocation = quotas(capacities, remaining, inverse, variance_objective=variance)
    selected = np.concatenate([pool[:count] for pool, count in zip(pools, allocation)])
    return selected, pilot, dict(zip(names, allocation))


def metrics(y, p, sets, groups):
    score, _ = enhanced_evaluate(y, p, sets, groups, bootstrap=0)
    return score


def one_repeat(condition, repeat, audit_cfg):
    rng = np.random.default_rng(810_000 + repeat + 10_000 * audit_cfg["simulation_conditions"].index(condition))
    regions = 12
    parameters = condition_parameters(condition, rng, regions)
    x_fit, y_fit, _, _ = population(rng, 4000, regions)
    x_cal, y_cal, _, _ = population(rng, 2000, regions)
    x_same, y_same, g_same, _ = population(rng, 3000, regions)
    x_adapt, y_adapt, g_adapt, p_adapt_true = population(
        rng, 5000, regions, parameters["x_shift"], parameters["adapt_effect"], parameters["coefficients"])
    x_test, y_test, g_test, _ = population(
        rng, 4000, regions, parameters["x_shift"], parameters["test_effect"], parameters["coefficients"])
    model = LogisticRegression(C=1.0, max_iter=1000, n_jobs=1).fit(x_fit, y_fit)
    p_cal = model.predict_proba(x_cal)[:, 1]
    p_same = model.predict_proba(x_same)[:, 1]
    p_adapt = model.predict_proba(x_adapt)[:, 1]
    p_test = model.predict_proba(x_test)[:, 1]
    rows, pilots = [], []

    def save(method, budget, sets, allocation="none", scope="source", pilot_n=0):
        rows.append(dict(condition=condition, repeat=repeat, method=method, budget=budget,
                         allocation=allocation, calibration_scope=scope, pilot_labels=pilot_n,
                         **metrics(y_test, p_test, sets, g_test)))

    for mode in ["pooled", "class"]:
        sets, _ = prediction_sets(p_cal, y_cal, p_test, mode=mode)
        save("source_" + mode, 0, sets)
    sets, _ = prediction_sets(p_cal, y_cal, p_same, mode="pooled")
    rows.append(dict(condition=condition, repeat=repeat, method="same_domain_source_pooled", budget=0,
                     allocation="none", calibration_scope="source_pooled", pilot_labels=0,
                     **metrics(y_same, p_same, sets, g_same)))

    rate = float(y_fit.mean())
    true_rates = {group: float(p_adapt_true[g_adapt == group].mean()) for group in np.unique(g_adapt)}

    budgets = sorted(set(audit_cfg["simulation_budgets"] + [SIMULATION_STRESS_BUDGET]))
    for budget in budgets:
        def label_oracle(indices):
            return y_adapt[np.asarray(indices, dtype=int)]

        for policy in ["uniform", "pilot_variance"]:
            seed = 93_000 + repeat
            selected, yc, pilot, allocation = allocate(
                g_adapt, budget, policy, seed, label_oracle, rate,
                audit_cfg["simulation_pilot_per_region"], 20)
            for scope, mode in [("pooled", "pooled"), ("class", "class"),
                                ("department_class", "group_class")]:
                sets, _ = prediction_sets(p_adapt[selected], yc, p_test, mode=mode,
                                           cal_g=g_adapt[selected] if mode == "group_class" else None,
                                           test_g=g_test if mode == "group_class" else None)
                save(f"{policy}__{scope}", budget, sets, policy, "local_" + scope, len(pilot))
            if policy == "pilot_variance":
                yp = y_adapt[pilot]
                for record in allocation:
                    group = str(record["group"])
                    mask = g_adapt[pilot] == group
                    pilots.append({"condition": condition, "repeat": repeat, "budget": budget,
                                   "group": group, "pilot_n": int(mask.sum()),
                                   "pilot_fatal_n": int(yp[mask].sum()),
                                   "pilot_zero_fatal": bool(yp[mask].sum() == 0),
                                   "pilot_posterior_rate": record["estimated_observed_fatal_rate"],
                                   "true_pool_rate": true_rates[group],
                                   "posterior_absolute_error": abs(record["estimated_observed_fatal_rate"] -
                                                                   true_rates[group])})

        for policy in ["oracle_true_variance_costed", "oracle_true_variance", "oracle_true_equal_fatal"]:
            selected, pilot, allocation = true_rate_allocation(
                g_adapt, true_rates, budget, policy, 93_000 + repeat,
                audit_cfg["simulation_pilot_per_region"])
            sets, cells = prediction_sets(p_adapt[selected], y_adapt[selected], p_test, mode="group_class",
                                           cal_g=g_adapt[selected], test_g=g_test)
            row = dict(condition=condition, repeat=repeat, method=policy, budget=budget,
                       allocation=policy, calibration_scope="local_department_class", pilot_labels=len(pilot),
                       **metrics(y_test, p_test, sets, g_test))
            row["fatal_cells_infinite"] = sum(cell["class"] == 1 and cell["infinite"] for cell in cells)
            row["expected_insufficient_fatal_cells"] = float(sum(
                expected_shortfall(allocation[group], true_rates[group]) for group in allocation))
            rows.append(row)
    return {"metrics": rows, "pilot": pilots}


def run():
    audit_cfg = json.loads((BASE / "audit_config.json").read_text(encoding="utf-8"))
    if audit_cfg["n_jobs"] != 1:
        raise ValueError("La simulation utilise n_jobs=1")
    output = AUDIT_RESULTS / "simulation"
    private = AUDIT_PRIVATE / "simulation-v2"
    output.mkdir(parents=True, exist_ok=True)
    private.mkdir(parents=True, exist_ok=True)
    all_results = []
    for condition in audit_cfg["simulation_conditions"]:
        for repeat in range(audit_cfg["simulation_repeats"]):
            checkpoint = private / f"{condition}-{repeat:03d}.json"
            if checkpoint.exists():
                payload = json.loads(checkpoint.read_text(encoding="utf-8"))
                if payload["fingerprint"] != simulation_fingerprint():
                    raise ValueError("Checkpoint de simulation périmé")
                result = payload["result"]
            else:
                with threadpool_limits(limits=1):
                    result = one_repeat(condition, repeat, audit_cfg)
                write_json(checkpoint, {"fingerprint": simulation_fingerprint(), "result": result})
            all_results.append(result)
            if (repeat + 1) % 20 == 0:
                print(condition, repeat + 1, "répétitions", flush=True)
    trials = pd.DataFrame([row for result in all_results for row in result["metrics"]])
    pilot = pd.DataFrame([row for result in all_results for row in result["pilot"]])
    trials.to_csv(output / "trials.csv", index=False)
    pilot.to_csv(output / "pilot_diagnostics.csv", index=False)
    measures = ["coverage", "fatal_coverage", "macro_fatal_department_coverage", "mean_size", "singleton_rate"]
    summary = trials.groupby(["condition", "budget", "method"], dropna=False)[measures].agg(["mean", "std"])
    summary.columns = ["_".join(column) for column in summary.columns]
    summary.reset_index().to_csv(output / "summary.csv", index=False)
    write_json(output / "execution.json", {
        "completed_utc": datetime.now(timezone.utc).isoformat(), "repeats": audit_cfg["simulation_repeats"],
        "conditions": audit_cfg["simulation_conditions"], "n_jobs": 1,
        "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
        "sklearn": sklearn.__version__, "stress_budget": SIMULATION_STRESS_BUDGET,
        "fingerprint": simulation_fingerprint()})


if __name__ == "__main__":
    run()
