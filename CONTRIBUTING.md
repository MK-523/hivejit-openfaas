# Contributing

Each prototype should make the profile-artifact lifecycle explicit: observe or
train, export, validate, import, and measure a fresh process or worker. Keep raw
measurements separate from interpretation and record runtime versions, hardware,
request counts, warmup policy, and cache-key inputs.

Before proposing a change, run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_repository.py --root .
```

Run the affected prototype as well when its toolchain is available. Generated
profiles, builds, caches, and result directories are ignored; publish only small
reviewable summaries and figures with enough provenance to reproduce them.

Do not describe a rebuild-time PGO experiment as live JIT-state injection, and
do not generalize a single machine's latency result beyond its documented setup.
