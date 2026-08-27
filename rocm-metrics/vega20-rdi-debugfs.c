// Read Vega 20 telemetry through amdgpu's debugfs register interface.
#define main vega20_rdi_bar5_main
#include "vega20-rdi.c"
#undef main

static int debugfs_read_dword(int fd, uint32_t dword, uint32_t *value) {
    if (lseek(fd, (off_t)dword * sizeof(*value), SEEK_SET) < 0)
        return -1;
    return read(fd, value, sizeof(*value)) == (ssize_t)sizeof(*value) ? 0 : -1;
}

static int debugfs_write_dword(int fd, uint32_t dword, uint32_t value) {
    if (lseek(fd, (off_t)dword * sizeof(value), SEEK_SET) < 0)
        return -1;
    return write(fd, &value, sizeof(value)) == (ssize_t)sizeof(value) ? 0 : -1;
}

static int copy_dwords(int fd, uint32_t *bar, uint32_t first, uint32_t count) {
    for (uint32_t index = 0; index < count; ++index) {
        if (debugfs_read_dword(fd, first + index, &bar[first + index]))
            return -1;
    }
    return 0;
}

static int print_hbm_debugfs(int fd) {
    uint32_t saved_index;
    if (debugfs_read_dword(fd, SMN_INDEX_DWORD, &saved_index))
        return -1;
    for (unsigned int stack = 0; stack < HBM_STACK_COUNT; ++stack) {
        uint32_t value;
        if (debugfs_write_dword(fd, SMN_INDEX_DWORD,
                                HBM_TEMPERATURE_SMN_BASE + stack * HBM_TEMPERATURE_SMN_STACK_STRIDE)
                || debugfs_read_dword(fd, SMN_DATA_DWORD, &value)) {
            debugfs_write_dword(fd, SMN_INDEX_DWORD, saved_index);
            return -1;
        }
        printf("    HBM_STACK%u                : %u.00 C\n", stack,
               (value >> HBM_TEMPERATURE_SHIFT) & HBM_TEMPERATURE_MASK);
    }
    return debugfs_write_dword(fd, SMN_INDEX_DWORD, saved_index);
}

static int read_gpu_debugfs(const char *bdf, const struct current_calibration *calibration) {
    char path[512], vendor[16], device[16];
    snprintf(path, sizeof(path), "/sys/bus/pci/devices/%s/vendor", bdf);
    if (read_line(path, vendor, sizeof(vendor)) || strcmp(vendor, "0x1002"))
        return 0;
    snprintf(path, sizeof(path), "/sys/bus/pci/devices/%s/device", bdf);
    if (read_line(path, device, sizeof(device)) || strcmp(device, "0x66a1"))
        return 0;

    snprintf(path, sizeof(path), "/sys/kernel/debug/dri/%s/amdgpu_regs", bdf);
    int fd = open(path, O_RDWR);
    if (fd < 0) {
        perror(path);
        return -1;
    }
    uint32_t *bar = calloc(BAR5_SIZE, sizeof(*bar));
    if (!bar) {
        perror("calloc");
        close(fd);
        return -1;
    }

    int failed = copy_dwords(fd, bar, TMON0_RDI_FIRST_DWORD, TMON_RDI_SENSORS_PER_DIRECTION * 2)
                 || copy_dwords(fd, bar, TMON1_RDI_FIRST_DWORD, TMON_RDI_SENSORS_PER_DIRECTION * 2)
                 || copy_dwords(fd, bar, TMON_THERMAL_POLICY_DWORD, 1)
                 || copy_dwords(fd, bar, TMON_HW_CTF_LIMIT_DWORD, 1)
                 || copy_dwords(fd, bar, DCLK_COUNTER_DWORD, 1)
                 || copy_dwords(fd, bar, VCLK_COUNTER_DWORD, 1)
                 || copy_dwords(fd, bar, ECLK_COUNTER_DWORD, 1);
    static const uint32_t svi2_registers[] = {
        SVI2_PLANE0_CHANNEL0, SVI2_PLANE0_CHANNEL1,
        SVI2_PLANE1_CHANNEL0, SVI2_PLANE1_CHANNEL1,
    };
    for (unsigned int rail = 0; !failed && rail < ATOM_SMC_DPM_V4_4_RAIL_COUNT; ++rail)
        failed = debugfs_read_dword(fd, svi2_registers[rail], &bar[svi2_registers[rail]]);
    if (failed) {
        perror("amdgpu_regs read");
        free(bar);
        close(fd);
        return -1;
    }

    printf("GPU %s\n", bdf);
    print_tmon(bar, 0, TMON0_RDI_FIRST_DWORD);
    print_tmon(bar, 1, TMON1_RDI_FIRST_DWORD);
    if (print_hbm_debugfs(fd))
        printf("    HBM stacks                 : unavailable\n");
    print_thermal_metrics(bar);
    print_clock_metrics(bar);
    if (calibration)
        print_svi2(bar, calibration);
    free(bar);
    close(fd);
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
        int result = read_gpu_debugfs(entry->d_name, current);
        if (result < 0) {
            closedir(devices);
            return EXIT_FAILURE;
        }
        found += result;
    }
    closedir(devices);
    return found ? EXIT_SUCCESS : EXIT_FAILURE;
}
