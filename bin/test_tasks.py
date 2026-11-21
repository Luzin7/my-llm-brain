import datetime
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "tasks"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


class TasksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "tasks"

    def new(self, title):
        result = run(str(self.dir), "new", title)
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(result.stdout.strip())

    def board(self):
        return (self.dir / "BOARD.md").read_text()

    def test_new_creates_file_and_board(self):
        path = self.new("First task")
        self.assertEqual(path.name, "T-0001-first-task.md")
        today = datetime.date.today().isoformat()
        self.assertEqual(
            path.read_text(),
            f"---\nid: T-0001\ntitle: First task\nstatus: todo\ncreated: {today}\nupdated: {today}\nproof: []\n---\n"
            f"## Goal\n\n## Done criteria\n\n## Log\n- {today} created\n",
        )
        self.assertIn("## todo (1)\n- [T-0001](T-0001-first-task.md) First task", self.board())

    def test_ids_increment(self):
        self.new("a")
        self.assertEqual(self.new("b").name, "T-0002-b.md")

    def test_title_with_colon_and_quotes_round_trips_into_board(self):
        self.new('Fix: the "thing" # now')
        self.assertIn('Fix: the "thing" # now', self.board())

    def test_board_groups_by_status_and_shows_proof(self):
        path = self.new("a")
        path.write_text(path.read_text().replace("status: todo", "status: doing").replace("proof: []", "proof:\n  - run-1\n  - run-2"))
        self.assertEqual(run(str(self.dir), "board").returncode, 0)
        board = self.board()
        self.assertIn("## doing (1)\n- [T-0001](T-0001-a.md) a", board)
        self.assertIn("proof: run-1, run-2", board)
        self.assertIn("## todo (0)", board)

    def test_unknown_status_fails_loudly(self):
        path = self.new("a")
        path.write_text(path.read_text().replace("status: todo", "status: bogus"))
        result = run(str(self.dir), "board")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bogus", result.stderr)

    def test_unsupported_frontmatter_names_the_file(self):
        path = self.new("a")
        path.write_text(path.read_text().replace("title: a", "title: |\n  x"))
        result = run(str(self.dir), "board")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("T-0001-a.md", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_usage_error(self):
        self.assertNotEqual(run(str(self.dir)).returncode, 0)


if __name__ == "__main__":
    unittest.main()
