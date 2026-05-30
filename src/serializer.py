"""Serialize rebulk matches to the standard JSON output format.

Every document produces a flat JSON object with:
  - ``Message Attributes`` (dict) — all ACP-127 key:value fields
  - ``_``-prefixed fields — computed/metadata matches not from the attribute section
"""


def normalize_match_value(name, value):
    """Normalize a match value: strip, remove name: prefix, convert N/A to None."""
    if value is None or not isinstance(value, str):
        return value
    value = value.strip()
    if value.startswith(name + ":"):
        value = value[len(name) + 1 :].strip()
    if value.lower() in ("n/a", "na", ""):
        value = None
    return value


def is_na_value(name, value):
    """Return True if this match's value is a meaningless placeholder."""
    return normalize_match_value(name, value) is None


def result_to_dict(matches):
    attributes = {}
    others = {}
    for match in matches:
        if match.private or match.marker or match.parent:
            continue
        name = match.name
        if not name:
            continue
        value = normalize_match_value(name, match.value)
        if match.tags and "attribute" in match.tags:
            attributes[name] = value
        else:
            others["_" + name] = value
    result = {"Message Attributes": attributes}
    result.update(others)
    return result
