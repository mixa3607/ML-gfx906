#!/usr/bin/env bash
set -euo pipefail

apt-get update
apt-get install -y --no-install-recommends ca-certificates curl libgomp1 libssl3t64

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://s3.arkprojects.space/apt-gfx906/ubuntu/gpg -o /etc/apt/keyrings/apt-gfx906.asc
cat > /etc/apt/sources.list.d/gfx906.sources <<'EOF'
Types: deb
URIs: https://s3.arkprojects.space/apt-gfx906/ubuntu
Suites: noble
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/apt-gfx906.asc
EOF

curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb \
    -o /tmp/cuda-keyring.deb
dpkg -i /tmp/cuda-keyring.deb
rm /tmp/cuda-keyring.deb

# Pin transitive ROCm packages too: the imported HIP backend was linked against this build.
cat > /etc/apt/preferences.d/rocm <<EOF
Package: amdrocm*
Pin: version ${ROCM_BUILD}
Pin-Priority: 1001
EOF
rocm_version="${ROCM_BUILD%%.*}"
remainder="${ROCM_BUILD#*.}"
rocm_version+=".${remainder%%.*}"
apt-get update
apt-get install -y --no-install-recommends \
    "amdrocm-runtime${rocm_version}=${ROCM_BUILD}" \
    "amdrocm-blas${rocm_version}-gfx906=${ROCM_BUILD}" \
    "amdrocm-rccl${rocm_version}-gfx906=${ROCM_BUILD}" \
    "cuda-cudart-13-3=${CUDA_CUDART_VERSION}" \
    "libcublas-13-3=${CUDA_CUBLAS_VERSION}"
# The full ROCm metapackage normally provides this alternatives link.
# Minimal component packages only populate the versioned directory.
ln -s "core-${rocm_version}/lib" /opt/rocm/lib
printf '/opt/rocm/lib\n/usr/local/cuda/lib64\n' > /etc/ld.so.conf.d/gpu-runtime.conf
ldconfig
rm -rf /var/lib/apt/lists/*
