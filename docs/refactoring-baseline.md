# CIS2HDL 插件化重构 — S0 冗余基线扫描报告

- 扫描日期：2026-08-14
- 扫描对象：`cis2hdl_plugin_ver/`（由 `cis2hdl/` Phase XXIII 复制而来，代码零改动）
- 扫描范围：`cis2hdl/` 源码包（不含 tests/、docs/、scripts/）
- 目的：为 Phase XXIV 插件化重构建立"冗余基线"，记录已知死代码/备份/重复，供后续 backlog 与清理决策参考

## 1. 测试等价验证（Step 3 结论）

| 项目 | 源仓库 cis2hdl/ | 插件版 cis2hdl_plugin_ver/ | 差异原因 |
|---|---|---|---|
| collected | 935 | 935 | 一致（SOP 中"936"为笔误，实测 935） |
| passed | 929 | 919 | 见下方差异明细 |
| skipped | 6 | 7 | 见下方差异明细 |
| failed | 0 | 9 | 全部为 SOP 排除目录导致（非复制缺陷） |

### 差异明细（10 项，全部源于 S0 Step2 的排除决策，非路径问题/复制遗漏）

| 测试 | 源行为 | 插件版行为 | 原因 |
|---|---|---|---|
| tests/e2e/test_v9_compare_package.py（8 项） | pass | FAIL | 读取 `HG5015_tests/output_phaseXXV_compare`（SOP 明确不复制 HG5015_tests） |
| tests/unit/test_phase_xi_p1.py::test_reference_cpc_uses_cell_for_mark | pass | FAIL | 读取 `docs_for_reference/OrCAD_files_references/...`（SOP 明确不复制 docs_for_reference） |
| tests/unit/test_error_diagnosis.py:181 | pass | skip | 同一 docs_for_reference 依赖，但该测试有 skip 守卫 → 跳过而非失败 |
| tests/unit/test_phase_xi_p1.py:95 | 视 /tmp 状态 | skip（时序相关） | `p1_verify*` 转换输出存在于 /tmp 时运行，否则跳过；与复制无关 |

**结论**：`cis2hdl/`、`tests/`、`scripts/`、`docs/` 与顶层文件均逐字节一致（`diff -rq` 通过）。9 项失败 + 1 项额外跳过全部由 S0 明确排除的 `HG5015_tests/`、`docs_for_reference/` 引起，属预期行为。若需插件版全绿，应由团队决定是否对这些数据依赖型 e2e 测试加 skip 守卫（Phase XXIV 决策，S0 不处理）。

## 2. 死代码扫描（vulture 2.16）

命令：`python -m vulture cis2hdl/`

- 总条目：**357**（confidence ≥ 60%）
- 高置信度（≥ 90% / 100%）：**21**

### 按类型分布

| 类型 | 条数 |
|---|---|
| unused variable | 167 |
| unused method | 82 |
| unused attribute | 44 |
| unused function | 26 |
| unused property | 18 |
| unused import | 12 |
| unused class | 8 |

### 按目录/文件 TOP 10

| 文件 | 条数 |
|---|---|
| cis2hdl/core/config.py | 51 |
| cis2hdl/core/parser/dsn/structures.py | 38 |
| cis2hdl/gui/colors.py | 20 |
| cis2hdl/core/diagnostics/diagnostic_report.py | 15 |
| cis2hdl/core/parser/dsn/ole_reader.py | 10 |
| cis2hdl/core/writer/wire_layout.py | 9 |
| cis2hdl/core/writer/csa_writer.py | 9 |
| cis2hdl/core/parser/olb/olb_parser.py | 9 |
| cis2hdl/core/diagnostics/pipeline.py | 9 |
| cis2hdl/gui/panels/schematic_view.py | 8 |

### 高置信度条目（≥ 90%，21 条）

| 文件:行 | 条目 | 置信度 |
|---|---|---|
| cis2hdl/core/diagnostics/multi_source.py:24 | unused import `_ET` | 90% |
| cis2hdl/core/diagnostics/pipeline.py:203 | unused variable `kwargs` | 100% |
| cis2hdl/core/ir/component.py:32 | unused variable `__context` | 100% |
| cis2hdl/core/ir/component.py:75 | unused variable `__context` | 100% |
| cis2hdl/core/matcher/pipeline.py:30 | unused import `is_passive_prefix` | 90% |
| cis2hdl/core/parser/component_catalog.py:102 | unused variable `library_path` | 100% |
| cis2hdl/core/parser/dsn/binary_reader.py:14 | unused import `overload` | 90% |
| cis2hdl/core/parser/olb/olb_reader.py:24 | unused import `DIR_TYPE_STORAGE` | 90% |
| cis2hdl/gui/candidate_selector.py:21 | unused import `os` | 90% |
| cis2hdl/gui/dialogs/match_confirm.py:342 | unused variable `previous` | 100% |
| cis2hdl/gui/dialogs/recovery_dialog.py:265 | unused variable `previous` | 100% |
| cis2hdl/gui/panels/chip_config_panel.py:383 | unused variable `kwargs` | 100% |
| cis2hdl/gui/panels/error_diagnostic_panel.py:242 | unused variable `previous` | 100% |
| cis2hdl/gui/panels/log_panel.py:8 | unused import `QEasingCurve` | 90% |
| cis2hdl/gui/panels/log_panel.py:8 | unused import `QPropertyAnimation` | 90% |
| cis2hdl/gui/panels/log_panel.py:9 | unused import `QTextCursor` | 90% |
| cis2hdl/gui/panels/schematic_view.py:11 | unused import `QTransform` | 90% |
| cis2hdl/gui/panels/schematic_view.py:20 | unused import `QGraphicsItem` | 90% |
| cis2hdl/gui/panels/schematic_view.py:20 | unused import `QGraphicsRectItem` | 90% |
| cis2hdl/gui/panels/schematic_view.py:20 | unused import `QGraphicsTextItem` | 90% |
| cis2hdl/gui/panels/sidebar.py:255 | unused variable `checked` | 100% |

> 注：60% 置信度条目（如 config.py 的 51 条变量/属性）多为配置字段，可能通过动态属性访问被使用，属 vulture 常见误报，清理前需逐一人工复核（建议结合 grep 使用点确认）。

## 3. 备份文件扫描

命令：`find cis2hdl/ -name "*.bak" -o -name "*.orig" -o -name "*.rej"`

源码包内共 **4 个 .bak**（无 .orig / .rej）：

| 文件 | 大小 | 说明 |
|---|---|---|
| cis2hdl/core/writer/sch_writer.py.bak | — | 已知备份冗余 |
| cis2hdl/core/config.py.bak | — | 已知备份冗余 |
| cis2hdl/core/matcher/pipeline.py.bak | — | 已知备份冗余 |
| cis2hdl/core/parser/dsn/structures.py.bak | — | 新增发现（SOP 已知 3 个之外） |

另有 2 个 `tests/fixtures/hdl_lib/**/symbol.css.bak`（测试数据，非源码，不纳入清理）。

## 4. 重复实现扫描

命令：`grep -rn "def <name>" cis2hdl/ --include="*.py"` + 全量 def/class 重名统计

### 已知重复函数

| 函数 | 定义位置（多份） | 建议 |
|---|---|---|
| `_resolve_body_name` | cis2hdl/core/writer/base.py:38、csa_writer.py:800、sch_writer.py:886（3 份） | 合并到 base.py 单一实现，子类复用 |
| `_resolve_prop` / `_resolve_property` | cis2hdl/core/writer/csa_writer.py:1480、sch_writer.py:939 | 同目的不同名，统一命名并合并 |

### 已核对项

| 函数 | 结论 |
|---|---|
| `_build_xcon_content` | 仅 1 处定义（cis2hdl/core/writer/xcon_writer.py:109），疑似已在此前重构中合并；插件化时仍建议确认无重复语义 |

> 注：全量 def/class 重名统计中 `__init__`/`write`/`parse`/`match` 等方法重名属于正常 OOP 覆盖，不计入重复实现。

## 5. TODO/FIXME 扫描

命令：`grep -rn "TODO\|FIXME" cis2hdl/ --include="*.py" | wc -l`

- **0 条**（源码无 TODO/FIXME 残留）

## 6. 扫描结果汇总表

| 扫描项 | 工具 | 结果 | 建议处理方式 |
|---|---|---|---|
| 死代码（总） | vulture 2.16 | 357 条（≥60%） | 高置信度 21 条进 backlog；60% 条目人工复核后分批清理 |
| 死代码（高置信度） | vulture 2.16 | 21 条（≥90%） | 直接进 REFACTORING_BACKLOG，可安全清理 |
| 备份文件 | find | 4 个 .bak（含新增 structures.py.bak） | 删除（git 有历史），进 backlog |
| 重复实现 | grep | `_resolve_body_name` ×3、`_resolve_prop/_resolve_property` ×2 | 合并单一实现，进 backlog |
| TODO/FIXME | grep | 0 条 | 无需处理 |
| 测试等价性 | pytest | 919 passed / 7 skipped / 9 failed | 9 failed + 1 skip 均为 SOP 排除目录所致，非复制缺陷（详见 §1） |
