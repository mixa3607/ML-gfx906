import fcntl
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import common


class LockTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "answers.json"
        self.lock_path = self.root / "answers.json.lock"

    def test_lock_removed_after_success(self):
        with common.result_lock(self.path):
            self.assertTrue(self.lock_path.exists())
        self.assertFalse(self.lock_path.exists())

    def test_lock_removed_after_exception_or_interrupt(self):
        for error in (RuntimeError("failure"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(type(error)):
                    with common.result_lock(self.path):
                        raise error
                self.assertFalse(self.lock_path.exists())

    def test_busy_lock_not_deleted_by_contender(self):
        with common.result_lock(self.path):
            original = self.lock_path.stat()
            with self.assertRaisesRegex(ValueError, "already in use"):
                with common.result_lock(self.path):
                    self.fail("Contender entered while the lock was held")
            self.assertEqual(self.lock_path.stat().st_ino, original.st_ino)
        self.assertFalse(self.lock_path.exists())

    def test_stale_lock_reused_and_removed(self):
        self.lock_path.touch()
        with common.result_lock(self.path):
            self.assertTrue(self.lock_path.exists())
        self.assertFalse(self.lock_path.exists())

    def test_old_open_descriptor_cannot_bypass_new_owner(self):
        with common.result_lock(self.path):
            stale = self.lock_path.open("a")
        self.addCleanup(stale.close)
        self.assertFalse(self.lock_path.exists())
        original_open = Path.open
        returned_stale = False

        def open_with_stale(path, *args, **kwargs):
            nonlocal returned_stale
            if path == self.lock_path and not returned_stale:
                returned_stale = True
                return stale
            return original_open(path, *args, **kwargs)

        with common.result_lock(self.path):
            active = self.lock_path.stat()
            with patch.object(Path, "open", new=open_with_stale):
                with self.assertRaisesRegex(ValueError, "already in use"):
                    with common.result_lock(self.path):
                        self.fail("Old unlinked inode bypassed the current lock")
            self.assertTrue(returned_stale)
            self.assertTrue(stale.closed)
            self.assertEqual(self.lock_path.stat().st_ino, active.st_ino)
        self.assertFalse(self.lock_path.exists())

    def test_old_open_descriptor_retries_when_path_is_missing(self):
        with common.result_lock(self.path):
            stale = self.lock_path.open("a")
        self.addCleanup(stale.close)
        original_open = Path.open
        opens = 0

        def open_with_stale(path, *args, **kwargs):
            nonlocal opens
            if path == self.lock_path:
                opens += 1
                if opens == 1:
                    return stale
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", new=open_with_stale):
            with common.result_lock(self.path):
                self.assertTrue(self.lock_path.exists())
                self.assertEqual(opens, 2)
        self.assertFalse(self.lock_path.exists())

    def test_cleanup_does_not_remove_a_replacement_inode(self):
        with common.result_lock(self.path):
            self.lock_path.unlink()
            with self.lock_path.open("a") as replacement:
                fcntl.flock(replacement, fcntl.LOCK_EX | fcntl.LOCK_NB)
                replacement_stat = self.lock_path.stat()
        self.assertEqual(self.lock_path.stat().st_ino, replacement_stat.st_ino)

    def test_partial_multi_lock_acquisition_cleans_up_acquired_locks(self):
        other = self.root / "z-validation.json"
        with common.result_lock(other):
            with self.assertRaisesRegex(ValueError, "already in use"):
                with common.locked_paths(self.path, other):
                    self.fail("Acquired a held lock")
            self.assertFalse(self.lock_path.exists())
            self.assertTrue(other.with_name(other.name + ".lock").exists())
        self.assertEqual(list(self.root.glob("*.lock")), [])

    def test_unlink_happens_before_unlock(self):
        original_flock = fcntl.flock

        def checked_flock(stream, operation):
            if operation == fcntl.LOCK_UN:
                self.assertFalse(self.lock_path.exists())
            return original_flock(stream, operation)

        with patch.object(common.fcntl, "flock", side_effect=checked_flock):
            with common.result_lock(self.path):
                pass

    def test_process_signals_release_and_clean_up_locks(self):
        script = """
import signal
import sys
from pathlib import Path
from common import result_lock
from run import interrupted

signal.signal(signal.SIGTERM, interrupted)
try:
    with result_lock(Path(sys.argv[1])):
        print('ready', flush=True)
        sys.stdin.read()
except KeyboardInterrupt:
    pass
"""
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
            with self.subTest(signal=sig):
                with subprocess.Popen(
                    [sys.executable, "-c", script, str(self.path)], cwd=common.BENCH.parent,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True,
                ) as process:
                    try:
                        with selectors.DefaultSelector() as selector:
                            selector.register(process.stdout, selectors.EVENT_READ)
                            self.assertTrue(selector.select(timeout=5), "Child did not acquire the lock")
                        self.assertEqual(process.stdout.readline().strip(), "ready")
                        self.assertTrue(self.lock_path.exists())
                        with self.assertRaisesRegex(ValueError, "already in use"):
                            with common.result_lock(self.path):
                                self.fail("Parent bypassed the child process's lock")
                        self.assertTrue(self.lock_path.exists())
                        process.send_signal(sig)
                        _, errors = process.communicate(timeout=5)
                        if sig == signal.SIGKILL:
                            self.assertEqual(process.returncode, -signal.SIGKILL, errors)
                            self.assertTrue(self.lock_path.exists())
                            with common.result_lock(self.path):
                                pass
                        else:
                            self.assertEqual(process.returncode, 0, errors)
                        self.assertFalse(self.lock_path.exists())
                    finally:
                        if process.returncode is None:
                            process.kill()
                            process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
