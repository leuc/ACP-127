# Merge src/missing_mrn_estimate.py output (missing-mrn-dates.ndjson) onto
# all-mrns-tags.ndjson into one NDJSON with a date for as many nodes as
# possible. Streaming over the real rows; the small estimates file is loaded
# once via --slurpfile.
#
#   run: jq -n -c --slurpfile est results/missing-mrn-dates.ndjson -f scripts/merge_missing_mrn_dates.jq results/all-mrns-tags.ndjson > results/all-mrns-tags.estimated.ndjson
#
# For each real row, if its document_number matches an estimated MRN the
# estimate metadata is attached; unresolvable estimates (estimated_date null)
# are dropped. Every resolved estimate then also yields one citation-only row
# (extracted_references/message_preview/tags all null, since that document
# exists only as a citation) so a consumer can tell estimated rows from real
# ones via estimate_type/accuracy_days/date_order_inverted.
(($est | map(select(.estimated_date != null))) as $r
 | ($r | map({key:.mrn, value:.}) | from_entries) as $idx
 | (inputs
     | if ($idx[.document_number]) then
         . + {estimated_date:         $idx[.document_number].estimated_date,
              estimate_type:          $idx[.document_number].estimate_type,
              accuracy_days:          $idx[.document_number].accuracy_days,
              date_order_inverted:    $idx[.document_number].date_order_inverted}
       else . end),
   ($r[]
    | {document_number: .mrn, date: .estimated_date,
       extracted_references: null, message_preview: null, tags: null,
       estimate_type: .estimate_type, accuracy_days: .accuracy_days,
       date_order_inverted: .date_order_inverted})
)