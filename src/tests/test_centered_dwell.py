"""Tests for continuous centered-observation dwell evidence."""

import math
import unittest

from src.badger_core.centered_dwell import CenteredDwell, CenteredDwellResult
from src.badger_core.observation import Observation, ObservationStatus


class TestCenteredDwell(unittest.TestCase):
    def observation(self, capture_time_s: float, **changes: object) -> Observation:
        values: dict[str, object] = {
            "target_id": 7,
            "capture_time_s": capture_time_s,
            "received_time_s": capture_time_s,
            "x_error_m": 0.06,
            "y_error_m": -0.04,
            "valid_pose": True,
            "calibration_version": "v1",
        }
        values.update(changes)
        return Observation(**values)  # type: ignore[arg-type]

    def test_first_centered_sample_starts_a_run(self) -> None:
        dwell = CenteredDwell(expected_target_id=7)

        result = dwell.evaluate(self.observation(10.0), now_s=10.0)

        self.assertEqual(result.decision.status, ObservationStatus.CENTERED)
        self.assertEqual(result.centered_duration_s, 0.0)
        self.assertFalse(result.dwell_met)

    def test_continuous_samples_cross_the_dwell_threshold(self) -> None:
        dwell = CenteredDwell(expected_target_id=7, required_dwell_s=0.4, max_gap_s=0.3)

        first = dwell.evaluate(self.observation(10.0), now_s=10.0)
        middle = dwell.evaluate(self.observation(10.2), now_s=10.2)
        threshold = dwell.evaluate(self.observation(10.4), now_s=10.4)

        self.assertFalse(first.dwell_met)
        self.assertAlmostEqual(middle.centered_duration_s, 0.2)
        self.assertFalse(middle.dwell_met)
        self.assertAlmostEqual(threshold.centered_duration_s, 0.4)
        self.assertTrue(threshold.dwell_met)

    def test_exact_gap_and_dwell_boundaries_continue_and_pass(self) -> None:
        dwell = CenteredDwell(expected_target_id=7, required_dwell_s=0.3, max_gap_s=0.3)

        dwell.evaluate(self.observation(10.0), now_s=10.0)
        result = dwell.evaluate(self.observation(10.3), now_s=10.3)

        self.assertAlmostEqual(result.centered_duration_s, 0.3)
        self.assertTrue(result.dwell_met)

    def test_gap_larger_than_limit_restarts_the_run(self) -> None:
        dwell = CenteredDwell(expected_target_id=7, required_dwell_s=0.4, max_gap_s=0.3)

        dwell.evaluate(self.observation(10.0), now_s=10.0)
        result = dwell.evaluate(self.observation(10.31), now_s=10.31)

        self.assertEqual(result.decision.status, ObservationStatus.CENTERED)
        self.assertEqual(result.centered_duration_s, 0.0)
        self.assertFalse(result.dwell_met)

    def test_valid_noncentered_sample_ends_the_run(self) -> None:
        dwell = CenteredDwell(expected_target_id=7, required_dwell_s=0.2, max_gap_s=0.3)

        dwell.evaluate(self.observation(10.0), now_s=10.0)
        noncentered = dwell.evaluate(
            self.observation(10.1, x_error_m=0.2, y_error_m=0.0), now_s=10.1
        )
        restarted = dwell.evaluate(self.observation(10.2), now_s=10.2)

        self.assertEqual(noncentered.decision.status, ObservationStatus.VALID)
        self.assertEqual(noncentered.centered_duration_s, 0.0)
        self.assertFalse(noncentered.dwell_met)
        self.assertEqual(restarted.centered_duration_s, 0.0)

    def test_rejected_or_duplicate_sample_ends_the_run(self) -> None:
        for observation, expected_status in (
            (self.observation(10.0), ObservationStatus.OUT_OF_ORDER),
            (self.observation(10.1, target_id=8), ObservationStatus.WRONG_TARGET),
        ):
            with self.subTest(status=expected_status):
                dwell = CenteredDwell(expected_target_id=7, required_dwell_s=0.1)
                dwell.evaluate(self.observation(10.0), now_s=10.0)

                result = dwell.evaluate(observation, now_s=observation.capture_time_s)

                self.assertEqual(result.decision.status, expected_status)
                self.assertEqual(result.centered_duration_s, 0.0)
                self.assertFalse(result.dwell_met)

    def test_reset_allows_a_new_clock_epoch(self) -> None:
        dwell = CenteredDwell(expected_target_id=7)
        dwell.evaluate(self.observation(10.0), now_s=10.0)
        dwell.reset()

        result = dwell.evaluate(self.observation(10.0), now_s=10.0)

        self.assertEqual(result.decision.status, ObservationStatus.CENTERED)
        self.assertEqual(result.centered_duration_s, 0.0)
        self.assertFalse(result.dwell_met)

    def test_duration_and_gap_settings_must_be_finite_positive_numbers(self) -> None:
        for value in (0, -1, True, math.nan, math.inf):
            with self.subTest(required_dwell_s=value):
                with self.assertRaises(ValueError):
                    CenteredDwell(expected_target_id=7, required_dwell_s=value)
            with self.subTest(max_gap_s=value):
                with self.assertRaises(ValueError):
                    CenteredDwell(expected_target_id=7, max_gap_s=value)

    def test_result_is_frozen_and_has_the_public_contract_shape(self) -> None:
        result = CenteredDwell(expected_target_id=7).evaluate(self.observation(10.0), now_s=10.0)

        self.assertIsInstance(result, CenteredDwellResult)
        self.assertEqual(tuple(result.__dataclass_fields__), (
            "decision", "centered_duration_s", "dwell_met"
        ))
        with self.assertRaises(AttributeError):
            result.dwell_met = True  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
