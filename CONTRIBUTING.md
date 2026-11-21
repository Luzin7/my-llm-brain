# Contributing

Changes to the template are welcome. The rules of the road: tests first, the leak gate clean, one reviewer pass before merge.

## Ground rules

- Rewrite, never paste. `core/` is neutral: no company, person, host, client, language, model-vendor or home-path names. Paths are `{{CORE}}` and `{{SIDE}}` tokens.
- Python 3.9+ and the standard library only. Node is for the opencode plugin tests only.
- Docs are English. `README.pt-BR.md` mirrors the README and must keep the same number of headings.
- Commits and pull requests carry no AI-attribution lines.

## Tests

Run everything before you push. Never point tests at your real home: the install tests run in a throwaway profile and check that the real one is untouched.

```bash
TZ=UTC python3 -m unittest discover -s bin -p 'test_*.py' -v
TZ=UTC python3 -m unittest discover -s adapters/claude-code/guards -p 'test_*.py' -v
python3 -m unittest tools/leak-gate/test_leak_gate.py -v
(cd adapters/opencode && node --test 'plugins/*.test.mjs' 'plugins/*/*.test.mjs')
tools/docs/check-links
python3 tools/test_build_dist.py
python3 tools/test_install_doc.py
python3 tools/build-dist --check
```

`tools/docs/check-links` checks that local links and anchors in the docs resolve. `tools/test_install_doc.py` executes the `install-test` blocks of `INSTALL.md` (POSIX everywhere, PowerShell where `pwsh` exists) against a temporary profile; if you change install behavior, change `INSTALL.md` and its blocks together. `dist/` is generated: run `python3 tools/build-dist` after touching `core/` or `adapters/` and commit the result.

New behavior gets a failing test first, seen failing for the right reason. A test is never loosened to pass.

## Review

Open a pull request with the diff, the commands you ran and their results. A reviewer checks the diff against these rules, re-runs the tests and confirms no assertion was weakened. Changes that touch install wiring (`INSTALL.md`, hooks, plugins) or CI also get an edge review: runs twice, stops halfway, stale state, timeouts, "nothing" versus "broken", and where it really runs. Merging is the maintainer's call.

## Leak gate

Nothing private may enter this repository, including its history. `tools/leak-gate/leak-gate` enforces it.

What it checks, in the working tree and (with `--history`) in every commit reachable from any ref, including author and committer identities:

1. gitleaks, with the rules in `.gitleaks.toml` (default rules plus redacted output).
2. `tools/leak-gate/patterns.txt`: home-directory paths, e-mail addresses outside the allowlist, private IPv4 addresses, `.internal` and `.local` hosts.
3. A private denylist of case-insensitive substring terms, read from the file named by `LEAK_DENYLIST`. The file lives outside the repository and is never committed. The gate prints `denylist #N` (the term's position in the file), never the term.

`--public-only` skips item 3 and prints `denylist: skipped (public-only mode)`. CI uses it unless the private denylist secret is enabled.

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

Enable the pre-push hook once per clone: `git config core.hooksPath .githooks`. It runs `leak-gate --history` and blocks the push on any non-zero exit. `git push --no-verify` bypasses it, so CI repeats the scan: the public patterns and gitleaks always, the private denylist scan only when the repository variable `LEAK_DENYLIST_REQUIRED` is `true`. Set it before the repository goes public.

### Commit identity

Commit with the GitHub noreply address, set repository-locally: `git config user.email <id>+<handle>@users.noreply.github.com`.

### Tests

`python3 -m unittest tools/leak-gate/test_leak_gate.py -v` (Python 3.9+, standard library only). Fake tokens and private terms are generated at runtime inside temporary repositories.
