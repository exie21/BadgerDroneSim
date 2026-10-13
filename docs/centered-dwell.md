# Centered-observation dwell

`CenteredDwell` is a pure, simulation-friendly timing gate for metric target
observations that have already passed the observation validator. It uses an
internal `ObservationSequence`, so an observation must be new, in-order, fresh,
for the expected target, and classified as `CENTERED` before it contributes to
dwell.

The first accepted centered sample starts a run at zero seconds. Each following
accepted centered sample continues that run only when its capture time is later
than the prior centered sample and the capture-time gap is no greater than
`max_gap_s`. The run duration is the current capture time less the run's first
capture time. `dwell_met` becomes true only when that duration reaches
`required_dwell_s`.

Any non-centered decision—including `VALID`, stale, invalid, wrong-target,
future, duplicate, or out-of-order data—ends the run. A gap larger than
`max_gap_s` also starts a new run. `reset()` is the only way to begin a new
operation or simulation clock epoch; time moving backward never resets state.

This is visual position evidence only. `dwell_met` does **not** prove low
vehicle speed, correct pickup-tool alignment, mission/operator authorization,
actuator success, payload attachment, or safe flight behavior. Those remain
separate gates owned by the native ArduPilot/Mission Planner workflow and later
payload verification work.
