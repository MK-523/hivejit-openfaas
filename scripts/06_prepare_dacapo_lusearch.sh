#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

DACAPO_BENCHMARKS_DIR="${DACAPO_BENCHMARKS_DIR:-/Users/maheshk/Downloads/dacapobench/benchmarks}"
DACAPO_JAR="${DACAPO_JAR:-$DACAPO_BENCHMARKS_DIR/dacapo-evaluation-git-4e3de06d.jar}"
DACAPO_DATA_DIR="${DACAPO_DATA_DIR:-$DACAPO_BENCHMARKS_DIR/dacapo-evaluation-git-4e3de06d}"
DEST_DIR="${DEST_DIR:-generated/fn/lib}"

if [ ! -f "$DACAPO_JAR" ]; then
  echo "DaCapo jar not found: $DACAPO_JAR" >&2
  exit 1
fi

if [ ! -d "$DACAPO_DATA_DIR/dat/lusearch" ] || [ ! -d "$DACAPO_DATA_DIR/jar/lusearch" ]; then
  echo "DaCapo lusearch data root must contain dat/lusearch and jar/lusearch: $DACAPO_DATA_DIR" >&2
  exit 1
fi

mkdir -p "$DEST_DIR"
rsync -a "$DACAPO_JAR" "$DEST_DIR/dacapo.jar"
rsync -a "$DACAPO_DATA_DIR/" "$DEST_DIR/dacapo/"

echo "Prepared DaCapo lusearch build context:"
echo "  jar:  $DEST_DIR/dacapo.jar"
echo "  data: $DEST_DIR/dacapo"
