#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

: "${OPENFAAS_SETUP_REPO:?source .env first}"
: "${GEORGE_JDK_REPO:?source .env first}"
: "${GEORGE_JDK_BRANCH:?source .env first}"

mkdir -p work

if [ ! -d work/openfaas-setup/.git ]; then
  git clone "$OPENFAAS_SETUP_REPO" work/openfaas-setup
fi

if [ ! -d work/jdk25u/.git ]; then
  git clone "$GEORGE_JDK_REPO" work/jdk25u
fi

cd work/jdk25u
git fetch origin
git checkout "$GEORGE_JDK_BRANCH"

cd "$ROOT_DIR"
rm -rf generated
mkdir -p generated/fn/src/main/java/com/example
mkdir -p generated/k8s
mkdir -p generated/openfaas

cp templates/fn/* generated/fn/
cp -R templates/fn/src generated/fn/
cp templates/k8s/* generated/k8s/
cp templates/openfaas/* generated/openfaas/

python3 - <<'PY'
from pathlib import Path
import os
root = Path('generated')
repl = {
    '__FUNCTION_IMAGE__': os.environ['FUNCTION_IMAGE'],
    '__ARTIFACT_KEY__': os.environ['ARTIFACT_KEY'],
}
for p in root.rglob('*'):
    if p.is_file():
        text = p.read_text()
        for k, v in repl.items():
            text = text.replace(k, v)
        p.write_text(text)
PY

echo "Prepared sources under $ROOT_DIR/generated"
