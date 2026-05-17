#!/usr/bin/env bash
# Run the Julia precompile-cache OpenFaaS/Redis experiment and produce warmup plots.
#
# Three-phase experiment (mirrors the JAX and JVM prototypes):
#
#   Phase 0 – baseline
#       Deploy Julia function with JULIA_CACHE_MODE=baseline.
#       Run churn benchmark.  Each pod restart triggers full JIT warmup.
#
#   Phase 1 – populate
#       Deploy with JULIA_CACHE_MODE=populate (Julia --trace-compile active).
#       Warm the pod, then hit /_/cache/push to export the precompile trace to Redis.
#
#   Phase 2 – redis
#       Deploy with JULIA_CACHE_MODE=redis.
#       entrypoint.sh pulls the trace from Redis before starting the handler.
#       handler.jl include()s it so LLVM compilation is done before first request.
#       Run churn benchmark.  Pod restarts show much smaller latency spikes.
#
# Outputs (under .runs/<RUN_ID>/results/):
#   <workload>-baseline.csv / .json / -warmup.svg
#   <workload>-redis.csv    / .json / -warmup.svg
#
# Required tools: docker kubectl python3
# Optional tools: faas-cli kind
set -euo pipefail

PROTO_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$PROTO_DIR/../.." && pwd)"
PLOT_SCRIPT="$PROTO_DIR/plot_churn.py"

FUNCTION_NAME="${FUNCTION_NAME:-julia-precompile}"
FUNCTION_NAMESPACE="${FUNCTION_NAMESPACE:-openfaas-fn}"
OPENFAAS_NAMESPACE="${OPENFAAS_NAMESPACE:-openfaas}"
OPENFAAS_GATEWAY="${OPENFAAS_GATEWAY:-http://127.0.0.1:8080}"

RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
WORKLOADS="${WORKLOADS:-lusearch h2 eclipse}"
SIZE="${SIZE:-1}"
INVOCATIONS="${INVOCATIONS:-60}"
SEGMENT_LENGTH="${SEGMENT_LENGTH:-20}"
POPULATE_INVOCATIONS="${POPULATE_INVOCATIONS:-200}"
WATCHDOG_TIMEOUT="${WATCHDOG_TIMEOUT:-180s}"
POST_READY_DELAY="${POST_READY_DELAY:-0}"
REDIS_POST_READY_DELAY="${REDIS_POST_READY_DELAY:-8}"

IMAGE_PREFIX="${IMAGE_PREFIX:-ttl.sh/${FUNCTION_NAME}-${USER:-user}}"
PUSH_IMAGE="${PUSH_IMAGE:-1}"
KIND_CLUSTER="${KIND_CLUSTER:-}"
DEPLOY_BACKEND="${DEPLOY_BACKEND:-direct}"
REDIS_HOST="${REDIS_HOST:-redis.openfaas-fn.svc.cluster.local}"
REDIS_PORT="${REDIS_PORT:-6379}"

ARTIFACT_ROOT="$PROTO_DIR/.runs/$RUN_ID"
RESULT_ROOT="$ARTIFACT_ROOT/results"
MANIFEST_ROOT="$ARTIFACT_ROOT/k8s"

read -r -a WORKLOAD_LIST <<< "$WORKLOADS"

slugify() { printf "%s" "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9._-' '-'; }
require_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "missing required command: $1" >&2; exit 1; }; }

login_openfaas() {
  [[ -n "${OPENFAAS_PASSWORD:-}" ]] && {
    printf "%s" "$OPENFAAS_PASSWORD" | faas-cli login \
      --username "${OPENFAAS_USERNAME:-admin}" --password-stdin --gateway "$OPENFAAS_GATEWAY"
    return
  }
  kubectl -n "$OPENFAAS_NAMESPACE" get secret basic-auth >/dev/null 2>&1 && {
    local password
    password="$(kubectl -n "$OPENFAAS_NAMESPACE" get secret basic-auth \
      -o jsonpath='{.data.basic-auth-password}' | base64 --decode)"
    printf "%s" "$password" | faas-cli login --username admin --password-stdin --gateway "$OPENFAAS_GATEWAY"
    return
  }
  echo "no basic-auth secret; assuming faas-cli already logged in."
}

build_image() {
  local image="$1"
  echo "== Build Julia precompile image $image =="
  DOCKER_BUILDKIT=1 docker build --target runtime -t "$image" "$PROTO_DIR"
  [[ "$PUSH_IMAGE" == "1" ]] && { echo "== Push $image =="; docker push "$image"; }
  [[ -n "$KIND_CLUSTER" ]] && { echo "== Load into kind $KIND_CLUSTER =="; kind load docker-image "$image" --name "$KIND_CLUSTER"; }
}

build_sysimage_image() {
  local image="$1" n_profiles="$2"
  echo "== Build AOT sysimage image $image (N_PROFILES=$n_profiles) =="
  DOCKER_BUILDKIT=1 docker build \
    --target sysimage-builder \
    --build-arg "N_PROFILES=$n_profiles" \
    -t "$image" "$PROTO_DIR"
  [[ "$PUSH_IMAGE" == "1" ]] && { echo "== Push $image =="; docker push "$image"; }
  [[ -n "$KIND_CLUSTER" ]] && { echo "== Load into kind $KIND_CLUSTER =="; kind load docker-image "$image" --name "$KIND_CLUSTER"; }
}

deploy_direct() {
  local image="$1" mode="$2" label="$3"
  local cache_key="${4:-julia-precompile-trace:default}"
  local manifest="$MANIFEST_ROOT/${FUNCTION_NAME}-${mode}.yaml"
  mkdir -p "$MANIFEST_ROOT"
  cat > "$manifest" <<YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: $FUNCTION_NAME
  namespace: $FUNCTION_NAMESPACE
  labels:
    faas_function: $FUNCTION_NAME
spec:
  replicas: 1
  selector:
    matchLabels:
      faas_function: $FUNCTION_NAME
  template:
    metadata:
      labels:
        faas_function: $FUNCTION_NAME
    spec:
      terminationGracePeriodSeconds: 20
      containers:
        - name: $FUNCTION_NAME
          image: $image
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8080
          env:
            - name: POD_UID
              valueFrom:
                fieldRef:
                  fieldPath: metadata.uid
            - name: BUILD_LABEL
              value: "$label"
            - name: JULIA_CACHE_MODE
              value: "$mode"
            - name: JULIA_CACHE_KEY
              value: "$cache_key"
            - name: REDIS_HOST
              value: "$REDIS_HOST"
            - name: REDIS_PORT
              value: "$REDIS_PORT"
            - name: read_timeout
              value: "$WATCHDOG_TIMEOUT"
            - name: write_timeout
              value: "$WATCHDOG_TIMEOUT"
            - name: exec_timeout
              value: "$WATCHDOG_TIMEOUT"
          livenessProbe:
            httpGet:
              path: /_/health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
          readinessProbe:
            httpGet:
              path: /_/health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: $FUNCTION_NAME
  namespace: $FUNCTION_NAMESPACE
spec:
  selector:
    faas_function: $FUNCTION_NAME
  ports:
    - name: http
      port: 8080
      targetPort: 8080
YAML
  kubectl apply -f "$manifest"
  kubectl rollout status "deployment/$FUNCTION_NAME" -n "$FUNCTION_NAMESPACE" --timeout=300s
}

deploy_function() {
  local image="$1" mode="$2" label="$3" cache_key="${4:-julia-precompile-trace:default}"
  echo "== Deploy $FUNCTION_NAME mode=$mode =="
  if [[ "$DEPLOY_BACKEND" == "direct" ]]; then
    deploy_direct "$image" "$mode" "$label" "$cache_key"
    return
  fi
  JULIA_CACHE_MODE="$mode" BUILD_LABEL="$label" JULIA_JVM_IMAGE="$image" \
    faas-cli deploy -f "$PROTO_DIR/stack.yml" --gateway "$OPENFAAS_GATEWAY"
  kubectl rollout status "deployment/$FUNCTION_NAME" -n "$FUNCTION_NAMESPACE" --timeout=300s
}

measure_workload() {
  local workload="$1" mode="$2"
  local slug
  slug="$(slugify "$workload")-$mode"
  local csv="$RESULT_ROOT/$slug.csv"
  local summary="$RESULT_ROOT/$slug.json"
  local svg="$RESULT_ROOT/$slug-warmup.png"
  local plot_summary="$RESULT_ROOT/$slug-plot-summary.json"
  local post_ready_delay="$POST_READY_DELAY"
  [[ "$mode" == "redis" ]] && post_ready_delay="$REDIS_POST_READY_DELAY"

  echo "== Measure workload=$workload mode=$mode size=$SIZE invocations=$INVOCATIONS =="
  python3 "$PROTO_DIR/run_churn_bench.py" \
    --function    "$FUNCTION_NAME" \
    --namespace   "$FUNCTION_NAMESPACE" \
    --gateway     "$OPENFAAS_GATEWAY" \
    --workload    "$workload" \
    --size        "$SIZE" \
    --invocations "$INVOCATIONS" \
    --segment-length "$SEGMENT_LENGTH" \
    --post-ready-delay "$post_ready_delay" \
    --csv         "$csv" \
    --summary     "$summary"

  python3 "$PLOT_SCRIPT" \
    --csv     "$csv" \
    --out     "$svg" \
    --summary "$plot_summary" \
    --title   "Julia $workload on OpenFaaS — $mode (with container churn + JIT warmup)"
}

populate_per_workload() {
  echo "== Populate: one fresh pod per workload, per-workload Redis key =="
  for workload in "${WORKLOAD_LIST[@]}"; do
    local cache_key="julia-precompile-trace:${workload}"
    echo "== Populate workload=$workload key=$cache_key =="
    deploy_function "$IMAGE" "populate" "${RUN_ID}-populate-${workload}" "$cache_key"
    python3 "$PROTO_DIR/run_churn_bench.py" \
      --function    "$FUNCTION_NAME" \
      --namespace   "$FUNCTION_NAMESPACE" \
      --gateway     "$OPENFAAS_GATEWAY" \
      --workload    "$workload" \
      --size        "$SIZE" \
      --invocations "$POPULATE_INVOCATIONS" \
      --segment-length 0 \
      --export-at   "$POPULATE_INVOCATIONS" \
      --csv         "$RESULT_ROOT/$(slugify "$workload")-populate.csv" \
      --summary     "$RESULT_ROOT/$(slugify "$workload")-populate.json"
  done
}

require_cmd docker
require_cmd kubectl
require_cmd python3
[[ "$DEPLOY_BACKEND" != "direct" ]] && require_cmd faas-cli
[[ -n "$KIND_CLUSTER" ]] && require_cmd kind

mkdir -p "$RESULT_ROOT"

[[ "$DEPLOY_BACKEND" != "direct" ]] && login_openfaas

IMAGE="${IMAGE_PREFIX}:${RUN_ID}"
build_image "$IMAGE"

echo
echo "=== Phase 0: baseline (no precompile cache) ==="
deploy_function "$IMAGE" "baseline" "${RUN_ID}-baseline"
for workload in "${WORKLOAD_LIST[@]}"; do
  measure_workload "$workload" "baseline"
done

echo
echo "=== Phase 1: populate (per-workload trace, per-workload Redis key) ==="
populate_per_workload

echo
echo "=== Phase 2: redis cache (per-workload pod loads only its own trace) ==="
for workload in "${WORKLOAD_LIST[@]}"; do
  cache_key="julia-precompile-trace:${workload}"
  deploy_function "$IMAGE" "redis" "${RUN_ID}-redis-${workload}" "$cache_key"
  measure_workload "$workload" "redis"
done

for N_PROF in 5 10; do
  echo
  echo "=== Phase: AOT sysimage ($N_PROF profile runs) ==="
  SYSIMAGE_TAG="${IMAGE_PREFIX}:${RUN_ID}-sysimage${N_PROF}"
  build_sysimage_image "$SYSIMAGE_TAG" "$N_PROF"
  deploy_function "$SYSIMAGE_TAG" "sysimage" "${RUN_ID}-sysimage${N_PROF}"
  for workload in "${WORKLOAD_LIST[@]}"; do
    measure_workload "$workload" "sysimage${N_PROF}"
  done
done

echo
echo "Done."
echo "  run:     $RUN_ID"
echo "  image:   $IMAGE"
echo "  results: $RESULT_ROOT"
echo
echo "SVG warmup plots:"
find "$RESULT_ROOT" -name "*-warmup.png" | sort | while read -r f; do
  echo "  $f"
done
