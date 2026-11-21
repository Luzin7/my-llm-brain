import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

SCRIPT = str(Path(__file__).resolve().parent / "memory-lint")


def load():
    return SourceFileLoader("memory_lint", SCRIPT).load_module()


def note(name="feedback_a", description="d", type_="feedback"):
    return f"---\nname: {name}\ndescription: {description}\nmetadata:\n  type: {type_}\n---\nbody\n"


def build(files):
    root = tempfile.mkdtemp()
    for filename, text in files.items():
        Path(root, filename).write_text(text, encoding="utf-8")
    return root


GOOD_INDEX = "# Index\n- [[feedback_a]] — hook\n"
GOOD = {"MEMORY.md": "# M\n- [Index](index_x.md) — all\n", "index_x.md": GOOD_INDEX, "feedback_a.md": note()}


class MemoryLintTest(unittest.TestCase):
    def errors(self, files, limit=3000):
        return load().lint(build(files), limit)

    def test_valid_tree_has_no_errors(self):
        self.assertEqual(self.errors(GOOD), [])

    def test_user_note_is_valid(self):
        files = {**GOOD, "user_a.md": note(name="user_a", type_="user")}
        files["index_x.md"] += "- [[user_a]] — hook\n"
        self.assertEqual(self.errors(files), [])

    def test_name_must_equal_filename_stem(self):
        files = {**GOOD, "feedback_a.md": note(name="feedback-a")}
        self.assertTrue(any("filename stem" in e for e in self.errors(files)))

    def test_prefix_required(self):
        files = {**GOOD, "other_a.md": note(name="other_a")}
        files["index_x.md"] += "- [[other_a]] — hook\n"
        self.assertTrue(any("prefix" in e for e in self.errors(files)))

    def test_metadata_type_must_be_valid(self):
        files = {**GOOD, "feedback_a.md": note(type_="lesson")}
        self.assertTrue(any("metadata.type" in e for e in self.errors(files)))

    def test_note_in_no_index_is_reported(self):
        files = {**GOOD, "index_x.md": "# Index\n"}
        self.assertTrue(any("0 index files" in e for e in self.errors(files)))

    def test_note_in_two_indexes_is_reported(self):
        files = {**GOOD, "index_y.md": GOOD_INDEX}
        self.assertTrue(any("2 index files" in e for e in self.errors(files)))

    def test_long_index_line_is_reported(self):
        files = {**GOOD, "index_x.md": GOOD_INDEX + "- [[feedback_a]] — " + "x" * 150 + "\n"}
        self.assertTrue(any("over 150" in e for e in self.errors(files)))

    def test_date_or_quote_in_index_line_is_reported(self):
        files = {**GOOD, "index_x.md": "- [[feedback_a]] — seen 2026-10-27\n"}
        self.assertTrue(any("date or quote" in e for e in self.errors(files)))

    def test_dangling_link_is_reported(self):
        files = {**GOOD, "feedback_a.md": note() + "see [[feedback_missing]]\n"}
        self.assertTrue(any("dangling" in e for e in self.errors(files)))

    def test_quoted_description_with_colon_is_valid(self):
        files = {**GOOD, "feedback_a.md": note(description='"a: b"')}
        self.assertEqual(self.errors(files), [])

    def test_unsupported_frontmatter_is_reported_not_crashed(self):
        files = {**GOOD, "feedback_a.md": "---\nname: feedback_a\ndescription: |\n  x\n---\nbody\n"}
        self.assertTrue(any("frontmatter" in e for e in self.errors(files)))

    def test_memory_over_budget_is_reported(self):
        files = {**GOOD, "MEMORY.md": GOOD["MEMORY.md"] + "x" * 100}
        self.assertTrue(any("MEMORY.md" in e and "bytes" in e for e in self.errors(files, limit=50)))


if __name__ == "__main__":
    unittest.main()
