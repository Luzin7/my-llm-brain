# Contributing

## Leak gate

Nothing private may enter this repository, including its history. `tools/leak-gate/leak-gate` enforces it.

What it checks, in the working tree and (with `--history`) in every commit reachable from any ref, including author and committer identities:

1. gitleaks, with the rules in `.gitleaks.toml` (default rules plus redacted output).
2. `tools/leak-gate/patterns.txt`: home-directory paths, e-mail addresses outside the allowlist, private IPv4 addresses, `.internal` and `.local` hosts.
3. A private denylist of whole-word, case-insensitive terms, read from the file named by `LEAK_DENYLIST`. The file lives outside the repository and is never committed. The gate prints `denylist #N` (the term's position in the file), never the term.

Exit codes: `0` clean, `1` findings, `2` the gate could not run (denylist unset, missing or empty; gitleaks unavailable or not the pinned version; not a git repository).

### Setup

1. Create the denylist, one term per line, outside the repository, and export `LEAK_DENYLIST=/path/to/denylist.txt`.
2. Install the pinned gitleaks and export `GITLEAKS_BIN`. Without it the gate runs the pinned container image through docker.

Pinned gitleaks:

| Item | Value |
|---|---|
| Version | 8.30.1 |
| Binary | `gitleaks_8.30.1_linux_x64.tar.gz` from the official release, sha256 `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb` |
| Container | `ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f` |

Verify the checksum before extracting. The gate refuses a binary whose `version` output is not the pinned one.

### Hooks

Enable the pre-push hook once per clone: `git config core.hooksPath .githooks`. It runs `leak-gate --history` and blocks the push on any non-zero exit. `git push --no-verify` bypasses it, so CI repeats the scan.

### Commit identity

Commit with the GitHub noreply address, set repository-locally: `git config user.email <id>+<handle>@users.noreply.github.com`.

### Tests

`python3 -m unittest tools/leak-gate/test_leak_gate.py -v` (Python 3.9+, standard library only). Fake tokens and private terms are generated at runtime inside temporary repositories.
