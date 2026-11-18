# Migrating from CLI flags to `pipeline.yaml`

Version 0.5.0 moved every behavioural switch out of the command line and into
configuration. Three path-level flags survive — `--output`, `--hdl-lib`,
`--extra-hdl-lib` — because they describe *this invocation*, not *how to convert*.

Passing a removed flag now fails immediately with a message naming the configuration field
that replaced it:

```
$ cis2hdl convert board.DSN --aesthetic
error: --aesthetic 已移除: ... 请用 --profile 或修改 pipeline.yaml 配置
```

## Flag → configuration field

| Removed flag | Replacement |
|---|---|
| `--routing p0\|detour\|edif_reuse` | `beautify.params.routing.mode` |
| `--aesthetic` | `--profile max-beauty` (enables text layout, overlap check, power-IC rules, detour routing, off-page edge layout, GND distribution, IOPORT audit) |
| `--wire-simplify` | `beautify.params.wire_simplify.enabled: true` |
| `--text-layout` | `beautify.params.text_layout.enabled: true` |
| `--gnd-distribute` | `beautify.params.gnd_distribution.enabled: true` (+ `.distribute_density`) |
| `--rotate-passives` | `beautify.params.placement.rotate_passives: true` |
| `--use-net-name` | `beautify.params.ioport.use_net_name: true` |
| `--ioport-edge` | `beautify.params.ioport.edge_layout: true` |
| `--ioport-audit` | `beautify.params.ioport.audit: true` |
| `--cross-page-opt` | `beautify.params.routing.cross_page_opt: true` |
| `--nonuniform-tracks` | `beautify.params.routing.nonuniform_tracks: true` |
| `--net-order short_first\|long_first` | `beautify.params.routing.net_order` |
| `--no-mirror-normalize` | `beautify.params.mirror.normalize: false` |
| `--no-report` | `beautify.params.report.always_write: false` |
| `--chip-config <file>` | `match.manual_overrides.file` |
| `--manual-matches <file>` | `match.manual_overrides.file` (former alias) |
| `--export-unmatched <file>` | `match.manual_overrides.export_unmatched` |
| `--power-ic` | `beautify.params.power_ic.enabled: true` |
| `--max-workers <n>` | `engine.max_workers` |
| `--benchmark` | `engine.benchmark: true` |

Retained path flags:

| Flag | Field it overrides |
|---|---|
| `--output <dir>` | `engine.output_dir` |
| `--hdl-lib <dir>` | `input.hdl_lib` |
| `--extra-hdl-lib <dir>` | appended to `input.extra_hdl_libs` |

## Precedence

```
pipeline.yaml  →  --profile <name>  →  --output / --hdl-lib / --extra-hdl-lib
```

A profile is a partial `PipelineConfig`; fields it does not mention keep the `pipeline.yaml`
value. Path flags always win, because they are per-run decisions.

## Before and after

```bash
# 0.5.0 and later
cis2hdl convert board.DSN --profile max-beauty --output out/

# equivalent flags under 0.3.x
cis2hdl convert board.DSN --output out/ --routing detour --aesthetic \
    --wire-simplify --gnd-distribute --ioport-edge --ioport-audit
```

To make a one-off configuration permanent, create a profile from the current configuration,
edit it, then select it by name:

```bash
cis2hdl profile create my-board --from-file pipeline.yaml
cis2hdl profile show my-board
cis2hdl convert board.DSN --profile my-board
```
