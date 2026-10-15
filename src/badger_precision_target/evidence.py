"""Receive-only D1 evidence check for routed metric ``LANDING_TARGET`` packets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import math
import os
from pathlib import Path
from numbers import Number
import sys
import time
from typing import Any

from .landing_target import MAV_FRAME_BODY_FRD


class LandingTargetEvidenceStatus(str, Enum):
    VALID = "VALID"
    WRONG_FRAME = "WRONG_FRAME"
    POSITION_NOT_VALID = "POSITION_NOT_VALID"
    INVALID_METRIC = "INVALID_METRIC"
    INCONSISTENT_DISTANCE = "INCONSISTENT_DISTANCE"
    INVALID_TIME = "INVALID_TIME"


@dataclass(frozen=True)
class LandingTargetEvidence:
    status: LandingTargetEvidenceStatus
    x_m: float | None
    y_m: float | None
    z_m: float | None
    distance_m: float | None


def _finite(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, Number):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


def inspect_metric_landing_target(message: Any) -> LandingTargetEvidence:
    """Validate the D1 metric fields of one decoded ``LANDING_TARGET`` message."""
    if getattr(message, "frame", None) != MAV_FRAME_BODY_FRD:
        return LandingTargetEvidence(LandingTargetEvidenceStatus.WRONG_FRAME, None, None, None, None)
    if getattr(message, "position_valid", None) != 1:
        return LandingTargetEvidence(LandingTargetEvidenceStatus.POSITION_NOT_VALID, None, None, None, None)

    time_usec = getattr(message, "time_usec", None)
    if isinstance(time_usec, bool) or not isinstance(time_usec, int) or time_usec < 0:
        return LandingTargetEvidence(LandingTargetEvidenceStatus.INVALID_TIME, None, None, None, None)

    x_m = getattr(message, "x", None)
    y_m = getattr(message, "y", None)
    z_m = getattr(message, "z", None)
    distance_m = getattr(message, "distance", None)
    if not all(_finite(value) for value in (x_m, y_m, z_m, distance_m)) or distance_m < 0:
        return LandingTargetEvidence(LandingTargetEvidenceStatus.INVALID_METRIC, None, None, None, None)

    expected_distance_m = math.sqrt(x_m * x_m + y_m * y_m + z_m * z_m)
    if not math.isclose(distance_m, expected_distance_m, rel_tol=1e-5, abs_tol=1e-4):
        return LandingTargetEvidence(
            LandingTargetEvidenceStatus.INCONSISTENT_DISTANCE,
            x_m,
            y_m,
            z_m,
            distance_m,
        )
    return LandingTargetEvidence(LandingTargetEvidenceStatus.VALID, x_m, y_m, z_m, distance_m)


def _configuration() -> tuple[str, int, float, int, Path]:
    host = os.environ.get("D1_EVIDENCE_BIND_HOST", "0.0.0.0")
    port = int(os.environ.get("D1_EVIDENCE_BIND_PORT", "14553"))
    timeout_s = float(os.environ.get("D1_EVIDENCE_TIMEOUT_S", "30"))
    minimum_samples = int(os.environ.get("D1_EVIDENCE_MIN_VALID_SAMPLES", "3"))
    path = Path(os.environ.get("D1_EVIDENCE_PATH", "/state/landing-target-evidence.json"))
    if not host or not 1 <= port <= 65535 or timeout_s <= 0 or minimum_samples <= 0:
        raise ValueError("invalid D1 landing-target evidence configuration")
    return host, port, timeout_s, minimum_samples, path


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _evidence_payload(evidence: LandingTargetEvidence) -> dict[str, object]:
    return {
        "evidence_status": evidence.status.value,
        "x_m": evidence.x_m,
        "y_m": evidence.y_m,
        "z_m": evidence.z_m,
        "distance_m": evidence.distance_m,
    }


def main() -> int:
    host, port, timeout_s, minimum_samples, path = _configuration()
    from pymavlink import mavutil

    connection = mavutil.mavlink_connection(f"udpin:{host}:{port}")
    deadline = time.monotonic() + timeout_s
    valid_count = 0
    while time.monotonic() < deadline:
        message = connection.recv_match(blocking=True, timeout=min(1.0, deadline - time.monotonic()))
        if message is None or message.get_type() != "LANDING_TARGET":
            continue
        evidence = inspect_metric_landing_target(message)
        if evidence.status is not LandingTargetEvidenceStatus.VALID:
            _write(path, {"status": "invalid", **_evidence_payload(evidence)})
            print(f"invalid LANDING_TARGET: {evidence.status.value}", file=sys.stderr, flush=True)
            return 1
        valid_count += 1
        if valid_count >= minimum_samples:
            _write(
                path,
                {"status": "ok", "valid_count": valid_count, **_evidence_payload(evidence)},
            )
            print(f"verified {valid_count} metric LANDING_TARGET messages", flush=True)
            return 0
    _write(path, {"status": "timeout", "valid_count": valid_count})
    print(f"no sufficient valid LANDING_TARGET messages within {timeout_s:g} seconds", file=sys.stderr, flush=True)
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(f"landing-target evidence failed: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
