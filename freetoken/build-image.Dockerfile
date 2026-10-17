# syntax=docker/dockerfile:1.7
ARG BASE_PYTORCH_IMAGE=docker.io/mixa3607/pytorch-gfx906:v2.13.0-rocm-7.14
FROM ${BASE_PYTORCH_IMAGE} AS build-base
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git python3-dev python3-venv && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install uv
ENV UV_SYSTEM_PYTHON=1 UV_BREAK_SYSTEM_PACKAGES=1

FROM build-base AS triton-build
COPY --from=triton-source / /src/triton/
WORKDIR /src/triton
RUN uv pip install -r python/requirements.txt
ARG MAX_JOBS=8
ENV MAX_JOBS=${MAX_JOBS}
RUN --mount=type=cache,target=/root/.triton python3 -u setup.py bdist_wheel --dist-dir /wheels

FROM build-base AS final
RUN uv pip uninstall amdsmi
COPY --from=triton-build /wheels/ /wheels/
RUN uv pip install /wheels/*.whl && rm /wheels/*.whl
COPY --from=freetoken-source / /opt/FreeToken/
COPY prepare-source.py /tmp/prepare-source.py
RUN python3 /tmp/prepare-source.py /opt/FreeToken
WORKDIR /opt/FreeToken
ENV PYTORCH_ROCM_ARCH=gfx906 FREETOKEN_ROCM_ARCH=gfx906 HSA_XNACK=0
ENV MAX_JOBS=8 CMAKE_BUILD_PARALLEL_LEVEL=8
RUN uv pip install -r requirements-rocm.txt && uv pip install --no-deps --no-build-isolation .
ENV HF_HOME=/root/.cache/huggingface TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=4
ENV PYTORCH_TUNABLEOP_ENABLED=1 PYTORCH_TUNABLEOP_TUNING=0 PYTORCH_TUNABLEOP_HIPBLASLT_ENABLED=0
ENV PYTORCH_ALLOC_CONF=expandable_segments:False
EXPOSE 1919
ENTRYPOINT ["ft"]
CMD ["--version"]
