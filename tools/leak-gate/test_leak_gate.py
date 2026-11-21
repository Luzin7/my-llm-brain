import os
import random
import shutil
import string
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GATE = Path(__file__).resolve().parent / "leak-gate"
PINNED_VERSION = "8.30.1"
REAL_GITLEAKS_CANDIDATES = [os.environ.get("GITLEAKS_BIN"), str(Path.home() / ".local/share/my-llm-brain/gitleaks")]
NOREPLY = "1+tester@users.noreply.github.com"


def random_word(prefix):
    return prefix + "".join(random.choices(string.ascii_lowercase, k=12))


def random_alphanumeric(length):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def real_gitleaks():
    for candidate in REAL_GITLEAKS_CANDIDATES:
        if candidate and os.access(candidate, os.X_OK):
            return candidate
    return None


class GateCase(unittest.TestCase):
    def setUp(self):
        self.workdir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.workdir, ignore_errors=True)
        self.repo = self.workdir / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "tester")
        self.git("config", "user.email", NOREPLY)
        self.term = random_word("zq")
        self.denylist = self.workdir / "denylist.txt"
        self.denylist.write_text(self.term + "\n")
        self.stub = self.workdir / "gitleaks-stub"
        self.stub.write_text(f'#!/bin/sh\n[ "$1" = version ] && echo {PINNED_VERSION}\nexit 0\n')
        self.stub.chmod(0o755)

    def git(self, *args, env=None):
        merged = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, **(env or {})}
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True, env=merged)

    def commit(self, message="commit", env=None):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message, env=env)

    def write(self, name, text):
        (self.repo / name).write_text(text)

    def gate(self, *args, denylist="default", gitleaks="default", path=None):
        env = {key: value for key, value in os.environ.items() if key not in ("LEAK_DENYLIST", "GITLEAKS_BIN")}
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        if denylist == "default":
            denylist = str(self.denylist)
        if denylist:
            env["LEAK_DENYLIST"] = denylist
        if gitleaks == "default":
            gitleaks = str(self.stub)
        if gitleaks:
            env["GITLEAKS_BIN"] = gitleaks
        if path is not None:
            env["PATH"] = path
        return subprocess.run([sys.executable, str(GATE), *args], cwd=self.repo, capture_output=True, text=True, env=env)


class CleanTreeTest(GateCase):
    def test_clean_tree_and_history_exit_0(self):
        self.write("a.txt", "nothing private here\n")
        self.commit()
        self.assertEqual(self.gate("--history").returncode, 0)


class DenylistTest(GateCase):
    def test_term_in_tree_exits_1(self):
        self.write("a.txt", f"before {self.term.upper()} after\n")
        self.assertEqual(self.gate().returncode, 1)

    def test_term_only_in_deleted_history_exits_1(self):
        self.write("a.txt", f"leaked {self.term}\n")
        self.commit()
        (self.repo / "a.txt").unlink()
        self.commit("remove")
        self.assertEqual(self.gate().returncode, 0)
        self.assertEqual(self.gate("--history").returncode, 1)

    def test_term_in_author_email_exits_1(self):
        self.write("a.txt", "clean\n")
        self.commit(env={"GIT_AUTHOR_EMAIL": f"{self.term}@users.noreply.github.com"})
        self.assertEqual(self.gate("--history").returncode, 1)

    def test_term_inside_longer_word_is_not_a_match(self):
        self.write("a.txt", f"x{self.term}y\n")
        self.assertEqual(self.gate().returncode, 0)

    def test_output_never_shows_term(self):
        self.write(f"{self.term}.txt", f"{self.term}\n")
        self.commit(f"msg {self.term}")
        result = self.gate("--history")
        self.assertEqual(result.returncode, 1)
        self.assertIn("denylist #1", result.stdout)
        self.assertNotIn(self.term, result.stdout + result.stderr)

    def test_unset_denylist_exits_2(self):
        self.assertEqual(self.gate(denylist="").returncode, 2)

    def test_missing_denylist_exits_2(self):
        self.assertEqual(self.gate(denylist=str(self.workdir / "absent.txt")).returncode, 2)

    def test_empty_denylist_exits_2(self):
        self.denylist.write_text("\n")
        self.assertEqual(self.gate().returncode, 2)


class GitleaksTest(GateCase):
    def test_no_gitleaks_and_no_container_exits_2(self):
        bin_dir = self.workdir / "bin"
        bin_dir.mkdir()
        (bin_dir / "git").symlink_to(shutil.which("git"))
        self.assertEqual(self.gate(gitleaks="", path=str(bin_dir)).returncode, 2)

    def test_wrong_version_exits_2(self):
        self.stub.write_text("#!/bin/sh\necho 0.0.1\n")
        self.assertEqual(self.gate().returncode, 2)

    @unittest.skipUnless(real_gitleaks(), "pinned gitleaks binary not installed")
    def test_runtime_fake_github_token_exits_1(self):
        token = "ghp_" + random_alphanumeric(36)
        self.write("config.txt", f"token = {token}\n")
        self.commit()
        result = self.gate("--history", gitleaks=real_gitleaks())
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(token, result.stdout + result.stderr)

    @unittest.skipUnless(real_gitleaks(), "pinned gitleaks binary not installed")
    def test_real_gitleaks_clean_exits_0(self):
        self.write("a.txt", "nothing private here\n")
        self.commit()
        self.assertEqual(self.gate("--history", gitleaks=real_gitleaks()).returncode, 0)


class PatternsTest(GateCase):
    def assert_flagged(self, text):
        self.write("a.txt", text + "\n")
        self.assertEqual(self.gate().returncode, 1)

    def test_home_path_exits_1(self):
        self.assert_flagged("/ho" + "me/" + random_word("u") + "/project")

    def test_placeholder_home_path_exits_0(self):
        self.write("a.txt", "/ho" + "me/user/project\n")
        self.assertEqual(self.gate().returncode, 0)

    def test_regular_email_exits_1(self):
        self.assert_flagged(random_word("p") + "@" + random_word("d") + ".com")

    def test_allowlisted_emails_exit_0(self):
        self.write("a.txt", f"{NOREPLY} and someone@example.com\n")
        self.assertEqual(self.gate().returncode, 0)

    def test_private_ipv4_exits_1(self):
        self.assert_flagged("host 192." + "168.0.12")

    def test_public_ipv4_exits_0(self):
        self.write("a.txt", "host 8.8.8.8 and 127.0.0.1\n")
        self.assertEqual(self.gate().returncode, 0)

    def test_internal_host_exits_1(self):
        self.assert_flagged("curl " + random_word("h") + ".inter" + "nal/health")

    def test_local_settings_filename_exits_0(self):
        self.write("a.txt", "see settings.local.json\n")
        self.assertEqual(self.gate().returncode, 0)

    def test_pattern_in_history_exits_1(self):
        self.write("a.txt", "/ho" + "me/" + random_word("u") + "/x\n")
        self.commit()
        (self.repo / "a.txt").unlink()
        self.commit("remove")
        self.assertEqual(self.gate("--history").returncode, 1)


if __name__ == "__main__":
    unittest.main()
