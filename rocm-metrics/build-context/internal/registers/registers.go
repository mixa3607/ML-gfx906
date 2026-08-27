package registers

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
)

const bar5Size = 512 * 1024

type IO interface {
	Read32(uint32) (uint32, error)
	Write32(uint32, uint32) error
	Close() error
}

func Open(backend, bdf string) (IO, error) {
	switch backend {
	case "debugfs":
		return openDebugfs(bdf)
	case "bar5":
		return openBAR5(bdf)
	default:
		return nil, fmt.Errorf("unsupported register backend %q", backend)
	}
}

type debugfs struct{ file *os.File }

func openDebugfs(bdf string) (*debugfs, error) {
	file, err := os.OpenFile(filepath.Join("/sys/kernel/debug/dri", bdf, "amdgpu_regs"), os.O_RDWR, 0)
	if err != nil {
		return nil, err
	}
	return &debugfs{file: file}, nil
}

func (d *debugfs) Read32(dword uint32) (uint32, error) {
	var value [4]byte
	_, err := d.file.ReadAt(value[:], int64(dword)*4)
	return binary.LittleEndian.Uint32(value[:]), err
}

func (d *debugfs) Write32(dword, value uint32) error {
	var data [4]byte
	binary.LittleEndian.PutUint32(data[:], value)
	_, err := d.file.WriteAt(data[:], int64(dword)*4)
	return err
}

func (d *debugfs) Close() error { return d.file.Close() }

type bar5 struct {
	file *os.File
	data []byte
}

func openBAR5(bdf string) (*bar5, error) {
	physical, err := bar5Start(bdf)
	if err != nil {
		return nil, err
	}
	file, err := os.OpenFile("/dev/mem", os.O_RDWR|syscall.O_SYNC, 0)
	if err != nil {
		return nil, err
	}
	data, err := syscall.Mmap(int(file.Fd()), int64(physical), bar5Size, syscall.PROT_READ|syscall.PROT_WRITE, syscall.MAP_SHARED)
	if err != nil {
		file.Close()
		return nil, err
	}
	return &bar5{file: file, data: data}, nil
}

func bar5Start(bdf string) (uint64, error) {
	file, err := os.Open(filepath.Join("/sys/bus/pci/devices", bdf, "resource"))
	if err != nil {
		return 0, err
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	for index := 0; index < 6 && scanner.Scan(); index++ {
		fields := strings.Fields(scanner.Text())
		if len(fields) != 3 {
			return 0, fmt.Errorf("invalid PCI resource line")
		}
		if index != 5 {
			continue
		}
		begin, err := strconv.ParseUint(fields[0], 0, 64)
		if err != nil {
			return 0, err
		}
		end, err := strconv.ParseUint(fields[1], 0, 64)
		if err != nil || end < begin || end-begin+1 < bar5Size {
			return 0, fmt.Errorf("BAR5 is unavailable")
		}
		return begin, nil
	}
	if err := scanner.Err(); err != nil {
		return 0, err
	}
	return 0, fmt.Errorf("BAR5 is unavailable")
}

func (b *bar5) Read32(dword uint32) (uint32, error) {
	offset := uint64(dword) * 4
	if offset+4 > uint64(len(b.data)) {
		return 0, fmt.Errorf("register 0x%x outside BAR5", dword)
	}
	return binary.LittleEndian.Uint32(b.data[offset:]), nil
}

func (b *bar5) Write32(dword, value uint32) error {
	offset := uint64(dword) * 4
	if offset+4 > uint64(len(b.data)) {
		return fmt.Errorf("register 0x%x outside BAR5", dword)
	}
	binary.LittleEndian.PutUint32(b.data[offset:], value)
	return nil
}

func (b *bar5) Close() error {
	err := syscall.Munmap(b.data)
	closeErr := b.file.Close()
	if err != nil {
		return err
	}
	return closeErr
}
