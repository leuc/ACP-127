"""ACPD extractor — structured JSON extraction from ACP-127 telegrams."""

from .batch import process_batch
from .builder import build_rebulk
from .coverage import CoverageTracker
from .extractor import (
    extract_from_text,
    extract_file,
    process_documents,
    result_to_dict,
)
