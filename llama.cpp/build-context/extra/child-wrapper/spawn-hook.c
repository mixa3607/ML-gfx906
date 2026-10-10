#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <limits.h>
#include <spawn.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef int (*spawn_fn)(pid_t *, const char *, const posix_spawn_file_actions_t *,
                        const posix_spawnattr_t *, char *const [], char *const []);

static int spawn_with_wrapper(const char *symbol, pid_t *pid, const char *path,
                              const posix_spawn_file_actions_t *actions,
                              const posix_spawnattr_t *attrs,
                              char *const argv[], char *const envp[]) {
    spawn_fn original = (spawn_fn) dlsym(RTLD_NEXT, symbol);
    if (!original) {
        return ENOSYS;
    }

    const char *wrapper = getenv("M36_LLAMA_CHILD_WRAPPER");
    char self[PATH_MAX];
    ssize_t length;
    if (!wrapper || !*wrapper) {
        return original(pid, path, actions, attrs, argv, envp);
    }
    length = readlink("/proc/self/exe", self, sizeof(self) - 1);
    if (length < 0 || length == sizeof(self) - 1) {
        return original(pid, path, actions, attrs, argv, envp);
    }
    self[length] = '\0';
    if (strcmp(path, self) != 0) {
        return original(pid, path, actions, attrs, argv, envp);
    }

    if (wrapper[0] != '/') {
        return EINVAL;
    }
    size_t argc = 0;
    while (argv[argc]) {
        argc++;
    }
    char **child_argv = calloc(argc + 3, sizeof(*child_argv));
    if (!child_argv) {
        return ENOMEM;
    }
    child_argv[0] = (char *) wrapper;
    child_argv[1] = (char *) path;
    for (size_t i = 1; i < argc; i++) {
        child_argv[i + 1] = argv[i];
    }

    int result = original(pid, wrapper, actions, attrs, child_argv, envp);
    free(child_argv);
    return result;
}

int posix_spawn(pid_t *pid, const char *path,
                const posix_spawn_file_actions_t *actions,
                const posix_spawnattr_t *attrs,
                char *const argv[], char *const envp[]) {
    return spawn_with_wrapper("posix_spawn", pid, path, actions, attrs, argv, envp);
}

int posix_spawnp(pid_t *pid, const char *path,
                 const posix_spawn_file_actions_t *actions,
                 const posix_spawnattr_t *attrs,
                 char *const argv[], char *const envp[]) {
    return spawn_with_wrapper("posix_spawnp", pid, path, actions, attrs, argv, envp);
}
