#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT_DIR/prototypes/julia-openfaas-redis-precompile/run_openfaas_redis_julia_precompile.sh" "$@"
