"""Render core agents, skills and rules into one tool's config dirs.

Usage: rendercore.py <side-config.json> [--dry-run | --check] [--config-dir PATH]

The core is the repository this module lives in (bin/lib/../..). The side is the
directory holding the side config. Text is rendered with {{CORE}}, {{SIDE}},
{{PY}} and, when --config-dir is given, {{CONFIG_DIR}}; any other {{...}} aborts the
run before anything is written.

--check only scans the core (secrets, then the side's denylist).

Every target is validated before anything is written. A target that exists but
is not listed in the directory's .my-llm-brain-manifest is never overwritten, and
a directory whose manifest belongs to another core, or is a legacy
.brain-sync-manifest, is refused.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "bin" / "lib"))

import frontmatter  # noqa: E402
import tokens  # noqa: E402

CORE = ROOT / "core"
MANIFEST = ".my-llm-brain-manifest"
LEGACY_MANIFEST = ".brain-sync-manifest"
MANIFEST_HEADER = f"core: {ROOT}"
VALID_TIERS = ("judge", "worker", "mechanical")
COMMENT_KEY = "_comment"
FILE_MODE = 0o644


class BrainSyncError(SystemExit):
    def __init__(self, detail):
        super().__init__(f"{type(self).__name__}: {detail}")


class UsageError(BrainSyncError):
    pass


class InvalidTierError(BrainSyncError):
    pass


class InvalidRulesError(BrainSyncError):
    pass


class InvalidConfigError(BrainSyncError):
    pass


class InvalidFrontmatterError(BrainSyncError):
    pass


class UnknownTokenError(BrainSyncError):
    pass


class MissingSourceError(BrainSyncError):
    pass


class SourceOutsideCoreError(BrainSyncError):
    pass


class ForeignManifestError(BrainSyncError):
    pass


class HandWrittenTargetError(BrainSyncError):
    pass


class DirectoryCollisionError(BrainSyncError):
    pass


class UnsafeManifestEntryError(BrainSyncError):
    pass


class SecretFoundError(BrainSyncError):
    pass


class DenylistUnavailableError(BrainSyncError):
    pass


class DenylistedTermError(BrainSyncError):
    pass


def expand(path):
    return Path(path).expanduser()


def strip_comments(value):
    if isinstance(value, dict):
        return {key: strip_comments(item) for key, item in value.items() if key != COMMENT_KEY}
    if isinstance(value, list):
        return [strip_comments(item) for item in value]
    return value


def load_config(path):
    try:
        return strip_comments(json.loads(expand(path).read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        raise InvalidConfigError(f"{path}: {type(error).__name__}")


class Renderer:
    def __init__(self, side, config_dir):
        self.values = {"CORE": ROOT, "SIDE": side, "PY": "python3"}
        if config_dir:
            self.values["CONFIG_DIR"] = config_dir

    def text(self, text, source):
        try:
            return tokens.render_tokens(text, self.values, source)
        except tokens.UnknownTokenError as error:
            raise UnknownTokenError(error)


def core_path(relative):
    path = (CORE / relative).resolve()
    if CORE.resolve() not in path.parents:
        raise SourceOutsideCoreError(str(relative))
    if not path.is_file():
        raise MissingSourceError(f"core/{relative}")
    return path


def core_text(relative):
    return core_path(relative).read_text(encoding="utf-8")


def read_rules(names):
    return "\n\n".join(core_text(name).strip() for name in names)


def with_rules(body, names):
    if not names:
        return body
    return f"{body.rstrip()}\n\n{read_rules(names)}\n"


def tier_settings(config, name, tier):
    if tier is None:
        return {}
    if tier not in VALID_TIERS:
        raise InvalidTierError(f"agent {name}: tier {tier!r} not in {list(VALID_TIERS)}")
    tiers = config.get("tiers")
    if tiers is None:
        return {}
    if tier not in tiers:
        raise InvalidTierError(f"agent {name}: tier {tier!r} missing from config tiers")
    return tiers[tier]


def rules_list(value, source):
    if value is None:
        return []
    if not isinstance(value, list):
        raise InvalidRulesError(f"{source}: rules must be a list, got {type(value).__name__}")
    return value


def merge_rules(*groups):
    return list(dict.fromkeys(rule for group in groups for rule in group))


def parse_agent(source):
    try:
        header, body = frontmatter.parse(source.read_text(encoding="utf-8"))
    except frontmatter.FrontmatterError as error:
        raise InvalidFrontmatterError(f"{source.name}: {type(error).__name__}: {error}")
    for key in ("name", "description"):
        if not header.get(key):
            raise InvalidFrontmatterError(f"{source.name}: missing {key}")
    return header, body


def emit_document(header, body, source):
    try:
        return frontmatter.render(header, body)
    except frontmatter.FrontmatterError as error:
        raise InvalidConfigError(f"{source}: {type(error).__name__}: {error}")


def agent_documents(config):
    include_name = config.get("include_name", True)
    defaults = config.get("defaults", {})
    overrides = config.get("agents", {})
    skip = set(config.get("skip", []))
    documents = {}
    extra_bodies = {core_path(extra["body_from"]) for extra in config.get("extra_agents", {}).values()}
    for source in sorted((CORE / "agents").glob("*.md")):
        if source.resolve() in extra_bodies:
            continue
        header, body = parse_agent(source)
        name = header["name"]
        if name in skip:
            continue
        tier = tier_settings(config, name, header.get("tier"))
        settings = {**defaults, **tier, **overrides.get(name, {})}
        rules = merge_rules(
            rules_list(header.get("rules"), f"agent {name} frontmatter"),
            rules_list(settings.pop("rules", None), f"agent {name} config"),
        )
        base = {"name": name} if include_name else {}
        documents[name] = ({**base, "description": header["description"], **settings}, with_rules(body, rules))
    for name, extra in config.get("extra_agents", {}).items():
        settings = dict(extra["frontmatter"])
        rules = rules_list(settings.pop("rules", None), f"extra agent {name}")
        base = {"name": name} if include_name else {}
        documents[name] = ({**base, **settings}, with_rules(core_text(extra["body_from"]), rules))
    return documents


def agent_files(config):
    return {f"{name}.md": emit_document(header, body, name) for name, (header, body) in agent_documents(config).items()}


def collect_skills(skills, files):
    if not skills.is_dir():
        return
    for skill in sorted(path for path in skills.iterdir() if path.is_dir()):
        for path in sorted(skill.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                files[str(path.relative_to(skills))] = path.read_bytes()


def skill_files(config=None, source=None):
    files = {}
    collect_skills(CORE / "skills", files)
    for raw in (config or {}).get("extra_skill_dirs", []):
        collect_skills(source / expand(raw), files)
    return files


def render_skill(renderer, relative, data):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    return renderer.text(text, f"skill {relative}").encode()


def rules_file(config, side, source=None):
    source = source or side
    rules = config.get("rules_file")
    if not rules:
        return None
    parts = [read_rules(rules.get("shared", []))]
    local = rules.get("local") or []
    for raw in [local] if isinstance(local, str) else local:
        path = source / expand(raw)
        if not path.is_file():
            raise MissingSourceError(str(path))
        parts.append(path.read_text(encoding="utf-8").strip())
    return side / expand(rules["target"]), "\n\n".join(parts) + "\n"


def escapes_directory(entry):
    try:
        return any(
            flavor(entry).drive or flavor(entry).root or ".." in flavor(entry).parts
            for flavor in (PurePosixPath, PureWindowsPath)
        )
    except (ValueError, OSError):
        return True


def owned_entries(directory):
    if (directory / LEGACY_MANIFEST).exists():
        raise ForeignManifestError(f"{directory} has a legacy {LEGACY_MANIFEST}")
    path = directory / MANIFEST
    if not path.exists():
        return set(), False
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != MANIFEST_HEADER:
        raise ForeignManifestError(f"{path} does not belong to core {ROOT}")
    entries = {line for line in lines[1:] if line}
    for entry in sorted(entries):
        if escapes_directory(entry):
            raise UnsafeManifestEntryError(f"{path}: entry {entry!r} escapes the directory")
    return entries, True


def is_planned_copy(target, content):
    return target.is_file() and not target.is_symlink() and target.read_bytes() == content


def plan_directory(directory, files):
    owned, has_manifest = owned_entries(directory)
    actions = [("remove", directory / name, None) for name in sorted(owned - set(files))]
    for name, content in sorted(files.items()):
        target = directory / name
        if not os.path.lexists(target):
            actions.append(("write", target, content))
            continue
        if name not in owned and is_planned_copy(target, content):
            continue
        if name not in owned or target.is_dir():
            raise HandWrittenTargetError(f"refusing to overwrite hand-written {target}")
        if target.is_symlink() or target.read_bytes() != content:
            actions.append(("write", target, content))
    if not files and not has_manifest:
        return actions
    manifest = "".join(f"{line}\n" for line in [MANIFEST_HEADER, *sorted(files)]).encode()
    path = directory / MANIFEST
    if not path.exists() or path.read_bytes() != manifest:
        actions.append(("write", path, manifest))
    return actions


def prune_empty(directory, stop):
    parent = directory.parent
    while parent != stop and stop in parent.parents and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent


def apply_action(action, target, payload, stop):
    if action == "remove":
        target.unlink()
        prune_empty(target, stop)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
        os.chmod(temporary, FILE_MODE)
        os.replace(temporary, target)
    except BaseException:
        if os.path.lexists(temporary):
            os.unlink(temporary)
        raise


def leak_check(config, side):
    scanner = ROOT / "bin" / "secret-scan"
    if subprocess.run([sys.executable, str(scanner), str(CORE)]).returncode != 0:
        raise SecretFoundError("secret found in core")
    denylist = config.get("denylist")
    if not denylist:
        return
    terms = denylist_terms(side / expand(denylist))
    hits = []
    for path in sorted(CORE.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if any(term in line.lower() for term in terms):
                hits.append(f"{path.relative_to(ROOT)}:{number}")
    if hits:
        raise DenylistedTermError("denylisted term in core:\n" + "\n".join(hits))


def denylist_terms(path):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        raise DenylistUnavailableError("file is missing or unreadable")
    terms = [line.strip().lower() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    if not terms:
        raise DenylistUnavailableError("file has no terms")
    return terms


def parse_arguments(argv):
    if len(argv) < 2 or argv[1].startswith("--"):
        raise SystemExit(__doc__)
    options = {"dry_run": False, "check": False, "config_dir": None}
    rest = iter(argv[2:])
    for argument in rest:
        if argument == "--dry-run":
            options["dry_run"] = True
        elif argument == "--check":
            options["check"] = True
        elif argument == "--config-dir":
            options["config_dir"] = next(rest, None)
            if not options["config_dir"]:
                raise UsageError("--config-dir needs a path")
        else:
            raise UsageError(f"unknown argument {argument}")
    return argv[1], options


def build_groups(config, side, renderer, source=None):
    source = source or side
    groups = []
    if config.get("agents_dir"):
        agents = {name: renderer.text(text, f"agent {name}").encode() for name, text in agent_files(config).items()}
        groups.append((side / expand(config["agents_dir"]), agents))
    if config.get("skills_dir"):
        skills = {name: render_skill(renderer, name, data) for name, data in skill_files(config, source).items()}
        groups.append((side / expand(config["skills_dir"]), skills))
    rules = rules_file(config, side, source)
    if rules:
        target, content = rules
        groups.append((target.parent, {target.name: renderer.text(content, "rules file").encode()}))
    refuse_collisions(groups)
    return groups


def refuse_collisions(groups):
    seen = set()
    for directory, _ in groups:
        resolved = directory.resolve()
        if resolved in seen:
            raise DirectoryCollisionError(f"two targets resolve to {resolved}")
        seen.add(resolved)


def main(argv):
    config_path, options = parse_arguments(argv)
    config = load_config(config_path)
    side = expand(config_path).resolve().parent
    leak_check(config, side)
    if options["check"]:
        return
    groups = build_groups(config, side, Renderer(side, options["config_dir"]))
    actions = [(directory, *action) for directory, files in groups for action in plan_directory(directory, files)]
    for _, action, target, _ in actions:
        print(f"{action} {target}")
    if options["dry_run"]:
        return
    for directory, action, target, payload in actions:
        apply_action(action, target, payload, directory)


if __name__ == "__main__":
    main(sys.argv)
