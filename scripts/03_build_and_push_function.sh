#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

: "${FUNCTION_IMAGE:?source .env first}"
: "${GEORGE_BUILD_OUT:?source .env first}"

if [ ! -x "$GEORGE_BUILD_OUT/jdk/bin/java" ]; then
  echo "George JDK not found at $GEORGE_BUILD_OUT/jdk. Run scripts/01_build_george_jdk.sh first."
  exit 1
fi

rm -rf generated/fn/george-jdk
mkdir -p generated/fn/george-jdk
cp -a "$GEORGE_BUILD_OUT/jdk/." generated/fn/george-jdk/

cd generated/fn
docker build -t "$FUNCTION_IMAGE" .
docker push "$FUNCTION_IMAGE"

echo "Built and pushed $FUNCTION_IMAGE"
