"""Render untrusted content as terminal text, never terminal instructions."""

import re
import unicodedata

ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))")


def terminal_text(value):
    text = ANSI.sub("", str(value))
    return "".join(c for c in text if c in "\n\t" or unicodedata.category(c) not in {"Cc", "Cf", "Cs"})
