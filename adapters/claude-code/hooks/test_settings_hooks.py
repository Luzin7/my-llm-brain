import json
import re
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


def script_of(hook):
    match = re.search(r"\{\{CORE\}\}/(adapters/claude-code/hooks/[a-z-]+)", hook["command"])
    return match.group(1) if match else None


class SettingsHooksTest(unittest.TestCase):
    def test_every_entry_has_timeout(self):
        for _, _, hook in entries():
            with self.subTest(command=hook["command"]):
                self.assertIsInstance(hook.get("timeout"), int)

    def test_dispatch_matcher_covers_agent_and_task(self):
        matchers = [group.get("matcher") for _, group, hook in entries() if "subagent-cap" in hook["command"]]
        self.assertEqual(matchers, ["Agent|Task"])

    def test_every_entry_is_a_command_hook(self):
        for _, _, hook in entries():
            with self.subTest(command=hook["command"]):
                self.assertEqual(hook["type"], "command")

    def test_every_entry_names_an_existing_script(self):
        for _, _, hook in entries():
            with self.subTest(command=hook["command"]):
                self.assertTrue((CORE / str(script_of(hook))).is_file())


if __name__ == "__main__":
    unittest.main()
