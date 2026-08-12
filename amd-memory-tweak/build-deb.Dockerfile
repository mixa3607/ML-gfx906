ARG BASE_UBUNTU_IMAGE="docker.io/library/ubuntu:24.04"
ARG AMT_VERSION="0.1.9.1"
ARG VERSION_SUFFIX="gfx906"

FROM ${BASE_UBUNTU_IMAGE} AS build_deb
ARG AMT_VERSION
ARG VERSION_SUFFIX

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates dpkg-dev libpci-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build/amdmemorytweak
COPY AmdMemTweak.cpp LICENSE NOTICE ./
RUN g++ -O2 -DNDEBUG AmdMemTweak.cpp -lpci -lresolv -o amdmemtweak

RUN set -eux; \
    package_version="${AMT_VERSION}-${VERSION_SUFFIX}"; \
    package_root="/root/amd-memory-tweak_${package_version}_amd64"; \
    install -Dm755 amdmemtweak "${package_root}/usr/bin/amdmemtweak"; \
    install -Dm644 LICENSE "${package_root}/usr/share/doc/amd-memory-tweak/copyright"; \
    install -Dm644 NOTICE "${package_root}/usr/share/doc/amd-memory-tweak/NOTICE"; \
    install -d -m 0755 "${package_root}/DEBIAN" /dist; \
    chmod 0755 "${package_root}/DEBIAN"; \
    chmod g-s "${package_root}/DEBIAN"; \
    printf '%s\n' \
      'Package: amd-memory-tweak' \
      "Version: ${package_version}" \
      'Section: admin' \
      'Priority: optional' \
      'Architecture: amd64' \
      'Depends: libc6, libgcc-s1, libpci3, libstdc++6' \
      'Recommends: python3' \
      'Maintainer: mixa3607 (ML-gfx906 project)' \
      'Homepage: https://github.com/Eliovp/amdmemorytweak' \
      'Description: AMD HBM2 memory timing tool with MI50 support' \
      ' Patched AMD Memory Tweak CLI with Vega20 MI50 device support and' \
      ' structured JSON output for current HBM2 timings.' \
      > "${package_root}/DEBIAN/control"; \
    dpkg-deb --root-owner-group --build "${package_root}" \
      "/dist/amd-memory-tweak_${package_version}_amd64.deb"

FROM scratch AS final
COPY --from=build_deb /dist/* /
