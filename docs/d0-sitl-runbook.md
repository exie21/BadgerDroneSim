# D0: read-only SITL telemetry foundation

This profile is a workstation-only integration check. It proves that one
ArduCopter SITL instance can emit MAVLink telemetry through MAVLink Router to a
receive-only Python process. It does not arm, take off, upload a mission, send
MAVLink commands, use a camera, expose a host port, or touch hardware.

## Topology and ownership

`sitl` owns the simulated flight controller and its native physics.
`router` is the only D0 transport owner: it connects to SITL's TCP 5760
endpoint, then forwards packets on the internal Compose network to the
telemetry process at UDP 14551. `telemetry` only binds that UDP port and waits
for a `HEARTBEAT`; it creates no MAVLink sender and has no vehicle-control
code. The Compose network is internal and no service publishes host ports.

The SITL endpoint follows ArduPilot's documented `--no-mavproxy` behavior.
MAVLink Router's TCP client and normal UDP endpoint behavior follow its
documented endpoint model. D0 deliberately does not add a Mission Planner/GCS
endpoint because that needs a later routing-loop and independent-link review.

## Pinned inputs

| Input | Immutable revision |
| --- | --- |
| ArduPilot Copter | `Copter-4.7.1`, `dbe792162d06cab66c3475fd5556bf7a120f119e` |
| MAVLink Router | `v4`, `42529d55b665e0a9a29e424e186f514c56c2e5b5` |
| pymavlink | `2.4.50` |
| Ubuntu base | `ubuntu@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55` |

The build Dockerfiles resolve those source commits and build locally. This is
an x86_64 workstation simulation profile, not a Jetson image or a claim of
Jetson/CSI/GPU support.

## Run and validate

From WSL, at the repository root:

```sh
docker compose -f compose/d0.compose.yaml up --build --abort-on-container-exit --exit-code-from telemetry
```

Success requires the `telemetry` service to exit `0`, print a received vehicle
system ID, and write `artifacts/d0/telemetry/telemetry-smoke.json` with
`"status": "ok"`. The artifact directory is intentionally ignored by Git.

Always clean up the internal containers and network after the check:

```sh
docker compose -f compose/d0.compose.yaml down --remove-orphans
```

If the smoke check times out, collect `docker compose -f compose/d0.compose.yaml
logs` before bringing it down. Do not work around a timeout by adding a command
sender, host networking, a serial device, or an external GCS endpoint.

## Boundary for the next stage

D0 is only transport evidence. Before a GCS endpoint, mission upload, mode
change, `LANDING_TARGET` stream, precision-loiter experiment, camera simulator,
or payload mock is added, recheck the selected firmware behavior and update the
native-alignment decision in [ADR 001](adr/001-native-alignment-handoff.md).

Primary references: [ArduPilot SITL](https://ardupilot.org/dev/docs/using-sitl-for-ardupilot-testing.html),
[ArduPilot SITL architecture](https://ardupilot.org/dev/docs/sitl-simulator-software-in-the-loop.html),
and [MAVLink Router endpoints](https://github.com/mavlink-router/mavlink-router#detailed-description-of-capabilities).
