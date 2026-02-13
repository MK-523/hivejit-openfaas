#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

REQUESTS="${REQUESTS:-12000}"
PROFILE_REQUESTS="${PROFILE_REQUESTS:-36000}"
INVOKES="${INVOKES:-16}"
PROFILE_ITERS="${PROFILE_ITERS:-3}"
BENCHMARKS="${BENCHMARKS:-dacapo-lusearch dacapo-h2}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
FIGURE_DIR="${FIGURE_DIR:-../../docs/figures}"
PLOT_RESULTS="${PLOT_RESULTS:-1}"

PROFILE_ROOT_BASE="profiles/$RUN_ID"
RESULT_DIR_BASE="results/$RUN_ID"
ARTIFACT_DIR_BASE="artifacts/$RUN_ID"

read -r -a BENCHMARK_LIST <<< "$BENCHMARKS"
if (( ${#BENCHMARK_LIST[@]} == 0 )); then
  echo "BENCHMARKS must contain at least one benchmark" >&2
  exit 1
fi

slugify() {
  printf "%s" "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9._-' '-'
}

mkdir -p "$PROFILE_ROOT_BASE" "$RESULT_DIR_BASE" "$ARTIFACT_DIR_BASE"

for benchmark in "${BENCHMARK_LIST[@]}"; do
  benchmark_slug="$(slugify "$benchmark")"
  PROFILE_ROOT="$PROFILE_ROOT_BASE/$benchmark_slug"
  RESULT_DIR="$RESULT_DIR_BASE/$benchmark_slug"
  ARTIFACT_DIR="$ARTIFACT_DIR_BASE/$benchmark_slug"
  figure_prefix="python-profile-specialization-$benchmark_slug"
  mkdir -p "$PROFILE_ROOT" "$RESULT_DIR" "$ARTIFACT_DIR"

  echo "== Measure generic cold invocations ($benchmark) =="
  "$PYTHON_BIN" runner.py \
    --label "python-generic" \
    --benchmark "$benchmark" \
    --requests "$REQUESTS" \
    --iterations "$INVOKES" \
    --csv "$RESULT_DIR/python-generic.csv"

  for iter_count in $PROFILE_ITERS; do
    profile_dir="$PROFILE_ROOT/${iter_count}-profiles"
    mkdir -p "$profile_dir"

    echo "== Export runtime profiles from $iter_count generic invocations ($benchmark) =="
    for i in $(seq 1 "$iter_count"); do
      "$PYTHON_BIN" handler.py \
        --benchmark "$benchmark" \
        --requests "$PROFILE_REQUESTS" \
        --seed "$i" \
        --profile-out "$profile_dir/invoke-$i.json" \
        --json > "$profile_dir/result-$i.json"
    done

    echo "== Generate specialization artifact from profile cache ($benchmark) =="
    artifact="$ARTIFACT_DIR/specialized-${iter_count}.py"
    "$PYTHON_BIN" profile_codegen.py --out "$artifact" "$profile_dir"/invoke-*.json

    echo "== Validate specialized artifact checksum ($benchmark) =="
    generic_check="$("$PYTHON_BIN" handler.py --benchmark "$benchmark" --requests 1000 --seed 99 --json)"
    specialized_check="$("$PYTHON_BIN" handler.py --benchmark "$benchmark" --requests 1000 --seed 99 --artifact "$artifact" --json)"
    "$PYTHON_BIN" -c 'import json, sys; a=json.loads(sys.argv[1]); b=json.loads(sys.argv[2]); raise SystemExit(0 if a["checksum"] == b["checksum"] else 1)' "$generic_check" "$specialized_check"

    echo "== Measure specialized cold invocations for $iter_count-profile artifact ($benchmark) =="
    "$PYTHON_BIN" runner.py \
      --label "python-specialized-${iter_count}" \
      --benchmark "$benchmark" \
      --requests "$REQUESTS" \
      --iterations "$INVOKES" \
      --artifact "$artifact" \
      --csv "$RESULT_DIR/python-specialized-${iter_count}.csv"
  done

  if [[ "$PLOT_RESULTS" == "1" ]]; then
    echo "== Render figures ($benchmark) =="
    "$PYTHON_BIN" plot_results.py \
      --results "$RESULT_DIR" \
      --out-dir "$FIGURE_DIR" \
      --prefix "$figure_prefix"
  fi
done

echo
echo "Artifacts:"
echo "  profiles:  $PROFILE_ROOT_BASE"
echo "  artifacts: $ARTIFACT_DIR_BASE"
echo "  results:   $RESULT_DIR_BASE"
if [[ "$PLOT_RESULTS" == "1" ]]; then
  echo "  figures:   $FIGURE_DIR/python-profile-specialization-*.svg"
fi
