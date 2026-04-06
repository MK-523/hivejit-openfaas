#!/usr/bin/env bash
set -euo pipefail

: "${OPENFAAS_GATEWAY:?source .env first}"
: "${FUNCTION_NAMESPACE:?source .env first}"
: "${ARTIFACT_KEY:?source .env first}"

URL="$OPENFAAS_GATEWAY/function/profile-fn"

echo "Sending warmup traffic..."
for i in $(seq 1 50); do
  curl -fsS "$URL?name=Mahesh-$i" >/dev/null
  sleep 0.05
done

echo "First restart: force dump/upload"
kubectl rollout restart deployment/profile-fn -n "$FUNCTION_NAMESPACE"
kubectl rollout status deployment/profile-fn -n "$FUNCTION_NAMESPACE" --timeout=180s

sleep 3

echo "Second restart: expect pull/load"
kubectl rollout restart deployment/profile-fn -n "$FUNCTION_NAMESPACE"
kubectl rollout status deployment/profile-fn -n "$FUNCTION_NAMESPACE" --timeout=180s

POD=$(kubectl get pods -n "$FUNCTION_NAMESPACE" -l faas_function=profile-fn -o jsonpath='{.items[0].metadata.name}')

echo "---- recent logs ----"
kubectl logs -n "$FUNCTION_NAMESPACE" "$POD" --tail=200

echo "Smoke test done. Look for:"
echo "- PROFILE_PULL_HIT or PROFILE_PULL_MISS"
echo "- GEORGE_LOAD_OK"
echo "- GEORGE_DUMP_OK"
echo "Artifact key: $ARTIFACT_KEY"
