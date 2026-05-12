# Python Profile-Specialization Results

This note captures the graphable Python/domain-specific specialization
prototype.

## System Loop

```text
generic cold execution -> route/query profile export -> generated specialization artifact -> future cold execution
```

Unlike Go PGO, this prototype does not rebuild a native binary. Unlike warm
starts, it does not keep a Python process alive. The reusable artifact is a
generated Python module specialized from runtime-observed route and query-shape
profiles.

## Run

```bash
cd prototypes/python-profile-specialization
BENCHMARKS="dacapo-lusearch dacapo-h2" \
REQUESTS=12000 PROFILE_REQUESTS=36000 INVOKES=16 PROFILE_ITERS="3" \
./run_profile_cache.sh
```

## Figures

After running, the generated figures are:

- `docs/figures/python-profile-specialization-dacapo-lusearch-invocation-curves.svg`
- `docs/figures/python-profile-specialization-dacapo-lusearch-p50-p95.svg`
- `docs/figures/python-profile-specialization-dacapo-lusearch-profile-specialization-improvement.svg`
- `docs/figures/python-profile-specialization-dacapo-h2-invocation-curves.svg`
- `docs/figures/python-profile-specialization-dacapo-h2-p50-p95.svg`
- `docs/figures/python-profile-specialization-dacapo-h2-profile-specialization-improvement.svg`

## Latest Run

Run id: `20260512-130927`

Command:

```bash
RUN_ID=20260512-130927 \
BENCHMARKS="dacapo-lusearch dacapo-h2" \
REQUESTS=12000 PROFILE_REQUESTS=36000 INVOKES=16 PROFILE_ITERS="3" \
bash prototypes/python-profile-specialization/run_profile_cache.sh
```

| benchmark | build | n | mean wall ms | p50 wall ms | p95 wall ms |
| --- | --- | ---: | ---: | ---: | ---: |
| dacapo-lusearch | Generic | 16 | 205.317 | 207.401 | 216.793 |
| dacapo-lusearch | Specialized, 3 profiles | 16 | 184.264 | 184.209 | 189.949 |
| dacapo-h2 | Generic | 16 | 314.816 | 314.469 | 319.283 |
| dacapo-h2 | Specialized, 3 profiles | 16 | 269.464 | 269.135 | 279.372 |

The profile-specialized artifact improved cold-process p50 by about 11.2% on
`dacapo-lusearch` and 14.4% on `dacapo-h2`. p95 also improved in this run:
about 12.4% for `dacapo-lusearch` and 12.5% for `dacapo-h2`.

## Interpretation

This is a domain-specific specialization result, not a stock Python JIT result.
The generic handler uses interpreted route/query operators. The profile artifact
records observed route frequencies, and `profile_codegen.py` emits direct code
ordered by the hot profile. Future cold invocations import that artifact and
avoid the generic dispatch path.

Use this as the third comparison when the requirement is: a non-JVM serverless
system where runtime information is exported from one execution and imported by
future cold executions as an optimizer artifact.
