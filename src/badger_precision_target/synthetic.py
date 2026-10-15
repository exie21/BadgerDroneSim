"""SITL-only publisher of a fixed local-NED target as `LANDING_TARGET` data."""

from __future__ import annotations

from dataclasses import dataclass
import os
import sys
import time
from typing import Any

from .landing_target import (
    MetricLandingTarget,
    NedPoint,
    VehicleAttitude,
    _finite,
    make_metric_landing_target,
    send_metric_landing_target,
)


@dataclass(frozen=True)
class SyntheticTargetConfiguration:
    target_ned: NedPoint
    rate_hz: float = 5.0
    state_max_age_s: float = 0.5
    target_num: int = 0
    telemetry_bind_host: str = "0.0.0.0"
    telemetry_bind_port: int = 14551
    router_host: str = "router"
    router_port: int = 14552
    stream_duration_s: float = 0.0

    def __post_init__(self) -> None:
        if not _finite(self.rate_hz) or self.rate_hz < 2.0:
            raise ValueError("rate_hz must be a finite number of at least 2")
        if not _finite(self.state_max_age_s) or self.state_max_age_s <= 0:
            raise ValueError("state_max_age_s must be a finite positive number")
        if isinstance(self.target_num, bool) or not isinstance(self.target_num, int) or not 0 <= self.target_num <= 255:
            raise ValueError("target_num must be an integer from 0 through 255")
        if not self.telemetry_bind_host or not self.router_host:
            raise ValueError("telemetry_bind_host and router_host must not be empty")
        if not 1 <= self.telemetry_bind_port <= 65535 or not 1 <= self.router_port <= 65535:
            raise ValueError("MAVLink ports must be in range 1 through 65535")
        if not _finite(self.stream_duration_s) or self.stream_duration_s < 0:
            raise ValueError("stream_duration_s must be a finite non-negative number")


@dataclass
class VehicleStateCache:
    """Latest local position and attitude received from the simulated FC."""

    vehicle_ned: NedPoint | None = None
    attitude: VehicleAttitude | None = None
    position_received_s: float | None = None
    attitude_received_s: float | None = None

    def accept(self, message: Any, received_s: float) -> bool:
        """Retain a supported MAVLink telemetry message; ignore everything else."""
        if not _finite(received_s):
            raise ValueError("received_s must be a finite number")
        message_type = message.get_type()
        if message_type == "LOCAL_POSITION_NED":
            try:
                self.vehicle_ned = NedPoint(message.x, message.y, message.z)
            except ValueError:
                return False
            self.position_received_s = received_s
            return True
        if message_type == "ATTITUDE":
            try:
                self.attitude = VehicleAttitude(message.roll, message.pitch, message.yaw)
            except ValueError:
                return False
            self.attitude_received_s = received_s
            return True
        return False

    def current(self, now_s: float, max_age_s: float) -> tuple[NedPoint, VehicleAttitude] | None:
        """Return a complete state only while both inputs are fresh."""
        if not _finite(now_s) or not _finite(max_age_s) or max_age_s <= 0:
            raise ValueError("now_s and max_age_s must be finite, with max_age_s positive")
        if (
            self.vehicle_ned is None
            or self.attitude is None
            or self.position_received_s is None
            or self.attitude_received_s is None
            or now_s - self.position_received_s > max_age_s
            or now_s - self.attitude_received_s > max_age_s
        ):
            return None
        return self.vehicle_ned, self.attitude


def _float_environment(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be a number") from error


def _int_environment(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error


def configuration_from_environment() -> SyntheticTargetConfiguration:
    """Load the deliberately small D1 simulation configuration surface."""
    return SyntheticTargetConfiguration(
        target_ned=NedPoint(
            _float_environment("D1_TARGET_NORTH_M", 5.0),
            _float_environment("D1_TARGET_EAST_M", 0.0),
            _float_environment("D1_TARGET_DOWN_M", 0.0),
        ),
        rate_hz=_float_environment("D1_RATE_HZ", 5.0),
        state_max_age_s=_float_environment("D1_STATE_MAX_AGE_S", 0.5),
        target_num=_int_environment("D1_TARGET_NUM", 0),
        telemetry_bind_host=os.environ.get("D1_TELEMETRY_BIND_HOST", "0.0.0.0"),
        telemetry_bind_port=_int_environment("D1_TELEMETRY_BIND_PORT", 14551),
        router_host=os.environ.get("D1_ROUTER_HOST", "router"),
        router_port=_int_environment("D1_ROUTER_PORT", 14552),
        stream_duration_s=_float_environment("D1_STREAM_DURATION_S", 0.0),
    )


def _time_usec_since_start(start_s: float, now_s: float) -> int:
    return int((now_s - start_s) * 1_000_000)


def run(configuration: SyntheticTargetConfiguration) -> int:
    """Receive state from D1 router and publish target data at the configured rate."""
    from pymavlink import mavutil

    receiver = mavutil.mavlink_connection(
        f"udpin:{configuration.telemetry_bind_host}:{configuration.telemetry_bind_port}"
    )
    sender_connection = mavutil.mavlink_connection(
        f"udpout:{configuration.router_host}:{configuration.router_port}",
        source_system=42,
        source_component=191,
    )
    cache = VehicleStateCache()
    start_s = time.monotonic()
    next_send_s = start_s
    sent_count = 0

    while True:
        now_s = time.monotonic()
        if configuration.stream_duration_s and now_s - start_s >= configuration.stream_duration_s:
            print(f"stopped after publishing {sent_count} LANDING_TARGET messages", flush=True)
            return 0

        state = cache.current(now_s, configuration.state_max_age_s)
        if state is not None and now_s >= next_send_s:
            vehicle_ned, attitude = state
            target = make_metric_landing_target(
                configuration.target_ned,
                vehicle_ned,
                attitude,
                _time_usec_since_start(start_s, now_s),
                configuration.target_num,
            )
            send_metric_landing_target(sender_connection.mav, target)
            sent_count += 1
            next_send_s = now_s + (1.0 / configuration.rate_hz)
            if sent_count == 1 or sent_count % int(configuration.rate_hz) == 0:
                print(
                    f"published LANDING_TARGET {sent_count}: "
                    f"x={target.x_m:.2f} y={target.y_m:.2f} z={target.z_m:.2f}",
                    flush=True,
                )

        wake_s = next_send_s if state is not None else time.monotonic() + 0.1
        wait_s = max(0.0, min(0.1, wake_s - time.monotonic()))
        message = receiver.recv_match(blocking=True, timeout=wait_s)
        if message is not None:
            cache.accept(message, time.monotonic())


def main() -> int:
    try:
        return run(configuration_from_environment())
    except (ValueError, OSError) as error:
        print(f"precision target source failed: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
