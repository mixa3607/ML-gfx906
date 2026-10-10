import os
from pathlib import Path
import subprocess
import tempfile
import unittest


HARNESS = r"""
#define _GNU_SOURCE
#include <limits.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

extern char **environ;

int main(int argc, char **argv) {
    if (argc > 1 && strcmp(argv[1], "child") == 0) {
        printf("arg=%s\nwrapped=%s\nwrapper=%s\n", argv[2],
               getenv("WRAPPED") ? getenv("WRAPPED") : "no",
               getenv("M36_LLAMA_CHILD_WRAPPER") ? "set" : "unset");
        return 0;
    }
    char self[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", self, sizeof(self) - 1);
    if (n < 0) return 1;
    self[n] = '\0';
    char *args[] = {self, "child", "spaces and 'quotes'", NULL};
    char *other_args[] = {"/bin/echo", "other", NULL};
    int other = strcmp(argv[1], "other") == 0;
    posix_spawn_file_actions_t actions;
    posix_spawn_file_actions_init(&actions);
    posix_spawn_file_actions_adddup2(&actions, STDERR_FILENO, STDOUT_FILENO);
    pid_t pid;
    int result = (strcmp(argv[1], "spawnp") == 0 ? posix_spawnp : posix_spawn)(
        &pid, other ? "/bin/echo" : self, &actions, NULL,
        other ? other_args : args, environ);
    posix_spawn_file_actions_destroy(&actions);
    if (result) {
        printf("spawn_error=%d\n", result);
        return 1;
    }
    int status;
    if (waitpid(pid, &status, 0) < 0) return 1;
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}
"""


class SpawnHookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="child-wrapper-")
        cls.root = Path(cls.temp.name)
        cls.library = cls.root / "spawn-hook.so"
        cls.harness = cls.root / "harness"
        source = Path(__file__).with_name("spawn-hook.c")
        compiler = os.environ.get("CC", "cc")
        subprocess.run([
            compiler, "-O2", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
            str(source), "-o", str(cls.library), "-ldl",
        ], check=True)
        harness_source = cls.root / "harness.c"
        harness_source.write_text(HARNESS)
        subprocess.run([
            compiler, "-Wall", "-Wextra", "-Werror", str(harness_source),
            "-o", str(cls.harness),
        ], check=True)
        cls.wrapper = cls.root / "wrapper with spaces.sh"
        cls.wrapper.write_text(
            '#!/bin/bash\nset -e\nunset M36_LLAMA_CHILD_WRAPPER\n'
            'export WRAPPED=yes\nbinary=$1\nshift\nexec "$binary" "$@"\n'
        )
        cls.wrapper.chmod(0o755)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_harness(self, mode="spawn", wrapper=None):
        env = dict(os.environ, LD_PRELOAD=str(self.library))
        env.pop("M36_LLAMA_CHILD_WRAPPER", None)
        env.pop("WRAPPED", None)
        if wrapper is not None:
            env["M36_LLAMA_CHILD_WRAPPER"] = str(wrapper)
        return subprocess.run(
            [str(self.harness), mode], env=env, capture_output=True, text=True,
            timeout=10,
        )

    def test_wrapper_and_file_actions(self):
        for mode in ("spawn", "spawnp"):
            with self.subTest(mode=mode):
                result = self.run_harness(mode, self.wrapper)
                self.assertEqual(result.returncode, 0, result)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr,
                                 "arg=spaces and 'quotes'\nwrapped=yes\nwrapper=unset\n")

    def test_without_wrapper(self):
        for wrapper in (None, ""):
            with self.subTest(wrapper=wrapper):
                result = self.run_harness(wrapper=wrapper)
                self.assertEqual(result.returncode, 0, result)
                self.assertIn("wrapped=no", result.stderr)

    def test_other_executable_is_not_wrapped(self):
        result = self.run_harness("other", self.wrapper)
        self.assertEqual(result.returncode, 0, result)
        self.assertEqual(result.stderr, "other\n")

    def test_missing_wrapper_fails(self):
        result = self.run_harness(wrapper=self.root / "missing.sh")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "spawn_error=2\n")

    def test_nonexecutable_wrapper_fails(self):
        wrapper = self.root / "not-executable.sh"
        wrapper.write_text("#!/bin/bash\nexit 0\n")
        wrapper.chmod(0o644)
        result = self.run_harness(wrapper=wrapper)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "spawn_error=13\n")

    def test_relative_wrapper_fails(self):
        result = self.run_harness(wrapper="relative.sh")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "spawn_error=22\n")


if __name__ == "__main__":
    unittest.main()
