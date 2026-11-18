# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] — 2026-08-17

The plugin-architecture release: the converter becomes a composable pipeline whose stages,
parameters and output set are described by configuration rather than by command-line flags.

### Added

- **Plugin pipeline** (`cis2hdl/plugins/`): seven hook specifications (`load_input`,
  `match_components`, `apply_manual_overrides`, `beautify`, `write_output`, `write_report`,
  `run_verification`) driven by [pluggy](https://pluggy.readthedocs.io/), with 20 plugins
  across the input, match, beautify and test stages.
- **Explicit plugin contract**: each plugin declares a `PluginSpec` with its stage, a
  description and the context keys it writes; the shared `ConversionContext` rejects writes
  to undeclared keys.
- **Declarative configuration**: `pipeline.yaml` with `schema_version`, and `input` /
  `match` / `beautify` / `output` / `test` / `engine` sections. Configuration precedence is
  `pipeline.yaml` → `--profile` → path-level CLI flags.
- **Profiles**: built-in `default`, `fast`, `max-beauty` and `match-only` profiles, plus
  user profiles managed with `cis2hdl profile list | show | create | export | import`.
- **`cis2hdl verify`**: verification runner with selectable suites (`unit`, `e2e`,
  `qa_package`) and meaningful exit codes.
- **CLI front end** (`cis2hdl/cli.py`): `convert`, `verify`, `profile`, `gui` subcommands.
- **GUI controller layer** decoupled from PySide6, so pipeline control, schema inference and
  YAML round-tripping are testable headlessly.
- **Documentation**: plugin API reference, developer guide, GUI design record, and the
  configuration-layer / plugin-foundation design documents under `docs/`.

### Changed

- Package version unified: the runtime `__version__` and the distribution metadata are now a
  single source of truth (previously `0.5.0` at runtime versus `0.3.5` in metadata).
- Match weights, thresholds, prefix scopes and beautification parameters moved out of code
  into configuration; the defaults reproduce the previously validated behaviour.
- Removed the legacy behavioural CLI flags. Passing one now fails with a message pointing to
  the equivalent `pipeline.yaml` field — see [docs/cli-migration.md](docs/cli-migration.md).

### Fixed

- `requirements.txt` now includes `pluggy`, which the plugin manager imports at runtime.
- `.gitignore` no longer excludes `cis2hdl/plugins/output/`: the unanchored `output/` rule
  was matching the output-stage plugin package, so it never entered version control and the
  44 tests covering that stage failed.
- `pipeline.yaml` no longer points at documents that are not part of the repository.

## [0.3.5] — 2026-08-03

First packaged release, corresponding to the pre-plugin architecture.

### Added

- Binary DSN parser (OLE reader plus binary record reader) with coordinates, and OLB library
  parsing for 20/21 package types.
- Two-stage component matcher: type hypothesis → candidate pool → per-class resolution, with
  five-dimensional weighted scoring for active devices and rule-based resolution for passives.
- Cadence-compatible writers producing `.cpm`, `.csa`, `.con`, `.dcf`, `.xcon`, `cds.lib` and
  the accompanying `worklib` tree; projects open in Cadence SPB 16.6.
- Six-stage diagnostics with 44 error codes, and a `mapping.csv` export of matched and
  unmatched components.
- PySide6 GUI: schematic preview, diff view, batch conversion queue, mapping-rule editor,
  HTML report export, conversion history.
- PyInstaller packaging (`cis2hdl.spec`, `scripts/build_exe.py`) and a pytest suite with
  unit, integration and end-to-end layers.

### Notes

- Version `0.4.x` and `1.x` labels that appear in the internal development log refer to
  project phases, not to public package releases; they are not part of this changelog.

[0.5.0]: https://github.com/echoingme/CIS2HDL_plugin_ver/releases/tag/v0.5.0
