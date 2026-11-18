# Contributing to CIS2HDL

Thanks for taking the time to look at this project. This document covers how to set up a
development environment, the standards the code follows, and what a change is expected to
demonstrate before it can be merged.

## Development setup

```bash
git clone https://github.com/echoingme/CIS2HDL_plugin_ver.git
cd CIS2HDL_plugin_ver
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

`pip install -e ".[dev]"` pulls in the runtime dependencies plus `pytest`, `pytest-cov`,
`ruff`, `mypy` and `pyinstaller`. A Cadence installation is **not** required for development
or testing — the converters and writers are exercised against file fixtures.

## Before opening a pull request

```bash
pytest -q                        # unit + integration + e2e
ruff check cis2hdl               # lint
mypy cis2hdl                     # strict typing on the package
```

The test suite must pass. Lint and typing are enforced on code you touch: the older modules
still carry findings, so `ruff check cis2hdl` is not yet clean repository-wide, but new code
and modified files should introduce none. If your change touches emitted file formats, also run:

```bash
cis2hdl verify --suite e2e --suite qa_package
```

## What a change is expected to include

| Change type | Expected evidence |
|---|---|
| Bug fix | A regression test that fails on the previous commit and passes after the fix |
| New parser or matcher rule | Unit tests plus at least one fixture-based integration test |
| Output-format change | A byte-level or structural comparison against the reference output, documented in the PR |
| New plugin | Plugin metadata test, hook behaviour test, and an entry in the relevant `pipeline.yaml` section |
| Behavioural default change | Explicit note in the PR description; default behaviour is treated as a compatibility contract |

Byte-equivalence with the validated baseline is a core invariant. Any change that alters
default output must say so explicitly and explain why the new output is correct.

## Coding standards

- Python 3.12+, `from __future__ import annotations` in new modules.
- Ruff with `E,F,W,I,N,UP,B,C4,SIM` enabled, line length 100 (see `pyproject.toml`).
- `mypy --strict` on `cis2hdl`. Public functions get type annotations; avoid bare `Any`.
- Docstrings for modules and public classes; inline comments explain *why*, not *what*.
- No new runtime dependency without a note in the PR describing what it replaces or enables.

## Adding a plugin

1. Implement the class in the appropriate `cis2hdl/plugins/<stage>/` module.
2. Declare a `PluginSpec` (name, stage, declared `writes_keys`, description).
3. Register the implementation so discovery picks it up.
4. Add hook-behaviour and metadata tests under `tests/unit/`.
5. Reference the plugin by name in `pipeline.yaml` (commented out if it should stay off by
   default) and document it in `docs/plugin-api.md`.

Plugins that handle a hook return `True`; plugins that decline return `False`/`None` so the
engine can fall back to its built-in implementation. Never partially mutate the shared
context and then return `False`.

## Commit messages

Short imperative subject line, then a body explaining the motivation and the verification
that was run. Reference the affected area (`parser`, `matcher`, `writer`, `plugins`, `docs`)
in the subject when it helps.

## Reporting issues

Please include: the input file type and the Capture/PST version that produced it, the command
line or profile used, the full diagnostic output, and — if possible — the smallest input that
reproduces the problem. Issues filed with a reproducing fixture are much faster to resolve.

## Documentation

Documents under `docs/` are part of the deliverable, not an afterthought. If a change makes a
documented behaviour wrong, update the document in the same pull request.

## License

By contributing you agree that your contribution is licensed under the [MIT License](LICENSE).
