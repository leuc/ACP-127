"""Remove declassification marking lines and content footer markers.

These are EO Systematic Review markings added by the declassification process,
not part of the original ACP-127 telegram text. Removed without JSON output.
"""

from rebulk import Rule, RemoveMatch

from ..rules.validate import ValidateSingleMessageAttributes


class RemoveDeclassMarkings(Rule):
    """Remove marking_line + content_footer_marker outside the content region.

    Runs after ValidateSingleMessageAttributes to ensure the content
    region boundaries are known.
    """

    priority = 200
    dependency = ValidateSingleMessageAttributes
    consequence = RemoveMatch

    def when(self, matches, context):
        text_ms = matches.markers.named("message_text_marker")
        attr_ms = matches.markers.named("message_attributes_marker")

        if len(text_ms) != 1 or len(attr_ms) != 1:
            return False

        region_start = text_ms[0].end
        region_end = attr_ms[0].start

        to_remove = []
        for m in matches.named("marking_line"):
            if m.start < region_start or m.start >= region_end:
                to_remove.append(m)

        for m in matches.named("content_footer_marker"):
            if m.start < region_start or m.start >= region_end:
                to_remove.append(m)

        return to_remove if to_remove else False
