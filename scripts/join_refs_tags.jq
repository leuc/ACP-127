# Stream-join all-mrns.ndjson against the all-tags.index.json map built by
# build_tags_index.jq, producing the single-file input used by
# cable-insights reftel2graph.py.
#
#   run: jq -c --slurpfile idx results/all-tags.index.json -f scripts/join_refs_tags.jq results/all-mrns.ndjson > results/all-mrns-tags.ndjson
$idx[0] as $tags
| {document_number, date, extracted_references, message_preview, tags: $tags[.document_number]}