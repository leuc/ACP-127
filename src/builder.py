"""Central builder that composes all pattern modules into a single Rebulk object."""

from rebulk import Rebulk

from .patterns.markers import markers
from .patterns.locator import locator
from .patterns.attributes import attributes
from .patterns.classification import classification
from .patterns.page_break import page_break
from .rules.split import (
    ValidateSingleMessageText,
    ValidateSingleMessageAttributes,
    MessageContentRegion,
)


def build_rebulk():
    """Build and return the main Rebulk object with all patterns and rules."""
    rebulk = Rebulk()

    rebulk.rebulk(markers())
    rebulk.rebulk(locator())
    rebulk.rebulk(attributes())
    rebulk.rebulk(classification())
    rebulk.rebulk(page_break())

    rebulk.rules(
        ValidateSingleMessageText,
        ValidateSingleMessageAttributes,
        MessageContentRegion,
    )

    return rebulk
