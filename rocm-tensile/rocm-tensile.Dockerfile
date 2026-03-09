ARG ROCM_IMAGE="docker.io/mixa3607/rocm-gfx906:6.3.3-complete"
ARG ROCM_ARCH="gfx906"

############# Copy files #############
FROM ${ROCM_IMAGE} AS rocm_files
RUN mkdir /tensile-files && \
    find "/opt/rocm-$(cat /opt/ROCM_VERSION_FULL)/lib/rocblas/library" -type f -name "*${ROCM_ARCH}*" -exec cp {} /tensile-files \; && \
    ls /tensile-files && \
    true
# cd /tensile-files && \
# tar -cvf "/tensile-files.tar" . && \
# true

############# Copy to scratch #############
FROM scratch AS final
COPY --from=rocm_files /tensile-files/* /
