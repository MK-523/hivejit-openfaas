ARG OF_WATCHDOG_VERSION=0.9.16

FROM ghcr.io/openfaas/of-watchdog:${OF_WATCHDOG_VERSION} AS watchdog

FROM alpine:3.20

ARG PUBLISH_DIR=build/il
ARG BUILD_LABEL=il

RUN apk --no-cache add ca-certificates libgcc libstdc++
COPY --from=watchdog /fwatchdog /usr/bin/fwatchdog
COPY ${PUBLISH_DIR}/ /app/
RUN chmod +x /app/DotnetOpenFaas && echo "$BUILD_LABEL" > /app/build-label

ENV mode="http" \
    upstream_url="http://127.0.0.1:8082" \
    http_port="8080" \
    fprocess="/app/DotnetOpenFaas" \
    HANDLER_ADDR="http://127.0.0.1:8082" \
    DOTNET_SYSTEM_GLOBALIZATION_INVARIANT="1" \
    BUILD_LABEL="${BUILD_LABEL}"

HEALTHCHECK --interval=5s CMD [ -e /tmp/.lock ] || exit 1
CMD ["fwatchdog"]
