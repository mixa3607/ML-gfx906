package config

import (
	"fmt"
	"os"
	"regexp"
	"strconv"
	"strings"

	"github.com/knadh/koanf/parsers/yaml"
	"github.com/knadh/koanf/providers/confmap"
	"github.com/knadh/koanf/providers/file"
	"github.com/knadh/koanf/v2"
	"github.com/mixa3607/ML-gfx906/vega20-metrics-exporter/internal/gpu"
)

const DefaultPath = "/etc/vega20-metrics-exporter/config.yaml"

var bdfPattern = regexp.MustCompile(`^[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]$`)

type Config struct {
	Listen    string    `koanf:"listen"`
	Devices   Devices   `koanf:"devices"`
	Providers Providers `koanf:"providers"`
}

type Devices struct {
	VendorProducts []gpu.DeviceID `koanf:"vendor_products"`
	PCIDevices     []string       `koanf:"pci_devices"`
}

type Providers struct {
	Sysfs     SysfsProvider     `koanf:"sysfs"`
	Registers RegistersProvider `koanf:"registers"`
}

type SysfsProvider struct {
	Enabled bool   `koanf:"enabled"`
	Path    string `koanf:"path"`
}

type RegistersProvider struct {
	Enabled             bool                `koanf:"enabled"`
	Backend             string              `koanf:"backend"`
	VBIOSRelatedMetrics VBIOSRelatedMetrics `koanf:"vbios_related_metrics"`
}

type VBIOSRelatedMetrics struct {
	Enabled bool   `koanf:"enabled"`
	Source  string `koanf:"vbios_source"`
	File    string `koanf:"vbios_file"`
	Device  string `koanf:"vbios_device"`
}

func Load(path string) (Config, error) {
	k := koanf.New(".")
	defaults := map[string]interface{}{
		"listen": ":9487",
		"devices": map[string]interface{}{
			"vendor_products": []map[string]string{{"vendor_id": "1002", "product_id": "66a1"}},
		},
		"providers": map[string]interface{}{
			"sysfs":     map[string]interface{}{"enabled": true, "path": "/sys"},
			"registers": map[string]interface{}{"enabled": true, "backend": "debugfs"},
		},
	}
	if err := k.Load(confmap.Provider(defaults, "."), nil); err != nil {
		return Config{}, err
	}
	if err := k.Load(file.Provider(path), yaml.Parser()); err != nil {
		return Config{}, fmt.Errorf("load config %q: %w", path, err)
	}
	var config Config
	if err := k.Unmarshal("", &config); err != nil {
		return Config{}, fmt.Errorf("decode config: %w", err)
	}
	if err := applyEnvironment(&config, os.Environ()); err != nil {
		return Config{}, err
	}
	if err := config.validate(); err != nil {
		return Config{}, err
	}
	return config, nil
}

func applyEnvironment(config *Config, environment []string) error {
	for _, item := range environment {
		key, value, found := strings.Cut(item, "=")
		if !found {
			continue
		}
		switch key {
		case "VEGA20_LISTEN":
			config.Listen = value
		case "VEGA20_PROVIDERS_SYSFS_ENABLED":
			parsed, err := strconv.ParseBool(value)
			if err != nil {
				return fmt.Errorf("parse %s: %w", key, err)
			}
			config.Providers.Sysfs.Enabled = parsed
		case "VEGA20_PROVIDERS_SYSFS_PATH":
			config.Providers.Sysfs.Path = value
		case "VEGA20_PROVIDERS_REGISTERS_ENABLED":
			parsed, err := strconv.ParseBool(value)
			if err != nil {
				return fmt.Errorf("parse %s: %w", key, err)
			}
			config.Providers.Registers.Enabled = parsed
		case "VEGA20_PROVIDERS_REGISTERS_BACKEND":
			config.Providers.Registers.Backend = value
		case "VEGA20_PROVIDERS_REGISTERS_VBIOS_RELATED_METRICS_ENABLED":
			parsed, err := strconv.ParseBool(value)
			if err != nil {
				return fmt.Errorf("parse %s: %w", key, err)
			}
			config.Providers.Registers.VBIOSRelatedMetrics.Enabled = parsed
		case "VEGA20_PROVIDERS_REGISTERS_VBIOS_RELATED_METRICS_VBIOS_SOURCE":
			config.Providers.Registers.VBIOSRelatedMetrics.Source = value
		case "VEGA20_PROVIDERS_REGISTERS_VBIOS_RELATED_METRICS_VBIOS_FILE":
			config.Providers.Registers.VBIOSRelatedMetrics.File = value
		case "VEGA20_PROVIDERS_REGISTERS_VBIOS_RELATED_METRICS_VBIOS_DEVICE":
			config.Providers.Registers.VBIOSRelatedMetrics.Device = value
		default:
			if err := applyDeviceEnvironment(&config.Devices, key, value); err != nil {
				return err
			}
		}
	}
	return nil
}

func applyDeviceEnvironment(devices *Devices, key, value string) error {
	const vendorProductPrefix = "VEGA20_DEVICES_VENDOR_PRODUCTS_"
	const pciDevicePrefix = "VEGA20_DEVICES_PCI_DEVICES_"
	if strings.HasPrefix(key, vendorProductPrefix) {
		parts := strings.Split(strings.TrimPrefix(key, vendorProductPrefix), "_")
		if len(parts) != 3 || (parts[1] != "VENDOR" || parts[2] != "ID") && (parts[1] != "PRODUCT" || parts[2] != "ID") {
			return nil
		}
		index, err := strconv.Atoi(parts[0])
		if err != nil || index < 0 {
			return fmt.Errorf("invalid environment variable %s", key)
		}
		for len(devices.VendorProducts) <= index {
			devices.VendorProducts = append(devices.VendorProducts, gpu.DeviceID{})
		}
		if parts[1] == "VENDOR" {
			devices.VendorProducts[index].VendorID = value
		} else {
			devices.VendorProducts[index].ProductID = value
		}
		return nil
	}
	if strings.HasPrefix(key, pciDevicePrefix) {
		index, err := strconv.Atoi(strings.TrimPrefix(key, pciDevicePrefix))
		if err != nil || index < 0 {
			return fmt.Errorf("invalid environment variable %s", key)
		}
		for len(devices.PCIDevices) <= index {
			devices.PCIDevices = append(devices.PCIDevices, "")
		}
		devices.PCIDevices[index] = value
	}
	return nil
}

func (config *Config) validate() error {
	if config.Listen == "" || config.Providers.Sysfs.Path == "" {
		return fmt.Errorf("listen and providers.sysfs.path must not be empty")
	}
	if !config.Providers.Sysfs.Enabled && !config.Providers.Registers.Enabled {
		return fmt.Errorf("at least one metrics provider must be enabled")
	}
	if config.Providers.Registers.Enabled && config.Providers.Registers.Backend != "debugfs" && config.Providers.Registers.Backend != "bar5" {
		return fmt.Errorf("unsupported providers.registers.backend %q", config.Providers.Registers.Backend)
	}
	if len(config.Devices.VendorProducts) == 0 {
		return fmt.Errorf("devices.vendor_products must not be empty")
	}
	for index := range config.Devices.VendorProducts {
		device := &config.Devices.VendorProducts[index]
		device.VendorID = normalizeHexID(device.VendorID)
		device.ProductID = normalizeHexID(device.ProductID)
		if len(device.VendorID) != 6 || len(device.ProductID) != 6 {
			return fmt.Errorf("invalid devices.vendor_products[%d]", index)
		}
	}
	seen := map[string]bool{}
	for index, bdf := range config.Devices.PCIDevices {
		bdf = strings.ToLower(bdf)
		if !bdfPattern.MatchString(bdf) {
			return fmt.Errorf("invalid devices.pci_devices[%d]", index)
		}
		if seen[bdf] {
			return fmt.Errorf("duplicate devices.pci_devices entry %q", bdf)
		}
		seen[bdf] = true
		config.Devices.PCIDevices[index] = bdf
	}
	vbios := &config.Providers.Registers.VBIOSRelatedMetrics
	if !vbios.Enabled {
		return nil
	}
	if !config.Providers.Registers.Enabled {
		return fmt.Errorf("vbios_related_metrics requires providers.registers.enabled")
	}
	switch vbios.Source {
	case "file":
		if vbios.File == "" || vbios.Device != "" {
			return fmt.Errorf("vbios_source file requires vbios_file and no vbios_device")
		}
	case "pci_rom":
		vbios.Device = strings.ToLower(vbios.Device)
		if vbios.File != "" || !bdfPattern.MatchString(vbios.Device) {
			return fmt.Errorf("vbios_source pci_rom requires vbios_device and no vbios_file")
		}
	default:
		return fmt.Errorf("unsupported vbios_source %q", vbios.Source)
	}
	return nil
}

func normalizeHexID(value string) string {
	value = strings.ToLower(strings.TrimSpace(value))
	if len(value) == 4 {
		return "0x" + value
	}
	return value
}
