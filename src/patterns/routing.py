"""Shared utility for routing header extraction.

The routing header is the block between FM and the first blank line
in the message content. Both TO and INFO lines live here.
"""

from rebulk.remodule import re


def find_routing_header(mc_text):
    """Return (header_start, header_end, header_text) or None."""
    fm_m = re.search(r"^FM\s+", mc_text, re.MULTILINE)
    if not fm_m:
        return None
    header_start = fm_m.start()
    rest = mc_text[header_start:]
    blank_m = re.search(r"\n\s*\n", rest)
    header_end = blank_m.start() if blank_m else len(rest)
    return header_start, header_end, rest[:header_end]
