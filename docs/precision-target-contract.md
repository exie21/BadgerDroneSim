# Precision-target input contract

This is the boundary between a future perception source and the one permitted
companion-to-ArduPilot data message: metric MAVLink `LANDING_TARGET`. It does
not authorize mode changes, motion setpoints, missions, payload actions,
arming, takeoff, descent, or landing. ArduPilot owns lateral motion through
native Precision Loiter.

## Why the current observation type cannot drive MAVLink

`badger_core.observation.Observation` is a pure, provisional 2-D
horizontal-error gate. It has no explicit coordinate frame, z/range,
transform chain, source identity, sequence, operation context, or uncertainty.
It must not be converted directly into `LANDING_TARGET`.

The D1 synthetic source is not a perception implementation either. It obtains
a fixed simulated NED target and fresh SITL state, then computes an already
body-FRD vector. It proves the protocol route and native receiver boundary,
not a camera, AprilTag, or ML system.

## Required future sample

A future adapter must produce one immutable sample containing at least:

| Field | Requirement |
| --- | --- |
| `operation_id` | Non-empty operator-authorized attempt ID. It changes for every new attempt and simulator reset. |
| `source_id` | Non-empty camera/perception source-instance ID. Source restart changes it or resets the operation. |
| `target_id` | Detected target identity; ID `0` is valid only when configured as expected. |
| `sequence` | Strictly increasing non-negative source sequence for this operation and target. |
| `capture_monotonic_s` | Capture time in the gate's companion monotonic-clock domain; never receipt time. |
| `received_monotonic_s` | Gate arrival time in that same clock domain; provenance only. |
| `body_frd_x_m`, `body_frd_y_m`, `body_frd_z_m` | Finite metre values relative to the vehicle: forward, right, down. |
| `pose_valid` | Exactly true only for a usable metric pose. A detector hit alone is insufficient. |
| `calibration_version` | Non-blank version covering intrinsics, distortion, and camera-to-body extrinsics. |
| `transform_version` | Non-blank version covering attitude-at-capture interpolation and camera/tool geometry. |
| `quality` | Finite source-defined quality or uncertainty with a documented configured threshold. |

For the first real adapter, capture and gate times must use one proven
companion monotonic clock. Never subtract camera-device, wall-clock, ROS-sim,
flight-controller boot, or GCS timestamps from it. If that cannot be supplied,
the clock conversion must be designed and validated first. MAVLink `time_usec`
is generated separately as source boot time; it is not freshness evidence.

## One geometry conversion

The adapter performs this conversion exactly once:

```text
detector image coordinates
  -> camera optical metric pose (right, down, forward)
  -> vehicle body FRD vector (forward, right, down)
  -> MAVLink LANDING_TARGET x, y, z
```

Use vehicle attitude at frame capture, not a later attitude. Apply camera
extrinsics and any pickup-tool geometry once, and retain that evidence in
`transform_version`. A camera optical frame is not body FRD. NED/world values
are simulation or geometry details and must be resolved before this boundary.

For each accepted sample, output MAVLink frame `MAV_FRAME_BODY_FRD` (12),
`position_valid=1`, x/y/z from the body-FRD values, and distance
`sqrt(x*x + y*y + z*z)`. Do not assume target yaw is consumed by Precision
Loiter.

## Forwarding rules

The future gate is configured with one expected operation, source, target,
calibration version, transform version, maximum capture age, and
source-specific quality policy. It forwards a sample only if all are true:

1. Operation, source, and target match the configured values exactly.
2. Timestamps and metric values are finite non-booleans, and receipt is not
   earlier than capture.
3. Pose is valid, version labels are non-blank and match configuration, and
   quality meets the documented policy.
4. Sequence and capture time are strictly newer than the last accepted sample.
5. `now_monotonic_s - capture_monotonic_s` is not older than the configured
   maximum age. Equality is accepted.
6. Any configured plausibility test passes. Such a test rejects bad input; it
   never clamps or invents a target position.

The gate records last sequence/capture time only after full acceptance and
resets explicitly for a new operation, source restart, calibration/transform
change, or simulation clock reset. Rejections do not advance state.

An absent, stale, invalid, reordered, wrong-target, wrong-operation, or
wrong-calibration sample produces no `LANDING_TARGET`. Never retimestamp a
cached pose, use a fictitious zero vector for target loss, or repeat old data.
The stream stops on loss; native ArduPilot loss behavior is demonstrated in
SITL rather than guessed here.

## Validation before replacing D1

Before connecting a camera source, add deterministic tests for frame axes,
attitude-at-capture timing, camera/tool offsets, timestamp domains,
duplicates/reordering, calibration mismatch, quality rejection, and target
loss. Then prove in SITL that the router still accepts only `LANDING_TARGET`
from the companion, operator exit works, and stale input/source/router restart
does not create an invented target. Rendered-camera truth must remain outside
the production perception path.

Exact camera, marker/range source, uncertainty model, and pickup geometry are
hardware decisions still pending. This contract records their required output
without prematurely choosing them.

## References

- [ADR 001: operator-controlled native Precision Loiter](adr/001-native-alignment-handoff.md)
- [D1 Precision Loiter SITL runbook](d1-precision-loiter-runbook.md)
- [Existing provisional observation contract](observation-contract.md)
- [ArduPilot MAVLink Precision Landing](https://ardupilot.org/dev/docs/mavlink-precision-landing.html)
- [MAVLink LANDING_TARGET definition](https://mavlink.io/en/messages/common.html#LANDING_TARGET)
