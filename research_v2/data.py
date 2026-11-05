"""Adaptation annuelle BAAC, unité accident et séparation préalable sans étiquettes."""
import argparse
import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src.data import category, numeric, road_numeric
from .download import BASE, RAW, ROOT, digest

PRIVATE = BASE / "private"
RESULTS = BASE / "results"
CHAR = {"lum": list(range(1, 6)), "atm": list(range(1, 10)),
        "int": list(range(1, 10)), "agg": [1, 2]}
ROAD = {"catr": [1, 2, 3, 4, 5, 6, 7, 9], "circ": [1, 2, 3, 4],
        "surf": list(range(1, 10)), "plan": [1, 2, 3, 4], "infra": list(range(10))}
ADAPTERS = {year: {"characteristic_id": "Accident_Id" if year == 2022 else "Num_Acc",
                   "has_user_id": year >= 2021, "fatal_code": 2,
                   "known_injury_codes": [1, 2, 3, 4], "separator": ";"}
            for year in range(2019, 2026)}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def hash_fraction(ids, salt):
    return np.array([int(hashlib.sha256(f"{salt}:{i}".encode()).hexdigest()[:16], 16) / 2**64 for i in ids])


def ids_hash(ids):
    return hashlib.sha256("\n".join(sorted(map(str, ids))).encode()).hexdigest()


def table(year, kind, columns=None):
    record = next(r for r in json.loads((BASE / "data_manifest.json").read_text(encoding="utf-8"))["files"]
                  if r.get("year") == year and r["table"] == kind)
    path = ROOT / record["path"]
    if digest(path) != record["sha256"]:
        raise ValueError(f"Intégrité non vérifiée : {path.name}")
    frame = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8-sig", keep_default_na=False, usecols=columns)
    if kind == "caracteristiques":
        frame = frame.rename(columns={ADAPTERS[year]["characteristic_id"]: "Num_Acc"})
    if "Num_Acc" not in frame or frame.Num_Acc.str.strip().eq("").any():
        raise ValueError("Identifiant absent")
    frame.Num_Acc = frame.Num_Acc.str.strip()
    return frame


def accident_labels(users, ids):
    """1 : décès observé ; 0 : tous les usagers connus non tués ; -1 : indéterminé."""
    grav = numeric(users.grav)
    fatal = grav.eq(2).groupby(users.Num_Acc).any().reindex(ids, fill_value=False)
    known = grav.isin([1, 2, 3, 4]).groupby(users.Num_Acc).all().reindex(ids, fill_value=False)
    return pd.Series(np.where(fatal, 1, np.where(known, 0, -1)), index=ids, name="target", dtype=int)


def labels(year, selected_ids=None):
    if year == 2025 and not (BASE / "freeze.json").exists():
        raise RuntimeError("Étiquettes 2025 verrouillées avant le gel du protocole")
    c = table(year, "caracteristiques", [ADAPTERS[year]["characteristic_id"]])
    u = table(year, "usagers", ["Num_Acc", "grav"])
    if not set(u.Num_Acc).issubset(set(c.Num_Acc)):
        raise ValueError("Usager sans accident CARACT")
    ids = pd.Index(c.Num_Acc if selected_ids is None else [str(i).split(":", 1)[-1] for i in selected_ids])
    if not set(ids).issubset(set(c.Num_Acc)):
        raise ValueError("Demande d'étiquettes hors année")
    u = u[u.Num_Acc.isin(ids)]
    result = accident_labels(u, ids)
    result.index = str(year) + ":" + result.index
    return result


def build_features(year):
    c, roads = table(year, "caracteristiques"), table(year, "lieux")
    if c.Num_Acc.duplicated().any() or not numeric(c.an).eq(year).all():
        raise ValueError("Unicité ou année CARACT incorrecte")
    if set(c.Num_Acc) != set(roads.Num_Acc):
        raise ValueError("Les accidents CARACT/LIEUX diffèrent")
    c = c.set_index("Num_Acc").sort_index()
    x = pd.DataFrame(index=c.index)
    x["dep"] = c.dep.str.strip().str.upper().map(lambda v: v.zfill(2) if v.isdigit() else v)
    if x.dep.isin(["", "-1"]).any():
        raise ValueError("Département absent")
    x["year"] = year
    invalid = {}
    observed = {}
    for name, allowed in CHAR.items():
        v = category(c[name], allowed)
        invalid[name] = int(v.isna().sum())
        observed[name] = c[name].value_counts().to_dict()
        x[name] = v.map(lambda a: str(int(a)) if pd.notna(a) else np.nan)
    date = pd.to_datetime(dict(year=numeric(c.an), month=numeric(c.mois), day=numeric(c.jour)), errors="coerce")
    parts = c.hrmn.str.strip().str.extract(r"^(\d{1,2}):(\d{2})$")
    h, m = numeric(parts[0]), numeric(parts[1])
    hour = (h + m / 60).where(h.between(0, 23) & m.between(0, 59))
    for name, v, period in [("heure", hour, 24), ("mois", date.dt.month - 1, 12),
                            ("semaine", date.dt.dayofweek, 7)]:
        x[name + "_sin"] = np.sin(2 * np.pi * v / period)
        x[name + "_cos"] = np.cos(2 * np.pi * v / period)
    rid = roads.Num_Acc
    for name, allowed in ROAD.items():
        v = category(roads[name], allowed)
        invalid[name] = int(v.isna().sum())
        observed[name] = roads[name].value_counts().to_dict()
        for code in allowed:
            x[f"{name}_p{code}"] = v.eq(code).groupby(rid).mean()
        x[name + "_inconnu"] = v.isna().groupby(rid).mean()
    for name in ["vma", "nbv"]:
        v = road_numeric(roads[name], name)
        invalid[name] = int(v.isna().sum())
        for stat in ["median", "min", "max"]:
            x[name + "_" + stat] = v.groupby(rid).agg(stat)
        x[name + "_inconnu"] = v.isna().groupby(rid).mean()
    x.index = str(year) + ":" + x.index
    user_header = pd.read_csv(RAW / f"usagers-{year}.csv", sep=";", nrows=0).columns.tolist()
    if ("id_usager" in user_header) != ADAPTERS[year]["has_user_id"]:
        raise ValueError("Changement de schéma USAGERS non adapté")
    audit = {"year": year, "accidents": len(c), "road_rows": len(roads),
             "multiple_roads": int(rid.value_counts().gt(1).sum()),
             "invalid_dates": int(date.isna().sum()), "invalid_times": int(hour.isna().sum()),
             "unknown_or_invalid": invalid, "observed_category_codes": observed,
             "adapter": ADAPTERS[year], "user_columns": user_header,
             "characteristic_columns_after_adapter": c.reset_index().columns.tolist(),
             "road_columns": roads.columns.tolist(), "feature_count": x.shape[1] - 2}
    return x, audit


def features(year):
    return pd.read_pickle(PRIVATE / f"features-{year}.pkl")


def prepare():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    audits = []
    for year in range(2019, 2026):
        x, audit = build_features(year)
        x.to_pickle(PRIVATE / f"features-{year}.pkl")
        if year < 2025:
            y = labels(year)
            audit["label_counts"] = {str(k): int(v) for k, v in y.value_counts().items()}
            u = table(year, "usagers")
            audit["user_rows"] = len(u)
            audit["grav_codes"] = u.grav.value_counts().to_dict()
            audit["accidents_without_users"] = int(len(set(x.index.str.split(":").str[-1]) - set(u.Num_Acc)))
        else:
            audit["labels"] = "non lues avant gel"
        audits.append(audit)
        print(year, audit["accidents"], audit.get("label_counts", "étiquettes verrouillées"), flush=True)
    write_json(RESULTS / "data_audit_before_freeze.json", audits)
    deps = sorted(features(2019).dep.unique())
    splits = {str(seed): sorted(sorted(deps, key=lambda g: hashlib.sha256(f"geographie:{seed}:{g}".encode()).hexdigest())[:20])
              for seed in [17, 43, 89]}
    partitions = {}
    feasibility = []
    for year in range(2022, 2026):
        x = features(year)
        role = np.where(hash_fraction(x.index, "adaptation-v2-20261105") < .5, "adaptation", "test")
        pd.DataFrame({"role": role}, index=x.index).to_csv(PRIVATE / f"partition-{year}.csv")
        partitions[str(year)] = {r: {"n": int(sum(role == r)), "ids_sha256": ids_hash(x.index[role == r])}
                                 for r in ["adaptation", "test"]}
        for split, held in splits.items():
            mask = x.dep.isin(held) & (role == "adaptation")
            feasibility.append({"year": year, "split": split, "adaptation_n": int(mask.sum()),
                                "departments_n": int(x.loc[mask, "dep"].nunique()),
                                "min_department_n": int(x.loc[mask, "dep"].value_counts().min())})
    receipt = {"created_utc": datetime.now(timezone.utc).isoformat(), "salt": "adaptation-v2-20261105",
               "labels_2025_read": False, "held_departments": splits, "partitions": partitions}
    target = BASE / "partitions.json"
    if target.exists():
        old = json.loads(target.read_text(encoding="utf-8"))
        if old["partitions"] != partitions or old["held_departments"] != splits:
            raise ValueError("La partition préexistante a changé")
    else:
        write_json(target, receipt)
    pd.DataFrame(feasibility).to_csv(RESULTS / "feasibility.csv", index=False)
    print(pd.DataFrame(feasibility).to_string(index=False))


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    prepare()
