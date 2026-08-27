package gpu

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/prometheus/client_golang/prometheus"
	"go.opentelemetry.io/otel"
)

const (
	amdVendor = "0x1002"
	vega20ID  = "0x66a1"
)

type Collector struct {
	sysfs       string
	backend     string
	calibration []calibration
	vram        *prometheus.Desc
	visibleVRAM *prometheus.Desc
	gtt         *prometheus.Desc
	power       *prometheus.Desc
	limit       *prometheus.Desc
	activity    *prometheus.Desc
	pcieSpeed   *prometheus.Desc
	pcieWidth   *prometheus.Desc
	up          *prometheus.Desc
	registerUp  *prometheus.Desc
	temperature *prometheus.Desc
	thermal     *prometheus.Desc
	gradient    *prometheus.Desc
	clock       *prometheus.Desc
	voltage     *prometheus.Desc
	current     *prometheus.Desc
}

func NewCollector(sysfs, backend, vbios string) (*Collector, error) {
	var calibration []calibration
	var err error
	if vbios != "" {
		calibration, err = readCalibration(vbios)
		if err != nil {
			return nil, err
		}
	}
	return &Collector{
		sysfs:       sysfs,
		backend:     backend,
		calibration: calibration,
		vram:        prometheus.NewDesc("vega20_vram_bytes", "VRAM capacity and current allocation.", []string{"gpu", "state"}, nil),
		visibleVRAM: prometheus.NewDesc("vega20_visible_vram_bytes", "CPU-visible VRAM capacity and current allocation.", []string{"gpu", "state"}, nil),
		gtt:         prometheus.NewDesc("vega20_gtt_bytes", "GTT capacity and current allocation.", []string{"gpu", "state"}, nil),
		power:       prometheus.NewDesc("vega20_power_watts", "GPU power reported by amdgpu hwmon.", []string{"gpu", "source"}, nil),
		limit:       prometheus.NewDesc("vega20_power_limit_watts", "GPU power-cap values reported by amdgpu hwmon.", []string{"gpu", "limit"}, nil),
		activity:    prometheus.NewDesc("vega20_gfx_activity_percent", "GPU graphics-engine activity reported by amdgpu.", []string{"gpu"}, nil),
		pcieSpeed:   prometheus.NewDesc("vega20_pcie_link_speed_gigatransfers_per_second", "Current and maximum PCIe link speed.", []string{"gpu", "state"}, nil),
		pcieWidth:   prometheus.NewDesc("vega20_pcie_link_width_lanes", "Current and maximum PCIe link width.", []string{"gpu", "state"}, nil),
		up:          prometheus.NewDesc("vega20_gpu_up", "Whether sysfs telemetry was read successfully for the GPU.", []string{"gpu"}, nil),
		registerUp:  prometheus.NewDesc("vega20_register_telemetry_up", "Whether register telemetry was read successfully for the GPU.", []string{"gpu", "backend"}, nil),
		temperature: prometheus.NewDesc("vega20_temperature_celsius", "Vega 20 temperature sensors.", []string{"gpu", "sensor"}, nil),
		thermal:     prometheus.NewDesc("vega20_thermal_limit_celsius", "Vega 20 thermal policy and CTF limits.", []string{"gpu", "limit"}, nil),
		gradient:    prometheus.NewDesc("vega20_temperature_gradient_celsius", "Hottest TMON0 reading less TMON0 RDIL0.", []string{"gpu"}, nil),
		clock:       prometheus.NewDesc("vega20_clock_mhz", "Vega 20 measured clock counters.", []string{"gpu", "clock"}, nil),
		voltage:     prometheus.NewDesc("vega20_voltage_volts", "Calibrated measured SVI2 voltage.", []string{"gpu", "rail"}, nil),
		current:     prometheus.NewDesc("vega20_current_amperes", "Calibrated measured SVI2 current.", []string{"gpu", "rail"}, nil),
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
	ch <- c.up
	ch <- c.registerUp
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

	cards, err := filepath.Glob(filepath.Join(c.sysfs, "class/drm/card[0-9]*"))
	if err != nil {
		return
	}
	for _, card := range cards {
		gpu, err := readGPU(card)
		if err != nil {
			continue
		}
		ch <- prometheus.MustNewConstMetric(c.up, prometheus.GaugeValue, 1, gpu.bdf)
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
		if c.backend == "none" {
			continue
		}
		telemetry, err := readTelemetry(c.backend, gpu.bdf, c.calibration)
		if err != nil {
			ch <- prometheus.MustNewConstMetric(c.registerUp, prometheus.GaugeValue, 0, gpu.bdf, c.backend)
			continue
		}
		ch <- prometheus.MustNewConstMetric(c.registerUp, prometheus.GaugeValue, 1, gpu.bdf, c.backend)
		for sensor, value := range telemetry.temperatures {
			ch <- prometheus.MustNewConstMetric(c.temperature, prometheus.GaugeValue, value, gpu.bdf, sensor)
		}
		ch <- prometheus.MustNewConstMetric(c.thermal, prometheus.GaugeValue, telemetry.policy, gpu.bdf, "policy")
		ch <- prometheus.MustNewConstMetric(c.thermal, prometheus.GaugeValue, telemetry.ctf, gpu.bdf, "hardware_ctf")
		ch <- prometheus.MustNewConstMetric(c.gradient, prometheus.GaugeValue, telemetry.gradient, gpu.bdf)
		for clock, value := range telemetry.clocks {
			ch <- prometheus.MustNewConstMetric(c.clock, prometheus.GaugeValue, value, gpu.bdf, clock)
		}
		for rail, value := range telemetry.voltages {
			ch <- prometheus.MustNewConstMetric(c.voltage, prometheus.GaugeValue, value, gpu.bdf, rail)
		}
		for rail, value := range telemetry.currents {
			ch <- prometheus.MustNewConstMetric(c.current, prometheus.GaugeValue, value, gpu.bdf, rail)
		}
	}
}

type sample struct {
	bdf         string
	vramTotal   uint64
	vramUsed    uint64
	visibleVRAM map[string]uint64
	gtt         map[string]uint64
	power       map[string]uint64
	limits      map[string]uint64
	activity    *uint64
	pcieSpeed   map[string]float64
	pcieWidth   map[string]uint64
}

func readGPU(card string) (sample, error) {
	device := filepath.Join(card, "device")
	if readText(filepath.Join(device, "vendor")) != amdVendor || readText(filepath.Join(device, "device")) != vega20ID {
		return sample{}, fmt.Errorf("not Vega 20")
	}
	bdf, err := filepath.EvalSymlinks(device)
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
	result := sample{
		bdf:         filepath.Base(bdf),
		vramTotal:   total,
		vramUsed:    used,
		visibleVRAM: memoryStats(device, "mem_info_vis_vram_total", "mem_info_vis_vram_used"),
		gtt:         memoryStats(device, "mem_info_gtt_total", "mem_info_gtt_used"),
		power:       map[string]uint64{},
		limits:      map[string]uint64{},
		pcieSpeed:   linkSpeeds(device),
		pcieWidth:   linkWidths(device),
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
	}
	return result, nil
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

func linkSpeeds(device string) map[string]float64 {
	result := map[string]float64{}
	for state, file := range map[string]string{"current": "current_link_speed", "maximum": "max_link_speed"} {
		fields := strings.Fields(readText(filepath.Join(device, file)))
		if len(fields) == 0 {
			continue
		}
		if speed, err := strconv.ParseFloat(fields[0], 64); err == nil {
			result[state] = speed
		}
	}
	return result
}

func linkWidths(device string) map[string]uint64 {
	result := map[string]uint64{}
	for state, file := range map[string]string{"current": "current_link_width", "maximum": "max_link_width"} {
		if width, err := readUint(filepath.Join(device, file)); err == nil {
			result[state] = width
		}
	}
	return result
}
