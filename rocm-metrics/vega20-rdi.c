// Read Vega 20 TMON RDI and HBM temperature registers from the selected GPU's BAR5.
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define BAR5_SIZE (512 * 1024)
#define PCI_RESOURCE_COUNT 6

#define TMON0_RDI_FIRST_DWORD 0x1660d
#define TMON1_RDI_FIRST_DWORD 0x16631
#define TMON_RDI_SENSORS_PER_DIRECTION 16
#define TMON_RDI_VALID_MASK 0x800
#define TMON_RDI_RAW_SHIFT 12
#define TMON_RDI_RAW_MASK 0xfff
#define TMON_RDI_DEGREES_PER_CODE 0.125
#define TMON_RDI_DEGREES_OFFSET -49.0
#define TMON_THERMAL_POLICY_DWORD 0x1665f
#define TMON_THERMAL_POLICY_MASK 0x1ff
#define TMON_HW_CTF_LIMIT_DWORD 0x16602
#define TMON_HW_CTF_LIMIT_SHIFT 6
#define TMON_HW_CTF_LIMIT_MASK 0xff
#define TMON_TGRADIENT_SENSOR_COUNT 32

#define DCLK_COUNTER_DWORD 0x16ca1
#define VCLK_COUNTER_DWORD 0x16ca2
#define ECLK_COUNTER_DWORD 0x16c9e
#define CLOCK_COUNTER_CODES_PER_MHZ 10

#define SMN_INDEX_DWORD 0x0e
#define SMN_DATA_DWORD 0x0f
#define HBM_STACK_COUNT 4
#define HBM_TEMPERATURE_SMN_BASE 0x57148
#define HBM_TEMPERATURE_SMN_STACK_STRIDE 0x200000
#define HBM_TEMPERATURE_SHIFT 16
#define HBM_TEMPERATURE_MASK 0xff

#define SVI2_PLANE0_CHANNEL1 0x16803
#define SVI2_PLANE0_CHANNEL0 0x16804
#define SVI2_PLANE1_CHANNEL0 0x16805
#define SVI2_PLANE1_CHANNEL1 0x16806
#define SVI2_VOLTAGE_SHIFT 16
#define SVI2_VOLTAGE_MASK 0xff
#define SVI2_CURRENT_MASK 0xff
#define SVI2_VOLTAGE_MAX 1.55
#define SVI2_VOLTAGE_STEP 0.00625
#define SVI2_CURRENT_CODE_MAX 255.0

#define ATOM_ROM_HEADER_POINTER_OFFSET 0x48
#define ATOM_ROM_HEADER_MIN_SIZE (ATOM_ROM_HEADER_POINTER_OFFSET + sizeof(uint16_t))
#define ATOM_ROM_MASTER_DATA_TABLE_FIELD_FIRST 0x1c
#define ATOM_ROM_MASTER_DATA_TABLE_FIELD_LAST 0x24
#define ATOM_ROM_MASTER_DATA_TABLE_FIELD_SIZE sizeof(uint16_t)
#define ATOM_COMMON_TABLE_FORMAT_REVISION_OFFSET 2
#define ATOM_COMMON_TABLE_CONTENT_REVISION_OFFSET 3
#define ATOM_MASTER_DATA_TABLE_SMC_DPM_ENTRY_OFFSET 8
#define ATOM_SMC_DPM_V4_4_CALIBRATION_OFFSET 0x1c
#define ATOM_SMC_DPM_V4_4_CALIBRATION_SIZE 4
#define ATOM_SMC_DPM_V4_4_RAIL_COUNT 4

struct current_calibration {
    uint16_t max_current;
    int8_t offset;
};

static int read_line(const char *path, char *value, size_t size) {
    FILE *file = fopen(path, "r");
    if (!file)
        return -1;
    int result = fgets(value, size, file) ? 0 : -1;
    fclose(file);
    value[strcspn(value, "\n")] = '\0';
    return result;
}

static int bar5_start(const char *bdf, uint64_t *start) {
    char path[512];
    snprintf(path, sizeof(path), "/sys/bus/pci/devices/%s/resource", bdf);
    FILE *resource = fopen(path, "r");
    if (!resource)
        return -1;
    uint64_t begin, end, flags;
    for (int index = 0; index < PCI_RESOURCE_COUNT; ++index) {
        if (fscanf(resource, "%" SCNx64 " %" SCNx64 " %" SCNx64,
                   &begin, &end, &flags) != 3) {
            fclose(resource);
            return -1;
        }
    }
    fclose(resource);
    if (end < begin || end - begin + 1 < BAR5_SIZE)
        return -1;
    *start = begin;
    return 0;
}

static uint16_t le16(const uint8_t *value) {
    return value[0] | (uint16_t)value[1] << 8;
}

static int read_current_calibration(
        const char *path, struct current_calibration calibration[ATOM_SMC_DPM_V4_4_RAIL_COUNT]) {
    FILE *rom = fopen(path, "rb");
    if (!rom)
        return -1;
    if (fseek(rom, 0, SEEK_END)) {
        fclose(rom);
        return -1;
    }
    long length = ftell(rom);
    if (length < 0 || fseek(rom, 0, SEEK_SET)) {
        fclose(rom);
        return -1;
    }
    uint8_t *data = malloc((size_t)length);
    if (!data || fread(data, 1, (size_t)length, rom) != (size_t)length) {
        free(data);
        fclose(rom);
        return -1;
    }
    fclose(rom);

    int result = -1;
    if (length >= (long)ATOM_ROM_HEADER_MIN_SIZE) {
        uint16_t header = le16(data + ATOM_ROM_HEADER_POINTER_OFFSET);
        // Atom ROM header revisions place the master data-table pointer in this small range.
        for (uint16_t field = ATOM_ROM_MASTER_DATA_TABLE_FIELD_FIRST;
             field <= ATOM_ROM_MASTER_DATA_TABLE_FIELD_LAST;
             field += ATOM_ROM_MASTER_DATA_TABLE_FIELD_SIZE) {
            if ((size_t)header + field + ATOM_ROM_MASTER_DATA_TABLE_FIELD_SIZE > (size_t)length)
                continue;
            uint16_t master = le16(data + header + field);
            if ((size_t)master + ATOM_MASTER_DATA_TABLE_SMC_DPM_ENTRY_OFFSET + sizeof(uint16_t) > (size_t)length
                || data[master + ATOM_COMMON_TABLE_FORMAT_REVISION_OFFSET] != 2
                || data[master + ATOM_COMMON_TABLE_CONTENT_REVISION_OFFSET] != 1)
                continue;
            uint16_t smc_dpm = le16(data + master + ATOM_MASTER_DATA_TABLE_SMC_DPM_ENTRY_OFFSET);
            if ((size_t)smc_dpm + ATOM_SMC_DPM_V4_4_CALIBRATION_OFFSET
                    + ATOM_SMC_DPM_V4_4_RAIL_COUNT * ATOM_SMC_DPM_V4_4_CALIBRATION_SIZE > (size_t)length
                || data[smc_dpm + ATOM_COMMON_TABLE_FORMAT_REVISION_OFFSET] != 4
                || data[smc_dpm + ATOM_COMMON_TABLE_CONTENT_REVISION_OFFSET] != 4)
                continue;
            for (unsigned int rail = 0; rail < ATOM_SMC_DPM_V4_4_RAIL_COUNT; ++rail) {
                const uint8_t *entry = data + smc_dpm + ATOM_SMC_DPM_V4_4_CALIBRATION_OFFSET
                                       + rail * ATOM_SMC_DPM_V4_4_CALIBRATION_SIZE;
                calibration[rail].max_current = le16(entry);
                calibration[rail].offset = (int8_t)entry[2];
            }
            result = 0;
            break;
        }
    }
    free(data);
    return result;
}

static void print_tmon(const volatile uint32_t *bar, unsigned int tmon, uint32_t first) {
    static const char *const directions[] = {"RDIL", "RDIR"};
    for (unsigned int group = 0; group < 2; ++group) {
        for (unsigned int sensor = 0; sensor < TMON_RDI_SENSORS_PER_DIRECTION; ++sensor) {
            uint32_t value = bar[first + group * TMON_RDI_SENSORS_PER_DIRECTION + sensor];
            if (!(value & TMON_RDI_VALID_MASK)) {
                printf("    TMON_%u_%s%u              : unavailable\n", tmon, directions[group], sensor);
                continue;
            }
            // Vega 20 RDI encodes an eighth-degree value biased by -49 C.
            uint32_t raw = (value >> TMON_RDI_RAW_SHIFT) & TMON_RDI_RAW_MASK;
            printf("    TMON_%u_%s%u              : %.2f C\n",
                   tmon, directions[group], sensor,
                   raw * TMON_RDI_DEGREES_PER_CODE + TMON_RDI_DEGREES_OFFSET);
        }
    }
}

static void print_hbm(volatile uint32_t *bar) {
    uint32_t saved_index = bar[SMN_INDEX_DWORD];
    for (unsigned int stack = 0; stack < HBM_STACK_COUNT; ++stack) {
        bar[SMN_INDEX_DWORD] = HBM_TEMPERATURE_SMN_BASE + stack * HBM_TEMPERATURE_SMN_STACK_STRIDE;
        uint32_t value = bar[SMN_DATA_DWORD];
        printf("    HBM_STACK%u                : %u.00 C\n", stack,
               (value >> HBM_TEMPERATURE_SHIFT) & HBM_TEMPERATURE_MASK);
    }
    // SMN_INDEX_DWORD is a selector, so put the caller-visible state back as found.
    bar[SMN_INDEX_DWORD] = saved_index;
}

static void print_thermal_metrics(const volatile uint32_t *bar) {
    uint32_t policy = bar[TMON_THERMAL_POLICY_DWORD] & TMON_THERMAL_POLICY_MASK;
    uint32_t limit = (bar[TMON_HW_CTF_LIMIT_DWORD] >> TMON_HW_CTF_LIMIT_SHIFT)
                     & TMON_HW_CTF_LIMIT_MASK;
    printf("    THERMAL_POLICY              : %u.00 C\n", policy);
    printf("    HW_CTF_LIMIT                : %.2f C\n", limit + TMON_RDI_DEGREES_OFFSET);

    uint32_t first = bar[TMON0_RDI_FIRST_DWORD];
    if (!(first & TMON_RDI_VALID_MASK)) {
        printf("    TGRADIENT                   : unavailable\n");
        return;
    }
    // Vega 20 defines TGRADIENT as the hottest TMON0 RDI minus RDIL0.
    double baseline = ((first >> TMON_RDI_RAW_SHIFT) & TMON_RDI_RAW_MASK)
                      * TMON_RDI_DEGREES_PER_CODE + TMON_RDI_DEGREES_OFFSET;
    double maximum = baseline;
    for (unsigned int sensor = 1; sensor < TMON_TGRADIENT_SENSOR_COUNT; ++sensor) {
        uint32_t value = bar[TMON0_RDI_FIRST_DWORD + sensor];
        if (!(value & TMON_RDI_VALID_MASK))
            continue;
        double temperature = ((value >> TMON_RDI_RAW_SHIFT) & TMON_RDI_RAW_MASK)
                             * TMON_RDI_DEGREES_PER_CODE + TMON_RDI_DEGREES_OFFSET;
        if (temperature > maximum)
            maximum = temperature;
    }
    printf("    TGRADIENT                   : %.2f C\n", maximum - baseline);
}

static void print_clock_metrics(const volatile uint32_t *bar) {
    printf("    DCLK                        : %u MHz\n", bar[DCLK_COUNTER_DWORD] / CLOCK_COUNTER_CODES_PER_MHZ);
    printf("    VCLK                        : %u MHz\n", bar[VCLK_COUNTER_DWORD] / CLOCK_COUNTER_CODES_PER_MHZ);
    printf("    ECLK                        : %u MHz\n", bar[ECLK_COUNTER_DWORD] / CLOCK_COUNTER_CODES_PER_MHZ);
}

static void print_svi2(
        const volatile uint32_t *bar,
        const struct current_calibration calibration[ATOM_SMC_DPM_V4_4_RAIL_COUNT]) {
    static const char *const names[] = {"SVI2_GFX", "SVI2_SOC", "SVI2_MEM0", "SVI2_MEM1"};
    static const uint32_t registers[] = {
        SVI2_PLANE0_CHANNEL0, SVI2_PLANE0_CHANNEL1,
        SVI2_PLANE1_CHANNEL0, SVI2_PLANE1_CHANNEL1,
    };
    for (unsigned int rail = 0; rail < ATOM_SMC_DPM_V4_4_RAIL_COUNT; ++rail) {
        uint32_t value = bar[registers[rail]];
        // SVI2 returns VID in byte 2; the regulator defines 1.55 V minus 6.25 mV per code.
        double voltage = SVI2_VOLTAGE_MAX - ((value >> SVI2_VOLTAGE_SHIFT) & SVI2_VOLTAGE_MASK) * SVI2_VOLTAGE_STEP;
        // AtomBIOS stores the calibrated current endpoints at codes 0 and 255.
        double current = (value & SVI2_CURRENT_MASK) * (calibration[rail].max_current - calibration[rail].offset) / SVI2_CURRENT_CODE_MAX
                         + calibration[rail].offset;
        printf("    %-24s : %.5f V  %.3f A\n", names[rail], voltage, current);
    }
}

static int read_gpu(const char *bdf, const struct current_calibration *calibration) {
    char path[512], vendor[16], device[16];
    snprintf(path, sizeof(path), "/sys/bus/pci/devices/%s/vendor", bdf);
    if (read_line(path, vendor, sizeof(vendor)) || strcmp(vendor, "0x1002"))
        return 0;
    snprintf(path, sizeof(path), "/sys/bus/pci/devices/%s/device", bdf);
    if (read_line(path, device, sizeof(device)) || strcmp(device, "0x66a1"))
        return 0;

    uint64_t physical;
    if (bar5_start(bdf, &physical)) {
        fprintf(stderr, "%s: BAR5 is unavailable\n", bdf);
        return -1;
    }
    int mem = open("/dev/mem", O_RDWR | O_SYNC);
    if (mem < 0) {
        perror("/dev/mem");
        return -1;
    }
    volatile uint32_t *bar = mmap(NULL, BAR5_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, mem, (off_t)physical);
    if (bar == MAP_FAILED) {
        perror("mmap BAR5");
        close(mem);
        return -1;
    }
    printf("GPU %s\n", bdf);
    print_tmon(bar, 0, TMON0_RDI_FIRST_DWORD);
    print_tmon(bar, 1, TMON1_RDI_FIRST_DWORD);
    print_hbm(bar);
    print_thermal_metrics(bar);
    print_clock_metrics(bar);
    if (calibration)
        print_svi2(bar, calibration);
    munmap((void *)bar, BAR5_SIZE);
    close(mem);
    return 1;
}

int main(int argc, char *argv[]) {
    struct current_calibration calibration[ATOM_SMC_DPM_V4_4_RAIL_COUNT];
    const struct current_calibration *current = NULL;
    if (argc == 3 && !strcmp(argv[1], "--vbios")) {
        if (read_current_calibration(argv[2], calibration)) {
            fprintf(stderr, "%s: unsupported AtomBIOS SMC DPM table\n", argv[2]);
            return EXIT_FAILURE;
        }
        current = calibration;
    } else if (argc != 1) {
        fprintf(stderr, "usage: %s [--vbios ROM]\n", argv[0]);
        return EXIT_FAILURE;
    }
    DIR *devices = opendir("/sys/bus/pci/devices");
    if (!devices) {
        perror("/sys/bus/pci/devices");
        return EXIT_FAILURE;
    }
    int found = 0;
    struct dirent *entry;
    while ((entry = readdir(devices))) {
        if (entry->d_name[0] == '.')
            continue;
        int result = read_gpu(entry->d_name, current);
        if (result < 0) {
            closedir(devices);
            return EXIT_FAILURE;
        }
        found += result;
    }
    closedir(devices);
    return found ? EXIT_SUCCESS : EXIT_FAILURE;
}
