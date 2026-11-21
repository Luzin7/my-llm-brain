# Install, update, verify, uninstall

This file serves two readers with one checklist. A person runs the commands by hand. An AI agent runs the same commands after the README prompt. The steps, the order and the stop rules are identical.

Commands come in POSIX shell (Linux, macOS, WSL) and PowerShell (Windows). Run one flavor, in order, in one terminal session, from the root of this clone. Blocks tagged `install-test` are executed by `tools/test_install_doc.py` against a throwaway profile on every CI leg. Steps that need a harness CLI are not tagged; they are checked on a real install (see `docs/harness/`).

## Rules for the agent

- Follow the steps in order. Run only commands written here.
- Step 3 is a plan: print every file you will create or edit and every backup, then stop until the user answers "yes". Harness permission prompts still apply to each write.
- Never overwrite an existing side, and never edit text outside the `my-llm-brain:start` and `my-llm-brain:end` markers.
- A line starting with `STOP` ends the run: report it, change nothing more.
- Merging into an existing JSON, JSONC or TOML file is the one judgment call. Back the file up first, add only the entries named here, keep everything else byte for byte.
- Done means the output of step 7, pasted. "No error seen" is not done.

## 1. Detect

Which harness you are in, the OS and shell, and what else is on PATH:

```sh
uname -sm
command -v git claude codex opencode || true
```

```powershell
[System.Environment]::OSVersion.VersionString
Get-Command git, claude, codex -ErrorAction SilentlyContinue | Select-Object Name, Source
```

Install only the harness you are in, plus others only if the user asked. opencode on Windows runs inside WSL: use the POSIX blocks there.

Set the variables. `CLONE` is the folder you are in (this clone). `SIDE` is your private folder (default `~/my-brain`); edit the line to use another path. Paths must not contain a double quote.

```sh install-test:vars
CLONE="$(pwd)"
SIDE="$HOME/my-brain"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
OPENCODE_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/opencode"
AGENTS_SKILLS_DIR="$HOME/.agents/skills"
STAMP="$(date +%Y%m%d%H%M%S)"
START='<!-- my-llm-brain:start -->'
END='<!-- my-llm-brain:end -->'
PY=none
FAILED=0
```

```powershell install-test:vars
$Clone = (Get-Location).Path
$Side = Join-Path $HOME 'my-brain'
$ClaudeDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$CodexDir = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$AgentsSkillsDir = Join-Path $HOME '.agents/skills'
$Stamp = Get-Date -Format 'yyyyMMddHHmmss'
$Start = '<!-- my-llm-brain:start -->'
$End = '<!-- my-llm-brain:end -->'
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$Py = 'none'
$script:Failed = $false
```

Define the helpers once per session. They are idempotent: a block already in place, or a copy equal to `dist/`, is left alone; any file they change is backed up first as `<file>.bak-<timestamp>`; every change is appended to the install record once.

```sh install-test:helpers
record() {
  [ -d "$SIDE" ] || return 0
  rec="$SIDE/.install-record.md"
  [ -f "$rec" ] || printf '# Install record\n\n- date: %s\n- clone: %s\n- python: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$CLONE" "$PY" > "$rec"
  grep -qxF -- "- $1" "$rec" || printf -- '- %s\n' "$1" >> "$rec"
}
bakname() {
  b="$1.bak-$STAMP"
  n=0
  while [ -e "$b" ]; do n=$((n+1)); b="$1.bak-$STAMP-$n"; done
  printf '%s' "$b"
}
backup() {
  b="$(bakname "$1")"
  cp -p "$1" "$b"
  record "backup: $b"
}
ref() {
  case "$1" in
    "$HOME") printf '~' ;;
    "$HOME"/*) printf '~%s' "${1#"$HOME"}" ;;
    *) printf '%s' "$1" ;;
  esac
}
esc() { printf '%s' "$1" | sed 's/ /\\ /g'; }
markers_ok() {
  s="$(grep -cxF -- "$START" "$1" || true)"
  e="$(grep -cxF -- "$END" "$1" || true)"
  [ "$s" = "$e" ] && [ "$s" -le 1 ] && return 0
  echo "STOP: unbalanced or repeated my-llm-brain markers in $1"
  return 1
}
put_block() {
  target="$1"; blockfile="$2"
  mkdir -p "$(dirname "$target")"
  new="$target.new-$$"
  if [ -f "$target" ]; then
    markers_ok "$target" || return 1
    BF="$blockfile" awk -v s="$START" -v e="$END" '
      function emit(  line) { while ((getline line < ENVIRON["BF"]) > 0) print line; close(ENVIRON["BF"]) }
      $0 == s { emit(); skipping = 1; placed = 1; next }
      skipping { if ($0 == e) skipping = 0; next }
      { print }
      END { if (!placed) emit() }
    ' "$target" > "$new"
    if cmp -s "$target" "$new"; then rm -f "$new"; return 0; fi
    backup "$target"
    record "edited: $target"
    cat "$new" > "$target"
    rm -f "$new"
    return 0
  fi
  cp "$blockfile" "$target"
  record "created: $target"
}
drop_block() {
  target="$1"
  [ -f "$target" ] || return 0
  markers_ok "$target" || return 1
  grep -qxF -- "$START" "$target" || return 0
  new="$target.new-$$"
  awk -v s="$START" -v e="$END" '
    $0 == s { skipping = 1; next }
    skipping { if ($0 == e) skipping = 0; next }
    { print }
  ' "$target" > "$new"
  backup "$target"
  if [ -s "$new" ]; then cat "$new" > "$target"; else rm -f "$target"; fi
  rm -f "$new"
  echo "block removed: $target"
}
owned() { head -n 2 "$1" | grep -qF -- "my-llm-brain generated: dist/$2"; }
put_copy() {
  src="$CLONE/dist/$1"; dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [ ! -e "$dst" ]; then cp "$src" "$dst"; record "created: $dst"; return 0; fi
  cmp -s "$src" "$dst" && return 0
  if owned "$dst" "$1"; then backup "$dst"; cp "$src" "$dst"; record "edited: $dst"; return 0; fi
  echo "SKIP: $dst exists and is not generated by my-llm-brain; not overwritten"
}
drop_copy() {
  src="$CLONE/dist/$1"; dst="$2"
  [ -f "$dst" ] || return 0
  owned "$dst" "$1" || return 0
  if [ -f "$src" ] && cmp -s "$src" "$dst"; then rm -f "$dst"; echo "removed: $dst"; return 0; fi
  b="$(bakname "$dst")"
  mv "$dst" "$b"
  record "backup: $b"
  echo "RENAMED: $dst -> $b (edited, or the clone no longer has the source)"
}
copy_tree() {
  files="$(cd "$CLONE/dist/$1" && find . -type f | sort)"
  printf '%s\n' "$files" | while IFS= read -r rel; do
    rel="${rel#./}"
    put_copy "$1/$rel" "$2/$rel"
  done
}
drop_tree() {
  [ -d "$2" ] || return 0
  files="$(cd "$2" && find . -type f | sort)"
  printf '%s\n' "$files" | while IFS= read -r rel; do
    rel="${rel#./}"
    drop_copy "$1/$rel" "$2/$rel"
  done
}
claude_settings() {
  printf '{\n  "autoMemoryDirectory": "%s/memory"\n}\n' "$(ref "$SIDE")"
}
opencode_config() {
  printf '{\n  "$schema": "https://opencode.ai/config.json",\n  "default_agent": "maestro",\n'
  printf '  "instructions": [\n    "%s/dist/opencode/BRAIN.md",\n    "%s/rules/side.md",\n    "%s/rules/preferences.md",\n    "%s/memory/MEMORY.md"\n  ],\n' "$CLONE" "$SIDE" "$SIDE" "$SIDE"
  printf '  "skills": {\n    "paths": ["%s/dist/opencode/skills"]\n  }\n}\n' "$CLONE"
}
paths_line() {
  rev="$(git -C "$CLONE" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  printf 'my-llm-brain paths: {{CORE}} = %s, {{SIDE}} = %s, {{PY}} = %s, rev = %s\n' "$CLONE" "$SIDE" "$PY" "$rev"
}
fail() { echo "FAIL: $*"; FAILED=1; }
finish() {
  [ "$FAILED" = 0 ] || { echo "verify FAILED"; return 1; }
  echo "verify ok"
}
check_tree() {
  files="$(cd "$CLONE/dist/$1" && find . -type f | sort)"
  for rel in $(printf '%s\n' "$files" | sed 's|^\./||'); do
    cmp -s "$CLONE/dist/$1/$rel" "$2/$rel" || fail "$2/$rel differs from dist/$1/$rel"
  done
}
check_rev() {
  want="$(git -C "$CLONE" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  have="$(sed -n 's/^my-llm-brain paths:.*rev = \(.*\)$/\1/p' "$1")"
  [ "$have" = "$want" ] || fail "paths line in $1 carries rev '$have' but the clone is at '$want': run the update step"
}
check_block() {
  [ "$(grep -cxF -- "$START" "$1" 2>/dev/null || true)" = 1 ] || fail "marked block in $1 is not present exactly once"
}
```

```powershell install-test:helpers
function Read-Text($Path) { [System.IO.File]::ReadAllText($Path, $Utf8) }
function Write-Text($Path, $Text) { [System.IO.File]::WriteAllText($Path, $Text, $Utf8) }
function Test-SameFile($A, $B) { (Get-FileHash -LiteralPath $A).Hash -eq (Get-FileHash -LiteralPath $B).Hash }
function Get-Rel($Root, $Full) { $Full.Substring($Root.Length).TrimStart('\', '/').Replace('\', '/') }
function Add-Record($Line) {
  if (-not (Test-Path -LiteralPath $Side -PathType Container)) { return }
  $rec = Join-Path $Side '.install-record.md'
  if (-not (Test-Path -LiteralPath $rec)) {
    $date = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    Write-Text $rec ("# Install record`n`n- date: $date`n- clone: $Clone`n- python: $Py`n")
  }
  $entry = "- $Line"
  if (@(Get-Content -LiteralPath $rec -Encoding UTF8) -notcontains $entry) { [System.IO.File]::AppendAllText($rec, "$entry`n", $Utf8) }
}
function Get-BackupPath($Path) {
  $b = "$Path.bak-$Stamp"
  $n = 0
  while (Test-Path -LiteralPath $b) { $n++; $b = "$Path.bak-$Stamp-$n" }
  $b
}
function Backup-File($Path) {
  $b = Get-BackupPath $Path
  Copy-Item -LiteralPath $Path -Destination $b
  Add-Record "backup: $b"
}
function Get-Ref($Path) {
  $full = $Path.Replace('\', '/')
  $h = $HOME.Replace('\', '/')
  if ($full -eq $h) { return '~' }
  if ($full.StartsWith($h + '/', [System.StringComparison]::OrdinalIgnoreCase)) { return '~' + $full.Substring($h.Length) }
  return $full
}
function Get-Escaped($Text) { $Text.Replace(' ', '\ ') }
function Test-Markers($Text) {
  $s = [regex]::Matches($Text, [regex]::Escape($Start)).Count
  $e = [regex]::Matches($Text, [regex]::Escape($End)).Count
  if ($s -ne $e -or $s -gt 1) { throw 'STOP: unbalanced or repeated my-llm-brain markers' }
  return $s
}
function Set-Block($Target, $Block) {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Target) | Out-Null
  $exists = Test-Path -LiteralPath $Target -PathType Leaf
  $old = if ($exists) { Read-Text $Target } else { '' }
  if ((Test-Markers $old) -eq 1) {
    $i = $old.IndexOf($Start)
    $j = $old.IndexOf($End) + $End.Length
    $new = $old.Substring(0, $i) + $Block + $old.Substring($j)
  } else {
    $gap = if ($old.Length -gt 0 -and -not $old.EndsWith("`n")) { "`n" } else { '' }
    $new = $old + $gap + $Block + "`n"
  }
  if ($exists -and $new -ceq $old) { return }
  if ($exists) { Backup-File $Target; Add-Record "edited: $Target" } else { Add-Record "created: $Target" }
  Write-Text $Target $new
}
function Remove-Block($Target) {
  if (-not (Test-Path -LiteralPath $Target -PathType Leaf)) { return }
  $old = Read-Text $Target
  if ((Test-Markers $old) -eq 0) { return }
  $i = $old.IndexOf($Start)
  $j = $old.IndexOf($End) + $End.Length
  if ($old.Substring($j).StartsWith("`r`n")) { $j += 2 } elseif ($old.Substring($j).StartsWith("`n")) { $j += 1 }
  $new = $old.Substring(0, $i) + $old.Substring($j)
  Backup-File $Target
  if ($new.Length -eq 0) { Remove-Item -LiteralPath $Target } else { Write-Text $Target $new }
  Write-Output "block removed: $Target"
}
function Test-Owned($Path, $Rel) {
  $needle = "my-llm-brain generated: dist/$Rel"
  @(@(Get-Content -LiteralPath $Path -TotalCount 2 -Encoding UTF8) | Where-Object { $_.Contains($needle) }).Count -gt 0
}
function Copy-Owned($Rel, $Dest) {
  $src = Join-Path $Clone "dist/$Rel"
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Dest) | Out-Null
  if (-not (Test-Path -LiteralPath $Dest)) { Copy-Item -LiteralPath $src -Destination $Dest; Add-Record "created: $Dest"; return }
  if (Test-SameFile $src $Dest) { return }
  if (Test-Owned $Dest $Rel) { Backup-File $Dest; Copy-Item -LiteralPath $src -Destination $Dest -Force; Add-Record "edited: $Dest"; return }
  Write-Output "SKIP: $Dest exists and is not generated by my-llm-brain; not overwritten"
}
function Remove-Owned($Rel, $Dest) {
  if (-not (Test-Path -LiteralPath $Dest -PathType Leaf)) { return }
  if (-not (Test-Owned $Dest $Rel)) { return }
  $src = Join-Path $Clone "dist/$Rel"
  if ((Test-Path -LiteralPath $src) -and (Test-SameFile $src $Dest)) { Remove-Item -LiteralPath $Dest; Write-Output "removed: $Dest"; return }
  $b = Get-BackupPath $Dest
  Move-Item -LiteralPath $Dest -Destination $b
  Add-Record "backup: $b"
  Write-Output "RENAMED: $Dest -> $b (edited, or the clone no longer has the source)"
}
function Copy-Tree($Sub, $DestDir) {
  $root = Join-Path $Clone "dist/$Sub"
  foreach ($f in @(Get-ChildItem -LiteralPath $root -Recurse -File | Sort-Object FullName)) {
    $rel = Get-Rel $root $f.FullName
    Copy-Owned "$Sub/$rel" (Join-Path $DestDir $rel)
  }
}
function Remove-Tree($Sub, $DestDir) {
  if (-not (Test-Path -LiteralPath $DestDir -PathType Container)) { return }
  foreach ($f in @(Get-ChildItem -LiteralPath $DestDir -Recurse -File | Sort-Object FullName)) {
    $rel = Get-Rel $DestDir $f.FullName
    Remove-Owned "$Sub/$rel" $f.FullName
  }
}
function Get-ClaudeSettings { "{`n  `"autoMemoryDirectory`": `"$(Get-Ref $Side)/memory`"`n}`n" }
function Get-Rev {
  $r = & git -C $Clone rev-parse --short HEAD 2>$null
  if ($LASTEXITCODE -eq 0 -and $r) { return "$r".Trim() }
  return 'unknown'
}
function Get-PathsLine { "my-llm-brain paths: {{CORE}} = $Clone, {{SIDE}} = $Side, {{PY}} = $Py, rev = $(Get-Rev)" }
function Add-Fail($Message) { Write-Output "FAIL: $Message"; $script:Failed = $true }
function Complete-Verify {
  if ($script:Failed) { throw 'verify FAILED' }
  Write-Output 'verify ok'
}
function Test-Tree($Sub, $DestDir) {
  $root = Join-Path $Clone "dist/$Sub"
  foreach ($f in @(Get-ChildItem -LiteralPath $root -Recurse -File)) {
    $rel = Get-Rel $root $f.FullName
    $dest = Join-Path $DestDir $rel
    if (-not (Test-Path -LiteralPath $dest) -or -not (Test-SameFile $f.FullName $dest)) { Add-Fail "$dest differs from dist/$Sub/$rel" }
  }
}
function Test-Rev($File) {
  $want = Get-Rev
  $line = @(Get-Content -LiteralPath $File -Encoding UTF8 | Where-Object { $_ -match '^my-llm-brain paths:.*rev = (.*)$' })
  $have = if ($line.Count -gt 0) { $Matches[1] } else { '' }
  if ($have -ne $want) { Add-Fail "paths line in $File carries rev '$have' but the clone is at '$want': run the update step" }
}
function Test-Block($File) {
  $n = 0
  if (Test-Path -LiteralPath $File -PathType Leaf) { $n = @(Get-Content -LiteralPath $File -Encoding UTF8 | Where-Object { $_ -eq $Start }).Count }
  if ($n -ne 1) { Add-Fail "marked block in $File is not present exactly once" }
}
```

Probe Python (step 2). `PY` is the first of `python3`, `py -3`, `python` that reports 3.9 or newer, else `none`. `none` turns off the optional guards (L3) and selects the manual fallbacks written in the rules; it never fails the install.

```sh install-test:python
for candidate in "python3" "py -3" "python"; do
  if $candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then PY="$candidate"; break; fi
done
echo "python: $PY"
```

```powershell install-test:python
foreach ($candidate in @('python3', 'py -3', 'python')) {
  $parts = $candidate.Split(' ')
  if (-not (Get-Command $parts[0] -ErrorAction SilentlyContinue)) { continue }
  $probe = @($parts | Select-Object -Skip 1) + @('-c', 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)')
  try { & $parts[0] @probe *> $null } catch { continue }
  if ($LASTEXITCODE -eq 0) { $Py = $candidate; break }
}
Write-Output "python: $Py"
```

Stop on a v1 install. v1 wrote `.my-llm-brain-manifest` files; v2 installs next to them badly. The v1 uninstall lives at tag `v1`:

```sh install-test:v1
v1_guard() {
  for m in "$CLAUDE_DIR/agents" "$CLAUDE_DIR/skills" "$OPENCODE_DIR/agent" "$OPENCODE_DIR/skill" "$OPENCODE_DIR/plugins" "$SIDE/.generated"; do
    for name in .my-llm-brain-manifest .brain-sync-manifest; do
      [ -e "$m/$name" ] || continue
      echo "STOP: v1 install detected ($m/$name). Uninstall it first: git checkout v1, follow the uninstall section of that version's README, then git checkout - and start this file again."
      return 1
    done
  done
}
v1_guard
```

```powershell install-test:v1
foreach ($m in @((Join-Path $ClaudeDir 'agents'), (Join-Path $ClaudeDir 'skills'), (Join-Path $Side '.generated'))) {
  foreach ($name in @('.my-llm-brain-manifest', '.brain-sync-manifest')) {
    if (Test-Path -LiteralPath (Join-Path $m $name)) {
      throw "STOP: v1 install detected ($m/$name). Uninstall it first: git checkout v1, follow the uninstall section of that version's README, then git checkout - and start this file again."
    }
  }
}
```

## 3. Plan

Print this list for the harness being installed, with the real paths, then wait for "yes".

| Step | Creates or edits | Backup |
|---|---|---|
| Side (all harnesses) | `$SIDE` copied from `templates/side/` only if absent; `$SIDE/.install-record.md` | none: an existing side is never touched |
| Claude Code | marked block in `$CLAUDE_DIR/CLAUDE.md`; `autoMemoryDirectory` in `$CLAUDE_DIR/settings.json` only if the key is absent; the marketplace and plugins, recorded by `claude plugin ...` itself | `CLAUDE.md.bak-<timestamp>`, `settings.json.bak-<timestamp>` |
| Codex | marked block in `$CODEX_DIR/AGENTS.md`; 12 `brain-*.toml` in `$CODEX_DIR/agents/`; `task-board` in `$AGENTS_SKILLS_DIR/` | `AGENTS.md.bak-<timestamp>`; a changed copy is backed up before it is replaced |
| opencode (POSIX or WSL) | 13 agent files in `$OPENCODE_DIR/agents/`; entries in `$OPENCODE_DIR/opencode.json`; an empty `$OPENCODE_DIR/AGENTS.md` only if absent | `opencode.json.bak-<timestamp>` |
| AGENTS.md-only | marked block in the file named by `AGENTS_TARGET` | `<file>.bak-<timestamp>` |

## 4. Side

Create the side from the template only if it is absent. An existing side is never overwritten.

```sh install-test:side
if [ -e "$SIDE" ]; then
  echo "side exists, left untouched: $SIDE"
else
  mkdir -p "$SIDE"
  cp -R "$CLONE/templates/side/." "$SIDE/"
  echo "side created: $SIDE"
fi
record "side: $SIDE"
```

```powershell install-test:side
if (Test-Path -LiteralPath $Side) {
  Write-Output "side exists, left untouched: $Side"
} else {
  New-Item -ItemType Directory -Force -Path $Side | Out-Null
  Copy-Item -Path (Join-Path $Clone 'templates/side/*') -Destination $Side -Recurse -Force
  Write-Output "side created: $Side"
}
Add-Record "side: $Side"
```

Then fill the placeholders in `rules/side.md` and `rules/preferences.md` of the side. Both are yours; nothing here overwrites them.

## 5. Harness steps

### Claude Code

The rules come in through one marked block of `@` imports; agents, skills and guards come from plugins read in place from this clone, so `git pull` is the update. `~/`-relative imports are used when the clone and side are under your home; spaces are escaped as `\ `.

```sh install-test:claude-install
tmp="$(mktemp)"
{
  printf '%s\n' "$START"
  paths_line
  printf '@%s/dist/claude-code/BRAIN.md\n' "$(esc "$(ref "$CLONE")")"
  printf '@%s/rules/side.md\n' "$(esc "$(ref "$SIDE")")"
  printf '@%s/rules/preferences.md\n' "$(esc "$(ref "$SIDE")")"
  printf '@%s/memory/MEMORY.md\n' "$(esc "$(ref "$SIDE")")"
  printf '%s\n' "$END"
} > "$tmp"
put_block "$CLAUDE_DIR/CLAUDE.md" "$tmp"
rm -f "$tmp"
settings="$CLAUDE_DIR/settings.json"
if [ -e "$settings" ]; then
  echo "MERGE: $settings exists. Add \"autoMemoryDirectory\": \"$(ref "$SIDE")/memory\" only if the key is absent (back the file up first), keep every other byte."
else
  mkdir -p "$CLAUDE_DIR"
  claude_settings > "$settings"
  record "created: $settings"
fi
record "harness: claude-code"
```

```powershell install-test:claude-install
$block = @(
  $Start
  (Get-PathsLine)
  "@$(Get-Escaped (Get-Ref $Clone))/dist/claude-code/BRAIN.md"
  "@$(Get-Escaped (Get-Ref $Side))/rules/side.md"
  "@$(Get-Escaped (Get-Ref $Side))/rules/preferences.md"
  "@$(Get-Escaped (Get-Ref $Side))/memory/MEMORY.md"
  $End
) -join "`n"
Set-Block (Join-Path $ClaudeDir 'CLAUDE.md') $block
$settings = Join-Path $ClaudeDir 'settings.json'
if (Test-Path -LiteralPath $settings) {
  Write-Output "MERGE: $settings exists. Add `"autoMemoryDirectory`": `"$(Get-Ref $Side)/memory`" only if the key is absent (back the file up first), keep every other byte."
} else {
  New-Item -ItemType Directory -Force -Path $ClaudeDir | Out-Null
  Write-Text $settings (Get-ClaudeSettings)
  Add-Record "created: $settings"
}
Add-Record 'harness: claude-code'
```

Then register the plugins with the CLI (not run by tests). Add `brain-guards` only if `PY` is not `none`; its `python` option takes one executable, so if `PY` is `py -3`, set the option to the absolute path printed by `py -3 -c "import sys; print(sys.executable)"`. If the side is not `~/my-brain`, set the `side` option of both plugins to it.

```sh
claude plugin marketplace add "$CLONE"
claude plugin install brain@my-llm-brain
claude plugin install brain-guards@my-llm-brain
```

If a managed policy blocks local marketplaces, report the policy error and stop.

Verify (files):

```sh install-test:claude-verify
f="$CLAUDE_DIR/CLAUDE.md"
check_block "$f"
for p in "$CLONE/dist/claude-code/BRAIN.md" "$SIDE/rules/side.md" "$SIDE/rules/preferences.md" "$SIDE/memory/MEMORY.md"; do
  [ -f "$p" ] || fail "missing $p"
done
finish
```

```powershell install-test:claude-verify
Test-Block (Join-Path $ClaudeDir 'CLAUDE.md')
foreach ($p in @((Join-Path $Clone 'dist/claude-code/BRAIN.md'), (Join-Path $Side 'rules/side.md'), (Join-Path $Side 'rules/preferences.md'), (Join-Path $Side 'memory/MEMORY.md'))) {
  if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { Add-Fail "missing $p" }
}
Complete-Verify
```

Verify (harness, run on the real binary): `claude plugin list` shows `brain` and `brain-guards`; `/memory` shows the 4 imports; dispatch `brain:reviewer`. Full checklist: `docs/harness/claude-code.md`.

### Codex

Codex has no import syntax and no agents in plugins, so it gets copies: a compact block (a paths line with the clone's revision, then `dist/codex/AGENTS.block.md`, then a memory line), the 12 TOML agents and the `task-board` skill. The skill is copied from `dist/opencode/skills` (literal tokens; Codex has no skills output of its own). Nothing here touches `config.toml`.

```sh install-test:codex-install
tmp="$(mktemp)"
{
  printf '%s\n' "$START"
  paths_line
  cat "$CLONE/dist/codex/AGENTS.block.md"
  printf 'Memory index: read %s/memory/MEMORY.md at session start.\n' "$SIDE"
  printf '%s\n' "$END"
} > "$tmp"
put_block "$CODEX_DIR/AGENTS.md" "$tmp"
rm -f "$tmp"
copy_tree codex/agents "$CODEX_DIR/agents"
copy_tree opencode/skills/task-board "$AGENTS_SKILLS_DIR/task-board"
record "harness: codex"
```

```powershell install-test:codex-install
$block = @(
  $Start
  (Get-PathsLine)
  (Read-Text (Join-Path $Clone 'dist/codex/AGENTS.block.md')).TrimEnd("`r", "`n")
  "Memory index: read $Side/memory/MEMORY.md at session start."
  $End
) -join "`n"
Set-Block (Join-Path $CodexDir 'AGENTS.md') $block
Copy-Tree 'codex/agents' (Join-Path $CodexDir 'agents')
Copy-Tree 'opencode/skills/task-board' (Join-Path $AgentsSkillsDir 'task-board')
Add-Record 'harness: codex'
```

Verify (files; the paths line must carry the clone's current `git rev-parse --short HEAD`, otherwise run the update step):

```sh install-test:codex-verify
check_block "$CODEX_DIR/AGENTS.md"
check_rev "$CODEX_DIR/AGENTS.md"
check_tree codex/agents "$CODEX_DIR/agents"
check_tree opencode/skills/task-board "$AGENTS_SKILLS_DIR/task-board"
finish
```

```powershell install-test:codex-verify
Test-Block (Join-Path $CodexDir 'AGENTS.md')
Test-Rev (Join-Path $CodexDir 'AGENTS.md')
Test-Tree 'codex/agents' (Join-Path $CodexDir 'agents')
Test-Tree 'opencode/skills/task-board' (Join-Path $AgentsSkillsDir 'task-board')
Complete-Verify
```

Verify (harness, run on the real binary): ask "what are the my-llm-brain paths"; `/agents` lists the `brain-*` roles; the skill is listed (if `task-board` is missing, move the copy to `$CODEX_DIR/skills/`); spawn the reviewer and confirm it does not see the parent conversation. Full checklist: `docs/harness/codex.md`.

### opencode (Linux, macOS, or WSL)

Instructions and skills are referenced in place by absolute path; the 13 agents are copied. An empty `AGENTS.md` marker keeps opencode from falling back to `~/.claude/CLAUDE.md`. `opencode.json` is created only if neither `opencode.json` nor `opencode.jsonc` exists; otherwise merging is yours (backup, then add only the entries printed here).

```sh install-test:opencode-install
copy_tree opencode/agents "$OPENCODE_DIR/agents"
mkdir -p "$OPENCODE_DIR"
if [ ! -e "$OPENCODE_DIR/AGENTS.md" ]; then : > "$OPENCODE_DIR/AGENTS.md"; record "created: $OPENCODE_DIR/AGENTS.md"; fi
if [ -e "$OPENCODE_DIR/opencode.json" ] || [ -e "$OPENCODE_DIR/opencode.jsonc" ]; then
  echo "MERGE: an opencode config exists. Back it up, then add only these entries, keeping every other byte:"
  opencode_config
else
  opencode_config > "$OPENCODE_DIR/opencode.json"
  record "created: $OPENCODE_DIR/opencode.json"
fi
record "harness: opencode"
```

Optional L3 plugins: add to the `plugin` array of the config the entries `"file://$CLONE/adapters/opencode/plugins/subagent-cap"` and `"file://$CLONE/adapters/opencode/plugins/context-guard"`.

```sh install-test:opencode-verify
check_tree opencode/agents "$OPENCODE_DIR/agents"
[ -f "$OPENCODE_DIR/opencode.json" ] || [ -f "$OPENCODE_DIR/opencode.jsonc" ] || fail "no opencode config in $OPENCODE_DIR"
finish
```

Verify (harness, run on the real binary): `opencode debug agents` lists maestro plus 12; `opencode debug config` shows the entries. Full checklist: `docs/harness/opencode.md`.

### AGENTS.md-only tools (Gemini CLI, Cursor, Copilot, others)

Set `AGENTS_TARGET` to the file your tool reads (usually the project's `AGENTS.md`), then add one marked block holding the paths line and `dist/agents-md/AGENTS.md`.

```sh
AGENTS_TARGET="$HOME/projects/app/AGENTS.md"
```

```powershell
$AgentsTarget = Join-Path $HOME 'projects/app/AGENTS.md'
```

```sh install-test:agents-md-install
: "${AGENTS_TARGET:?set AGENTS_TARGET to the AGENTS.md path first}"
tmp="$(mktemp)"
{
  printf '%s\n' "$START"
  paths_line
  cat "$CLONE/dist/agents-md/AGENTS.md"
  printf '%s\n' "$END"
} > "$tmp"
put_block "$AGENTS_TARGET" "$tmp"
rm -f "$tmp"
record "harness: agents-md"
```

```powershell install-test:agents-md-install
if (-not $AgentsTarget) { throw 'STOP: set $AgentsTarget to the AGENTS.md path first' }
$block = @(
  $Start
  (Get-PathsLine)
  (Read-Text (Join-Path $Clone 'dist/agents-md/AGENTS.md')).TrimEnd("`r", "`n")
  $End
) -join "`n"
Set-Block $AgentsTarget $block
Add-Record 'harness: agents-md'
```

```sh install-test:agents-md-verify
check_block "$AGENTS_TARGET"
check_rev "$AGENTS_TARGET"
finish
```

```powershell install-test:agents-md-verify
Test-Block $AgentsTarget
Test-Rev $AgentsTarget
Complete-Verify
```

## 6. Record

Every block above appends to `$SIDE/.install-record.md`: the date, the clone path, `PY`, the harness and every created or edited path with its backup. The record is an index of where to look; uninstall proves ownership item by item and never trusts it alone.

## 7. Verify

Run the verify blocks of the harness you installed, then the harness-side checks listed with it, and paste their output. Any `FAIL` line means the install is not done: fix it or report it.

## Update

Run `git pull` in the clone. Claude Code needs nothing more (next session, or `/reload-plugins`). Codex, opencode and AGENTS.md-only: rerun the install blocks of that harness (helpers and variables first), then its verify blocks. The run is idempotent: the marked block is replaced in place, an unchanged copy is left alone, a copy changed by an upstream update is replaced after a `.bak-<timestamp>` backup.

## Uninstall

Ownership is proven at removal time; the side is never deleted.

1. Harness-owned records first (not run by tests): `claude plugin uninstall brain@my-llm-brain`, `claude plugin uninstall brain-guards@my-llm-brain`, `claude plugin marketplace remove my-llm-brain`.
2. Marked blocks: only the text between the markers is removed; a file left empty is deleted.
3. Created config files: `settings.json` and `opencode.json` are removed only when they are byte-equal to what install wrote. If you merged into yours, remove by hand only the entries whose value contains the clone or side path (`autoMemoryDirectory` when it points at the side's `memory`).
4. Copied files: removed only when line 1 or 2 carries the generated marker for that exact `dist/` path and the file equals the clone's `dist/` file. A changed copy, or any copy when the clone is already gone, is renamed to `<file>.bak-<timestamp>` and reported.
5. Every edited config file is backed up first, as in install. Backups are listed, never deleted.

```sh install-test:claude-uninstall
drop_block "$CLAUDE_DIR/CLAUDE.md"
settings="$CLAUDE_DIR/settings.json"
if [ -f "$settings" ]; then
  tmp="$(mktemp)"
  claude_settings > "$tmp"
  if cmp -s "$tmp" "$settings"; then rm -f "$settings"; echo "removed: $settings"; else echo "KEPT: $settings differs from what install wrote; remove autoMemoryDirectory by hand if it points at $SIDE/memory"; fi
  rm -f "$tmp"
fi
```

```powershell install-test:claude-uninstall
Remove-Block (Join-Path $ClaudeDir 'CLAUDE.md')
$settings = Join-Path $ClaudeDir 'settings.json'
if (Test-Path -LiteralPath $settings) {
  if ((Read-Text $settings) -ceq (Get-ClaudeSettings)) { Remove-Item -LiteralPath $settings; Write-Output "removed: $settings" }
  else { Write-Output "KEPT: $settings differs from what install wrote; remove autoMemoryDirectory by hand if it points at $Side/memory" }
}
```

```sh install-test:codex-uninstall
drop_block "$CODEX_DIR/AGENTS.md"
drop_tree codex/agents "$CODEX_DIR/agents"
drop_tree opencode/skills/task-board "$AGENTS_SKILLS_DIR/task-board"
rmdir "$AGENTS_SKILLS_DIR/task-board" 2>/dev/null || true
```

```powershell install-test:codex-uninstall
Remove-Block (Join-Path $CodexDir 'AGENTS.md')
Remove-Tree 'codex/agents' (Join-Path $CodexDir 'agents')
Remove-Tree 'opencode/skills/task-board' (Join-Path $AgentsSkillsDir 'task-board')
$skillDir = Join-Path $AgentsSkillsDir 'task-board'
if ((Test-Path -LiteralPath $skillDir) -and @(Get-ChildItem -LiteralPath $skillDir -Force).Count -eq 0) { Remove-Item -LiteralPath $skillDir }
```

```sh install-test:opencode-uninstall
drop_tree opencode/agents "$OPENCODE_DIR/agents"
[ -f "$OPENCODE_DIR/AGENTS.md" ] && [ ! -s "$OPENCODE_DIR/AGENTS.md" ] && rm -f "$OPENCODE_DIR/AGENTS.md" && echo "removed: $OPENCODE_DIR/AGENTS.md"
if [ -f "$OPENCODE_DIR/opencode.json" ]; then
  tmp="$(mktemp)"
  opencode_config > "$tmp"
  if cmp -s "$tmp" "$OPENCODE_DIR/opencode.json"; then rm -f "$OPENCODE_DIR/opencode.json"; echo "removed: $OPENCODE_DIR/opencode.json"; else echo "KEPT: $OPENCODE_DIR/opencode.json differs from what install wrote; back it up and remove only the entries containing $CLONE or $SIDE (default_agent only if it is maestro)"; fi
  rm -f "$tmp"
fi
true
```

```sh install-test:agents-md-uninstall
: "${AGENTS_TARGET:?set AGENTS_TARGET to the AGENTS.md path first}"
drop_block "$AGENTS_TARGET"
```

```powershell install-test:agents-md-uninstall
if (-not $AgentsTarget) { throw 'STOP: set $AgentsTarget to the AGENTS.md path first' }
Remove-Block $AgentsTarget
```
