FROM ubuntu@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55

ARG PYMAVLINK_VERSION
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates python3 python3-pip \
    && python3 -m pip install --break-system-packages --no-cache-dir "pymavlink==${PYMAVLINK_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

COPY src/badger_precision_target /app/badger_precision_target
WORKDIR /app
USER 1000:1000
ENTRYPOINT ["python3", "-m", "badger_precision_target.synthetic"]
