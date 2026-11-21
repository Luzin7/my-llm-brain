import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent
EXAMPLES = BIN.parent / "examples" / "sides"
MANIFEST = ".my-llm-brain-manifest"


def join(*parts):
    return "".join(parts)


class Fixture:
    def __init__(self, tmp):
        self.home = Path(tmp)
        self.root = self.home / "core-root"
        (self.root / "bin" / "lib").mkdir(parents=True)
        for name in ("brain-sync", "secret-scan"):
            shutil.copy(BIN / name, self.root / "bin" / name)
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
        env = dict(os.environ, HOME=str(self.home))
        return subprocess.run([str(self.root / "bin" / "brain-sync"), str(path), *flags], capture_output=True, text=True, env=env)

    def generated(self, name):
        return (self.out / "agents" / f"{name}.md").read_text()

    def snapshot(self):
        return {str(p.relative_to(self.out)): (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(self.out.rglob("*")) if p.is_file()}

    def outputs(self):
        return sorted(str(p.relative_to(self.out)) for p in self.out.rglob("*"))


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
        for entry in ("../victim.txt", "/tmp/should-not-exist-victim", "sub/../../victim.txt"):
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


class RealCoreExampleSidesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)
        self.side = self.home / "side"
        (self.side / "rules").mkdir(parents=True)
        for name in ("side", "preferences"):
            (self.side / "rules" / f"{name}.md").write_text(f"LOCAL-{name}\n")

    def sync_real(self, config_text):
        config = self.side / "brain-sync.json"
        config.write_text(config_text)
        env = dict(os.environ, HOME=str(self.home))
        return subprocess.run(
            [str(BIN / "brain-sync"), str(config), "--config-dir", str(self.home / "cfg")], capture_output=True, text=True, env=env
        )

    def test_every_example_side_syncs_against_the_real_core(self):
        examples = sorted(EXAMPLES.glob("*.json"))
        self.assertTrue(examples)
        for example in examples:
            with self.subTest(example.name):
                result = self.sync_real(example.read_text())
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_opencode_side_renders_maestro_from_the_real_core(self):
        result = self.sync_real((EXAMPLES / "opencode.json").read_text())
        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = self.home / ".config" / "opencode" / "agent" / "maestro.md"
        self.assertTrue(rendered.is_file())
        self.assertNotIn("{{", rendered.read_text())

    def test_missing_body_from_in_a_config_copy_fails(self):
        text = (EXAMPLES / "opencode.json").read_text().replace("maestro/maestro.md", "maestro/absent.md")
        result = self.sync_real(text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MissingSourceError", result.stderr)


class ExampleSidesTest(FixtureCase):
    def seed_core(self):
        for name in ("posture", "orchestration"):
            self.fx.rule(f"{name}.md", f"RULE-{name}")
        for name in ("architect", "scout"):
            self.fx.agent(name, "tier: judge\n")
        (self.fx.side / "rules").mkdir()
        for name in ("side", "preferences"):
            (self.fx.side / "rules" / f"{name}.md").write_text(f"LOCAL-{name}\n")

    def test_every_example_side_config_syncs(self):
        examples = sorted(EXAMPLES.glob("*.json"))
        self.assertTrue(examples)
        for example in examples:
            with self.subTest(example.name):
                self.tearDown_fixture()
                self.seed_core()
                for extra in json.loads(example.read_text()).get("extra_agents", {}).values():
                    body = self.fx.core / extra["body_from"]
                    body.parent.mkdir(parents=True, exist_ok=True)
                    body.write_text("Maestro body.\n")
                (self.fx.side / "brain-sync.json").write_text(example.read_text())
                env = dict(os.environ, HOME=str(self.fx.home))
                result = subprocess.run([str(self.fx.root / "bin" / "brain-sync"), str(self.fx.side / "brain-sync.json")], capture_output=True, text=True, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                again = subprocess.run([str(self.fx.root / "bin" / "brain-sync"), str(self.fx.side / "brain-sync.json")], capture_output=True, text=True, env=env)
                self.assertEqual((again.returncode, again.stdout), (0, ""))

    def tearDown_fixture(self):
        shutil.rmtree(self.fx.home, ignore_errors=True)
        self.fx = Fixture(self.fx.home)

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


if __name__ == "__main__":
    unittest.main()
