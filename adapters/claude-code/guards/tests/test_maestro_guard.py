import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))

from testlib.isolation import isolated_env, symlink_or_skip  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "hooks" / "maestro_guard.py"


def run(payload, config=None, raw=None, args=(), extra_env=None):
    stdin = raw if raw is not None else json.dumps(payload)
    with tempfile.TemporaryDirectory() as profile:
        env = isolated_env(profile)
        env.pop("CLAUDE_CONFIG_DIR", None)
        if config is not None:
            env.update(CLAUDE_CONFIG_DIR=str(config), HOME=str(config), USERPROFILE=str(config))
        env.update(extra_env or {})
        return subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin, capture_output=True, text=True, env=env)


def main_call(tool, **tool_input):
    return {"tool_name": tool, "tool_input": tool_input, "session_id": "s", "cwd": "/"}


def bash(command):
    return main_call("Bash", command=command)


class MaestroGuardTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.config = self.tmp / "config"
        self.config.mkdir()
        self.args = []

    def assertAllowed(self, payload):
        result = run(payload, self.config, args=self.args)
        self.assertEqual(result.returncode, 0, result.stderr)

    def assertBlocked(self, payload):
        result = run(payload, self.config, args=self.args)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Main session only orchestrates", result.stderr)

    def with_side(self, side, *extra):
        self.args = ["--side", str(side), *extra]

    def test_subagent_edit_allowed(self):
        payload = main_call("Edit", file_path="/x/a.ts")
        payload["agent_id"] = "abc"
        self.assertAllowed(payload)

    def test_subagent_grep_allowed(self):
        payload = main_call("Grep", pattern="a", path="/etc")
        payload["agent_id"] = "abc"
        self.assertAllowed(payload)

    def test_main_edit_blocked(self):
        self.assertBlocked(main_call("Edit", file_path="/x/a.ts"))

    def test_block_message_is_generic(self):
        result = run(main_call("Edit", file_path="/x/a.ts"), self.config)
        self.assertIn("dispatch this to a worker subagent", result.stderr)

    def test_main_write_memory_allowed(self):
        memory = self.tmp / "notes" / "memory"
        memory.mkdir(parents=True)
        self.with_side(self.tmp / "notes")
        self.assertAllowed(main_call("Write", file_path=str(memory / "x.md")))

    def test_main_write_memory_dotdot_blocked(self):
        memory = self.tmp / "notes" / "memory"
        memory.mkdir(parents=True)
        self.with_side(self.tmp / "notes")
        self.assertBlocked(main_call("Write", file_path=f"{memory}/../x.md"))

    def test_main_write_memory_symlink_escape_blocked(self):
        memory = self.tmp / "notes" / "memory"
        memory.mkdir(parents=True)
        symlink_or_skip(memory / "link", self.tmp)
        self.with_side(self.tmp / "notes")
        self.assertBlocked(main_call("Write", file_path=str(memory / "link" / "x.md")))

    def test_main_write_without_side_blocked(self):
        self.assertBlocked(main_call("Write", file_path=f"{self.tmp}/x.md"))

    def test_main_write_outside_paths_blocked(self):
        memory = self.tmp / "notes" / "memory"
        memory.mkdir(parents=True)
        self.with_side(self.tmp / "notes")
        for tool in ["Edit", "Write"]:
            with self.subTest(tool=tool):
                self.assertBlocked(main_call(tool, file_path=f"{self.tmp}/other/x.md"))

    def test_main_git_readonly_allowed(self):
        for cmd in [
            "git status",
            "git diff --stat main",
            "git log --oneline -5",
            "git show HEAD:a.ts",
            "git -C /srv/repo status --short",
            "git -C ~/x diff --stat",
        ]:
            with self.subTest(cmd=cmd):
                self.assertAllowed(bash(cmd))

    def test_main_bash_blocked(self):
        for cmd in [
            "npm test",
            "git diff > f",
            "git diff --output=f",
            "git -c x=y diff",
            "git difftool -x sh",
            "git status; rm -rf x",
            "echo $(id)",
            "git diff --ext-diff",
            "git log | sh",
            "git -C /tmp log > f",
            'git -C "a b" status',
            "git -C x -c y=z diff",
            "git -C x difftool -x sh",
        ]:
            with self.subTest(cmd=cmd):
                self.assertBlocked(bash(cmd))

    def test_main_one_call_commands_allowed(self):
        for cmd in ["ls -la /tmp", "wc -l a.txt", "head -n 5 a.txt", "cat a.txt", "jq .a b.json"]:
            with self.subTest(cmd=cmd):
                self.assertAllowed(bash(cmd))

    def test_main_one_call_commands_blocked(self):
        for cmd in [
            "cp /dev/null ~/.claude/maestro-guard.off",
            "cp x ~/.claude/settings.json",
            "mv a ~/.bashrc",
            "cp --target-directory=/etc a",
            "cp a b; rm x",
            "cp a b && rm x",
            "cat a | sh",
            "ls > f",
            "cat $(echo a)",
            "cat `echo a`",
            "rm a",
            "git commit -m x",
            "ls\nrm a",
        ]:
            with self.subTest(cmd=cmd):
                self.assertBlocked(bash(cmd))

    def test_main_blocked_tools(self):
        for tool in ["NotebookEdit", "MultiEdit", "mcp__server__send"]:
            with self.subTest(tool=tool):
                self.assertBlocked(main_call(tool))

    def test_main_allowed_tools(self):
        for tool in ["Agent", "Read", "Glob", "Skill", "ToolSearch", "AskUserQuestion",
                     "WebFetch", "WebSearch"]:
            with self.subTest(tool=tool):
                self.assertAllowed(main_call(tool))

    def test_main_read_any_file_allowed(self):
        self.assertAllowed(main_call("Read", file_path="/etc/hostname"))

    def with_grep_roots(self):
        vault = self.tmp / "vault"
        for name in ["memory", "tasks", "other"]:
            (vault / name).mkdir(parents=True)
        symlink_or_skip(self.config / "vault", vault)
        self.with_side("~/vault")
        return vault

    def test_main_grep_allowed_roots(self):
        vault = self.with_grep_roots()
        for path in [vault / "memory", vault / "memory" / "x.md", "~/vault/tasks"]:
            with self.subTest(path=path):
                self.assertAllowed(main_call("Grep", pattern="a", path=str(path)))

    def test_main_grep_elsewhere_blocked(self):
        vault = self.with_grep_roots()
        symlink_or_skip(vault / "memory" / "link", vault / "other")
        for path in [
            vault / "other",
            vault,
            vault / "memory" / ".." / "other",
            vault / "memory" / "link",
            vault / "memoryx",
            self.tmp,
        ]:
            with self.subTest(path=path):
                self.assertBlocked(main_call("Grep", pattern="a", path=str(path)))

    def test_main_grep_without_side_blocked(self):
        self.assertBlocked(main_call("Grep", pattern="a", path=str(self.tmp)))

    def test_main_grep_without_path_blocked(self):
        self.with_grep_roots()
        self.assertBlocked(main_call("Grep", pattern="a"))

    def test_main_grep_non_string_path_blocked(self):
        self.assertBlocked(main_call("Grep", pattern="a", path=["x"]))

    def test_main_write_memory_backslash_path_allowed(self):
        memory = self.tmp / "notes" / "memory"
        memory.mkdir(parents=True)
        self.with_side(self.tmp / "notes")
        self.assertAllowed(main_call("Write", file_path=f"{memory}\\x.md"))

    def test_main_write_memory_backslash_dotdot_blocked(self):
        memory = self.tmp / "notes" / "memory"
        memory.mkdir(parents=True)
        self.with_side(self.tmp / "notes")
        self.assertBlocked(main_call("Write", file_path=f"{memory}\\..\\x.md"))

    def test_main_write_outside_backslash_path_blocked(self):
        self.with_side(self.tmp / "notes")
        self.assertBlocked(main_call("Write", file_path=f"{self.tmp}\\other\\x.md"))

    def test_main_grep_core_allowed_but_write_blocked(self):
        core = self.tmp / "core"
        core.mkdir()
        self.with_side(self.tmp / "notes", "--core", str(core))
        self.assertAllowed(main_call("Grep", pattern="a", path=str(core / "rules")))
        self.assertBlocked(main_call("Write", file_path=str(core / "x.md")))

    def test_unknown_argument_warns_and_keeps_guarding(self):
        self.args = ["--bogus", "x"]
        result = run(main_call("Edit", file_path="/x/a.ts"), self.config, args=self.args)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("step=parse-args", result.stderr)

    def test_internal_error_fails_open_naming_step_and_input(self):
        failing = self.tmp / "failing"
        failing.mkdir()
        (failing / "sitecustomize.py").write_text(
            "import os.path\n\n\ndef broken(path):\n    raise OSError('forced')\n\n\nos.path.realpath = broken\n",
            encoding="utf-8",
        )
        result = run(
            main_call("Write", file_path="/x/a.md"), self.config, args=self.args, extra_env={"PYTHONPATH": str(failing)}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("step=decide", result.stderr)
        self.assertIn("input=tool Write", result.stderr)

    def test_non_ascii_path_outside_side_blocked_on_utf8_stdin(self):
        self.with_side(self.tmp / "notes")
        env = isolated_env(self.tmp / "profile", CLAUDE_CONFIG_DIR=str(self.config))
        stdin = json.dumps(main_call("Write", file_path=str(self.tmp / "ação" / "x.md")), ensure_ascii=False)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *self.args], input=stdin.encode("utf-8"), capture_output=True, env=env
        )
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_off_switch(self):
        (self.config / "maestro-guard.off").touch()
        self.assertAllowed(main_call("Edit", file_path="/x/a.ts"))

    def test_default_config_dir_is_dot_claude_under_home(self):
        (self.config / ".claude").mkdir()
        (self.config / ".claude" / "maestro-guard.off").touch()
        env = isolated_env(self.tmp / "profile", HOME=str(self.config), USERPROFILE=str(self.config))
        env.pop("CLAUDE_CONFIG_DIR", None)
        result = subprocess.run(
            [sys.executable, str(SCRIPT)], input=json.dumps(main_call("Edit", file_path="/x")),
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_json_fails_open(self):
        result = run(None, self.config, raw="not json")
        self.assertEqual(result.returncode, 0)
        self.assertIn("warning", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
