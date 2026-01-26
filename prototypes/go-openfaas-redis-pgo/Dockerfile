ARG OF_WATCHDOG_VERSION=0.9.16

FROM golang:1.22-alpine AS build

WORKDIR /src
COPY go.mod ./
COPY . .

ARG PGO_PROFILE=
ARG BUILD_LABEL=nopgo

RUN set -eux; \
    if [ -n "$PGO_PROFILE" ]; then \
      test -s "$PGO_PROFILE"; \
      go build -buildvcs=false -trimpath -pgo="$PGO_PROFILE" -ldflags="-s -w" -o /out/handler .; \
    else \
      go build -buildvcs=false -trimpath -pgo=off -ldflags="-s -w" -o /out/handler .; \
    fi; \
    echo "$BUILD_LABEL" > /out/build-label

FROM ghcr.io/openfaas/of-watchdog:${OF_WATCHDOG_VERSION} AS watchdog

FROM alpine:3.20

ARG BUILD_LABEL=nopgo

RUN apk --no-cache add ca-certificates
COPY --from=watchdog /fwatchdog /usr/bin/fwatchdog
COPY --from=build /out/handler /usr/local/bin/handler
COPY --from=build /out/build-label /usr/local/share/go-pgo-build-label

ENV mode="http" \
    upstream_url="http://127.0.0.1:8082" \
    http_port="8080" \
    fprocess="/usr/local/bin/handler" \
    HANDLER_ADDR=":8082" \
    BUILD_LABEL="${BUILD_LABEL}" \
    GOMAXPROCS="1"

HEALTHCHECK --interval=5s CMD [ -e /tmp/.lock ] || exit 1
CMD ["fwatchdog"]
