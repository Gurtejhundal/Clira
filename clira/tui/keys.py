"""Modified keys reported by CSI-u and xterm modifyOtherKeys terminals.

Legacy terminals may send ordinary Enter/Backspace for shifted keys. Never remap those:
Ctrl+J and /back remain available when the terminal cannot distinguish the modifiers.
"""

from prompt_toolkit.input.vt100_parser import ANSI_SEQUENCES
from prompt_toolkit.keys import Keys


def register_modified_keys():
    for code in (13,):
        for sequence in (f"\x1b[{code};2u", f"\x1b[27;2;{code}~", f"\x1b[{code};2~"):
            ANSI_SEQUENCES[sequence] = (Keys.Escape, Keys.ControlM)
    for code in (8, 127):
        for sequence in (f"\x1b[{code};2u", f"\x1b[27;2;{code}~", f"\x1b[{code};2~"):
            ANSI_SEQUENCES[sequence] = (Keys.Escape, Keys.ControlH)
