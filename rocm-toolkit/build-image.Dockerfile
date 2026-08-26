ARG BASE_ROCM_IMAGE="docker.io/mixa3607/rocm-gfx906:7.14-complete"
ARG ROCM_VERSION="7.14"

FROM ${BASE_ROCM_IMAGE} AS final
ARG ROCM_VERSION

RUN set -e; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      rocm-validation-suite \
      "amdrocm${ROCM_VERSION}-transferbench" \
      amd-memory-tweak \
      amd-tuning \
      aria2 \
      curl \
      nano \
      python3 \
      python3-venv \
      python3-pip \
      python3-dev \
      tmux \
      wget; \
    python3 -m pip config set global.break-system-packages true; \
    python3 -m pip install huggingface_hub; \
    amd-tuning-deps-installer; \
    rm -rf /var/lib/apt/lists/*

CMD ["/bin/bash"]
