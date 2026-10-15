FROM ubuntu@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55 AS builder

ARG MAVLINK_ROUTER_COMMIT
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        build-essential ca-certificates git meson ninja-build pkg-config systemd \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --recurse-submodules https://github.com/mavlink-router/mavlink-router.git /opt/mavlink-router \
    && git -C /opt/mavlink-router checkout --detach "${MAVLINK_ROUTER_COMMIT}" \
    && git -C /opt/mavlink-router submodule update --init --recursive

WORKDIR /opt/mavlink-router
RUN meson setup build --buildtype=release --prefix=/usr/local \
    && ninja -C build

FROM ubuntu@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55

ARG ROUTER_CONFIG=containers/router/main.conf
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install --yes --no-install-recommends libsystemd0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/mavlink-router/build/src/mavlink-routerd /usr/local/bin/mavlink-routerd
COPY ${ROUTER_CONFIG} /etc/mavlink-router/main.conf

USER 1000:1000
ENTRYPOINT ["/usr/local/bin/mavlink-routerd", "-c", "/etc/mavlink-router/main.conf"]
