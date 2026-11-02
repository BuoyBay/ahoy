# Toolchain follow-ups for developer tools

The shared runner, TestKit and catalog generator work with Buoy 0.72.0. The
following capabilities require upstream APIs or further platform work. These are
tracked locally; no upstream issue has been submitted.

## Compiler/LSP source model and formatter

Expose machine-readable declarations, literal localization values, comments,
conditional branches and exact source ranges. The installed buoy-lsp 0.2.0 probe
returns procedure symbols but omits a compiled `Localization` declaration.
Tools need capability/version negotiation and byte/UTF-16 coordinate rules.

The installed LSP advertises document formatting; the native `format` command now
uses it with capability negotiation, UTF-16 edit conversion, token/comment/line
preservation and compiler checks. The bounded `l10n extract` scanner handles
literal declarations, rejecting conditional source and unsafe fallback order.
Richer extraction still needs a semantic source model. The current highlighting
grammars are not semantic parsers. A new
tree-sitter grammar should be maintained against compiler fixtures rather than
used as an unverified source rewriter. See [the enhancement record](ENHANCEMENTS.md).

## UI language and translation semantics

Provide preferred UI languages and an application override independently of
formatting Locale. On this Linux host, a compiler-checked probe under
`LANG=fr_FR.UTF-8` returned a French bare Localization while
`Locale.Current().Identifier` returned `C`; `LANGUAGE`/`LC_MESSAGES` did not select
the expected translation. The independently reviewable Linux repro and current
evidence are recorded locally as
BUI-702.
The discrepancy concerns the documented lookup identifier; support for
`LANGUAGE`/`LC_MESSAGES` is a separate proposed enhancement. Add conformance tests
for each supported platform. No upstream publication is authorized by this record.

Document fallback order as part of the language contract. Add script/variant
tags and parameterized messages through explicit versioned APIs. LocaleKit now
supplies CLDR plural rules and a separate schema-2 catalog companion; schema 1
continues to generate singular compiled declarations.
Runtime catalogs and live language switching need a deliberate design; the
current generator uses compiled declarations and does not replace the runtime.

## Testing diagnostics and supervision

Add source locations and precise floating-point diagnostics to built-in Assert.
Document its actual current methods. Built-in assertions exit immediately;
TestKit supplies separate throwing checks for sequential case execution.

ProcessKit now implements opt-in POSIX group ownership and Windows jobs; the
native CLI uses those APIs. Linux tests cover parent exit, held pipes, descendants
and deadlines. macOS arm64 runs the native runner (18) and extension (21) suites;
the ProcessKit dylib builds warning-clean for arm64 and x86_64. Windows native
code cross-compiles; Windows runtime verification remains required. Rebuild each native slice before distribution.

## Dependency graph, coverage and release work

Implement the explicit compiler/LSP package map proposed in
[BPM's requests](https://github.com/BuoyBay/bpm/blob/main/src/BUOY_REQUESTS.md). Then tighten isolated resolution and
extend Ahoy/BPM Windows execution without POSIX shell dependencies.

Source coverage needs compiler instrumentation and source maps. Sampling
profiling can be evaluated independently; a lack of coverage counters does not
prevent every form of profiling or ordinary wall-clock benchmarking.

Studio translation panels, semantic API documentation, Xojo catalog import,
and package API diffs can build on the current protocols. Bounded XLIFF 2.1
exchange and process wall-time benchmarks are now native CLI commands. Signing,
notarization and installers remain app-specific release work. These later
milestones are not claimed as implemented by the command-line foundation.

## XojoUnit review (2026-10-31)

Cloned [xojo/XojoUnit](https://github.com/xojo/XojoUnit) with its Git history to
`local/XojoUnit`. Inspected master at
`c91ab8bcc46e1510313fa00b07b60999e4c10816` (2024-06-05, release 6.9.1).
This is a source review, not an executed Xojo test run. The checkout retains
`XojoUnitLicense.txt`; its MIT-style terms require preserving the copyright and
permission notice when copying code or substantial portions. No upstream code
was incorporated into Buoy during this review.

The relevant upstream sources are under `Shared Resources/XojoUnit/`:
`TestFramework/TestController.xojo_code`, `TestGroup.xojo_code`,
`TestResult.xojo_code`, `Assert.xojo_code`, `ObjectSpy.xojo_code`, and
`XojoUnitAPI2TestWindow.xojo_window`. Findings below were compared with
`libraries/testkit/modules/TestKit.bui`, `tools/buoydev/TestRunner.bui`, the Python
reference runner, and the Studio sources.

Recommended order of work:

1. **Case selection and failed-case reruns.** XojoUnit supports include/exclude
   wildcard patterns over group and method names, plus selecting failed tests in
   its desktop UI. Buoy's CLI currently filters suite names; TestKit separately
   supports a case-name substring supplied by its consumer. Add an explicit
   case-selection contract between runner and TestKit, with separate suite/case
   patterns, excludes, and reruns from a prior JSON report. Keep exact case names
   rather than adopting Xojo's optional `Test` suffix convention. Define empty
   selections and stale report names, and preserve infrastructure failures when
   choosing reruns.
2. **Case timing.** XojoUnit measures individual tests and exports JUnit `time`.
   Buoy retains process phase timings but TestKit cases have no elapsed duration,
   and its JUnit writer emits no time attributes. Add finite, nonnegative case
   durations in seconds, define whether fixtures are included, and propagate
   timing through both native and reference exporters. Use a monotonic clock;
   do not mistake compile time for case execution time.
3. **Bounded repeat-until-failure.** XojoUnit's desktop runner can loop until a
   failure. Add a CLI repeat limit and overall deadline, keeping each iteration's
   evidence and using fresh execution state. This is useful for flaky native
   control and process lifecycle checks. Decide explicitly whether builds are
   reused and how cancellation appears in the final report.
4. **More focused assertions.** XojoUnit has array, byte-buffer, regex,
   object-identity and nil checks beyond our small assertion surface. Prioritize
   array equality with the first differing index, byte comparisons with an
   offset, and readable string diffs using existing DiffKit. Keep TestKit's
   documented case-sensitive string and explicit floating tolerance semantics.
5. **Async cases and Studio UI.** XojoUnit's timer-driven `AsyncAwait`/
   `AsyncComplete` protocol provides per-case deadlines while allowing events
   to run. Buoy's synchronous TestKit cannot currently express that lifecycle;
   an outer process timeout is not equivalent. Design explicit completion,
   cleanup, late-callback and cancellation behavior before adding this feature.
   A Studio test tree can then consume the shared reports, show diagnostics and
   timings, and rerun selected/failed cases. Live progress would need a separate
   event protocol; today's final JSON record alone does not provide it.

Retain the existing fixtures, catchable failures, distinct error/skip outcomes,
structured exception diagnostics, process supervision, JSON validation and
JUnit export. These foundations already exist in Buoy. XojoUnit additionally
creates a fresh group instance per test; our callbacks do not automatically
reset captured/shared fixture state, so document or provide explicit fixture
factories if class-based suites are added.

Avoid a direct framework port: test discovery and ObjectSpy depend on Xojo's
Introspection and dynamic invocation. ObjectSpy is a reflective member accessor,
not a call-recording mock. Keep explicit delegates and interface-based test
doubles unless Buoy gains a deliberate reflection contract. Its XML exporter is
also not a template to copy: names and failure messages are concatenated with
incomplete attribute escaping. Preserve Buoy's XML escaping and protocol checks.
The list above records the original recommendations from the source review.

### Implementation pass

TestKit now provides scoped selection acknowledgement, selected/discovered
metadata, monotonic case timing, bounded string diagnostics, typed array and
byte comparisons, and explicit async completion tokens. Async callers retain
their own event loop and call `PollAsync`; the package never pumps a GUI loop.
The native runner and Python reference implement exact selections and failed
reruns, bounded repeat history with failure-preserving representative results,
overall deadlines, fixed-decimal JUnit timing and cooperative cancellation.
The [extension contract](README.md#testing-extension-contract) specifies flags,
schemas and failure behavior. No upstream source was copied.

The Astra and Opus implementation audits led to regression fixes for large-log
JUnit performance and XML control-character round trips, async callback
reentrancy/exception capture, eager runtime-suite alias validation, duplicate-key
and truncated-output protocol rejection, interrupted-run reruns, and preserving
executed results when some selected names go stale. POSIX ProcessKit ownership
now uses a supervisor and owner-liveness pipe so force-killing a suspended runner
also stops its active command and descendants. Native Linux runtime and strict
x86_64 Windows bridge compilation were verified; remaining native slices must be
rebuilt on their platforms before distribution.

Opus also inspected native screenshots and fixed the narrow-window filter and
column clipping. A toolchain follow-up remains: GTK derives a large minimum from
manually positioned children and does not honor a smaller Window.SetMinSize.
The Tests layout can fit 720×480 content, but the current Linux runtime prevents
shrinking the actual window that far. The screenshots are in
`dist/studio-testing-review/`; they distinguish actual standard-size captures
from the explicitly sized/cropped minimum-layout captures.

The final native Tests-window regression run covers ten scripted jobs, including
closing/reopening the window during a run and displaying executed failures from
a partially stale selection. On Linux the window hides on close and is disposed
only at Studio shutdown, avoiding the runtime's close-triggered main-loop exit.
All three GUI integration scenarios pass in the isolated testing Studio build
at `dist/BuoyStudio-testing/BuoyStudio`, with the current testing modules and
ProcessKit runtime. This build isolates the testing work from concurrent Studio
editor/debugger changes. The subsequent full Studio build also passed its
six-target compiler gate and all three testing-window scenarios on Linux;
the verified executable is `dist/BuoyStudio-final-testing/BuoyStudio`.
The full documentation-window test remains blocked on
this host's missing WebKitGTK runtime. On macOS arm64 the three testing-window
scenarios pass in a native Studio build, with window captures inspected
(`dist/xojounit-macos-validation/results.md`). Windows native validation followed
and is recorded below.

The final ProcessKit audit also verifies that polling retains the supervisor's
waitable identity until handle close and repeated tree termination is idempotent.
POSIX owned-tree spawning explicitly rejects SIGCHLD auto-reaping dispositions;
custom reapers must leave owned supervisors waitable until ProcessKit closes them.

Native follow-through on macOS arm64 and Windows x64 now passes the configured
suites, runner/extension regressions, real desktop Timer probe and all three
Studio testing scenarios. Evidence and source-version limitations are recorded
in `dist/xojounit-macos-validation/results.md` and
`dist/xojounit-windows-validation/results.md`. Opus's subsequent UI review found
no blocking issues; its Windows CRLF advisory was fixed by normalizing CRLF and
standalone CR before converting LF for TextArea. The native Windows contract now
checks mixed line endings and rejects doubled carriage returns. All three GUI
scenarios passed again (`logs/studio-crlf-final.result.json`), and the updated
window passed all six target compiler checks.

Astra's final scoped platform review found no blocking issues. The Windows
fake-runner shim now rejects oversized environment values before string access;
native boundary checks and ordinary argument forwarding pass. Latest ProcessKit
verification (`dist/xojounit-processkit-final/results.md`) confirms four current
native slices: both Mac architectures, Linux x64 and Windows x64. Pipe/sync tests
pass on macOS arm64, Linux x64 and Windows x64; Intel macOS is build-only because
Rosetta is absent. The shared archive already contains all four slices. Further
sealing belongs to the process-inspection team while it changes the Buoy modules;
this task did not package that team's unfinished work.

Follow-through adds an isolated Linux CI gate with unexpected-skip rejection,
glyph-raster coverage, and saved-input freshness regressions. Studio now tracks
suite-specific saved-input edits, additions and deletions with explicit coverage
limits. The five model regressions pass on Linux, macOS arm64 and Windows x64.
All three testing-window scenarios pass on each host with the final placement
fix: ownership and moved geometry survive hide/reopen, and the Windows lab frame
fits its work area. Final independent Opus review reports no blocking findings
and 18 clean compiler checks. Hosted CI provisioning, unsaved-editor hook wiring,
architecture gaps, and final shared packaging remain explicitly documented in
`design/testing-followups.md`; separate Windows designer acceptance steps are in
`design/testing-followups-windows.md`.
