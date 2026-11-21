import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

MODULE = Path(__file__).resolve().parent / "lib" / "frontmatter.py"


def load():
    return SourceFileLoader("frontmatter", str(MODULE)).load_module()


def doc(header, body="Body.\n"):
    return f"---\n{header}---\n{body}"


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.fm = load()

    def header(self, text):
        return self.fm.parse(doc(text))[0]

    def test_scalars(self):
        parsed = self.header("name: alpha\ncount: 3\nflag: true\nempty:\nquoted: \"a: b\"\nsingle: 'it''s'\n")
        self.assertEqual(
            parsed,
            {"name": "alpha", "count": 3, "flag": True, "empty": None, "quoted": "a: b", "single": "it's"},
        )

    def test_dates_stay_strings(self):
        self.assertEqual(self.header("created: 2026-11-21\n"), {"created": "2026-11-21"})

    def test_inline_list(self):
        self.assertEqual(self.header("rules: [a.md, \"b, c.md\"]\nnone: []\n"), {"rules": ["a.md", "b, c.md"], "none": []})

    def test_block_list(self):
        self.assertEqual(self.header("rules:\n  - a.md\n  - b.md\nafter: x\n"), {"rules": ["a.md", "b.md"], "after": "x"})

    def test_block_list_at_key_indent(self):
        self.assertEqual(self.header("rules:\n- a.md\n- b.md\n"), {"rules": ["a.md", "b.md"]})

    def test_nested_map(self):
        self.assertEqual(
            self.header("metadata:\n  type: feedback\n  deep:\n    k: v\nname: n\n"),
            {"metadata": {"type": "feedback", "deep": {"k": "v"}}, "name": "n"},
        )

    def test_body_is_returned_without_leading_blank_lines(self):
        self.assertEqual(self.fm.parse("---\na: b\n---\n\n\nText\n")[1], "Text\n")

    def test_comment_lines_are_skipped(self):
        self.assertEqual(self.header("# note\na: b\n"), {"a": "b"})

    def test_missing_frontmatter_is_named_error(self):
        with self.assertRaises(self.fm.MissingFrontmatterError):
            self.fm.parse("no header\n")

    def test_unterminated_frontmatter_is_named_error(self):
        with self.assertRaises(self.fm.MissingFrontmatterError):
            self.fm.parse("---\na: b\n")

    def test_unsupported_syntax_is_named_error(self):
        for header in ("a: |\n  text\n", "a: &anchor x\n", "a: {k: v}\n", "a: *ref\n", "a: [x, [y]]\n", "\ta: b\n", "just text\n"):
            with self.subTest(header):
                with self.assertRaises(self.fm.UnsupportedSyntaxError):
                    self.fm.parse(doc(header))

    def test_error_names_the_line(self):
        with self.assertRaises(self.fm.UnsupportedSyntaxError) as raised:
            self.fm.parse(doc("a: b\nc: |\n"))
        self.assertIn("line 3", str(raised.exception))


class EmitTest(unittest.TestCase):
    def setUp(self):
        self.fm = load()

    def test_plain_scalars_and_lists(self):
        self.assertEqual(
            self.fm.emit({"name": "alpha", "description": "Does alpha.", "rules": ["a", "b"], "none": []}),
            "name: alpha\ndescription: Does alpha.\nrules: [a, b]\nnone: []\n",
        )

    def test_nested_map(self):
        self.assertEqual(self.fm.emit({"permission": {"edit": "deny", "bash": {"git": "ask"}}}), "permission:\n  edit: deny\n  bash:\n    git: ask\n")

    def test_values_that_need_quotes_round_trip(self):
        values = ["a: b", "", "true", "12", "null", "- x", "{{CORE}}", "has # hash", " lead", "multi\nline", "it's", 'say "hi"']
        for value in values:
            with self.subTest(value):
                parsed = self.fm.parse(self.fm.render({"k": value}, "b\n"))[0]
                self.assertEqual(parsed, {"k": value})

    def test_types_round_trip(self):
        data = {"n": 3, "f": True, "z": None, "l": ["a b", "c, d"], "m": {"x": {"y": "z"}}}
        self.assertEqual(self.fm.parse(self.fm.render(data, "b\n"))[0], data)

    def test_list_of_maps_is_named_error(self):
        with self.assertRaises(self.fm.UnsupportedValueError):
            self.fm.emit({"k": [{"a": "b"}]})

    def test_unsupported_type_is_named_error(self):
        with self.assertRaises(self.fm.UnsupportedValueError):
            self.fm.emit({"k": 1.5})


class CheckCliTest(unittest.TestCase):
    def run_check(self, *texts):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for number, text in enumerate(texts):
                path = Path(tmp) / f"f{number}.md"
                path.write_text(text, encoding="utf-8")
                paths.append(str(path))
            return subprocess.run([sys.executable, str(MODULE), "--check", *paths], capture_output=True, text=True)

    def test_valid_files_exit_0(self):
        self.assertEqual(self.run_check(doc("a: b\n"), doc("c: [d]\n")).returncode, 0)

    def test_invalid_file_exits_1_and_names_it(self):
        result = self.run_check(doc("a: b\n"), "no header\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("f1.md", result.stderr)
        self.assertIn("MissingFrontmatterError", result.stderr)

    def test_non_ascii_file_exits_0(self):
        self.assertEqual(self.run_check(doc("a: ação — ü\n")).returncode, 0)

    def test_no_files_is_usage_error(self):
        result = subprocess.run([sys.executable, str(MODULE), "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
