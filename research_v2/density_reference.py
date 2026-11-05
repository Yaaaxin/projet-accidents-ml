"""Comparer fit et tuning avec les mêmes prédictions et le même environnement."""
import json
import pickle
import platform
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import sklearn
from threadpoolctl import threadpool_limits

from .audit import AUDIT_PRIVATE, AUDIT_RESULTS, density_weights_aligned, enhanced_evaluate, fingerprint
from .conformal import weighted_sets
from .data import BASE, labels, write_json
from .download import digest
from .models import density_weights, pipeline
from .run import prepare_scenario


def comparison_fingerprint():
    return {"audit": fingerprint(), "density_reference.py": digest(BASE / "density_reference.py"),
            "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
            "sklearn": sklearn.__version__}


def scenario_weights(year, split, cfg):
    cache = AUDIT_PRIVATE / f"density-reference-{year}-{split}.pkl"
    expected = comparison_fingerprint()
    if cache.exists():
        payload = pickle.loads(cache.read_bytes())
        if payload["fingerprint"] != expected:
            raise ValueError(f"Cache de densité périmé : {cache.name}")
        return payload
    source, frames, _ = prepare_scenario(year, split, cfg)
    estimator = pipeline(frames["fit"], "logistic", cfg)
    estimator.named_steps["preparation"].fit(frames["fit"])
    fit_weights = density_weights(estimator, frames, cfg)
    tuning_weights, audit = density_weights_aligned(estimator, frames, cfg)
    payload = {"fingerprint": expected, "fit": fit_weights, "tuning": tuning_weights,
               "source_y": source["conformal"].target.to_numpy(dtype=int), "density_audit": audit}
    cache.write_bytes(pickle.dumps(payload))
    return payload


def read_audit_metrics(period):
    path = AUDIT_RESULTS / period / "metrics.csv"
    return pd.read_csv(path if path.exists() else path.with_suffix(".csv.gz"))


def run():
    cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    if cfg["n_jobs"] != 1:
        raise ValueError("La comparaison utilise n_jobs=1")
    rows = []
    for year in cfg["development_years"] + [cfg["final_year"]]:
        period = "development" if year in cfg["development_years"] else "corrected_2025"
        for split in cfg["geography_seeds"]:
            with threadpool_limits(limits=1):
                weights = scenario_weights(year, split, cfg)
            for model in cfg["models"]:
                prediction_cache = AUDIT_PRIVATE / f"predictions-{year}-{split}-{model}.pkl"
                cached = pickle.loads(prediction_cache.read_bytes())
                if cached["fingerprint"] != fingerprint():
                    raise ValueError(f"Cache de prédictions périmé : {prediction_cache.name}")
                for role in ["conformal", "test"]:
                    np.testing.assert_allclose(weights["tuning"][role], cached["weights"][role], rtol=0, atol=0)
                test_y_all = labels(year, cached["target_ids"]["test"]).to_numpy()
                known = np.isin(test_y_all, [0, 1])
                y = test_y_all[known]
                p = cached["probabilities"]["test"][known]
                groups = cached["target_dep"]["test"][known]
                for reference in ["fit", "tuning"]:
                    selected_weights = weights[reference]
                    sets = weighted_sets(cached["probabilities"]["conformal"], weights["source_y"], p,
                                         selected_weights["conformal"], selected_weights["test"][known],
                                         cfg["alpha"])
                    score, _ = enhanced_evaluate(y, p, sets, groups, cfg["bootstrap_departments"])
                    rows.append({"period": period, "year": year, "split": split, "model": model,
                                 "reference_source": reference, "post_publication_2025": year == 2025,
                                 "prediction_cache": prediction_cache.name,
                                 "weight_effective_n": float(selected_weights["conformal"].sum() ** 2 /
                                                             np.square(selected_weights["conformal"]).sum()),
                                 **score})

    output = AUDIT_RESULTS / "tables"
    detailed = pd.DataFrame(rows)
    detailed.to_csv(output / "density_reference_paired.csv", index=False)
    measures = ["coverage", "fatal_coverage", "macro_fatal_department_coverage", "mean_size", "singleton_rate"]
    summary = detailed.groupby(["period", "reference_source"])[measures + ["weight_effective_n"]].mean().reset_index()
    summary.to_csv(output / "density_reference_summary.csv", index=False)

    audit = pd.concat([read_audit_metrics("development"), read_audit_metrics("corrected_2025")])
    audit = audit[audit.method == "source_weighted_aligned"]
    tuning = detailed[detailed.reference_source == "tuning"]
    matched = tuning.merge(audit, on=["year", "split", "model"], suffixes=("_paired", "_audit"))
    for measure in measures:
        np.testing.assert_allclose(matched[measure + "_paired"], matched[measure + "_audit"], rtol=0, atol=1e-15)

    comparisons = []
    for period, original_directory in [("development", "development"), ("corrected_2025", "final")]:
        original = pd.read_csv(BASE / "results" / original_directory / "metrics.csv")
        original = original[original.method == "source_weighted"].set_index(["year", "split", "model"])
        current = detailed[detailed.period == period].set_index(["year", "split", "model", "reference_source"])
        for measure in ["coverage", "fatal_coverage", "mean_size", "singleton_rate"]:
            old = original[measure].mean()
            fit = current.xs("fit", level="reference_source")[measure].mean()
            tuning_value = current.xs("tuning", level="reference_source")[measure].mean()
            comparisons.append({"period": period, "measure": measure,
                                "published_fit_python_3_13": old,
                                "fit_python_3_14_same_predictions": fit,
                                "tuning_python_3_14_same_predictions": tuning_value,
                                "reference_effect_tuning_minus_fit": tuning_value - fit,
                                "software_and_compatibility_effect_fit": fit - old})
    pd.DataFrame(comparisons).to_csv(output / "density_reference_versions.csv", index=False)
    write_json(AUDIT_RESULTS / "density_reference_execution.json", {
        "completed_utc": datetime.now(timezone.utc).isoformat(), "status_2025": "analyse postérieure",
        "prediction_probabilities": "caches inchangés de l'audit", "n_jobs": 1,
        "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
        "sklearn": sklearn.__version__, "fingerprint": comparison_fingerprint(),
        "tuning_matches_published_audit": True})


if __name__ == "__main__":
    run()
