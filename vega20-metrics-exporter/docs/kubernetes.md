# Kubernetes

The exporter must run on a node with MI50/Vega 20 hardware. This manifest uses
host `/sys` and debugfs, therefore the container is privileged. Apply it only
to trusted GPU nodes.

Replace `<tag>` with a published image tag and adjust the node selector for the
GPU worker pool.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: vega20-metrics-exporter
data:
  config.yaml: |
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
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vega20-metrics-exporter
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: vega20-metrics-exporter
  template:
    metadata:
      labels:
        app.kubernetes.io/name: vega20-metrics-exporter
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/path: /metrics
        prometheus.io/port: "9487"
    spec:
      nodeSelector:
        accelerator: amd-mi50
      containers:
        - name: exporter
          image: docker.io/mixa3607/vega20-metrics-exporter:<tag>
          ports:
            - name: metrics
              containerPort: 9487
          securityContext:
            privileged: true
          volumeMounts:
            - name: host-sys
              mountPath: /sys
              readOnly: true
            - name: host-debugfs
              mountPath: /sys/kernel/debug
            - name: config
              mountPath: /etc/vega20-metrics-exporter/config.yaml
              subPath: config.yaml
              readOnly: true
      volumes:
        - name: host-sys
          hostPath:
            path: /sys
            type: Directory
        - name: host-debugfs
          hostPath:
            path: /sys/kernel/debug
            type: Directory
        - name: config
          configMap:
            name: vega20-metrics-exporter
```

The Prometheus annotations are on the pod template because annotation-based
discovery scrapes pods, not Deployment objects. Configure `pci_devices` in the
ConfigMap to force specific BDFs; a missing configured BDF emits
`vega20_provider_up{gpu="<BDF>",provider="sysfs"} 0`.

For sysfs-only telemetry, set `providers.registers.enabled: false` and remove the
`host-debugfs` volume/mount. Privileged mode may also be removable under the
cluster's device and security policy.
