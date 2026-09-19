"""Root message sections that split input into Message Text and Message Attributes."""

from rebulk import Rebulk
from rebulk.remodule import re


def message_sections():
    """Define Message Text and Message Attributes markers as the root split points.

    These MUST match only once per document and are the root of the
    dependency tree expressed as rebulk Rules per AGENTS.md.
    """
    rebulk = Rebulk()

    rebulk.regex(
        r"^[ \t]*Message Text[ \t]*$",
        name="message_text_marker",
        marker=True,
        tags=["section", "root"],
        flags=re.MULTILINE,
    )

    rebulk.regex(
        r"^[ \t]*Message Attributes[ \t]*$",
        name="message_attributes_marker",
        marker=True,
        tags=["section", "root"],
        flags=re.MULTILINE,
    )

    return rebulk
