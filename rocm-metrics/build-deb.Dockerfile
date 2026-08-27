ARG BASE_BUILD_IMAGE="docker.io/library/golang:1.24-bookworm"

FROM ${BASE_BUILD_IMAGE} AS build
ARG PACKAGE_VERSION

WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . ./
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /usr/bin/vega20-metrics ./cmd/vega20-metrics
RUN mkdir -p /pkg/DEBIAN /pkg/usr/bin /dist && \
    chmod g-s /pkg /pkg/DEBIAN /pkg/usr /pkg/usr/bin && \
    chmod 0755 /pkg /pkg/DEBIAN /pkg/usr /pkg/usr/bin && \
    cp /usr/bin/vega20-metrics /pkg/usr/bin/vega20-metrics && \
    printf 'Package: rocm-metrics\nVersion: %s\nSection: utils\nPriority: optional\nArchitecture: amd64\nMaintainer: mixa3607\nDescription: Prometheus exporter for AMD Vega 20 / MI50 metrics\n' "${PACKAGE_VERSION}" > /pkg/DEBIAN/control && \
    dpkg-deb --build /pkg "/dist/rocm-metrics_${PACKAGE_VERSION}_amd64.deb"

FROM scratch AS final
COPY --from=build /dist/*.deb /
