#!/usr/bin/env python3
"""Stdlib frontmatter subset: scalars, inline and block lists, nested maps.

parse(text) -> (mapping, body); emit(mapping) -> header text; render(mapping, body) -> document.
Anything outside the subset raises a named FrontmatterError.

CLI: frontmatter.py --check <file>...   exit 1 when any file is not valid frontmatter.
"""
import json
import re
import sys

BARE_RESERVED = {"true", "false", "null", "yes", "no", "on", "off", "~"}
NUMBER = re.compile(r"^[-+]?(\d+|\d*\.\d+)([eE][-+]?\d+)?$")
INTEGER = re.compile(r"^[-+]?\d+$")
KEY = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.-]*):(?:\s+(.*)|\s*)$")
UNSUPPORTED_START = ("|", ">", "&", "*", "!", "{", "%", "@", "`")
SPECIAL_START = set("-?:,[]{}#&*!|>'\"%@`")


class FrontmatterError(Exception):
    pass


class MissingFrontmatterError(FrontmatterError):
    def __init__(self):
        super().__init__("missing or unterminated frontmatter")


class UnsupportedSyntaxError(FrontmatterError):
    def __init__(self, number, detail):
        super().__init__(f"line {number}: {detail}")


class UnsupportedValueError(FrontmatterError):
    def __init__(self, key, value):
        super().__init__(f"{key}: cannot emit {type(value).__name__} value")


def split(text):
    lines = text.split("\n")
    if lines[0] != "---":
        raise MissingFrontmatterError()
    for index in range(1, len(lines)):
        if lines[index] == "---":
            return lines[1:index], "\n".join(lines[index + 1:]).lstrip("\n")
    raise MissingFrontmatterError()


def parse_scalar(raw, number):
    if raw.startswith("\""):
        try:
            value = json.loads(raw)
        except ValueError:
            raise UnsupportedSyntaxError(number, "malformed double-quoted string")
        if not isinstance(value, str):
            raise UnsupportedSyntaxError(number, "malformed double-quoted string")
        return value
    if raw.startswith("'"):
        if len(raw) < 2 or not raw.endswith("'"):
            raise UnsupportedSyntaxError(number, "malformed single-quoted string")
        return raw[1:-1].replace("''", "'")
    if raw.startswith(UNSUPPORTED_START):
        raise UnsupportedSyntaxError(number, f"unsupported construct {raw[0]!r}")
    if raw in ("true", "false"):
        return raw == "true"
    if raw in ("null", "~"):
        return None
    if INTEGER.match(raw):
        return int(raw)
    return raw


def split_inline(inner, number):
    items, current, quote = [], "", None
    for char in inner:
        if quote:
            current += char
            if char == quote:
                quote = None
            continue
        if char in "\"'":
            quote = char
            current += char
            continue
        if char in "[]{}":
            raise UnsupportedSyntaxError(number, "nested inline collections are not supported")
        if char == ",":
            items.append(current.strip())
            current = ""
            continue
        current += char
    if quote:
        raise UnsupportedSyntaxError(number, "unterminated quote in inline list")
    if current.strip() or items:
        items.append(current.strip())
    return items


def parse_inline_list(raw, number):
    if not raw.endswith("]"):
        raise UnsupportedSyntaxError(number, "unterminated inline list")
    return [parse_scalar(item, number) for item in split_inline(raw[1:-1], number) if item != ""]


def parse_value(raw, number):
    if raw.startswith("["):
        return parse_inline_list(raw, number)
    return parse_scalar(raw, number)


def indent_of(line):
    return len(line) - len(line.lstrip(" "))


def significant(lines):
    return [(number, line) for number, line in enumerate(lines, 2) if line.strip() and not line.lstrip().startswith("#")]


def parse_block_list(entries, position, floor):
    items = []
    while position < len(entries):
        number, line = entries[position]
        if indent_of(line) < floor or not line.lstrip().startswith("- "):
            break
        items.append(parse_scalar(line.lstrip()[2:].strip(), number))
        position += 1
    return items, position


def parse_map(entries, position, indent):
    result = {}
    while position < len(entries):
        number, line = entries[position]
        if "\t" in line[: indent_of(line) + 1]:
            raise UnsupportedSyntaxError(number, "tabs are not supported")
        current = indent_of(line)
        if current < indent:
            break
        if current > indent:
            raise UnsupportedSyntaxError(number, "unexpected indentation")
        match = KEY.match(line.strip())
        if not match:
            raise UnsupportedSyntaxError(number, "expected 'key: value'")
        key, raw = match.group(1), match.group(2)
        position += 1
        if raw is not None and raw.strip():
            result[key] = parse_value(raw.strip(), number)
            continue
        result[key], position = parse_child(entries, position, indent)
    return result, position


def parse_child(entries, position, indent):
    if position >= len(entries):
        return None, position
    number, line = entries[position]
    child_indent = indent_of(line)
    if line.lstrip().startswith("- ") and child_indent >= indent:
        return parse_block_list(entries, position, child_indent)
    if child_indent > indent:
        return parse_map(entries, position, child_indent)
    return None, position


def parse(text):
    header, body = split(text)
    entries = significant(header)
    for number, line in entries:
        if line.startswith("\t") or line.lstrip(" ").startswith("\t"):
            raise UnsupportedSyntaxError(number, "tabs are not supported")
    mapping, position = parse_map(entries, 0, 0)
    if position < len(entries):
        raise UnsupportedSyntaxError(entries[position][0], "unexpected content")
    return mapping, body


def needs_quotes(value):
    if value == "" or value != value.strip():
        return True
    if value.lower() in BARE_RESERVED or NUMBER.match(value):
        return True
    if value[0] in SPECIAL_START:
        return True
    if ": " in value or " #" in value or value.endswith(":"):
        return True
    return any(ord(char) < 32 for char in value)


def emit_scalar(key, value, in_list=False):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        quoted = needs_quotes(value) or (in_list and any(char in value for char in ",[]{}"))
        return json.dumps(value, ensure_ascii=False) if quoted else value
    raise UnsupportedValueError(key, value)


def emit_lines(mapping, indent):
    pad = "  " * indent
    lines = []
    for key, value in mapping.items():
        if isinstance(value, dict) and value:
            lines.append(f"{pad}{key}:")
            lines.extend(emit_lines(value, indent + 1))
            continue
        if isinstance(value, dict):
            raise UnsupportedValueError(key, value)
        if isinstance(value, (list, tuple)):
            items = ", ".join(emit_scalar(key, item, True) for item in value)
            lines.append(f"{pad}{key}: [{items}]")
            continue
        lines.append(f"{pad}{key}: {emit_scalar(key, value)}")
    return lines


def emit(mapping):
    lines = emit_lines(mapping, 0)
    return "".join(f"{line}\n" for line in lines)


def render(mapping, body):
    return f"---\n{emit(mapping)}---\n{body}"


def check(paths):
    failures = 0
    for path in paths:
        try:
            with open(path, encoding="utf-8") as handle:
                parse(handle.read())
        except (FrontmatterError, OSError, UnicodeDecodeError) as error:
            print(f"{path}: {type(error).__name__}: {error}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


def main(argv):
    if len(argv) < 3 or argv[1] != "--check":
        print("usage: frontmatter.py --check <file>...", file=sys.stderr)
        return 2
    return check(argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
