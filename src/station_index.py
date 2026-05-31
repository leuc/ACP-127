"""Station name resolution with exact variant lookup and fuzzy fallback.

Provides a StationIndex that consolidates:
  - Exact variant-to-canonical mapping (known OCR errors / abbreviations)
  - Fuzzy (Levenshtein) fallback for novel typos
  - Regex alternation pattern for multi-stage matching
  - STOP_STATIONS filter for false positive prevention
"""

from difflib import get_close_matches

from station_data import STATIONS, _VARIANT_TO_TARGET, _SINGLE_STATIONS

_STOP_STATIONS = frozenset(
    s.upper()
    for s in [
        "JANUARY",
        "FEBRUARY",
        "MARCH",
        "APRIL",
        "MAY",
        "JUNE",
        "JULY",
        "AUGUST",
        "SEPTEMBER",
        "OCTOBER",
        "NOVEMBER",
        "DECEMBER",
        "JAN",
        "FEB",
        "MAR",
        "APR",
        "MAY",
        "JUN",
        "JUL",
        "AUG",
        "SEP",
        "OCT",
        "NOV",
        "DEC",
        "DATED",
        "DATE",
        "NUMBER",
        "NBR",
        "REFERENCE",
        "REF",
        "REFTEL",
        "PAGE",
        "PAGES",
        "SECTION",
        "CLASSIFIED",
        "UNCLASSIFIED",
        "SECRET",
        "CONFIDENTIAL",
        "SENSITIVE",
        "NOTAL",
        "EXDIS",
        "NODIS",
        "STADIS",
        "MONDAY",
        "TUESDAY",
        "WEDNESDAY",
        "THURSDAY",
        "FRIDAY",
        "SATURDAY",
        "SUNDAY",
        "PART",
        "SECT",
        "ITEM",
        "NOTE",
    ]
)

_MIN_STATION_LEN = 3
_FUZZY_CUTOFF = 0.90


class StationIndex:
    """Index for station name resolution and pattern building."""

    def __init__(self, fuzzy_cutoff=_FUZZY_CUTOFF):
        self._fuzzy_cutoff = fuzzy_cutoff
        self._canonical_set = set(STATIONS)
        self._canonical_list = sorted(STATIONS, key=lambda s: (-len(s), s))
        self._pattern = None

    def resolve(self, name, allow_fuzzy=True):
        """Resolve a station name to its canonical form.

        Tries exact variant lookup first, then fuzzy fallback.
        Returns canonical name or None if no match found.

        Fuzzy matching is conservative: if the input ends with 'A' and the
        only close match would drop that 'A' (indicating a potential airgram
        suffix instead of a typo), the match is rejected.
        """
        normalized = name.strip().upper()
        if len(normalized) < _MIN_STATION_LEN:
            return None
        if normalized in _STOP_STATIONS:
            return None

        # 1) Exact variant lookup
        canonical = _VARIANT_TO_TARGET.get(normalized)
        if canonical is not None:
            return canonical

        # 2) Direct canonical name match
        if normalized in self._canonical_set:
            return normalized

        if not allow_fuzzy:
            return None

        # 2) Fuzzy fallback — but not if input ends in 'A' (likely airgram)
        if normalized.endswith("A"):
            # Check if the only close match is just dropping the A
            plain = normalized[:-1]
            if plain in self._canonical_set:
                return None

        matches = get_close_matches(
            normalized, self._canonical_list, n=1, cutoff=self._fuzzy_cutoff
        )
        if matches:
            return matches[0]

        return None

    def is_stop_station(self, name):
        """Return True if *name* is a known stop-word (never a valid station)."""
        return name.strip().upper() in _STOP_STATIONS

    def alternation_pattern(self):
        """Build regex alternation string for ALL known station forms.

        Includes canonical names, single-word variants (abbreviations,
        OCR errors), and multi-word variant patterns (e.g. ``USUN NEW YORK``
        as ``USUN NEW YORK``).  All entries are sorted longest-first so
        the regex engine prefers longer matches (avoids partial matches like
        ``USUN`` matching before ``USUNNEWYORK``).
        """
        if self._pattern is not None:
            return self._pattern

        seen = set()
        parts = []

        for name in self._canonical_list:
            if " " in name:
                p = name.replace(" ", r"\s+")
            else:
                p = name
            if p not in seen:
                parts.append((len(p), p))
                seen.add(p)

        for variant in _VARIANT_TO_TARGET:
            if " " in variant:
                p = variant.replace(" ", r"\s+")
            else:
                p = variant
            if p not in seen:
                parts.append((len(p), p))
                seen.add(p)

        parts.sort(key=lambda x: (-x[0], x[1]))
        self._pattern = "|".join(p[1] for p in parts)
        return self._pattern

        seen = set()
        parts = []

        for name in self._canonical_list:
            if " " in name:
                p = name.replace(" ", r"\s+")
            else:
                p = name
            if p not in seen:
                parts.append(p)
                seen.add(p)

        for variant, canonical in _VARIANT_TO_TARGET.items():
            if " " in variant:
                p = variant.replace(" ", r"\s+")
                if p not in seen:
                    parts.append(p)
                    seen.add(p)

        self._pattern = "|".join(parts)
        return self._pattern

    @property
    def canonical_names(self):
        return self._canonical_list
