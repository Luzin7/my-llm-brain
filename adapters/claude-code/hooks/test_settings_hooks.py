import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ADAPTER = Path(__file__).resolve().parents[1]
CORE = ADAPTER.parents[1]


def entries():
    data = json.loads((ADAPTER / "settings.hooks.json").read_text())
    for event, groups in data["hooks"].items():
        for group in groups:
            for hook in group["hooks"]:
                yield event, group, hook


def run_command(hook, core):
    command = hook["command"].replace("{{CORE}}", str(core))
    return subprocess.run(["sh", "-c", command], input="", capture_output=True, text=True)


class SettingsHooksTest(unittest.TestCase):
    def test_every_entry_has_timeout(self):
        for _, _, hook in entries():
            with self.subTest(command=hook["command"]):
                self.assertIsInstance(hook.get("timeout"), int)

    def test_dispatch_matcher_covers_agent_and_task(self):
        matchers = [group.get("matcher") for _, group, hook in entries() if "subagent-cap" in hook["command"]]
        self.assertEqual(matchers, ["Agent|Task"])

    def test_missing_core_fails_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            for _, _, hook in entries():
                with self.subTest(command=hook["command"]):
                    result = run_command(hook, Path(tmp) / "moved")
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_present_core_runs_the_script(self):
        for _, _, hook in entries():
            with self.subTest(command=hook["command"]):
                result = run_command(hook, CORE)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
