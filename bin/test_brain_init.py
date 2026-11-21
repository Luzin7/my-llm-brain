import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from testlib.isolation import isolated_env, refuse_real_profile, symlink_or_skip  # noqa: E402

COPIED = ("bin", "core", "adapters", "examples", "templates")

MATRIX = [("claude-code", 1), ("claude-code", 2), ("claude-code", 3),
          ("opencode", 1), ("opencode", 2), ("opencode", 3),
          ("agents-md", 1)]


def tree_hash(*roots):
    digest = hashlib.sha256()
    for root in roots:
        for path in sorted(Path(root).rglob("*")):
            digest.update(str(path.relative_to(root)).encode())
            if path.is_file():
                digest.update(path.read_bytes())
    return digest.hexdigest()


SNIPPET_MARKER = "never edited by brain-init):\n"


def snippet_of(result):
    return result.stdout.split(SNIPPET_MARKER, 1)[1]


def words(path):
    return len(Path(path).read_text().split())


RETIRED_ON_WINDOWS = unittest.skipIf(os.name == 'nt', 'retired in T2')


@RETIRED_ON_WINDOWS
class BrainInitCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="brain-init-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.claude = self.tmp / "claude-config"
        self.xdg = self.tmp / "xdg"
        self.opencode = self.xdg / "opencode"
        for path in (self.home, self.claude, self.xdg, self.opencode):
            path.mkdir()
        refuse_real_profile(self.tmp)
        self.env = isolated_env(self.tmp / "profile", HOME=str(self.home), USERPROFILE=str(self.home),
                                CLAUDE_CONFIG_DIR=str(self.claude), XDG_CONFIG_HOME=str(self.xdg),
                                XDG_STATE_HOME=str(self.home / "state"))
        self.side = self.tmp / "side"

    def init(self, *args, root=ROOT, side=None):
        command = [sys.executable, str(root / "bin" / "brain-init"), str(side or self.side), *args]
        return subprocess.run(command, env=self.env, capture_output=True, text=True, timeout=120)

    def config_dir(self, harness):
        return self.claude if harness == "claude-code" else self.opencode

    def install(self, harness, level=None, *extra):
        args = ["--harness", harness, "--config-dir", str(self.config_dir(harness)), *extra]
        if level:
            args += ["--level", str(level)]
        if harness == "agents-md":
            args += ["--target", str(self.tmp / "AGENTS.md")]
        return self.init(*args)

    def backups(self, directory, name):
        return sorted(p.name for p in Path(directory).glob(f"{name}.*") if p.is_file() and "bak" in p.name)


class TestInstallMatrix(BrainInitCase):
    def test_each_harness_and_level_installs_and_verifies(self):
        for harness, level in MATRIX:
            with self.subTest(harness=harness, level=level):
                shutil.rmtree(self.side, ignore_errors=True)
                result = self.install(harness, level)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                if harness == "opencode":
                    (self.opencode / "opencode.json").write_text(snippet_of(result))
                verify = self.init("--verify")
                self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)

    def test_verify_on_uninstalled_side_exits_1_saying_not_installed(self):
        verify = self.init("--verify")
        self.assertEqual(verify.returncode, 1)
        self.assertIn("not installed", verify.stdout + verify.stderr)

    def test_second_run_is_byte_identical(self):
        for harness, level in MATRIX:
            with self.subTest(harness=harness, level=level):
                shutil.rmtree(self.side, ignore_errors=True)
                self.assertEqual(self.install(harness, level).returncode, 0)
                before = tree_hash(self.side, self.claude, self.opencode, self.tmp / "AGENTS.md") \
                    if (self.tmp / "AGENTS.md").is_dir() else tree_hash(self.side, self.claude, self.opencode)
                agents_file = self.tmp / "AGENTS.md"
                agents_before = agents_file.read_bytes() if agents_file.exists() else None
                self.assertEqual(self.install(harness, level).returncode, 0)
                self.assertEqual(tree_hash(self.side, self.claude, self.opencode), before)
                if agents_before is not None:
                    self.assertEqual(agents_file.read_bytes(), agents_before)


class TestSideTemplate(BrainInitCase):
    def test_template_copied_into_new_side(self):
        self.assertEqual(self.install("claude-code", 2).returncode, 0)
        for name in ("rules/side.md", "rules/preferences.md", "memory/MEMORY.md", "brain-sync.json"):
            self.assertTrue((self.side / name).is_file(), name)
        for name in ("tasks", "specs"):
            self.assertTrue((self.side / name).is_dir(), name)

    def test_existing_side_files_are_not_overwritten(self):
        (self.side / "rules").mkdir(parents=True)
        (self.side / "rules" / "side.md").write_text("mine\n")
        self.assertEqual(self.install("claude-code", 2).returncode, 0)
        self.assertEqual((self.side / "rules" / "side.md").read_text(), "mine\n")


class TestClaudeCode(BrainInitCase):
    def test_hand_written_configs_preserved(self):
        (self.claude / "CLAUDE.md").write_text("# mine\nkeep this\n")
        (self.claude / "settings.json").write_text(json.dumps(
            {"theme": "dark", "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
                {"type": "command", "command": "echo mine"}]}]}}))
        for _ in range(2):
            self.assertEqual(self.install("claude-code", 3).returncode, 0)
        claude_md = (self.claude / "CLAUDE.md").read_text()
        self.assertIn("keep this", claude_md)
        self.assertEqual(claude_md.count(f"@{self.side}/.generated/CLAUDE.md"), 1)
        settings_text = (self.claude / "settings.json").read_text()
        settings = json.loads(settings_text)
        self.assertEqual(settings["theme"], "dark")
        self.assertEqual(settings_text.count("echo mine"), 1)
        for hook in ("maestro-guard", "subagent-cap", "context-guard"):
            commands = [h["command"] for groups in settings["hooks"].values() for g in groups
                        for h in g["hooks"] if hook in h["command"]]
            self.assertEqual(len(commands), 1, hook)
        self.assertEqual(len(self.backups(self.claude, "CLAUDE.md")), 1)
        self.assertEqual(len(self.backups(self.claude, "settings.json")), 1)

    def test_foreign_auto_memory_directory_kept_with_warning(self):
        (self.claude / "settings.json").write_text(json.dumps({"autoMemoryDirectory": "/somewhere/else"}))
        result = self.install("claude-code", 2)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("autoMemoryDirectory", result.stdout + result.stderr)
        self.assertIn("warning", (result.stdout + result.stderr).lower())
        self.assertEqual(json.loads((self.claude / "settings.json").read_text())["autoMemoryDirectory"],
                         "/somewhere/else")

    def test_auto_memory_directory_set_when_unset(self):
        self.assertEqual(self.install("claude-code", 2).returncode, 0)
        settings = json.loads((self.claude / "settings.json").read_text())
        self.assertEqual(settings["autoMemoryDirectory"], str(self.side / "memory"))

    def test_always_loaded_defaults_within_2500_words(self):
        self.assertEqual(self.install("claude-code").returncode, 0)
        total = words(self.side / ".generated" / "CLAUDE.md") + words(self.claude / "CLAUDE.md") \
            + words(self.side / "memory" / "MEMORY.md")
        self.assertLessEqual(total, 2500)

    def test_moved_core_fails_verify_naming_dead_hook(self):
        old = self.tmp / "core-old"
        for name in COPIED:
            if (ROOT / name).exists():
                shutil.copytree(ROOT / name, old / name, ignore=shutil.ignore_patterns("__pycache__"))
        self.assertEqual(self.init("--harness", "claude-code", "--level", "3", "--config-dir",
                                   str(self.claude), root=old).returncode, 0)
        self.assertEqual(self.init("--verify", root=old).returncode, 0)
        new = self.tmp / "core-new"
        old.rename(new)
        verify = self.init("--verify", root=new)
        self.assertEqual(verify.returncode, 1)
        self.assertIn("maestro-guard", verify.stdout + verify.stderr)
        self.assertNotIn("not installed", verify.stdout + verify.stderr)


class TestStaleHook(BrainInitCase):
    def test_stale_hook_command_and_timeout_updated(self):
        stale = 'python3 "/old/core/adapters/claude-code/hooks/subagent-cap"'
        (self.claude / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
            {"matcher": "Agent", "hooks": [{"type": "command", "command": stale, "timeout": 99}]}]}}))
        self.assertEqual(self.install("claude-code", 3).returncode, 0)
        entries = [h for g in json.loads((self.claude / "settings.json").read_text())["hooks"]["PreToolUse"]
                   for h in g["hooks"] if "subagent-cap" in h["command"]]
        self.assertEqual(len(entries), 1)
        self.assertNotIn("/old/core", entries[0]["command"])
        self.assertEqual(entries[0]["timeout"], 10)


class TestCrashRecovery(BrainInitCase):
    def test_rerun_after_crash_before_manifests_takes_over_written_files(self):
        self.assertEqual(self.install("claude-code", 2).returncode, 0)
        for manifest in (self.claude / "agents", self.claude / "skills", self.side / ".generated"):
            (manifest / ".my-llm-brain-manifest").unlink()
        result = self.install("claude-code", 2)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.init("--verify").returncode, 0)


class TestSymlinkedConfig(BrainInitCase):
    def test_symlinked_files_stay_links_and_real_files_are_updated(self):
        real = self.tmp / "dotfiles"
        real.mkdir()
        for name, text in (("CLAUDE.md", "# mine\n"), ("settings.json", '{"theme": "dark"}')):
            (real / name).write_text(text)
            symlink_or_skip(self.claude / name, real / name)
        self.assertEqual(self.install("claude-code", 2).returncode, 0)
        for name in ("CLAUDE.md", "settings.json"):
            self.assertTrue((self.claude / name).is_symlink(), name)
        self.assertIn(f"@{self.side}/.generated/CLAUDE.md", (real / "CLAUDE.md").read_text())
        self.assertEqual(json.loads((real / "settings.json").read_text())["theme"], "dark")
        self.assertEqual(len(self.backups(real, "settings.json")), 1)


class TestUninstall(BrainInitCase):
    def test_uninstall_after_core_moved_restores_user_files(self):
        (self.claude / "CLAUDE.md").write_text("# mine\nkeep this\n")
        original = {"theme": "dark", "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": "echo mine"}]}]}}
        (self.claude / "settings.json").write_text(json.dumps(original))
        old = self.tmp / "core-old"
        for name in COPIED:
            shutil.copytree(ROOT / name, old / name, ignore=shutil.ignore_patterns("__pycache__"))
        args = ["--harness", "claude-code", "--level", "3", "--config-dir", str(self.claude)]
        self.assertEqual(self.init(*args, root=old).returncode, 0)
        (self.claude / "state" / "subagent-cap").mkdir(parents=True)
        new = self.tmp / "core-new"
        old.rename(new)
        result = self.init("--uninstall", root=new)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.claude / "CLAUDE.md").read_text(), "# mine\nkeep this\n")
        self.assertEqual(json.loads((self.claude / "settings.json").read_text()), original)
        for name in ("maestro-guard.paths", "maestro-guard.grep-paths", "state", "agents", "skills"):
            self.assertFalse((self.claude / name).exists(), name)
        verify = self.init("--verify", root=new)
        self.assertEqual(verify.returncode, 1)
        self.assertIn("not installed", verify.stdout + verify.stderr)
        self.assertEqual(self.init(*args, root=new).returncode, 0)

    def test_uninstall_after_core_moved_backs_up_every_removed_file(self):
        old = self.tmp / "core-old"
        for name in COPIED:
            shutil.copytree(ROOT / name, old / name, ignore=shutil.ignore_patterns("__pycache__"))
        args = ["--harness", "claude-code", "--config-dir", str(self.claude)]
        self.assertEqual(self.init(*args, root=old).returncode, 0)
        new = self.tmp / "core-new"
        old.rename(new)
        result = self.init("--uninstall", root=new)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        saved = {p.name for p in (self.side / ".generated" / "uninstall-backups").rglob("*.md")}
        self.assertIn("reviewer.md", saved)
        self.assertIn("SKILL.md", saved)

    def test_edited_owned_file_backed_up_and_unedited_removed_without_backup(self):
        self.assertEqual(self.install("claude-code", 2).returncode, 0)
        reviewer = self.claude / "agents" / "reviewer.md"
        reviewer.write_text(reviewer.read_text() + "my own line\n")
        result = self.init("--uninstall")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.claude / "agents").exists())
        saved = [p for p in (self.side / ".generated" / "uninstall-backups").rglob("*") if p.is_file()]
        self.assertEqual([p.name for p in saved], ["reviewer.md"])
        self.assertIn("my own line", saved[0].read_text())
        self.assertIn(str(saved[0]), result.stdout)

    def test_claude_md_with_only_our_line_is_emptied_not_deleted_when_symlinked(self):
        real = self.tmp / "dotfiles"
        real.mkdir()
        (real / "CLAUDE.md").write_text("")
        symlink_or_skip(self.claude / "CLAUDE.md", real / "CLAUDE.md")
        self.assertEqual(self.install("claude-code", 2).returncode, 0)
        self.assertEqual(self.init("--uninstall").returncode, 0)
        self.assertTrue((self.claude / "CLAUDE.md").is_symlink())
        self.assertEqual((real / "CLAUDE.md").read_text(), "")

    def test_claude_md_with_only_our_line_is_deleted_when_regular_file(self):
        self.assertEqual(self.install("claude-code", 2).returncode, 0)
        self.assertEqual(self.init("--uninstall").returncode, 0)
        self.assertFalse((self.claude / "CLAUDE.md").exists())

    def test_uninstall_keeps_foreign_auto_memory_directory(self):
        (self.claude / "settings.json").write_text(json.dumps({"autoMemoryDirectory": "/somewhere/else"}))
        self.assertEqual(self.install("claude-code", 2).returncode, 0)
        self.assertEqual(self.init("--uninstall").returncode, 0)
        settings = json.loads((self.claude / "settings.json").read_text())
        self.assertEqual(settings["autoMemoryDirectory"], "/somewhere/else")

    def test_uninstall_opencode_and_agents_md_remove_owned_files(self):
        self.assertEqual(self.install("opencode", 3).returncode, 0)
        self.assertEqual(self.init("--uninstall").returncode, 0)
        self.assertEqual(list(self.opencode.iterdir()), [])
        shutil.rmtree(self.side)
        self.assertEqual(self.install("agents-md", 1).returncode, 0)
        self.assertEqual(self.init("--uninstall").returncode, 0)
        self.assertFalse((self.tmp / "AGENTS.md").exists())

    def test_uninstall_on_uninstalled_side_exits_1(self):
        result = self.init("--uninstall")
        self.assertEqual(result.returncode, 1)
        self.assertIn("not installed", result.stdout + result.stderr)


class TestOldHookCommand(BrainInitCase):
    def test_old_command_form_rewritten_once(self):
        old = f'python3 "{ROOT}/adapters/claude-code/hooks/maestro-guard"'
        (self.claude / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
            {"matcher": "*", "hooks": [{"type": "command", "command": old, "timeout": 99}]}]}}))
        for _ in range(2):
            self.assertEqual(self.install("claude-code", 3).returncode, 0)
        entries = [h for g in json.loads((self.claude / "settings.json").read_text())["hooks"]["PreToolUse"]
                   for h in g["hooks"] if "maestro-guard" in h["command"]]
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0]["command"].startswith("test ! -f"))
        self.assertEqual(entries[0]["timeout"], 10)
        self.assertEqual(len(self.backups(self.claude, "settings.json")), 1)


class TestRefusals(BrainInitCase):
    def test_legacy_manifest_dir_refused_with_nothing_written(self):
        agents = self.claude / "agents"
        agents.mkdir()
        (agents / ".brain-sync-manifest").write_text("x.md\n")
        before = tree_hash(self.tmp)
        result = self.install("claude-code", 2)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(".brain-sync-manifest", result.stdout + result.stderr)
        self.assertEqual(tree_hash(self.tmp), before)
        self.assertFalse(self.side.exists())

    def test_side_inside_core_refused_with_nothing_written(self):
        side = ROOT / "brain-init-test-side"
        self.addCleanup(shutil.rmtree, side, ignore_errors=True)
        before = tree_hash(self.claude)
        result = self.init("--harness", "claude-code", "--config-dir", str(self.claude), side=side)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("inside the core", result.stdout + result.stderr)
        self.assertFalse(side.exists())
        self.assertEqual(tree_hash(self.claude), before)


class TestDryRun(BrainInitCase):
    def test_dry_run_writes_nothing(self):
        for harness, level in MATRIX:
            with self.subTest(harness=harness, level=level):
                before = tree_hash(self.tmp)
                result = self.install(harness, level, "--dry-run")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(tree_hash(self.tmp), before)
                self.assertFalse(self.side.exists())


class TestOpencode(BrainInitCase):
    def test_jsonc_untouched_and_snippet_printed_filled(self):
        jsonc = self.opencode / "opencode.jsonc"
        jsonc.write_text('{\n  // mine\n  "theme": "dark",\n}\n')
        before = hashlib.sha256(jsonc.read_bytes()).hexdigest()
        result = self.install("opencode", 3)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(hashlib.sha256(jsonc.read_bytes()).hexdigest(), before)
        self.assertIn('"default_agent": "maestro"', result.stdout)
        self.assertIn(str(self.side / "memory" / "MEMORY.md"), result.stdout)
        self.assertIn(f"file://{self.opencode}/plugins/subagent-cap.js", result.stdout)
        self.assertNotIn("{{", result.stdout)

    def test_hand_written_agents_md_refused(self):
        (self.opencode / "AGENTS.md").write_text("mine\n")
        result = self.install("opencode", 2)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("AGENTS.md", result.stdout + result.stderr)
        self.assertEqual((self.opencode / "AGENTS.md").read_text(), "mine\n")


class TestOpencodePlugins(BrainInitCase):
    def test_l3_installs_helper_modules_and_plugins_import(self):
        result = self.install("opencode", 3)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        plugins = self.opencode / "plugins"
        for name in ("with-timeout.mjs", "context-guard-core.mjs"):
            self.assertTrue((plugins / name).is_file(), name)
        self.assertFalse(list(plugins.glob("*.test.*")))
        self.assertNotIn("with-timeout", snippet_of(result))
        for name in ("subagent-cap.js", "context-guard.js"):
            imported = subprocess.run(["node", "-e", f"import('{plugins / name}')"], capture_output=True, text=True)
            self.assertEqual(imported.returncode, 0, imported.stderr)


class TestOpencodeVerify(BrainInitCase):
    def test_verify_reports_snippet_not_applied(self):
        self.assertEqual(self.install("opencode", 3).returncode, 0)
        verify = self.init("--verify")
        self.assertEqual(verify.returncode, 1)
        self.assertIn("snippet not applied", verify.stdout + verify.stderr)


class TestAgentsMd(BrainInitCase):
    def test_target_generated_by_another_core_refused(self):
        target = self.tmp / "AGENTS.md"
        target.write_text("<!-- my-llm-brain generated file; core: /elsewhere/core -->\n\nbody\n")
        result = self.install("agents-md", 1)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("AGENTS.md", result.stdout + result.stderr)
        self.assertIn("body", target.read_text())

    def test_writes_one_file_within_4000_words(self):
        target = self.tmp / "AGENTS.md"
        result = self.install("agents-md", 1)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLessEqual(words(target), 4000)
        self.assertGreater(words(target), 0)
        self.assertEqual(sorted(p.name for p in self.tmp.glob("AGENTS*")), ["AGENTS.md"])
        self.assertEqual(list(self.claude.iterdir()), [])
        self.assertEqual(list(self.opencode.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
