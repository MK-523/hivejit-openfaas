#!/usr/bin/env bash
set -euo pipefail

PROTO_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$PROTO_DIR/../.." && pwd)"

FUNCTION_NAME="${FUNCTION_NAME:-dotnet-r2r}"
FUNCTION_NAMESPACE="${FUNCTION_NAMESPACE:-openfaas-fn}"
OPENFAAS_NAMESPACE="${OPENFAAS_NAMESPACE:-openfaas}"
OPENFAAS_GATEWAY="${OPENFAAS_GATEWAY:-http://127.0.0.1:8080}"

RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
DOTNET_BIN="${DOTNET_BIN:-dotnet}"
RID="${RID:-linux-musl-arm64}"
IMAGE_PREFIX="${IMAGE_PREFIX:-dotnet-openfaas-r2r}"
PUSH_IMAGE="${PUSH_IMAGE:-0}"
KIND_CLUSTER="${KIND_CLUSTER:-openfaas}"
OF_WATCHDOG_VERSION="${OF_WATCHDOG_VERSION:-0.9.16}"

MEASURE_REQUESTS="${MEASURE_REQUESTS:-80}"
MEASURE_WARMUP="${MEASURE_WARMUP:-10}"
MEASURE_CONCURRENCY="${MEASURE_CONCURRENCY:-1}"
HANDLER_ITERATIONS="${HANDLER_ITERATIONS:-250000}"
SCENARIOS="${SCENARIOS:-serve-hot serve-mixed}"

BUILD_ROOT="$PROTO_DIR/build/$RUN_ID"
RESULT_ROOT="$PROTO_DIR/.runs/$RUN_ID/results"
PROJECT="$PROTO_DIR/DotnetOpenFaas.csproj"
URL="$OPENFAAS_GATEWAY/function/$FUNCTION_NAME"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required command: $1" >&2
    exit 1
  fi
}

login_openfaas() {
  if [[ -n "${OPENFAAS_PASSWORD:-}" ]]; then
    printf "%s" "$OPENFAAS_PASSWORD" | faas-cli login --username "${OPENFAAS_USERNAME:-admin}" --password-stdin --gateway "$OPENFAAS_GATEWAY"
    return
  fi

  if kubectl -n "$OPENFAAS_NAMESPACE" get secret basic-auth >/dev/null 2>&1; then
    local password
    password="$(kubectl -n "$OPENFAAS_NAMESPACE" get secret basic-auth -o jsonpath='{.data.basic-auth-password}' | base64 --decode)"
    printf "%s" "$password" | faas-cli login --username admin --password-stdin --gateway "$OPENFAAS_GATEWAY"
  else
    echo "OpenFaaS basic-auth secret not found; assuming faas-cli is already logged in or auth is disabled."
  fi
}

publish_variant() {
  local label="$1"
  local ready_to_run="$2"
  local out_dir="$BUILD_ROOT/$label"

  mkdir -p "$out_dir"
  echo "== Publish $label self-contained RID=$RID ReadyToRun=$ready_to_run =="
  "$DOTNET_BIN" publish "$PROJECT" -c Release -r "$RID" --self-contained true -o "$out_dir" \
    -p:PublishReadyToRun="$ready_to_run" \
    -p:PublishSingleFile=true \
    -p:UseAppHost=true \
    -p:InvariantGlobalization=true
}

build_load_deploy() {
  local label="$1"
  local image="${IMAGE_PREFIX}:${RUN_ID}-${label}"
  local publish_dir="build/$RUN_ID/$label"

  echo "== Build image $image =="
  docker build \
    --build-arg "PUBLISH_DIR=$publish_dir" \
    --build-arg "BUILD_LABEL=$label" \
    --build-arg "OF_WATCHDOG_VERSION=$OF_WATCHDOG_VERSION" \
    -t "$image" "$PROTO_DIR"

  if [[ "$PUSH_IMAGE" == "1" ]]; then
    echo "== Push image $image =="
    docker push "$image"
  fi
  if [[ -n "$KIND_CLUSTER" ]]; then
    echo "== Load image $image into kind cluster $KIND_CLUSTER =="
    kind load docker-image "$image" --name "$KIND_CLUSTER"
  fi

  echo "== Deploy $FUNCTION_NAME with $label =="
  export OPENFAAS_GATEWAY DOTNET_OPENFAAS_IMAGE="$image" BUILD_LABEL="$label"
  faas-cli deploy -f "$PROTO_DIR/stack.yml" --gateway "$OPENFAAS_GATEWAY"
  kubectl label "deployment/$FUNCTION_NAME" -n "$FUNCTION_NAMESPACE" \
    com.openfaas.scale.min=1 \
    com.openfaas.scale.max=1 \
    com.openfaas.scale.zero=false \
    --overwrite
  kubectl scale "deployment/$FUNCTION_NAME" -n "$FUNCTION_NAMESPACE" --replicas=1
  kubectl rollout status "deployment/$FUNCTION_NAME" -n "$FUNCTION_NAMESPACE" --timeout=240s
}

measure() {
  local build_label="$1"
  local scenario="$2"
  local out_prefix="dotnet-openfaas-${build_label}-${scenario}"

  python3 "$ROOT_DIR/scripts/http_invoke_latency.py" \
    --url "$URL/work" \
    --method POST \
    --header "Content-Type: application/json" \
    --body "{\"scenario\":\"$scenario\",\"iterations\":$HANDLER_ITERATIONS}" \
    --requests "$MEASURE_REQUESTS" \
    --warmup "$MEASURE_WARMUP" \
    --concurrency "$MEASURE_CONCURRENCY" \
    --timeout 120 \
    --label "$out_prefix" \
    --csv "$RESULT_ROOT/${out_prefix}.csv" \
    --summary "$RESULT_ROOT/${out_prefix}.json" \
    --svg "$RESULT_ROOT/${out_prefix}.svg"
}

require_cmd docker
require_cmd faas-cli
require_cmd kubectl
require_cmd kind
require_cmd python3
require_cmd "$DOTNET_BIN"

mkdir -p "$BUILD_ROOT" "$RESULT_ROOT"

login_openfaas
publish_variant "il" "false"
publish_variant "r2r" "true"

for label in il r2r; do
  build_load_deploy "$label"
  for scenario in $SCENARIOS; do
    echo "== Measure $label $scenario =="
    measure "$label" "$scenario"
  done
done

echo
echo "Done."
echo "  run:      $RUN_ID"
echo "  results:  $RESULT_ROOT"
