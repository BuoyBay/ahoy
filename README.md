# CLI for diagnostics, format, lint

Ahoy runs project checks, formats source, generates documentation, manages
localization catalogs, measures benchmarks and lints native GUI layouts. Its
commands operate on your project and use the real Buoy compiler for diagnostics.

## Use

```sh
ahoy --help
ahoy doctor
ahoy format src/main.bui --check
ahoy docs src/main.bui --output docs/API.md
ahoy gui-lint src/MainWindow.bui --platform linux
```

Project tasks and test selections use `buoy.dev.json`. Recipe builds use
`buoy.build.json`; the [command guide](src/buoydev/README.md) documents arguments,
selection rules, exit codes, localization formats and configuration contracts.

## Build Ahoy

The [native build guide](tools/NATIVE_BUILD.md) gives the ProcessKit bootstrap and
source dependencies. With that driver built, run from your workspace-tools root:

```sh
./local/ahoy-builder/bin/build-ahoy --root "$PWD"
./dist/ahoy-native-client/ahoy --help
```

The native builder supports Linux x86_64 and ARM64. It rebuilds the host bridge,
stages package dependencies and checks all six compiler targets before linking.
Other-host native builders remain unported. Recipe `build`, `check` and `clean`
still need the documented compatibility helper; other ordinary commands are native.
Keep driver and client runtime libraries in their separate output directories.

`BUOY_DEV_*` variables and internal compatibility paths remain supported.
[buoy-run](https://github.com/BuoyBay/buoy-run) is the separate script runner.

## Local Buoy setup

On your own machine, install Buoy and run:

```sh
buoy ai init --both
```

[Contributing](CONTRIBUTING.md) · [License](LICENSE)
