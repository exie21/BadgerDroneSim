# D1: native Precision Loiter SITL experiment

D1 is a workstation-only experiment for the boundary approved in
[ADR 001](adr/001-native-alignment-handoff.md): a simulated companion source
provides target data and ArduPilot's own Precision Loiter controller performs
the lateral hold. Mission Planner and the operator remain responsible for the
mission, modes, arming, takeoff, altitude, and landing.

**Execution status:** Stage 1 packet-path evidence has passed locally: the
source published a plausible metric target and the receive-only service
validated three routed packets. Stage 2 has not been run. Do not claim a
successful Precision Loiter hold until the operator evidence below is
collected from a running SITL profile.

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
       |  | TCP telemetry
       |  v
       | Synthetic fixed-ground-target source (router TCP client)
       | local NED target + SITL GLOBAL_POSITION_INT/ATTITUDE
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
coordinates (default: north 5 m, east 0 m, down 0 m). It receives
`GLOBAL_POSITION_INT` and `ATTITUDE` from SITL, derives vehicle local NED from
the configured SITL home and relative altitude, then recomputes the target's
vehicle-relative body-FRD vector and emits a metric `LANDING_TARGET` at 5 Hz.
It publishes nothing until both state messages are fresh (default maximum age:
0.5 s). `time_usec` is source boot time and does not need synchronization with
the flight controller. This GPS-to-local conversion is D1 simulation-only;
real perception must satisfy the precision-target contract instead.

Each target message uses the documented metric form: `MAV_FRAME_BODY_FRD` (12),
`position_valid=1`, `x` forward, `y` right, `z` down, and Euclidean `distance`.
The source uses router TCP to read SITL's MAVLink 1 telemetry and a separate
MAVLink 2 encoder for the metric target packet, because these fields are
MAVLink 2 extensions. The source's target number is 0. This tests a
stationary-world target; it is not a visual detection, an AprilTag integration,
a calibrated camera frame, or a bridge from the existing `Observation`
contract. That future bridge must provide the missing body-frame transform,
range/height, target identity, calibration evidence, and source-health policy
before it can replace D1's synthetic data.

## Docker preflight

Docker Desktop must be running with the WSL integration that contains this
repository enabled. From the repository root in WSL:

```sh
docker info
docker compose -f compose/d1.compose.yaml config --quiet
```

`docker info` must print a server version. If it reports an inaccessible
`docker_engine` pipe, do not continue: start Docker Desktop, enable the WSL
distribution that contains this repository, then open a new WSL terminal and
repeat the preflight. A successful Compose config parse alone does not prove
that an engine is available.

## Stage 1: packet-path evidence

This bounded run proves SITL-to-source telemetry, synthetic target generation,
router forwarding, and the receive-only packet check. It does not involve
Mission Planner or a mode change:

```sh
docker compose -f compose/d1.compose.yaml up --build --abort-on-container-exit --exit-code-from target-evidence
```

The D1 SITL overlay configures its own first-link stream rates
(`MAV1_POSITION=10` and `MAV1_EXTRA1=10`) so it emits
`GLOBAL_POSITION_INT` and `ATTITUDE` without a companion request message.
The source emits only metric `LANDING_TARGET`; it has no movement or
mission-control output. During SITL startup it rejects the all-zero GPS state
until the reported position is within 1 km of the configured simulated home,
so it cannot publish a target from an uninitialized world origin.

D1 starts SITL with `--wipe`, which removes only its ignored local simulation
EEPROM state before applying this overlay. This makes Stage 1 reproducible, but
also means Mission Planner parameter changes do not survive a D1 restart.

Success requires `target-evidence` to exit `0`, log that it verified three
metric target messages, and write
`artifacts/d1/evidence/landing-target-evidence.json` with `"status": "ok"`
and `"evidence_status": "VALID"`. Review the source logs as well: they must
show a `published LANDING_TARGET` line. Preserve the artifact and relevant
Compose logs as local evidence; artifacts are intentionally ignored by Git.

Stop and inspect failures before retrying:

```sh
docker compose -f compose/d1.compose.yaml logs
docker compose -f compose/d1.compose.yaml down --remove-orphans
```

Do not work around a failure by adding a movement command, loosening the router
message filter, host networking, hardware devices, or a real flight controller.

## Stage 2: operator-controlled Precision Loiter

After Stage 1 passes, start the long-running SIM-only profile:

```sh
docker compose -f compose/d1.compose.yaml up --build -d
docker compose -f compose/d1.compose.yaml logs -f precision-target target-evidence
```

Wait until the source publishes a target and the evidence service has succeeded.
In Mission Planner, connect with connection type **TCP** to `127.0.0.1:5761`.
Do not use this profile against a physical flight controller.

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

Record the following for every Stage 2 attempt: firmware/Compose revision,
`PLND_*` settings, target coordinates, Mission Planner connection, selected
mode and auxiliary-switch transition, evidence JSON, source/router/SITL logs,
and observed vehicle response. An accepted parameter write or GCS action is
not evidence of a mode transition or target-relative hold.

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

The required D1 result is a four-part checklist:

1. **Packet path:** the evidence artifact is `ok` and all sampled target
   packets are metric body-FRD messages.
2. **GCS isolation:** Mission Planner reaches the loopback endpoint and retains
   ordinary operator control; the companion source remains limited to message
   149.
3. **Native hold:** in Loiter with function 39 enabled, changing the simulated
   ground target causes target-relative lateral hold at the current altitude,
   without any companion movement command.
4. **Loss and exit:** a stopped target stream and an explicit operator exit are
   observed and recorded. Neither must trigger companion-controlled recovery,
   mission resumption, descent, or payload action.

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
