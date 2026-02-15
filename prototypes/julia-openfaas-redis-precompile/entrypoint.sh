#!/usr/bin/env bash
# entrypoint.sh – startup for Julia OpenFaaS precompile-cache experiments.
#
# JULIA_CACHE_MODE controls which profile-artifact path is taken:
#   baseline  – no precompile cache; Julia JIT-compiles on first request (default)
#   populate  – same as baseline but Julia records --trace-compile to JULIA_TRACE_FILE
#   redis     – pull precompile trace from Redis before starting the handler;
#               JULIA_PRECOMPILE_FILE is set so handler.jl includes it at startup
#   sysimage  – start Julia with -J /app/sysimage.so (AOT-compiled via PackageCompiler);
#               sysimage must be baked into the image at build time
set -euo pipefail

MODE="${JULIA_CACHE_MODE:-baseline}"
TRACE_FILE="${JULIA_TRACE_FILE:-/tmp/julia-trace.jl}"
PRECOMPILE_FILE="${JULIA_PRECOMPILE_FILE:-/tmp/julia-precompile.jl}"
SYSIMAGE_PATH="${JULIA_SYSIMAGE_PATH:-/app/sysimage.so}"

echo "[entrypoint] mode=$MODE trace_file=$TRACE_FILE precompile_file=$PRECOMPILE_FILE"

if [[ "$MODE" == "redis" ]]; then
    echo "[entrypoint] pulling precompile trace from Redis"
    python3 /app/cachectl.py pull --out "$PRECOMPILE_FILE" 2>&1 || {
        echo "[entrypoint] WARN: failed to pull precompile trace from Redis; starting cold"
    }
    if [[ -f "$PRECOMPILE_FILE" ]]; then
        echo "[entrypoint] precompile trace pulled: $(wc -l < "$PRECOMPILE_FILE") lines"
        export JULIA_PRECOMPILE_FILE="$PRECOMPILE_FILE"
    else
        echo "[entrypoint] no precompile trace found; starting cold"
        unset JULIA_PRECOMPILE_FILE
    fi
fi

JULIA_EXTRA_FLAGS=()
if [[ "$MODE" == "populate" ]]; then
    echo "[entrypoint] trace-compile active: output to $TRACE_FILE"
    JULIA_EXTRA_FLAGS+=("--trace-compile=$TRACE_FILE")
fi

if [[ "$MODE" == "sysimage" ]]; then
    if [[ -f "$SYSIMAGE_PATH" ]]; then
        echo "[entrypoint] AOT sysimage: $SYSIMAGE_PATH ($(du -sh "$SYSIMAGE_PATH" | cut -f1))"
        JULIA_EXTRA_FLAGS+=("-J" "$SYSIMAGE_PATH")
    else
        echo "[entrypoint] WARN: sysimage not found at $SYSIMAGE_PATH; falling back to cold JIT"
    fi
fi

export JULIA_TRACE_FILE="$TRACE_FILE"

exec julia \
    --startup-file=no \
    --compile=yes \
    --optimize=2 \
    "${JULIA_EXTRA_FLAGS[@]}" \
    /app/handler.jl
