import json
import unittest

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from src.data import ROOT, build_accidents, category, load_raw, road_numeric
from src.experiment import bootstrap_scores, metric_values, pipeline_for, split_accidents


def fixture():
    caract = pd.DataFrame([
        {"Num_Acc": str(i), "agg": str(1 + i % 2), "dep": "07" if i < 4 else "75",
         "an": "2024", "jour": "15", "mois": "2", "hrmn": "23:30",
         "lum": "1", "atm": "1", "col": "2"} for i in range(12)
    ])
    lieux = pd.DataFrame([
        {"Num_Acc": str(i), "vma": "30", "nbv": "2", "catr": "4", "circ": "2",
         "surf": "1", "plan": "1", "infra": "0", "situ": "1"} for i in range(12)
    ])
    extra = lieux.iloc[[0]].copy()
    extra.loc[:, ["vma", "catr"]] = ["70", "3"]
    return caract, pd.concat([lieux, extra], ignore_index=True)


class MethodTests(unittest.TestCase):
    def test_missing_codes_and_valid_zero(self):
        values = pd.Series([" -1", "", ".", "#VALEURMULTI", "0", "5"])
        self.assertEqual(category(values, list(range(10))).isna().tolist(), [True] * 4 + [False, False])
        self.assertTrue(road_numeric(pd.Series(["900", "-1", "0"]), "vma").isna().all())
        self.assertTrue(road_numeric(pd.Series(["2.5", "#VALEURMULTI", "0"]), "nbv").isna().all())

    def test_aggregation_equal_units_and_order_invariance(self):
        caract, lieux = fixture()
        result, sets, _ = build_accidents(caract, lieux)
        shuffled, _, _ = build_accidents(caract.sample(frac=1, random_state=3), lieux.sample(frac=1, random_state=4))
        assert_frame_equal(result, shuffled)
        self.assertEqual(len(result), len(caract))
        self.assertEqual(result.loc["0", "vma__median"], 50)
        self.assertEqual(result.loc["0", "vma__min"], 30)
        self.assertEqual(result.loc["0", "catr__p3"], 0.5)
        self.assertEqual(result.loc["0", "catr__p4"], 0.5)
        self.assertFalse(set(sets["all"]) & {"agg", "Num_Acc", "dep", "target"})
        self.assertFalse(any(c.startswith(("vma__", "catr__")) for c in sets["without_road"]))
        self.assertEqual(set(sets["all"]), set(sets["without_road"]) | set(sets["road_only"]))

    def test_cleaning_reaches_model_and_unseen_category(self):
        caract, lieux = fixture()
        lieux.loc[lieux.Num_Acc.eq("1"), "vma"] = " -1"
        caract.loc[caract.Num_Acc.eq("1"), "hrmn"] = "25:10"
        data, sets, _ = build_accidents(caract, lieux)
        self.assertTrue(pd.isna(data.loc["1", "vma__median"]))
        self.assertTrue(pd.isna(data.loc["1", "hour_sin"]))
        config = json.loads((ROOT / "config/experiment.json").read_text())
        train = data.loc[["0", "1", "2", "3"], sets["all"]]
        model = pipeline_for(train, "logistic", config)
        model.fit(train, data.loc[train.index, "target"])
        imputer = model.named_steps["preprocess"].named_transformers_["numeric"].named_steps["impute"]
        before = imputer.statistics_.copy()
        test = data.loc[["4"], sets["all"]].copy()
        test.loc[:, "lum"] = "unseen"
        test.loc[:, "vma__median"] = 100000
        self.assertTrue(np.isfinite(model.predict_proba(test)).all())
        np.testing.assert_array_equal(before, imputer.statistics_)

    def test_invalid_label_and_duplicate_accident_rejected(self):
        caract, lieux = fixture()
        with self.assertRaises(ValueError):
            build_accidents(pd.concat([caract, caract.iloc[[0]]]), lieux)
        caract.loc[0, "agg"] = "-1"
        with self.assertRaises(ValueError):
            build_accidents(caract, lieux)

    def test_group_disjointness(self):
        data, _, _ = build_accidents(*fixture())
        config = {"held_out_departments": ["07"], "test_fraction": 0.25, "random_seed": 42}
        for name, (train, test) in split_accidents(data, config).items():
            self.assertFalse(set(train) & set(test))
            if name == "geographic":
                self.assertFalse(set(data.loc[train, "dep"]) & set(data.loc[test, "dep"]))

    def test_bootstrap_matches_sklearn_with_ties_and_is_paired(self):
        y = np.array([0, 1] * 10)
        p = np.array([0.2, 0.7, 0.5, 0.5, 0.7] * 4)
        actual, skipped = bootstrap_scores(y, [p, p], 30, 73)
        rng = np.random.default_rng(73)
        expected = []
        for _ in range(30):
            index = rng.integers(0, len(y), len(y))
            if len(np.unique(y[index])) == 2:
                expected.append(metric_values(y[index], p[index]))
        np.testing.assert_allclose(actual[0], expected)
        np.testing.assert_array_equal(actual[0], actual[1])
        self.assertEqual(actual.shape[1] + skipped, 30)

    def test_real_data_hashes_aggregation_and_splits(self):
        if not (ROOT / "data/caract_2024.csv").exists():
            self.skipTest("Données locales non téléchargées")
        data, _, audit = build_accidents(*load_raw())
        self.assertEqual(audit["accidents"], 54402)
        self.assertEqual(audit["lieux_rows"], 70248)
        self.assertEqual(audit["accidents_with_multiple_lieux"], 15645)
        config = json.loads((ROOT / "config/experiment.json").read_text())
        for train, test in split_accidents(data, config).values():
            self.assertFalse(set(train) & set(test))


if __name__ == "__main__":
    unittest.main()
