# DaCapo lusearch Benchmark

This repository now treats `lusearch` as the JVM benchmark workload for the OpenFaaS/George profile-cache path.

## Prepare Assets

The DaCapo jar and data are intentionally not committed because the lusearch data is large. Prepare the Docker build context from the local DaCapo checkout:

```bash
scripts/06_prepare_dacapo_lusearch.sh
```

By default, this copies:

- `/Users/maheshk/Downloads/dacapobench/benchmarks/dacapo-evaluation-git-4e3de06d.jar`
- `/Users/maheshk/Downloads/dacapobench/benchmarks/dacapo-evaluation-git-4e3de06d/`

into:

- `generated/fn/lib/dacapo.jar`
- `generated/fn/lib/dacapo/`

The DaCapo harness expects the `dat/` and `jar/` directories next to the jar under a sibling directory named after the jar basename, so the layout is important.

## Local Smoke Benchmark

```bash
RUNS=3 scripts/07_benchmark_dacapo_lusearch_local.sh
```

This runs fresh local JVM processes and writes:

- `measurements/dacapo-lusearch/<run-id>/local-lusearch.csv`
- `docs/figures/dacapo-lusearch-local-latency.svg`
- `docs/figures/dacapo-lusearch-local-summary.json`

## OpenFaaS Benchmark

After preparing assets, rebuilding, pushing, and deploying the function:

```bash
source .env
scripts/03_build_and_push_function.sh
scripts/04_deploy_function.sh
MEASURE_RUNS=3 WARMUP_RUNS=3 scripts/08_benchmark_openfaas_lusearch.sh
```

The function invokes:

```text
/opt/george-jdk/bin/java -jar /app/lib/dacapo.jar lusearch -n 1
```

with per-invocation scratch directories under `/tmp`.
