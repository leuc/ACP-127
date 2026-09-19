# Build a single document_number -> tags index object from all-tags.ndjson.
# Output is ONE JSON object (the merged map), so downstream --slurpfile sees a
# single-entity array and reads it via $idx[0].
#
#   run: jq -n -f scripts/build_tags_index.jq results/all-tags.ndjson > results/all-tags.index.json
[inputs | {(.document_number): .tags}] | add