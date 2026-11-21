import os
import unittest
from pathlib import Path

PROFILE_VARIABLES = (
    "HOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "XDG_CONFIG_HOME",
    "XDG_STATE_HOME",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
)

WATCHED_FILES = (".claude/settings.json", ".claude/CLAUDE.md")
WATCHED_DIRECTORIES = (".codex", ".config/opencode")


def isolated_env(root, base=None, **extra):
    root = Path(root)
    env = dict(os.environ if base is None else base)
    for name in PROFILE_VARIABLES:
        path = root / name.lower()
        path.mkdir(parents=True, exist_ok=True)
        env[name] = str(path)
    env["TZ"] = "UTC"
    env.update(extra)
    return env


def stat_of(path):
    if not path.is_file():
        return None
    info = path.stat()
    return (info.st_size, info.st_mtime_ns)


def names_in(path):
    if not path.is_dir():
        return None
    return tuple(sorted(child.name for child in path.iterdir()))


def real_profile_snapshot():
    home = Path.home()
    files = {name: stat_of(home / name) for name in WATCHED_FILES}
    directories = {name: names_in(home / name) for name in WATCHED_DIRECTORIES}
    return files, directories


def is_inside(path, parent):
    return path == parent or parent in path.parents


def refuse_real_profile(path):
    path = Path(path).resolve()
    home = Path.home().resolve()
    protected = [home, *(home / name for name in (".claude", ".codex", ".config/opencode"))]
    if path == home or any(is_inside(path, guarded) for guarded in protected[1:]):
        raise SystemExit(f"refusing to run: {path} is the real profile")


def symlink_or_skip(link, target):
    try:
        Path(link).symlink_to(target)
    except (OSError, NotImplementedError) as error:
        raise unittest.SkipTest(f"symlink unavailable: {error}")
