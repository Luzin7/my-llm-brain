#!/usr/bin/env python3
"""UserPromptSubmit hook: warn the assistant when the main context is large.

Threshold in tokens from CONTEXT_GUARD_TOKENS (default 100000). Fails open.
"""
import json
import os
import sys

sys.stderr.reconfigure(errors="backslashreplace")

DEFAULT_THRESHOLD = 100_000
CHUNK_BYTES = 256 * 1024
USAGE_FIELDS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
MESSAGE = (
    "Context size is about {size}. If the user's prompt starts a topic unrelated "
    "to the current request, recommend in one line that the user log open items "
    "and run /clear before continuing."
)


def threshold():
    try:
        return int(os.environ.get("CONTEXT_GUARD_TOKENS", DEFAULT_THRESHOLD))
    except ValueError:
        return DEFAULT_THRESHOLD


def reverse_lines(path):
    with open(path, "rb") as handle:
        position = handle.seek(0, os.SEEK_END)
        tail = b""
        while position > 0:
            step = min(CHUNK_BYTES, position)
            position -= step
            handle.seek(position)
            lines = (handle.read(step) + tail).split(b"\n")
            tail = lines[0]
            yield from reversed(lines[1:])
        yield tail


def context_tokens(line):
    try:
        entry = json.loads(line)
        if entry["type"] != "assistant" or entry.get("isSidechain"):
            return None
        usage = entry["message"]["usage"]
        return sum(usage.get(field) or 0 for field in USAGE_FIELDS)
    except (ValueError, KeyError, TypeError):
        return None


def last_context_tokens(path):
    for line in reverse_lines(path):
        tokens = context_tokens(line)
        if tokens is not None:
            return tokens
    return None


def warn(step, error, input_class):
    print(
        f"context-guard warning: step={step} error={type(error).__name__}: {error} "
        f"input={input_class}, allowing",
        file=sys.stderr,
    )


def read_transcript_path():
    try:
        return json.loads(sys.stdin.buffer.read().decode("utf-8"))["transcript_path"]
    except (ValueError, KeyError, TypeError) as error:
        warn("read-input", error, "stdin payload")
        return None


def main():
    path = read_transcript_path()
    if path is None:
        return
    try:
        tokens = last_context_tokens(path)
    except OSError as error:
        warn("read-transcript", error, "transcript file")
        return
    if tokens is None or tokens < threshold():
        return
    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": MESSAGE.format(size=f"{tokens // 1000}K"),
        }
    }
    print(json.dumps(output))


try:
    main()
except Exception as error:
    warn("unexpected", error, "hook run")
