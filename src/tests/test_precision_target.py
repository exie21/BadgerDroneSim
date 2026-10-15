"""Tests for the pure, simulation-only metric landing-target data path."""

from dataclasses import dataclass
import math
import unittest

from src.badger_precision_target.landing_target import (
    MAV_FRAME_BODY_FRD,
    MAVLINK_MSG_ID_LANDING_TARGET,
    NedPoint,
    VehicleAttitude,
    make_metric_landing_target,
    send_metric_landing_target,
    target_relative_to_body_frd,
)
from src.badger_precision_target.synthetic import VehicleStateCache


@dataclass
class Message:
    message_type: str

    def get_type(self) -> str:
        return self.message_type


class Sender:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def landing_target_send(self, *arguments: object) -> None:
        self.calls.append(arguments)


class TestPrecisionTarget(unittest.TestCase):
    def test_level_north_east_down_coordinates_are_already_body_frd(self) -> None:
        target = NedPoint(5.0, -2.0, 0.0)
        vehicle = NedPoint(1.0, 3.0, -5.0)
        attitude = VehicleAttitude(0.0, 0.0, 0.0)

        result = target_relative_to_body_frd(target, vehicle, attitude)

        self.assertEqual(result.x_m, 4.0)
        self.assertEqual(result.y_m, -5.0)
        self.assertEqual(result.z_m, 5.0)

    def test_yaw_rotation_changes_north_target_to_vehicle_left(self) -> None:
        result = target_relative_to_body_frd(
            NedPoint(1.0, 0.0, 0.0),
            NedPoint(0.0, 0.0, 0.0),
            VehicleAttitude(0.0, 0.0, math.pi / 2),
        )

        self.assertAlmostEqual(result.x_m, 0.0, places=12)
        self.assertAlmostEqual(result.y_m, -1.0, places=12)
        self.assertAlmostEqual(result.z_m, 0.0, places=12)

    def test_metric_message_has_relative_body_position_and_distance(self) -> None:
        target = make_metric_landing_target(
            NedPoint(3.0, 4.0, 0.0),
            NedPoint(0.0, 0.0, -12.0),
            VehicleAttitude(0.0, 0.0, 0.0),
            time_usec=123_000,
            target_num=7,
        )

        self.assertEqual((target.time_usec, target.target_num), (123_000, 7))
        self.assertEqual((target.x_m, target.y_m, target.z_m), (3.0, 4.0, 12.0))
        self.assertEqual(target.distance_m, 13.0)

    def test_sender_emits_only_documented_metric_landing_target_fields(self) -> None:
        target = make_metric_landing_target(
            NedPoint(1.0, 2.0, 3.0),
            NedPoint(0.0, 0.0, 0.0),
            VehicleAttitude(0.0, 0.0, 0.0),
            time_usec=10,
        )
        sender = Sender()

        send_metric_landing_target(sender, target)

        self.assertEqual(len(sender.calls), 1)
        self.assertEqual(
            sender.calls[0],
            (10, 0, MAV_FRAME_BODY_FRD, 0.0, 0.0, math.sqrt(14), 0.0, 0.0, 1.0, 2.0, 3.0,
             [1.0, 0.0, 0.0, 0.0], 0, 1),
        )
        self.assertEqual(MAVLINK_MSG_ID_LANDING_TARGET, 149)

    def test_cache_requires_complete_fresh_local_state(self) -> None:
        cache = VehicleStateCache()
        position = Message("LOCAL_POSITION_NED")
        position.x, position.y, position.z = 1.0, 2.0, -3.0
        attitude = Message("ATTITUDE")
        attitude.roll, attitude.pitch, attitude.yaw = 0.1, 0.2, 0.3

        self.assertTrue(cache.accept(position, received_s=10.0))
        self.assertIsNone(cache.current(now_s=10.0, max_age_s=0.5))
        self.assertTrue(cache.accept(attitude, received_s=10.1))
        self.assertEqual(cache.current(now_s=10.5, max_age_s=0.5), (NedPoint(1.0, 2.0, -3.0), VehicleAttitude(0.1, 0.2, 0.3)))
        self.assertIsNone(cache.current(now_s=10.51, max_age_s=0.5))

    def test_cache_ignores_unrelated_or_invalid_messages(self) -> None:
        cache = VehicleStateCache()
        unrelated = Message("HEARTBEAT")
        invalid_position = Message("LOCAL_POSITION_NED")
        invalid_position.x, invalid_position.y, invalid_position.z = math.nan, 0.0, 0.0

        self.assertFalse(cache.accept(unrelated, received_s=10.0))
        self.assertFalse(cache.accept(invalid_position, received_s=10.0))
        self.assertIsNone(cache.current(now_s=10.0, max_age_s=0.5))


if __name__ == "__main__":
    unittest.main()
