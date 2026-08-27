package gpu

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/prometheus/client_golang/prometheus"
)

func TestReadGPU(t *testing.T) {
	root := t.TempDir()
	device := filepath.Join(root, "devices", "pci0000:30", "0000:31:00.0", "0000:32:00.0", "0000:33:00.0")
	if err := os.MkdirAll(filepath.Join(device, "hwmon", "hwmon0"), 0o755); err != nil {
		t.Fatal(err)
	}
	card := filepath.Join(root, "card0")
	if err := os.Symlink(device, filepath.Join(card, "device")); err != nil {
		if err := os.MkdirAll(card, 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.Symlink(device, filepath.Join(card, "device")); err != nil {
			t.Fatal(err)
		}
	}
	files := map[string]string{
		"vendor":                      "0x1002\n",
		"device":                      "0x66a1\n",
		"mem_info_vram_total":         "34359738368\n",
		"mem_info_vram_used":          "4294967296\n",
		"mem_info_vis_vram_total":     "17179869184\n",
		"mem_info_vis_vram_used":      "2147483648\n",
		"mem_info_gtt_total":          "68719476736\n",
		"mem_info_gtt_used":           "1073741824\n",
		"gpu_busy_percent":            "42\n",
		"current_link_speed":          "16.0 GT/s PCIe\n",
		"max_link_speed":              "16.0 GT/s PCIe\n",
		"current_link_width":          "16\n",
		"max_link_width":              "16\n",
		"product_number":              "102-D16317-11\n",
		"product_name":                "Radeon Instinct MI50 32GB\n",
		"serial_number":               "6921210044327dd4\n",
		"vbios_version":               "113-D1631700-111\n",
		"hwmon/hwmon0/power1_average": "125000000\n",
		"hwmon/hwmon0/power1_cap":     "200000000\n",
		"hwmon/hwmon0/power1_cap_min": "100000000\n",
		"hwmon/hwmon0/power1_cap_max": "250000000\n",
		"hwmon/hwmon0/pwm1":           "64\n",
		"hwmon/hwmon0/pwm1_max":       "255\n",
	}
	for name, value := range files {
		if err := os.WriteFile(filepath.Join(device, name), []byte(value), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	for name, value := range map[string]string{
		"current_link_speed": "16.0 GT/s PCIe\n",
		"max_link_speed":     "16.0 GT/s PCIe\n",
		"current_link_width": "8\n",
		"max_link_width":     "16\n",
	} {
		if err := os.WriteFile(filepath.Join(filepath.Dir(filepath.Dir(device)), name), []byte(value), 0o644); err != nil {
			t.Fatal(err)
		}
	}

	sample, err := readGPUSample(filepath.Join(card, "device"))
	if err != nil {
		t.Fatal(err)
	}
	if sample.bdf != "0000:33:00.0" || sample.vramTotal != 34359738368 || sample.vramUsed != 4294967296 {
		t.Fatalf("unexpected sample: %#v", sample)
	}
	if sample.power["average"] != 125000000 || sample.limits["maximum"] != 250000000 {
		t.Fatalf("unexpected power data: %#v %#v", sample.power, sample.limits)
	}
	if sample.visibleVRAM["free"] != 15032385536 || sample.gtt["free"] != 67645734912 {
		t.Fatalf("unexpected memory data: %#v %#v", sample.visibleVRAM, sample.gtt)
	}
	if sample.activity == nil || *sample.activity != 42 || sample.pcieSpeed["current"] != 16 || sample.pcieWidth["current"] != 8 {
		t.Fatalf("unexpected activity or PCIe data: %#v %#v %#v", sample.activity, sample.pcieSpeed, sample.pcieWidth)
	}
	if sample.model != "102-D16317-11" || sample.series != "Radeon Instinct MI50 32GB" || sample.serial != "6921210044327dd4" || sample.vbios != "113-D1631700-111" || sample.driverVersion == "" {
		t.Fatalf("unexpected GPU metadata: %#v", sample)
	}
	if sample.fan == nil || *sample.fan != float64(64)*100/255 {
		t.Fatalf("unexpected fan data: %#v", sample.fan)
	}
}

func TestCollectorForcedDeviceMissingReportsDown(t *testing.T) {
	collector, err := NewCollector(Config{
		SysfsPath:        t.TempDir(),
		SysfsEnabled:     true,
		RegistersEnabled: false,
		Devices:          []DeviceID{{VendorID: "0x1002", ProductID: "0x66a1"}},
		PCIDevices:       []string{"0000:33:00.0"},
	})
	if err != nil {
		t.Fatal(err)
	}
	registry := prometheus.NewRegistry()
	registry.MustRegister(collector)
	families, err := registry.Gather()
	if err != nil {
		t.Fatal(err)
	}
	for _, family := range families {
		if family.GetName() != "vega20_provider_up" {
			continue
		}
		if len(family.Metric) != 1 || family.Metric[0].GetGauge().GetValue() != 0 || family.Metric[0].Label[0].GetValue() != "0000:33:00.0" || family.Metric[0].Label[1].GetValue() != "sysfs" {
			t.Fatalf("unexpected up metric: %#v", family.Metric)
		}
		return
	}
	t.Fatal("vega20_provider_up was not collected")
}
