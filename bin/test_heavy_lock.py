import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from testlib.isolation import isolated_env  # noqa: E402

SCRIPT = Path(__file__).with_name("heavy-lock")


def start(args, lock, timeout="30"):
    env = isolated_env(lock.parent / "profile", HEAVY_LOCK_FILE=str(lock), HEAVY_LOCK_TIMEOUT=timeout)
    return subprocess.Popen(
        [sys.executable, str(SCRIPT), *args], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )


class HeavyLockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lock = Path(self.tmp.name) / "heavy.lock"

    def test_runs_command_and_returns_its_exit_code(self):
        job = start([sys.executable, "-c", "print('ok'); raise SystemExit(3)"], self.lock)
        out, _ = job.communicate()
        self.assertEqual((job.returncode, out.strip()), (3, "ok"))

    def test_second_job_waits_for_first(self):
        log = Path(self.tmp.name) / "log"
        body = "import sys,time; open(sys.argv[1],'a').write('s'+sys.argv[2]+'\\n'); time.sleep(0.6); open(sys.argv[1],'a').write('e'+sys.argv[2]+'\\n')"
        first = start([sys.executable, "-c", body, str(log), "1"], self.lock)
        time.sleep(0.2)
        second = start([sys.executable, "-c", body, str(log), "2"], self.lock)
        first.wait()
        second.wait()
        self.assertEqual(log.read_text().split(), ["s1", "e1", "s2", "e2"])

    def test_wait_timeout_fails_loudly(self):
        holder = start([sys.executable, "-c", "import time; time.sleep(3)"], self.lock)
        time.sleep(0.3)
        waiter = start([sys.executable, "-c", "print('ran')"], self.lock, timeout="1")
        out, err = waiter.communicate()
        holder.kill()
        holder.wait()
        self.assertEqual(waiter.returncode, 75)
        self.assertIn("heavy-lock", err)
        self.assertEqual(out, "")

    def test_lock_released_when_job_dies(self):
        first = start([sys.executable, "-c", "raise SystemExit(1)"], self.lock)
        first.wait()
        second = start([sys.executable, "-c", "print('ok')"], self.lock, timeout="2")
        out, _ = second.communicate()
        self.assertEqual((second.returncode, out.strip()), (0, "ok"))

    def default_path_env(self, **extra):
        base = {key: value for key, value in os.environ.items() if key != "HEAVY_LOCK_FILE"}
        env = isolated_env(Path(self.tmp.name) / "profile", base=base)
        env["HOME"] = str(Path(self.tmp.name) / "home")
        env["USERPROFILE"] = env["HOME"]
        env.pop("XDG_STATE_HOME")
        env.update(extra)
        return env

    def default_lock_dir(self, env):
        if os.name == "nt":
            return Path(env["LOCALAPPDATA"]) / "brain"
        return Path(env["HOME"]) / ".local" / "state" / "brain"

    def run_default(self, env):
        return subprocess.run([sys.executable, str(SCRIPT), sys.executable, "-c", "pass"], env=env, capture_output=True, text=True)

    def test_default_lock_under_xdg_state_home(self):
        state = Path(self.tmp.name) / "state"
        result = self.run_default(self.default_path_env(XDG_STATE_HOME=str(state)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((state / "brain" / "heavy.lock").exists())

    def test_default_lock_falls_back_to_home_local_state(self):
        env = self.default_path_env()
        result = self.run_default(env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.default_lock_dir(env) / "heavy.lock").exists())

    def test_empty_xdg_state_home_is_treated_as_unset(self):
        env = self.default_path_env(XDG_STATE_HOME="")
        self.assertEqual(self.run_default(env).returncode, 0)
        self.assertTrue((self.default_lock_dir(env) / "heavy.lock").exists())

    def test_no_command_is_usage_error(self):
        job = start([], self.lock)
        _, err = job.communicate()
        self.assertEqual(job.returncode, 64)
        self.assertIn("usage", err.lower())

    def test_missing_command_reports_127(self):
        job = start(["definitely-not-a-command-xyz"], self.lock)
        _, err = job.communicate()
        self.assertEqual(job.returncode, 127)
        self.assertIn("heavy-lock", err)


if __name__ == "__main__":
    unittest.main()
