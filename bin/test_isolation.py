import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from testlib.isolation import (  # noqa: E402
    PROFILE_VARIABLES,
    isolated_env,
    real_profile_snapshot,
    refuse_real_profile,
    symlink_or_skip,
)

WRITE_HOME = "from pathlib import Path; (Path.home() / 'written').write_text('x')"


class IsolationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_every_profile_variable_points_inside_the_root(self):
        env = isolated_env(self.root / "iso")
        for name in PROFILE_VARIABLES:
            with self.subTest(name=name):
                self.assertIn(self.root / "iso", Path(env[name]).parents)

    def test_none_of_the_profile_variables_keeps_the_inherited_value(self):
        inherited = {name: str(self.root / "real" / name) for name in PROFILE_VARIABLES}
        env = isolated_env(self.root / "iso", base=inherited)
        for name in PROFILE_VARIABLES:
            with self.subTest(name=name):
                self.assertNotEqual(env[name], inherited[name])

    def test_extra_overrides_win(self):
        env = isolated_env(self.root / "iso", CLAUDE_CONFIG_DIR=str(self.root / "cfg"))
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(self.root / "cfg"))

    def test_child_writes_land_in_the_root(self):
        env = isolated_env(self.root / "iso")
        subprocess.run([sys.executable, "-c", WRITE_HOME], env=env, check=True)
        self.assertTrue((Path(env["HOME"]) / "written").exists())

    def test_sentinel_in_the_real_profile_is_untouched(self):
        real = self.root / "real"
        real.mkdir()
        sentinel = real / "sentinel"
        sentinel.write_text("keep")
        inherited = {name: str(real) for name in PROFILE_VARIABLES}
        env = isolated_env(self.root / "iso", base={**os.environ, **inherited})
        subprocess.run([sys.executable, "-c", WRITE_HOME], env=env, check=True)
        self.assertEqual((sorted(p.name for p in real.iterdir()), sentinel.read_text()), (["sentinel"], "keep"))

    def test_real_harness_dirs_are_unchanged_by_an_isolated_run(self):
        before = real_profile_snapshot()
        subprocess.run([sys.executable, "-c", WRITE_HOME], env=isolated_env(self.root / "iso"), check=True)
        self.assertEqual(real_profile_snapshot(), before)

    def test_real_claude_dir_is_refused(self):
        with self.assertRaises(SystemExit):
            refuse_real_profile(Path.home() / ".claude" / "x")

    def test_temp_dir_is_accepted(self):
        refuse_real_profile(self.root)

    def test_symlink_helper_skips_when_os_symlink_raises(self):
        link = self.root / "dir-missing" / "link"
        with self.assertRaises(unittest.SkipTest):
            symlink_or_skip(link, self.root)

    def test_symlink_helper_creates_the_link(self):
        symlink_or_skip(self.root / "link", self.root)
        self.assertTrue((self.root / "link").is_symlink())


if __name__ == "__main__":
    unittest.main()
