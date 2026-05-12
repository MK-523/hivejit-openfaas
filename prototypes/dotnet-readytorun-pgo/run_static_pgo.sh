#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$ROOT/ProfileCacheDotNet.csproj"
BUILD="$ROOT/build"
ARTIFACTS="$ROOT/artifacts"
RESULTS="$ROOT/results"
DOTNET_BIN="${DOTNET_BIN:-dotnet}"
DOTNET_TRACE_BIN="${DOTNET_TRACE_BIN:-dotnet-trace}"
DOTNET_PGO_BIN="${DOTNET_PGO_BIN:-dotnet-pgo}"

if ! command -v "$DOTNET_BIN" >/dev/null 2>&1; then
  echo "SKIP dotnet-static-pgo: .NET SDK is not installed or DOTNET_BIN is not on PATH" >&2
  exit 2
fi

if ! command -v "$DOTNET_TRACE_BIN" >/dev/null 2>&1; then
  echo "SKIP dotnet-static-pgo: dotnet-trace is required for nettrace export" >&2
  exit 2
fi

if ! command -v "$DOTNET_PGO_BIN" >/dev/null 2>&1; then
  echo "SKIP dotnet-static-pgo: dotnet-pgo is required to convert nettrace to MIBC" >&2
  exit 2
fi

rid() {
  case "$(uname -s)-$(uname -m)" in
    Darwin-arm64) echo "osx-arm64" ;;
    Darwin-x86_64) echo "osx-x64" ;;
    Linux-aarch64) echo "linux-arm64" ;;
    Linux-arm64) echo "linux-arm64" ;;
    Linux-x86_64) echo "linux-x64" ;;
    *) echo "" ;;
  esac
}

RID="${RID:-$(rid)}"
if [[ -z "$RID" ]]; then
  echo "Unable to infer RID; set RID explicitly, for example RID=osx-arm64" >&2
  exit 2
fi

TRAIN_DIR="$BUILD/static-pgo-train"
R2R_DIR="$BUILD/static-pgo-r2r"
PGO_R2R_DIR="$BUILD/static-pgo-r2r-with-mibc"
TRACE="$ARTIFACTS/train.nettrace"
MIBC="$ARTIFACTS/train.mibc"
LAST="$RESULTS/static-pgo.jsonl"
PROVIDER="Microsoft-Windows-DotNETRuntime:0x1C000080018:4"

mkdir -p "$TRAIN_DIR" "$R2R_DIR" "$PGO_R2R_DIR" "$ARTIFACTS" "$RESULTS"
: > "$LAST"

echo "== Publish training IL"
"$DOTNET_BIN" publish "$PROJECT" -c Release -o "$TRAIN_DIR" \
  -p:PublishReadyToRun=false \
  -p:UseAppHost=false

TRAIN_DLL="$TRAIN_DIR/ProfileCacheDotNet.dll"

echo "== Execute training run and export nettrace"
"$DOTNET_TRACE_BIN" collect --providers "$PROVIDER" --output "$TRACE" -- \
  "$DOTNET_BIN" "$TRAIN_DLL" --scenario train --invocations 6 --iterations 300000 --json

echo "== Convert nettrace to MIBC profile artifact"
"$DOTNET_PGO_BIN" create-mibc --trace "$TRACE" --output "$MIBC" --reference "$TRAIN_DIR" --compressed

echo "== Publish ReadyToRun without MIBC"
"$DOTNET_BIN" publish "$PROJECT" -c Release -r "$RID" --self-contained false -o "$R2R_DIR" \
  -p:PublishReadyToRun=true \
  -p:UseAppHost=false

echo "== Publish ReadyToRun with imported MIBC"
"$DOTNET_BIN" publish "$PROJECT" -c Release -r "$RID" --self-contained false -o "$PGO_R2R_DIR" \
  -p:PublishReadyToRun=true \
  -p:UseAppHost=false \
  -p:ReadyToRunOptimizationData="$MIBC"

echo "== Compare"
"$DOTNET_BIN" "$R2R_DIR/ProfileCacheDotNet.dll" --scenario serve-hot --invocations 6 --iterations 250000 --json \
  | tee "$RESULTS/r2r-no-mibc-hot.json" \
  | tee -a "$LAST"
"$DOTNET_BIN" "$PGO_R2R_DIR/ProfileCacheDotNet.dll" --scenario serve-hot --invocations 6 --iterations 250000 --json \
  | tee "$RESULTS/r2r-mibc-hot.json" \
  | tee -a "$LAST"
"$DOTNET_BIN" "$R2R_DIR/ProfileCacheDotNet.dll" --scenario serve-mixed --invocations 6 --iterations 250000 --json \
  | tee "$RESULTS/r2r-no-mibc-mixed.json" \
  | tee -a "$LAST"
"$DOTNET_BIN" "$PGO_R2R_DIR/ProfileCacheDotNet.dll" --scenario serve-mixed --invocations 6 --iterations 250000 --json \
  | tee "$RESULTS/r2r-mibc-mixed.json" \
  | tee -a "$LAST"

echo "== Artifacts"
ls -lh "$BUILD" "$ARTIFACTS" "$RESULTS"
