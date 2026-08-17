# Phase XXIV S1 · 旧 CLI → pipeline.yaml 迁移对照表（初稿）

> 日期：2026-08-14｜起草：齐活林（主理人）｜依据：routing.yaml（12 子节）+ __main__.py 23 参数
> 状态：初稿，待架构师 S1 设计确认后定稿
>
> **S10 归档说明（2026-08-17）**：兼容窗口已结束，20 个行为参数（表中除
> `--output/--hdl-lib/--extra-hdl-lib` 路径类外的全部）已从 CLI 移除——传入
> `cis2hdl convert` 报错并提示迁移字段（见 `cis2hdl/cli.py`
> `_REMOVED_FLAGS_TARGETS`）。本表保留作**用户迁移参考**（旧参数 → yaml 字段
> 仍准确）；路径类参数继续保留为 CLI 参数。最新 CLI 用法见
> `docs/developer-guide.md` §10.3。

## A. CLI 参数 → yaml 映射（23 个参数）

| 旧 CLI | 新 yaml 位置 | 说明 |
|--------|-------------|------|
| `--routing p0\|detour\|edif_reuse` | `beautify.params.routing.mode` | p0→default；detour→max-beauty 预设 |
| `--aesthetic` | `profile: max-beauty` 或 `beautify.plugins: [all]` | 语义=全美化（text_layout+overlap+power_ic 联动） |
| `--wire-simplify` | `beautify.plugins: [..., wire_simplify]` | 并入美化钩子链 |
| `--gnd-distribute` | `beautify.plugins: [..., gnd_cluster]` + `gnd.distribute_density` | GND 分布插件 |
| `--rotate-passives` | `beautify.params.placement.rotate_passives` | 被动件旋转感知 |
| `--use-net-name` | `output.reports: [..., net_name]` + `ioport.use_net_name` | 网络名标签 |
| `--text-layout` | `beautify.plugins: [..., text_layout]` | 标签方向 |
| `--chip-config` | `match.manual_overrides.file` | FR3 手动匹配 |
| `--manual-matches` | 同上（别名保留） | 兼容 |
| `--export-unmatched` | `match.manual_overrides.export` | 未匹配导出 |
| `--power-ic` | `match.plugins: [..., power_ic]` | 电源 IC 规则 |
| `--hdl-lib / --extra-hdl-lib` | `input.hdl_libs: [lib1, lib2]` | 库路径 |
| `--max-workers` | `engine.max_workers` | 并行度 |
| `--benchmark` | `output.reports: [..., benchmark]` | 基准报告 |
| `--nonuniform-tracks` | `beautify.params.tracks.nonuniform` | 轨道 |
| `--net-order long_first\|short_first` | `beautify.params.routing.net_order` | 布线顺序 |
| `--no-mirror-normalize` | `beautify.params.mirror.normalize: false` | 镜像归一化 |
| `--no-report` | `report.always_write: false` | 关闭诊断报告 |
| `--ioport-audit` | `output.reports: [..., ioport_audit]` | IOPORT 审计 |
| `--ioport-edge` | `beautify.params.ioport.edge_layout` | IOPORT 边缘分布 |
| `--cross-page-opt` | `beautify.params.routing.cross_page_opt` | 跨页优化 |
| `--output` | 保留 CLI（路径非配置） | 输出路径 |

## B. routing.yaml 12 子节 → pipeline.yaml 位置

| routing.yaml 子节 | 迁移目标 | 备注 |
|-------------------|---------|------|
| `routing.*`（mode/grid/stub_lead/three_stage_stub 等） | `beautify.params.routing.*` | 布线参数 |
| `text_layout.*` | `beautify.params.text_layout.*` | 标签布局 |
| `overlap.*` | `beautify.params.overlap.*` | 防重叠 |
| `manual_matches / chip_config / export_unmatched` | `match.manual_overrides.*` | 手动匹配 |
| `power_ic.*` | `match.params.power_ic.*` | 电源 IC |
| `aesthetic.*` | 由 profile 语义替代（max-beauty） | — |
| `placeholder.*` | `beautify.params.placeholder.*` | 占位符号 |
| `ioport.*` | `beautify.params.ioport.*` | 跨页端口 |
| `mirror.*` | `beautify.params.mirror.*` | 镜像归一化 |
| `gnd_distribution.*` | `beautify.params.gnd.*` | GND 分布/聚类 |
| `report.*` | `output.reports.*` + `report.params` | 报告 |
| `temp_lib.*` | `beautify.params.temp_lib.*` | 模拟图标 |
| `attribute.*` | `output.params.attribute.*` | 属性注入 |
| `matching.*` | `match.params.*` | 匹配约束 |
| `placement.*` | `beautify.params.placement.*` | 布局 |
| `net_name.*` | `output.params.net_name.*` | 网络名 |
| `wire_simplify.*` | `beautify.params.wire_simplify.*` | 电线化简 |
| `pin_audit.*` | `output.reports: [..., pin_audit]` | 引脚审计 |

## C. 兼容策略
- S1 起 CLI 仍接受旧参数 → 映射为等价 yaml 段 + 打印 deprecation 警告（格式：`[deprecation] --<flag> 已迁移至 pipeline.yaml <path>，将于 S10 移除`）
- S10 移除旧参数（兼容窗口结束，文档说明）
