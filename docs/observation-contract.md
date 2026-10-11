# Observation validation contract (provisional)

`src.badger_core.observation` is a pure-Python gate for one already-metric target
observation. It screens supplied data; it does not estimate a pose or authorize
any aircraft or payload action. This contract is for simulation-side work and
is not the final integration message schema.

## Public data and call

`Observation` is a frozen dataclass with exactly these fields:

| Field | Meaning |
| --- | --- |
| `target_id` | Observed target identity; compared with `expected_target_id`. ID `0` is valid when expected. |
| `capture_time_s` | Capture timestamp in the caller's clock domain. |
| `received_time_s` | Receipt timestamp in the caller's clock domain; must be finite and not earlier than `capture_time_s`. |
| `x_error_m`, `y_error_m` | Supplied horizontal metric errors in meters. |
| `valid_pose` | Caller-supplied pose-valid flag; only `True` passes. |
| `calibration_version` | Nonblank string identifying the caller's calibration. |

`ObservationDecision` is a frozen dataclass with `status` and
`horizontal_error_m`. The latter is `None` for every rejected status; for
`VALID` or `CENTERED` it is `hypot(x_error_m, y_error_m)` in meters. `status` is
an `ObservationStatus` member: `VALID`, `CENTERED`, `STALE`, `WRONG_TARGET`,
`INVALID_POSE`, `OUT_OF_ORDER`, `FUTURE`, or `INVALID_TIME`.

`validate_observation(observation, expected_target_id, now_s,
last_capture_time_s, max_age_s=0.2, centered_tolerance_m=0.15)` returns an
`ObservationDecision`. The caller supplies the expected target, current time,
and previous accepted capture time. `last_capture_time_s` may be `None` for a
first observation. `now_s`, a non-`None` prior capture time, and both thresholds
must be finite non-boolean numbers; both thresholds must also be positive.
Invalid caller arguments raise `ValueError` before an observation is classified.

## Decision order and boundaries

The first matching rule wins after caller arguments are validated:

1. `INVALID_TIME`: `capture_time_s` or `received_time_s` is missing, boolean,
   nonnumeric, or nonfinite, or receipt is earlier than capture.
2. `FUTURE`: either finite observation timestamp is later than `now_s`.
3. `WRONG_TARGET`: `target_id` is `None`, an empty string, or unequal to
   `expected_target_id`.
4. `INVALID_POSE`: `valid_pose` is not exactly `True`, `calibration_version` is
   not a nonblank string, or either metric error is missing, boolean,
   nonnumeric, or nonfinite.
5. `OUT_OF_ORDER`: a non-first `capture_time_s <= last_capture_time_s`
   (duplicates count).
6. `STALE`: `now_s - capture_time_s > max_age_s`.
7. `INVALID_POSE`: the computed horizontal error is nonfinite, including
   numeric overflow in `hypot`.
8. Otherwise `CENTERED` when horizontal error is
   `<= centered_tolerance_m`; otherwise `VALID`.

An age **equal** to `max_age_s` is accepted, and an error **equal** to
`centered_tolerance_m` is `CENTERED`. A capture timestamp equal to the last
accepted timestamp is `OUT_OF_ORDER`. Rejection order matters: for example, a
wrong target with an invalid pose is `WRONG_TARGET`.

For a synthetic observation with target `7`, capture `100.00` s, receipt
`100.05` s, errors `(0.06, -0.04)` m, `valid_pose=True`, and calibration
version `"v1"`, calling the validator with expected target `7`, `now_s=100.08`,
and `last_capture_time_s=99.90` returns `CENTERED` with horizontal error about
`0.0721` m.

## Caller obligations and limits

All supplied timestamps must use one caller-defined clock domain. The caller
must not subtract or compare timestamps from different domains; the domain is
not encoded in `Observation`, and this version does not synchronize clocks.
Age is calculated from **capture**, not receipt, time. The validator rejects
unusable observation timestamps but cannot establish that a caller's chosen
clock domain represents real-world synchronized time. A first sample uses
`last_capture_time_s=None`; later callers must retain the prior accepted capture
time in that same domain.

The caller must provide already-transformed metric `x_error_m` and `y_error_m`
in one documented frame, verify the calibration behind `calibration_version`,
and account for any camera-to-tool offset. This gate stores no frame or
transform and only checks that the calibration label is nonblank. `CENTERED`
means a supplied position error is within one numerical tolerance; it does
not establish low speed, dwell time, correct pickup-point alignment, mission
authorization, or successful payload capture. The provisional data type also
lacks an operation ID, uncertainty, and cross-clock conversion.
