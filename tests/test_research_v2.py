"""Contrôles des frontières statistiques et du budget de calibration."""
import itertools
import unittest

import numpy as np
import pandas as pd

from research_v2.conformal import allocate, prediction_sets, quantile, quotas, weighted_sets
from research_v2.data import accident_labels, hash_fraction, labels


class ResearchV2Tests(unittest.TestCase):
    def test_unknown_injury_is_not_negative(self):
        u = pd.DataFrame({"Num_Acc": ["a", "a", "b", "b", "c", "d"],
                          "grav": ["2", "-1", "1", "-1", "4", "9"]})
        self.assertEqual(accident_labels(u, pd.Index(list("abcde"))).tolist(), [1, -1, 0, -1, -1])

    def test_quantile_small_cells_and_ties(self):
        self.assertTrue(np.isinf(quantile([])))
        self.assertTrue(np.isinf(quantile(np.arange(8))))
        self.assertEqual(quantile(np.arange(9)), 8)
        self.assertTrue(np.isinf(quantile(np.arange(18), .05)))
        self.assertEqual(quantile(np.arange(19), .05), 18)
        self.assertEqual(quantile(np.ones(100)), 1)

    def test_unseen_class_included_and_order_invariant(self):
        p, y = np.linspace(.01, .15, 30), np.zeros(30, dtype=int)
        sets, _ = prediction_sets(p, y, [.1, .95], mode="class")
        self.assertTrue(sets[:, 1].all())
        other, _ = prediction_sets(p[::-1], y[::-1], [.1, .95], mode="class")
        np.testing.assert_array_equal(sets, other)
        groups, _ = prediction_sets(p, y, [.1, .95], mode="group_class", cal_g=["A"] * 30, test_g=["Z", "Z"])
        self.assertTrue(groups.all())

    def test_weighted_equal_weights_equal_standard(self):
        rng = np.random.default_rng(1)
        p, y, test = rng.random(99), rng.integers(2, size=99), rng.random(30)
        actual = weighted_sets(p, y, test, np.ones(99), np.ones(30))
        expected, _ = prediction_sets(p, y, test)
        np.testing.assert_array_equal(actual, expected)
        inflated = weighted_sets(p, y, test, np.ones(99), np.full(30, 1000))
        self.assertTrue(inflated.all())

    def test_integer_allocation_is_exact_for_surrogate(self):
        cap, a, budget = np.array([4, 7, 5]), np.array([2., 20., 5.]), 10
        n = quotas(cap, budget, a, variance_objective=True)
        optimum = min(np.sum(a / np.array(v)) for v in itertools.product(range(1, 5), range(1, 8), range(1, 6)) if sum(v) == budget)
        self.assertAlmostEqual(np.sum(a / n), optimum)
        self.assertEqual(int(quotas(cap, 16, [1, 2, 3]).sum()), 16)

    def test_pilot_is_paid_and_independent_of_calibration(self):
        g = np.repeat(["A", "B", "C"], [12, 80, 90])
        y = np.arange(len(g)) % 17 == 0
        for policy in ["uniform", "proportional", "pilot_variance"]:
            calls = []
            def oracle(indices):
                calls.extend(indices.tolist())
                return y[indices].astype(int)
            chosen, yc, pilot, allocation = allocate(g, 100, policy, 7, oracle, .05)
            self.assertEqual(len(calls), 100)
            self.assertEqual(len(set(calls)), 100)
            self.assertFalse(set(chosen) & set(pilot))
            self.assertEqual(sum(q["quota"] + q["pilot_n"] for q in allocation), 100)
            np.testing.assert_array_equal(yc, y[chosen])

    def test_hash_partition_stable_under_reordering(self):
        ids = np.array(["2025:a", "2025:b", "2025:c"])
        np.testing.assert_array_equal(hash_fraction(ids, "s")[::-1], hash_fraction(ids[::-1], "s"))

    def test_no_identifier_as_model_feature(self):
        from research_v2.data import CHAR, ROAD
        self.assertFalse((set(CHAR) | set(ROAD)) & {"grav", "dep", "Num_Acc"})
        self.assertNotIn("col", CHAR)


if __name__ == "__main__":
    unittest.main()
