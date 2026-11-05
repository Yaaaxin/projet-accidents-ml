"""Expériences reprises par scénario ; aucun réglage sur le test final."""
import argparse
import json
import pickle
import platform
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import sklearn
from threadpoolctl import threadpool_limits

from .conformal import allocate, prediction_sets, weighted_sets
from .data import BASE, PRIVATE, RESULTS, features, hash_fraction, ids_hash, labels, write_json
from .download import digest
from .metrics import evaluate
from .models import density_weights, fit_predict


def fingerprint():
    paths = [BASE / n for n in ["config.json", "partitions.json", "data_manifest.json",
             "data.py", "models.py", "metrics.py", "conformal.py", "run.py"]]
    return {p.name: digest(p) for p in paths}


def prepare_scenario(year, split, cfg):
    held = json.loads((BASE / "partitions.json").read_text(encoding="utf-8"))["held_departments"][str(split)]
    history = pd.concat([features(y).join(labels(y)) for y in range(2019, year)])
    history = history[(~history.dep.isin(held)) & history.target.isin([0, 1])]
    latest = history[history.year == year - 1]
    frac = hash_fraction(latest.index, cfg["source_roles_salt"])
    a, b, _ = cfg["source_latest_year_fractions"]
    source = {"fit": history[history.year < year - 1], "tuning": latest[frac < a],
              "probability": latest[(frac >= a) & (frac < a + b)], "conformal": latest[frac >= a + b]}
    target = features(year)
    target = target[target.dep.isin(held)]
    partition = pd.read_csv(PRIVATE / f"partition-{year}.csv", index_col=0).role
    source["adaptation"] = target[partition.reindex(target.index).eq("adaptation")]
    source["test"] = target[partition.reindex(target.index).eq("test")]
    roles = list(source)
    for i, first in enumerate(roles):
        for second in roles[i + 1:]:
            if len(source[first].index.intersection(source[second].index)):
                raise AssertionError("Accidents communs entre rôles")
    feature_names = [c for c in target if c not in ["dep", "year", "target"]]
    forbidden = {"Num_Acc", "Accident_Id", "grav", "col", "dep", "year", "target", "id_usager", "id_vehicule"}
    if forbidden.intersection(feature_names):
        raise AssertionError("Variable interdite")
    frames = {name: frame[feature_names] for name, frame in source.items()}
    audit = {name: {"n": len(frame), "ids_sha256": ids_hash(frame.index)} for name, frame in source.items()}
    audit["all_roles_disjoint"] = True
    audit["source_target_departments_disjoint"] = not bool(set(history.dep) & set(target.dep))
    return source, frames, audit


def scenario(year, split, model, cfg, pilot=False):
    key = f"{year}-{split}-{model}"
    cache = PRIVATE / f"predictions-{key}.pkl"
    fp = fingerprint()
    started = time.perf_counter()
    if cache.exists():
        payload = pickle.loads(cache.read_bytes())
        if payload["fingerprint"] != fp:
            raise ValueError(f"Cache périmé : {cache.name}. Utiliser un nouveau répertoire ou l'archiver.")
    else:
        source, frames, audit = prepare_scenario(year, split, cfg)
        estimator, pred = fit_predict(frames, source["fit"].target, source["probability"].target, model, cfg)
        weights = density_weights(estimator, frames, cfg)
        payload = {"fingerprint": fp, "probabilities": pred, "weights": weights, "roles": audit,
                   "historical_rate": float(source["fit"].target.mean()),
                   "source_y": {k: source[k].target.to_numpy(dtype=int) for k in ["conformal", "tuning"]},
                   "target_ids": {k: source[k].index.tolist() for k in ["adaptation", "test"]},
                   "target_dep": {k: source[k].dep.to_numpy() for k in ["adaptation", "test"]},
                   "fit_seconds": time.perf_counter() - started}
        cache.write_bytes(pickle.dumps(payload))
    pred, weights = payload["probabilities"], payload["weights"]
    # L'évaluation finale n'est atteignable qu'après vérification du gel dans main().
    test_y_all = labels(year, payload["target_ids"]["test"]).to_numpy()
    known_test = np.isin(test_y_all, [0, 1])
    y, p = test_y_all[known_test], pred["test"][known_test]
    g = payload["target_dep"]["test"][known_test]
    adapt_ids = np.asarray(payload["target_ids"]["adaptation"])
    adapt_g = payload["target_dep"]["adaptation"]
    # L'oracle n'expose à l'allocation que les étiquettes des accidents demandés.
    label_cache = {}
    def oracle(indices):
        requested = adapt_ids[indices]
        missing = [i for i in requested if i not in label_cache]
        if missing:
            label_cache.update(labels(year, missing).to_dict())
        return np.array([label_cache[i] for i in requested])
    records, departments, cells_all, allocations = [], [], [], []
    base = {"year": year, "split": split, "model": model,
            "unknown_test_excluded": int((~known_test).sum()), "fit_seconds": payload["fit_seconds"]}
    def save(method, budget, seed, sets, cells=None, extra=None):
        meta = dict(base, method=method, budget=budget, seed=seed)
        score, regional = evaluate(y, p, sets, g, cfg["bootstrap_departments"])
        records.append(dict(meta, **score, **(extra or {})))
        departments.extend(dict(meta, **row) for row in regional)
        if cells:
            cells_all.extend(dict(meta, **row) for row in cells)
    for mode in ["pooled", "class"]:
        sets, cells = prediction_sets(pred["conformal"], payload["source_y"]["conformal"], p, cfg["alpha"], mode)
        save("source_" + mode, 0, 0, sets, cells, {"setting": "sans_cible"})
    sets = weighted_sets(pred["conformal"], payload["source_y"]["conformal"], p,
                         weights["conformal"], weights["test"][known_test], cfg["alpha"])
    save("source_weighted", 0, 0, sets, extra={"setting": "cible_non_etiquetee",
         "weight_effective_n": float(weights["conformal"].sum() ** 2 / np.square(weights["conformal"]).sum())})
    budgets = cfg["budgets"][:1] if pilot else cfg["budgets"]
    seeds = cfg["calibration_seeds"][:1] if pilot else cfg["calibration_seeds"]
    for budget in budgets:
        for seed in seeds:
            for policy in cfg["policies"]:
                selected, yc, pil, quota = allocate(adapt_g, budget, policy, seed, oracle,
                       payload["historical_rate"], cfg["pilot_per_department"], cfg["pilot_prior_strength"])
                known_cal = np.isin(yc, [0, 1])
                chosen = selected[known_cal]
                sets, cells = prediction_sets(pred["adaptation"][chosen], yc[known_cal], p, cfg["alpha"],
                                             "group_class", adapt_g[chosen], g)
                save(policy, budget, seed, sets, cells, {"setting": "cible_etiquetee",
                     "pilot_labels": len(pil), "calibration_labels": len(chosen),
                     "unknown_calibration_excluded": int((~known_cal).sum()),
                     "fatal_calibration": int(np.sum(yc == 1)),
                     "fatal_cells_infinite": sum(c["class"] == 1 and c["infinite"] for c in cells)})
                allocations.extend(dict(base, method=policy, budget=budget, seed=seed, **q) for q in quota)
    from sklearn.metrics import average_precision_score, brier_score_loss
    yt, pt = payload["source_y"]["tuning"], pred["tuning"]
    tuning = dict(base, n=len(yt), average_precision=float(average_precision_score(yt, pt)),
                  brier=float(brier_score_loss(yt, pt)))
    return {"fingerprint": fp, "metrics": records, "departments": departments, "cells": cells_all,
            "allocation": allocations, "roles": payload["roles"], "source_validation": tuning}


def run(phase):
    cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    if cfg["n_jobs"] != 1:
        raise ValueError("Cette expérience utilise n_jobs=1")
    if phase == "final":
        frozen = json.loads((BASE / "freeze.json").read_text(encoding="utf-8"))
        if frozen["fingerprint"] != fingerprint():
            raise ValueError("Le code ou le protocole ne correspond plus au gel")
        write_json(RESULTS / "final_access_receipt.json", {"opened_utc": datetime.now(timezone.utc).isoformat(),
                   "freeze_sha256": digest(BASE / "freeze.json"), "fingerprint": fingerprint()})
    years = [2024] if phase == "pilot" else [2025] if phase == "final" else cfg["development_years"]
    splits = cfg["geography_seeds"][:1] if phase == "pilot" else cfg["geography_seeds"]
    output = RESULTS / phase
    output.mkdir(parents=True, exist_ok=True)
    runs = []
    for year in years:
        for split in splits:
            for model in cfg["models"]:
                checkpoint = PRIVATE / f"checkpoint-{phase}-{year}-{split}-{model}.json"
                if checkpoint.exists():
                    result = json.loads(checkpoint.read_text(encoding="utf-8"))
                    if result["fingerprint"] != fingerprint():
                        raise ValueError("Checkpoint périmé")
                else:
                    with threadpool_limits(limits=1):
                        result = scenario(year, split, model, cfg, phase == "pilot")
                    write_json(checkpoint, result)
                runs.append(result)
                for kind in ["metrics", "departments", "cells", "allocation"]:
                    pd.DataFrame([r for run in runs for r in run[kind]]).to_csv(output / f"{kind}.csv", index=False)
                pd.DataFrame([r["source_validation"] for r in runs]).to_csv(output / "source_validation.csv", index=False)
                write_json(output / "roles.json", [dict(year=r["metrics"][0]["year"], split=r["metrics"][0]["split"],
                           model=r["metrics"][0]["model"], **r["roles"]) for r in runs])
                print(phase, year, split, model, len(result["metrics"]), "évaluations sauvegardées", flush=True)
    write_json(output / "execution.json", {"completed_utc": datetime.now(timezone.utc).isoformat(),
               "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
               "sklearn": sklearn.__version__, "n_jobs": 1, "fingerprint": fingerprint()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["pilot", "development", "final"])
    run(parser.parse_args().phase)
