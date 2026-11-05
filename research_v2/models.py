"""Deux prédicteurs fixes, calibration de Platt et rapport de densités estimé."""
import warnings

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def pipeline(x, model, cfg):
    categorical = x.select_dtypes(include="object").columns.tolist()
    numerical = [c for c in x if c not in categorical]
    transform = ColumnTransformer([
        ("numerique", Pipeline([("imputation", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
                                 ("echelle", StandardScaler())]), numerical),
        ("categorie", Pipeline([("imputation", SimpleImputer(strategy="constant", fill_value="inconnu")),
                                 ("encodage", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), categorical)
    ], n_jobs=1)
    if model == "logistic":
        estimator = LogisticRegression(C=cfg["logistic_C"], max_iter=cfg["logistic_max_iter"], n_jobs=1)
    elif model == "hist_gradient_boosting":
        estimator = HistGradientBoostingClassifier(max_iter=cfg["boosting_max_iter"],
                    max_leaf_nodes=cfg["boosting_max_leaf_nodes"], learning_rate=cfg["boosting_learning_rate"],
                    min_samples_leaf=cfg["boosting_min_samples_leaf"], l2_regularization=cfg["boosting_l2"],
                    early_stopping=False, random_state=cfg["model_seed"])
    else:
        raise ValueError(model)
    return Pipeline([("preparation", transform), ("modele", estimator)])


def logit(p):
    p = np.clip(p, 1e-8, 1 - 1e-8)
    return np.log(p / (1 - p)).reshape(-1, 1)


def fit_predict(frames, yfit, yprob, model, cfg):
    estimator = pipeline(frames["fit"], model, cfg)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        estimator.fit(frames["fit"], yfit)
        platt = LogisticRegression(C=1e6, max_iter=1000, n_jobs=1)
        platt.fit(logit(estimator.predict_proba(frames["probability"])[:, 1]), yprob)
    predictions = {name: platt.predict_proba(logit(estimator.predict_proba(frame)[:, 1]))[:, 1]
                   for name, frame in frames.items() if name != "fit"}
    return estimator, predictions


def density_weights(estimator, frames, cfg):
    """Régression logistique de domaine équilibrée ; poids tronqués, garantie non exacte."""
    source = frames["fit"].sample(n=min(len(frames["fit"]), cfg["domain_source_limit"]), random_state=cfg["model_seed"])
    both = pd.concat([source, frames["adaptation"]])
    domain = np.r_[np.zeros(len(source)), np.ones(len(frames["adaptation"]))]
    transform = estimator.named_steps["preparation"]
    classifier = LogisticRegression(C=.1, max_iter=1500, class_weight="balanced", n_jobs=1)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        classifier.fit(transform.transform(both), domain)
    output = {}
    for name in ["conformal", "test"]:
        p = np.clip(classifier.predict_proba(transform.transform(frames[name]))[:, 1], 1e-6, 1 - 1e-6)
        output[name] = np.clip(p / (1 - p), *cfg["domain_weight_clip"])
    return output
