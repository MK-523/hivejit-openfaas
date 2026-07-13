# Profile Artifact Cache for Serverless

Research prototypes for testing whether a short-lived serverless worker can reuse compact optimization artifacts instead of relearning the same runtime behavior after every cold start.

The common loop is:

```text
representative execution
        -> export profile or compilation artifact
        -> store and version artifact
        -> import artifact into a fresh build or worker
        -> measure startup and warmup behavior
```

This repository explores that loop across managed runtimes, ahead-of-time profile-guided optimization, and domain-specific compilation caches. It is an experimental workspace, not a production caching service.

## Research question

Short-lived functions discard information that was expensive to learn, including hot methods, branch frequencies, type feedback, compiled code, and workload-specific shapes. The project asks whether a smaller, versioned artifact can preserve some of that information across worker or pod churn without snapshotting an entire process heap.

A cache key would need to account for at least the code version, runtime/compiler version, architecture, and workload profile. Evaluation must include the cost of exporting, storing, importing, and validating an artifact—not only the speed of the optimized execution.

## Implemented experiments

| Area | Repository path | What it exercises |
|---|---|---|
| Node/V8 | [`prototypes/node-v8-artifact-cache`](prototypes/node-v8-artifact-cache) | V8 code-cache export and reuse |
| LLVM/Clang | [`prototypes/llvm-aot-pgo`](prototypes/llvm-aot-pgo) | `.profraw` → `.profdata` → profile-guided rebuild |
| Go PGO | [`prototypes/go-pgo-serverless`](prototypes/go-pgo-serverless) | `pprof` capture and `go build -pgo` |
| Go + OpenFaaS + Redis | [`prototypes/go-openfaas-redis-pgo`](prototypes/go-openfaas-redis-pgo) | Profile capture, Redis storage, PGO rebuild, redeployment, and HTTP measurement |
| Python specialization | [`prototypes/python-profile-specialization`](prototypes/python-profile-specialization) | Generated specialization modules from observed route/query profiles |
| JAX/XLA | [`prototypes/jax-xla-runtime-specialization`](prototypes/jax-xla-runtime-specialization) | Runtime signatures and JAX's persistent compilation cache |
| JAX + OpenFaaS + Redis | [`prototypes/jax-openfaas-redis-xla`](prototypes/jax-openfaas-redis-xla) | Baseline-versus-cache serverless cold-start experiments |
| JVM/DaCapo | [`prototypes/jvm-openfaas-dacapo`](prototypes/jvm-openfaas-dacapo) | Pod churn and warmup resets for real JVM DaCapo workloads |
| Julia | [`prototypes/julia-openfaas-redis-precompile`](prototypes/julia-openfaas-redis-precompile) | `--trace-compile` artifacts stored through Redis |
| .NET | [`prototypes/dotnet-readytorun-pgo`](prototypes/dotnet-readytorun-pgo) | ReadyToRun and static-PGO build paths |

The [`scripts`](scripts) directory contains matrix runners, HTTP latency collection, plotting, and export-overhead analysis. Design and experiment notes live in [`docs`](docs).

## Representative measured run

One local `kind`/OpenFaaS experiment compared a Go baseline with PGO builds trained from five and ten warm-profile captures. Each build received 80 measured requests.

| Build | Mean | p50 | p95 |
|---|---:|---:|---:|
| No PGO | 109.1 ms | 104.0 ms | 130.0 ms |
| PGO, 5 profiles | 103.7 ms | 102.9 ms | 107.4 ms |
| PGO, 10 profiles | 102.8 ms | 102.7 ms | 105.0 ms |

The ten-profile build reduced p95 from 130.0 ms to 105.0 ms in that run. This is a workload- and environment-specific observation, not a general performance claim. The environment, raw-artifact locations, plots, and smaller smoke-test caveats are recorded in [`docs/go-openfaas-redis-pgo-results.md`](docs/go-openfaas-redis-pgo-results.md).

## Verified entry points

Run the local V8 cache experiment:

```bash
node prototypes/node-v8-artifact-cache/bench.js --runs 8
```

Run the LLVM AOT-PGO loop:

```bash
bash prototypes/llvm-aot-pgo/run_pgo.sh
```

Run every prototype supported by the installed local toolchain:

```bash
python3 scripts/run_profile_cache_matrix.py
```

Validate the repository's Python, shell, and JSON sources without installing
project dependencies:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_repository.py --root .
```

OpenFaaS, Redis, JVM, Go, JAX, Julia, and .NET experiments have additional environment requirements documented beside their respective prototypes.

## Evaluation principles

Report more than steady-state throughput. A useful study should capture:

- cold-start and first-request latency;
- per-invocation warmup curves and time-to-hot;
- p50, p95, and p99 latency;
- compilation and deoptimization events where available;
- artifact size, export/import cost, and cache lookup cost;
- behavior under version mismatches and workload drift.

## Limitations

- The repository contains multiple independent prototypes with different maturity levels; it is not one integrated production system.
- Some paths require SDKs or infrastructure that the matrix runner may skip when unavailable.
- The Go “DaCapo-shaped” aliases are Go-native workload shapes, not the real JVM DaCapo programs. The JVM harness is the path for real DaCapo workloads.
- PGO rebuild experiments demonstrate profile reuse through a new binary; they are not equivalent to injecting live JIT state into an already-created worker.
- The JVM/HiveJIT export-overhead analyzer requires instrumentation logs that are not produced by the analyzer itself.
- Published measurements should always name the hardware, runtime versions, workload, warmup policy, request count, and run count.

## Background sources

- [Go profile-guided optimization](https://go.dev/doc/pgo)
- [Node `vm.Script` cached data](https://nodejs.org/api/vm.html#scriptcreatecacheddata)
- [LLVM `llvm-profdata`](https://llvm.org/docs/CommandGuide/llvm-profdata.html)
- [JAX persistent compilation cache](https://docs.jax.dev/en/latest/persistent_compilation_cache.html)
- [DaCapo benchmark suite](https://www.dacapobench.org/)
- [Virtual-machine warmup study](https://doi.org/10.1145/3133876)
