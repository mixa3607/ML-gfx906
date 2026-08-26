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

static int read_gpu(const char *bdf) {
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
    munmap((void *)bar, BAR5_SIZE);
    close(mem);
    return 1;
}

int main(void) {
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
        int result = read_gpu(entry->d_name);
        if (result < 0) {
            closedir(devices);
            return EXIT_FAILURE;
        }
        found += result;
    }
    closedir(devices);
    return found ? EXIT_SUCCESS : EXIT_FAILURE;
}
