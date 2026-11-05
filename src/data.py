"""Nettoyage BAAC et représentation symétrique d'un accident, sans fit global."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CHAR_CATEGORIES = {
    "lum": [1, 2, 3, 4, 5],
    "atm": list(range(1, 10)),
    "col": list(range(1, 8)),
}
ROAD_CATEGORIES = {
    "catr": [1, 2, 3, 4, 5, 6, 7, 9],
    "circ": [1, 2, 3, 4],
    "surf": list(range(1, 10)),
    "plan": [1, 2, 3, 4],
    "infra": list(range(10)),
    "situ": [0, 1, 2, 3, 4, 5, 6, 8],
}
CHAR_COLUMNS = ["Num_Acc", "agg", "dep", "an", "jour", "mois", "hrmn", *CHAR_CATEGORIES]
ROAD_COLUMNS = ["Num_Acc", "vma", "nbv", *ROAD_CATEGORIES]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_raw(data_dir=ROOT / "data", verify_hashes=True):
    data_dir = Path(data_dir)
    manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
    tables = []
    for record, columns in zip(manifest["files"], [CHAR_COLUMNS, ROAD_COLUMNS]):
        path = data_dir / Path(record["path"]).name
        if verify_hashes and sha256(path) != record["sha256"]:
            raise ValueError(f"SHA-256 inattendu : {path.name}. Vérifier la provenance.")
        tables.append(pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str,
                                  keep_default_na=False, usecols=columns))
    return tables


def numeric(series):
    return pd.to_numeric(series.astype(str).str.strip(), errors="coerce")


def category(series, allowed):
    values = numeric(series)
    return values.where(values.isin(allowed))


def road_numeric(series, name):
    values = numeric(series)
    if name == "vma":
        valid = values.gt(0) & values.le(130)
    elif name == "nbv":
        valid = values.ge(1) & values.le(20) & values.eq(values.round())
    else:
        raise ValueError(name)
    return values.where(valid)


def validate_raw(caract, lieux):
    for table, required in [(caract, CHAR_COLUMNS), (lieux, ROAD_COLUMNS)]:
        missing = set(required) - set(table)
        if missing:
            raise ValueError(f"Colonnes absentes : {sorted(missing)}")
        if table["Num_Acc"].isna().any() or table["Num_Acc"].astype(str).str.strip().eq("").any():
            raise ValueError("Identifiant d'accident manquant")
    if caract["Num_Acc"].duplicated().any():
        raise ValueError("CARACT doit avoir exactement une ligne par accident")
    if set(caract["Num_Acc"]) != set(lieux["Num_Acc"]):
        raise ValueError("Les ensembles d'accidents CARACT/LIEUX diffèrent")
    if not numeric(caract["agg"]).isin([1, 2]).all():
        raise ValueError("Cible agg invalide : ne pas convertir une valeur inconnue en 0")
    if not numeric(caract["an"]).eq(2024).all():
        raise ValueError("Cette étude est fixée à BAAC 2024")
    if caract["dep"].isna().any() or caract["dep"].astype(str).str.strip().isin(["", "-1"]).any():
        raise ValueError("Département absent")


def build_accidents(caract, lieux):
    """Une ligne par accident. Aucun remplissage appris sur les données complètes."""
    validate_raw(caract, lieux)
    c = caract.set_index("Num_Acc").sort_index()
    result = pd.DataFrame(index=c.index)
    result["target"] = numeric(c["agg"]).eq(2).astype(int)
    result["dep"] = c["dep"].str.strip()
    missing_counts = {}
    for name, allowed in CHAR_CATEGORIES.items():
        values = category(c[name], allowed)
        missing_counts[name] = int(values.isna().sum())
        result[name] = values.map(lambda v: str(int(v)) if pd.notna(v) else np.nan)

    date = pd.to_datetime(pd.DataFrame({"year": numeric(c["an"]),
                                       "month": numeric(c["mois"]),
                                       "day": numeric(c["jour"])}), errors="coerce")
    time_parts = c["hrmn"].str.strip().str.extract(r"^(\d{1,2}):(\d{2})$")
    hour, minute = numeric(time_parts[0]), numeric(time_parts[1])
    hour_value = (hour + minute / 60).where(hour.between(0, 23) & minute.between(0, 59))
    for name, values, period in [("hour", hour_value, 24),
                                 ("month", date.dt.month - 1, 12),
                                 ("day", date.dt.day - 1, 31)]:
        result[name + "_sin"] = np.sin(2 * np.pi * values / period)
        result[name + "_cos"] = np.cos(2 * np.pi * values / period)
    result["weekday"] = date.dt.dayofweek.map(lambda v: str(int(v)) if pd.notna(v) else np.nan)

    ids = lieux["Num_Acc"]
    multiplicity = ids.value_counts()
    heterogeneity = {}
    for name, allowed in ROAD_CATEGORIES.items():
        values = category(lieux[name], allowed)
        missing_counts[name] = int(values.isna().sum())
        heterogeneity[name] = int(values.groupby(ids).nunique().gt(1).sum())
        for value in allowed:
            result[f"{name}__p{value}"] = values.eq(value).groupby(ids).mean()
        result[f"{name}__missing"] = values.isna().groupby(ids).mean()
    for name in ["vma", "nbv"]:
        values = road_numeric(lieux[name], name)
        missing_counts[name] = int(values.isna().sum())
        heterogeneity[name] = int(values.groupby(ids).nunique().gt(1).sum())
        stats = values.groupby(ids).agg(["median", "min", "max"])
        for stat in stats:
            result[f"{name}__{stat}"] = stats[stat]
        result[f"{name}__missing"] = values.isna().groupby(ids).mean()

    features = [name for name in result if name not in ["target", "dep"]]
    road_only = [name for name in features if name.startswith(("vma__", "catr__"))]
    feature_sets = {"all": features, "road_only": road_only,
                    "without_road": [name for name in features if name not in road_only]}
    audit = {
        "accidents": len(c), "lieux_rows": len(lieux),
        "accidents_with_multiple_lieux": int(multiplicity.gt(1).sum()),
        "lieux_multiplicity": {str(k): int(v) for k, v in multiplicity.value_counts().sort_index().items()},
        "target_counts_accidents": {str(k): int(v) for k, v in result.target.value_counts().items()},
        "unknown_or_invalid_by_source_column": missing_counts,
        "accidents_with_conflicting_known_lieu_values": heterogeneity,
        "invalid_dates": int(date.isna().sum()), "invalid_times": int(hour_value.isna().sum()),
        "vma_above_130": int(numeric(lieux.vma).gt(130).sum()),
        "feature_count": {k: len(v) for k, v in feature_sets.items()},
        "weight_per_accident": 1,
    }
    return result, feature_sets, audit
