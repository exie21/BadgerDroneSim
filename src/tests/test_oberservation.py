"""Contract tests for the pure observation gate."""

from dataclasses import FrozenInstanceError, fields
from decimal import Decimal
from types import SimpleNamespace
import math
import unittest

from src.badger_core.oberservation import (
    Observation, ObservationDecision, ObservationStatus, validate_observation,
)


class TestObservationValidation(unittest.TestCase):
    def observation(self, **changes):
        values = dict(target_id=7, capture_time_s=100.00, received_time_s=100.05,
                      x_error_m=0.06, y_error_m=-0.04, valid_pose=True,
                      calibration_version="v1")
        values.update(changes)
        return Observation(**values)

    def decide(self, observation, **changes):
        options = dict(expected_target_id=7, now_s=100.08,
                       last_capture_time_s=99.90)
        options.update(changes)
        return validate_observation(observation, **options)

    def test_public_shapes_are_frozen_and_status_values_are_strings(self):
        self.assertEqual([field.name for field in fields(Observation)],
                         ["target_id", "capture_time_s", "received_time_s", "x_error_m",
                          "y_error_m", "valid_pose", "calibration_version"])
        self.assertEqual([field.name for field in fields(ObservationDecision)],
                         ["status", "horizontal_error_m"])
        self.assertEqual({member.name for member in ObservationStatus},
                         {"VALID", "CENTERED", "STALE", "WRONG_TARGET",
                          "INVALID_POSE", "OUT_OF_ORDER", "FUTURE"})
        for member in ObservationStatus:
            self.assertIsInstance(member, str)
            self.assertEqual(member.value, member.name)
        with self.assertRaises(FrozenInstanceError):
            self.observation().target_id = 8

    def test_centered_example_from_sketch(self):
        result = self.decide(self.observation())
        self.assertEqual(result.status, ObservationStatus.CENTERED)
        self.assertAlmostEqual(result.horizontal_error_m, math.hypot(0.06, -0.04))

    def test_valid_non_centered_example(self):
        result = self.decide(self.observation(x_error_m=0.20, y_error_m=0.00))
        self.assertEqual(result.status, ObservationStatus.VALID)
        self.assertAlmostEqual(result.horizontal_error_m, 0.20)

    def test_nonpositive_thresholds_raise(self):
        for option in (dict(max_age_s=0), dict(max_age_s=-1),
                       dict(centered_tolerance_m=0), dict(centered_tolerance_m=-1)):
            with self.subTest(option=option), self.assertRaises(ValueError):
                self.decide(self.observation(), **option)

    def test_wrong_target_precedes_other_rejections(self):
        for target in (None, "", 8):
            with self.subTest(target=target):
                result = self.decide(self.observation(target_id=target, valid_pose=False,
                                                      capture_time_s=101))
                self.assertEqual(result, ObservationDecision(ObservationStatus.WRONG_TARGET, None))

    def test_invalid_pose_and_measurements(self):
        invalid = (dict(valid_pose=False), dict(valid_pose=1),
                   dict(calibration_version=""), dict(calibration_version="  "),
                   dict(calibration_version=None), dict(x_error_m=None),
                   dict(x_error_m=True), dict(x_error_m="0.1"),
                   dict(x_error_m=math.inf), dict(x_error_m=math.nan),
                   dict(y_error_m=None), dict(y_error_m=False),
                   dict(y_error_m="0.1"), dict(y_error_m=-math.inf))
        for change in invalid:
            with self.subTest(change=change):
                result = self.decide(self.observation(**change))
                self.assertEqual(result, ObservationDecision(ObservationStatus.INVALID_POSE, None))

    def test_missing_metric_and_decimal_metric(self):
        values = vars(self.observation()).copy()
        del values["x_error_m"]
        missing = self.decide(SimpleNamespace(**values))
        self.assertEqual(missing, ObservationDecision(ObservationStatus.INVALID_POSE, None))
        decimal = self.decide(self.observation(x_error_m=Decimal("0.06")))
        self.assertEqual(decimal.status, ObservationStatus.CENTERED)

    def test_invalid_pose_precedes_future(self):
        result = self.decide(self.observation(valid_pose=False, capture_time_s=101))
        self.assertEqual(result.status, ObservationStatus.INVALID_POSE)

    def test_future_precedes_out_of_order(self):
        result = self.decide(self.observation(capture_time_s=101),
                             last_capture_time_s=102)
        self.assertEqual(result, ObservationDecision(ObservationStatus.FUTURE, None))

    def test_out_of_order_precedes_stale(self):
        result = self.decide(self.observation(capture_time_s=99.0),
                             last_capture_time_s=99.0)
        self.assertEqual(result, ObservationDecision(ObservationStatus.OUT_OF_ORDER, None))

    def test_stale(self):
        result = self.decide(self.observation(capture_time_s=99.0),
                             last_capture_time_s=98.0)
        self.assertEqual(result, ObservationDecision(ObservationStatus.STALE, None))

    def test_hypot_overflow_is_invalid_pose(self):
        result = self.decide(self.observation(x_error_m=1.7e308, y_error_m=1.7e308))
        self.assertEqual(result, ObservationDecision(ObservationStatus.INVALID_POSE, None))


if __name__ == "__main__":
    unittest.main()
