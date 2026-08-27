package gpu

import (
	"os"
	"path/filepath"
	"testing"
)

func TestReadGPU(t *testing.T) {
	root := t.TempDir()
	device := filepath.Join(root, "devices", "0000:33:00.0")
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
		"hwmon/hwmon0/power1_average": "125000000\n",
		"hwmon/hwmon0/power1_cap":     "200000000\n",
		"hwmon/hwmon0/power1_cap_min": "100000000\n",
		"hwmon/hwmon0/power1_cap_max": "250000000\n",
	}
	for name, value := range files {
		if err := os.WriteFile(filepath.Join(device, name), []byte(value), 0o644); err != nil {
			t.Fatal(err)
		}
	}

	sample, err := readGPU(card)
	if err != nil {
		t.Fatal(err)
	}
	if sample.bdf != "0000:33:00.0" || sample.vramTotal != 34359738368 || sample.vramUsed != 4294967296 {
		t.Fatalf("unexpected sample: %#v", sample)
	}
	if sample.power["average"] != 125000000 || sample.limits["maximum"] != 250000000 {
		t.Fatalf("unexpected power data: %#v %#v", sample.power, sample.limits)
	}
}
