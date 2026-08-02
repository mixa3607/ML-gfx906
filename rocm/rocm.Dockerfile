ARG ROCM_BASE_IMAGE="docker.io/library/ubuntu:24.04"
ARG ROCM_BUILD="7.14.0-gfx906+20260802001858"

############# Base image #############
FROM ${ROCM_BASE_IMAGE} AS rocm_base
ARG ROCM_BUILD

ENV ROCM_PATH=/opt/rocm
ENV PATH=/opt/rocm/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN <<EOF_DOCKERFILE bash
set -ex
apt-get update
apt-get install -y ca-certificates curl git jq

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://s3.arkprojects.space/apt-gfx906/ubuntu/gpg -o /etc/apt/keyrings/apt-gfx906.asc
chmod a+r /etc/apt/keyrings/apt-gfx906.asc
tee /etc/apt/sources.list.d/gfx906.sources <<EOF
Types: deb
URIs: https://s3.arkprojects.space/apt-gfx906/ubuntu
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: main
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/apt-gfx906.asc
EOF

apt-get update
ROCM_PACKAGES="$(
  apt list | 
  sed -nE 's|^(.+)/(.+) (.+) (.+)$|{ "name": "\1", "version": "\3" }|1p' | 
  jq -r \
    --arg prefix amdrocm \
    --arg build "$ROCM_BUILD" \
  '
    select(.name | startswith($prefix)) | 
    select(.version == $build) | 
    .name + "=" + .version
  ' 
)"
ROCM_PACKAGES_COUNT="$(( $(echo "$ROCM_PACKAGES" | wc -l) -1 ))"
if [ "$ROCM_PACKAGES_COUNT" -eq 0 ]; then
  echo "No ROCm packages found. Exit 1"
  exit 1
fi
echo "Rocm packages to install ($ROCM_PACKAGES_COUNT): \n$ROCM_PACKAGES" 
apt-get install -y $ROCM_PACKAGES

tee /etc/ld.so.conf.d/rocm.conf <<EOF
# ROCm gfx906
$ROCM_PATH/lib
EOF
ldconfig

rm -rf /var/lib/apt/lists/*
EOF_DOCKERFILE

############# Final image #############
FROM rocm_base AS final
