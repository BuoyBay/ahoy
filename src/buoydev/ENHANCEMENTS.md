# Native source and interchange enhancements

## Delivered

- `format`: installed LSP formatting, capability/UTF-16 negotiation, bounded
  requests, token/comment/statement preservation, compiler checks and atomic
  individual writes. Supports stdout, drift checking and explicit target checks.
- `l10n extract`: literal `Localization` declarations, stable IDs, adjacent doc
  comments and optional source locations. Refuses conditional source, expressions
  and fallback-order changes; does not rewrite handwritten declarations.
- `l10n export-xliff` / `import-xliff`: a bounded XLIFF 2.0/2.1 core profile with
  stable IDs, source snapshots, whitespace preservation, intentional empty targets
  and explicit review states. Imports reject unsupported structures before commit.
- `bench`: trusted configured tasks, fresh processes, warmups, bounded logs and
  deadlines, failure evidence and successful sample summaries.
- Shared task argument expansion, PO source references, catalog metadata
  validation and bootstrap package staging.

Usage and limitations are in [the command guide](README.md) and
[the localization example](../../examples/localization/README.md).

## Remaining boundaries

There is no general compiler source-model API, arbitrary-expression extractor,
source rewriter or Xojo catalog importer in these commands. Native translation
editor panels, semantic API documentation/diffs and source coverage remain
separate work. LocaleKit's existing plural catalog companion is separate from
schema-1 compiled declarations. The full XLIFF standard is deliberately outside
the singular exchange profile.
