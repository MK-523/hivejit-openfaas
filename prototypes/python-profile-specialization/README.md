# Python Profile-Specialization Cache Prototype

This prototype is the non-JVM domain-specific specialization path:

```text
generic cold execution -> route/query profile export -> generated specialization artifact -> future cold execution
```

It is intentionally different from Go PGO and .NET ReadyToRun. The artifact is
not a rebuilt binary. It is generated Python code that bakes in runtime-observed
route and query-shape information, then future cold processes import that code
directly.

The taxonomy match is the "code specializations" and "domain-specific
specializations" bucket from the PrismX excerpt: runtime values and workload
shape drive which specialized code is generated.

## Run

```bash
bash prototypes/python-profile-specialization/run_profile_cache.sh
```

Default benchmarks:

- `dacapo-lusearch`: search/indexing route mix.
- `dacapo-h2`: relational query route mix.

Optional:

```bash
cd prototypes/python-profile-specialization
BENCHMARKS="dacapo-lusearch dacapo-h2 dacapo-eclipse" \
REQUESTS=12000 PROFILE_REQUESTS=36000 INVOKES=16 PROFILE_ITERS="3" \
./run_profile_cache.sh
```

## Outputs

```text
prototypes/python-profile-specialization/profiles/<run>/
prototypes/python-profile-specialization/artifacts/<run>/
prototypes/python-profile-specialization/results/<run>/
docs/figures/python-profile-specialization-*-invocation-curves.svg
docs/figures/python-profile-specialization-*-p50-p95.svg
docs/figures/python-profile-specialization-*-summary.json
```

## Serverless Interpretation

Each measured point is a fresh Python process, approximating cold function
execution. The generic run exports a compact JSON profile. The controller then
generates a specialization artifact and stores it outside the process. A future
cold process imports the artifact at startup.

That makes this closer to the JVM/HiveJIT profile-cache idea than ordinary warm
starts: the old process dies, but learned runtime information is preserved as an
optimizer artifact.
