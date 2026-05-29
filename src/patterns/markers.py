"""Root markers that split input into Message Text and Message Attributes sections."""

from rebulk import Rebulk
from rebulk.remodule import re


def markers():
    """Define Message Text and Message Attributes markers as the root split points.

    These MUST match only once per document and are the root of the
    dependency tree expressed as rebulk Rules per AGENTS.md.
    """
    rebulk = Rebulk()

    rebulk.regex(
        r"\s+Message Text\b",
        name="message_text_marker",
        marker=True,
        tags=["section", "root"],
        flags=re.IGNORECASE,
    )

    rebulk.regex(
        r"\s+Message Attributes\b",
        name="message_attributes_marker",
        marker=True,
        tags=["section", "root"],
        flags=re.IGNORECASE,
    )

    return rebulk
