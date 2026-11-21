import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARDS = Path(__file__).resolve().parents[1]
ROOT = GUARDS.parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from testlib.isolation import isolated_env  # noqa: E402

PLUGIN_ROOT = "${CLAUDE_PLUGIN_ROOT}"
EVENTS = {"SessionStart", "PreToolUse", "UserPromptSubmit"}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def entries():
    for event, groups in read_json(GUARDS / "hooks" / "hooks.json")["hooks"].items():
        for group in groups:
            for hook in group["hooks"]:
                yield event, group, hook


def script_of(hook):
    return GUARDS / hook["args"][1].replace(PLUGIN_ROOT + "/", "")


class HooksJsonTest(unittest.TestCase):
    def test_events_are_the_expected_ones(self):
        self.assertEqual({event for event, _, _ in entries()}, EVENTS)

    def test_every_entry_is_exec_form_on_the_configured_python(self):
        for _, _, hook in entries():
            with self.subTest(args=hook["args"]):
                self.assertEqual(hook["type"], "command")
                self.assertEqual(hook["command"], "${user_config.python}")
                self.assertEqual(hook["args"][0], "-I")

    def test_no_entry_uses_shell_form(self):
        for _, _, hook in entries():
            with self.subTest(args=hook["args"]):
                self.assertNotIn("test ", hook["command"])
                self.assertNotIn("||", hook["command"])
                self.assertEqual(hook["command"].split(), [hook["command"]])

    def test_every_entry_fails_open_with_a_timeout(self):
        for _, _, hook in entries():
            with self.subTest(args=hook["args"]):
                self.assertEqual(hook["onFailure"], "continue")
                self.assertIsInstance(hook.get("timeout"), int)
                self.assertLessEqual(hook["timeout"], 10)

    def test_every_entry_names_an_existing_plugin_script(self):
        for _, _, hook in entries():
            with self.subTest(args=hook["args"]):
                self.assertTrue(hook["args"][1].startswith(f"{PLUGIN_ROOT}/hooks/"))
                self.assertTrue(script_of(hook).is_file())

    def test_dispatch_matcher_covers_agent_and_task(self):
        matchers = [group.get("matcher") for _, group, hook in entries() if "subagent_cap" in hook["args"][1]]
        self.assertEqual(matchers, ["Agent|Task"])

    def test_maestro_guard_receives_the_side_option(self):
        args = [hook["args"] for _, _, hook in entries() if "maestro_guard" in hook["args"][1]]
        self.assertEqual([a[2:] for a in args], [["--side", "${user_config.side}"]])

    def test_plugin_declares_side_and_python_options(self):
        manifest = read_json(GUARDS / ".claude-plugin" / "plugin.json")
        self.assertEqual(manifest["name"], "brain-guards")
        self.assertEqual(sorted(manifest["userConfig"]), ["python", "side"])

    def test_marketplace_lists_both_plugins_with_existing_sources(self):
        plugins = read_json(ROOT / ".claude-plugin" / "marketplace.json")["plugins"]
        self.assertEqual([plugin["name"] for plugin in plugins], ["brain", "brain-guards"])
        for plugin in plugins:
            self.assertTrue((ROOT / plugin["source"] / ".claude-plugin" / "plugin.json").is_file())


class SessionStartTest(unittest.TestCase):
    def run_hook(self):
        script = GUARDS / "hooks" / "session_start.py"
        with tempfile.TemporaryDirectory() as profile:
            env = isolated_env(profile)
            return subprocess.run([sys.executable, "-I", str(script)], capture_output=True, text=True, env=env)

    def test_prints_health_line_with_python_version(self):
        result = self.run_hook()
        expected = f"brain-guards active (python {sys.version_info.major}.{sys.version_info.minor})\n"
        self.assertEqual((result.returncode, result.stdout), (0, expected))

    def test_is_idempotent(self):
        self.assertEqual(self.run_hook().stdout, self.run_hook().stdout)


if __name__ == "__main__":
    unittest.main()
