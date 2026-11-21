#!/usr/bin/env python3
"""PreToolUse hook (matcher Agent|Task): cap subagent dispatches per main session.

Counts only calls from the main session (no agent_id). Cap from SUBAGENT_CAP
(default 25): call cap+1 exits 2. State: one counter file per session under
${CLAUDE_PLUGIN_DATA}/subagent-cap, or <config>/state/subagent-cap when that is unset
(config from CLAUDE_CONFIG_DIR, default ~/.claude), guarded by an exclusive file lock
(fcntl, msvcrt on Windows). Counters older than 7 days are pruned. Internal errors allow
the call and name step, error and input class on stderr.
"""
import errno
import hashlib
import json
import os
import sys
import time

if os.name == "nt":
    import msvcrt
else:
    import fcntl

sys.stderr.reconfigure(errors="backslashreplace")

DEFAULT_CAP = 25
PRUNE_AGE_SECONDS = 7 * 24 * 3600
LOCK_WAIT_SECONDS = 5.0
LOCK_POLL_SECONDS = 0.02
LOCK_NAME = ".lock"
SUBAGENT_TOOLS = ("Agent", "Task")
BUSY_ERRNOS = (errno.EACCES, errno.EAGAIN, errno.EDEADLK)


class LockTimeoutError(OSError):
    pass


class CorruptStateError(ValueError):
    pass


def warn(step, error, input_class):
    print(
        f"subagent-cap warning: step={step} error={type(error).__name__}: {error} "
        f"input={input_class}, allowing",
        file=sys.stderr,
    )


def resolve_cap():
    try:
        cap = int(os.environ.get("SUBAGENT_CAP", ""))
    except ValueError:
        return DEFAULT_CAP
    return cap if cap >= 0 else DEFAULT_CAP


def state_dir():
    plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if plugin_data:
        return os.path.join(os.path.expanduser(plugin_data), "subagent-cap")
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    config = os.path.expanduser(configured) if configured else os.path.expanduser("~/.claude")
    return os.path.join(config, "state", "subagent-cap")


def prune(directory):
    cutoff = time.time() - PRUNE_AGE_SECONDS
    for name in os.listdir(directory):
        path = os.path.join(directory, name)
        try:
            if name != LOCK_NAME and os.path.isfile(path) and os.stat(path).st_mtime < cutoff:
                os.remove(path)
        except OSError:
            continue


def try_lock(handle):
    try:
        if os.name == "nt":
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        if error.errno not in BUSY_ERRNOS:
            raise
        return False
    return True


def acquire(directory):
    handle = open(os.path.join(directory, LOCK_NAME), "a+", encoding="utf-8")
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    while not try_lock(handle):
        if time.monotonic() >= deadline:
            handle.close()
            raise LockTimeoutError(f"lock busy for over {LOCK_WAIT_SECONDS}s")
        time.sleep(LOCK_POLL_SECONDS)
    return handle


def read_count(path):
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read().strip()
    except FileNotFoundError:
        return 0
    except UnicodeDecodeError as error:
        raise CorruptStateError(f"counter file is not text ({error})")
    if not text:
        return 0
    if not text.isdigit():
        raise CorruptStateError(f"counter file holds {text[:20]!r}")
    return int(text)


def write_count(path, count):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(str(count))


def reserve(directory, session_id, cap):
    path = os.path.join(directory, hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:32])
    lock = acquire(directory)
    try:
        try:
            count = read_count(path)
        except CorruptStateError as error:
            warn("read-state", error, "counter file")
            write_count(path, 1)
            return None
        if count >= cap:
            return count
        write_count(path, count + 1)
        return None
    finally:
        lock.close()


def read_event():
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except ValueError as error:
        warn("read-input", error, "stdin payload")
        return None
    return event if isinstance(event, dict) else None


def main():
    event = read_event()
    if event is None or event.get("agent_id") or event.get("tool_name") not in SUBAGENT_TOOLS:
        return
    session_id = event.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        warn("read-input", ValueError("no session_id"), "stdin payload")
        return
    cap = resolve_cap()
    try:
        directory = state_dir()
        os.makedirs(directory, exist_ok=True)
        prune(directory)
        blocked_at = reserve(directory, session_id, cap)
    except OSError as error:
        warn("reserve-slot", error, "state directory")
        return
    if blocked_at is None:
        return
    print(
        f"Subagent fan-out cap reached: this session already dispatched {blocked_at} "
        f"subagents and the cap is {cap}. Do not split the work further. "
        "Stop and ask the user how to proceed.",
        file=sys.stderr,
    )
    sys.exit(2)


try:
    main()
except Exception as error:
    warn("unexpected", error, "hook run")
