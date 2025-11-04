# HiveJIT + OpenFaaS end-to-end starter

This bundle gives you runnable code and scripts for the shortest path to an end-to-end profile-reuse demo:

- local `kind` cluster
- OpenFaaS install
- Redis artifact store
- George JDK build hook
- Java function wrapper that calls George's internal `ProfileCheckpoint.load(Path)` / `dump(Path)` reflectively
- OpenFaaS function image with pull-before-start and push-on-termination
- deployment and smoke test scripts

## What this proves

It proves the lifecycle you care about:

1. start pod
2. pull profile artifact
3. start JVM
4. load profile if present
5. serve requests
6. on SIGTERM dump profile
7. upload dumped profile
8. next pod pulls and loads it

## Assumptions

You have these installed locally:

- docker
- kind
- kubectl
- helm
- faas-cli
- git
- bash
- a boot JDK (21+ is safest for building the UCLA JDK fork)

## Quick start

```bash
cd hivejit_openfaas_bundle
cp env.example .env
$EDITOR .env
source .env

bash scripts/00_clone_and_prepare.sh
bash scripts/01_build_george_jdk.sh
bash scripts/02_install_openfaas.sh
bash scripts/03_build_and_push_function.sh
bash scripts/04_deploy_function.sh
bash scripts/05_smoke_test.sh
```

## Required `.env` fields

Set at least:

```bash
export IMAGE_REPO=docker.io/YOUR_DOCKERHUB_USERNAME
export FUNCTION_IMAGE_NAME=profile-fn
export FUNCTION_IMAGE_TAG=latest
```

If you prefer GHCR:

```bash
export IMAGE_REPO=ghcr.io/YOUR_GITHUB_USERNAME
export FUNCTION_IMAGE_NAME=profile-fn
export FUNCTION_IMAGE_TAG=latest
```

Then login before pushing.

## What to expect

- first deployment: `PROFILE_PULL_MISS`
- after traffic + rollout restart: old pod logs `GEORGE_DUMP_OK`
- after second restart: new pod logs `GEORGE_LOAD_OK`

## Notes

- The function uses reflection to call George's internal API so it can compile cleanly without requiring compile-time access to internal modules.
- The artifact store is Redis first because it is the easiest way to prove correctness.
- Once this works, swap Redis for a richer metadata/object store.
