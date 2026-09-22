"""Serialize rebulk matches to the standard JSON output format.

Every document produces a flat JSON object with:
  - ``Message Attributes`` (dict) — all ACP-127 key:value fields
  - ``_``-prefixed fields — computed/metadata matches not from the attribute section
"""


_NA_STRINGS = ("n/a", "na", "")


def is_empty_value(value):
    """Return True if a (possibly serialized) value carries no information.

    Shared basis for ``normalize_match_value``/``is_na_value`` (pre-serialization,
    match values) and ``coverage._has_value`` (post-serialization, JSON values):
    None, NA strings (case-insensitive, whitespace-tolerant) and empty
    collections all count as empty. Numbers and booleans always count as
    present — even 0/False, which are genuine extracted values, not placeholders.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in _NA_STRINGS
    if isinstance(value, (list, dict, set, tuple)):
        return len(value) == 0
    return False


def normalize_match_value(name, value):
    """Normalize a match value: strip, remove name: prefix, convert N/A to None."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value.startswith(name + ":"):
            value = value[len(name) + 1 :].strip()
        if value.lower() in _NA_STRINGS:
            return None
        return value
    if isinstance(value, (list, dict, set, tuple)) and len(value) == 0:
        return None
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
