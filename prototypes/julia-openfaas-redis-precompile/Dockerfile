# Dockerfile for Julia OpenFaaS precompile-cache warmup experiments.
#
# Build targets:
#   (default)        – runtime image with fwatchdog + handler, no sysimage
#   sysimage-builder – extends runtime with a PackageCompiler AOT sysimage
#                      baked in at build time (use --build-arg N_PROFILES=5|10)
#
# The image is intentionally self-contained: no DaCapo data files are needed
# because the workloads (lusearch / h2 / eclipse) generate their own inputs.

ARG JULIA_VERSION=1.10
ARG FWATCHDOG_VERSION=0.9.15

# ─── stage 1: install and precompile Julia packages ──────────────────────────
FROM julia:${JULIA_VERSION}-bookworm AS julia-deps

WORKDIR /app
COPY handler.jl ./

RUN julia --startup-file=no -e 'using Pkg; Pkg.add(["HTTP","JSON3"]); Pkg.precompile(); println("packages ready")'

# ─── stage 2: runtime image ──────────────────────────────────────────────────
FROM julia:${JULIA_VERSION}-bookworm AS runtime

ARG FWATCHDOG_VERSION

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

ARG TARGETARCH
RUN ARCH="${TARGETARCH:-amd64}" && \
    curl -fsSL \
    "https://github.com/openfaas/of-watchdog/releases/download/${FWATCHDOG_VERSION}/fwatchdog-${ARCH}" \
    -o /usr/local/bin/fwatchdog \
    && chmod +x /usr/local/bin/fwatchdog

COPY --from=julia-deps /root/.julia /root/.julia

WORKDIR /app
COPY handler.jl entrypoint.sh cachectl.py ./
RUN chmod +x entrypoint.sh

ENV mode="http"
ENV fprocess="/app/entrypoint.sh"
ENV upstream_url="http://127.0.0.1:8000"
ENV exec_timeout="120s"
ENV write_timeout="120s"
ENV read_timeout="120s"
ENV HANDLER_PORT="8000"
ENV JULIA_CACHE_MODE="baseline"

EXPOSE 8080

HEALTHCHECK --interval=5s --timeout=5s --start-period=60s \
    CMD curl -sf http://localhost:8080/_/health || exit 1

CMD ["/usr/local/bin/fwatchdog"]

# ─── stage 3: AOT sysimage (optional target) ─────────────────────────────────
# Build with:
#   docker build --target sysimage-builder --build-arg N_PROFILES=5  -t julia-precompile:sysimage5  .
#   docker build --target sysimage-builder --build-arg N_PROFILES=10 -t julia-precompile:sysimage10 .
FROM runtime AS sysimage-builder

ARG N_PROFILES=5

RUN set -eux; \
    for attempt in 1 2 3 4 5; do \
        rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/partial/*; \
        apt-get clean; \
        if apt-get update \
              -o Acquire::Retries=5 \
              -o Acquire::http::No-Cache=true \
              -o Acquire::http::Pipeline-Depth=0 \
              -o Acquire::BrokenProxy=true && \
           apt-get install -y --no-install-recommends --fix-missing \
              -o Acquire::Retries=5 \
              -o Acquire::http::No-Cache=true \
              -o Acquire::http::Pipeline-Depth=0 \
              -o Acquire::BrokenProxy=true \
              gcc g++; then \
            break; \
        fi; \
        if [ "$attempt" = "5" ]; then exit 1; fi; \
        sleep "$((attempt * 10))"; \
    done; \
    rm -rf /var/lib/apt/lists/*

COPY build_sysimage.jl ./

RUN julia --startup-file=no -e \
    'using Pkg; Pkg.add("PackageCompiler"); Pkg.precompile(); println("PackageCompiler ready")'

ENV JULIA_BUILD_SYSIMAGE=1
RUN julia --startup-file=no /app/build_sysimage.jl ${N_PROFILES}

ENV JULIA_BUILD_SYSIMAGE=""
ENV JULIA_CACHE_MODE="sysimage"

CMD ["/usr/local/bin/fwatchdog"]
