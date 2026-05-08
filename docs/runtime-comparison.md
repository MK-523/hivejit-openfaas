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

The Java line is an HTTP/OpenFaaS run from `openfaas_lusearch.csv`. The Go and
.NET lines are local handler-loop prototypes. They are useful for comparing
profile-artifact patterns, but they are not yet a strict serverless platform
comparison until the Go and .NET handlers are deployed behind the same HTTP
gateway and resource limits as the JVM function.

The current Java/OpenFaaS CSV records HTTP `500` for every invocation. The
latency shape is still plotted because it matches the JVM graph in the research
PDF, but the function status should be fixed before treating the Java point as
a successful workload result.
