import re

TOKEN = re.compile(r"\{\{[^{}\n]*\}\}")
KNOWN = ("CORE", "SIDE", "PY", "CONFIG_DIR")


class UnknownTokenError(Exception):
    def __init__(self, tokens, source):
        super().__init__(f"{source}: unknown or unset token(s) {', '.join(sorted(tokens))}")
        self.tokens = tokens


def render_tokens(text, values, source):
    leftover = set()

    def replace(match):
        name = match.group(0)[2:-2]
        if name in KNOWN and name in values:
            return str(values[name])
        leftover.add(match.group(0))
        return match.group(0)

    rendered = TOKEN.sub(replace, text)
    if leftover:
        raise UnknownTokenError(leftover, source)
    return rendered
