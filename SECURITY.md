# Security

This repository contains experimental build and deployment scripts. Review them
before running, pin external images and toolchains for controlled experiments,
and never commit cloud credentials, kubeconfigs, registry tokens, profile data
containing production inputs, or unredacted runtime dumps.

Use isolated development clusters and test workloads. The OpenFaaS, Redis, and
container prototypes are not hardened production services. Report a suspected
security issue privately through GitHub's security-advisory interface rather
than opening a public issue with credentials or exploit details.
