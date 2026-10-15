"""Pure coordinate conversion and MAVLink message construction for D1.

This module deliberately has no vehicle connection or command API.  Its sole
outbound data shape is MAVLink ``LANDING_TARGET`` with metric body-FRD values.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Number
from typing import Protocol


MAV_FRAME_BODY_FRD = 12
MAVLINK_MSG_ID_LANDING_TARGET = 149


def _finite(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, Number):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


@dataclass(frozen=True)
class NedPoint:
    """A point or vector expressed in local North-East-Down metres."""

    north_m: float
    east_m: float
    down_m: float

    def __post_init__(self) -> None:
        if not all(_finite(value) for value in (self.north_m, self.east_m, self.down_m)):
            raise ValueError("NED coordinates must be finite numbers")


@dataclass(frozen=True)
class VehicleAttitude:
    """Vehicle roll, pitch, and yaw in radians, using the MAVLink NED convention."""

    roll_rad: float
    pitch_rad: float
    yaw_rad: float

    def __post_init__(self) -> None:
        if not all(_finite(value) for value in (self.roll_rad, self.pitch_rad, self.yaw_rad)):
            raise ValueError("attitude values must be finite numbers")


@dataclass(frozen=True)
class BodyFrdVector:
    """A vector expressed as vehicle-body forward, right, and down metres."""

    x_m: float
    y_m: float
    z_m: float

    def __post_init__(self) -> None:
        if not all(_finite(value) for value in (self.x_m, self.y_m, self.z_m)):
            raise ValueError("body-FRD coordinates must be finite numbers")


@dataclass(frozen=True)
class MetricLandingTarget:
    """One metric target position ready for MAVLink ``LANDING_TARGET``."""

    time_usec: int
    target_num: int
    x_m: float
    y_m: float
    z_m: float

    def __post_init__(self) -> None:
        if isinstance(self.time_usec, bool) or not isinstance(self.time_usec, int) or self.time_usec < 0:
            raise ValueError("time_usec must be a non-negative integer")
        if isinstance(self.target_num, bool) or not isinstance(self.target_num, int) or not 0 <= self.target_num <= 255:
            raise ValueError("target_num must be an integer from 0 through 255")
        if not all(_finite(value) for value in (self.x_m, self.y_m, self.z_m)):
            raise ValueError("body-FRD coordinates must be finite numbers")

    @property
    def distance_m(self) -> float:
        return math.sqrt(self.x_m * self.x_m + self.y_m * self.y_m + self.z_m * self.z_m)


class LandingTargetSender(Protocol):
    def landing_target_send(
        self,
        time_usec: int,
        target_num: int,
        frame: int,
        angle_x: float,
        angle_y: float,
        distance: float,
        size_x: float,
        size_y: float,
        x: float,
        y: float,
        z: float,
        q: list[float],
        target_type: int,
        position_valid: int,
    ) -> None: ...


def target_relative_to_body_frd(
    target_ned: NedPoint,
    vehicle_ned: NedPoint,
    attitude: VehicleAttitude,
) -> BodyFrdVector:
    """Express a fixed local-NED target relative to the vehicle body FRD frame.

    ArduPilot's metric Precision Loiter input expects forward/right/down.  The
    calculation is the transpose of the normal body-to-NED aerospace rotation.
    """
    north = target_ned.north_m - vehicle_ned.north_m
    east = target_ned.east_m - vehicle_ned.east_m
    down = target_ned.down_m - vehicle_ned.down_m

    roll = attitude.roll_rad
    pitch = attitude.pitch_rad
    yaw = attitude.yaw_rad
    cos_roll, sin_roll = math.cos(roll), math.sin(roll)
    cos_pitch, sin_pitch = math.cos(pitch), math.sin(pitch)
    cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)

    return BodyFrdVector(
        x_m=(cos_pitch * cos_yaw * north) + (cos_pitch * sin_yaw * east) - (sin_pitch * down),
        y_m=(sin_roll * sin_pitch * cos_yaw - cos_roll * sin_yaw) * north
        + (sin_roll * sin_pitch * sin_yaw + cos_roll * cos_yaw) * east
        + (sin_roll * cos_pitch * down),
        z_m=(cos_roll * sin_pitch * cos_yaw + sin_roll * sin_yaw) * north
        + (cos_roll * sin_pitch * sin_yaw - sin_roll * cos_yaw) * east
        + (cos_roll * cos_pitch * down),
    )


def make_metric_landing_target(
    target_ned: NedPoint,
    vehicle_ned: NedPoint,
    attitude: VehicleAttitude,
    time_usec: int,
    target_num: int = 0,
) -> MetricLandingTarget:
    """Build one metric body-FRD target message from simulation state."""
    relative_body = target_relative_to_body_frd(target_ned, vehicle_ned, attitude)
    return MetricLandingTarget(
        time_usec=time_usec,
        target_num=target_num,
        x_m=relative_body.x_m,
        y_m=relative_body.y_m,
        z_m=relative_body.z_m,
    )


def send_metric_landing_target(sender: LandingTargetSender, target: MetricLandingTarget) -> None:
    """Send the one permitted D1 outbound MAVLink message.

    The numeric constants and field population follow ArduPilot's documented
    metric ``LANDING_TARGET`` format: body-FRD frame and position_valid=1.
    """
    sender.landing_target_send(
        target.time_usec,
        target.target_num,
        MAV_FRAME_BODY_FRD,
        0.0,
        0.0,
        target.distance_m,
        0.0,
        0.0,
        target.x_m,
        target.y_m,
        target.z_m,
        [1.0, 0.0, 0.0, 0.0],
        0,
        1,
    )
