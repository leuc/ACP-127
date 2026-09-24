"""Shared utility for routing header extraction.

The routing header is the block between FM and the first blank line
in the message content. Both TO and INFO lines live here.

Section 4.3 replaces the two independent collectors
(``ParseTo._collect_to_lines`` / ``ParseInfo._collect_info_lines``) with
a single joint walk over the FM-to-header-end window. The walker returns
TO and INFO values plus exact line intervals for each, so no later rule
needs to carve TAGS or SUBJECT out of a routing value.
"""

from rebulk.remodule import re

_FM_RE = re.compile(r"^FM[ \t]+", re.MULTILINE)
_BLANK_RE = re.compile(r"\n\s*\n")
_TO_RE = re.compile(r"^TO\s", re.IGNORECASE)
_INFO_RE = re.compile(r"^INFO\s", re.IGNORECASE)

# Labels that end the routing window even without a blank separator: a
# label wins over a continuation. Kept deliberately narrow -- only labels
# with corpus evidence as routing followers.
_STOP_LABEL_RES = (
    re.compile(r"^(?:E\s*\.?\s*O\s*\.?|EO)\b", re.IGNORECASE),
    re.compile(r"^TAGS?\b", re.IGNORECASE),
    re.compile(r"^SUBJ", re.IGNORECASE),
    re.compile(r"^REF(?:S|ERENCE)?\b|^REFTEL\b|^RETELS?\b", re.IGNORECASE),
    re.compile(r"^(?:EXDIS|NODIS|LIMDIS|NOFORN|FOUO|NESCO|STADIS|ONLY|LOU)\b",
               re.IGNORECASE),
)


def find_routing_header(mc_text):
    """Return (header_start, header_end, header_text) or None.

    Absolute clean-view offsets into ``mc_text``. The window runs from
    the FM line start to the first blank line, known header label,
    classification banner, page/end marker, or section marker --
    whichever comes first. Kept for backwards compatibility; prefer
    :func:`walk_routing` for new code.
    """
    walked = walk_routing(mc_text)
    if walked is None:
        return None
    return walked["header_start"], walked["header_end"], walked["header_text"]


def _is_stop_line(stripped):
    """Return whether a stripped line ends the routing window."""
    for pattern in _STOP_LABEL_RES:
        if pattern.match(stripped):
            return True
    if stripped.upper().startswith("SECTION "):
        return True
    return False


def walk_routing(mc_text):
    """Jointly walk the FM-to-header-end window.

    Returns a dict with absolute clean-view ``(start, end)`` intervals::

        {
            "header_start": int, "header_end": int, "header_text": str,
            "to": {"value": str, "spans": [(start, end), ...]} | None,
            "info": {"value": str, "spans": [(start, end), ...]} | None,
            "stop_reason": str,  # "blank" | "label:<LABEL>" | "end"
        }

    Accepts TO/INFO labels at line start, alternation between them, and
    valid indented continuations. Stops at the first blank line or known
    EO/TAGS/SUBJECT/REF/section label, classification banner, page/end
    marker, or body-start line. A label wins over a continuation even
    without a blank separator. Tolerates an INFO-first record.
    """
    fm_m = _FM_RE.search(mc_text)
    if not fm_m:
        return None
    line_start = mc_text.rfind("\n", 0, fm_m.start()) + 1
    header_start = line_start

    to_parts, to_spans = [], []
    info_parts, info_spans = [], []
    current = None
    stop_reason = "end"

    offset = line_start
    lines = mc_text[line_start:].split("\n")
    header_end = len(mc_text)
    for index, line in enumerate(lines):
        abs_start = offset
        abs_end = offset + len(line)
        stripped = line.strip()
        upper = stripped.upper()
        if not stripped:
            header_end = abs_start
            stop_reason = "blank"
            break
        if index > 0 and _is_stop_line(stripped):
            header_end = abs_start
            stop_reason = "label:" + stripped.split()[0].upper()
            break
        if _TO_RE.match(stripped):
            current = "TO"
            to_parts.append(stripped[3:].strip())
            to_spans.append((abs_start, abs_end))
        elif _INFO_RE.match(stripped):
            current = "INFO"
            info_parts.append(stripped[5:].strip())
            info_spans.append((abs_start, abs_end))
        elif index == 0:
            # The FM line itself.
            current = None
        elif current in ("TO", "INFO"):
            if current == "TO":
                to_parts.append(stripped)
                to_spans.append((abs_start, abs_end))
            else:
                info_parts.append(stripped)
                info_spans.append((abs_start, abs_end))
        else:
            # Text before any TO/INFO label (e.g. DTG residue) -- not
            # part of either value, but still inside the window.
            pass
        offset = abs_end + 1

    header_text = mc_text[header_start:header_end]
    result = {
        "header_start": header_start,
        "header_end": header_end,
        "header_text": header_text,
        "to": None,
        "info": None,
        "stop_reason": stop_reason,
    }
    if to_parts:
        result["to"] = {"value": " ".join(to_parts), "spans": to_spans}
    if info_parts:
        result["info"] = {"value": " ".join(info_parts), "spans": info_spans}
    return result
