from dataclasses import dataclass
from enum import Enum
import math


class ObservationStatus(Enum):
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
    x_error_m: float
    y_error_m: float
    valid_pose: bool
    calibration_version: str


@dataclass(frozen=True)
class ObservationDecision:
    status: ObservationStatus
    horizontal_error_m: float | None


def validate_observation(
    observation: Observation,
    expected_target_id: int,
    now_s: float,
    last_capture_time_s: float,
    max_age_s: float = 0.2,
    centered_tolerance_m: float = 0.15
) -> ObservationDecision:
    # Validate threshold parameters first
    if max_age_s <= 0 or centered_tolerance_m <= 0:
        raise ValueError("max_age_s and centered_tolerance_m must be positive")
    
    # WRONG_TARGET check (target_id None, empty string, or mismatch)
    if observation.target_id is None or observation.target_id == "" or observation.target_id != expected_target_id:
        return ObservationDecision(status=ObservationStatus.WRONG_TARGET, horizontal_error_m=None)
    
    # INVALID_POSE checks
    if not observation.valid_pose:
        return ObservationDecision(status=ObservationStatus.INVALID_POSE, horizontal_error_m=None)
    
    if not isinstance(observation.calibration_version, str) or observation.calibration_version.strip() == "":
        return ObservationDecision(status=ObservationStatus.INVALID_POSE, horizontal_error_m=None)
    
    if not isinstance(observation.x_error_m, (int, float)) or not math.isfinite(observation.x_error_m):
        return ObservationDecision(status=ObservationStatus.INVALID_POSE, horizontal_error_m=None)
    
    if not isinstance(observation.y_error_m, (int, float)) or not math.isfinite(observation.y_error_m):
        return ObservationDecision(status=ObservationStatus.INVALID_POSE, horizontal_error_m=None)
    
    # FUTURE check
    if observation.capture_time_s > now_s:
        return ObservationDecision(status=ObservationStatus.FUTURE, horizontal_error_m=None)
    
    # OUT_OF_ORDER check
    if observation.capture_time_s <= last_capture_time_s:
        return ObservationDecision(status=ObservationStatus.OUT_OF_ORDER, horizontal_error_m=None)
    
    # STALE check
    age = now_s - observation.capture_time_s
    if age > max_age_s:
        return ObservationDecision(status=ObservationStatus.STALE, horizontal_error_m=None)
    
    # Calculate horizontal error
    horizontal_error_m = math.hypot(observation.x_error_m, observation.y_error_m)
    
    # Check for overflow/nonfinite result
    if not math.isfinite(horizontal_error_m):
        return ObservationDecision(status=ObservationStatus.INVALID_POSE, horizontal_error_m=None)
    
    # CENTERED check
    if horizontal_error_m <= centered_tolerance_m:
        return ObservationDecision(status=ObservationStatus.CENTERED, horizontal_error_m=horizontal_error_m)
    
    # VALID (default)
    return ObservationDecision(status=ObservationStatus.VALID, horizontal_error_m=horizontal_error_m)
