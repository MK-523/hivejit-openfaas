ARG OF_WATCHDOG_VERSION=0.9.16

FROM ghcr.io/openfaas/of-watchdog:${OF_WATCHDOG_VERSION} AS watchdog

FROM mcr.microsoft.com/dotnet/sdk:8.0-alpine AS nativeaot-build

ARG BUILD_LABEL=nativeaot
ARG RID=linux-musl-arm64

RUN apk add --no-cache clang build-base zlib-dev
WORKDIR /src
COPY DotnetOpenFaas.csproj ./
RUN dotnet restore DotnetOpenFaas.csproj -r "${RID}" -p:PublishAot=true
COPY Program.cs ./
RUN dotnet publish DotnetOpenFaas.csproj \
    -c Release \
    -r "${RID}" \
    --self-contained true \
    --no-restore \
    -o /out \
    -p:PublishAot=true \
    -p:InvariantGlobalization=true \
    -p:StripSymbols=true && \
    echo "$BUILD_LABEL" > /out/build-label

FROM alpine:3.20 AS runtime

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

FROM alpine:3.20 AS nativeaot-runtime

ARG BUILD_LABEL=nativeaot

RUN apk --no-cache add ca-certificates libgcc libstdc++
COPY --from=watchdog /fwatchdog /usr/bin/fwatchdog
COPY --from=nativeaot-build /out/ /app/
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
