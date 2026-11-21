#!/usr/bin/env python3
"""PreToolUse hook: the main session only orchestrates; subagents keep full tools.

Arguments: --side <dir> (main-session writes and Grep allowed under <dir>/memory,
<dir>/tasks and <dir>/specs) and --core <dir> (Grep allowed under it, never writes).
Without them every write and Grep is blocked. Config directory: CLAUDE_CONFIG_DIR,
default ~/.claude; create <config>/maestro-guard.off there to disable.
Internal errors allow the call and name step, error and input class on stderr.
"""
import json
import os
import re
import sys

sys.stderr.reconfigure(errors="backslashreplace")

BLOCK_MESSAGE = (
    "Main session only orchestrates: dispatch this to a worker subagent "
    "(scout, researcher, implementer, test engineer, reviewer)."
)
BLOCKED_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "Grep"}
MEMORY_WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}
READONLY_GIT = re.compile(r"^\s*git\s+(-C\s+[\w./~+@:-]+\s+)?(status|diff|log|show)(\s|$)")
SHELL_METACHARS = set(";&|`$<>()\n\r")
ONE_CALL_PROGRAMS = {"ls", "wc", "head", "cat", "jq"}
FORBIDDEN_GIT_TOKENS = ("--output", "--ext-diff", "difftool")
SIDE_SUBDIRECTORIES = ("memory", "tasks", "specs")


def config_dir():
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    return os.path.expanduser(configured) if configured else os.path.expanduser("~/.claude")


def block():
    print(BLOCK_MESSAGE, file=sys.stderr)
    sys.exit(2)


def fail_open(step, error, input_class):
    print(
        f"maestro-guard warning: step={step} error={type(error).__name__}: {error} "
        f"input={input_class}, allowing",
        file=sys.stderr,
    )


def parse_options(argv):
    options = {"side": None, "core": None}
    index = 0
    while index < len(argv):
        name = argv[index].lstrip("-")
        known = argv[index].startswith("--") and name in options
        if known and index + 1 < len(argv):
            options[name] = argv[index + 1]
            index += 2
            continue
        fail_open("parse-args", ValueError(argv[index]), "hook argument")
        index += 1
    return options


def canonical(path):
    normalized = os.path.expanduser(path).replace("\\", os.sep)
    return os.path.normcase(os.path.realpath(normalized))


def write_roots(options):
    if not options["side"]:
        return []
    return [canonical(os.path.join(os.path.expanduser(options["side"]), name)) for name in SIDE_SUBDIRECTORIES]


def grep_roots(options):
    roots = write_roots(options)
    if options["core"]:
        roots.append(canonical(options["core"]))
    return roots


def is_under(path, roots, allow_root):
    if not isinstance(path, str) or not path:
        return False
    target = canonical(path)
    return any(
        (allow_root and target == root) or target.startswith(root + os.sep) for root in roots
    )


def is_readonly_git(command):
    if not isinstance(command, str) or not READONLY_GIT.match(command):
        return False
    if SHELL_METACHARS & set(command):
        return False
    return not any(token in command for token in FORBIDDEN_GIT_TOKENS)


def is_one_call_command(command):
    if not isinstance(command, str) or SHELL_METACHARS & set(command):
        return False
    words = command.split()
    return bool(words) and words[0] in ONE_CALL_PROGRAMS


def is_allowed_bash(command):
    return is_readonly_git(command) or is_one_call_command(command)


def is_allowed_main_call(tool, tool_input, options):
    if tool == "Bash":
        return is_allowed_bash(tool_input.get("command"))
    if tool in MEMORY_WRITE_TOOLS and is_under(tool_input.get("file_path"), write_roots(options), False):
        return True
    if tool == "Grep" and is_under(tool_input.get("path"), grep_roots(options), True):
        return True
    return tool not in BLOCKED_TOOLS and not tool.startswith("mcp__")


def read_event():
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        if not isinstance(event, dict):
            raise ValueError("payload is not an object")
    except ValueError as error:
        fail_open("read-input", error, "stdin payload")
        return None
    return event


def main(argv):
    if os.path.exists(os.path.join(config_dir(), "maestro-guard.off")):
        return
    event = read_event()
    if event is None or event.get("agent_id"):
        return
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    tool = event.get("tool_name") or ""
    try:
        allowed = is_allowed_main_call(tool, tool_input, parse_options(argv))
    except Exception as error:
        fail_open("decide", error, f"tool {tool}")
        return
    if not allowed:
        block()


main(sys.argv[1:])
