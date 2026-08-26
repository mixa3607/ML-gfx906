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
#define TMON0_RDIL0 0x1660d
#define TMON1_RDIL0 0x16631
#define SMN_INDEX 0x0e
#define SMN_DATA 0x0f
#define HBM_TEMP_BASE 0x57148
#define SVI2_PLANE0_CHANNEL1 0x16803
#define SVI2_PLANE0_CHANNEL0 0x16804
#define SVI2_PLANE1_CHANNEL0 0x16805
#define SVI2_PLANE1_CHANNEL1 0x16806

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
    for (int index = 0; index < 6; ++index) {
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

static int read_current_calibration(const char *path, struct current_calibration calibration[4]) {
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
    if (length >= 0x4a) {
        uint16_t header = le16(data + 0x48);
        for (uint16_t field = 0x1c; field <= 0x24; field += 2) {
            if ((size_t)header + field + 2 > (size_t)length)
                continue;
            uint16_t master = le16(data + header + field);
            if ((size_t)master + 12 > (size_t)length || data[master + 2] != 2 || data[master + 3] != 1)
                continue;
            uint16_t smc_dpm = le16(data + master + 8);
            if ((size_t)smc_dpm + 0x2c > (size_t)length || data[smc_dpm + 2] != 4 || data[smc_dpm + 3] != 4)
                continue;
            for (unsigned int rail = 0; rail < 4; ++rail) {
                const uint8_t *entry = data + smc_dpm + 0x1c + rail * 4;
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
        for (unsigned int sensor = 0; sensor < 16; ++sensor) {
            uint32_t value = bar[first + group * 16 + sensor];
            if (!(value & 0x800)) {
                printf("    TMON_%u_%s%u              : unavailable\n", tmon, directions[group], sensor);
                continue;
            }
            uint32_t raw = (value >> 12) & 0xfff;
            printf("    TMON_%u_%s%u              : %.2f C\n",
                   tmon, directions[group], sensor, raw * 0.125 - 49.0);
        }
    }
}

static void print_hbm(volatile uint32_t *bar) {
    uint32_t saved_index = bar[SMN_INDEX];
    for (unsigned int stack = 0; stack < 4; ++stack) {
        bar[SMN_INDEX] = HBM_TEMP_BASE + stack * 0x200000;
        uint32_t value = bar[SMN_DATA];
        printf("    HBM_STACK%u                : %u.00 C\n", stack, (value >> 16) & 0xff);
    }
    // SMN_INDEX is a selector, so put the caller-visible state back as found.
    bar[SMN_INDEX] = saved_index;
}

static void print_svi2(const volatile uint32_t *bar, const struct current_calibration calibration[4]) {
    static const char *const names[] = {"SVI2_GFX", "SVI2_SOC", "SVI2_MEM0", "SVI2_MEM1"};
    static const uint32_t registers[] = {
        SVI2_PLANE0_CHANNEL0, SVI2_PLANE0_CHANNEL1,
        SVI2_PLANE1_CHANNEL0, SVI2_PLANE1_CHANNEL1,
    };
    for (unsigned int rail = 0; rail < 4; ++rail) {
        uint32_t value = bar[registers[rail]];
        double voltage = 1.55 - ((value >> 16) & 0xff) * 0.00625;
        double current = (value & 0xff) * (calibration[rail].max_current - calibration[rail].offset) / 255.0
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
    print_tmon(bar, 0, TMON0_RDIL0);
    print_tmon(bar, 1, TMON1_RDIL0);
    print_hbm(bar);
    if (calibration)
        print_svi2(bar, calibration);
    munmap((void *)bar, BAR5_SIZE);
    close(mem);
    return 1;
}

int main(int argc, char *argv[]) {
    struct current_calibration calibration[4];
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
