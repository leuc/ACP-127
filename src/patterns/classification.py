"""Identify standalone classification marker lines (UNCLASSIFIED, CONFIDENTIAL, etc.).

Two shapes are matched on the same line:
  - bare: "CONFIDENTIAL"
  - banner: "CONFIDENTIAL ABIDJAN 4532" (classification + cable ID attached),
    optionally with letter-spaced classification text ("C O N F I D E N T I A L
    ABIDJAN 4532") — the same NARA reproduction-noise pattern
    `section_marker.py::_spaced_alternation` already tolerates for the
    classification+"SECTION N OF M" combo. Without this, the banner line
    (present in most documents, often redundantly alongside a bare
    classification line elsewhere) is left unmatched in `_message_content`,
    polluting the body text with tens of thousands of leftover lines per year
    even though document-level classification_marker coverage is usually
    unaffected by a different, already-matching bare occurrence.
"""

from rebulk import Rebulk
from rebulk.remodule import re

_CLASSIFICATIONS = [
    "UNCLASSIFIED",
    "UNCLAS",
    "LIMITED OFFICIAL USE",
    "CONFIDENTIAL",
    "SECRET",
    "TOP SECRET",
]


def spaced_alternation(classifications=None):
    """Build alternation pattern for classifications with spaced-out letters.

    Shared by ``section_marker.py`` -- both modules must tolerate the same
    NARA reproduction-noise pattern of injected whitespace mid-token.
    """
    parts = []
    for cls in classifications or _CLASSIFICATIONS:
        words = cls.split()
        spaced_words = [" ".join(word) for word in words]
        parts.append(r"\s+".join(spaced_words))
    return "|".join(parts)


def _spaced_alternation():
    """Backwards-compatible alias for the shared helper."""
    return spaced_alternation()


_CLASS_ALT = "(?:" + "|".join(_CLASSIFICATIONS) + "|" + _spaced_alternation() + r")"
_BANNER_SUFFIX = r"(?:[ \t]+[A-Z][A-Z \-]*[A-Z]\s+\d+[A-Z]?)?"


def _classification_value(line):
    """Return the normalized classification word from a matched line."""
    m = re.match(r"^\s*(?P<classification>" + _CLASS_ALT + r")", line, re.IGNORECASE)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group("classification")).strip().upper()


def classification():
    """Build pattern that matches standalone classification marker lines."""
    rebulk = Rebulk()

    rebulk.regex(
        r"^\s*(?P<classification>" + _CLASS_ALT + r")" + _BANNER_SUFFIX + r"\s*$\n{0,2}",
        name="classification_marker",
        tags=["classification"],
        flags=re.MULTILINE | re.IGNORECASE,
        formatter=_classification_value,
        # Private candidate: only the ExtractClassificationMarker aggregate
        # (list of unique values) may serialize. Rejected candidates stay
        # in the body text but must never leak as raw strings into JSON.
        private=True,
    )
    return rebulk
