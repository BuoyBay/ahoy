# Contributing to ahoy

This repository owns **Ahoy**, the Buoy developer toolkit, under
`src/buoydev/` and its command/build entrypoints. Internal compatibility filenames and
`BUOY_DEV_*` variables remain compatible. The separate **buoy-run** repository
owns the script runner; keep command naming and responsibilities distinct.

## Development conventions

Use the installed Buoy language reference and verify changed `.bui` files with
the compiler. Prefer native Buoy/BuoyScript for new automation. Preserve public
command names, environment-variable contracts and explicit platform limitations.

## Build context

Read the [toolkit guide](src/buoydev/README.md). Build from the assembled
integration workspace, where ProcessKit and required compiler/package archives
are available; the standalone source checkout is not the full bootstrap context.
The native driver is [tools/build_ahoy.bui](tools/build_ahoy.bui):

```sh
mkdir -p dist/ahoy-native-builder
buoy tools/build_ahoy.bui -o dist/ahoy-native-builder/build-ahoy
./dist/ahoy-native-builder/build-ahoy --root "$PWD"
```

Run those commands from `local/integration/`. Keep driver/client runtime libraries
in separate output directories. Recipe execution is still being migrated; record
any required local helper or unsupported mode explicitly. A successful native
build does not establish recipe portability.

## Verification and pull requests

For each edited Buoy entrypoint, in its documented staged dependency context:

```sh
buoy path/to/entrypoint.bui --check --diagnostic-format json
```

Require exit status zero and an empty `errors` array. Read warnings. Check each
affected conditional platform branch with `--target`; compiler checks do not prove
native runtime behavior on another OS. Build/link and exercise the changed API or
workflow on its supported host as well.

Test suites, fixtures and detailed reports are private/ignored for now. Maintainers
run those suites before merge or publication; a fresh checkout is not expected to
contain them. Include your compiler/tool versions, host/target, exact build and
reproduction commands, expected behavior and observed output in the pull request.
Do not commit private tests, generated builds, caches, credentials or machine
configuration. Keep the patch focused and note any unverified platforms or runtime
prerequisites. Inventory checks alone are not build or test acceptance.

## License of contributions

Original contributions are accepted under the existing license for the files you
change: `MIT OR Apache-2.0` for first-party code and `CC-BY-4.0` for documentation
prose. Code samples follow their code's license. No CLA or DCO signing step is
required. Keep your own authorship and copyright attribution.

Read [LICENSE](LICENSE) and [LICENSING.md](LICENSING.md). Preserve upstream license,
copyright, attribution and provenance files for third-party material, and identify
its source in the pull request. Submit only material you have the right to license.
Reusable packages and tools keep their permissive licensing boundary; changes to
Studio's AGPL application code belong in its separate repository.
