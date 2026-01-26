#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT_DIR/prototypes/go-openfaas-redis-pgo/run_openfaas_redis_pgo.sh" "$@"
