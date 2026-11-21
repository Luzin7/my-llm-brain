import os
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

SCRIPT = str(Path(__file__).resolve().parent / "secret-scan")
scanner = SourceFileLoader("secret_scan", SCRIPT).load_module()

def join(*parts):
    return "".join(parts)


PASSWORD_VALUE = join("hunter2", "hunter2")
GITHUB_TOKEN = join("gh", "p_", "a" * 36)
LONG_SK_KEY = join("sk", "-v1-", "a1b2" * 8)
SLACK_TOKEN = join("xo", "xb-", "1234567890-", "abcdefghij")
AWS_KEY = join("AK", "IA", "ABCDEFGHIJKLMNOP")
PRIVATE_KEY_HEADER = join("-----", "BEGIN RSA PRIVATE", " KEY-----")
JWT = join("ey", "J", "a" * 12, ".ey", "J", "b" * 12, ".", "c" * 12)


FLAGGED_LINES = {
    "env db password": join("DB_", "PASSWORD", "=", PASSWORD_VALUE),
    "env postgres password": join("POSTGRES_", "PASSWORD", "=", PASSWORD_VALUE),
    "env openai key": join("OPENAI_", "API_KEY", "=", "abcdefgh1234"),
    "env secret key": join("SECRET_", "KEY", "=", "abcdefgh1234"),
    "export auth token": join("export AUTH_", "TOKEN", "=", "abcdefgh1234"),
    "json quoted": join('"pass', 'word": "', PASSWORD_VALUE, '"'),
    "yaml single quoted": join("'api", "_key': '", "abcdefgh1234", "'"),
    "value starting with x": join("PASS", "WORD", "=", "xyzzy1234abc"),
    "value starting with dot": join("pass", "word", ": ", ".Secr3t-value"),
    "localized lowercase": join("sen", "ha", ": ", "minhasenha123"),
    "localized uppercase": join("SEN", "HA", "=", "minhasenha123"),
    "url empty user": join("redis", "://", ":", "s3cretpw", "@host:6379"),
    "url with user": join("postgres", "://", "user", ":", "pass", "@host/db"),
    "default word plus symbol": join("PASS", "WORD", "=", "Admin@2024"),
    "capitalized default word": join("pass", "word", ": ", "Password@123"),
    "dash default expansion": join("${JWT_", "SECRET:-", "RealSecret99}"),
    "suffix after keyword": join("DB_", "PASSWORD", "_PROD=", PASSWORD_VALUE),
    "secret key base": join("SECRET_", "KEY_BASE=", "abcdefgh1234"),
    "aws secret access key": join("AWS_", "SECRET_ACCESS_KEY=", "abcdefgh1234"),
    "smtp pass": join("SMTP_", "PASS=", PASSWORD_VALUE),
    "db pass": join("DB_", "PASS=", PASSWORD_VALUE),
    "api token": join("API_", "TOKEN=", "abcdefgh1234"),
    "bot token": join("CHAT_BOT_", "TOKEN=", "abcdefgh1234"),
    "sk- key": LONG_SK_KEY,
    "github token": GITHUB_TOKEN,
    "private key": PRIVATE_KEY_HEADER,
    "jwt": JWT,
    "slack token": SLACK_TOKEN,
    "aws key": AWS_KEY,
}

CLEAN_LINES = {
    "vault placeholder": join("pass", "word", ": ", "<in vault>"),
    "env interpolation": join("API_", "KEY", "=", "${UPSTREAM_API_KEY}"),
    "xxx placeholder": join("SECRET_", "KEY", "=", "xxx"),
    "stars placeholder": join("pass", "word", ": ", "***"),
    "template placeholder": join("tok", "en", ": ", "{{ token }}"),
    "changeme": join("PASS", "WORD", "=", "changeme"),
    "example": join("pass", "word", ": ", "example-password"),
    "your password here": join("pass", "word", ": ", "your-password-here"),
    "process env": "process.env.DB_PASSWORD",
    "os environ": 'os.environ["API_KEY"]',
    "code reference": "const passwordField = form.password",
    "prose": "the password field must be hashed",
    "docker inspect": "POSTGRES_PASSWORD from docker inspect",
    "stdin flag": "docker login --password-stdin",
    "git ssh url": "git@example.com:x/y.git",
    "pr url": "https://example.com/x/y/pull/12",
    "public default postgres": join("POSTGRES_", "PASSWORD", ": ", "postgres", "  secret-scan:ignore"),
    "ignore marker": join("pass", "word", "=", PASSWORD_VALUE, "  secret-scan:ignore"),
}


class ScanLineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def hits_for(self, line):
        path = Path(self.tmp.name) / "note.md"
        path.write_text(line + "\n")
        return scanner.scan([path])

    def test_flagged(self):
        for name, line in FLAGGED_LINES.items():
            with self.subTest(name):
                self.assertTrue(self.hits_for(line))

    def test_clean(self):
        for name, line in CLEAN_LINES.items():
            with self.subTest(name):
                self.assertEqual(self.hits_for(line), [])


def run_cli(args, cwd):
    return subprocess.run([sys.executable, SCRIPT, *args], cwd=cwd, capture_output=True, text=True)


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = self.tmp.name
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")

    def test_staged_reads_staged_blob(self):
        note = Path(self.repo) / "note.md"
        note.write_text(join("pass", "word", "=", PASSWORD_VALUE) + "\n")
        git(self.repo, "add", "note.md")
        note.write_text("clean\n")
        result = run_cli(["--staged"], self.repo)
        self.assertEqual(result.returncode, 1)
        self.assertIn("note.md:1:", result.stderr)

    def test_staged_ignores_secret_only_in_working_tree(self):
        note = Path(self.repo) / "note.md"
        note.write_text("clean\n")
        git(self.repo, "add", "note.md")
        note.write_text(join("pass", "word", "=", PASSWORD_VALUE) + "\n")
        self.assertEqual(run_cli(["--staged"], self.repo).returncode, 0)

    def test_staged_rename_is_flagged(self):
        old = Path(self.repo) / "old.md"
        old.write_text(join("pass", "word", "=", PASSWORD_VALUE) + "\n" + "filler\n" * 20)
        git(self.repo, "add", "old.md")
        git(self.repo, "commit", "-q", "-m", "x", "--no-verify")
        git(self.repo, "mv", "old.md", "new.md")
        result = run_cli(["--staged"], self.repo)
        self.assertEqual(result.returncode, 1)
        self.assertIn("new.md:1:", result.stderr)

    def test_staged_from_subdirectory(self):
        sub = Path(self.repo) / "sub"
        sub.mkdir()
        (sub / "note.md").write_text(join("pass", "word", "=", PASSWORD_VALUE) + "\n")
        git(self.repo, "add", "sub/note.md")
        self.assertEqual(run_cli(["--staged"], str(sub)).returncode, 1)

    def test_missing_path_fails_with_message(self):
        missing = os.path.join(self.repo, "nope.md")
        result = run_cli([missing], self.repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("nope.md", result.stderr)
        self.assertIn("not found", result.stderr)

    def test_output_never_contains_value(self):
        note = Path(self.repo) / "note.md"
        note.write_text("\n".join(FLAGGED_LINES.values()) + "\n")
        result = run_cli([str(note)], self.repo)
        self.assertEqual(result.returncode, 1)
        for secret in (PASSWORD_VALUE, GITHUB_TOKEN, LONG_SK_KEY, SLACK_TOKEN, AWS_KEY, JWT, "minhasenha123", "s3cretpw"):
            self.assertNotIn(secret, result.stdout + result.stderr)

    def test_pycache_and_pyc_are_skipped_but_py_is_reported(self):
        line = join("pass", "word", "=", PASSWORD_VALUE) + "\n"
        cache = Path(self.repo) / "__pycache__"
        cache.mkdir()
        (cache / "mod.cpython-310.pyc").write_text(line)
        (Path(self.repo) / "stray.pyc").write_text(line)
        self.assertEqual(run_cli([self.repo], self.repo).returncode, 0)
        (Path(self.repo) / "mod.py").write_text(line)
        result = run_cli([self.repo], self.repo)
        self.assertEqual(result.returncode, 1)
        self.assertIn("mod.py:1:", result.stderr)
        self.assertNotIn("pyc", result.stderr)

    def test_clean_file_exits_zero(self):
        note = Path(self.repo) / "note.md"
        note.write_text("\n".join(CLEAN_LINES.values()) + "\n")
        self.assertEqual(run_cli([str(note)], self.repo).returncode, 0)


if __name__ == "__main__":
    unittest.main()
