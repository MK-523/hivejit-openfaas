#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
RUNS="${RUNS:-3}"
JAVA_BIN="${JAVA_BIN:-java}"
DACAPO_JAR="${DACAPO_JAR:-generated/fn/lib/dacapo.jar}"
DACAPO_ITERATIONS="${DACAPO_ITERATIONS:-1}"
DACAPO_THREADS="${DACAPO_THREADS:-}"
DACAPO_SIZE="${DACAPO_SIZE:-}"
RESULT_DIR="${RESULT_DIR:-measurements/dacapo-lusearch/$RUN_ID}"
FIGURE_DIR="${FIGURE_DIR:-docs/figures}"

mkdir -p "$RESULT_DIR" "$FIGURE_DIR"

if [ ! -f "$DACAPO_JAR" ]; then
  echo "Missing $DACAPO_JAR. Run scripts/06_prepare_dacapo_lusearch.sh first." >&2
  exit 1
fi

if [ ! -d "generated/fn/lib/dacapo/dat/lusearch" ]; then
  echo "Missing generated/fn/lib/dacapo/dat/lusearch. Run scripts/06_prepare_dacapo_lusearch.sh first." >&2
  exit 1
fi

csv="$RESULT_DIR/local-lusearch.csv"
printf 'label,iteration,wall_ms,dacapo_ms,requests,rc\n' > "$csv"

for i in $(seq 1 "$RUNS"); do
  log="$RESULT_DIR/local-lusearch-$i.log"
  scratch="$RESULT_DIR/scratch-$i"
  logdir="$RESULT_DIR/dacapo-log-$i"
  cmd=("$JAVA_BIN" -jar "$DACAPO_JAR" --scratch-directory "$scratch" --log-directory "$logdir")
  if [ -n "$DACAPO_THREADS" ]; then
    cmd+=(-t "$DACAPO_THREADS")
  fi
  if [ -n "$DACAPO_SIZE" ]; then
    cmd+=(-s "$DACAPO_SIZE")
  fi
  cmd+=(lusearch -n "$DACAPO_ITERATIONS")

  start_ns=$(python3 - <<'PY'
import time
print(time.monotonic_ns())
PY
)
  set +e
  "${cmd[@]}" >"$log" 2>&1
  rc=$?
  set -e
  end_ns=$(python3 - <<'PY'
import time
print(time.monotonic_ns())
PY
)

  wall_ms=$(python3 - <<PY
print(f"{($end_ns - $start_ns) / 1_000_000:.3f}")
PY
)
  dacapo_ms=$(python3 - "$log" <<'PY'
import re
import sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
matches = re.findall(r"lusearch PASSED in ([0-9]+) msec", text)
print(matches[-1] if matches else "")
PY
)
  requests=$(python3 - "$log" <<'PY'
import re
import sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
matches = re.findall(r"processed ([0-9]+) requests", text)
print(matches[-1] if matches else "")
PY
)
  printf 'local,%s,%s,%s,%s,%s\n' "$i" "$wall_ms" "$dacapo_ms" "$requests" "$rc" >> "$csv"
  if [ "$rc" -ne 0 ]; then
    echo "Run $i failed with rc=$rc; see $log" >&2
    exit "$rc"
  fi
done

python3 scripts/plot_dacapo_lusearch.py \
  --csv "$csv" \
  --out-dir "$FIGURE_DIR" \
  --prefix "dacapo-lusearch-local"

echo "Results: $csv"
echo "Figures: $FIGURE_DIR/dacapo-lusearch-local-*.svg"
