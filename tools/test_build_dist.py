import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

try:
    import tomllib
except ImportError:
    tomllib = None

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from testlib.isolation import isolated_env  # noqa: E402

BIN = REPO / "bin"
BUILD_DIST = REPO / "tools" / "build-dist"
DIST = REPO / "dist"
MARKER_PREFIX = "my-llm-brain generated: dist/"
MANIFEST = ".my-llm-brain-manifest"
SKIP_ON_WINDOWS_MODE = unittest.skipIf(os.name == "nt", "Windows reports 0o666 for regular files")


def join(*parts):
    return "".join(parts)


class Fixture:
    def __init__(self, tmp):
        self.home = Path(os.path.realpath(tmp))
        self.root = self.home / "core-root"
        (self.root / "bin" / "lib").mkdir(parents=True)
        shutil.copy(BIN / "secret-scan", self.root / "bin" / "secret-scan")
        shutil.copytree(BIN / "lib", self.root / "bin" / "lib", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
        self.core = self.root / "core"
        for name in ("agents", "skills", "rules"):
            (self.core / name).mkdir(parents=True)
        self.side = self.home / "side"
        self.side.mkdir()
        self.out = self.home / "out"
        (self.out / "agents").mkdir(parents=True)
        (self.out / "skills").mkdir()
        self.config = {"agents_dir": str(self.out / "agents"), "skills_dir": str(self.out / "skills")}

    def rule(self, name, text):
        (self.core / "rules" / name).write_text(text + "\n")

    def agent(self, name, extra_frontmatter="", body="Body."):
        text = f"---\nname: {name}\ndescription: Does {name}.\n{extra_frontmatter}---\n{body}\n"
        (self.core / "agents" / f"{name}.md").write_text(text)

    def skill(self, name, relative, text):
        path = self.core / "skills" / name / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def write_config(self, **config):
        self.config.update(config)
        path = self.side / "brain-sync.json"
        path.write_text(json.dumps(self.config))
        return path

    def sync(self, *flags, **config):
        path = self.write_config(**config)
        env = isolated_env(self.home / "profile")
        return subprocess.run([sys.executable, str(self.root / "bin" / "lib" / "rendercore.py"), str(path), *flags], capture_output=True, text=True, env=env)

    def generated(self, name):
        return (self.out / "agents" / f"{name}.md").read_text()

    def snapshot(self):
        return {str(p.relative_to(self.out)): (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(self.out.rglob("*")) if p.is_file()}

    def outputs(self):
        return sorted(p.relative_to(self.out).as_posix() for p in self.out.rglob("*"))


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fx = Fixture(self._tmp.name)


class TiersTest(FixtureCase):
    def test_tier_settings_applied(self):
        self.fx.agent("alpha", "tier: judge\n")
        result = self.fx.sync(tiers={"judge": {"model": "model-a"}})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("model: model-a", self.fx.generated("alpha"))

    def test_tier_overrides_defaults(self):
        self.fx.agent("alpha", "tier: judge\n")
        self.fx.sync(defaults={"model": "model-c"}, tiers={"judge": {"model": "model-a"}})
        generated = self.fx.generated("alpha")
        self.assertIn("model: model-a", generated)
        self.assertNotIn("model-c", generated)

    def test_agent_override_beats_tier(self):
        self.fx.agent("alpha", "tier: judge\n")
        self.fx.sync(tiers={"judge": {"model": "model-a"}}, agents={"alpha": {"model": "model-b"}})
        generated = self.fx.generated("alpha")
        self.assertIn("model: model-b", generated)
        self.assertNotIn("model-a", generated)

    def test_tier_only_applies_to_its_agents(self):
        self.fx.agent("alpha", "tier: judge\n")
        self.fx.agent("beta", "tier: worker\n")
        self.fx.sync(tiers={"judge": {"model": "model-a"}, "worker": {"model": "model-c"}})
        self.assertIn("model: model-c", self.fx.generated("beta"))
        self.assertNotIn("model-a", self.fx.generated("beta"))

    def test_unknown_tier_is_an_error(self):
        self.fx.agent("alpha", "tier: bogus\n")
        result = self.fx.sync(tiers={"judge": {"model": "model-a"}})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("InvalidTierError", result.stderr)
        self.assertIn("bogus", result.stderr)

    def test_tier_outside_allowed_set_is_an_error_without_tiers_map(self):
        self.fx.agent("alpha", "tier: bogus\n")
        result = self.fx.sync()
        self.assertIn("InvalidTierError", result.stderr)

    def test_tier_not_emitted(self):
        self.fx.agent("alpha", "tier: judge\n")
        self.fx.sync(tiers={"judge": {"model": "model-a"}})
        self.assertNotIn("tier", self.fx.generated("alpha").split("---\n")[1])

    def test_no_tiers_config_exact_output(self):
        self.fx.agent("alpha")
        self.fx.sync(defaults={"effort": "high"}, agents={"alpha": {"model": "model-b"}})
        self.assertEqual(
            self.fx.generated("alpha"),
            "---\nname: alpha\ndescription: Does alpha.\neffort: high\nmodel: model-b\n---\nBody.\n",
        )

    def test_include_name_false_omits_name(self):
        self.fx.agent("alpha")
        self.fx.sync(include_name=False)
        self.assertEqual(self.fx.generated("alpha"), "---\ndescription: Does alpha.\n---\nBody.\n")

    def test_nested_settings_are_emitted(self):
        self.fx.agent("alpha")
        self.fx.sync(agents={"alpha": {"permission": {"edit": "deny"}}})
        self.assertIn("permission:\n  edit: deny\n", self.fx.generated("alpha"))

    def test_skip_omits_agent(self):
        self.fx.agent("alpha")
        self.fx.agent("beta")
        self.fx.sync(skip=["beta"])
        self.assertEqual(self.fx.outputs(), ["agents", "agents/.my-llm-brain-manifest", "agents/alpha.md", "skills"])


class RulesMergeTest(FixtureCase):
    def rules(self):
        for name in ("a", "b", "c", "d"):
            self.fx.rule(f"{name}.md", f"RULE-{name}")

    def test_frontmatter_rules_then_config_rules_deduplicated_in_order(self):
        self.rules()
        self.fx.agent("alpha", "rules: [rules/a.md, rules/b.md]\n")
        self.fx.sync(agents={"alpha": {"rules": ["rules/b.md", "rules/c.md"]}})
        generated = self.fx.generated("alpha")
        self.assertEqual(generated.count("RULE-b"), 1)
        positions = [generated.find(f"RULE-{n}") for n in "abc"]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn(-1, positions)

    def test_rules_key_not_emitted_in_frontmatter(self):
        self.rules()
        self.fx.agent("alpha", "rules: [rules/a.md]\n")
        self.fx.sync()
        self.assertNotIn("rules", self.fx.generated("alpha").split("---\n")[1])

    def test_defaults_then_tier_then_agent_last_layer_wins(self):
        self.rules()
        self.fx.agent("alpha", "tier: judge\n")
        defaults = {"rules": ["rules/a.md"]}
        tiers = {"judge": {"rules": ["rules/b.md"]}}
        self.fx.sync(defaults=defaults, tiers=tiers)
        self.assertEqual([n for n in "abcd" if f"RULE-{n}" in self.fx.generated("alpha")], ["b"])
        self.fx.sync(defaults=defaults, tiers=tiers, agents={"alpha": {"rules": ["rules/c.md"]}})
        self.assertEqual([n for n in "abcd" if f"RULE-{n}" in self.fx.generated("alpha")], ["c"])

    def test_defaults_rules_apply_when_no_tier_or_agent_rules(self):
        self.rules()
        self.fx.agent("alpha", "tier: judge\n")
        self.fx.sync(defaults={"rules": ["rules/a.md"]}, tiers={"judge": {"model": "model-a"}})
        self.assertIn("RULE-a", self.fx.generated("alpha"))

    def test_frontmatter_rules_unioned_with_resolved_config_rules(self):
        self.rules()
        self.fx.agent("alpha", "rules: [rules/a.md]\n")
        self.fx.sync(defaults={"rules": ["rules/b.md"]})
        generated = self.fx.generated("alpha")
        self.assertIn("RULE-a", generated)
        self.assertIn("RULE-b", generated)

    def test_rules_not_a_list_is_an_error(self):
        self.fx.agent("alpha", "rules: rules/a.md\n")
        self.assertIn("InvalidRulesError", self.fx.sync().stderr)
        self.fx.agent("alpha")
        self.assertIn("InvalidRulesError", self.fx.sync(agents={"alpha": {"rules": "rules/a.md"}}).stderr)

    def test_rule_outside_core_is_refused(self):
        self.fx.agent("alpha", "rules: [../outside.md]\n")
        (self.fx.root / "outside.md").write_text("x\n")
        result = self.fx.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SourceOutsideCoreError", result.stderr)
        self.assertEqual(self.fx.outputs(), ["agents", "skills"])

    def test_missing_rule_is_named_error_without_writes(self):
        self.fx.agent("alpha", "rules: [rules/absent.md]\n")
        result = self.fx.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MissingSourceError", result.stderr)
        self.assertEqual(self.fx.outputs(), ["agents", "skills"])


class TokensTest(FixtureCase):
    def test_leftover_token_fails_with_zero_writes(self):
        self.fx.agent("alpha", body="Fine.")
        self.fx.agent("beta", body="Uses {{BOGUS}} here.")
        result = self.fx.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("UnknownTokenError", result.stderr)
        self.assertIn("BOGUS", result.stderr)
        self.assertEqual(self.fx.outputs(), ["agents", "skills"])

    def test_leftover_token_in_skill_or_rules_file_fails_with_zero_writes(self):
        self.fx.agent("alpha")
        self.fx.skill("s", "SKILL.md", "ok {{CORE}}\n")
        self.fx.skill("t", "notes/extra.md", "bad {{NOPE}}\n")
        result = self.fx.sync()
        self.assertIn("UnknownTokenError", result.stderr)
        self.assertEqual(self.fx.outputs(), ["agents", "skills"])
        (self.fx.core / "skills" / "t" / "notes" / "extra.md").write_text("fine\n")
        (self.fx.side / "local.md").write_text("bad {{LOCAL}}\n")
        self.fx.rule("a.md", "A")
        result = self.fx.sync(rules_file={"shared": ["rules/a.md"], "local": ["local.md"], "target": str(self.fx.out / "R.md")})
        self.assertIn("UnknownTokenError", result.stderr)
        self.assertEqual(self.fx.outputs(), ["agents", "skills"])

    def test_known_tokens_are_rendered_everywhere(self):
        self.fx.rule("a.md", "rule {{CORE}}")
        self.fx.agent("alpha", "rules: [rules/a.md]\n", body="core {{CORE}} side {{SIDE}}")
        self.fx.skill("s", "SKILL.md", "skill {{CORE}} {{SIDE}}\n")
        result = self.fx.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        generated = self.fx.generated("alpha")
        self.assertIn(f"core {self.fx.root} side {self.fx.side}", generated)
        self.assertIn(f"rule {self.fx.root}", generated)
        self.assertNotIn("{{", generated)
        self.assertEqual((self.fx.out / "skills" / "s" / "SKILL.md").read_text(), f"skill {self.fx.root} {self.fx.side}\n")


class ConfigDirTokenTest(FixtureCase):
    def test_config_dir_token_rendered_when_flag_given(self):
        self.fx.agent("alpha", body="cfg {{CONFIG_DIR}}")
        self.fx.skill("s", "SKILL.md", "cfg {{CONFIG_DIR}}\n")
        result = self.fx.sync("--config-dir", "/some/config")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cfg /some/config", self.fx.generated("alpha"))
        self.assertEqual((self.fx.out / "skills" / "s" / "SKILL.md").read_text(), "cfg /some/config\n")

    def test_config_dir_token_without_flag_fails_with_zero_writes(self):
        self.fx.agent("alpha", body="cfg {{CONFIG_DIR}}")
        result = self.fx.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("UnknownTokenError", result.stderr)
        self.assertIn("CONFIG_DIR", result.stderr)
        self.assertEqual(self.fx.outputs(), ["agents", "skills"])

    def test_other_tokens_still_rejected_with_flag(self):
        self.fx.agent("alpha", body="x {{OTHER}}")
        result = self.fx.sync("--config-dir", "/c")
        self.assertIn("UnknownTokenError", result.stderr)


class ManifestTest(FixtureCase):
    def test_second_sync_has_no_actions_and_changes_nothing(self):
        self.fx.agent("alpha")
        self.fx.skill("s", "SKILL.md", "skill\n")
        self.fx.skill("s", "sub/x.md", "x\n")
        self.fx.rule("a.md", "A")
        extra = {"rules_file": {"shared": ["rules/a.md"], "target": str(self.fx.out / "rules" / "R.md")}}
        first = self.fx.sync(**extra)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertNotEqual(first.stdout, "")
        before = self.fx.snapshot()
        second = self.fx.sync(**extra)
        self.assertEqual((second.returncode, second.stdout), (0, ""))
        self.assertEqual(self.fx.snapshot(), before)

    def test_manifest_has_core_header_first(self):
        self.fx.agent("alpha")
        self.fx.sync()
        lines = (self.fx.out / "agents" / MANIFEST).read_text().splitlines()
        self.assertEqual(lines, [f"core: {self.fx.root}", "alpha.md"])

    def test_legacy_manifest_dir_is_refused_and_nothing_written(self):
        self.fx.agent("alpha")
        self.fx.skill("s", "SKILL.md", "skill\n")
        (self.fx.out / "skills" / ".brain-sync-manifest").write_text("s\n")
        result = self.fx.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ForeignManifestError", result.stderr)
        self.assertEqual(self.fx.outputs(), ["agents", "skills", "skills/.brain-sync-manifest"])

    def test_other_cores_manifest_is_refused(self):
        self.fx.agent("alpha")
        (self.fx.out / "agents" / MANIFEST).write_text("core: /somewhere/else\nalpha.md\n")
        result = self.fx.sync()
        self.assertIn("ForeignManifestError", result.stderr)
        self.assertEqual(self.fx.outputs(), ["agents", f"agents/{MANIFEST}", "skills"])

    def test_manifest_without_core_header_is_refused(self):
        self.fx.agent("alpha")
        (self.fx.out / "agents" / MANIFEST).write_text("alpha.md\n")
        self.assertIn("ForeignManifestError", self.fx.sync().stderr)

    def test_hand_written_file_is_never_overwritten(self):
        self.fx.agent("alpha")
        (self.fx.out / "agents" / "alpha.md").write_text("mine\n")
        result = self.fx.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HandWrittenTargetError", result.stderr)
        self.assertEqual(self.fx.generated("alpha"), "mine\n")

    def test_stale_generated_files_are_removed(self):
        self.fx.agent("alpha")
        self.fx.agent("beta")
        self.fx.skill("s", "sub/x.md", "x\n")
        self.fx.sync()
        (self.fx.core / "agents" / "beta.md").unlink()
        shutil.rmtree(self.fx.core / "skills" / "s")
        result = self.fx.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.fx.outputs(), ["agents", f"agents/{MANIFEST}", "agents/alpha.md", "skills", f"skills/{MANIFEST}"])

    def test_dry_run_prints_actions_and_writes_nothing(self):
        self.fx.agent("alpha")
        result = self.fx.sync("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("alpha.md", result.stdout)
        self.assertEqual(self.fx.outputs(), ["agents", "skills"])

    def test_skills_are_rendered_copies_not_links(self):
        self.fx.skill("s", "SKILL.md", "skill\n")
        self.fx.skill("s", "sub/x.md", "x\n")
        self.fx.sync()
        for relative in ("s/SKILL.md", "s/sub/x.md"):
            self.assertFalse((self.fx.out / "skills" / relative).is_symlink())
        self.assertFalse((self.fx.out / "skills" / "s").is_symlink())


class SafetyTest(FixtureCase):
    def test_foreign_file_with_old_temp_name_is_not_touched(self):
        self.fx.agent("alpha")
        foreign = self.fx.out / "agents" / ".alpha.md.tmp"
        foreign.write_text("foreign\n")
        result = self.fx.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(foreign.read_text(), "foreign\n")
        self.assertIn("Does alpha.", self.fx.generated("alpha"))

    @SKIP_ON_WINDOWS_MODE
    def test_generated_files_are_world_readable(self):
        self.fx.agent("alpha")
        self.fx.sync()
        self.assertEqual((self.fx.out / "agents" / "alpha.md").stat().st_mode & 0o777, 0o644)

    def test_no_temp_files_left_behind(self):
        self.fx.agent("alpha")
        self.fx.sync()
        self.assertEqual(sorted(p.name for p in (self.fx.out / "agents").iterdir()), [MANIFEST, "alpha.md"])

    def test_agents_and_skills_in_same_directory_are_refused(self):
        self.fx.agent("alpha")
        result = self.fx.sync(skills_dir=str(self.fx.out / "agents"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DirectoryCollisionError", result.stderr)
        self.assertEqual(self.fx.outputs(), ["agents", "skills"])

    def test_rules_target_directory_equal_to_agents_dir_is_refused(self):
        self.fx.agent("alpha")
        self.fx.rule("a.md", "A")
        result = self.fx.sync(rules_file={"shared": ["rules/a.md"], "target": str(self.fx.out / "agents" / "R.md")})
        self.assertIn("DirectoryCollisionError", result.stderr)
        self.assertEqual(self.fx.outputs(), ["agents", "skills"])

    def test_tampered_manifest_entries_are_refused_and_nothing_outside_is_touched(self):
        for entry in (
            "../victim.txt",
            "/tmp/should-not-exist-victim",
            "sub/../../victim.txt",
            "\\tmp\\x",
            "C:\\x",
            "C:x",
            "..\\x",
            "//server/share/x",
        ):
            with self.subTest(entry):
                victim = self.fx.out / "victim.txt"
                victim.write_text("keep\n")
                self.fx.agent("alpha")
                (self.fx.out / "agents" / MANIFEST).write_text(f"core: {self.fx.root}\n{entry}\n")
                result = self.fx.sync()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("UnsafeManifestEntryError", result.stderr)
                self.assertEqual(victim.read_text(), "keep\n")
                self.assertFalse((self.fx.out / "agents" / "alpha.md").exists())


class RulesFileTest(FixtureCase):
    def test_rules_file_merges_core_then_side_local(self):
        self.fx.rule("a.md", "RULE-a")
        self.fx.rule("b.md", "RULE-b")
        (self.fx.side / "rules").mkdir()
        (self.fx.side / "rules" / "side.md").write_text("SIDE-RULE\n")
        target = self.fx.out / "gen" / "CLAUDE.md"
        result = self.fx.sync(rules_file={"shared": ["rules/a.md", "rules/b.md"], "local": ["rules/side.md"], "target": str(target)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_text(), "RULE-a\n\nRULE-b\n\nSIDE-RULE\n")

    def test_missing_local_rules_file_is_named_error_without_writes(self):
        self.fx.agent("alpha")
        target = self.fx.out / "gen" / "CLAUDE.md"
        result = self.fx.sync(rules_file={"shared": [], "local": ["rules/absent.md"], "target": str(target)})
        self.assertIn("MissingSourceError", result.stderr)
        self.assertEqual(self.fx.outputs(), ["agents", "skills"])

    def test_extra_agent_body_from_core(self):
        (self.fx.core / "agents" / "extra.md").write_text("Extra body.\n")
        self.fx.rule("a.md", "RULE-a")
        result = self.fx.sync(extra_agents={"maestro": {"frontmatter": {"description": "D", "rules": ["rules/a.md"]}, "body_from": "agents/extra.md"}})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.fx.generated("maestro"), "---\nname: maestro\ndescription: D\n---\nExtra body.\n\nRULE-a\n")

    def test_missing_body_from_is_named_error_without_writes(self):
        self.fx.agent("alpha")
        result = self.fx.sync(extra_agents={"maestro": {"frontmatter": {"description": "D"}, "body_from": "agents/maestro.md"}})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MissingSourceError", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.fx.outputs(), ["agents", "skills"])


class LeakCheckTest(FixtureCase):
    def test_secret_in_core_blocks_with_zero_writes(self):
        self.fx.agent("alpha", body=join("pass", "word", "=", "hunter2", "hunter2"))
        result = self.fx.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.fx.outputs(), ["agents", "skills"])

    def test_denylisted_term_blocks_and_is_not_printed(self):
        term = "zqdenyterm"
        self.fx.agent("alpha", body=f"mentions {term} here")
        denylist = self.fx.home / "deny.txt"
        denylist.write_text(f"# c\n{term}\n")
        result = self.fx.sync(denylist=str(denylist))
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(term, result.stdout + result.stderr)
        self.assertIn("alpha.md", result.stderr)
        self.assertEqual(self.fx.outputs(), ["agents", "skills"])


class SideConfigTest(FixtureCase):
    def test_comment_keys_are_ignored_at_any_level(self):
        self.fx.agent("alpha")
        result = self.fx.sync(_comment="top", agents={"_comment": "x", "alpha": {"_comment": "y", "model": "model-a"}}, defaults={"_comment": "z"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.fx.generated("alpha"), "---\nname: alpha\ndescription: Does alpha.\nmodel: model-a\n---\nBody.\n")

    def test_null_dirs_skip_agents_and_skills(self):
        self.fx.agent("alpha")
        self.fx.rule("a.md", "RULE-a")
        target = self.fx.out / "AGENTS.md"
        result = self.fx.sync(agents_dir=None, skills_dir=None, rules_file={"shared": ["rules/a.md"], "target": str(target)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.fx.outputs(), [MANIFEST, "AGENTS.md", "agents", "skills"])


class DistTest(unittest.TestCase):
    def dist_files(self):
        return sorted(path for path in DIST.rglob("*") if path.is_file())

    def relative(self, path):
        return path.relative_to(DIST).as_posix()

    def test_every_dist_file_carries_its_marker_first(self):
        files = self.dist_files()
        self.assertTrue(files)
        for path in files:
            with self.subTest(self.relative(path)):
                lines = path.read_text(encoding="utf-8").splitlines()
                expected = MARKER_PREFIX + self.relative(path)
                head = lines[1] if lines[0] == "---" else lines[0]
                self.assertIn(expected, head)
                self.assertTrue(head.startswith(("# ", "<!-- ")))

    def test_no_token_survives_in_claude_code_plugin_files(self):
        files = [path for path in (DIST / "claude-code").rglob("*.md") if path.name != "BRAIN.md"]
        self.assertEqual(len(files), 13)
        for path in files:
            with self.subTest(self.relative(path)):
                self.assertNotIn("{{", path.read_text(encoding="utf-8"))

    def test_claude_code_plugin_files_use_plugin_variables(self):
        text = (DIST / "claude-code" / "skills" / "task-board" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn('${user_config.python} "${CLAUDE_PLUGIN_ROOT}/bin/tasks" "${user_config.side}/tasks"', text)

    @unittest.skipUnless(tomllib, "tomllib needs Python 3.11")
    def test_every_codex_agent_parses_as_toml(self):
        files = sorted((DIST / "codex" / "agents").glob("*.toml"))
        self.assertEqual(len(files), 12)
        for path in files:
            with self.subTest(path.name):
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(f"{data['name']}.toml", path.name)
                self.assertIn(data["model_reasoning_effort"], ("high", "medium", "low"))
                self.assertNotIn("model", data)
                self.assertTrue(data["developer_instructions"].strip())

    def test_codex_block_fits_eight_kibibytes(self):
        size = (DIST / "codex" / "AGENTS.block.md").stat().st_size
        self.assertLessEqual(size, 8192)

    def test_always_loaded_brain_files_stay_within_2500_words(self):
        for name in ("claude-code", "opencode"):
            with self.subTest(name):
                words = len((DIST / name / "BRAIN.md").read_text(encoding="utf-8").split())
                self.assertLessEqual(words, 2500)

    def test_opencode_workers_are_subagents_and_maestro_is_primary(self):
        agents = sorted((DIST / "opencode" / "agents").glob("*.md"))
        self.assertEqual(len(agents), 13)
        for path in agents:
            with self.subTest(path.name):
                expected = "mode: primary" if path.stem == "maestro" else "mode: subagent"
                self.assertIn(expected, path.read_text(encoding="utf-8").splitlines())

    def test_plugin_manifest_lists_every_claude_code_agent(self):
        manifest = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        listed = sorted(manifest["agents"])
        actual = sorted(f"./dist/claude-code/agents/{path.name}" for path in (DIST / "claude-code" / "agents").glob("*.md"))
        self.assertEqual(listed, actual)
        self.assertEqual(len(listed), 12)


class OutputNamesTest(unittest.TestCase):
    def test_skill_output_names_have_no_backslash(self):
        loader = importlib.machinery.SourceFileLoader("build_dist_under_test", str(BUILD_DIST))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)

        class Plain:
            def text(self, text, label):
                return text

        windows_keys = {"task-board\\SKILL.md": b"---\nname: x\n---\nbody\n"}
        with mock.patch.object(module.rendercore, "skill_files", return_value=windows_keys):
            names = module.skill_files("claude-code", Plain())
        self.assertEqual(["claude-code/skills/task-board/SKILL.md"], list(names))


class BuildDistCheckTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.copy = Path(os.path.realpath(self._tmp.name)) / "repo"
        shutil.copytree(
            REPO, self.copy, ignore=shutil.ignore_patterns(".git", "__pycache__", "node_modules")
        )

    def check(self):
        return subprocess.run(
            [sys.executable, str(self.copy / "tools" / "build-dist"), "--check"], capture_output=True, text=True, env=isolated_env(self.copy.parent / "profile")
        )

    def test_check_passes_on_the_committed_tree(self):
        result = subprocess.run([sys.executable, str(BUILD_DIST), "--check"], capture_output=True, text=True, env=isolated_env(self.copy.parent / "profile"))
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_check_fails_after_editing_a_core_file(self):
        path = self.copy / "core" / "rules" / "posture.md"
        path.write_text(path.read_text(encoding="utf-8") + "Extra line.\n", encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("StaleDistError", result.stderr)
        self.assertIn("outdated dist/claude-code/BRAIN.md", result.stderr)

    def test_check_fails_on_an_unexpected_dist_file(self):
        (self.copy / "dist" / "stray.md").write_text("x\n", encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("unexpected dist/stray.md", result.stderr)

    def test_generate_then_check_passes_and_is_idempotent(self):
        shutil.rmtree(self.copy / "dist")
        generate = subprocess.run([sys.executable, str(self.copy / "tools" / "build-dist")], capture_output=True, text=True, env=isolated_env(self.copy.parent / "profile"))
        self.assertEqual((generate.returncode, generate.stderr), (0, ""))
        self.assertEqual(self.check().returncode, 0)


if __name__ == "__main__":
    unittest.main()
