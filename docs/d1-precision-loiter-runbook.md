# D1: native Precision Loiter SITL experiment

D1 is a workstation-only experiment for the boundary approved in
[ADR 001](adr/001-native-alignment-handoff.md): a simulated companion source
provides target data and ArduPilot's own Precision Loiter controller performs
the lateral hold. Mission Planner and the operator remain responsible for the
mission, modes, arming, takeoff, altitude, and landing.

It is deliberately separate from D0. D0 remains a read-only telemetry check;
D1 adds a loopback-only GCS connection and a single restricted target-data
ingress. Neither profile represents a Jetson image, a camera, a real aircraft,
or a payload operation.

## Topology and authority

```text
Mission Planner (operator, host only)
            | TCP 127.0.0.1:5761
            v
  MAVLink Router <---- TCP ----> ArduCopter SITL
       ^  |                         native Precision Loiter controller
       |  | UDP telemetry
       |  v
       | Synthetic fixed-ground-target source
       | local NED target + SITL LOCAL_POSITION_NED/ATTITUDE
       +---- UDP LANDING_TARGET only (MAVLink message 149)
            |
            +---- UDP receive-only target-evidence check
```

The router publishes the TCP server only as `127.0.0.1:5761`; it is not a LAN
or hardware interface. The synthetic source has a separate inbound router
endpoint with `AllowMsgIdIn = 149`, so the router drops every source message
except `LANDING_TARGET`. Its code has no API for velocity, position, yaw,
arming, takeoff, land, mode, mission, parameter, or payload commands.
The separate `target-evidence` service receives routed traffic but does not send
anything; it exits successfully only after validating three metric target
messages and writes `artifacts/d1/evidence/landing-target-evidence.json`.

Mission Planner is intentionally not restricted by that target-source filter:
the operator uses it as the ordinary GCS to configure SITL and choose modes.
This does not grant any authority to the companion source.

## What the synthetic target means

The D1 source sets a fixed simulated pickup point in ArduPilot local NED
coordinates (default: north 5 m, east 0 m, down 0 m). It receives only
`LOCAL_POSITION_NED` and `ATTITUDE` from SITL, recomputes the target's
vehicle-relative body-FRD vector, and emits a metric `LANDING_TARGET` at 5 Hz.
It publishes nothing until both state messages are fresh (default maximum age:
0.5 s). `time_usec` is source boot time and does not need synchronization with
the flight controller.

Each target message uses the documented metric form: `MAV_FRAME_BODY_FRD` (12),
`position_valid=1`, `x` forward, `y` right, `z` down, and Euclidean `distance`.
The source's target number is 0. This tests a stationary-world target; it is
not a visual detection, an AprilTag integration, a calibrated camera frame,
or a bridge from the existing `Observation` contract. That future bridge must
provide the missing body-frame transform, range/height, target identity,
calibration evidence, and source-health policy before it can replace D1's
synthetic data.

## Run in SITL only

Docker Desktop must be running with the WSL integration that contains this
repository enabled. From the repository root in WSL:

```sh
docker compose -f compose/d1.compose.yaml up --build
```

Wait until the `precision-target` logs show a first `published
LANDING_TARGET` line and the `target-evidence` service reports that it verified
three messages. Its JSON evidence must have `"status": "ok"`. In Mission
Planner, connect with connection type **TCP** to `127.0.0.1:5761`. Do not use
this profile against a physical flight controller.

Before flight, in SITL only:

1. Set `PLND_ENABLED = 1` and reboot SITL so Precision Landing parameters are
   exposed.
2. Set `PLND_TYPE = 1` for MAVLink `LANDING_TARGET` input.
3. Configure an auxiliary switch option as function 39 (`PrecLoiter Enable`).
4. Use Mission Planner to verify the target data arrives while disarmed and
   that changing a `D1_TARGET_*` coordinate changes the reported offset.
5. Use an operator-authored staging mission or manual flight to reach a safe
   simulated altitude. The companion does not upload or start that mission.
6. The operator enters Loiter and enables Precision Loiter. The expected D1
   behavior is target-relative lateral holding at the current altitude.
7. The operator disables Precision Loiter or selects the next mode to exit.
   Do not use D1 to test automatic mission resumption, descent, landing, or
   payload actions.

To move the synthetic fixed point before starting the profile, override one or
more Compose environment values, for example:

```sh
D1_TARGET_NORTH_M=3.0 D1_TARGET_EAST_M=-1.0 docker compose -f compose/d1.compose.yaml up --build
```

Do not alter these values while the vehicle is flying until target-loss and
transient behavior have been explicitly tested in SITL.

To inject a controlled simulated target loss, start D1 with a positive stream
duration such as `D1_STREAM_DURATION_S=10`. The target source will then exit
normally after ten seconds without sending a replacement, zero, or cached
target. Observe the native Precision Loiter response and operator exit in SITL;
do not assume it will be appropriate for an eventual payload operation.

Stop and clean up after each run:

```sh
docker compose -f compose/d1.compose.yaml down --remove-orphans
```

## Required evidence and stop conditions

Record the selected SITL firmware, Precision Landing parameters, target
coordinates, mode/switch transitions, target-source logs, and the operator's
observed hold behavior. A useful first success is: in Loiter with function 39
enabled, changing the simulated ground target causes the vehicle to hold over
that target without any companion movement command.

Stop the experiment if target messages stop, target state becomes stale,
router connectivity is lost, the observed motion is unexpected, or operator
control is unclear. D1 has no automatic recovery behavior. Testing stale data,
target loss, router restart, clean restart, and operator exit is required
before expanding scope.

## Pinned inputs and references

D1 uses the same pinned ArduPilot Copter-4.7.1 commit
`dbe792162d06cab66c3475fd5556bf7a120f119e`, MAVLink Router v4 commit
`42529d55b665e0a9a29e424e186f514c56c2e5b5`, and pymavlink `2.4.50` as D0.

ArduPilot documents that Precision Loiter uses the Precision Landing backend,
requires Loiter plus auxiliary function 39, and uses MAVLink input when
`PLND_TYPE=1`. Its MAVLink guidance specifies metric body-FRD fields with
`position_valid=1` when x/y/z are known, at no less than 2 Hz. MAVLink Router
documents TCP server endpoints, UDP server/normal endpoints, and message-ID
allow filters used by this profile.

- [ArduPilot: Precision Landing and Loiter](https://ardupilot.org/copter/docs/precision-landing-and-loiter.html)
- [ArduPilot: MAVLink Precision Landing](https://ardupilot.org/dev/docs/mavlink-precision-landing.html)
- [MAVLink: LANDING_TARGET](https://mavlink.io/en/messages/common.html#LANDING_TARGET)
- [Pinned MAVLink Router configuration sample](https://github.com/mavlink-router/mavlink-router/blob/42529d55b665e0a9a29e424e186f514c56c2e5b5/examples/config.sample)
