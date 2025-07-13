ARG ROCM_DOCKER_ARCH
ARG ROCM_VERSION
ARG ROCBLAS_PACKAGE_URL
ARG BASE_LLAMA_TAG
ARG BASE_LLAMA_IMAGE
ARG BASE_LLAMA_CONTAINER=${BASE_LLAMA_IMAGE}:${BASE_LLAMA_TAG}

FROM ${BASE_LLAMA_CONTAINER} AS rocblas
ARG ROCBLAS_PACKAGE_URL
ARG ROCM_DOCKER_ARCH
WORKDIR /
RUN apt-get update && apt-get install -y wget curl zstd
RUN mkdir /rocblas_files; \
    if [ "${ROCBLAS_PACKAGE_URL}" != "" ]; then \
      wget "${ROCBLAS_PACKAGE_URL}" -O rocblas.pkg.tar.zst --progress=dot:mega; \
	  tar -xf rocblas.pkg.tar.zst; \
	  ls /opt/rocm/lib/rocblas/library | grep ${ROCM_DOCKER_ARCH} | xargs -I {} mv /opt/rocm/lib/rocblas/library/{} /rocblas_files ; \
	else \
	  echo "No external rocblas bins"; \
	fi;
RUN ls /rocblas_files

FROM ${BASE_LLAMA_CONTAINER} AS full
ARG ROCM_DOCKER_ARCH
ARG ROCM_VERSION

RUN pip install --break-system-packages "huggingface_hub[cli]"
COPY --from=rocblas /rocblas_files/* /opt/rocm-${ROCM_VERSION}/lib/rocblas/library/

ENV LLAMA_ARG_HOST=0.0.0.0
WORKDIR /app
HEALTHCHECK CMD [ "curl", "-f", "http://localhost:8080/health" ]
ENTRYPOINT [ "/app/llama-server" ]
