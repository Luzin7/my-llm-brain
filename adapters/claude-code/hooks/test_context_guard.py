import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("context-guard")


def run(stdin, env_extra=None):
    env = dict(os.environ)
    env.pop("CONTEXT_GUARD_TOKENS", None)
    env.update(env_extra or {})
    if not SCRIPT.exists():
        return subprocess.CompletedProcess([], 127, "", "context-guard missing")
    return subprocess.run(
        [str(SCRIPT)], input=stdin, capture_output=True, text=True, env=env
    )


def assistant(input_tokens, cache_read=0, cache_creation=0, sidechain=False):
    return {
        "type": "assistant",
        "isSidechain": sidechain,
        "message": {
            "role": "assistant",
            "usage": {
                "input_tokens": input_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_creation,
                "output_tokens": 5,
            },
        },
    }


class ContextGuardTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def transcript(self, lines):
        path = self.tmp / "t.jsonl"
        path.write_text(
            "\n".join(l if isinstance(l, str) else json.dumps(l) for l in lines) + "\n"
        )
        return path

    def hook(self, path, env=None):
        return run(json.dumps({"transcript_path": str(path)}), env)

    def assertSilent(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_below_threshold_silent(self):
        path = self.transcript([assistant(10, 50000, 1000)])
        self.assertSilent(self.hook(path))

    def test_at_threshold_injects_context(self):
        path = self.transcript([assistant(1000, 98000, 1000)])
        result = self.hook(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "UserPromptSubmit")
        self.assertIn("100K", output["additionalContext"])

    def test_sums_all_three_token_fields(self):
        path = self.transcript([assistant(50000, 60000, 40000)])
        result = self.hook(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertIn("150K", output["additionalContext"])

    def test_message_recommends_clear(self):
        path = self.transcript([assistant(150000)])
        result = self.hook(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("/clear", text)
        self.assertIn("unrelated", text)

    def test_uses_last_main_entry(self):
        path = self.transcript([assistant(150000), assistant(20000)])
        self.assertSilent(self.hook(path))

    def test_sidechain_entries_ignored(self):
        path = self.transcript([assistant(20000), assistant(150000, sidechain=True)])
        self.assertSilent(self.hook(path))

    def test_only_sidechain_entries_silent(self):
        path = self.transcript([assistant(150000, sidechain=True)])
        self.assertSilent(self.hook(path))

    def test_env_threshold_overrides_default(self):
        path = self.transcript([assistant(5000)])
        result = self.hook(path, {"CONTEXT_GUARD_TOKENS": "1000"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("additionalContext", result.stdout)

    def test_env_threshold_raises_default(self):
        path = self.transcript([assistant(150000)])
        self.assertSilent(self.hook(path, {"CONTEXT_GUARD_TOKENS": "200000"}))

    def test_missing_transcript_fails_open(self):
        self.assertSilent(self.hook(self.tmp / "nope.jsonl"))

    def test_garbled_lines_skipped(self):
        path = self.transcript(["{not json", assistant(150000), "also garbage"])
        result = self.hook(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("150K", result.stdout)

    def test_only_garbled_lines_silent(self):
        path = self.transcript(["{not json", "[]"])
        self.assertSilent(self.hook(path))

    def test_no_assistant_entries_silent(self):
        path = self.transcript([{"type": "user", "message": {"content": "hi"}}])
        self.assertSilent(self.hook(path))

    def test_bad_stdin_fails_open(self):
        self.assertSilent(run("not json"))

    def test_empty_stdin_fails_open(self):
        self.assertSilent(run(""))

    def test_missing_transcript_path_fails_open(self):
        self.assertSilent(run(json.dumps({})))


if __name__ == "__main__":
    unittest.main()
