package gpu

import (
	"fmt"
	"os"

	"github.com/mixa3607/ML-gfx906/rocm-metrics-go/internal/registers"
)

const (
	tmon0First      = 0x1660d
	tmon1First      = 0x16631
	thermalPolicy   = 0x1665f
	hwCTFLimit      = 0x16602
	dclkCounter     = 0x16ca1
	vclkCounter     = 0x16ca2
	eclkCounter     = 0x16c9e
	smnIndex        = 0x0e
	smnData         = 0x0f
	hbmTemperature  = 0x57148
	hbmStride       = 0x200000
	svi2Gfx         = 0x16804
	svi2Soc         = 0x16803
	svi2Mem0        = 0x16805
	svi2Mem1        = 0x16806
	registerCount   = 32
	temperatureBias = -49.0
)

type calibration struct {
	max    uint16
	offset int8
}

type telemetry struct {
	temperatures map[string]float64
	policy       float64
	ctf          float64
	gradient     float64
	clocks       map[string]float64
	voltages     map[string]float64
	currents     map[string]float64
}

func readTelemetry(backend, bdf string, calibration []calibration) (telemetry, error) {
	io, err := registers.Open(backend, bdf)
	if err != nil {
		return telemetry{}, err
	}
	defer io.Close()
	result := telemetry{temperatures: map[string]float64{}, clocks: map[string]float64{}, voltages: map[string]float64{}, currents: map[string]float64{}}
	for _, group := range []struct {
		first uint32
		name  string
	}{{tmon0First, "tmon_0"}, {tmon1First, "tmon_1"}} {
		for sensor := uint32(0); sensor < registerCount; sensor++ {
			value, err := io.Read32(group.first + sensor)
			if err != nil {
				return telemetry{}, err
			}
			if value&0x800 == 0 {
				continue
			}
			direction := "rdil"
			if sensor >= 16 {
				direction = "rdir"
			}
			result.temperatures[fmt.Sprintf("%s_%s%d", group.name, direction, sensor%16)] = float64((value>>12)&0xfff)*0.125 + temperatureBias
		}
	}
	policy, err := io.Read32(thermalPolicy)
	if err != nil {
		return telemetry{}, err
	}
	result.policy = float64(policy & 0x1ff)
	ctf, err := io.Read32(hwCTFLimit)
	if err != nil {
		return telemetry{}, err
	}
	result.ctf = float64((ctf>>6)&0xff) + temperatureBias
	if baseline, ok := result.temperatures["tmon_0_rdil0"]; ok {
		maximum := baseline
		for sensor := uint32(1); sensor < registerCount; sensor++ {
			value, err := io.Read32(tmon0First + sensor)
			if err != nil {
				return telemetry{}, err
			}
			if value&0x800 != 0 {
				temperature := float64((value>>12)&0xfff)*0.125 + temperatureBias
				if temperature > maximum {
					maximum = temperature
				}
			}
		}
		result.gradient = maximum - baseline
	}
	for name, register := range map[string]uint32{"dclk": dclkCounter, "vclk": vclkCounter, "eclk": eclkCounter} {
		value, err := io.Read32(register)
		if err != nil {
			return telemetry{}, err
		}
		result.clocks[name] = float64(value / 10)
	}
	savedIndex, err := io.Read32(smnIndex)
	if err != nil {
		return telemetry{}, err
	}
	for stack := uint32(0); stack < 4; stack++ {
		if err := io.Write32(smnIndex, hbmTemperature+stack*hbmStride); err != nil {
			return telemetry{}, err
		}
		value, err := io.Read32(smnData)
		if err != nil {
			io.Write32(smnIndex, savedIndex)
			return telemetry{}, err
		}
		result.temperatures[fmt.Sprintf("hbm_stack%d", stack)] = float64((value >> 16) & 0xff)
	}
	if err := io.Write32(smnIndex, savedIndex); err != nil {
		return telemetry{}, err
	}
	if len(calibration) == 0 {
		return result, nil
	}
	for rail, channel := range []struct {
		name     string
		register uint32
	}{{"gfx", svi2Gfx}, {"soc", svi2Soc}, {"mem0", svi2Mem0}, {"mem1", svi2Mem1}} {
		value, err := io.Read32(channel.register)
		if err != nil {
			return telemetry{}, err
		}
		result.voltages[channel.name] = 1.55 - float64((value>>16)&0xff)*0.00625
		result.currents[channel.name] = float64(value&0xff)*float64(int(calibration[rail].max)-int(calibration[rail].offset))/255 + float64(calibration[rail].offset)
	}
	return result, nil
}

func readCalibration(path string) ([]calibration, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read VBIOS: %w", err)
	}
	if len(data) < 0x4a {
		return nil, fmt.Errorf("VBIOS is too short")
	}
	le16 := func(offset int) uint16 { return uint16(data[offset]) | uint16(data[offset+1])<<8 }
	header := int(le16(0x48))
	for field := 0x1c; field <= 0x24; field += 2 {
		if header+field+2 > len(data) {
			continue
		}
		master := int(le16(header + field))
		if master+10 > len(data) || data[master+2] != 2 || data[master+3] != 1 {
			continue
		}
		smc := int(le16(master + 8))
		if smc+0x2c > len(data) || data[smc+2] != 4 || data[smc+3] != 4 {
			continue
		}
		result := make([]calibration, 4)
		for rail := range result {
			offset := smc + 0x1c + rail*4
			result[rail] = calibration{max: le16(offset), offset: int8(data[offset+2])}
		}
		return result, nil
	}
	return nil, fmt.Errorf("unsupported AtomBIOS SMC DPM table")
}
