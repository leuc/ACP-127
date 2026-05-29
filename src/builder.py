"""Central builder that composes all pattern modules into a single Rebulk object."""

from rebulk import Rebulk

from .patterns.message_sections import message_sections
from .patterns.locator import locator
from .patterns.attributes import attributes
from .patterns.classification import classification
from .patterns.declass_markings import declass_markings
from .patterns.page_break import page_break
from .patterns.dtg import dtg
from .patterns.distribution import distribution
from .rules.split import (
    ValidateSingleMessageText,
    ValidateSingleMessageAttributes,
    MessageContentRegion,
)


def build_rebulk():
    """Build and return the main Rebulk object with all patterns and rules."""
    rebulk = Rebulk()

    rebulk.rebulk(message_sections())
    rebulk.rebulk(locator())
    rebulk.rebulk(attributes())
    rebulk.rebulk(classification())
    rebulk.rebulk(declass_markings())
    rebulk.rebulk(page_break())
    rebulk.rebulk(dtg())
    rebulk.rebulk(distribution())

    rebulk.rules(
        ValidateSingleMessageText,
        ValidateSingleMessageAttributes,
        MessageContentRegion,
    )

    return rebulk
