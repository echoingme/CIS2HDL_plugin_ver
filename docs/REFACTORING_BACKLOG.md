# CIS2HDL 插件化重构 — 重构待办清单（REFACTORING_BACKLOG）

- 建立日期：2026-08-14（S0 基线）
- 依据：`docs/refactoring-baseline.md`（vulture 2.16 扫描 + 备份文件 + 重复实现核对）
- 规则：每项处理前必须先 `git commit` 当前代码；处理完成后更新状态。

## 备份冗余（4 项，git 有历史可安全删除）

| # | 文件:行 | 问题类型 | 处理方式 | 状态 |
|---|--------|---------|---------|:---:|
| 1 | cis2hdl/core/writer/sch_writer.py.bak | 备份冗余 | 删除（git 有历史） | 🟡 |
| 2 | cis2hdl/core/config.py.bak | 备份冗余 | 删除（git 有历史） | 🟡 |
| 3 | cis2hdl/core/matcher/pipeline.py.bak | 备份冗余 | 删除（git 有历史） | 🟡 |
| 4 | cis2hdl/core/parser/dsn/structures.py.bak | 备份冗余 | 删除（git 有历史；S0 新增发现） | 🟡 |

## 高置信度死代码（vulture ≥90%，21 项）

| # | 文件:行 | 问题类型 | 处理方式 | 状态 |
|---|--------|---------|---------|:---:|
| 5 | cis2hdl/core/diagnostics/multi_source.py:24 | 未使用 import `_ET` | 删除 import（先确认无动态引用） | 🟡 |
| 6 | cis2hdl/core/diagnostics/pipeline.py:203 | 未使用变量 `kwargs` | 删除变量 | 🟡 |
| 7 | cis2hdl/core/ir/component.py:32 | 未使用变量 `__context` | 删除变量（复核 pydantic 语义） | 🟡 |
| 8 | cis2hdl/core/ir/component.py:75 | 未使用变量 `__context` | 删除变量（复核 pydantic 语义） | 🟡 |
| 9 | cis2hdl/core/matcher/pipeline.py:30 | 未使用 import `is_passive_prefix` | 删除 import | 🟡 |
| 10 | cis2hdl/core/parser/component_catalog.py:102 | 未使用变量 `library_path` | 删除变量 | 🟡 |
| 11 | cis2hdl/core/parser/dsn/binary_reader.py:14 | 未使用 import `overload` | 删除 import | 🟡 |
| 12 | cis2hdl/core/parser/olb/olb_reader.py:24 | 未使用 import `DIR_TYPE_STORAGE` | 删除 import | 🟡 |
| 13 | cis2hdl/gui/candidate_selector.py:21 | 未使用 import `os` | 删除 import | 🟡 |
| 14 | cis2hdl/gui/dialogs/match_confirm.py:342 | 未使用变量 `previous` | 删除变量 | 🟡 |
| 15 | cis2hdl/gui/dialogs/recovery_dialog.py:265 | 未使用变量 `previous` | 删除变量 | 🟡 |
| 16 | cis2hdl/gui/panels/chip_config_panel.py:383 | 未使用变量 `kwargs` | 删除变量 | 🟡 |
| 17 | cis2hdl/gui/panels/error_diagnostic_panel.py:242 | 未使用变量 `previous` | 删除变量 | 🟡 |
| 18 | cis2hdl/gui/panels/log_panel.py:8 | 未使用 import `QEasingCurve`/`QPropertyAnimation` | 删除 import | 🟡 |
| 19 | cis2hdl/gui/panels/log_panel.py:9 | 未使用 import `QTextCursor` | 删除 import | 🟡 |
| 20 | cis2hdl/gui/panels/schematic_view.py:11 | 未使用 import `QTransform` | 删除 import | 🟡 |
| 21 | cis2hdl/gui/panels/schematic_view.py:20 | 未使用 import `QGraphicsItem`/`QGraphicsRectItem`/`QGraphicsTextItem` | 删除 import | 🟡 |
| 22 | cis2hdl/gui/panels/sidebar.py:255 | 未使用变量 `checked` | 删除变量 | 🟡 |

## 重复实现（2 项）

| # | 文件:行 | 问题类型 | 处理方式 | 状态 |
|---|--------|---------|---------|:---:|
| 23 | cis2hdl/core/writer/base.py:38 / csa_writer.py:800 / sch_writer.py:886 | 重复实现 `_resolve_body_name`（3 份） | 合并到 base.py 单一实现，子类复用 | 🟡 |
| 24 | cis2hdl/core/writer/csa_writer.py:1480 / sch_writer.py:939 | 重复实现 `_resolve_prop`/`_resolve_property`（同目的不同名） | 统一命名并合并 | 🟡 |

## 状态图例

- 🟡 待处理（S0 基线已记录，未改动）
- 🔵 处理中
- 🟢 已完成
- ⚪ 已取消 / 确认无需处理

## S4 匹配插件化遗留/设计假设（2026-08-17）

| # | 项 | 说明 | 状态 |
|---|-----|------|:---:|
| S4-1 | `prefix_scope` 并集语义 | S4 实现为"并集关键字收窄候选库副本"（不改 matcher 内部），无法表达逐 prefix 收窄；未来可扩展 `CandidatePoolBuilder._filter_by_type` 为感知 prefix_scope（S4 铁律禁止改 matcher，故未做） | 🟡 |
| S4-2 | `match.weights` 默认值修正 | S1 占位权重（part_name 0.5/...）与 `ActiveMatcher.WITHIN_TYPE_WEIGHTS` 不一致；S4 对齐为 WITHIN_TYPE_WEIGHTS（否则默认应用破坏 FR9） | 🟢 |
| S4-3 | `match.prefix_scope` 默认值修正 | S1 占位示例（R:[0603,...]）若直接应用会收窄候选库、破坏默认等价；S4 改为空 dict（默认不限制，显式配置生效） | 🟢 |
| S4-4 | `match.mock` 无新消费点 | mock.prefixes/auto_icon 由后端 temp_lib.mock_all 消费（S1 已承载）；S4 仅随 match 段承载，未新增插件消费 | ⚪ |
| S4-5 | 匹配插件"链首编排"语义 | exact/fuzzy/passive/fallback 单独启用时均委托完整 legacy 管线（内部含全部策略）；插件名表达优先级序位而非策略过滤——S4 设计假设，已文档化 | 🟢 |
