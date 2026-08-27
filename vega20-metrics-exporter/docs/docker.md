# Docker And Compose

The default `debugfs` backend reads and writes AMDGPU RDI registers. It needs
host `/sys`, host debugfs, and privileged access. The examples below are for a
trusted host running MI50/Vega 20 hardware.

Replace `<tag>` with a published image tag.

## Docker

```sh
docker run --rm --name vega20-metrics-exporter \
  --publish 9487:9487 \
  --privileged \
  --mount type=bind,src=/sys,dst=/sys,readonly \
  --mount type=bind,src=/sys/kernel/debug,dst=/sys/kernel/debug \
  docker.io/mixa3607/vega20-metrics-exporter:<tag>
```

Verify the endpoint:

```sh
curl http://localhost:9487/metrics
```

To override the image's `/etc/vega20-metrics-exporter/config.yaml`, bind-mount
a local YAML file:

```sh
docker run --rm --publish 9487:9487 --privileged \
  --mount type=bind,src=/sys,dst=/sys,readonly \
  --mount type=bind,src=/sys/kernel/debug,dst=/sys/kernel/debug \
  --mount type=bind,src="$PWD/config.yaml",dst=/etc/vega20-metrics-exporter/config.yaml,readonly \
  docker.io/mixa3607/vega20-metrics-exporter:<tag>
```

Set `providers.registers.enabled: false` in `config.yaml` when register
telemetry is not needed. The `/sys/kernel/debug` mount and privileged access can
then be removed.

## Docker Compose

Create `compose.yaml`:

```yaml
services:
  vega20-metrics-exporter:
    image: docker.io/mixa3607/vega20-metrics-exporter:<tag>
    privileged: true
    ports:
      - "9487:9487"
    volumes:
      - type: bind
        source: /sys
        target: /sys
        read_only: true
      - type: bind
        source: /sys/kernel/debug
        target: /sys/kernel/debug
      - type: bind
        source: ./config.yaml
        target: /etc/vega20-metrics-exporter/config.yaml
        read_only: true
```

Use the following minimal `config.yaml` for automatic Vega 20 discovery:

```yaml
listen: ":9487"
devices:
  vendor_products:
    - vendor_id: "1002"
      product_id: "66a1"
  pci_devices: []
providers:
  sysfs:
    enabled: true
    path: /sys
  registers:
    enabled: true
    backend: debugfs
    vbios_related_metrics:
      enabled: false
      vbios_source: null
      vbios_file: null
      vbios_device: null
```

Start it with:

```sh
docker compose up -d
```
