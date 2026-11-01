# Ahoy developer toolkit

The native [src/main.bui](../main.bui) executable provides the shared
test runner, localization tools, formatting, benchmarks, toolchain diagnostics,
configured tasks and source documentation. Commands execute in Buoy and use ProcessKit argument
arrays with separate stdout/stderr. They do not start Python or a shell.
Set `BUOY` to an executable path to override the installed compiler.

Build the Linux host with the [native Buoy builder](../../tools/NATIVE_BUILD.md). It
privately rebuilds ProcessKit, seals current source dependencies, checks all six
compiler targets and emits the isolated `dist/ahoy-native-client/ahoy` deployment.
The builder never invokes Python. Keep its compiler-deployed libraries and
Resources directory beside the executable.

The development checkout keeps `tools/build_buoy_dev.py` locally as a fallback;
native Windows/macOS build paths remain unported. Recipe builds and explicit Python tasks
still require Python; the native builder preserves the existing immutable recipe
helper deployment. `BUOY_DEV_BINARY` selects a prebuilt client for compatibility
launchers and tests.

## Start here

Native UI checks are available through `ahoy gui-lint SOURCE.bui`.
See [GUILintKit](https://github.com/BuoyBay/guilintkit/blob/main/README.md) for extensible rules,
platform profiles, source-matched preview evidence and shared designer snapping.

```sh
./dist/ahoy task build-testkit
./dist/ahoy doctor
./dist/ahoy task test
./dist/ahoy task localize
./dist/ahoy task test-tools
./dist/ahoy task workspace-audit-list
./dist/ahoy task docs-testkit
```

`task workspace-audit-list` lists the curated offline workspace suites, separate
from the seven suites registered for `test`. Run `task workspace-audit` to execute
that offline inventory and write `dist/workspace-audit.json`. These configured
tasks require Python; each audit suite has a 180-second timeout and the full task
has a 4,500-second limit. See the audit guide
for component selection and the native Buoy port.

The shared [buoy.dev.json](https://github.com/BuoyBay/devtools/blob/main/buoy.dev.json) is rooted at its own directory,
so `--config /path/to/buoy.dev.json` also works from another working directory.
Configured tasks use literal argument arrays. `{ahoy}` (or the compatibility
placeholder `{buoy-dev}`) resolves to this
executable. `{python}` resolves via `BUOY_DEV_PYTHON` or PATH for tasks that
explicitly need Python. They do not invoke a shell. Task output is bounded; a timeout
or nonzero exit fails the command. Configurations contain executable commands
and must be trusted.
For `task` and `bench`, an empty `BUOY_DEV_PYTHON` uses the normal `python3`,
then `python` search. An explicit interpreter is resolved from the invocation
directory before the task changes to its configuration directory.

`doctor` prints JSON with the compiler path/version, host tools and configured
package manifests. It reports missing inputs and the known Linux wrapper's
separate packager path. It does not install anything, verify native ABI slices,
or prove that cross-built programs run on another OS.

## Declarative builds

```sh
./dist/ahoy build --list
./dist/ahoy build studio --plan --json dist/studio-plan.json
./dist/ahoy build diffkit processkit --explain --json dist/build.json
./dist/ahoy build studio
./dist/ahoy check studio --all-targets --json dist/check.json
./dist/ahoy clean studio
```

The versioned [buoy.build.json](https://github.com/BuoyBay/devtools/blob/main/buoy.build.json) contains the artifact graph.
The initial recipes cover plain developer packages, ProcessKit, TerminalKit,
FontKit, GitKit, and Studio; `devtools` groups the registered plain developer packages.
Studio's output is under `dist/build/studio/TARGET/release/`. The original Python
builders and their imported functions remain supported. Native/package-specific
workarounds stay in their adapters. BPM continues to own dependency acquisition;
build recipes do not run during package installation.

Build commands require Python 3.10+ and the `buoy-build/` helper directory shipped
beside the native executable. The bootstrap deploys it automatically. Keep that
directory when distributing the CLI for build use. `BUOY_DEV_PYTHON` selects the
interpreter; `BUOY_DEV_BUILD_HELPER` overrides the helper script for development.
The native executor supervises each action through ProcessKit, with separate
bounded logs, timeout and cancellation. POSIX supervision covers the owned process
group; a process that deliberately creates another session can escape. Adapters
must not daemonize. Windows uses an owned job object. This is process supervision,
not a security sandbox. The shared Python planner and actions contain build policy.
Helper deployment publishes immutable, content-addressed snapshots, atomically
selects a current version, and disables bytecode writes. Running plans keep their
snapshot. Older versions are retained so deployment cannot invalidate active jobs.

`--config FILE` resolves project paths relative to the build configuration, so it
works from other directories. `--list` lists names. `--plan` validates and prints
the selected dependency order without running build actions or creating a lock.
`--explain` prints rebuild reasons to stderr during execution. Plans and final
reports are JSON on stdout; action logs go to stderr. `--json FILE` also saves the
JSON atomically after a plan has validated the destination. Invalid planning emits
JSON on stdout with `phase: planning`, `status: invalid`, and `complete: false`;
it preserves the requested report file because its path may itself be invalid.
Planner timeout/cancellation also emits an incomplete planning result. CLI syntax
errors use stderr. Reports distinguish `passed`, `checked`, `failed`, `timeout`,
`cancelled`, `error`, `locked` and `not_run`; a completed report can contain failures.

Execution is serial and always rebuilds. There is no incremental cache yet.
Package actions seal and check an isolated copy of their modules/resources and
the declared repository dependency closure, then atomically replace completed
archives. The compiler can additionally discover installed packages; this does
not provide compiler-level hermeticity.
They check all six semantic targets on build. `check` checks the selected target,
or all six with `--all-targets`, using temporary seals without publishing them.
Its dependency archives must already exist and match current source; stale module,
resource or manifest inputs fail preflight. Run build first after dependency
changes. Opaque command adapters remain responsible for undeclared inputs and
artifact freshness. Legacy adapters may always check six targets and retain their own
publication behavior. A semantic check is separate from native runtime testing.

Only the `release` profile is currently registered. `--target TRIPLE` selects one
target; native command adapters default to host-only support and reject other
targets before execution. Cross-target semantic checks on plain packages do not
promise native slices. `--compiler EXECUTABLE` and `--packager EXECUTABLE` override
toolchain selection; `BUOY` and `BPM_PACKAGER` remain supported. `--deadline N`
bounds planning, lock acquisition and execution (default 4500 seconds);
`--cancel-file PATH` cooperatively stops work and kills the owned process group/job.
Exit codes are 0 success, 1 action
failure/timeout, 2 invalid configuration/preflight, and 3 cancellation.

Successful builds record content and directory membership in `.buoy/build/receipts/`.
Separate ownership records in `.buoy/build/owners/` survive failed actions, so a
normal failure can be retried or its owned partial output cleaned. A no-op cannot
claim an existing unowned file. Clean retains shared `packages/` archives and
removes their verified disposable mirrors under `dist/`. It refuses tracked
files, changed contents and added directories. Cleaning a group expands its
members; an ordinary recipe does not implicitly clean its dependencies. Output
producers are unique across the configuration and declared target/profile modes,
including recipes selected in separate invocations. Plain package receipts use
a target-independent artifact identity. Receipt keys include the output paths,
so renaming an output or bumping a package version preserves the old artifact
without preventing the new build. Old artifacts require explicit retirement.

Shared package publication stages every mirror before replacing any and rolls
back earlier replacements on ordinary errors. Each replacement is atomic;
multiple mirrors are not one atomic snapshot or a power-loss transaction.
ProcessKit, TerminalKit and ChatGPTAuth receipts bind native source/header and
module contents, builder source, binary, compiler executable, command arguments
and selected SDK/compiler environment. They do not fingerprint all system SDK
contents. Only matching native slices are sealed. Studio's registered adapter
requires the explicit package graph, including ModelKit and ChatGPTAuth, and
stages those archives without resealing live libraries or discovering optional
project packages. Compiler-bundled libraries still come from the toolchain.

Cooperating writers hold an OS advisory/byte-range lock in `.buoy/build.lock`.
The compatibility marker `.buoy/build-writer/owner.json` records PID, host and time.
Kernel locks release on process death; the next holder can reclaim a stale
protocol-2 marker. Older or unknown directory claims still require inspection
before manual removal. Hard signals can omit the final report and interrupt
failure bookkeeping; they are not equivalent to cooperative cancellation. Direct
legacy scripts do not participate in this lock. Report paths under `.buoy/` or
overlapping declared inputs/outputs are rejected.

### Recipe schema

The root has `schema: 1`, `recipes`, and optional `compiler`/`packager` paths.
Recipe names are lowercase identifiers. Every recipe may have `needs`, `inputs`
(project-relative file globs), `targets`, `profiles`, and a positive finite
`timeout` of at most 86400 seconds. Missing inputs, linked paths, dependency cycles,
unknown fields, output conflicts and unsupported targets/profiles fail preflight.

- `package`: `path` selects a package directory. Inputs must include its manifest
  and every modules/resources file. Identity/version and archive destinations
  come from the manifest. `bundled_packages` explicitly names required compiler
  packages, resolved through `BUOY_PACKAGES_DIR` and known toolchain locations.
  `checks` may explicitly select module entry points for
  partial-class packages; every selected file must be staged. Text `.tbd` system-linker stubs must be declared as inputs and are preserved;
  compiled native libraries require a command adapter. Root metadata/build directories are not copied.
- `command`: `argv` is a literal argument array, with optional `check_argv`.
  `check_all_targets: true` declares that the check adapter covers all six targets.
  `outputs` names owned paths under `dist/` or `packages/`. An adapter that succeeds
  without creating its outputs fails verification. Adapters retain responsibility
  for their internal staging and atomic publication.
- `group`: `needs` selects other recipes; a group has no command or outputs.

Arguments/output paths support `{python}`, `{root}`, `{target}`, `{profile}`,
`{application-suffix}` (`.app`, `.exe` or empty), and resolved `{compiler}` and
`{packager}` when toolchain selection is configured. `{{` and `}}` escape literal
braces. Inserted values are not interpreted again. No shell interprets arguments.
Package identity stays in `manifest.json`; recipe `needs` currently supplies local
build ordering. The first release does not resolve or install BPM dependencies.
Update recipes when changing a package's local dependency requirements.

Maintainers run the private validation suite before release. See the repository README for public build instructions.

## Shared tests

```sh
./dist/ahoy test --list
./dist/ahoy test --filter '*kit' --json dist/tests.json --junit dist/tests.xml
./dist/ahoy test --check-only --target arm64-darwin --target x86_64-windows
```

The shared configuration registers the localization demo, TestKit, its async demo
and scheduler probe, BuildKit, DiffKit and LSPKit.
Each suite declares a `name`, entry `source`, `files` globs, `packages` globs,
optional `args`, `timeout`, and `protocol` (`exit` or `testkit`). Missing glob
matches, duplicate package filenames and paths leaving the project are errors.
Add imports, fixtures and resources explicitly to `files`; stage package
archives through `packages`. Files retain their project-relative paths.

Every suite gets a new temporary project and working directory. It sees only
staged project inputs and the installed toolchain, rather than the repository's
ambient `packages/`. This is build isolation, not a security sandbox: test code
can still access the host. The compiler, build and executable each have a
deadline. Tests inherit the environment, with temporary-directory variables
pointing at their suite directory. Callers control live-service credentials.

One suite file is one process. Legacy `exit` tests use their exit status.
TestKit cases additionally require exactly one complete schema-1 record, unique
case names, known outcomes and an exit status consistent with their results.
Compiler diagnostics preserve `errors` and advisory `warnings`. `checked` is
reported as skipped in JUnit, so cross-target checks cannot masquerade as runtime
passes. `--target` requires `--check-only`; normal runs build for the host.

The report distinguishes `passed`, `checked`, `failed`, `compile_error`, `crash`,
`timeout`, `protocol_error`, and runner `error`. Case outcomes are `passed`,
`failed`, `error`, and `skipped`. Reports have `schema: 1`, `complete`, and
`suites`; suites include phase logs, diagnostic objects and optional case results.
Each stream retains at most `log_limit` bytes while continuing to drain pipes.
Truncation is recorded; losing a TestKit result fails protocol validation.

ProcessKit starts owned child trees: a new POSIX session/process group or a
Windows job object assigned before the suspended child starts. Deadlines cover
the child and its pipes; cleanup kills descendants even after the direct child
exits. Temporary-tree cleanup unlinks symlinks without traversing their targets.
Inputs reject symlinks/reparse points. Atomic output replacement happens on the
destination volume after syncing the completed temporary file. Input JSON rejects
duplicate decoded keys, NUL and invalid surrogate escapes before stdlib parsing.
Captured logs replace NUL with U+FFFD to avoid Buoy's NUL-terminated string
truncation; invalid UTF-8 is also replaced. Logs still drain after reaching the
retention cap (`log_limit`: 1..67108864 bytes per stream).

Runtime verification covers Linux x64, macOS arm64 and Windows x64. Intel macOS
is build-checked only. Native runner, selection/repeat/cancellation and reference
parity evidence is recorded with exact source snapshots in
`dist/xojounit-macos-validation/results.md` and
`dist/xojounit-windows-validation/results.md`; latest ProcessKit pipe/sync checks
are in `dist/xojounit-processkit-final/results.md`.

The existing `tests/run_devtools_tests.py` now uses this execution engine for
ordinary sealed consumers and examples, retaining its six-target checks.
Specialized live/native harnesses keep their existing setup adapters.

## Testing extension contract

The XojoUnit follow-up uses the following shared contract for TestKit, native
runner, Python reference and Studio. Existing commands and schema-1 readers
remain supported.

```sh
./dist/ahoy test --suite testkit --case '*assert*' --json dist/selected.json
./dist/ahoy test --rerun-failed dist/test-results.json --json dist/rerun.json
./dist/ahoy test --suite testkit --repeat 20 --until-failure --deadline 120
./dist/ahoy task test-testing-extensions
./dist/ahoy task probe-testkit-native
```

- `--filter GLOB` retains suite filtering. New repeatable `--suite PATTERN` and
  `--exclude-suite PATTERN` intersect/subtract from it. Repeatable `--case PATTERN`
  and `--exclude-case PATTERN` operate on case names. New patterns are case
  sensitive, with only `*` and `?` special (brackets and dots are literal).
- `--rerun-failed REPORT` selects exact failed/error case names from a complete
  schema-1 runner report. Infrastructure failures and failures with no failing
  cases select the whole configured suite. Repeated report entries are combined,
  with whole-suite selection taking precedence. `--selection FILE` accepts
  `{ "version": 1, "suites": [{ "name": "configured suite", "cases": ["exact name"] }] }`;
  `cases: null` means the whole suite. These two options are mutually exclusive.
  Prior report `not_run` suites are also selected whole, so interrupted runs can
  resume unfinished work.
  Other filters intersect with either selection. Stale suite/case names are
  reported in `selection.unmatched` as `{ "suite": "configured name",
  "cases": null }` for a missing suite selected whole, or with an array of
  missing exact case names, and fail with exit 2. An empty selected run
  also exits 2. Case filters on exit-protocol suites are rejected explicitly.
- The runner writes a per-process selection file and passes its absolute path in
  `BUOY_TESTKIT_SELECTION`. It contains `{ "version": 1, "suite": "runtime suite",
  "include": [], "exclude": [], "exact": null }`. Empty includes mean all;
  exact arrays constrain names literally. The runtime name defaults to the
  configured name, overridable with `testkit_suite` in the suite configuration.
  Only the TestSuite with that runtime name applies the file, protecting nested
  helper suites. With no selection the runner overrides the variable to empty.
- Selected TestKit reports acknowledge `selection: { version: 1, applied: true,
  selected: N, discovered: N, unmatched: ["missing exact name"] }`. Missing or
  invalid acknowledgement is a protocol error. Cases have `selected: Boolean`;
  excluded cases remain `skipped`, message `not selected`, duration 0. The legacy
  constructor substring filter intersects with runner selection. No new statuses.
- Case `duration` is finite nonnegative seconds measured with the monotonic
  clock, including setup and cleanup. Older producers may omit it. Suite duration
  measures the run phase. JUnit exports fixed decimal `time` values.
- `--repeat N` is bounded to 1..1000; `--until-failure` requires N > 1 and stops
  after the first failing suite. Every iteration gets fresh processes, workspaces
  and builds. `--deadline SECONDS` caps the whole command across phases (default
  300 for repeated runs; otherwise no overall deadline). Deadline exhaustion is
  a timeout/failing run, never a successful early stop.
- Reports keep unique top-level `suites`: for each configured suite, its first
  failing record, otherwise its latest record. Ordered evidence is also in
  `iterations: [{ index: 1, duration: SECONDS, suites: [...] }]` and
  `repeat: { requested: N, completed: N, until_failure: Boolean,
  stop_reason: "count" | "failure" | "deadline" | "cancelled" | "selection" }`.
  Any failed iteration means exit 1. JUnit exports the representative suites.
  `selection` indicates an empty or stale selection stopped repetition with exit 2.
- `--cancel-file PATH` is checked between suites and during process supervision.
  Cancellation kills owned child trees, cleans temporary workspaces, finalizes
  the runner report with `cancelled: true` and `not_run: ["suite"]`, and exits 3.
  An interrupted active suite is `error` with `cancelled: true`; no fake TestKit
  completion record is created. Exit 0/1/2 retain success/failure/usage meanings.
  Export also observes cancellation/deadline checks. Interrupted export finalizes
  JSON evidence and may omit JUnit; use unique output paths and honor the exit code.
  Preflight usage errors preserve existing output files and execute no suites.
- Studio invokes native ahoy with explicit argv, unique result/cancel paths
  and one active job. It reads final JSON after process exit, supports Run All,
  exact Run Selected and Rerun Failed, and requests cooperative cancellation
  before a bounded hard-kill fallback. It distinguishes failure from unavailable
  results, cancelled runs and filtered/skipped cases; it does not claim live
  case progress. Old results are not merged into a new run.

TestKit's nonblocking `RunAsync` returns a completion token; callers invoke
`PollAsync` from their existing loop or timer. It never pumps a GUI loop or
assumes `Async/Await` suspends. Executed Linux probes establish console callback
queue delivery and desktop native timer delivery, while observing no native
timer delivery under console pumping. See [TestKit](https://github.com/BuoyBay/testkit/blob/main/README.md)
for lifecycle rules and examples. The desktop timer probe also passes natively
on macOS arm64 and Windows x64.

## Localization

See the [catalog example and workflow](../../examples/localization/README.md).
Commands provide catalog validation, translation status, deterministic `.bui`
generation, PO import/export and pseudolocalization. Generation and import run
the real compiler before changing the destination.

## Formatting

```sh
./dist/ahoy format path/to/source.bui
./dist/ahoy format path/to/source.bui --check
./dist/ahoy format path/to/source.bui --write --target x86_64-linux --target arm64-darwin
```

The installed `buoy-lsp` performs formatting. Override it with `BUOY_LSP` or
`--server PATH`; `--indent` defaults to 4 and `--timeout` to 30 seconds per file.
The client negotiates formatting support and UTF-16 coordinates in a temporary
empty workspace, then opens the requested document. It does not load the full
project into the server. Compiler checks still resolve imports beside the source.

Without flags, one formatted file goes to stdout. `--check` accepts multiple
files and exits 1 on drift. `--write` prepares and compiler-checks every candidate,
rejects stale inputs, then replaces changed files atomically one at a time. An
I/O failure during a multi-file commit can leave earlier files formatted.
Tokens, comments and interior line boundaries must remain identical; unsafe or
unsupported formatter changes fail without writing. This conservative guard can
reject harmless server changes such as keyword recasing. Source is limited to
2 MiB and 200,000 tokens per file. Compiler validation creates a temporary sibling
file, so the source directory must be writable even for stdout and check modes.
Use repeated `--target` options to check conditional branches for other targets.

## Command benchmarks

```sh
./dist/ahoy bench localize --iterations 10 --warmup 1 --deadline 300 --json dist/localize-bench.json
```

Benchmarks execute a trusted configured task in its configuration directory,
with the same argument substitutions as `task`. Every warmup and measured sample
starts a fresh process. JSON retains exit codes, bounded logs, timeout evidence
and successful measured timings, with min/max/mean/median in seconds. Measurements
include startup, output draining and cleanup; they are process wall times, not
isolated function timings. Warmups and failed samples never enter the summary.
Execution stops on the first failure, timeout or overall deadline and exits 1;
invalid configuration or failure to save `--json` exits 2. The completed JSON
record is always written to stdout before saving the optional file, so a bad
report path can run the task but cannot discard its timing/failure evidence.
Defaults are ten measurements, one warmup and a
300-second total deadline. Tasks may modify files: choose the benchmark task
deliberately. The runner does not restore task side effects.

## Package source reference

```sh
./dist/ahoy docs libraries/testkit/modules/TestKit.bui --output dist/docs/testkit.md
```

This extracts adjacent `'''` comments and declaration lines into a Markdown
source reference. It does not infer exported visibility, resolve types, render
documentation sites or parse every grammar feature. It intentionally makes no
claim to be a semantic API index.

## Verification and next steps

The final audit record (private maintainer material) lists the three independent reviews,
resolved findings, verification scope and remaining platform work.
The [enhancement record](ENHANCEMENTS.md) describes the later source tools,
XLIFF and benchmark verification separately.

Maintainers run the private validation suite before release. See the repository README for public build instructions.

Maintainers run the private validation suite before release. See the repository README for public build instructions.

Maintainers run the private validation suite before release. See the repository README for public build instructions.

The [toolchain follow-ups](BUOY_REQUESTS.md) record the semantic source model,
language-selection, instrumentation and package-map work needed for later
milestones. Studio's Tests window consumes the shared result protocol; a dedicated
translation editor remains a later catalog view.

Windows report/configuration environment paths use wide Win32 APIs. Native consumer
builds discover the standard SDK runtime directory, pass its linker search path
and copy missing runtime DLLs beside the executable. These are local workarounds
for the recorded Buoy 0.72 distribution, not modifications to the installed compiler.

The public executable is now `ahoy`. Internal `buoy_dev` filenames and
`BUOY_DEV_*` environment variables remain compatible with existing integrations.
The separate script runner is published as `buoy-run`.
