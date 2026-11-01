# Localization catalog workflow

This is a working catalog-to-Buoy example. Translation editing happens in the
catalog, a PO editor or an XLIFF editor; `Messages.bui` is generated and must not be edited.

```sh
./dist/buoy-dev l10n generate examples/localization/catalog.json --output examples/localization/Messages.bui
./dist/buoy-dev l10n status examples/localization/catalog.json
./dist/buoy-dev l10n export-po examples/localization/catalog.json --language fr --output dist/fr.po
# Edit dist/fr.po in a gettext-compatible editor, then import:
./dist/buoy-dev l10n import-po examples/localization/catalog.json --language fr --input dist/fr.po
./dist/buoy-dev task localize
./dist/buoy-dev test --filter localization --json dist/localization-demo.json
```

The runner builds the demo in an isolated project, checks exact translations and
fallback, and captures its French greeting and Spanish Save caption in the JSON
report. Explicit UI language tags are separate from regional formatting. Rebuild
after translation changes; this tool does not patch an existing executable.

## Catalog contract

Schema 1 contains `source_language`, an ordered `languages` array, and `messages`.
Each message has a stable Buoy identifier `id`, `default` text, optional `notes`,
optional `locations` (an array of source-reference strings), and `translations`.
Each translation contains `text`, a `source` snapshot, and
`state` (`translated` or `needs-review`). Unknown fields, duplicate keys, case
collisions and unsupported controls reject the catalog.

Keep the ID when English wording changes. Existing translations become stale
when their source snapshot differs. Generation includes only current, approved
translations; missing/stale/unreviewed entries fall back through Buoy's normal
resolution. `status` exits 1 if any target-language translation needs attention.
Intentionally empty translations are valid and distinct from missing entries.

The `languages` order matters: Buoy uses the first declared same-language tag
when no exact match exists. Generation preserves that order and emits the source
language first, so a regional variant cannot accidentally intercept the base
source language. Reordering language branches is a behavior change.

Messages must be literal strings. Add message IDs to the catalog explicitly or
use the bounded source extractor below, then reference those declarations in your
UI. The compiler validates identifiers and
every declared language tag, including languages with no populated translations.
Script/variant tags such as `zh-Hans` are unsupported by the current compiler.

## Extract existing declarations

```sh
./dist/buoy-dev l10n extract path/to/Strings.bui --source-language en --output dist/extracted.json
```

Extraction reads explicitly declared, module-level `Localization` blocks with
literal defaults and literal language branches. It preserves stable IDs,
adjacent `'''` translator comments and absolute source locations. It does not
find arbitrary UI strings, evaluate constant expressions or rewrite source.
Escapes are restricted to `\\`, `\"`, `\n`, `\r` and `\t`; other spellings
reject rather than assuming JSON and Buoy decode them identically.
Existing output is refused unless `--force` is supplied. Both input and generated
declarations pass real compiler checks; use repeated `--target` for other targets.
Checks require a writable source directory for temporary sibling files.

Conditional source is rejected until a target-aware source model is available.
Duplicate IDs, differing source-language fallbacks and incompatible regional
branch order are rejected rather than changing lookup behavior. Language order
uses first appearance across inputs, so the conservative ordering check can
require separate catalogs even where a different global order would work.
Review the extracted catalog and replace handwritten declarations deliberately;
do not import both the original and generated declarations into one program.
Files are limited to 2 MiB and 200,000 lexical tokens each.

## PO interchange

`msgctxt` carries the stable ID and `msgid` carries current source wording.
Imports require the complete current message set, matching source strings and a
matching `Language`/UTF-8 header. Unknown, duplicate, stale, partial, obsolete and
plural entries reject the import before it writes the catalog. Entries marked
`fuzzy` remain `needs-review`. Review them and clear that flag to approve.

An empty `msgstr` means untranslated and leaves the existing translation alone.
For an intentional empty translation, add `#, buoy-empty`; export retains this
flag. Deletion is an explicit catalog edit. PO support is a documented singular
subset with context, comments, flags, quoted strings and quoted continuations;
plural forms and legacy non-JSON string escapes reject. Runtime gettext and
`.mo` files are not used. Verify an editor round trip before adopting it for a
project, especially preservation of custom flags.

## XLIFF interchange

```sh
./dist/buoy-dev l10n export-xliff examples/localization/catalog.json --language fr --output dist/fr.xlf
# Edit targets in an XLIFF editor, then import:
./dist/buoy-dev l10n import-xliff examples/localization/catalog.json --language fr --input dist/fr.xlf
```

The native exchange profile exports [XLIFF 2.1 core](https://docs.oasis-open.org/xliff/xliff-core/v2.1/os/xliff-core-v2.1-os.html)
and imports 2.0/2.1: one file, one literal segment per stable unit ID, up to
10,000 messages. Source/target text preserves whitespace, Unicode, CR and LF.
Notes include translator comments and optional source references. Imported notes
do not replace catalog notes. A present empty target is an intentional empty
translation; an absent target in an `initial` segment leaves the existing
translation alone. A translated segment must contain a target.

Current approved entries export as `final`; stale/unreviewed entries export as
`initial`. Imported `initial` targets remain `needs-review`; `translated`,
`reviewed` and `final` approve the target against the current source. Imports
require every current ID, matching source text and document languages. DTDs,
entities, inline codes, groups, multiple segments, unknown extensions and partial
files reject the import. Input must be UTF-8 XML 1.0; other encoding/version
declarations reject explicitly. This is a bounded interchange profile, not a general
XLIFF implementation. Verify an editor round trip before adopting it. Rejected
imports leave the catalog unchanged; accepted imports compiler-check generated
declarations before committing readable JSON.

Catalog replacements preserve existing read/write/execute permission bits and
refuse files with no write bits set. They do not preserve every filesystem
metadata feature such as ACLs. This applies to both PO and XLIFF imports.

## CI and layout checks

```sh
./dist/buoy-dev l10n generate examples/localization/catalog.json --output examples/localization/Messages.bui --check
./dist/buoy-dev l10n generate examples/localization/catalog.json --output examples/localization/Messages.bui --check --target arm64-darwin --target x86_64-windows
./dist/buoy-dev l10n pseudo examples/localization/catalog.json --language de --output dist/PseudoMessages.bui
```

`--check` detects generated-source drift without writing and exits 2 on drift.
Both import commands write the catalog with two-space JSON indentation to keep translation
changes reviewable. `pseudo` adds accented,
expanded, bracketed text in the output only, leaving the catalog untouched. Use
that generated module in a separate app build and select the requested language
to inspect text fit. Do not import both generated modules into one application.
Pseudolocalization does not validate bidirectional rendering or translation
quality. This schema-1 workflow covers singular compiled declarations. LocaleKit's
separate schema-2 catalog companion supports
plural catalogs; parameterized messages and Xojo imports remain separate work.

Test suites and fixtures are maintainer-local and are not part of this public repository.
