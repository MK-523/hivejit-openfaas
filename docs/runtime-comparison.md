# Runtime Comparison Graphs

These graphs compare the existing Java/OpenFaaS George JVM HTTP run with fresh
Go and C#/.NET profile-artifact prototype runs.

Generated files:

```text
docs/figures/jvm-go-dotnet-invocation-curves.svg
docs/figures/jvm-go-dotnet-p50-p95.svg
docs/figures/jvm-go-dotnet-comparison-summary.json
```

Regenerate after running the Go and .NET benchmarks:

```bash
bash prototypes/go-pgo-serverless/run_pgo.sh
DOTNET_BIN=/private/tmp/dotnet-sdk/dotnet bash prototypes/dotnet-readytorun-pgo/run_readytorun.sh
python3 scripts/plot_runtime_comparison.py
```

Latest regenerated run:

| Series | mean ms | p50 ms | p95 ms | Note |
| --- | ---: | ---: | ---: | --- |
| Go baseline hot | 11.3 | 11.3 | 11.4 | local handler loop |
| Go PGO hot | 15.5 | 11.2 | 38.0 | one first-invocation outlier |
| Go baseline mixed | 18.4 | 18.5 | 18.9 | local handler loop |
| Go PGO mixed | 18.1 | 18.1 | 18.2 | small improvement |
| .NET IL hot | 18.2 | 18.2 | 19.1 | SDK-only IL/JIT baseline |
| .NET ReadyToRun hot | 11.7 | 11.6 | 12.1 | ReadyToRun artifact |
| .NET IL mixed | 40.0 | 50.2 | 52.2 | SDK-only IL/JIT baseline |
| .NET ReadyToRun mixed | 19.1 | 19.2 | 19.3 | ReadyToRun artifact |

The C#/.NET run used .NET SDK `8.0.420` / runtime `8.0.26` from
`/private/tmp/dotnet-sdk`. ReadyToRun improved p50 by about 36% on the hot
scenario and about 62% on the mixed scenario in this run. The full static-PGO
loop still needs a usable `dotnet-pgo` tool; `dotnet tool search` found
`dotnet-trace`, but no public `dotnet-pgo` global tool package in the configured
NuGet feed.

An OpenFaaS C#/.NET ReadyToRun prototype was added at
`prototypes/dotnet-openfaas-readytorun`. Local publish and Docker packaging
succeeded for a self-contained `linux-musl-arm64` IL image, but deploying the
new function with `PUSH_IMAGE=0` was rejected by OpenFaaS Community Edition
because the image reference was not public. Completing this specific OpenFaaS
.NET run requires explicitly approving a push of the generated function image to
a registry the cluster can pull.

The Java line is an HTTP/OpenFaaS run from `openfaas_lusearch.csv`. The Go and
.NET lines are local handler-loop prototypes. They are useful for comparing
profile-artifact patterns, but they are not yet a strict serverless platform
comparison until the Go and .NET handlers are deployed behind the same HTTP
gateway and resource limits as the JVM function.

The current Java/OpenFaaS CSV records HTTP `500` for every invocation. The
latency shape is still plotted because it matches the JVM graph in the research
PDF, but the function status should be fixed before treating the Java point as
a successful workload result.
