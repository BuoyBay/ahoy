# Native Ahoy builder

`build_ahoy.bui` builds the Ahoy developer toolkit on a native Linux x86_64 or
ARM64 host. It uses ProcessKit argument arrays for compiler, package and C compiler
processes. It never invokes Python or a shell. `--compiler`, `--packager` and
`--cc` take executable names or absolute executable paths, with `BUOY`,
`BPM_PACKAGER` and `CC` as compatible defaults.

From the BuoyBay workspace root, bootstrap the driver using the ProcessKit archive:

```sh
mkdir -p local/ahoy-builder/packages local/ahoy-builder/bin
cp repos/ahoy/tools/build_ahoy.bui local/ahoy-builder/main.bui
cp repos/processkit/packages/processkit-0.1.0.buipkg local/ahoy-builder/packages/
(cd local/ahoy-builder && buoy main.bui --check --diagnostic-format json)
(cd local/ahoy-builder && buoy main.bui -o bin/build-ahoy)
./local/ahoy-builder/bin/build-ahoy --root "$PWD"
./dist/ahoy-native-client/ahoy --help
```

The workspace must contain the Ahoy, developer-tool support, ProcessKit, LSPKit,
EditorKit, LayoutKit and GUILintKit checkouts. Ahoy's native source is
`src/main.bui` and `src/buoydev/`; recipe compatibility helpers stay under
`tools/`. Package checkouts expose `manifest.json` and `modules/` at their roots.
An assembled source workspace with compatibility `tools/` and `libraries/` paths
is also accepted by `--root`. The driver requires the
installed Buoy Zip, Regex, Crypto and XML packages, a C11 compiler, `mktemp`,
`uname`, `file` and `sha256sum`. `BUOY_PACKAGES_DIR` selects the installed package
folder when it differs from the standard Linux install.

Each build privately compiles the current ProcessKit C bridge, seals a host-only
ProcessKit archive and fresh source dependencies, then checks the Ahoy entrypoint
for all six compiler targets. It emits the executable and all compiler-deployed
runtime/resource files in its own output directory. It does not overwrite a
multi-platform ProcessKit package with the host-only archive. `--check-only`
performs the same staging and six semantic checks without emitting a client.
`--output /absolute/path/to/ahoy` selects another isolated deployment directory.

The native driver supports Linux hosts only. Native Windows/macOS build paths
remain unported. The development checkout retains the old `build_buoy_dev.py`
locally as a fallback; it is not required by this public native bootstrap. A
cross-target semantic check is not a native ABI or runtime test for that platform.

Ahoy's ordinary test/localization/formatting/benchmark/diagnostic/task commands
remain native. Recipe `build`, `check` and `clean` still use the legacy Python
planning/locking helper, and explicitly configured Python tasks need Python.
The native builder preserves the immutable `buoy-build/versions/<sha256>` helper
layout, atomically selects its current snapshot and copies its existing launcher;
it does not execute that helper while building Ahoy. Porting the recipe engine
is separate work.

After building, run the client's `--help` and exercise the commands you use with
your project's configuration. `BUOY_DEV_BINARY` selects a prebuilt client for
compatibility launchers.
