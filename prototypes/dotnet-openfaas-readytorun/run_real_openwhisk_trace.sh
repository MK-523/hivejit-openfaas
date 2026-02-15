#!/usr/bin/env bash
# Collect real OpenFaaS C#/.NET data at the same request scale/churn positions
# as the OpenWhisk reference plot. No synthetic trace generation is used.
set -euo pipefail

PROTO_DIR="$(cd "$(dirname "$0")" && pwd)"

export RUN_ID="${RUN_ID:-real-openwhisk-dotnet-$(date +%Y%m%d-%H%M%S)}"
export MEASURE_MODE="${MEASURE_MODE:-churn}"
export CHURN_INVOCATIONS="${CHURN_INVOCATIONS:-2000}"
export SEGMENT_LENGTH="${SEGMENT_LENGTH:-0}"
export CHURN_AT="${CHURN_AT:-1,112,478,800,1044,1283,1679,1790}"
export POST_READY_DELAY="${POST_READY_DELAY:-0}"
export SCENARIOS="${SCENARIOS:-serve-hot serve-mixed}"
export VARIANTS="${VARIANTS:-il r2r nativeaot}"
export PUSH_IMAGE="${PUSH_IMAGE:-0}"
export KIND_CLUSTER="${KIND_CLUSTER:-openfaas}"
export DEPLOY_BACKEND="${DEPLOY_BACKEND:-direct}"
export IMAGE_PREFIX="${IMAGE_PREFIX:-dotnet-openfaas-r2r}"
export DOTNET_BIN="${DOTNET_BIN:-/private/tmp/dotnet-sdk/dotnet}"
export DOTNET_CLI_HOME="${DOTNET_CLI_HOME:-/private/tmp/dotnet-home}"
export NUGET_PACKAGES="${NUGET_PACKAGES:-/private/tmp/nuget-packages}"

exec "$PROTO_DIR/run_openfaas_readytorun.sh"
