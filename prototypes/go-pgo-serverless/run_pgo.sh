#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD="$ROOT/build"
ARTIFACTS="$ROOT/artifacts"
RESULTS="$ROOT/results"
GO_BIN="${GO_BIN:-go}"

if ! command -v "$GO_BIN" >/dev/null 2>&1; then
  echo "SKIP go-pgo-serverless: Go SDK is not installed or GO_BIN is not on PATH" >&2
  exit 2
fi

mkdir -p "$BUILD" "$ARTIFACTS" "$RESULTS"
export GOCACHE="$BUILD/go-cache"
export GOMODCACHE="$BUILD/go-mod-cache"

BASE="$BUILD/profilecache-go-base"
PGO="$BUILD/profilecache-go-pgo"
PROFILE="$ARTIFACTS/train.pprof"
MANIFEST="$ARTIFACTS/train.manifest.json"
LAST="$RESULTS/last.jsonl"

sha256_file() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    sha256sum "$1" | awk '{print $1}'
  fi
}

run_json() {
  local label="$1"
  local binary="$2"
  shift 2
  echo "== $label"
  "$binary" "$@" --json | tee "$RESULTS/$label.json" | tee -a "$LAST"
}

: > "$LAST"

echo "== Build baseline without PGO"
(cd "$ROOT" && "$GO_BIN" build -trimpath -pgo=off -o "$BASE" .)

echo "== Train baseline and export CPU pprof profile"
"$BASE" --scenario train --invocations 4 --iterations 350000 --cpuprofile "$PROFILE" --json \
  | tee "$RESULTS/train.json" \
  | tee -a "$LAST"

PROFILE_SHA="$(sha256_file "$PROFILE")"
PROFILE_BYTES="$(wc -c < "$PROFILE" | tr -d ' ')"
cat > "$MANIFEST" <<EOF
{
  "domain": "go-pgo-serverless",
  "artifact": "cpu-pprof",
  "profile": "$PROFILE",
  "profileBytes": $PROFILE_BYTES,
  "profileSha256": "$PROFILE_SHA",
  "buildImport": "go build -pgo=$PROFILE",
  "cacheKeyFields": ["source hash", "go version", "GOOS", "GOARCH", "scenario/workload shape"]
}
EOF

echo "== Build future binary with imported pprof profile"
(cd "$ROOT" && "$GO_BIN" build -trimpath -pgo="$PROFILE" -o "$PGO" .)

run_json baseline-hot "$BASE" --scenario serve-hot --invocations 6 --iterations 250000
run_json pgo-hot "$PGO" --scenario serve-hot --invocations 6 --iterations 250000
run_json baseline-mixed "$BASE" --scenario serve-mixed --invocations 6 --iterations 250000
run_json pgo-mixed "$PGO" --scenario serve-mixed --invocations 6 --iterations 250000

echo "== Artifacts"
ls -lh "$BUILD" "$ARTIFACTS" "$RESULTS"
