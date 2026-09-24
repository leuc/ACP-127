"""Report provided Message Attributes missing from body extraction.

This is a semantic complement to byte coverage: a document can have complete
byte coverage while a header field supplied in Message Attributes failed to
produce its independently extracted body field.

Evidence classes (per missing attribute/body pair):

* ``metadata_only`` -- the attribute is provided but the telegram body has
  no trace of the value at all (not even as unstructured prose).
* ``body_only`` -- (reported separately) the body extraction exists while
  the attribute is absent; a frequent, expected metadata-enrichment shape.
* ``comparable`` -- both sides present in a comparable form; agreement is
  checked with the field comparator and reported as ``agree``/``divergent``
  (``representation_divergent`` when the values match after field-specific
  normalization but differ as raw strings).
* ``later_section`` -- the document has section markers and the value may
  live in a later section whose header was not propagated (per-file miss,
  not recoverable by regex broadening; needs a section join keyed by
  validated section MRN, which is outside the extractor).
* ``candidate_rejected`` -- positional validation rejected every raw
  candidate (inferred when the raw value text appears in the body but no
  body field was emitted and the document has no sections).
* ``true_missing`` -- none of the above: eligible body, no sections, no
  body trace of the value.

Comparators: TAGS uses tokenization on comma/whitespace with N/A and
terminal periods normalized; SUBJECT uses whitespace/punctuation
normalization plus a hard alphanumeric comparison; REF compares MRN
cores only where an MRN core exists; drafting joins all officer lines;
EO codes use an explicit equivalence map (comparison-only; no map
belongs in extraction). Current Classification versus body
classification and EO attribute codes versus printed EO lines are
semantically different comparisons -- their disjoint groups are not
automatically extraction failures. The comparator never proves
identity; original raw values stay in the diagnostic output.
"""

import argparse
from collections import Counter
import re
import sys

try:
    import orjson as json
except ImportError:
    import json

from .coverage import (
    ATTRIBUTE_BODY_FIELDS,
    has_retrievable_body,
    missing_body_extractions,
)

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")
_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]")

# EO code-to-printed-marking equivalence for comparison only. Maps common
# attribute-side codes to the printed EO order numbers they correspond to.
# Lives here (quality reporting), never in extraction.
_EO_EQUIVALENCE = {
    "EO 11652": "11652",
    "E.O. 11652": "11652",
    "EO 11653": "11653",
    "E.O. 11653": "11653",
    "EO 12065": "12065",
    "E.O. 12065": "12065",
    "GDS": "11652",
    "XGDS": "11652",
    "RDS": "11652",
}


def _normalize_ws(text):
    return _WS_RE.sub(" ", str(text)).strip()


def _normalize_alnum(text):
    return _NON_ALNUM_RE.sub("", str(text).upper())


def _tags_tokens(text):
    tokens = [
        token.strip().strip(".").upper()
        for token in re.split(r"[\s,]+", str(text))
        if token.strip().strip(".")
    ]
    return [token for token in tokens if token not in ("N/A", "NA")]


def _ref_cores(text):
    """Return MRN cores (station + number runs) where they exist."""
    cores = set()
    for match in re.finditer(r"[A-Z]{2,}", str(text).upper()):
        cores.add(match.group(0))
    for match in re.finditer(r"\d{3,}", str(text)):
        cores.add(match.group(0))
    return cores


def _compare(attribute_name, provided, body_value):
    """Compare an attribute value with its body extraction.

    Returns ``agree``, ``representation_divergent`` or ``divergent``.
    """
    if attribute_name == "TAGS":
        provided_tokens = set(_tags_tokens(provided))
        body_tokens = set(_tags_tokens(body_value))
        if provided_tokens == body_tokens:
            if _normalize_ws(provided) == _normalize_ws(body_value):
                return "agree"
            return "representation_divergent"
        if provided_tokens and provided_tokens <= body_tokens:
            return "representation_divergent"
        return "divergent"
    if attribute_name == "Subject":
        if _normalize_alnum(provided) == _normalize_alnum(body_value):
            if _normalize_ws(provided) == _normalize_ws(body_value):
                return "agree"
            return "representation_divergent"
        return "divergent"
    if attribute_name == "Reference":
        provided_cores = _ref_cores(provided)
        body_cores = _ref_cores(body_value)
        if provided_cores and provided_cores <= body_cores:
            return "agree"
        if provided_cores and provided_cores & body_cores:
            return "representation_divergent"
        if _normalize_ws(provided) in _normalize_ws(body_value):
            return "agree"
        return "divergent"
    if attribute_name in ("Drafter",):
        provided_joined = _normalize_ws(provided)
        if isinstance(body_value, list):
            body_joined = _normalize_ws(" ".join(body_value))
        else:
            body_joined = _normalize_ws(body_value)
        if provided_joined == body_joined:
            return "agree"
        if _normalize_alnum(provided_joined) == _normalize_alnum(body_joined):
            return "representation_divergent"
        if provided_joined in body_joined or body_joined in provided_joined:
            return "representation_divergent"
        return "divergent"
    if attribute_name == "Executive Order":
        provided_norm = _normalize_alnum(
            _EO_EQUIVALENCE.get(_normalize_ws(provided), provided)
        )
        body_norm = _normalize_alnum(body_value)
        if provided_norm == body_norm:
            return "agree"
        if provided_norm in body_norm or body_norm in provided_norm:
            return "representation_divergent"
        return "divergent"
    if _normalize_ws(provided) == _normalize_ws(body_value):
        return "agree"
    if _normalize_alnum(provided) == _normalize_alnum(body_value):
        return "representation_divergent"
    provided_norm = _normalize_ws(provided)
    body_norm = _normalize_ws(body_value)
    if provided_norm in body_norm or body_norm in provided_norm:
        return "representation_divergent"
    return "divergent"


def _body_trace(attribute_name, provided, document):
    """Return whether the raw attribute value appears anywhere in the body."""
    body = document.get("_message_content") or ""
    if not body or not provided:
        return False
    if isinstance(provided, list):
        return any(
            _normalize_ws(item) and _normalize_ws(item) in _normalize_ws(body)
            for item in provided
        )
    needle = _normalize_ws(provided)
    return bool(needle) and needle in _normalize_ws(body)


def classify_issue(document, issue):
    """Assign an evidence class to one missing attribute/body pair."""
    attribute_name = issue["attribute"]
    provided = issue["provided_value"]
    has_sections = bool(document.get("_section_marker"))
    if has_sections:
        return "later_section"
    if _body_trace(attribute_name, provided, document):
        return "candidate_rejected"
    return "true_missing"


def _loads(line):
    return json.loads(line)


def _dumps(value):
    output = json.dumps(value)
    if isinstance(output, bytes):
        return output.decode("utf-8")
    return output


def _documents(paths):
    for path in paths:
        if path == "-":
            for line_number, line in enumerate(sys.stdin.buffer, 1):
                if line.strip():
                    yield "<stdin>", line_number, _loads(line)
            continue

        with open(path, "rb") as source:
            for line_number, line in enumerate(source, 1):
                if line.strip():
                    yield path, line_number, _loads(line)


def _write_report(
    stream, inputs, documents, eligible, counts, cable_count, evidence_counts,
    agreement_counts,
):
    field_map = dict(ATTRIBUTE_BODY_FIELDS)
    lines = [
        "Attribute/body extraction completeness",
        f"inputs: {', '.join(inputs)}",
        f"documents_processed: {documents}",
        f"documents_with_retrievable_body: {eligible}",
        f"cables_with_missing_body_extractions: {cable_count}",
        f"missing_body_extractions: {sum(counts.values())}",
        "missing_by_field:",
    ]
    for attribute_name, _body_field in ATTRIBUTE_BODY_FIELDS:
        lines.append(
            f"    {attribute_name} -> {field_map[attribute_name]}: "
            f"{counts[attribute_name]}"
        )
    lines.append("missing_by_evidence_class:")
    lines.append(f"    metadata_only: {sum(counts.values())}")
    for evidence_class in (
        "true_missing",
        "candidate_rejected",
        "later_section",
    ):
        lines.append(
            f"    {evidence_class}: {evidence_counts[evidence_class]}"
        )
    lines.append("comparable_agreement:")
    for outcome in ("agree", "representation_divergent", "divergent"):
        lines.append(f"    {outcome}: {agreement_counts[outcome]}")
    stream.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Find retrievable telegrams where a supplied Message Attribute "
            "has no corresponding body-extracted field"
        )
    )
    parser.add_argument("inputs", nargs="+", help="Extractor NDJSON files, or -")
    args = parser.parse_args()

    documents = 0
    eligible = 0
    counts = Counter()
    evidence_counts = Counter()
    agreement_counts = Counter()
    cable_count = 0

    for input_path, line_number, document in _documents(args.inputs):
        documents += 1
        attributes = document.get("Message Attributes") or {}
        if has_retrievable_body(document):
            eligible += 1

        # Agreement audit on comparable pairs (both sides present).
        for attribute_name, body_field in ATTRIBUTE_BODY_FIELDS:
            provided = attributes.get(attribute_name)
            body_value = document.get(body_field)
            if provided in (None, "") or body_value in (None, "", [], {}):
                continue
            agreement_counts[
                _compare(attribute_name, provided, body_value)
            ] += 1

        missing = missing_body_extractions(document)
        if not missing:
            continue

        filepath = document.get("_file")
        cable_count += 1
        enriched = []
        for issue in missing:
            evidence_class = classify_issue(document, issue)
            counts[issue["attribute"]] += 1
            evidence_counts[evidence_class] += 1
            enriched.append({**issue, "evidence_class": evidence_class})
        sys.stdout.write(
            _dumps(
                {
                    "file": filepath or f"{input_path}:{line_number}",
                    "document_number": attributes.get("Document Number"),
                    "missing": enriched,
                }
            )
            + "\n"
        )

    _write_report(
        sys.stderr,
        args.inputs,
        documents,
        eligible,
        counts,
        cable_count,
        evidence_counts,
        agreement_counts,
    )


if __name__ == "__main__":
    main()
