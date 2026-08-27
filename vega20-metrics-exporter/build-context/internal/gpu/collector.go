package gpu

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/prometheus/client_golang/prometheus"
	"go.opentelemetry.io/otel"
)

type DeviceID struct {
	VendorID  string `koanf:"vendor_id"`
	ProductID string `koanf:"product_id"`
}

type Config struct {
	SysfsPath        string
	SysfsEnabled     bool
	RegistersEnabled bool
	RegisterBackend  string
	VBIOS            VBIOSConfig
	Devices          []DeviceID
	PCIDevices       []string
}

type VBIOSConfig struct {
	Enabled bool
	Source  string
	File    string
	Device  string
}

type Collector struct {
	sysfsPath        string
	sysfsEnabled     bool
	registersEnabled bool
	backend          string
	calibration      []calibration
	devices          []DeviceID
	pcieDevices      []string
	vram             *prometheus.Desc
	visibleVRAM      *prometheus.Desc
	gtt              *prometheus.Desc
	power            *prometheus.Desc
	limit            *prometheus.Desc
	activity         *prometheus.Desc
	pcieSpeed        *prometheus.Desc
	pcieWidth        *prometheus.Desc
	info             *prometheus.Desc
	fan              *prometheus.Desc
	providerUp       *prometheus.Desc
	temperature      *prometheus.Desc
	thermal          *prometheus.Desc
	gradient         *prometheus.Desc
	clock            *prometheus.Desc
	voltage          *prometheus.Desc
	current          *prometheus.Desc
}

func NewCollector(config Config) (*Collector, error) {
	calibration, err := loadCalibration(config.SysfsPath, config.VBIOS)
	if err != nil {
		return nil, err
	}
	log.Printf("configured providers: sysfs=%t registers=%t backend=%s vbios_related_metrics=%t", config.SysfsEnabled, config.RegistersEnabled, config.RegisterBackend, config.VBIOS.Enabled)
	if config.VBIOS.Enabled {
		log.Printf("loaded VBIOS calibration: source=%s device=%s file=%s", config.VBIOS.Source, config.VBIOS.Device, config.VBIOS.File)
	}
	return &Collector{
		sysfsPath:        config.SysfsPath,
		sysfsEnabled:     config.SysfsEnabled,
		registersEnabled: config.RegistersEnabled,
		backend:          config.RegisterBackend,
		calibration:      calibration,
		devices:          config.Devices,
		pcieDevices:      config.PCIDevices,
		vram:             prometheus.NewDesc("vega20_vram_bytes", "VRAM capacity and current allocation.", []string{"gpu", "state"}, nil),
		visibleVRAM:      prometheus.NewDesc("vega20_visible_vram_bytes", "CPU-visible VRAM capacity and current allocation.", []string{"gpu", "state"}, nil),
		gtt:              prometheus.NewDesc("vega20_gtt_bytes", "GTT capacity and current allocation.", []string{"gpu", "state"}, nil),
		power:            prometheus.NewDesc("vega20_power_watts", "GPU power reported by amdgpu hwmon.", []string{"gpu", "source"}, nil),
		limit:            prometheus.NewDesc("vega20_power_limit_watts", "GPU power-cap values reported by amdgpu hwmon.", []string{"gpu", "limit"}, nil),
		activity:         prometheus.NewDesc("vega20_gfx_activity_percent", "GPU graphics-engine activity reported by amdgpu.", []string{"gpu"}, nil),
		pcieSpeed:        prometheus.NewDesc("vega20_pcie_link_speed_gigatransfers_per_second", "Effective current and maximum PCIe link speed across the GPU parent chain.", []string{"gpu", "state"}, nil),
		pcieWidth:        prometheus.NewDesc("vega20_pcie_link_width_lanes", "Effective current and maximum PCIe link width across the GPU parent chain.", []string{"gpu", "state"}, nil),
		info:             prometheus.NewDesc("vega20_gpu_info", "Vega 20 GPU identity and driver metadata.", []string{"gpu", "card_vendor", "card_model", "card_series", "driver_version", "serial_number", "vbios_version"}, nil),
		fan:              prometheus.NewDesc("vega20_fan_speed_percent", "GPU fan PWM duty cycle.", []string{"gpu"}, nil),
		providerUp:       prometheus.NewDesc("vega20_provider_up", "Whether a telemetry provider was read successfully for the GPU.", []string{"gpu", "provider"}, nil),
		temperature:      prometheus.NewDesc("vega20_temperature_celsius", "Vega 20 temperature sensors.", []string{"gpu", "sensor"}, nil),
		thermal:          prometheus.NewDesc("vega20_thermal_limit_celsius", "Vega 20 thermal policy and CTF limits.", []string{"gpu", "limit"}, nil),
		gradient:         prometheus.NewDesc("vega20_temperature_gradient_celsius", "Hottest TMON0 reading less TMON0 RDIL0.", []string{"gpu"}, nil),
		clock:            prometheus.NewDesc("vega20_clock_mhz", "Vega 20 measured clock counters.", []string{"gpu", "clock"}, nil),
		voltage:          prometheus.NewDesc("vega20_voltage_volts", "Calibrated measured SVI2 voltage.", []string{"gpu", "rail"}, nil),
		current:          prometheus.NewDesc("vega20_current_amperes", "Calibrated measured SVI2 current.", []string{"gpu", "rail"}, nil),
	}, nil
}

func (c *Collector) Describe(ch chan<- *prometheus.Desc) {
	ch <- c.vram
	ch <- c.visibleVRAM
	ch <- c.gtt
	ch <- c.power
	ch <- c.limit
	ch <- c.activity
	ch <- c.pcieSpeed
	ch <- c.pcieWidth
	ch <- c.info
	ch <- c.fan
	ch <- c.providerUp
	ch <- c.temperature
	ch <- c.thermal
	ch <- c.gradient
	ch <- c.clock
	ch <- c.voltage
	ch <- c.current
}

func (c *Collector) Collect(ch chan<- prometheus.Metric) {
	_, span := otel.Tracer("vega20-metrics").Start(context.Background(), "gpu.collect")
	defer span.End()

	targets, err := c.discoverDevices()
	if err != nil {
		return
	}
	for _, target := range targets {
		if c.sysfsEnabled {
			sample, err := readGPUSample(target.path)
			if err != nil {
				ch <- prometheus.MustNewConstMetric(c.providerUp, prometheus.GaugeValue, 0, target.bdf, "sysfs")
			} else {
				ch <- prometheus.MustNewConstMetric(c.providerUp, prometheus.GaugeValue, 1, target.bdf, "sysfs")
				c.collectSysfs(ch, sample)
			}
		}
		if !c.registersEnabled {
			continue
		}
		if target.path == "" {
			ch <- prometheus.MustNewConstMetric(c.providerUp, prometheus.GaugeValue, 0, target.bdf, "registers")
			continue
		}
		telemetry, err := readTelemetry(c.backend, target.bdf, c.calibration)
		if err != nil {
			ch <- prometheus.MustNewConstMetric(c.providerUp, prometheus.GaugeValue, 0, target.bdf, "registers")
			continue
		}
		ch <- prometheus.MustNewConstMetric(c.providerUp, prometheus.GaugeValue, 1, target.bdf, "registers")
		c.collectRegisters(ch, target.bdf, telemetry)
	}
}

type target struct {
	bdf  string
	path string
}

func (c *Collector) discoverDevices() ([]target, error) {
	if len(c.pcieDevices) > 0 {
		result := make([]target, 0, len(c.pcieDevices))
		for _, bdf := range c.pcieDevices {
			path := filepath.Join(c.sysfsPath, "bus/pci/devices", bdf)
			if matchesDevice(readText(filepath.Join(path, "vendor")), readText(filepath.Join(path, "device")), c.devices) {
				result = append(result, target{bdf: bdf, path: path})
				continue
			}
			result = append(result, target{bdf: bdf})
		}
		return result, nil
	}
	cards, err := filepath.Glob(filepath.Join(c.sysfsPath, "class/drm/card[0-9]*"))
	if err != nil {
		return nil, err
	}
	var result []target
	for _, card := range cards {
		path := filepath.Join(card, "device")
		if !matchesDevice(readText(filepath.Join(path, "vendor")), readText(filepath.Join(path, "device")), c.devices) {
			continue
		}
		devicePath, err := filepath.EvalSymlinks(path)
		if err != nil {
			continue
		}
		result = append(result, target{bdf: filepath.Base(devicePath), path: path})
	}
	return result, nil
}

func (c *Collector) collectSysfs(ch chan<- prometheus.Metric, gpu sample) {
	ch <- prometheus.MustNewConstMetric(c.vram, prometheus.GaugeValue, float64(gpu.vramTotal), gpu.bdf, "total")
	ch <- prometheus.MustNewConstMetric(c.vram, prometheus.GaugeValue, float64(gpu.vramUsed), gpu.bdf, "used")
	ch <- prometheus.MustNewConstMetric(c.vram, prometheus.GaugeValue, float64(gpu.vramTotal-gpu.vramUsed), gpu.bdf, "free")
	for state, value := range gpu.visibleVRAM {
		ch <- prometheus.MustNewConstMetric(c.visibleVRAM, prometheus.GaugeValue, float64(value), gpu.bdf, state)
	}
	for state, value := range gpu.gtt {
		ch <- prometheus.MustNewConstMetric(c.gtt, prometheus.GaugeValue, float64(value), gpu.bdf, state)
	}
	for source, value := range gpu.power {
		ch <- prometheus.MustNewConstMetric(c.power, prometheus.GaugeValue, float64(value)/1_000_000, gpu.bdf, source)
	}
	for limit, value := range gpu.limits {
		ch <- prometheus.MustNewConstMetric(c.limit, prometheus.GaugeValue, float64(value)/1_000_000, gpu.bdf, limit)
	}
	if gpu.activity != nil {
		ch <- prometheus.MustNewConstMetric(c.activity, prometheus.GaugeValue, float64(*gpu.activity), gpu.bdf)
	}
	for state, value := range gpu.pcieSpeed {
		ch <- prometheus.MustNewConstMetric(c.pcieSpeed, prometheus.GaugeValue, value, gpu.bdf, state)
	}
	for state, value := range gpu.pcieWidth {
		ch <- prometheus.MustNewConstMetric(c.pcieWidth, prometheus.GaugeValue, float64(value), gpu.bdf, state)
	}
	ch <- prometheus.MustNewConstMetric(c.info, prometheus.GaugeValue, 1, gpu.bdf, gpu.vendor, gpu.model, gpu.series, gpu.driverVersion, gpu.serial, gpu.vbios)
	if gpu.fan != nil {
		ch <- prometheus.MustNewConstMetric(c.fan, prometheus.GaugeValue, *gpu.fan, gpu.bdf)
	}
}

func (c *Collector) collectRegisters(ch chan<- prometheus.Metric, bdf string, telemetry telemetry) {
	for sensor, value := range telemetry.temperatures {
		ch <- prometheus.MustNewConstMetric(c.temperature, prometheus.GaugeValue, value, bdf, sensor)
	}
	ch <- prometheus.MustNewConstMetric(c.thermal, prometheus.GaugeValue, telemetry.policy, bdf, "policy")
	ch <- prometheus.MustNewConstMetric(c.thermal, prometheus.GaugeValue, telemetry.ctf, bdf, "hardware_ctf")
	ch <- prometheus.MustNewConstMetric(c.gradient, prometheus.GaugeValue, telemetry.gradient, bdf)
	for clock, value := range telemetry.clocks {
		ch <- prometheus.MustNewConstMetric(c.clock, prometheus.GaugeValue, value, bdf, clock)
	}
	for rail, value := range telemetry.voltages {
		ch <- prometheus.MustNewConstMetric(c.voltage, prometheus.GaugeValue, value, bdf, rail)
	}
	for rail, value := range telemetry.currents {
		ch <- prometheus.MustNewConstMetric(c.current, prometheus.GaugeValue, value, bdf, rail)
	}
}

type sample struct {
	bdf           string
	vramTotal     uint64
	vramUsed      uint64
	visibleVRAM   map[string]uint64
	gtt           map[string]uint64
	power         map[string]uint64
	limits        map[string]uint64
	activity      *uint64
	pcieSpeed     map[string]float64
	pcieWidth     map[string]uint64
	vendor        string
	model         string
	series        string
	driverVersion string
	serial        string
	vbios         string
	fan           *float64
}

func readGPUSample(device string) (sample, error) {
	devicePath, err := filepath.EvalSymlinks(device)
	if err != nil {
		return sample{}, err
	}
	total, err := readUint(filepath.Join(device, "mem_info_vram_total"))
	if err != nil {
		return sample{}, err
	}
	used, err := readUint(filepath.Join(device, "mem_info_vram_used"))
	if err != nil || used > total {
		return sample{}, fmt.Errorf("invalid VRAM allocation")
	}
	pcie := effectivePCIeLink(devicePath)
	result := sample{
		bdf:           filepath.Base(devicePath),
		vramTotal:     total,
		vramUsed:      used,
		visibleVRAM:   memoryStats(device, "mem_info_vis_vram_total", "mem_info_vis_vram_used"),
		gtt:           memoryStats(device, "mem_info_gtt_total", "mem_info_gtt_used"),
		power:         map[string]uint64{},
		limits:        map[string]uint64{},
		pcieSpeed:     pcie.speeds,
		pcieWidth:     pcie.widths,
		vendor:        "AMD",
		model:         readText(filepath.Join(device, "product_number")),
		series:        readText(filepath.Join(device, "product_name")),
		driverVersion: readText("/proc/sys/kernel/osrelease"),
		serial:        readText(filepath.Join(device, "serial_number")),
		vbios:         readText(filepath.Join(device, "vbios_version")),
	}
	if activity, err := readUint(filepath.Join(device, "gpu_busy_percent")); err == nil {
		result.activity = &activity
	}
	hwmons, _ := filepath.Glob(filepath.Join(device, "hwmon/hwmon*"))
	for _, hwmon := range hwmons {
		for source, file := range map[string]string{"average": "power1_average", "instant": "power1_input"} {
			if value, err := readUint(filepath.Join(hwmon, file)); err == nil {
				result.power[source] = value
			}
		}
		for limit, file := range map[string]string{"current": "power1_cap", "minimum": "power1_cap_min", "maximum": "power1_cap_max"} {
			if value, err := readUint(filepath.Join(hwmon, file)); err == nil {
				result.limits[limit] = value
			}
		}
		if pwm, err := readUint(filepath.Join(hwmon, "pwm1")); err == nil {
			if maximum, err := readUint(filepath.Join(hwmon, "pwm1_max")); err == nil && maximum > 0 && pwm <= maximum {
				fan := float64(pwm) * 100 / float64(maximum)
				result.fan = &fan
			}
		}
	}
	return result, nil
}

func matchesDevice(vendor, product string, devices []DeviceID) bool {
	for _, device := range devices {
		if vendor == device.VendorID && product == device.ProductID {
			return true
		}
	}
	return false
}

func readText(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(data))
}

func readUint(path string) (uint64, error) {
	return strconv.ParseUint(readText(path), 10, 64)
}

func memoryStats(device, totalFile, usedFile string) map[string]uint64 {
	total, totalErr := readUint(filepath.Join(device, totalFile))
	used, usedErr := readUint(filepath.Join(device, usedFile))
	if totalErr != nil || usedErr != nil || used > total {
		return nil
	}
	return map[string]uint64{"total": total, "used": used, "free": total - used}
}

type pcieLink struct {
	speeds map[string]float64
	widths map[string]uint64
}

func effectivePCIeLink(device string) pcieLink {
	result := pcieLink{speeds: map[string]float64{}, widths: map[string]uint64{}}
	var currentBandwidth, maximumBandwidth float64
	for path := device; strings.Count(filepath.Base(path), ":") == 2; path = filepath.Dir(path) {
		currentSpeed, currentSpeedErr := readLinkSpeed(filepath.Join(path, "current_link_speed"))
		currentWidth, currentWidthErr := readUint(filepath.Join(path, "current_link_width"))
		if currentSpeedErr == nil && currentWidthErr == nil {
			bandwidth := currentSpeed * float64(currentWidth)
			if currentBandwidth == 0 || bandwidth < currentBandwidth {
				currentBandwidth = bandwidth
				result.speeds["current"] = currentSpeed
				result.widths["current"] = currentWidth
			}
		}
		maximumSpeed, maximumSpeedErr := readLinkSpeed(filepath.Join(path, "max_link_speed"))
		maximumWidth, maximumWidthErr := readUint(filepath.Join(path, "max_link_width"))
		if maximumSpeedErr == nil && maximumWidthErr == nil {
			bandwidth := maximumSpeed * float64(maximumWidth)
			if maximumBandwidth == 0 || bandwidth < maximumBandwidth {
				maximumBandwidth = bandwidth
				result.speeds["maximum"] = maximumSpeed
				result.widths["maximum"] = maximumWidth
			}
		}
	}
	return result
}

func readLinkSpeed(path string) (float64, error) {
	fields := strings.Fields(readText(path))
	if len(fields) == 0 {
		return 0, fmt.Errorf("missing PCIe link speed")
	}
	return strconv.ParseFloat(fields[0], 64)
}
