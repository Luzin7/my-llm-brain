import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))

from testlib.isolation import isolated_env, symlink_or_skip  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "hooks" / "subagent_cap.py"


def payload(session="s1", agent_id=None, tool="Agent"):
    event = {"tool_name": tool, "tool_input": {}, "session_id": session, "cwd": "/"}
    if agent_id:
        event["agent_id"] = agent_id
    return json.dumps(event)


class SubagentCapTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config = Path(self._tmp.name) / "config"

    def env(self, cap=None, config=None, extra_env=()):
        extra_env = dict(extra_env)
        env = isolated_env(Path(self._tmp.name) / "profile", CLAUDE_CONFIG_DIR=str(config or self.config))
        env.pop("SUBAGENT_CAP", None)
        env.pop("CLAUDE_PLUGIN_DATA", None)
        env.update(extra_env)
        if cap is not None:
            env["SUBAGENT_CAP"] = str(cap)
        return env

    def run_hook(self, stdin, **kw):
        return subprocess.run(
            [sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True, env=self.env(**kw)
        )

    def call(self, n, **kw):
        for _ in range(n):
            result = self.run_hook(payload(), **kw)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_cap_allows_25_and_blocks_26th(self):
        self.call(25)
        result = self.run_hook(payload())
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("cap", result.stderr)

    def test_env_cap_overrides_default(self):
        self.call(2, cap=2)
        self.assertEqual(self.run_hook(payload(), cap=2).returncode, 2)

    def test_invalid_cap_falls_back_to_default(self):
        self.call(3, cap="abc")

    def test_blocked_calls_do_not_raise_the_count(self):
        self.call(1, cap=1)
        for _ in range(3):
            self.assertEqual(self.run_hook(payload(), cap=1).returncode, 2)

    def test_subagent_calls_not_counted(self):
        for _ in range(5):
            result = self.run_hook(payload(agent_id="abc"), cap=1)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.call(1, cap=1)

    def test_task_tool_name_counts_like_agent(self):
        for _ in range(2):
            result = self.run_hook(payload(tool="Task"), cap=2)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_hook(payload(tool="Agent"), cap=2).returncode, 2)

    def test_other_tools_not_counted(self):
        for _ in range(3):
            result = self.run_hook(payload(tool="Read"), cap=1)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.call(1, cap=1)

    def test_sessions_are_independent(self):
        self.call(1, cap=1)
        self.assertEqual(self.run_hook(payload("s1"), cap=1).returncode, 2)
        self.assertEqual(self.run_hook(payload("s2"), cap=1).returncode, 0)

    def test_two_concurrent_at_24_allow_exactly_one(self):
        self.call(24)
        procs = [
            subprocess.Popen(
                [sys.executable, str(SCRIPT)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, env=self.env(),
            )
            for _ in range(2)
        ]
        for proc in procs:
            proc.stdin.write(payload())
            proc.stdin.close()
        codes = sorted(proc.wait() for proc in procs)
        for proc in procs:
            proc.stdout.close()
            proc.stderr.close()
        self.assertEqual(codes, [0, 2])

    def concurrent_codes(self, count, session, cap):
        procs = [
            subprocess.Popen(
                [sys.executable, str(SCRIPT)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, env=self.env(cap=cap),
            )
            for _ in range(count)
        ]
        for proc in procs:
            proc.stdin.write(payload(session))
            proc.stdin.close()
        codes = sorted(proc.wait() for proc in procs)
        for proc in procs:
            proc.stdout.close()
            proc.stderr.close()
        return codes

    def test_concurrent_calls_count_is_exact_on_repeated_rounds(self):
        for session in ("round-1", "round-2"):
            with self.subTest(session=session):
                self.assertEqual(self.concurrent_codes(8, session, 5), [0] * 5 + [2] * 3)

    def test_state_lives_under_plugin_data_when_set(self):
        data = Path(self._tmp.name) / "plugin-data"
        result = self.run_hook(payload(), extra_env={"CLAUDE_PLUGIN_DATA": str(data)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((data / "subagent-cap").is_dir())
        self.assertFalse((self.config / "state").exists())

    def state_file(self):
        return next(path for path in (self.config / "state" / "subagent-cap").iterdir() if path.name != ".lock")

    def test_corrupt_state_fails_open_naming_step_and_input(self):
        self.call(1, cap=1)
        self.state_file().write_text("not a number", encoding="utf-8")
        result = self.run_hook(payload(), cap=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("step=read-state", result.stderr)
        self.assertIn("input=counter file", result.stderr)

    def test_corrupt_state_is_repaired_so_the_cap_still_applies(self):
        self.call(1, cap=1)
        self.state_file().write_bytes(b"\xff\xfe\x00")
        self.assertEqual(self.run_hook(payload(), cap=1).returncode, 0)
        self.assertEqual(self.run_hook(payload(), cap=1).returncode, 2)

    def test_unwritable_state_allows_with_warning(self):
        blocker = Path(self._tmp.name) / "file"
        blocker.write_text("x")
        result = self.run_hook(payload(), cap=1, config=blocker)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("warning", result.stderr.lower())

    def test_invalid_json_allows_with_warning(self):
        result = self.run_hook("not json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("warning", result.stderr.lower())

    def test_missing_session_id_allows_with_warning(self):
        result = self.run_hook(json.dumps({"tool_name": "Agent"}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("warning", result.stderr.lower())

    def test_prunes_state_older_than_seven_days(self):
        state = self.config / "state" / "subagent-cap"
        state.mkdir(parents=True)
        old, fresh = state / "old", state / "fresh"
        old.write_text("3")
        fresh.write_text("3")
        stale = time.time() - 8 * 86400
        os.utime(old, (stale, stale))
        self.call(1)
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())


if __name__ == "__main__":
    unittest.main()
