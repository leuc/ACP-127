r"""Identify page break markers (PAGE \d+) and end-of-message markers (NNNNMAFVVZCZ).

Page break lines are extracted as _page_breaks and stripped from _message_content
(via ExtractPageBreak rule using match positions).
End-of-message markers are used internally for classification proximity validation.
"""

from functools import partial

from rebulk import Rebulk
from rebulk.remodule import re
from rebulk.validators import chars_before

_KNOWN_END_MARKERS = {"NNN", "NNNN", "NNNNMAFVVZCZ", "<< END OF DOCUMENT >>"}


def page_break():
    """Build pattern that matches page break and end-of-message markers."""
    rebulk = Rebulk()
    rebulk.defaults(flags=re.MULTILINE)

    rebulk.regex(
        r"^PAGE\s+(?P<page_number>\d+).*",
        name="page_break",
        tags=["page_break"],
        flags=re.MULTILINE | re.IGNORECASE,
        every=True,
        private_names=["page_number"],
    )

    for marker in _KNOWN_END_MARKERS:
        rebulk.string(
            marker,
            name="end_marker",
            tags=["end_marker"],
            validator=partial(chars_before, "\n"),
        )

    rebulk.regex(
        r"^\*\*\* Current (?:Handling Restrictions|Classification) .*",
        name="content_footer_marker",
        tags=["content_footer"],
    )

    return rebulk
