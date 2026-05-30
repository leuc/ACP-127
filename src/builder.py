"""Central builder that composes all pattern modules into a single Rebulk object."""

from rebulk import Rebulk

from .patterns.message_sections import message_sections
from .patterns.locator import locator
from .patterns.attributes import attributes
from .patterns.classification import classification
from .patterns.declass_markings import declass_markings
from .patterns.page_break import page_break
from .patterns.dash_counter import dash_counter
from .patterns.dtg import dtg
from .patterns.distribution import distribution
from .patterns.from_line import from_line
from .patterns.to_line import to_line
from .patterns.info_line import info_line
from .patterns.drafting import drafting
from .patterns.eo_line import eo_line
from .patterns.tags_line import tags_line
from .patterns.subject_line import subject_line
from .patterns.ref_line import ref_line
from .patterns.section_marker import section_marker
from .rules.validate import (
    ValidateSingleMessageText,
    ValidateSingleMessageAttributes,
)
from .rules.declass_removal import RemoveDeclassMarkings
from .rules.classification_extraction import ExtractClassificationMarker
from .rules.page_break_extraction import ExtractPageBreak
from .rules.end_marker_removal import RemoveEndMarker
from .rules.message_content import BuildMessageContent
from .rules.header_removal import RemoveHeaders


def build_rebulk():
    """Build and return the main Rebulk object with all patterns and rules."""
    rebulk = Rebulk()

    rebulk.rebulk(message_sections())
    rebulk.rebulk(locator())
    rebulk.rebulk(attributes())
    rebulk.rebulk(classification())
    rebulk.rebulk(declass_markings())
    rebulk.rebulk(page_break())
    rebulk.rebulk(dash_counter())
    rebulk.rebulk(dtg())
    rebulk.rebulk(distribution())
    rebulk.rebulk(from_line())
    rebulk.rebulk(to_line())
    rebulk.rebulk(info_line())
    rebulk.rebulk(drafting())
    rebulk.rebulk(eo_line())
    rebulk.rebulk(tags_line())
    rebulk.rebulk(subject_line())
    rebulk.rebulk(ref_line())
    rebulk.rebulk(section_marker())

    rebulk.rules(
        ValidateSingleMessageText,
        ValidateSingleMessageAttributes,
        RemoveDeclassMarkings,
        ExtractClassificationMarker,
        ExtractPageBreak,
        RemoveEndMarker,
        BuildMessageContent,
        RemoveHeaders,
    )

    return rebulk
