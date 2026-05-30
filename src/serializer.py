"""Serialize rebulk matches to the standard JSON output format.

Every document produces a flat JSON object with:
  - ``Message Attributes`` (dict) — all ACP-127 key:value fields
  - ``_``-prefixed fields — computed/metadata matches not from the attribute section
"""


def result_to_dict(matches):
    attributes = {}
    others = {}
    for match in matches:
        if match.private or match.marker or match.parent:
            continue
        name = match.name
        if not name:
            continue
        value = match.value
        if value is not None and isinstance(value, str):
            value = value.strip()
            if value.startswith(name + ":"):
                value = value[len(name) + 1 :].strip()
            # Normalize common placeholder values to None for better coverage accuracy
            if value.lower() in ("n/a", "na", "") or value == "N/A":
                value = None
        if match.tags and "attribute" in match.tags:
            attributes[name] = value
        else:
            others["_" + name] = value
    result = {"Message Attributes": attributes}
    result.update(others)
    return result
