# Documentation

Technical documentation for CIS2HDL. Everything here describes *how the converter is built
and how to verify it*; usage lives in the top-level [README](../README.md).

| Document | What it answers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the system is put together: pipeline layers, backend design, device model, diagnostics, and the GUI design record. Start here. |
| [MATCHING.md](MATCHING.md) | How components are matched: the failure modes of naive matching, the two-stage design, scoring dimensions, class and sequence diagrams. |
| [plugin-api.md](plugin-api.md) | The plugin contract: hook specifications, `ConversionContext`, `PluginSpec`, discovery, ordering. Read before writing a plugin. |
| [developer-guide.md](developer-guide.md) | Stage-by-stage walkthrough with extension recipes and per-stage CLI usage. |
| [gui-design.md](gui-design.md) | GUI structure, component tree, interface signatures, data flow between controller and views. |
| [STANDARDS.md](STANDARDS.md) | Coding standards, development process, and schematic conventions the output must satisfy. |
| [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) | How to verify a conversion against a reference design, including the metrics that matter. |
| [RESEARCH.md](RESEARCH.md) | File-format analysis: DSN container, OLB packages, PST side files, plus library-mapping notes. |
| [cli-migration.md](cli-migration.md) | Flag-by-flag mapping from the pre-0.5.0 CLI to `pipeline.yaml`. |
| [S1-config-design.md](S1-config-design.md) | Design record for the configuration layer: schema, precedence, profiles. |
| [S2-plugin-base-design.md](S2-plugin-base-design.md) | Design record for the plugin foundation: hooks, context ownership, ordering semantics. |
| [class-diagram.mermaid](class-diagram.mermaid) · [sequence-diagram.mermaid](sequence-diagram.mermaid) | Diagrams for the core domain model and the conversion sequence. |

## Diagram sources

Both `.mermaid` files render directly on GitHub. To export them as images, paste the contents
into the [Mermaid Live Editor](https://mermaid.live/) or run `mmdc -i class-diagram.mermaid -o class-diagram.svg`.

## Note on references

Some documents cite earlier working records (development logs, phase plans, archived
research) that are kept outside this repository. Where a citation points to a file that is
not present, the surrounding text is the authoritative description; no behaviour depends on
those records.
