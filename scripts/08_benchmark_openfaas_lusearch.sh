#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

: "${OPENFAAS_GATEWAY:?source .env first}"
: "${FUNCTION_NAMESPACE:?source .env first}"

RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
MEASURE_RUNS="${MEASURE_RUNS:-3}"
WARMUP_RUNS="${WARMUP_RUNS:-3}"
URL="${URL:-$OPENFAAS_GATEWAY/function/profile-fn}"
RESULT_DIR="${RESULT_DIR:-measurements/dacapo-lusearch-openfaas/$RUN_ID}"

mkdir -p "$RESULT_DIR"
csv="$RESULT_DIR/openfaas-lusearch.csv"
printf 'phase,iteration,http_ms,handler_ms,http_code\n' > "$csv"

invoke() {
  phase="$1"
  iteration="$2"
  body="$RESULT_DIR/${phase}-${iteration}.txt"
  meta="$RESULT_DIR/${phase}-${iteration}.curl"
  curl -sS -o "$body" -w '%{time_total},%{http_code}\n' "$URL" > "$meta"
  http_ms=$(python3 - "$meta" <<'PY'
import sys
time_total, _ = open(sys.argv[1], encoding="utf-8").read().strip().split(",", 1)
print(f"{float(time_total) * 1000:.3f}")
PY
)
  http_code=$(cut -d, -f2 "$meta")
  handler_ms=$(python3 - "$body" <<'PY'
import re
import sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
match = re.search(r"elapsed_ms=([0-9]+)", text)
print(match.group(1) if match else "")
PY
)
  printf '%s,%s,%s,%s,%s\n' "$phase" "$iteration" "$http_ms" "$handler_ms" "$http_code" >> "$csv"
}

echo "Measuring before profile load..."
for i in $(seq 1 "$MEASURE_RUNS"); do
  invoke before-profile "$i"
done

echo "Sending lusearch warmup traffic before restart/export..."
for i in $(seq 1 "$WARMUP_RUNS"); do
  invoke warmup "$i" >/dev/null
done

echo "Restarting function to force profile dump/upload, then pull/load..."
kubectl rollout restart deployment/profile-fn -n "$FUNCTION_NAMESPACE"
kubectl rollout status deployment/profile-fn -n "$FUNCTION_NAMESPACE" --timeout=240s
sleep 5
kubectl rollout restart deployment/profile-fn -n "$FUNCTION_NAMESPACE"
kubectl rollout status deployment/profile-fn -n "$FUNCTION_NAMESPACE" --timeout=240s
sleep 5

echo "Measuring after profile load..."
for i in $(seq 1 "$MEASURE_RUNS"); do
  invoke after-profile "$i"
done

echo "Results: $csv"
