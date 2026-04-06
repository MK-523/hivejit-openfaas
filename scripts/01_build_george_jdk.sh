#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

: "${GEORGE_WORKDIR:?source .env first}"
: "${GEORGE_BUILD_OUT:?source .env first}"

if [ ! -d "$GEORGE_WORKDIR" ]; then
  echo "Missing $GEORGE_WORKDIR. Run scripts/00_clone_and_prepare.sh first."
  exit 1
fi

cd "$GEORGE_WORKDIR"

CONFIGURE_CMD=(bash configure)
if [ -n "${BOOT_JAVA_HOME:-}" ]; then
  CONFIGURE_CMD+=(--with-boot-jdk="$BOOT_JAVA_HOME")
fi
if [ -n "${GEORGE_CONFIGURE_ARGS:-}" ]; then
  # shellcheck disable=SC2206
  EXTRA=( ${GEORGE_CONFIGURE_ARGS} )
  CONFIGURE_CMD+=("${EXTRA[@]}")
fi

"${CONFIGURE_CMD[@]}"
make images

JDK_DIR=$(find build -type d -path '*/images/jdk' | head -n 1)
if [ -z "$JDK_DIR" ]; then
  echo "Could not find built JDK under build/*/images/jdk"
  exit 1
fi

rm -rf "$GEORGE_BUILD_OUT"
mkdir -p "$GEORGE_BUILD_OUT"
cp -a "$JDK_DIR" "$GEORGE_BUILD_OUT/jdk"

echo "George JDK copied to $GEORGE_BUILD_OUT/jdk"
"$GEORGE_BUILD_OUT/jdk/bin/java" -version
