ARG BASE_UBUNTU_IMAGE="docker.io/library/ubuntu:24.04"
ARG AMD_TUNING_VERSION="0.0.0"
ARG VERSION_SUFFIX="gfx906"

FROM ${BASE_UBUNTU_IMAGE} AS build_deb
ARG AMD_TUNING_VERSION
ARG VERSION_SUFFIX

RUN apt-get update && apt-get install -y --no-install-recommends dpkg-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build/amd-tuning
COPY amd-tuning amd-tuning-deps-installer \
     pp-table-allowlist.txt memory-tweak-allowlist.txt ./
COPY examples/ ./examples/

RUN set -eux; \
    package_version="${AMD_TUNING_VERSION}-${VERSION_SUFFIX}"; \
    package_root="/root/amd-tuning_${package_version}_amd64"; \
    install -Dm755 amd-tuning "${package_root}/usr/bin/amd-tuning"; \
    install -Dm755 amd-tuning-deps-installer "${package_root}/usr/bin/amd-tuning-deps-installer"; \
    install -Dm644 pp-table-allowlist.txt "${package_root}/usr/lib/amd-tuning/pp-table-allowlist.txt"; \
    install -Dm644 memory-tweak-allowlist.txt "${package_root}/usr/lib/amd-tuning/memory-tweak-allowlist.txt"; \
    install -Dm644 examples/profile-mi50-113-D1631700-111-mem-oc.yaml "${package_root}/usr/share/amd-tuning/examples/profile-mi50-113-D1631700-111-mem-oc.yaml"; \
    install -Dm644 examples/profile-mi50-113-D1631700-111-stock.yaml "${package_root}/usr/share/amd-tuning/examples/profile-mi50-113-D1631700-111-stock.yaml"; \
    install -d -m 0755 "${package_root}/DEBIAN" /dist; \
    chmod 0755 "${package_root}/DEBIAN"; \
    chmod g-s "${package_root}/DEBIAN"; \
    printf '%s\n' \
      'Package: amd-tuning' \
      "Version: ${package_version}" \
      'Section: admin' \
      'Priority: optional' \
      'Architecture: amd64' \
      'Depends: amd-memory-tweak, bash' \
      'Maintainer: mixa3607 (ML-gfx906 project)' \
      'Description: YAML profiles for MI50 PowerPlay and HBM2 tuning' \
      ' Applies allowlisted PowerPlay and AMD Memory Tweak settings from YAML.' \
      ' Run amd-tuning-deps-installer once to install UPP and yq.' \
      > "${package_root}/DEBIAN/control"; \
    dpkg-deb --root-owner-group --build "${package_root}" \
      "/dist/amd-tuning_${package_version}_amd64.deb"

FROM scratch AS final
COPY --from=build_deb /dist/* /
