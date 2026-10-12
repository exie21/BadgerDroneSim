"""Bounded, receive-only MAVLink heartbeat smoke check for D0."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time


def _configuration() -> tuple[str, int, float, Path]:
    host = os.environ.get("SMOKE_BIND_HOST", "0.0.0.0")
    port = int(os.environ.get("SMOKE_BIND_PORT", "14551"))
    timeout_s = float(os.environ.get("SMOKE_TIMEOUT_S", "30"))
    evidence_path = Path(os.environ.get("SMOKE_EVIDENCE_PATH", "/state/telemetry-smoke.json"))
    if not host or not 1 <= port <= 65535 or timeout_s <= 0:
        raise ValueError("invalid receive-only telemetry smoke configuration")
    return host, port, timeout_s, evidence_path


def main() -> int:
    host, port, timeout_s, evidence_path = _configuration()
    from pymavlink import mavutil

    connection = mavutil.mavlink_connection(f"udpin:{host}:{port}")
    deadline = time.monotonic() + timeout_s
    heartbeat_count = 0
    vehicle_system_id: int | None = None
    while time.monotonic() < deadline:
        message = connection.recv_match(blocking=True, timeout=min(1.0, deadline - time.monotonic()))
        if message is None or message.get_type() != "HEARTBEAT":
            continue
        heartbeat_count += 1
        vehicle_system_id = message.get_srcSystem()
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(
                {
                    "status": "ok",
                    "heartbeat_count": heartbeat_count,
                    "vehicle_system_id": vehicle_system_id,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"received heartbeat from vehicle system {vehicle_system_id}", flush=True)
        return 0
    print(f"no MAVLink heartbeat received within {timeout_s:g} seconds", file=sys.stderr, flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
