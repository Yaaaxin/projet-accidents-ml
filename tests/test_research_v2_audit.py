"""Tests de non-régression propres à l'amendement d'audit."""
import unittest

import numpy as np
import pandas as pd

from research_v2.audit import density_weights_aligned, enhanced_evaluate, expected_shortfall
from research_v2.audit_simulation import condition_parameters, true_rate_allocation


class _IdentityPreparation:
    def transform(self, frame):
        return frame.to_numpy()


class _Estimator:
    named_steps = {"preparation": _IdentityPreparation()}


class ResearchV2AuditTests(unittest.TestCase):
    def test_density_estimation_uses_independent_aligned_source(self):
        rng = np.random.default_rng(4)
        frames = {
            "fit": pd.DataFrame(rng.normal(99, 1, (20, 2))),
            "tuning": pd.DataFrame(rng.normal(0, 1, (80, 2))),
            "adaptation": pd.DataFrame(rng.normal(.4, 1, (90, 2))),
            "conformal": pd.DataFrame(rng.normal(0, 1, (60, 2))),
            "test": pd.DataFrame(rng.normal(.4, 1, (70, 2))),
        }
        cfg = {"domain_source_limit": 100, "model_seed": 3, "domain_weight_clip": [.1, 10.]}
        weights, audit = density_weights_aligned(_Estimator(), frames, cfg)
        self.assertEqual(audit["source_role"], "tuning")
        self.assertEqual(audit["source_calibration_overlap"], 0)
        self.assertEqual(len(weights["conformal"]), 60)
        self.assertTrue(np.isfinite(weights["test"]).all())
        self.assertTrue((weights["conformal"] > 0).all())

    def test_macro_fatal_coverage_weights_departments_equally(self):
        y = np.array([1, 0, 0, 1, 1, 0])
        p = np.full(len(y), .2)
        sets = np.ones((len(y), 2), dtype=bool)
        sets[0, 1] = False
        score, _ = enhanced_evaluate(y, p, sets, np.array(["A", "A", "A", "B", "B", "B"]), 0)
        self.assertEqual(score["fatal_coverage"], 2 / 3)
        self.assertEqual(score["macro_fatal_department_coverage"], .5)

    def test_nine_fatal_scores_are_needed_at_alpha_point_one(self):
        self.assertEqual(expected_shortfall(8, .9), 1.0)
        self.assertAlmostEqual(expected_shortfall(9, 1.0), 0.0)

    def test_simulation_separates_shared_and_changed_effects(self):
        shared = condition_parameters("shared_region_effect", np.random.default_rng(1), 12)
        changed = condition_parameters("changed_region_effect", np.random.default_rng(1), 12)
        np.testing.assert_array_equal(shared["adapt_effect"], shared["test_effect"])
        self.assertFalse(np.array_equal(changed["adapt_effect"], changed["test_effect"]))

    def test_true_oracle_pays_or_avoids_pilot_as_declared(self):
        groups = np.repeat(np.arange(12).astype(str), 100)
        rates = {group: .01 + .002 * int(group) for group in np.unique(groups)}
        selected, pilot, allocation = true_rate_allocation(
            groups, rates, 120, "oracle_true_variance_costed", 9, 5)
        self.assertEqual(len(selected) + len(pilot), 120)
        self.assertEqual(len(pilot), 60)
        self.assertFalse(set(selected) & set(pilot))
        selected, pilot, allocation = true_rate_allocation(
            groups, rates, 120, "oracle_true_variance", 9, 5)
        self.assertEqual(len(selected), 120)
        self.assertEqual(len(pilot), 0)
        self.assertEqual(sum(allocation.values()), 120)


if __name__ == "__main__":
    unittest.main()
