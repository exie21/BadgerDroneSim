"""Pure validation of one already-metric target observation."""

from dataclasses import dataclass
from enum import Enum
import math
from numbers import Number


class ObservationStatus(str, Enum):
    VALID = "VALID"
    CENTERED = "CENTERED"
    STALE = "STALE"
    WRONG_TARGET = "WRONG_TARGET"
    INVALID_POSE = "INVALID_POSE"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    FUTURE = "FUTURE"


@dataclass(frozen=True)
class Observation:
    target_id: int | None
    capture_time_s: float
    received_time_s: float
    x_error_m: float | None
    y_error_m: float | None
    valid_pose: bool
    calibration_version: str


@dataclass(frozen=True)
class ObservationDecision:
    status: ObservationStatus
    horizontal_error_m: float | None


def _finite_metric(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, Number):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


def validate_observation(
    observation: Observation,
    expected_target_id: int,
    now_s: float,
    last_capture_time_s: float,
    max_age_s: float = 0.2,
    centered_tolerance_m: float = 0.15,
) -> ObservationDecision:
    """Classify an observation without I/O or external dependencies."""
    if max_age_s <= 0 or centered_tolerance_m <= 0:
        raise ValueError("max_age_s and centered_tolerance_m must be positive")

    def rejected(status: ObservationStatus) -> ObservationDecision:
        return ObservationDecision(status, None)

    if observation.target_id is None or observation.target_id == "" or observation.target_id != expected_target_id:
        return rejected(ObservationStatus.WRONG_TARGET)
    if (
        getattr(observation, "valid_pose", None) is not True
        or not isinstance(getattr(observation, "calibration_version", None), str)
        or not observation.calibration_version.strip()
        or not _finite_metric(getattr(observation, "x_error_m", None))
        or not _finite_metric(getattr(observation, "y_error_m", None))
    ):
        return rejected(ObservationStatus.INVALID_POSE)
    if observation.capture_time_s > now_s:
        return rejected(ObservationStatus.FUTURE)
    if observation.capture_time_s <= last_capture_time_s:
        return rejected(ObservationStatus.OUT_OF_ORDER)
    if now_s - observation.capture_time_s > max_age_s:
        return rejected(ObservationStatus.STALE)

    horizontal_error = math.hypot(observation.x_error_m, observation.y_error_m)
    if not math.isfinite(horizontal_error):
        return rejected(ObservationStatus.INVALID_POSE)
    status = ObservationStatus.CENTERED if horizontal_error <= centered_tolerance_m else ObservationStatus.VALID
    return ObservationDecision(status, horizontal_error)
