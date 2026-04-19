#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p work/george-jdk

if [ ! -d work/jdk25u/.git ]; then
  echo "Missing work/jdk25u. Run scripts/00_clone_and_prepare.sh first."
  exit 1
fi

export DOCKER_DEFAULT_PLATFORM="${DOCKER_DEFAULT_PLATFORM:-linux/arm64}"

# Official OpenJDK build container (no apt needed)
IMAGE=openjdk:24-slim

docker pull --platform "${DOCKER_DEFAULT_PLATFORM}" $IMAGE

docker run --rm \
  --platform "${DOCKER_DEFAULT_PLATFORM}" \
  -v "$ROOT:/src" \
  -w /src \
  $IMAGE \
  bash -lc '
    set -euo pipefail

    BOOT_JAVA_HOME=/usr/local/openjdk-24

    cd /src/work/jdk25u

    bash configure \
      --with-boot-jdk="$BOOT_JAVA_HOME" \
      --enable-headless-only=yes \
      --with-jvm-variants=server \
      --with-debug-level=release

    make images

    OUT_DIR="$(find build -type d -path "*/images/jdk" | head -n 1)"
    if [ -z "$OUT_DIR" ]; then
      echo "Could not find built JDK image"
      exit 1
    fi

    rm -rf /src/work/george-jdk
    cp -a "$OUT_DIR" /src/work/george-jdk

    echo "=== BUILD SUCCESS ==="
    /src/work/george-jdk/bin/java -version
  '
