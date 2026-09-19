# Flatten raw extractor NDJSON into reftel NDJSON.
# Input:  results/<year>.ndjson   (output of src.extractor)
# Output: results/<year>.reftel.ndjson
# draft_date/sent_date/dtg stay RAW here -- src.reftel_normalize reads them
# and resolves its own single date.
#
#   jq -Mc -f scripts/flatten_reftel.jq results/1973.ndjson > results/1973.reftel.ndjson
{
  references: ._reference,
  attr_reference: ."Message Attributes"."Reference",
  document_number: ."Message Attributes"."Document Number",
  draft_date: ."Message Attributes"."Draft Date",
  sent_date: ."Message Attributes"."Sent Date",
  dtg: ._dtg,
  message_preview: (._message_content | if . then split("\n")[:100] | join("\n") else null end)
}