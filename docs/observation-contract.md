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
| `received_time_s` | Receipt timestamp; stored, but **not currently checked** by this validator. |
| `x_error_m`, `y_error_m` | Supplied horizontal metric errors in meters. |
| `valid_pose` | Caller-supplied pose-valid flag; only `True` passes. |
| `calibration_version` | Nonblank string identifying the caller's calibration. |

`ObservationDecision` is a frozen dataclass with `status` and
`horizontal_error_m`. The latter is `None` for every rejected status; for
`VALID` or `CENTERED` it is `hypot(x_error_m, y_error_m)` in meters. `status` is
an `ObservationStatus` member: `VALID`, `CENTERED`, `STALE`, `WRONG_TARGET`,
`INVALID_POSE`, `OUT_OF_ORDER`, or `FUTURE`.

`validate_observation(observation, expected_target_id, now_s,
last_capture_time_s, max_age_s=0.2, centered_tolerance_m=0.15)` returns an
`ObservationDecision`. The caller supplies the expected target, current time,
and previous accepted capture time. Both thresholds must be positive; a
non-positive value raises `ValueError` before an observation is classified.

## Decision order and boundaries

The first matching rule wins:

1. `WRONG_TARGET`: `target_id` is `None`, an empty string, or unequal to
   `expected_target_id`.
2. `INVALID_POSE`: `valid_pose` is not exactly `True`, `calibration_version` is
   not a nonblank string, or either metric error is missing, boolean,
   nonnumeric, or nonfinite.
3. `FUTURE`: `capture_time_s > now_s`.
4. `OUT_OF_ORDER`: `capture_time_s <= last_capture_time_s` (duplicates count).
5. `STALE`: `now_s - capture_time_s > max_age_s`.
6. `INVALID_POSE`: the computed horizontal error is nonfinite, including
   numeric overflow in `hypot`.
7. Otherwise `CENTERED` when horizontal error is
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
Age is calculated from **capture**, not receipt, time. The current validator
does not validate `received_time_s` or the finiteness of timestamp inputs, so
callers must check those before relying on a decision. It expects a comparable
`last_capture_time_s`; a first-sample `None` is not supported yet.

The caller must provide already-transformed metric `x_error_m` and `y_error_m`
in one documented frame, verify the calibration behind `calibration_version`,
and account for any camera-to-tool offset. This gate stores no frame or
transform and only checks that the calibration label is nonblank. `CENTERED`
means a supplied position error is within one numerical tolerance; it does
not establish low speed, dwell time, correct pickup-point alignment, mission
authorization, or successful payload capture. The provisional data type also
lacks an operation ID, uncertainty, and cross-clock conversion.
