#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

: "${OPENFAAS_GATEWAY:?source .env first}"
: "${OPENFAAS_NAMESPACE:?source .env first}"
: "${FUNCTION_NAMESPACE:?source .env first}"

PASSWORD=$(kubectl -n "$OPENFAAS_NAMESPACE" get secret basic-auth -o jsonpath='{.data.basic-auth-password}' | base64 --decode)
echo "$PASSWORD" | faas-cli login --username admin --password-stdin --gateway "$OPENFAAS_GATEWAY"

faas-cli deploy -f generated/openfaas/stack.yml --gateway "$OPENFAAS_GATEWAY"
kubectl patch deployment profile-fn -n "$FUNCTION_NAMESPACE" --patch-file generated/k8s/function-patch.yaml
kubectl rollout status deployment/profile-fn -n "$FUNCTION_NAMESPACE" --timeout=180s

echo "Function deployed."
