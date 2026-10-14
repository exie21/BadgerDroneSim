"""Deterministic, simulation-only payload request stand-in."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
import math
from numbers import Number


class PayloadStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class PayloadResult:
    request_id: str
    status: PayloadStatus


def _finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, Number):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


class ScriptedPayloadMock:
    """Return scripted payload outcomes from caller-supplied simulation time.

    This is test infrastructure. It neither communicates with a payload device
    nor establishes that a physical pickup action has happened.
    """

    def __init__(self, script: Mapping[str, tuple[float, PayloadStatus]]) -> None:
        if not isinstance(script, Mapping):
            raise ValueError("script must be a mapping of request IDs to outcome pairs")

        self._script: dict[str, tuple[float, PayloadStatus]] = {}
        for request_id, outcome in script.items():
            if not isinstance(request_id, str) or not request_id:
                raise ValueError("script request IDs must be nonempty strings")
            if not isinstance(outcome, tuple) or len(outcome) != 2:
                raise ValueError("each scripted outcome must be a (delay_s, terminal_status) pair")
            delay_s, terminal_status = outcome
            if not _finite_number(delay_s) or delay_s < 0:
                raise ValueError("scripted delay_s must be a finite nonnegative number")
            if (
                not isinstance(terminal_status, PayloadStatus)
                or terminal_status is PayloadStatus.IN_PROGRESS
            ):
                raise ValueError("scripted terminal status must be SUCCEEDED, FAILED, or UNKNOWN")
            self._script[request_id] = (delay_s, terminal_status)

        self._start_times_s: dict[str, float] = {}

    def start(self, request_id: str, now_s: float) -> PayloadResult:
        """Record the first request time and report acceptance as in progress."""
        self._validate_now(now_s)
        self._scripted_outcome(request_id)
        self._start_times_s.setdefault(request_id, now_s)
        return PayloadResult(request_id, PayloadStatus.IN_PROGRESS)

    def poll(self, request_id: str, now_s: float) -> PayloadResult:
        """Return the scripted status for a previously started request."""
        self._validate_now(now_s)
        delay_s, terminal_status = self._scripted_outcome(request_id)
        try:
            start_time_s = self._start_times_s[request_id]
        except KeyError as exc:
            raise KeyError(f"payload request {request_id!r} has not been started") from exc
        if now_s < start_time_s:
            raise ValueError("poll time cannot be earlier than the original start time")
        status = terminal_status if now_s >= start_time_s + delay_s else PayloadStatus.IN_PROGRESS
        return PayloadResult(request_id, status)

    def _scripted_outcome(self, request_id: str) -> tuple[float, PayloadStatus]:
        try:
            return self._script[request_id]
        except (KeyError, TypeError) as exc:
            raise KeyError(f"payload request {request_id!r} is not scripted") from exc

    @staticmethod
    def _validate_now(now_s: float) -> None:
        if not _finite_number(now_s):
            raise ValueError("now_s must be a finite number")
