#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

: "${CLUSTER_NAME:?source .env first}"
: "${OPENFAAS_NAMESPACE:?source .env first}"
: "${FUNCTION_NAMESPACE:?source .env first}"
: "${REDIS_NAMESPACE:?source .env first}"

if ! kind get clusters | grep -qx "$CLUSTER_NAME"; then
  kind create cluster --name "$CLUSTER_NAME"
fi

kubectl apply -f https://raw.githubusercontent.com/openfaas/faas-netes/master/namespaces.yml || true
helm repo add openfaas https://openfaas.github.io/faas-netes/ || true
helm repo update

helm upgrade --install openfaas openfaas/openfaas \
  --namespace "$OPENFAAS_NAMESPACE" \
  --set functionNamespace="$FUNCTION_NAMESPACE" \
  --set generateBasicAuth=true

kubectl create namespace "$REDIS_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f generated/k8s/redis.yaml

kubectl rollout status deployment/gateway -n "$OPENFAAS_NAMESPACE" --timeout=180s
kubectl rollout status deployment/redis -n "$REDIS_NAMESPACE" --timeout=180s

echo "OpenFaaS and Redis installed."
echo "Run this in another terminal:"
echo "kubectl port-forward -n $OPENFAAS_NAMESPACE svc/gateway 8080:8080"
echo "kubectl port-forward -n $REDIS_NAMESPACE svc/redis 6379:6379"
