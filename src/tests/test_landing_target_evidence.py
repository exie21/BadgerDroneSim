"""Tests for receive-only validation of D1 metric landing-target packets."""

from dataclasses import dataclass
import math
import unittest

from src.badger_precision_target.evidence import (
    LandingTargetEvidenceStatus,
    inspect_metric_landing_target,
)


@dataclass
class LandingTargetMessage:
    frame: object = 12
    position_valid: object = 1
    time_usec: object = 123
    x: object = 3.0
    y: object = 4.0
    z: object = 12.0
    distance: object = 13.0


class TestLandingTargetEvidence(unittest.TestCase):
    def test_valid_metric_packet_is_accepted(self) -> None:
        result = inspect_metric_landing_target(LandingTargetMessage())

        self.assertEqual(result.status, LandingTargetEvidenceStatus.VALID)
        self.assertEqual((result.x_m, result.y_m, result.z_m, result.distance_m), (3.0, 4.0, 12.0, 13.0))

    def test_frame_and_position_valid_are_required_before_metrics(self) -> None:
        wrong_frame = inspect_metric_landing_target(LandingTargetMessage(frame=1, x=math.nan))
        invalid_position = inspect_metric_landing_target(LandingTargetMessage(position_valid=0, x=math.nan))

        self.assertEqual(wrong_frame.status, LandingTargetEvidenceStatus.WRONG_FRAME)
        self.assertEqual(invalid_position.status, LandingTargetEvidenceStatus.POSITION_NOT_VALID)

    def test_invalid_time_and_metric_values_are_rejected(self) -> None:
        for changes, expected in (
            ({"time_usec": -1}, LandingTargetEvidenceStatus.INVALID_TIME),
            ({"time_usec": True}, LandingTargetEvidenceStatus.INVALID_TIME),
            ({"x": math.nan}, LandingTargetEvidenceStatus.INVALID_METRIC),
            ({"distance": -1.0}, LandingTargetEvidenceStatus.INVALID_METRIC),
        ):
            with self.subTest(changes=changes):
                self.assertEqual(
                    inspect_metric_landing_target(LandingTargetMessage(**changes)).status,
                    expected,
                )

    def test_distance_must_match_body_frd_position(self) -> None:
        result = inspect_metric_landing_target(LandingTargetMessage(distance=12.9))

        self.assertEqual(result.status, LandingTargetEvidenceStatus.INCONSISTENT_DISTANCE)
        self.assertEqual((result.x_m, result.y_m, result.z_m, result.distance_m), (3.0, 4.0, 12.0, 12.9))


if __name__ == "__main__":
    unittest.main()
