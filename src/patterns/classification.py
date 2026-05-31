"""Identify standalone classification marker lines (UNCLASSIFIED, CONFIDENTIAL, etc.)."""

from rebulk import Rebulk
from rebulk.remodule import re

_CLASSIFICATIONS = [
    "UNCLASSIFIED",
    "LIMITED OFFICIAL USE",
    "CONFIDENTIAL",
    "SECRET",
    "TOP SECRET",
]


def classification():
    """Build pattern that matches standalone classification marker lines."""
    rebulk = Rebulk()

    rebulk.regex(
        r"^\s*(?P<classification>" + "|".join(_CLASSIFICATIONS) + r")\s*$\n{0,2}",
        name="classification_marker",
        tags=["classification"],
        flags=re.MULTILINE | re.IGNORECASE,
    )

    return rebulk
