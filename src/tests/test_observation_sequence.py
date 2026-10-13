"""Tests for ordering state around the pure observation validator."""

import math
import unittest

from src.badger_core.observation import Observation, ObservationStatus
from src.badger_core.observation_sequence import ObservationSequence


class TestObservationSequence(unittest.TestCase):
    def observation(self, **changes: object) -> Observation:
        values: dict[str, object] = {
            "target_id": 7,
            "capture_time_s": 100.0,
            "received_time_s": 100.0,
            "x_error_m": 0.06,
            "y_error_m": -0.04,
            "valid_pose": True,
            "calibration_version": "v1",
        }
        values.update(changes)
        return Observation(**values)  # type: ignore[arg-type]

    def setUp(self) -> None:
        self.sequence = ObservationSequence(expected_target_id=7)

    def test_first_centered_observation_is_accepted(self) -> None:
        decision = self.sequence.evaluate(self.observation(), now_s=100.0)

        self.assertEqual(decision.status, ObservationStatus.CENTERED)
        self.assertEqual(self.sequence.last_capture_time_s, 100.0)

    def test_duplicate_and_older_observations_are_out_of_order(self) -> None:
        self.sequence.evaluate(self.observation(), now_s=100.0)

        duplicate = self.sequence.evaluate(self.observation(), now_s=100.0)
        older = self.sequence.evaluate(
            self.observation(capture_time_s=99.0, received_time_s=99.0),
            now_s=100.0,
        )

        self.assertEqual(duplicate.status, ObservationStatus.OUT_OF_ORDER)
        self.assertEqual(older.status, ObservationStatus.OUT_OF_ORDER)
        self.assertEqual(self.sequence.last_capture_time_s, 100.0)

    def test_newer_valid_observation_advances_accepted_capture_time(self) -> None:
        first = self.sequence.evaluate(
            self.observation(x_error_m=0.2, y_error_m=0.0), now_s=100.0
        )
        second = self.sequence.evaluate(
            self.observation(capture_time_s=100.01, received_time_s=100.01),
            now_s=100.01,
        )

        self.assertEqual(first.status, ObservationStatus.VALID)
        self.assertEqual(second.status, ObservationStatus.CENTERED)
        self.assertEqual(self.sequence.last_capture_time_s, 100.01)

    def test_nonaccepted_observations_do_not_advance_state(self) -> None:
        self.sequence.evaluate(self.observation(), now_s=100.0)
        rejected_samples = (
            (
                self.observation(capture_time_s=100.01, received_time_s=100.01),
                100.5,
                ObservationStatus.STALE,
            ),
            (
                self.observation(target_id=8, capture_time_s=100.01, received_time_s=100.01),
                100.01,
                ObservationStatus.WRONG_TARGET,
            ),
            (
                self.observation(valid_pose=False, capture_time_s=100.01, received_time_s=100.01),
                100.01,
                ObservationStatus.INVALID_POSE,
            ),
            (
                self.observation(capture_time_s=100.01, received_time_s=100.0),
                100.01,
                ObservationStatus.INVALID_TIME,
            ),
            (
                self.observation(capture_time_s=100.1, received_time_s=100.1),
                100.0,
                ObservationStatus.FUTURE,
            ),
        )

        for observation, now_s, expected_status in rejected_samples:
            with self.subTest(status=expected_status):
                decision = self.sequence.evaluate(observation, now_s=now_s)
                self.assertEqual(decision.status, expected_status)
                self.assertEqual(self.sequence.last_capture_time_s, 100.0)

    def test_reset_allows_a_new_clock_epoch(self) -> None:
        self.sequence.evaluate(self.observation(), now_s=100.0)
        self.sequence.reset()
        decision = self.sequence.evaluate(self.observation(), now_s=100.0)

        self.assertEqual(decision.status, ObservationStatus.CENTERED)
        self.assertEqual(self.sequence.last_capture_time_s, 100.0)

    def test_threshold_validation_matches_the_validator(self) -> None:
        invalid_values = (0, -1, True, math.nan, math.inf)
        for value in invalid_values:
            with self.subTest(max_age_s=value):
                with self.assertRaises(ValueError):
                    ObservationSequence(expected_target_id=7, max_age_s=value)
            with self.subTest(centered_tolerance_m=value):
                with self.assertRaises(ValueError):
                    ObservationSequence(expected_target_id=7, centered_tolerance_m=value)

    def test_last_capture_time_property_is_read_only(self) -> None:
        with self.assertRaises(AttributeError):
            self.sequence.last_capture_time_s = 100.0  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
