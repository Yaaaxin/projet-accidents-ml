"""Exécuter les 18 évaluations fixées dans config/experiment.json."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import time
import warnings

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .data import ROOT, build_accidents, load_raw, sha256

METRICS = ["balanced_accuracy", "macro_f1", "roc_auc"]


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def split_accidents(data, config):
    train_ids, test_ids = train_test_split(data.index.to_numpy(), test_size=config["test_fraction"],
                                          stratify=data.target, random_state=config["random_seed"])
    geographic_test = data.dep.isin(config["held_out_departments"])
    if not set(config["held_out_departments"]).issubset(set(data.dep)):
        raise ValueError("Départements réservés absents des données")
    splits = {"random_accident": (np.sort(train_ids), np.sort(test_ids)),
              "geographic": (data.index[~geographic_test].to_numpy(), data.index[geographic_test].to_numpy())}
    for name, (train, test) in splits.items():
        if set(train) & set(test) or len(train) + len(test) != len(data):
            raise ValueError("Découpage accident non disjoint ou incomplet")
        if any(data.loc[ids, "target"].nunique() != 2 for ids in (train, test)):
            raise ValueError("Chaque partie doit contenir les deux classes")
        if name == "geographic" and set(data.loc[train, "dep"]) & set(data.loc[test, "dep"]):
            raise ValueError("Départements non disjoints")
    return splits


def pipeline_for(X, model_name, config):
    cats = [c for c in X if X[c].dtype == object]
    nums = [c for c in X if c not in cats]
    transformers = []
    if nums:
        transformers.append(("numeric", Pipeline([
            ("impute", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            ("scale", StandardScaler()),
        ]), nums))
    if cats:
        transformers.append(("categorical", Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent", keep_empty_features=True)),
            ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), cats))
    preprocess = ColumnTransformer(transformers, remainder="drop")
    if model_name == "majority":
        model = DummyClassifier(strategy="most_frequent")
    elif model_name == "logistic":
        model = LogisticRegression(solver="lbfgs", **config["logistic"])
    elif model_name == "forest":
        model = RandomForestClassifier(random_state=config["model_seed"], **config["forest"])
    else:
        raise ValueError(model_name)
    return Pipeline([("preprocess", preprocess), ("model", model)])


def metric_values(y, probability):
    predicted = probability >= 0.5
    return np.array([balanced_accuracy_score(y, predicted),
                     f1_score(y, predicted, average="macro", zero_division=0),
                     roc_auc_score(y, probability)])


def bootstrap_scores(y, probabilities, repetitions, seed):
    """Bootstrap apparié, un poids multinomial par accident et mêmes tirages partout.

    AUROC pondérée calculée par groupes de scores ex aequo ; évite de trier
    1 000 fois chaque vecteur. Vérifiée contre les métriques sklearn dans les tests.
    """
    y = np.asarray(y, dtype=int)
    prepared = []
    for p in probabilities:
        _, ties = np.unique(p, return_inverse=True)
        prepared.append((2 * y + (np.asarray(p) >= 0.5), ties))
    scores = np.empty((len(prepared), repetitions, 3))
    rng = np.random.default_rng(seed)
    valid = 0
    for _ in range(repetitions):
        weights = np.bincount(rng.integers(0, len(y), len(y)), minlength=len(y))
        positives = weights * y
        negatives = weights * (1 - y)
        if positives.sum() == 0 or negatives.sum() == 0:
            continue
        for j, (cells, ties) in enumerate(prepared):
            tn, fp, fn, tp = np.bincount(cells, weights=weights, minlength=4)
            ba = (tp / (tp + fn) + tn / (tn + fp)) / 2
            macro = (2 * tp / (2 * tp + fp + fn) + 2 * tn / (2 * tn + fp + fn)) / 2
            pos_ties = np.bincount(ties, weights=positives)
            neg_ties = np.bincount(ties, weights=negatives)
            auc = np.sum(pos_ties * (np.cumsum(neg_ties) - neg_ties / 2)) / (positives.sum() * negatives.sum())
            scores[j, valid] = [ba, macro, auc]
        valid += 1
    if valid == 0:
        raise ValueError("Aucun bootstrap avec deux classes")
    return scores[:, :valid], repetitions - valid


def legacy_overlap(caract, lieux):
    joined = caract.merge(lieux, on="Num_Acc", how="left", validate="one_to_many")
    y = joined["agg"].astype(int).eq(2).astype(int)
    train, test = train_test_split(np.arange(len(joined)), test_size=0.2, random_state=42, stratify=y)
    train_ids, test_ids = joined.iloc[train].Num_Acc, joined.iloc[test].Num_Acc
    shared = set(train_ids) & set(test_ids)
    return {
        "train_rows": len(train), "test_rows": len(test), "shared_accidents": len(shared),
        "test_rows_from_seen_accidents": int(test_ids.isin(shared).sum()),
        "test_rows_from_seen_accidents_fraction": float(test_ids.isin(shared).mean()),
        "test_unique_accidents": int(test_ids.nunique()),
        "test_unique_accidents_seen_fraction": len(shared) / test_ids.nunique(),
        "historical_roc_auc_logistic": 0.909273446532967,
        "historical_roc_auc_forest": 0.9686662666488022,
        "status": "Scores lus dans le notebook initial ; non validés par le protocole corrigé.",
    }


def run(output=ROOT / "results", config_path=ROOT / "config/experiment.json", repetitions=None):
    started = datetime.now(timezone.utc).isoformat()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    private = output / "private"
    private.mkdir(exist_ok=True)
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if repetitions is not None:
        config["bootstrap_replicates"] = repetitions
    caract, lieux = load_raw()
    data, feature_sets, audit = build_accidents(caract, lieux)
    splits = split_accidents(data, config)
    audit["legacy_split"] = legacy_overlap(caract, lieux)
    audit["feature_sets"] = feature_sets
    write_json(output / "data_audit.json", audit)
    print(f"Données : {len(data)} accidents, {len(lieux)} descriptions de lieux.", flush=True)
    records, differences, split_records = [], [], {}
    for split_name, (train_ids, test_ids) in splits.items():
        train, test = data.loc[train_ids], data.loc[test_ids]
        y_train, y_test = train.target.to_numpy(), test.target.to_numpy()
        split_records[split_name] = {
            "train_accidents": len(train), "test_accidents": len(test), "overlap_accidents": 0,
            "train_positive_fraction": float(train.target.mean()), "test_positive_fraction": float(test.target.mean()),
            "train_departments": sorted(train.dep.unique()), "test_departments": sorted(test.dep.unique()),
            "train_ids_sha256": hashlib.sha256("\n".join(train_ids).encode()).hexdigest(),
            "test_ids_sha256": hashlib.sha256("\n".join(test_ids).encode()).hexdigest(),
        }
        pd.DataFrame({"Num_Acc": data.index, "partition": np.where(data.index.isin(test_ids), "test", "train")}).to_csv(
            private / f"{split_name}_split.csv", index=False)
        predictions = pd.DataFrame({"Num_Acc": test.index, "target": y_test})
        probabilities, current = [], []
        for features_name, columns in feature_sets.items():
            for model_name in ["majority", "logistic", "forest"]:
                begin = time.perf_counter()
                estimator = pipeline_for(train[columns], model_name, config)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    warnings.filterwarnings("error", category=ConvergenceWarning)
                    estimator.fit(train[columns], y_train)
                p = estimator.predict_proba(test[columns])[:, 1]
                values = metric_values(y_test, p)
                matrix = confusion_matrix(y_test, p >= 0.5, labels=[0, 1])
                record = {"split": split_name, "features": features_name, "model": model_name,
                          "n_train": len(train), "n_test": len(test),
                          **dict(zip(METRICS, values.tolist())),
                          **dict(zip(["tn", "fp", "fn", "tp"], matrix.ravel().tolist())),
                          "fit_predict_seconds": time.perf_counter() - begin,
                          "warning_count": len(caught),
                          "iterations": int(estimator.named_steps["model"].n_iter_[0]) if model_name == "logistic" else None}
                if caught:
                    write_json(private / f"{split_name}_{features_name}_{model_name}_warnings.json",
                               [str(w.message) for w in caught])
                current.append(record)
                probabilities.append(p)
                predictions[f"{features_name}__{model_name}"] = p
                print(f"{split_name} / {features_name} / {model_name}: BA={values[0]:.4f}, AUC={values[2]:.4f}", flush=True)
        predictions.to_csv(private / f"{split_name}_predictions.csv", index=False)
        boot, skipped = bootstrap_scores(y_test, probabilities, config["bootstrap_replicates"], config["bootstrap_seed"])
        split_records[split_name]["bootstrap_skipped_single_class"] = skipped
        for i, record in enumerate(current):
            for j, metric in enumerate(METRICS):
                low, high = np.quantile(boot[i, :, j], [0.025, 0.975])
                record[metric + "_low"] = float(low)
                record[metric + "_high"] = float(high)
            records.append(record)
        lookup = {(r["features"], r["model"]): i for i, r in enumerate(current)}
        contrasts = [(f, "forest", f, "logistic") for f in feature_sets]
        contrasts += [("all", m, other, m) for m in ["logistic", "forest"] for other in ["road_only", "without_road"]]
        for fa, ma, fb, mb in contrasts:
            a, b = lookup[fa, ma], lookup[fb, mb]
            for j, metric in enumerate(METRICS):
                low, high = np.quantile(boot[a, :, j] - boot[b, :, j], [0.025, 0.975])
                differences.append({"split": split_name, "comparison": f"{fa}/{ma} - {fb}/{mb}", "metric": metric,
                                    "difference": current[a][metric] - current[b][metric], "low": float(low), "high": float(high)})
        # Sauvegarde à chaque découpage : une interruption ne perd pas les résultats terminés.
        pd.DataFrame(records).to_csv(output / "metrics.csv", index=False)
        pd.DataFrame(differences).to_csv(output / "paired_differences.csv", index=False)
        write_json(output / "splits.json", split_records)
        print(f"{split_name} : métriques et IC sauvegardés.", flush=True)
    metadata = {
        "started_at_utc": started, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "platform": platform.system(),
        "packages": {name: importlib.metadata.version(name) for name in ["numpy", "pandas", "scikit-learn", "matplotlib"]},
        "config": config, "config_sha256": sha256(config_path), "protocol_sha256": sha256(ROOT / "docs/protocol.md"),
        "source_sha256": {p.relative_to(ROOT).as_posix(): sha256(p) for p in sorted((ROOT / "src").glob("*.py"))},
        "data_sha256": {p.name: sha256(p) for p in sorted((ROOT / "data").glob("*.csv"))},
        "completed_evaluations": len(records), "confidence_interval": "95% percentile, accident bootstrap, fitted models fixed",
    }
    write_json(output / "run_metadata.json", metadata)
    return pd.DataFrame(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results")
    parser.add_argument("--bootstrap", type=int, help="Remplace 1000 ; réserver aux vérifications rapides")
    args = parser.parse_args()
    if args.bootstrap is not None and args.bootstrap < 1:
        parser.error("--bootstrap doit être positif")
    run(args.output, repetitions=args.bootstrap)
