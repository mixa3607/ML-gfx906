ARG BASE_BUILD_IMAGE="docker.io/library/ubuntu:24.04"
ARG GO_VERSION="1.24.0"

FROM ${BASE_BUILD_IMAGE} AS build
ARG PACKAGE_VERSION
ARG GO_VERSION

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    curl --fail --location "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" | tar -C /usr/local -xz && \
    rm -rf /var/lib/apt/lists/*
ENV PATH="/usr/local/go/bin:${PATH}"

WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY cmd ./cmd
COPY internal ./internal
COPY DEBIAN ./DEBIAN
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /usr/bin/vega20-metrics ./cmd/vega20-metrics
RUN mkdir -p /pkg/usr/bin /dist && \
    chmod g-s /pkg /pkg/usr /pkg/usr/bin && \
    chmod 0755 /pkg /pkg/usr /pkg/usr/bin && \
    cp /usr/bin/vega20-metrics /pkg/usr/bin/vega20-metrics && \
    cp -a DEBIAN /pkg/DEBIAN && \
    chmod g-s /pkg/DEBIAN && \
    chmod 0755 /pkg/DEBIAN && \
    sed -i "s/@PACKAGE_VERSION@/${PACKAGE_VERSION}/" /pkg/DEBIAN/control && \
    dpkg-deb --build /pkg "/dist/vega20-metrics-exporter_${PACKAGE_VERSION}_amd64.deb"

FROM scratch AS final
COPY --from=build /dist/*.deb /
