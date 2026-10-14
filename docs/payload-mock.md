# Scripted payload mock

`ScriptedPayloadMock` is deterministic, simulation-only test infrastructure.
It accepts a script that maps a request ID to a nonnegative delay and one
terminal `PayloadStatus`: `SUCCEEDED`, `FAILED`, or `UNKNOWN`.

Call `start(request_id, now_s)` to begin a scripted request. It always returns
`IN_PROGRESS`, including for a zero-delay script and for a duplicate start. The
first start time is retained permanently for that request; a duplicate start
does not create another operation or reset completion timing.

Call `poll(request_id, now_s)` for a request that has already started. Before
the original start time plus its scripted delay, the result is `IN_PROGRESS`.
At the exact delay boundary and afterward it is the scripted terminal status.
`UNKNOWN` remains an ambiguous terminal result and must not be treated as
success.

This mock has no serial, Arduino, ROS, MAVLink, ArduPilot, or hardware protocol
behavior. A returned `SUCCEEDED` result proves only the selected simulation
script completed; it is not evidence that a physical pickup occurred.
