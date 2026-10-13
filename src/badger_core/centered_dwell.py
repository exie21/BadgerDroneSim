"""Pure contiguity evidence for a centered visual observation stream."""

from dataclasses import dataclass
import math

from .observation import Observation, ObservationDecision, ObservationStatus, _finite_metric
from .observation_sequence import ObservationSequence


@dataclass(frozen=True)
class CenteredDwellResult:
    """The current observation decision and its continuous centered duration."""

    decision: ObservationDecision
    centered_duration_s: float
    dwell_met: bool


class CenteredDwell:
    """Track continuous accepted ``CENTERED`` observations for one operation.

    The output is visual-position evidence only. It does not establish vehicle
    speed, pickup-tool alignment, authorization, actuator success, or safe
    flight behavior.
    """

    def __init__(
        self,
        expected_target_id: int,
        required_dwell_s: float = 2.0,
        max_gap_s: float = 0.3,
        max_age_s: float = 0.2,
        centered_tolerance_m: float = 0.15,
    ) -> None:
        if not _finite_metric(required_dwell_s) or required_dwell_s <= 0:
            raise ValueError("required_dwell_s must be a finite positive number")
        if not _finite_metric(max_gap_s) or max_gap_s <= 0:
            raise ValueError("max_gap_s must be a finite positive number")

        self._required_dwell_s = required_dwell_s
        self._max_gap_s = max_gap_s
        self._sequence = ObservationSequence(
            expected_target_id=expected_target_id,
            max_age_s=max_age_s,
            centered_tolerance_m=centered_tolerance_m,
        )
        self._run_start_capture_time_s: float | None = None
        self._last_centered_capture_time_s: float | None = None

    def reset(self) -> None:
        """Clear sequence and dwell state for a new operation or clock epoch."""
        self._sequence.reset()
        self._run_start_capture_time_s = None
        self._last_centered_capture_time_s = None

    def evaluate(self, observation: Observation, now_s: float) -> CenteredDwellResult:
        """Evaluate one observation and return continuous centered-time evidence."""
        decision = self._sequence.evaluate(observation, now_s)
        if decision.status is not ObservationStatus.CENTERED:
            self._end_run()
            return CenteredDwellResult(decision, centered_duration_s=0.0, dwell_met=False)

        capture_time_s = observation.capture_time_s
        if (
            self._run_start_capture_time_s is None
            or self._last_centered_capture_time_s is None
            or capture_time_s <= self._last_centered_capture_time_s
            or self._gap_exceeds_limit(capture_time_s)
        ):
            self._run_start_capture_time_s = capture_time_s

        self._last_centered_capture_time_s = capture_time_s
        centered_duration_s = capture_time_s - self._run_start_capture_time_s
        return CenteredDwellResult(
            decision,
            centered_duration_s=centered_duration_s,
            dwell_met=(
                centered_duration_s >= self._required_dwell_s
                or math.isclose(
                    centered_duration_s,
                    self._required_dwell_s,
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
            ),
        )

    def _end_run(self) -> None:
        self._run_start_capture_time_s = None
        self._last_centered_capture_time_s = None

    def _gap_exceeds_limit(self, capture_time_s: float) -> bool:
        """Compare timestamp subtraction without penalizing float round-off."""
        gap_s = capture_time_s - self._last_centered_capture_time_s
        return gap_s > self._max_gap_s and not math.isclose(
            gap_s,
            self._max_gap_s,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
