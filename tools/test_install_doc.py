import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from testlib.isolation import isolated_env, real_profile_snapshot

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "INSTALL.md"
FENCE = re.compile(r"^```(sh|powershell) install-test:([\w-]+)\n(.*?)^```$", re.MULTILINE | re.DOTALL)
REPO_PATH = re.compile(r"\b(?:dist|core|templates|adapters|tools|docs|bin)/[\w./-]+")
MARKETPLACE_LINE = "/plugin install brain --marketplace Luzin7/my-llm-brain"
START = "<!-- my-llm-brain:start -->"
END = "<!-- my-llm-brain:end -->"
BASE = ("vars", "helpers", "python", "v1", "side")
PWSH = shutil.which("pwsh")
ON_WINDOWS = os.name == "nt"
POSIX_ONLY = unittest.skipIf(ON_WINDOWS, "POSIX flavor")
NEEDS_POWERSHELL = unittest.skipUnless(ON_WINDOWS or PWSH, "pwsh not available")


def blocks(flavor):
    found = {}
    for kind, step, body in FENCE.findall(INSTALL.read_text(encoding="utf-8")):
        if kind == flavor:
            found[step] = body
    return found


def snapshot(root):
    return {
        str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
        for path in sorted(Path(root).rglob("*"))
    }


def outside_markers(text):
    return re.sub(rf"{re.escape(START)}.*?{re.escape(END)}\n?", "", text, flags=re.DOTALL)


class InstallDocContract(unittest.TestCase):
    def test_blocks_exist_for_both_flavors(self):
        self.assertTrue(blocks("sh"))
        self.assertTrue(blocks("powershell"))

    def test_every_repo_path_named_exists(self):
        text = INSTALL.read_text(encoding="utf-8")
        named = {match.rstrip(".,:;)") for match in REPO_PATH.findall(text)}
        missing = sorted(path for path in named if not (ROOT / path).exists())
        self.assertEqual([], missing)

    def test_marketplace_names_match_manifest(self):
        manifest = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        text = INSTALL.read_text(encoding="utf-8")
        self.assertEqual("my-llm-brain", manifest["name"])
        for plugin in manifest["plugins"]:
            self.assertIn(f"{plugin['name']}@{manifest['name']}", text)

    def test_readmes_carry_prompt_marketplace_line_and_same_structure(self):
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        portuguese = (ROOT / "README.pt-BR.md").read_text(encoding="utf-8")
        for text in (english, portuguese):
            self.assertIn("INSTALL.md", text)
            self.assertIn(MARKETPLACE_LINE, text)
        self.assertEqual(english.count("\n## "), portuguese.count("\n## "))

    def test_root_agents_md_points_to_install(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("INSTALL.md", text)


class InstallScenarios:
    flavor = None
    harnesses = ()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.env = isolated_env(self.root)
        self.home = Path(self.env["HOME"])
        self.side = self.home / "my-brain"
        self.claude = Path(self.env["CLAUDE_CONFIG_DIR"])
        self.codex = Path(self.env["CODEX_HOME"])
        self.opencode = Path(self.env["XDG_CONFIG_HOME"]) / "opencode"
        self.skills = self.home / ".agents/skills/task-board"
        self.agents_target = self.root / "project/AGENTS.md"
        self.before = real_profile_snapshot()
        self.addCleanup(self.assert_real_profile_untouched)

    def assert_real_profile_untouched(self):
        self.assertEqual(self.before, real_profile_snapshot())

    def script(self, steps):
        found = blocks(self.flavor)
        body = "\n".join(found[step] for step in steps)
        if self.flavor == "sh":
            return f'AGENTS_TARGET="{self.agents_target}"\n{body}\n'
        return f"$ErrorActionPreference = 'Stop'\n$AgentsTarget = '{self.agents_target}'\n{body}\n"

    def run_steps(self, steps):
        suffix = ".sh" if self.flavor == "sh" else ".ps1"
        path = self.root / f"run{suffix}"
        path.write_text(self.script(steps), encoding="utf-8", newline="\n")
        command = ["sh", "-eu", str(path)] if self.flavor == "sh" else [PWSH or "pwsh", "-NoProfile", "-File", str(path)]
        return subprocess.run(command, cwd=ROOT, env=self.env, capture_output=True, text=True, timeout=120)

    def ok(self, steps):
        result = self.run_steps(steps)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return result.stdout

    def install(self, harness):
        self.ok([*BASE, f"{harness}-install"])

    def verify(self, harness):
        return self.run_steps([*BASE, f"{harness}-verify"])

    def uninstall(self, harness):
        self.ok(["vars", "helpers", f"{harness}-uninstall"])

    def test_side_created_once_and_second_run_is_byte_identical(self):
        self.install("claude")
        self.assertTrue((self.side / "rules/side.md").is_file())
        first = snapshot(self.root)
        self.install("claude")
        self.assertEqual(first, snapshot(self.root))

    def test_existing_side_is_left_untouched(self):
        (self.side / "rules").mkdir(parents=True)
        (self.side / "rules/side.md").write_text("mine\n", encoding="utf-8")
        self.install("claude")
        self.assertEqual("mine\n", (self.side / "rules/side.md").read_text(encoding="utf-8"))
        self.assertFalse((self.side / "memory").exists())

    def test_claude_block_appears_once_and_user_text_survives_roundtrip(self):
        original = "# my own rules\nkeep me\n"
        (self.claude / "CLAUDE.md").write_text(original, encoding="utf-8")
        self.install("claude")
        self.install("claude")
        text = (self.claude / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertEqual(1, text.count(START))
        self.assertEqual(original, outside_markers(text))
        self.assertTrue(self.verify("claude").returncode == 0)
        self.uninstall("claude")
        self.assertEqual(original, (self.claude / "CLAUDE.md").read_text(encoding="utf-8"))
        self.assertFalse((self.claude / "settings.json").exists())
        self.assertTrue(self.side.is_dir())

    def test_marker_text_inside_prose_is_left_untouched(self):
        original = f"I write {START} and {END} inside a sentence.\nkeep me\n"
        (self.claude / "CLAUDE.md").write_text(original, encoding="utf-8")
        self.install("claude")
        text = (self.claude / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith(original))
        self.assertEqual(1, text.splitlines().count(START))
        self.uninstall("claude")
        self.assertEqual(original, (self.claude / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_marker_text_inside_prose_survives_uninstall_without_block(self):
        original = f"see {START} in the docs\n"
        (self.claude / "CLAUDE.md").write_text(original, encoding="utf-8")
        self.uninstall("claude")
        self.assertEqual(original, (self.claude / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_end_before_start_is_refused_and_file_untouched(self):
        original = f"{END}\nmine\n{START}\n"
        (self.claude / "CLAUDE.md").write_text(original, encoding="utf-8")
        result = self.run_steps([*BASE, "claude-install"])
        self.assertNotEqual(0, result.returncode)
        self.assertIn("STOP", result.stdout + result.stderr)
        self.assertEqual(original, (self.claude / "CLAUDE.md").read_text(encoding="utf-8"))
        result = self.run_steps(["vars", "helpers", "claude-uninstall"])
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(original, (self.claude / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_codex_copies_equal_dist_and_roundtrip_restores_agents_md(self):
        original = "# codex notes\nkeep me\n"
        (self.codex / "AGENTS.md").write_text(original, encoding="utf-8")
        self.install("codex")
        self.install("codex")
        for source in (ROOT / "dist/codex/agents").iterdir():
            self.assertEqual(source.read_bytes(), (self.codex / "agents" / source.name).read_bytes())
        skill = ROOT / "dist/opencode/skills/task-board/SKILL.md"
        self.assertEqual(skill.read_bytes(), (self.skills / "SKILL.md").read_bytes())
        text = (self.codex / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(1, text.count(START))
        self.assertEqual(original, outside_markers(text))
        self.assertEqual(0, self.verify("codex").returncode)
        self.uninstall("codex")
        self.assertEqual(original, (self.codex / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertEqual([], list((self.codex / "agents").iterdir()))
        self.assertFalse(self.skills.exists())
        self.assertTrue(self.side.is_dir())

    def test_codex_verify_fails_on_stale_revision(self):
        self.install("codex")
        target = self.codex / "AGENTS.md"
        text = target.read_text(encoding="utf-8")
        target.write_text(re.sub(r"rev = \S+", "rev = 0000000", text), encoding="utf-8")
        result = self.verify("codex")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("rev '0000000'", result.stdout + result.stderr)

    def test_edited_copy_is_renamed_to_bak_never_deleted(self):
        self.install("codex")
        edited = self.codex / "agents/brain-reviewer.toml"
        edited.write_text(edited.read_text(encoding="utf-8") + "# mine\n", encoding="utf-8")
        self.uninstall("codex")
        self.assertFalse(edited.exists())
        backups = list((self.codex / "agents").glob("brain-reviewer.toml.bak-*"))
        self.assertEqual(1, len(backups))
        self.assertIn("# mine", backups[0].read_text(encoding="utf-8"))

    def test_foreign_file_with_same_name_is_not_overwritten(self):
        (self.codex / "agents").mkdir(parents=True)
        foreign = self.codex / "agents/brain-reviewer.toml"
        foreign.write_text("name = \"mine\"\n", encoding="utf-8")
        output = self.run_steps([*BASE, "codex-install"])
        self.assertEqual(0, output.returncode, output.stdout + output.stderr)
        self.assertEqual("name = \"mine\"\n", foreign.read_text(encoding="utf-8"))
        self.assertIn("SKIP", output.stdout)
        self.uninstall("codex")
        self.assertEqual("name = \"mine\"\n", foreign.read_text(encoding="utf-8"))

    def test_v1_manifest_stops_before_creating_the_side(self):
        manifest = self.claude / "agents/.my-llm-brain-manifest"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("v1\n", encoding="utf-8")
        result = self.run_steps(BASE)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("STOP", result.stdout + result.stderr)
        self.assertFalse(self.side.exists())

    def test_agents_md_block_roundtrip_in_chosen_target(self):
        self.agents_target.parent.mkdir(parents=True)
        original = "# project\nkeep me\n"
        self.agents_target.write_text(original, encoding="utf-8")
        self.install("agents-md")
        self.install("agents-md")
        text = self.agents_target.read_text(encoding="utf-8")
        self.assertEqual(1, text.count(START))
        self.assertEqual(original, outside_markers(text))
        self.assertEqual(0, self.verify("agents-md").returncode)
        self.uninstall("agents-md")
        self.assertEqual(original, self.agents_target.read_text(encoding="utf-8"))


class OpencodeScenarios:
    def test_opencode_roundtrip_keeps_existing_config_byte_identical(self):
        self.opencode.mkdir(parents=True)
        config = '{ "theme": "mine" }\n'
        (self.opencode / "opencode.json").write_text(config, encoding="utf-8")
        self.install("opencode")
        self.install("opencode")
        self.assertEqual(config, (self.opencode / "opencode.json").read_text(encoding="utf-8"))
        for source in (ROOT / "dist/opencode/agents").iterdir():
            self.assertEqual(source.read_bytes(), (self.opencode / "agents" / source.name).read_bytes())
        self.assertEqual(0, self.verify("opencode").returncode)
        self.uninstall("opencode")
        self.assertEqual(config, (self.opencode / "opencode.json").read_text(encoding="utf-8"))
        self.assertEqual([], list((self.opencode / "agents").iterdir()))

    def test_opencode_created_config_is_valid_json_and_removed_on_uninstall(self):
        self.install("opencode")
        config = json.loads((self.opencode / "opencode.json").read_text(encoding="utf-8"))
        self.assertEqual("maestro", config["default_agent"])
        self.assertEqual(4, len(config["instructions"]))
        self.uninstall("opencode")
        self.assertFalse((self.opencode / "opencode.json").exists())
        self.assertFalse((self.opencode / "AGENTS.md").exists())


@POSIX_ONLY
class PosixInstall(OpencodeScenarios, InstallScenarios, unittest.TestCase):
    flavor = "sh"


@NEEDS_POWERSHELL
class PowerShellInstall(InstallScenarios, unittest.TestCase):
    flavor = "powershell"


if __name__ == "__main__":
    unittest.main()
