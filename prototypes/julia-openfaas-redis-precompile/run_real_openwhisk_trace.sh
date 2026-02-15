#!/usr/bin/env bash
# Collect real OpenFaaS Julia data at the same request scale/churn positions
# as the OpenWhisk reference plot. No synthetic trace generation is used.
set -euo pipefail

PROTO_DIR="$(cd "$(dirname "$0")" && pwd)"

export RUN_ID="${RUN_ID:-real-openwhisk-julia-$(date +%Y%m%d-%H%M%S)}"
export WORKLOADS="${WORKLOADS:-lusearch h2 eclipse}"
export INVOCATIONS="${INVOCATIONS:-2000}"
export SEGMENT_LENGTH="${SEGMENT_LENGTH:-0}"
export CHURN_AT="${CHURN_AT:-1,112,478,800,1044,1283,1679,1790}"
export AOT_PROFILE_COUNTS="${AOT_PROFILE_COUNTS:-5 10}"
export POST_READY_DELAY="${POST_READY_DELAY:-0}"
export SYSIMAGE_POST_READY_DELAY="${SYSIMAGE_POST_READY_DELAY:-0}"
export PUSH_IMAGE="${PUSH_IMAGE:-0}"
export KIND_CLUSTER="${KIND_CLUSTER:-openfaas}"
export DEPLOY_BACKEND="${DEPLOY_BACKEND:-direct}"

exec "$PROTO_DIR/run_aot_profile_cache_comparison.sh"
