"""Remove declassification marking lines and content footer markers.

These are EO Systematic Review markings added by the declassification process,
not part of the original ACP-127 telegram text. Removed without JSON output.
"""

from rebulk import Rule

from ..patterns.declass_markings import RemoveMatchesWithCoverage
from ..rules.validate import ValidateSingleMessageAttributes


class RemoveDeclassMarkings(Rule):
    """Remove marking_line + content_footer_marker outside the content region.

    Runs after ValidateSingleMessageAttributes to ensure the content
    region boundaries are known.
    """

    priority = 200
    dependency = ValidateSingleMessageAttributes
    consequence = RemoveMatchesWithCoverage()

    def when(self, matches, context):
        from ..patterns.locator import is_text_online

        text_ms = matches.markers.named("message_text_marker")
        attr_ms = matches.markers.named("message_attributes_marker")

        if len(text_ms) != 1 or len(attr_ms) != 1:
            # Ambiguous markers: body parsing is unsafe, so drop all
            # boilerplate matches rather than leaking them into JSON.
            return list(matches.named("marking_line")) + list(
                matches.named("content_footer_marker")
            ) or False

        region_start = text_ms[0].end
        region_end = attr_ms[0].start

        # When no retrievable body will be built (ambiguous markers are
        # already removed by validation; here: no scoped TEXT ON-LINE
        # Locator), in-region boilerplate has no BuildMessageContent to
        # hand it to -- remove it here so marking_line never leaks into
        # JSON output. Attribute extraction is unaffected (those are
        # attribute-tagged matches, not marking_line pattern matches).
        eligible = any(
            is_text_online(m.value) and m.start >= region_end
            for m in matches.named("Locator")
        )
        if not eligible:
            text = matches.input_string
            for m in matches.named("Locator"):
                if m.start < region_end:
                    continue
                line_end = text.find("\n", m.start)
                line = text[m.start : line_end if line_end >= 0 else len(text)]
                if is_text_online(line):
                    eligible = True
                    break

        to_remove = []
        for m in matches.named("marking_line"):
            if eligible and region_start <= m.start < region_end:
                continue
            to_remove.append(m)

        for m in matches.named("content_footer_marker"):
            if eligible and region_start <= m.start < region_end:
                continue
            to_remove.append(m)

        return to_remove if to_remove else False
