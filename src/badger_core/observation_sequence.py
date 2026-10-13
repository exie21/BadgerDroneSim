"""Stateful ordering guard around the pure observation validator."""

from .observation import (
    Observation,
    ObservationDecision,
    ObservationStatus,
    _finite_metric,
    validate_observation,
)


class ObservationSequence:
    """Track the capture time of observations accepted for one operation.

    This class has no clock, I/O, vehicle, or authorization behavior.  A caller
    supplies the current time for each sample and explicitly resets the sequence
    before beginning a new operation or simulation clock epoch.
    """

    def __init__(
        self,
        expected_target_id: int,
        max_age_s: float = 0.2,
        centered_tolerance_m: float = 0.15,
    ) -> None:
        if not _finite_metric(max_age_s) or max_age_s <= 0:
            raise ValueError("max_age_s must be a finite positive number")
        if not _finite_metric(centered_tolerance_m) or centered_tolerance_m <= 0:
            raise ValueError("centered_tolerance_m must be a finite positive number")

        self._expected_target_id = expected_target_id
        self._max_age_s = max_age_s
        self._centered_tolerance_m = centered_tolerance_m
        self._last_capture_time_s: float | None = None

    @property
    def last_capture_time_s(self) -> float | None:
        """The capture time of the most recently accepted observation."""
        return self._last_capture_time_s

    def reset(self) -> None:
        """Clear accepted state for a new operation or simulation clock epoch."""
        self._last_capture_time_s = None

    def evaluate(self, observation: Observation, now_s: float) -> ObservationDecision:
        """Classify an observation and retain its capture time only if accepted."""
        decision = validate_observation(
            observation=observation,
            expected_target_id=self._expected_target_id,
            now_s=now_s,
            last_capture_time_s=self._last_capture_time_s,
            max_age_s=self._max_age_s,
            centered_tolerance_m=self._centered_tolerance_m,
        )
        if decision.status in (ObservationStatus.VALID, ObservationStatus.CENTERED):
            self._last_capture_time_s = observation.capture_time_s
        return decision
