# ADR 001: operator-controlled handoff to native Precision Loiter

Status: Accepted — simulation-first scope  
Date: 2026-10-11

## Context

The first useful capability is horizontal alignment above a pickup target at a
height defined by a Mission Planner-authored ArduPilot mission. The legacy
workspace used a companion-side ROS sequencer that switched to GUIDED and
streamed velocity and yaw setpoints. That creates a second movement-control
path and is outside this project's scope.

ArduPilot Precision Loiter uses the `LANDING_TARGET` backend while in Loiter
mode. It can hold laterally above a target without initiating a landing.

## Decision

For the first SITL alignment experiment:

1. Mission Planner authors the AUTO route, including the fixed mission altitude
   and a pickup staging location. ArduPilot executes that route and altitude.
2. At staging, an operator explicitly enters Loiter and enables ArduPilot's
   Precision Loiter auxiliary function.
3. The companion sends only fresh, validated target measurements through its
   future single MAVLink gateway. It does not send velocity, position, yaw-rate,
   takeoff, landing, arming, or mode-change commands.
4. The operator explicitly exits the alignment phase. The first experiment
   ends after target-relative hold is demonstrated; it does not resume AUTO or
   attempt a payload action automatically.

For a future metric `LANDING_TARGET` adapter, the exact selected ArduPilot
firmware must be rechecked. The current documented form uses `MAV_FRAME_BODY_FRD`,
`position_valid=1`, populated metric `x`, `y`, `z`, and `distance`.
The required perception-to-target-data boundary is tracked in
[the precision-target contract](../precision-target-contract.md); the existing
2-D observation validator is not itself a MAVLink adapter.

## Consequences

- The first experiment tests the boundary we need: validated perception data
  reaches ArduPilot's native lateral controller at a mission-defined height.
- It does not prove pickup, vertical clearance, yaw alignment, payload action,
  automatic mission continuation, target-loss safety, or real-aircraft behavior.
- The operator-controlled handoff is deliberately less autonomous, but avoids
  inventing unproven command authority while mode/mission semantics are still
  being validated in SITL.
- A later change to automatic handoff, mission continuation, descent, yaw, or
  payload actuation requires a new decision and SITL evidence.

## Required SITL evidence before expanding scope

- Mission upload/readback and arrival at the staging point at the configured
  altitude.
- Explicit Loiter and Precision Loiter entry, plus target-relative hold from a
  bounded fresh measurement stream.
- Target-loss, stale-input, operator-exit, router/gateway-loss, and clean
  restart observations.
- No companion movement setpoints or unapproved flight-changing commands.

## References

- [ArduPilot: Precision Landing and Loiter](https://ardupilot.org/copter/docs/precision-landing-and-loiter.html)
- [ArduPilot: MAVLink Precision Landing](https://ardupilot.org/dev/docs/mavlink-precision-landing.html)
- [MAVLink: Landing Target Protocol](https://mavlink.io/en/services/landing_target.html)
