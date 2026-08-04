#!/bin/bash
set -eo pipefail

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
