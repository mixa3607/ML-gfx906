package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadEnvironmentOverridesIndexedValues(t *testing.T) {
	path := filepath.Join(t.TempDir(), "config.yaml")
	data := []byte(`listen: ":9500"
devices:
  vendor_products:
    - vendor_id: "1002"
      product_id: "66a1"
    - vendor_id: "1002"
      product_id: "66a2"
  pci_devices:
    - "0000:33:00.0"
    - "0000:36:00.0"
`)
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
	t.Setenv("VEGA20_DEVICES_VENDOR_PRODUCTS_1_PRODUCT_ID", "66a3")
	t.Setenv("VEGA20_DEVICES_PCI_DEVICES_0", "0000:4d:00.0")
	config, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if config.Listen != ":9500" || len(config.Devices.VendorProducts) != 2 || config.Devices.VendorProducts[0].ProductID != "0x66a1" || config.Devices.VendorProducts[1].ProductID != "0x66a3" {
		t.Fatalf("unexpected vendor products: %#v", config)
	}
	if len(config.Devices.PCIDevices) != 2 || config.Devices.PCIDevices[0] != "0000:4d:00.0" || config.Devices.PCIDevices[1] != "0000:36:00.0" {
		t.Fatalf("unexpected PCI devices: %#v", config.Devices.PCIDevices)
	}
}
