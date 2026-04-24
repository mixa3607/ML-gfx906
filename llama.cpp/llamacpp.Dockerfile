ARG BASE_CUDA_IMAGE=""
ARG CUDA_ARCH="120"

ARG LLAMACPP_REPO="https://github.com/ggml-org/llama.cpp.git"
ARG LLAMACPP_BRANCH="master"
ARG LLAMACPP_COMMIT=""
ARG LLAMACPP_CODE_PATH=""

############# Base image #############
FROM ${BASE_CUDA_IMAGE} AS cuda_base
# Install basic utilities and Python
RUN apt-get update && \
    apt-get install -y curl libgomp1 git python3 python3-venv python3-pip && \
    pip3 config set global.break-system-packages true && \
    true

ARG CUDA_ARCH
ENV CUDA_ARCH=${CUDA_ARCH}

############# Clone repos #############
FROM cuda_base AS files_llamacpp
ARG LLAMACPP_REPO
ARG LLAMACPP_BRANCH
ARG LLAMACPP_COMMIT
ARG LLAMACPP_CODE_PATH
# Clone
WORKDIR /files/llamacpp
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch ${LLAMACPP_BRANCH} ${LLAMACPP_REPO} .
RUN if [ "$LLAMACPP_COMMIT" != "" ]; then git checkout "$LLAMACPP_COMMIT"; fi
RUN if [ "$LLAMACPP_CODE_PATH" != "" ]; then cd "$LLAMACPP_CODE_PATH" && find ./ -maxdepth 1 -mindepth 1 -exec mv -t /files/llamacpp {} + ; fi

FROM files_llamacpp AS files_llamacpp_python
WORKDIR /files/llamacpp-python
RUN cp -r /files/llamacpp/requirements.txt /files/llamacpp/requirements /files/llamacpp/gguf-py /files/llamacpp/*.py /files/llamacpp-python
RUN find .

############# Build #############
FROM cuda_base AS build_llamacpp
RUN apt-get install -y build-essential cmake libssl-dev
COPY --from=files_llamacpp /files/llamacpp /build/llamacpp
WORKDIR /build/llamacpp

# https://github.com/ggml-org/llama.cpp/blob/a6206958d28a064564ef132091b9c617ae005f49/ggml/CMakeLists.txt#L221
RUN cmake -S . -B build \
        -DGGML_CUDA=ON                \
        -DGGML_NATIVE=OFF             \
        -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
        -DGGML_BACKEND_DL=ON          \
        -DGGML_CPU_ALL_VARIANTS=ON    \
        -DGGML_AVX512=ON              \
        -DGGML_AVX512_VBMI=ON         \
        -DGGML_AVX512_VNNI=ON         \
        -DGGML_AVX512_BF16=ON         \
        -DCMAKE_BUILD_TYPE=Release    \
        -DLLAMA_BUILD_TESTS=OFF       \
    && cmake --build build --config Release -j$(nproc)
RUN mkdir -p /builded && cp -r ./build/bin/* .devops/tools.sh /builded

############# Copy and install all #############
FROM cuda_base AS final
WORKDIR /app
COPY --from=files_llamacpp_python /files/llamacpp-python /app
RUN pip3 install --upgrade setuptools && \
    pip3 install -r requirements.txt && \
    pip3 cache purge && \
    true
COPY --from=build_llamacpp /builded/ /app
ENTRYPOINT ["/app/tools.sh"]
