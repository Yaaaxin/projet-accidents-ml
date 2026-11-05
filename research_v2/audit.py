"""Audit ciblé : densité alignée, granularité locale et mécanismes d'allocation."""
import argparse
import hashlib
import json
import math
import pickle
import platform
import time
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss
from threadpoolctl import threadpool_limits

from .conformal import allocate, prediction_sets, quotas, weighted_sets
from .data import BASE, PRIVATE, RESULTS, ids_hash, labels, write_json
from .download import digest
from .metrics import evaluate
from .models import fit_predict
from .run import prepare_scenario

AUDIT_RESULTS = RESULTS / "audit"
AUDIT_PRIVATE = PRIVATE / "audit"
BASE_CONFIG = BASE / "config.json"
AUDIT_CONFIG = BASE / "audit_config.json"


def fingerprint():
    paths = [BASE_CONFIG, AUDIT_CONFIG, BASE / "data.py", BASE / "models.py", BASE / "metrics.py",
             BASE / "conformal.py", BASE / "run.py", BASE / "audit.py"]
    return {p.name: digest(p) for p in paths}


def density_weights_aligned(estimator, frames, cfg):
    """Estimation indépendante sur tuning, de même loi source que conformal."""
    source = frames["tuning"]
    if len(source) > cfg["domain_source_limit"]:
        source = source.sample(n=cfg["domain_source_limit"], random_state=cfg["model_seed"])
    target = frames["adaptation"]
    both = pd.concat([source, target])
    domain = np.r_[np.zeros(len(source)), np.ones(len(target))]
    transform = estimator.named_steps["preparation"]
    classifier = LogisticRegression(C=.1, max_iter=1500, class_weight="balanced", n_jobs=1)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        classifier.fit(transform.transform(both), domain)
    output = {}
    for name in ["conformal", "test"]:
        p = np.clip(classifier.predict_proba(transform.transform(frames[name]))[:, 1], 1e-6, 1 - 1e-6)
        output[name] = np.clip(p / (1 - p), *cfg["domain_weight_clip"])
    return output, {"source_role": "tuning", "source_n": len(source), "target_role": "adaptation",
                    "target_n": len(target), "source_calibration_overlap": 0,
                    "same_source_year_and_departments": True}


def enhanced_evaluate(y, p, sets, departments, bootstrap, seed=782):
    score, regional = evaluate(y, p, sets, departments, bootstrap, seed)
    frame = pd.DataFrame(regional)
    fatal = frame[frame.fatal_n > 0]
    if fatal.empty:
        raise ValueError("Aucun décès test : couverture mortelle régionale non définie")
    values = fatal.fatal_coverage.to_numpy(float)
    score.update({
        "macro_fatal_department_coverage": float(values.mean()),
        "fatal_department_coverage_min": float(values.min()),
        "fatal_department_coverage_q10": float(np.quantile(values, .10)),
        "fatal_department_coverage_q25": float(np.quantile(values, .25)),
        "fatal_department_coverage_median": float(np.median(values)),
        "fatal_department_coverage_q75": float(np.quantile(values, .75)),
        "fatal_department_coverage_q90": float(np.quantile(values, .90)),
        "fatal_department_coverage_max": float(values.max()),
        "fatal_departments_evaluable": int(len(fatal)),
        "fatal_departments_zero_test": int((frame.fatal_n == 0).sum()),
        "fatal_department_n_min": int(fatal.fatal_n.min()),
        "fatal_department_n_median": float(fatal.fatal_n.median()),
        "fatal_department_n_max": int(fatal.fatal_n.max()),
    })
    return score, regional


def empirical_rates(groups, y):
    groups, y = np.asarray(groups), np.asarray(y)
    rows = []
    for group in np.unique(groups):
        values = y[groups == group]
        deaths = int(np.sum(values == 1))
        n = len(values)
        rows.append({"group": str(group), "pool_n": n, "pool_fatal_n": deaths,
                     "oracle_rate_raw": deaths / n,
                     "oracle_rate_smoothed": (deaths + .5) / (n + 1)})
    return pd.DataFrame(rows).set_index("group")


def expected_shortfall(n, p, minimum=9):
    n = int(n)
    if n < minimum:
        return 1.0
    q = 1 - float(p)
    return float(sum(math.comb(n, j) * float(p) ** j * q ** (n - j) for j in range(minimum)))


def allocation_diagnostics(records, rates, minimum=9):
    expected, objective = 0.0, 0.0
    for record in records:
        group = str(record["group"])
        n = int(record["quota"])
        p = float(rates.loc[group, "oracle_rate_smoothed"])
        expected += expected_shortfall(n, p, minimum)
        objective += 1 / (max(n, 1) * p)
    return {"expected_insufficient_fatal_cells": expected, "oracle_surrogate_objective": objective}


def explanatory_allocation(groups, y_all, budget, policy, seed, pilot_per_group=5):
    """Oracle historique non déployable, avec tirage aléatoire après quotas."""
    groups, y_all = np.asarray(groups), np.asarray(y_all)
    names = np.unique(groups)
    rates = empirical_rates(groups, y_all)
    rng = np.random.default_rng(seed)
    pools = [rng.permutation(np.flatnonzero(groups == group)) for group in names]
    pilot = np.array([], dtype=int)
    if policy == "oracle_variance_costed":
        counts = np.array([min(pilot_per_group, len(pool)) for pool in pools])
        pilot = np.concatenate([pool[:n] for pool, n in zip(pools, counts)])
        pools = [pool[n:] for pool, n in zip(pools, counts)]
    elif policy not in ["oracle_variance", "oracle_equal_fatal"]:
        raise ValueError(policy)
    remaining = budget - len(pilot)
    if remaining < 0:
        raise ValueError("Budget inférieur au coût oracle contrôlé")
    capacity = np.array([len(pool) for pool in pools])
    inverse_rate = 1 / rates.loc[names, "oracle_rate_smoothed"].to_numpy()
    if policy in ["oracle_variance_costed", "oracle_variance"]:
        n = quotas(capacity, remaining, inverse_rate, variance_objective=True)
    else:
        n = quotas(capacity, remaining, inverse_rate, variance_objective=False)
    selected = np.concatenate([pool[:count] for pool, count in zip(pools, n)])
    records = [{"group": str(group), "quota": int(count),
                "pilot_n": int(np.sum(groups[pilot] == group)),
                "estimated_observed_fatal_rate": float(rates.loc[str(group), "oracle_rate_smoothed"])}
               for group, count in zip(names, n)]
    return selected, y_all[selected], pilot, records, rates


def role_hashes(source):
    return {name: ids_hash(frame.index) for name, frame in source.items()}


def scenario(year, split, model, cfg, audit_cfg, phase):
    key = f"{year}-{split}-{model}"
    cache = AUDIT_PRIVATE / f"predictions-{key}.pkl"
    AUDIT_PRIVATE.mkdir(parents=True, exist_ok=True)
    fp = fingerprint()
    started = time.perf_counter()
    if cache.exists():
        payload = pickle.loads(cache.read_bytes())
        if payload["fingerprint"] != fp:
            raise ValueError(f"Cache d'audit périmé : {cache.name}")
    else:
        source, frames, roles = prepare_scenario(year, split, cfg)
        estimator, pred = fit_predict(frames, source["fit"].target, source["probability"].target, model, cfg)
        weights, density_audit = density_weights_aligned(estimator, frames, cfg)
        payload = {"fingerprint": fp, "probabilities": pred, "weights": weights,
                   "density_audit": density_audit, "roles": roles, "role_hashes": role_hashes(source),
                   "historical_rate": float(source["fit"].target.mean()),
                   "source_y": {name: source[name].target.to_numpy(dtype=int) for name in ["conformal", "tuning"]},
                   "source_dep": {name: source[name].dep.to_numpy() for name in ["conformal", "tuning"]},
                   "target_ids": {name: source[name].index.tolist() for name in ["adaptation", "test"]},
                   "target_dep": {name: source[name].dep.to_numpy() for name in ["adaptation", "test"]},
                   "fit_seconds": time.perf_counter() - started}
        cache.write_bytes(pickle.dumps(payload))

    pred = payload["probabilities"]
    test_y_all = labels(year, payload["target_ids"]["test"]).to_numpy()
    known_test = np.isin(test_y_all, [0, 1])
    y, p = test_y_all[known_test], pred["test"][known_test]
    test_groups = payload["target_dep"]["test"][known_test]
    adapt_ids = np.asarray(payload["target_ids"]["adaptation"])
    adapt_groups = payload["target_dep"]["adaptation"]
    label_cache = {}

    def oracle(indices):
        requested = adapt_ids[np.asarray(indices, dtype=int)]
        missing = [item for item in requested if item not in label_cache]
        if missing:
            label_cache.update(labels(year, missing).to_dict())
        return np.array([label_cache[item] for item in requested], dtype=int)

    development = phase == "development"
    all_adapt_y = labels(year, adapt_ids).to_numpy() if development else None
    rates = empirical_rates(adapt_groups, all_adapt_y) if development else None
    records, departments, cells_all, allocations, pilot_diagnostics = [], [], [], [], []
    base = {"phase": phase, "year": year, "split": split, "model": model,
            "post_publication_2025": year == 2025, "unknown_test_excluded": int((~known_test).sum()),
            "fit_seconds": payload["fit_seconds"], "evaluation_domain": "target_test"}

    def save(method, budget, seed, sets, cells=None, extra=None):
        meta = dict(base, method=method, budget=budget, seed=seed)
        score, regional = enhanced_evaluate(y, p, sets, test_groups, cfg["bootstrap_departments"])
        records.append(dict(meta, **score, **(extra or {})))
        departments.extend(dict(meta, **(extra or {}), **row) for row in regional)
        if cells:
            cells_all.extend(dict(meta, **(extra or {}), **row) for row in cells)

    for mode in ["pooled", "class"]:
        sets, cells = prediction_sets(pred["conformal"], payload["source_y"]["conformal"], p,
                                      cfg["alpha"], mode)
        save("source_" + mode, 0, 0, sets, cells, {"allocation": "none",
             "calibration_scope": "source_" + mode, "deployable": True,
             "analysis_status": "reference_originale_recalculee"})

    same_y, same_p = payload["source_y"]["tuning"], pred["tuning"]
    same_sets, same_cells = prediction_sets(pred["conformal"], payload["source_y"]["conformal"],
                                             same_p, cfg["alpha"], "pooled")
    same_score, same_regional = enhanced_evaluate(same_y, same_p, same_sets,
                                                   payload["source_dep"]["tuning"],
                                                   cfg["bootstrap_departments"])
    same_meta = dict(base, method="same_domain_source_pooled", budget=0, seed=0,
                     allocation="none", calibration_scope="source_pooled",
                     deployable=True, analysis_status="controle_meme_domaine",
                     evaluation_domain="source_tuning", unknown_test_excluded=0)
    records.append(dict(same_meta, **same_score))
    departments.extend(dict(same_meta, **row) for row in same_regional)
    cells_all.extend(dict(same_meta, **row) for row in same_cells)
    sets = weighted_sets(pred["conformal"], payload["source_y"]["conformal"], p,
                         payload["weights"]["conformal"], payload["weights"]["test"][known_test], cfg["alpha"])
    save("source_weighted_aligned", 0, 0, sets, extra={"allocation": "none",
         "calibration_scope": "source_weighted", "deployable": True,
         "analysis_status": "baseline_corrigee",
         "weight_effective_n": float(payload["weights"]["conformal"].sum() ** 2 /
                                     np.square(payload["weights"]["conformal"]).sum())})

    min_budget = min(cfg["budgets"])
    for budget in cfg["budgets"]:
        for seed in cfg["calibration_seeds"]:
            for policy in cfg["policies"]:
                selected, yc, pilot, quota = allocate(adapt_groups, budget, policy, seed, oracle,
                    payload["historical_rate"], cfg["pilot_per_department"], cfg["pilot_prior_strength"])
                known_cal = np.isin(yc, [0, 1])
                chosen = selected[known_cal]
                shared = {"allocation": policy, "deployable": True,
                          "analysis_status": "controle_post_publication" if year == 2025 else "validation_historique",
                          "pilot_labels": len(pilot), "calibration_labels": int(known_cal.sum()),
                          "unknown_calibration_excluded": int((~known_cal).sum()),
                          "fatal_calibration": int(np.sum(yc == 1)),
                          "calibration_ids_sha256": ids_hash(adapt_ids[selected])}
                if development:
                    shared.update(allocation_diagnostics(quota, rates,
                                  audit_cfg["fatal_cell_minimum_alpha_0_10"]))
                for scope, mode in [("pooled", "pooled"), ("class", "class"),
                                    ("department_class", "group_class")]:
                    sets, cells = prediction_sets(pred["adaptation"][chosen], yc[known_cal], p, cfg["alpha"],
                        mode, adapt_groups[chosen] if mode == "group_class" else None,
                        test_groups if mode == "group_class" else None)
                    extra = dict(shared, calibration_scope="local_" + scope,
                                 fatal_cells_infinite=sum(c["class"] == 1 and c["infinite"] for c in cells
                                                          if c["class"] != "all"))
                    save(f"{policy}__{scope}", budget, seed, sets, cells, extra)
                allocations.extend(dict(base, method=policy, budget=budget, seed=seed, **row) for row in quota)
                if policy == "pilot_variance" and budget == min_budget:
                    pilot_y = oracle(pilot)
                    for row in quota:
                        group = str(row["group"])
                        mask = adapt_groups[pilot] == group
                        pdg = int(np.sum(pilot_y[mask] == 1))
                        diag = dict(base, seed=seed, group=group, pilot_n=int(mask.sum()), pilot_fatal_n=pdg,
                                    pilot_zero_fatal=pdg == 0,
                                    pilot_raw_rate=pdg / max(int(mask.sum()), 1),
                                    pilot_posterior_rate=float(row["estimated_observed_fatal_rate"]))
                        if development:
                            diag.update(rates.loc[group].to_dict())
                            diag["posterior_abs_error_raw"] = abs(diag["pilot_posterior_rate"] - diag["oracle_rate_raw"])
                            diag["posterior_abs_error_smoothed"] = abs(diag["pilot_posterior_rate"] - diag["oracle_rate_smoothed"])
                        pilot_diagnostics.append(diag)

            if development:
                for policy in audit_cfg["historical_oracle_policies"]:
                    selected, yc, pilot, quota, oracle_rates = explanatory_allocation(
                        adapt_groups, all_adapt_y, budget, policy, seed, cfg["pilot_per_department"])
                    known_cal = np.isin(yc, [0, 1])
                    chosen = selected[known_cal]
                    sets, cells = prediction_sets(pred["adaptation"][chosen], yc[known_cal], p, cfg["alpha"],
                                                  "group_class", adapt_groups[chosen], test_groups)
                    extra = {"allocation": policy, "calibration_scope": "local_department_class",
                             "deployable": False, "analysis_status": "oracle_historique_explicatif",
                             "pilot_labels": len(pilot), "calibration_labels": int(known_cal.sum()),
                             "unknown_calibration_excluded": int((~known_cal).sum()),
                             "fatal_calibration": int(np.sum(yc == 1)),
                             "calibration_ids_sha256": ids_hash(adapt_ids[selected]),
                             "fatal_cells_infinite": sum(c["class"] == 1 and c["infinite"] for c in cells)}
                    extra.update(allocation_diagnostics(quota, oracle_rates,
                                 audit_cfg["fatal_cell_minimum_alpha_0_10"]))
                    save(policy, budget, seed, sets, cells, extra)
                    allocations.extend(dict(base, method=policy, budget=budget, seed=seed, **row) for row in quota)

    yt, pt = payload["source_y"]["tuning"], pred["tuning"]
    source_validation = dict(base, n=len(yt), average_precision=float(average_precision_score(yt, pt)),
                             brier=float(brier_score_loss(yt, pt)))
    return {"fingerprint": fp, "metrics": records, "departments": departments, "cells": cells_all,
            "allocation": allocations, "pilot_diagnostics": pilot_diagnostics, "roles": payload["roles"],
            "role_hashes": payload["role_hashes"], "density_audit": payload["density_audit"],
            "source_validation": source_validation}


def run(phase):
    cfg = json.loads(BASE_CONFIG.read_text(encoding="utf-8"))
    audit_cfg = json.loads(AUDIT_CONFIG.read_text(encoding="utf-8"))
    if cfg["n_jobs"] != 1 or audit_cfg["n_jobs"] != 1:
        raise ValueError("L'audit utilise n_jobs=1")
    if phase == "corrected_2025":
        frozen = json.loads((BASE / "audit_freeze.json").read_text(encoding="utf-8"))
        if frozen["fingerprint"] != fingerprint():
            raise ValueError("Le code d'audit ne correspond plus au gel historique")
        write_json(AUDIT_RESULTS / "corrected_2025_access.json", {
            "opened_utc": datetime.now(timezone.utc).isoformat(), "status": "correction postérieure",
            "audit_freeze_sha256": digest(BASE / "audit_freeze.json"), "fingerprint": fingerprint()})
    years = cfg["development_years"] if phase == "development" else [cfg["final_year"]]
    output = AUDIT_RESULTS / phase
    output.mkdir(parents=True, exist_ok=True)
    runs = []
    for year in years:
        for split in cfg["geography_seeds"]:
            for model in cfg["models"]:
                checkpoint = AUDIT_PRIVATE / f"checkpoint-{phase}-{year}-{split}-{model}.json"
                if checkpoint.exists():
                    result = json.loads(checkpoint.read_text(encoding="utf-8"))
                    if result["fingerprint"] != fingerprint():
                        raise ValueError("Checkpoint d'audit périmé")
                else:
                    with threadpool_limits(limits=1):
                        result = scenario(year, split, model, cfg, audit_cfg, phase)
                    write_json(checkpoint, result)
                runs.append(result)
                for kind in ["metrics", "departments", "cells", "allocation", "pilot_diagnostics"]:
                    pd.DataFrame([row for run_result in runs for row in run_result[kind]]).to_csv(
                        output / f"{kind}.csv", index=False)
                pd.DataFrame([r["source_validation"] for r in runs]).to_csv(output / "source_validation.csv", index=False)
                write_json(output / "roles.json", [{"year": r["metrics"][0]["year"],
                    "split": r["metrics"][0]["split"], "model": r["metrics"][0]["model"],
                    "roles": r["roles"], "role_hashes": r["role_hashes"],
                    "density_audit": r["density_audit"]} for r in runs])
                print(phase, year, split, model, len(result["metrics"]), "évaluations sauvegardées", flush=True)
    write_json(output / "execution.json", {"completed_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
        "sklearn": sklearn.__version__, "n_jobs": 1, "fingerprint": fingerprint(),
        "post_publication_2025": phase == "corrected_2025"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["development", "corrected_2025"])
    run(parser.parse_args().phase)
