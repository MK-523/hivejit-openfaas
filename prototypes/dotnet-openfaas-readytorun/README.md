# C#/.NET OpenFaaS ReadyToRun Prototype

This prototype runs the C#/.NET workload behind OpenFaaS and compares two
self-contained Linux function images:

```text
IL/JIT function image -> OpenFaaS gateway latency
ReadyToRun function image -> OpenFaaS gateway latency
```

It is not the full static-PGO MIBC loop. It measures the deployable
ReadyToRun artifact path under the same gateway style as the Go/OpenFaaS run.
On OpenFaaS Community Edition, deploying a new function may require a public
image reference. The default script keeps images local (`PUSH_IMAGE=0`) and
loads them into kind; pushing to an external registry should only be done when
the code export is explicitly approved.

Run with a local kind OpenFaaS cluster and a local .NET SDK:

```bash
DOTNET_BIN=/private/tmp/dotnet-sdk/dotnet \
PUSH_IMAGE=0 \
KIND_CLUSTER=openfaas \
IMAGE_PREFIX=dotnet-openfaas-r2r \
bash prototypes/dotnet-openfaas-readytorun/run_openfaas_readytorun.sh
```

Each run writes CSV, JSON summaries, and SVGs under `.runs/<run-id>/results`.
