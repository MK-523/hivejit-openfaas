# Go PGO Serverless Prototype

This is the cleanest non-JVM implementation of the project pattern:

```text
Execution -> CPU pprof export -> go build -pgo import -> future execution
```

The handler is a small route-dispatch workload shaped like a serverless function
with one dominant hot request path and a mixed workload for rejection testing.
The Go compiler consumes CPU `pprof` profiles directly, so this prototype uses
only public Go APIs.

## Run

Requires Go 1.21+.

```bash
bash prototypes/go-pgo-serverless/run_pgo.sh
```

The script writes:

```text
prototypes/go-pgo-serverless/artifacts/train.pprof
prototypes/go-pgo-serverless/artifacts/train.manifest.json
prototypes/go-pgo-serverless/build/profilecache-go-base
prototypes/go-pgo-serverless/build/profilecache-go-pgo
prototypes/go-pgo-serverless/results/last.jsonl
```

## Serverless Interpretation

The profile artifact is deployable build input. A production control loop would:

1. Build and deploy the baseline function binary.
2. Collect `pprof` from representative production or canary executions.
3. Store the profile under a cache key containing source hash, Go version,
   architecture, and workload label.
4. Rebuild the next function version with `go build -pgo=<profile>`.
5. Compare fresh-worker latency curves against the baseline binary.

Go's public docs describe this iterative lifecycle and note that profiles are
intended to feed representative behavior from one release into the next build.
