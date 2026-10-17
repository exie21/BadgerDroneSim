FROM ubuntu@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55

ARG ARDUPILOT_COMMIT
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        build-essential ca-certificates ccache file gawk git python3 python3-dev python3-pip \
        python3-venv wget xterm zlib1g-dev \
    && python3 -m pip install --break-system-packages --no-cache-dir \
        "empy==3.3.4" "pexpect==4.9.0" \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git /opt/ardupilot \
    && git -C /opt/ardupilot checkout --detach "${ARDUPILOT_COMMIT}" \
    && git -C /opt/ardupilot submodule update --init --recursive

WORKDIR /opt/ardupilot
RUN ./waf configure --board sitl \
    && ./waf copter

COPY containers/sitl/d1-telemetry.param /opt/badger/d1-telemetry.param

USER 1000:1000
WORKDIR /state
ENTRYPOINT ["python3", "/opt/ardupilot/Tools/autotest/sim_vehicle.py"]
CMD ["--vehicle", "ArduCopter", "--no-mavproxy", "--no-rebuild", "--speedup", "1"]
