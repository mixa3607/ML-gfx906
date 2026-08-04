ARG BASE_ROCM_IMAGE="docker.io/mixa3607/rocm-gfx906:latest"
ARG PACKAGE_SOURCE=fetch
ARG PACKAGES_BASE_URL=""

############# Get packages #############
FROM ${BASE_ROCM_IMAGE} AS packages-source
ARG PACKAGE_SOURCE
ARG PACKAGES_BASE_URL

RUN --mount=type=bind,from=packages,target=/packages-src <<EOF_DOCKERFILE bash
set -eo pipefail

mkdir -p /packages
pushd /packages

if [ "$PACKAGES_BASE_URL" == "" ]; then
  cat index.txt | while read FILE_NAME; do
    echo "Copy  \$FILE_NAME"
    cp "\$FILE_NAME" ./
  done
else 
  apt-get update
  apt-get install -y curl
  curl --fail -O "$PACKAGES_BASE_URL/index.txt"
  cat index.txt | while read FILE_NAME; do
    PACKAGE_URL="$PACKAGES_BASE_URL/\$FILE_NAME"
    echo "Downloading \$PACKAGE_URL"
    curl --fail -O "\$PACKAGE_URL"
  done
fi

popd
EOF_DOCKERFILE

############# Base image #############
FROM ${BASE_ROCM_IMAGE} AS final

# Install basic utilities and Python
RUN --mount=type=bind,from=packages-source,source=/packages,target=/packages <<EOF_DOCKERFILE bash
set -eo pipefail

apt-get update
apt-get install -y git python3 python3-venv python3-pip python3-dev
python3 -m pip config set global.break-system-packages true
python3 -m pip install /opt/rocm/share/amd_smi
pushd /packages; python3 -m pip install *.whl; popd

rm -rf /var/lib/{apt,dpkg,cache,log}/
EOF_DOCKERFILE

CMD ["/bin/bash"]
