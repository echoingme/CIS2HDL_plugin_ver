# CIS2HDL

> OrCAD Capture CIS 原理图 → Cadence Design Entry HDL 原理图格式转换工具

| 项目 | 值 |
|------|-----|
| 文档版本 | v1.4（2026-08-07 合并更新） |
| 项目版本 | **v1.1.0**（匹配系统 v2.0） |
| 测试基线 | **268 passed / 23 skipped / 0 failed**（291 collected，2026-08-07 实测） |
| 状态 | 现行门户文档（权威口径以 [STATUS.md](STATUS.md) 为准） |
| 合并来源 | 合并自 README / DOCS_INDEX / PROJECT_OVERVIEW（2026-08-07） |
| 关联文档 | [STATUS.md](STATUS.md)（含技术债清单，原 KNOWN_ISSUES.md 已并入） · [ROADMAP.md](ROADMAP.md) · [changelog_master.md](changelog_master.md)（全量历史总集，附录 A 为 CHANGELOG 完整副本；原文存 [archive/handoff&logs/CHANGELOG.md](archive/handoff&logs/CHANGELOG.md)） · [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [MATCHING.md](MATCHING.md) · [STANDARDS.md](STANDARDS.md) · [RESEARCH.md](RESEARCH.md) |

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-v1.1.0%20%7C%20matching%20v2.0-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/tests-268%20passed-brightgreen.svg)]()
[![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)]()

---

## 概述

**CIS2HDL** 是一款 EDA 辅助工具，用于将 OrCAD Capture CIS（`.dsn` + `.olb`）格式的原理图和器件库，转换为 Cadence Design Entry HDL（原 Concept HDL，`.cpm` + `.sch` + `.sym` + `.ptf`）格式的完整工程。

### 核心能力

- **DSN/OLB 解析** — 解析 OrCAD 二进制原理图格式（OleReader + BinaryReader），提取器件/引脚/网络/层次结构
- **Cadence 兼容** — UPREV 已消除，输出 `.xcon`/`.dcf`/`.con` 完整工程文件，SPB 16.6 可直接打开
- **匹配系统 v2.0** — 两阶段匹配架构（Phase1 TypeHypothesis 类型假设 → Phase1.5 CandidatePool 候选池 → Phase2A PassiveMatcher 5 级确定性规则 / Phase2B ActiveMatcher 5 维评分），final_conf = phase1_prior × phase2_within
- **六阶段诊断** — 文件完整性→依赖解析→就绪度评估→匹配→校验→质量评估（错误码 44 条）
- **完整 GUI** — PySide6 界面（Anthropic 暖米色），原理图预览/Diff/规则管理/批量转换
- **OLB 解析器** — 20/21 Package 成功，8 种图形元素，已注册到 ParserRegistry
- **CLI 支持** — `python -m cis2hdl convert` 无 GUI 命令行转换（已实现）

---

## 项目状态

**当前版本：v1.1.0（匹配系统 v2.0）** — 2026-08-07 发布。测试基线 **268 passed / 23 skipped / 0 failed**（291 collected）。

详见 [STATUS.md](STATUS.md)（当前状态权威文档，含技术债清单，原 KNOWN_ISSUES.md 已并入）与 [changelog_master.md](changelog_master.md)（全量历史文档总集，附录 A 为 CHANGELOG 完整副本）。

### Phase III 规划（历史记录，已完成）

> 以下为 v0.3.5 时代（2026-08-03）的 Phase III 规划与完成状态，保留作历史记录。当前版本已演进至 v1.1.0（匹配系统 v2.0）。

| 优先级 | 任务 | 状态 |
|:--:|------|:--:|
| P0 | OLB 解析器 — 20/21 Package, 8图形元素 | ✅ |
| P0 | PyInstaller 打包 — cis2hdl.spec + build_exe.py | ✅ |
| P1 | 原理图预览 — QGraphicsView 缩放平移 | ✅ |
| P1 | 差异对比 — DiffViewPanel 语义色 | ✅ |
| P1 | 批量转换 — BatchConversionEngine 队列 | ✅ |
| P1 | 映射规则 — YAML 导入导出 + RulesPanel | ✅ |
| P1 | 性能优化 — benchmark + max_workers | ✅ |
| P1 | E2E 测试 — RTL8367RB 真实项目 9 tests | ✅ |
| P2 | HTML 报告导出 | ✅ |
| P2 | ConversionHistoryManager | ✅ |
| P2 | MultiSourceCrossValidator | ✅ |
| P2 | OLBIntegrityChecker | ✅ |

---

## 文档导航

> 本文档承担 docs/ 目录地图职责（原 DOCS_INDEX.md 主体并入，2026-08-07）。docs/ 根目录 md 已整合为 **9 份权威文档**；被合并的源文档移入 `archive/合并源/`（原二次合并源已并入，2026-08-07 路径更新），历史文档全部归档于 `archive/` 各分区（只归档不删除）。原 README「文档索引」快捷入口已并入本节。

### 1. 根目录权威文档清单（9 份）

| # | 文档 | 一句话定位 |
|:--:|------|-----------|
| 1 | [README.md](README.md) | 项目门户（本文档）：概述、核心能力、文档导航、需求基线 |
| 2 | [STATUS.md](STATUS.md) | **当前状态权威**：版本 v1.1.0、测试基线 268+23、阶段完成度、匹配指标、技术债清单（原 KNOWN_ISSUES.md 已并入） |
| 3 | [ROADMAP.md](ROADMAP.md) | **合并后权威路线图**：Part I 初始愿景 + Part II 阶段审计 + Part III 最新状态/裁决 + 附录研发时间线 |
| 4 | [changelog_master.md](changelog_master.md) | **全量历史文档总集**：15 份源时期板块化合并，附录 A 为 CHANGELOG 完整副本（原文已移至 `archive/handoff&logs/CHANGELOG.md`） |
| 5 | [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) | 验证指南唯一权威：Part I 现行 HG5015（24 CSA / 889 元件 / 3717 网络）+ Part II 历史（RTL8367RB/HG5015） |
| 6 | [ARCHITECTURE.md](ARCHITECTURE.md) | 系统架构五合一：Part I 架构总览 / Part II 后端详设 / Part III 器件模型 / Part IV 诊断体系 / Part V GUI 设计 |
| 7 | [MATCHING.md](MATCHING.md) | 匹配系统四合一：Part I 根因分析 / Part II v2.0 设计 / Part III 类图 / Part IV 时序图 |
| 8 | [STANDARDS.md](STANDARDS.md) | 规范标准三合一：Part I 编码规范 / Part II 开发流程 / Part III 原理图规范 |
| 9 | [RESEARCH.md](RESEARCH.md) | 调研参考四合一：Part I 格式分析 / Part II 技术调研 / Part III 参考库笔记 / Part IV 文件索引 |

> 合并说明：ARCHITECTURE.md / MATCHING.md / STANDARDS.md / RESEARCH.md 由对应源文档内容保全式合并生成（2026-08-07，详见各文档「合并说明」章节）；合并前的源文档（SYSTEM_ARCHITECTURE.md 等 16 份被合并源 + DOCS_INDEX.md / PROJECT_OVERVIEW.md / TIMELINE.md 吸收源等）归档于 `archive/合并源/`（原二次合并源已并入，2026-08-07 路径更新）。

docs/ 根目录另保留非 md 文件：`_gen_cmp_pt1.py`、`_gen_imp.py`（文档工具脚本）、`_ref_file_list.csv`（参考库结构索引）、`硬件设计规范.docx` / `硬件设计规范.pdf`（外部权威规范）。

### 2. archive/ 归档区索引

> 归档区存放全部历史文档（只归档不删除）。2026-08-07 16:30 用户手动调整后，archive/ 现为 **4 个主分区**（handoff&logs / 合并源 / 废弃设计 / 过程文档）+ 散件。子目录 → 内容 → 映射说明如下（源文档映射表原文保留自 DOCS_INDEX.md，路径已按最新分区更新）。

| 子目录 | 内容 | 映射说明 |
|--------|------|----------|
| `archive/handoff&logs/` | 9 份日期工作日志（2026-07-22 ~ 2026-08-06）+ 4 份历史交接文档（handoff-20260805-103417 / 20260805-160515 / 20260806-085237 / 20260806-161951）+ **CHANGELOG.md**（2026-08-07 由 docs/ 根移入，原文存此） | 原 `docs/2026-07-29.md` 等 9 份日志与 `docs/handoff-20260805-*.md`、`docs/handoff-20260806-*.md` 4 份交接 → `docs/archive/handoff&logs/`。其中 **2026-07-22.md / 2026-07-23.md 为 waveform_viewer 项目日志（非 CIS2HDL）**，仅归档不并入主线（详见 ROADMAP.md 附录研发时间线）。**handoff-20260807-113237.md 已移入 `archive/合并源/`** 作 STATUS 状态源 |
| `archive/合并源/` | 合并源文档（首次合并源 10 份 + 二次合并源 16 被合并源 + 3 吸收源 + 独立归档）+ 运行快照 8 份 + `runtime_logs_master.txt`（运行日志合并档） | 原 `archive/二次合并源/` 已并入本区（2026-08-07 路径更新）。首次合并源主目标：DEVELOPMENT_ROADMAP.md / ROADMAP_AUDIT_2026-08-03.md → ROADMAP.md；FRONTEND_DESIGN.md → UI_DESIGN_SPEC.md（前端 GUI 设计，§13 交互流程）；HDL_OUTPUT_FIX_PLAN.md → fix_proposal.md（附录根因链）；_comparison_report.md → HDL_SCHEMATIC_STANDARDS.md（比特级比对来源）；_reference_index.md / reference_project_file_list.md → FILE_INDEX_AND_MAPPING.md（A.1 参考库索引）；2608041210report.md → SYSTEM_ARCHITECTURE.md（HG5015 解析算法正式归宿）；test1.txt → VERIFICATION_GUIDE.md 九（BOM 交叉验证方法论）；VERIFICATION_GUIDE_HG5015.md → VERIFICATION_GUIDE.md Part II.2。二次合并源（SYSTEM_ARCHITECTURE.md、BACKEND_DESIGN.md、COMPONENT_ARCHITECTURE.md、DIAGNOSTICS_AND_RECOVERY.md、UI_DESIGN_SPEC.md、system_design.md、MATCHING_ANALYSIS_2026-08-06.md、class-diagram.mermaid、sequence-diagram.mermaid、CODING_STANDARDS.md、DEVELOPMENT_SOP.md、HDL_SCHEMATIC_STANDARDS.md、ORCAD_SOURCE_ANALYSIS.md、RESEARCH_REPORT.md、REFERENCE_READING_NOTES.md、FILE_INDEX_AND_MAPPING.md + 吸收源 DOCS_INDEX.md / PROJECT_OVERVIEW.md / TIMELINE.md + 独立归档 fix_proposal.md / handoff-20260807-113237.md / MEMORY.md）归 ARCHITECTURE / MATCHING / STANDARDS / RESEARCH 与门户（README/ROADMAP）合并。运行快照（_rtl_result.txt、convert_output.log、errors08060847.txt、hg5015_verify.txt、test_output*.txt、tests_output.txt 等，errors08060847.txt 为 CSA 尾部页历史缺陷证据，见 STATUS.md 技术债 ③；test_output_20260807_291collected.txt 为 291-collected 运行快照，2026-08-07 实测）与 runtime_logs_master.txt 亦归本区 |
| `archive/废弃设计/` | 5 份废弃设计源（system_design08061513.md、class-diagram08061513.mermaid、sequence-diagram08061513.mermaid、MATCHING_DIAGNOSIS_2026-08-04.md、CIS2HDL_IMPROVEMENT_DOC.md）+ **合并档 deprecated_designs_master.md**（废弃设计 5 合一，2026-08-07） | v0.9.0 时代匹配方案与旧图，已被匹配 v2.0 取代 → `docs/archive/废弃设计/`；合并档位于同目录，源文件保留不删 |
| `archive/过程文档/` | 14 份过程文档源（_audit_code.md、_audit_tests.md、_implementation_log.md、_improvement_plan.md、_qa_report.md、_refactor_log.md、_test_reorg_log.md、binary_diff_report.md、validation_report.md、FILE_COLLECTION_CHECKLIST.md、PHASE2_DESIGN.md、PRD_v0.5.1_incremental.md、temp.txt、test1.md）+ **合并档 process_docs_master.md**（过程文档 14 合一，2026-08-07） | 带 `_` 前缀的审计/过程文档与一次性报告 → `docs/archive/过程文档/`（其中 _audit_code.md 技术债已收纳进 STATUS.md 技术债清单）；合并档位于同目录，源文件保留不删 |
| 散件（archive/ 根） | `_cis2hdl_file_list.csv`（2026-08-03 全量文件清单快照，含 .venv 噪音与 nul 条目，已过期） | 原 `archive/清单快照/` 内容，现位于 archive/ 根目录 |

> 另：整合总档 `docs/docs_consolidation260807.md`（4 份方案/报告总档：docs_consolidation_plan_2026-08-07 / docs_consolidation_report_2026-08-07 / docs_merge_plan_2026-08-07 / docs_merge_report_2026-08-07，2026-08-07）位于 cis2hdl 根目录，后续 plan/report 类内容统一写入该档。

### 3. 文档元信息块规范

**适用范围**：docs/ 下全部现行权威文档（README、STATUS、ROADMAP、changelog_master、VERIFICATION_GUIDE、ARCHITECTURE、MATCHING、STANDARDS、RESEARCH 及归档区文档）建议在文档开头放置元信息块，防止版本/数字口径漂移。

**推荐格式**（Markdown 表格，位于标题后第一位置）：

```markdown
# 文档标题

| 项目 | 值 |
|------|-----|
| 文档版本 | vX.Y（YYYY-MM-DD 更新） |
| 项目版本 | v1.1.0（匹配系统 v2.0） |
| 状态 | 现行权威 / 草稿 / 历史归档 |
| 关联文档 | [STATUS.md](STATUS.md) · [DOCS_INDEX.md](DOCS_INDEX.md) |
```

**字段说明**：

| 字段 | 说明 |
|------|------|
| 文档版本 | 该文档自身的修订版本，随更新递增 |
| 项目版本 | 该文档描述/对齐的项目版本（当前权威 v1.1.0） |
| 状态 | 权威等级：现行权威 / 草稿 / 历史（归档文档标注历史边界） |
| 关联文档 | 与本文档有引用关系的其他文档（相对路径） |

**强制规则**：

1. 数字口径（版本号、测试数、错误码、匹配指标）必须与 [STATUS.md](STATUS.md) 一致；历史数字一律标注"历史口径"
2. 交叉引用统一用相对路径 + 章节锚点（如 `[STATUS.md](STATUS.md#3-匹配系统-v20-架构与指标)`）
3. 归档文档不改名、保留原始文件名（便于检索与追溯）
4. 正式文档无 `_` 前缀；过程/临时文档以 `_` 前缀并在归档区存放

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 核心语言 | Python 3.12+ |
| GUI 框架 | PySide6 (Qt 6) |
| 模糊匹配 | rapidfuzz |
| 数据模型 | Pydantic |
| EDIF 解析 | sexpdata（S-expression 文本解析） |
| 二进制解析 | OleReader + BinaryReader + StructureParsers（纯 Python，从 TS/C++ 移植） |
| 测试 | pytest |
| 代码质量 | ruff + mypy (strict) |

---

## 快速开始

```bash
# 安装（开发阶段使用 editable 模式）
pip install -e ".[dev]"

# GUI 模式
python -m cis2hdl.gui.app

# CLI 模式（已实现）
python -m cis2hdl convert project.dsn --output ./hdl_output/ --hdl-lib ./company_lib/
```

---

## 开发计划

> 以下为项目启动时（v0.1.0，2026-07-29）的三阶段开发计划，保留作历史记录。实际执行演进详见 [ROADMAP.md](ROADMAP.md) 附录：研发过程时间线（原 TIMELINE.md 全文）。

| 阶段 | 内容 | 预计产出 |
|:----:|------|---------|
| **Phase I-A** | EDIF 快速验证 | EDIF Parser → IR → 无坐标 HDL 骨架，交叉验证基线 |
| **Phase I-B** | Binary DSN 解析 | OleReader + BinaryReader + StructureParsers → IR（含坐标）→ 完整 HDL 生成 |
| **Phase II** | Core Pipeline | 两阶段匹配管道（v2.0）、校验层、完整生成器（网络规范化、总线转换）、GUI 匹配确认交互 |
| **Phase III** | Polish | 原理图预览、差异对比、批量转换、报告导出、OLB 解析器 |

---

## 需求基线

> 本节吸收原 PROJECT_OVERVIEW.md（v1.3，2026-08-07 更新）主体：需求总纲（业务/功能/非功能需求、约束与假设、术语表、参考基准数据），原文保留（仅调整标题层级）。原 PROJECT_OVERVIEW.md 已归档 `archive/合并源/`（原二次合并源已并入，2026-08-07 路径更新）。实现状态以项目参数卡 v1.1.0 与 [STATUS.md](STATUS.md) 为准。

### 1. 项目定义

#### 1.1 项目名称

**CIS2HDL** — OrCAD Capture CIS 原理图到 Cadence Design Entry HDL 原理图格式转换工具

#### 1.2 项目代号

`cis2hdl`

#### 1.3 一句话描述

将 OrCAD Capture CIS（`.dsn` + `.olb`）格式的原理图和器件库，转换为 Cadence Design Entry HDL（`.cpm` + `.sch` + `.sym` + `.ptf`）格式的完整工程，并提供器件模糊匹配、转换预览、差异对比等全流程 GUI 支持。

### 2. 业务需求

#### 2.1 问题陈述

- 某公司当前使用 OrCAD Capture CIS 进行原理图设计
- 公司规范要求迁移到 Design Entry HDL（更好的层次化设计、版本管理、多人协作支持）
- CIS 原理图库不符合公司 HDL 库命名规范
- Cadence 官方未提供完整、可靠、自动化的原理图级转换工具
- 现有方案（cap2con.exe、Elgris）要么不可用、要么需商业授权

#### 2.2 目标用户

- PCB 硬件设计工程师
- EDA 库管理员
- 设计团队技术负责人

#### 2.3 使用场景

| 场景 | 描述 |
|------|------|
| 单项目转换 | 选择 CIS `.dsn` 项目，一键转换为 HDL 完整工程 |
| 器件库迁移 | 将 `.olb` 库文件转换为 HDL `.sym` + `.ptf` 格式 |
| 批量转换 | 同时转换多个 CIS 项目 |
| 增量转换 | 仅转换变更页面，保留已确认的映射结果 |

### 3. 功能需求（F01-F23 完整）

#### 3.1 核心功能（P0 - 必须实现）

| 编号 | 功能 | 描述 |
|:----:|------|------|
| F01 | DSN 解析 | 直接解析 `.dsn` 二进制文件（OleReader → BinaryReader → StructureParsers），提取器件实例、引脚、网络、属性、层次结构、**图形坐标** |
| F01a | EDIF 解析 | 解析 `.edf` 文本文件（sexpdata S-expression），提取完整逻辑数据，**先行验证 + 交叉校验 Binary DSN 正确性** |
| F02 | OLB 解析 | 解析 `.olb` 二进制文件，提取符号定义、引脚、属性（Phase III） |
| F03 | 器件模糊匹配 | 将 CIS 器件名/属性与 HDL 库器件进行模糊匹配，生成映射建议 |
| F04 | 引脚对应校准 | 校验 CIS 器件引脚与 HDL 器件引脚的编号和名称一致性 |
| F05 | 网络名规范化 | 清洗非法字符、转换总线格式、处理电源网络命名 |
| F06 | HDL 工程生成 | 生成完整的 `.cpm` + `cds.lib` + `.sch` + `.sym` + `.ptf` 文件树 |
| F07 | 转换日志 | 记录所有转换操作、匹配决策、警告、错误 |
| **F07a** | **文件完整性校验** | **对用户输入的 CIS 项目文件集进行完整性检查：验证 .dsn 文件存在性/格式正确性/版本兼容性，检测 OLB 库引用是否满足，列出缺失文件清单和必需性等级（必选/建议/可选）** |
| **F07b** | **数据质量评估** | **转换前输出四维评估报告：逻辑完整性%（器件/引脚/网络覆盖率）、坐标可用性%（有坐标的器件占比）、匹配覆盖率%（已匹配 HDL 库的器件占比）、符号保真度%（保留原始符号 vs 默认符号）。用彩色进度条可视化。** |
| **F07c** | **错误诊断与修复引导** | **包含 44 条结构化错误码（对标 Cadence Canvas 错误码体系），每条错误附带：严重级别、详细消息、可操作的修复建议。FEATAL/ERROR 级阻止转换，WARNING 级可忽略继续，INFO 级仅提示。** |
| **F07d** | **降级转换路径** | **当输入文件不完整或部分损坏时，提供多级降级转换路径（DSN 损坏→.dbk 恢复→EDIF 备用→跳过损坏页），每条路径明确标注数据损失程度，用户自主选择。** |
| **F07e** | **转换就绪度评估** | **综合评分系统：分析当前文件集后给出"可完整转换"/"可降级转换（含数据损失）"/"无法转换"三级判定，并列出缺失项和补充建议。** |

#### 3.2 增强功能（P1 - 应该实现）

| 编号 | 功能 | 描述 |
|:----:|------|------|
| F08 | GUI 主界面 | 完整的图形用户界面（项目管理、参数配置、进度显示） |
| F09 | 匹配确认交互 | 对低置信度匹配项弹出确认对话框 |
| F10 | 转换预览 | 转换前预览目标 HDL 工程结构 |
| F11 | 差异对比 | 转换前后器件、网络、引脚的差异对比视图 |
| F12 | 映射规则管理 | 保存/加载/编辑器件名映射规则配置文件 |
| F13 | 批量转换 | 支持多项目队列转换 |

#### 3.3 增强功能（P1 - 续）

| 编号 | 功能 | 描述 |
|:----:|------|------|
| F14 | HDL 库自动导入 | 扫描 hdl_lib 目录，自动解析 chips.prt / symbol.css / part.ptf / .pad / .dra / .psm |
| F15 | BOM_SEQ 自动生成 | 根据器件类型和封装自动生成公司规范的 BOM 编码 |
| F16 | 位号前缀自动分配 | 根据器件类型自动分配位号前缀（电阻→R，电容→C...） |
| F17 | 网络名自动规范化 | 非法字符清洗、总线格式 CIS→HDL 转换、全局命名检测 |
| **F17a** | **结构化诊断报告** | **转换完成后生成结构化报告（JSON → 前端渲染为彩色 HTML/PDF），包含：文件状态表、逐页解析详情、匹配结果色标表、校验问题清单、生成文件目录、质量评估摘要、后续操作建议** |
| **F17b** | **多数据源交叉验证** | **当同时提供 .dsn + .edf + pstx*.dat 时，三路逐字段比对器件数/引脚数/网络数/属性值/连接关系，任一路不一致触发详细差异定位报告** |

#### 3.4 高级功能（P2 - 可以实现）

| 编号 | 功能 | 描述 |
|:----:|------|------|
| F18 | 原理图预览 | 在 GUI 中渲染 CIS 源原理图 |
| F19 | 规则引擎 | 用户自定义的匹配规则 DSL |
| F20 | 报告导出 | 生成 PDF/HTML 转换报告 |
| F21 | 命令行模式 | 无 GUI 的命令行批量转换 |
| F22 | 原理图自动排版 | 网络名对齐、Port 对齐、网格对齐、不重叠检测 |
| F23 | 多版本兼容 | 输出可配置为 SPB 16.6 / 17.2 / 17.4 格式 |

#### 3.5 功能需求实现状态总览（2026-08-07 核对）

> 实现状态以项目参数卡 v1.1.0 与代码核对为准（2026-08-07）。"已实现"指对应功能在当前代码库可运行；"部分实现"指主路径可用但存在已知缺口；"待确认"指暂无权威落地证据，需人工核实后填写。

| 编号 | 功能 | 实现状态 | 说明/证据 |
|:----:|------|:--:|------|
| F01 | DSN 解析 | ✅ 已实现 | OleReader + BinaryReader + StructureParsers → IR（含坐标） |
| F01a | EDIF 解析 | ✅ 已实现 | sexpdata 解析，先行验证 + 交叉校验 |
| F02 | OLB 解析 | ✅ 已实现 | 20/21 Package 成功，8 种图形元素（Phase III） |
| F03 | 器件模糊匹配 | ✅ 已实现 | 匹配系统 v2.0（两阶段架构，MultiScorer 已删除） |
| F04 | 引脚对应校准 | ✅ 已实现 | PST 数据链路（pstchip→InstanceIR→ComponentDef） |
| F05 | 网络名规范化 | ✅ 已实现 | net_utils + 总线转换 |
| F06 | HDL 工程生成 | ✅ 已实现 | 输出 .cpm + cds.lib + .sch/.csa + .sym + .ptf 文件树 |
| F07 | 转换日志 | ✅ 已实现 | 转换日志 + errors.txt 输出 |
| F07a | 文件完整性校验 | ✅ 已实现 | 诊断类需求（FileInventory + DSNInventory） |
| F07b | 数据质量评估 | ✅ 已实现 | 诊断类需求（四维评估报告） |
| F07c | 错误诊断与修复引导 | ✅ 已实现 | 44 条结构化错误码（ErrorDiagnosisEngine） |
| F07d | 降级转换路径 | ✅ 已实现 | FileRecoveryStrategy（多级降级路径） |
| F07e | 转换就绪度评估 | ✅ 已实现 | ReadinessEvaluator 三级判定 |
| F08 | GUI 主界面 | ✅ 已实现 | PySide6（Anthropic Token 体系） |
| F09 | 匹配确认交互 | ✅ 已实现 | MatchConfirmDialog + candidate_selector |
| F10 | 转换预览 | ✅ 已实现 | 预览目标 HDL 工程结构 |
| F11 | 差异对比 | ✅ 已实现 | DiffViewPanel 语义色 |
| F12 | 映射规则管理 | ✅ 已实现 | YAML 导入导出 + RulesPanel |
| F13 | 批量转换 | ✅ 已实现 | BatchConversionEngine 队列 |
| F14 | HDL 库自动导入 | ✅ 已实现 | HDLLibScanner + ChipsPrtParser + PartPtfParser |
| F15 | BOM_SEQ 自动生成 | 待确认 | 未见权威落地证据，需人工核实 |
| F16 | 位号前缀自动分配 | ✅ 已实现 | prefix_filter 前缀→类型映射 |
| F17 | 网络名自动规范化 | ✅ 已实现 | 网络规范化 + 总线转换 |
| F17a | 结构化诊断报告 | ✅ 已实现 | JSON + HTML 报告生成（report_gen） |
| F17b | 多数据源交叉验证 | ✅ 已实现 | MultiSourceCrossValidator（DSN+EDF+PST） |
| F18 | 原理图预览 | ✅ 已实现 | SchematicPreviewPanel（QGraphicsView） |
| F19 | 规则引擎 | 部分实现 | CTW DSL 已实现；GUI 规则编辑器落地状态待确认 |
| F20 | 报告导出 | ✅ 已实现 | HTML 报告 + 38 列 CSV 映射表 |
| F21 | 命令行模式 | ✅ 已实现 | `python -m cis2hdl convert`（CLI 已实现） |
| F22 | 原理图自动排版 | 部分实现 | 坐标映射已实现；完整自动排版待确认 |
| F23 | 多版本兼容 | 部分实现 | SPB 16.6 主目标已实测；17.2/17.4 待验证 |

> 注：实现状态会随版本演进更新；任何状态与代码不一致时，以代码实际行为与 [STATUS.md](STATUS.md) 为准。

### 4. 非功能需求

#### 4.1 性能

| 指标 | 目标 |
|------|------|
| 单页原理图转换 | < 2 秒 |
| 100 页原理图项目 | < 5 分钟 |
| 器件匹配（1000 个器件） | < 30 秒 |
| GUI 响应 | < 500ms 界面不冻结 |

#### 4.2 可靠性

- 转换结果可通过 `Packager-XL` 成功导出网表
- 器件匹配准确率 > 95%（经过人工确认后 > 99%）
- 所有异常情况必须有日志记录，不静默失败

#### 4.3 可维护性

- 代码遵循统一的开发规范（详见 `CODING_STANDARDS.md`，已并入 STANDARDS.md Part I）
- 模块高内聚、低耦合
- 使用基类-注册模式实现可扩展的解析器/导出器/匹配器

#### 4.4 跨平台

- 优先支持 Windows（目标用户主要平台）
- Python 代码本身跨平台兼容
- GUI 选型考虑跨平台（PySide6）

### 5. 约束与假设

#### 5.1 约束

- 目标 HDL 版本：**Cadence SPB 16.6（主目标）**，兼容 17.2 / 17.4
- CIS 源版本：OrCAD Capture 16.6 及以上
- 不得要求用户安装完整的 Cadence 软件（解析层独立实现）
- 不需要用户在 OrCAD 中执行任何导出操作（直读 .dsn 二进制文件）
- 公司 HDL 库规范遵循《硬件设计规范》中定义的目录结构和文件格式
- BOM_SEQ 编码遵循公司统一编码规则

#### 5.2 假设

- CIS 原理图不包含仿真配置信息
- 公司 HDL 器件库结构已知且可读取
- 目标用户具备基本的 HDL 工程操作知识
- 单次转换的源项目不超过 500 页原理图

### 6. 术语表（关键项）

| 术语 | 缩写 | 含义 |
|------|------|------|
| OrCAD Capture CIS | CIS | Cadence 的原理图编辑工具（原 OrCAD 产品） |
| Design Entry HDL | HDL | Cadence 的原理图编辑工具（原 Concept HDL） |
| Schematic Page | 原理图页 | 一张独立的电路图纸 |
| Symbol / Part | 器件/符号 | 原理图中的元件图形符号 |
| Net | 网络 | 器件引脚之间的电气连接 |
| Pin | 引脚 | 器件的电气连接点 |
| Reference Designator | RefDes | 器件位号（如 R1, U3, C5） |
| Footprint / JEDEC_TYPE | 封装 | 器件的物理 PCB 封装 |
| Netlist | 网表 | 描述器件间连接关系的文本文件 |
| CFB / OLE | 复合文件二进制 | Microsoft 的 OLE 结构化存储格式 |
| Part Table | PTF | HDL 器件属性表 |
| chips.prt | PRT | HDL 器件管脚定义文件 |
| symbol.css | CSS | HDL 符号图形定义文件 |
| pstxnet.dat | XNET | Allegro 网络连接网表 |
| pstxprt.dat | XPRT | Allegro 器件-封装对应网表 |
| pstchip.dat | CHIP | Allegro 器件管脚定义网表 |
| BOM_SEQ | BSQ | 公司 BOM 编码：安装方式+器件类型+封装 |
| SN_NUM | SN | 公司物料编号 |
| MPN | MPN | Manufacturer Part Number |
| DNS / DNP / DNI | — | Do Not Stuff / Do Not Populate / Do Not Install |
| T0x10 | — | DSN 二进制格式中表示"引脚-网络连接点"的结构体 |
| PlacedInstance | — | DSN 二进制格式中表示"放置的器件实例"的结构体 |
| strLst | — | DSN Library 流中的全局字符串表 |
| FutureDataList | — | DSN 解析框架中的检查点边界追踪器 |

### 7. 参考基准数据

#### 7.1 公司 HDL 器件库规模

- **器件类别总数**：135 个目录
- **IC 类器件**：约 90 个（网络交换、WiFi/射频、PON、语音、MCU、接口等）
- **无源器件类**：约 20 个（电阻、电容、电感、磁珠、晶振、变压器等）
- **分立器件类**：约 10 个（二极管、LED、MOS管、三极管、光耦等）
- **特殊符号类**：约 15 个（电源/地符号、接插件、标记、安装孔等）

#### 7.2 已知 DSN 测试数据

universal-netlist 在 10 个 Cadence 开源设计中验证了解析器：
BeagleBoard-xM, BeagleBone-Black, CC13xxEM, CutiePi, LAUNCHXL-CC1310, 
reComputer J201/J202/J401, reServer J401/J2032

综合指标：Net 100%, Component 100%, Value 100%, PinNum 99.8%, PinName 96.0%

---

## 许可证

MIT License

---

## Phase XI P0 A-D 实施状态（2026-08-10 更新）

**核心进展**：P0 A-D（EDIF 连线数据解析 + con/xcon/csv/cpc 重构为 Cadence 真实格式 + CSA 连线生成 + DSN 禁用）已全部实施完成。测试基线 **364 passed / 23 skipped**。

### 新增能力

- **EDIF 为主数据源**：`use_dsn_components=False`（默认）——输入 .dsn 时自动优先同名 .EDF；DSN 对 RTL 变体是负资产（0 实例/3717 假网络），已旁路；pstxnet.dat 仍为权威网络注入
- **Cadence 真实 con/xcon 格式**：con 重写为 S-Expr（cells+terms / nets+scope / instances+pins+conn），xcon 填充 XML（lastids/cells/nets/aliases/netScopes/pages）——Packager-XL 可读取的基础
- **pageN.csv/cpc 生成**：每页 CONNECTIVITY 文件（网络编号 + $PN 引脚映射）+ 实例清单（#ISCELL/#CELL）
- **CSA 连线生成**：`WIRE 16 -1` + `LASTPIN $PN/SIG_NAME` + `DOT` + 每网 SIG_NAME 标签——DEHDL 原理图连线显示的基础（推翻 v0.9.0 "SPCOCN-1891 不支持连线" 的错误诊断）
- **页面结构**：EDIF 24 页正确划分（不再塌缩 1 页），页面尺寸从 pageSize 读取

### 已知限制（诚实声明）

1. **连线显示与网表导出尚未在 Cadence 16.6 实测**——静态断言（格式/坐标/语法）全部通过，需在装有 Cadence 的电脑验证
2. con instances 889 vs pstxnet 906（U6 主芯片 + 25 J-jumper 未在 CrossRef Catalog）
3. 引脚连接 2771 vs 2821（差异源于 Catalog 缺失实例）
4. 自动网名未转 UN$ 形式；off_page 522 vs 765（接口层）

### 详细文档

- [STATUS.md](STATUS.md) — Phase XI 状态/验收口径/任务跟踪
- [ROADMAP.md](ROADMAP.md) — Part V Phase XI（任务分解 + 实施记录）
- [system_design.md](system_design.md) — 权威系统设计（格式模板 + 验收断言）
- [ARCHITECTURE.md](ARCHITECTURE.md) — P0 架构补充
- [changelog_master.md](changelog_master.md) — 全量改动记录

---

## Phase XI P1 第二轮修复状态（2026-08-10 更新）

**P1 五子任务（Cadence 实测报错修复）全部完成**，测试基线 **387 passed / 23 skipped**。

### 本次修复

- **page.map 页码修复（P1-1）**：页码从 EDIF page_name 提取（`01-Cover_Page`→1）并按真实页码排序，不再用 enumerate 索引（修复 hierarchy viewer 页面标题错位 + ORCAP-11007 容错）
- **symbol.css 默认属性（P1-2）**：ch347/rf_sw/rj45_2x2_led 补 `$LOCATION/VALUE/PART_NAME/PATH` 声明（防 SPCOCN-542 属性丢失）
- **csa $LOCATION（P1-3）**：统一输出 `FORCEPROP 1 LAST $LOCATION`（实测发现 $LOCATION/LOCATION 是 OrCAD 实例级属性，04p4 单 section 绝大多数用 $LOCATION）
- **旋转/镜像/NC/电气类型存储（P1-4）**：EDIF `(orientation R90/MY...)` → ComponentInstanceIR.rotation/mirror（783+217）；67 个 NC 引脚 → nc_pins；SymbolPin 加电气类型字段
- **cpc mark 改 #CELL（P1-5）**：mark 符号不再输出 #ISCELL（8367/04p4 双实证）

### 两个前置问题

1. **ORCAP-11007**：源设计 TitleBlock 页码无效——转换器已容错（page.map 不依赖 title block），源设计侧需 `Tools→Annotate` 修复
2. **U6 双口径**：实测证明 pstxnet 同时含母 U6 与 U6A-I（引脚 100% 重叠），con 2821 = 3352 - 531 重复，**U6A-I 口径正确无引脚丢失**

### 已知限制

- rotation/mirror/NC 数据已存储但 **csa/csv 输出尚未消费**（DEHDL 旋转用 sym_N 视图映射，待后续）
- P1 全部为静态验证，**待 Cadence 实测**（连线显示/属性/网表导出）

---

## Phase XI P2 开发状态（2026-08-10 更新）

**P2 三项核心完成**，测试基线 **395 passed / 23 skipped**。

### 本次完成

- **P2-1 rotation→sym_N 视图映射**：EDIF orientation（R90/MY 等）→ 元件引脚偏移几何旋转（`rotate_point`），50.1% 元件方向正确显示（C97 R90 引脚横向验证）；绕开 sym_N 语义混合歧义（dc_dc 的 sym_N 是器件变体）
- **P2-2 NC 标记渲染**：67 个 NC 引脚不画网络标签/WIRE（无连接），保留 LASTPIN 引脚位置
- **P2-3 xcon netScopes**：确认格式与 8367 一致（双层结构 + 49 全局网），无需改动
- **ORCAP-11007**：完整操作步骤（Capture Tools→Annotate）已写入 STATUS §12.1

### 深度分析结论

- **已闭环** 26 项任务（P0/P1/P2 核心）
- **阻塞**：Cadence 实测（需用户环境）、特殊样本缺失（总线/多 section/标准 DSN）
- **可继续**：P0-C5 IOPORT 符号、P2-7 OLB 电气类型接通、信息页 CSA、csv 旋转

### 已知限制

- 旋转依赖 pstxprt.dat 的 ins_to_refdes 映射（主链已有）；缺则回退无旋转
- NC 引脚在 csa 中为孤立引脚（无连线，合理）
- 全部静态验证，**待 Cadence 实测**

---

## Phase XI 收尾完成（2026-08-10 更新）

**收尾五项全部完成**，测试基线 **424 passed / 1 skipped**（跳过从 23 降到 1）。

### 本次完成

- **P0-A3 off_page 765 完整**：页面级 522 + 设计级 243（EDIF 顶层 cell 的 offPageConnector 声明）= EDIF 文件 100%
- **P0-C5 跨页 IOPORT 符号**：每跨页连接输出 IOPORT 块（OFFPAGE TRUE + HDL_PORT INOUT），SIG_NAME 标签共存
- **P2-7 OLB 电气类型分析**：DEHDL csa 不消费普通引脚类型；chips.prt PINUSE 为可靠源
- **CH347 引脚修复**：chips.prt 功能名↔引脚号映射桥接，多引脚 IC 塌缩 0%
- **T17 DSN RTL 恢复**：8367 DSN 实例 0→578（RTL PlacedInstance 解析恢复）
- **fixture 补齐**：RTL8367RB DSN/EDF + LIBRARY2CLEAN.OLB（跳过 23→1）

### 架构师设计

`docs/system_design.md`（38247 字节，T01-T05 任务分解 + 共享知识 + 依赖图）+ class/sequence-diagram.mermaid

### 已知限制

- IOPORT/引脚方向/DSN RTL 解析均为静态验证，**待 Cadence 实测**
- 8367 pstxnet 导出测试需用户环境 pstx 文件
- U6 主芯片无匹配 hdl_lib 符号（数据限制，BGA 引脚无法匹配 CH347）

---

## Phase XIV 布线美观化（2026-08-11）

转换器新增布线/美观化可选项（全部默认关闭，零回归）：

```bash
# 默认转换（P0 车道法，与历史一致）
python -m cis2hdl convert <input>.DSN --output out/ --hdl-lib tests/fixtures/hdl_lib

# 可选：正交绕障（stub 避让元件体）
python -m cis2hdl convert <input>.DSN --output out_detour/ --hdl-lib ... --routing detour

# 可选：EDIF 折线复用（与原图连线一致）
python -m cis2hdl convert <input>.DSN --output out_edif/ --hdl-lib ... --routing edif_reuse

# 可选：文本去冲突 + 网络名对齐 + 差分对 P上N下
python -m cis2hdl convert <input>.DSN --output out_tl/ --hdl-lib ... --text-layout

# 可选：美观化总开关（去冲突+重叠检测+aesthetic_report.txt）
python -m cis2hdl convert <input>.DSN --output out_aes/ --hdl-lib ... --aesthetic

# 可选：人工确认匹配 → 软件自动配线（两阶段）
python -m cis2hdl convert <input>.DSN --output out/ --hdl-lib ... --export-unmatched unmatched.yaml
# 用户填写 unmatched.yaml 后：
python -m cis2hdl convert <input>.DSN --output out2/ --hdl-lib ... --manual-matches unmatched.yaml

# 可选：电源芯片匹配（--extra-hdl-lib 挂载 practice hdl_lib + power_ic 规则）
python -m cis2hdl convert <input>.DSN --output out_pic/ --hdl-lib ... --power-ic --extra-hdl-lib <dir>
```

配置：`cis2hdl/config/routing.yaml`（routing.mode / text_layout.enabled / overlap.check / manual_matches / power_ic.enabled / aesthetic.enabled）。

模块：`core/writer/{router_base,detour_router,edif_wire_reuse,text_layout,overlap_detector,aesthetic_report}.py` + `core/matcher/{manual_matches,power_ic_scorer}.py`。

测试：496 passed / 1 skipped。

---

## Phase XV Cadence 实测修复（2026-08-11）

转换器修复 Cadence 16.6 实测 7 类问题（SPCOCN-543/电容差一点/IO口/单GND/元件翻转/CH347/电线贴引脚）：

```bash
# 默认转换（p0，LASTPIN 格式已对齐 04p4、占位符号自动生成）
python -m cis2hdl convert <input>.DSN --output out/ --hdl-lib tests/fixtures/hdl_lib

# 美观化（用户对比版：电线明显不同——stub 引出段 + 绕障 + 每芯片 GND + IO 边缘分布）
python -m cis2hdl convert <input>.DSN --output out_aes/ --hdl-lib ... --aesthetic

# 独立开关（--aesthetic 已含以下两项，也可单独用）
python -m cis2hdl convert <input>.DSN --output out/ --hdl-lib ... --gnd-distribute --ioport-edge
```

关键行为：
- 主芯片（U6 等无 hdl_lib 符号）自动生成**占位符号**（贴合引脚数/名，标注 PLACEHOLDER），不再 fallback 错误符号 CH347
- $PN LASTPIN 格式与 04p4 参考一致（消除 SPCOCN-543 与"电容偏下差一点"）
- EDIF rotation 90↔270 互换（修复元件翻转 180°）
- GND 每芯片分布（规范要求）；跨页 IO 口右缘等间距（不再挤右上角）
- aesthetic 模式电线排布与默认**明显不同**（stub 引出段 +132% WIRE 段）

配置：`cis2hdl/config/routing.yaml`（routing.stub_lead / ioport.edge_layout / gnd_distribution.enabled / placeholder.enabled）。

测试：519 passed / 5 skipped。

---

## Phase XVI 镜像归一化 + IOPORT 审计（2026-08-11）

```bash
# 默认转换（镜像归一化已自动生效：EDIF mirror 实例引脚精确镜像 + 等效 R 行）
python -m cis2hdl convert <input>.DSN --output out/ --hdl-lib tests/fixtures/hdl_lib

# IOPORT 一致性核对（接线/网名/孤立三节报告）
python -m cis2hdl convert <input>.DSN --output out/ --hdl-lib ... --ioport-audit

# 美观化（含 [MIRROR] 报告节 + IOPORT 审计）
python -m cis2hdl convert <input>.DSN --output out_aes/ --hdl-lib ... --aesthetic

# 逃生舱：关闭镜像归一化（回归对照）
python -m cis2hdl convert <input>.DSN --output out/ --hdl-lib ... --no-mirror-normalize
```

关键行为：
- **镜像归一化**：EDIF 的 MX/MY/MYR90/MXR90 实例（原 L20"翻转 180°"根因）引脚坐标精确镜像 + 等效旋转 R 行；aesthetic_report 新增 [MIRROR] 节（154 个：134 精确 + 20 近似标注人工复核）
- **IOPORT 审计**：`ioport_audit_report.txt` 三节（UNWIRED 接线缺失 / NAME_CONFLICT 网名不一 / ORPHAN 孤立 connector）——HG5015 实测 unwired=0、conflict=1（wps/WPS）、orphan=7（auto-net）
- 电源符号（GND/VCC）镜像一致修复（LASTPIN 与 WIRE 端点精确重合）

配置：`cis2hdl/config/routing.yaml`（mirror.normalize / ioport.audit / ioport.skip_orphan / ioport.manual_names）。

测试：581 passed / 5 skipped。

---

## 诊断报告（Phase XVI 追加）

**默认转换即生成两个诊断报告**（输出根目录，只读不影响 CSA；`--no-report` 关闭）：

```bash
python -m cis2hdl convert <input>.DSN --output out/ --hdl-lib ...   # 默认
# → out/aesthetic_report.txt（[MIRROR] 镜像归一化清单 / [OVERLAP] 元件重叠 / [GRID] 网格）
# → out/ioport_audit_report.txt（[UNWIRED] 接线缺失 / [NAME_CONFLICT] 网名冲突 / [ORPHAN] 孤立 connector）
```

配置：`routing.yaml` → `report.always_write`（默认 true）/ `report.aesthetic` / `report.ioport_audit`。

---

## Phase XVII 调研与规划（2026-08-12）

> 本阶段为**调研+方案交付**（未改源码，测试 583/5 保持）。两版 Cadence 16.6 实测报错
> （errors_aes_08111200.txt / errors_aes6_08111718.txt）16 条根因分析 + 四项新需求方案
> （temp_lib 模拟图标 / GUI 手动配置 / 引脚匹配 / 默认模拟原理图）+ A* 布线开源方案深度调研。

### 报错现状（两版对比）

- 12:00 版（XIV aes）：SPCOCN-543 ×182、SPCOCN-515 ×13（芯片不渲染根因——占位符号未写入库）
- 17:18 版（XVI aes6）：SPCOCN-515 消除、SPCOCN-543 降到 116、新增 SPCOCN-542 ×15（PLACEHOLDER 属性被删）
- 量化问题：aes6 WIRE=12786 vs final 4911（+160%）、GND=541 vs 19（+28 倍）——"连接点/GND 过多"

### 新需求方案预览（未实现）

| 需求 | 方案 | 状态 |
|------|------|:---:|
| 匹配照常生成 csv/html | 匹配管线不动（硬约束） | 📋 规划 |
| temp_lib 模拟芯片图标 | `mock_icon_lib.py` 按硬件规范绘制，独立库不污染 hdl_lib | 📋 规划 |
| GUI 手动配置芯片/connector | `chip_config_panel.py`（复用 match_review 三栏+可编辑引脚映射表） | 📋 规划 |
| 引脚级匹配/悬空引脚 | `pin_connect_audit.py` + chip_config.yaml 注入 | 📋 规划 |
| 默认模拟图标原理图 | temp_lib 替代占位符号 + NOTE"模拟图标，无标准电气特性" | 📋 规划 |
| 重叠检测+腾挪 | `collision.py` 统一函数 + `placement_fitter.py` | 📋 规划 |
| 电线化简/GND 合并 | `wire_simplifier.py`（SKiDL cleanup_wires 移植） | 📋 规划 |
| 跨页网用网络名 | `net_name_connect.py`（IOPORT 默认不生成） | 📋 规划 |

### 关键调研结论（A* 美化布线开源方案）

- **SKiDL cleanup_wires**（MIT）：merge_segments 共线合并 / trim_stubs 删悬空 / remove_jogs 拐角化简 —— "电线爆炸/连接点过多"的现成解法，最高优先移植
- **OpenRAM**（BSD-3）：get_edge_cost 代价公式（线长+拐角×grid+方向×4）、inflate_shape 障碍膨胀、add_side_pin（GND 聚类）
- **KiCad**（GPL 抄思路）：SchematicCleanUp / MergeOverlap / EE_RTREE
- **结论**：不做全量 A*（固定布局过度设计）；化简后处理 + shapely 避让 + KMeans GND 聚类；A* 留远期自动布局

### 相关文档

- 完整问题清单：`docs/archive/temp files/phase17-problem-list.md`（16 条 + 17 条共性 → 7 类根因）
- 新需求方案：`docs/archive/temp files/phase17-requirement-scheme.md` + `system_design0812-phase17.md`
- A* 调研：`docs/archive/temp files/phase17-research-a-star-routing.md` + RESEARCH.md Phase XVII
- 状态/路线：STATUS.md §19-23 / ROADMAP.md XVI.1

---

## Phase XVII 开发完成（2026-08-12）

> P0 修复 + M1-M8 全部实现，QA 两轮验证闭环。测试 **662 passed / 5 skipped / 0 failed**。

### 新功能 CLI/配置速览

```bash
# 默认转换（temp_lib 模拟图标自动生成，未匹配芯片用 mock 图标替代占位方块）
python -m cis2hdl convert <input>.DSN --output out/ --hdl-lib tests/fixtures/hdl_lib
# → out/temp_lib/（模拟图标库）+ pin_audit_report.txt（引脚四状态审计）

# 电线化简（SKiDL cleanup_wires 移植：共线合并/悬空修剪/拐角化简/连接点合并）
python -m cis2hdl convert <input>.DSN --output out/ --hdl-lib ... \
  --routing detour   # + routing.yaml wire_simplify.enabled=true（或 CLI）

# 网络名跨页（IOPORT 522→0，CSA+con 同步去 IOPORT，用户 D2）
python -m cis2hdl convert <input>.DSN --output out/ --hdl-lib ... --use-net-name

# 人工配置（统一 chip_config.yaml v2.0，替代 manual_matches.yaml + mapping_rules.yaml）
python -m cis2hdl convert <input>.DSN --output out/ --hdl-lib ... --chip-config chip_config.yaml
# --manual-matches 保留为别名；v2.0 覆盖 v1.0 同 refdes
```

### 关键行为

- **temp_lib 模拟图标**：未匹配芯片生成 mock 图标（三档分布：≤12 两列 / 12-64 四列 / >64 BGA 矩形四边，引脚朝外 + 功能名标签 + 旋转对齐），CDS_LIB temp_lib + cds.lib DEFINE；图标标注 MOCK_TEXT"模拟图标，无标准电气特性"（中英双标字号 24）
- **SPCOCN-543 修复**：LASTPIN 坐标命中校验 + 旋转实例 SIG_NAME 移 WIRE + 引脚数不匹配跳 LASTPIN（真实根因=坐标未命中+旋转组合）
- **pin_audit_report.txt**：引脚四状态（connected/hanging/net_mismatch/pin_mismatch），悬空引脚保留 LASTPIN 不画 WIRE 待 Allegro 布线
- **统一配置文件**：chip_config.yaml v2.0（refdes/library_id/section/value/note/pin_map/hanging/placement），v1.0 自动升级，删除了 mapping_rules 冗余格式

### 配置（routing.yaml 新增）

```yaml
temp_lib: {enabled: true, lib_name: temp_lib, annotate: true}
wire_simplify: {enabled: false, dot_merge: 50, max_wire_len: 5000}
pin_audit: {enabled: true, report_hanging: true}
ioport: {use_net_name: false, ...}   # --use-net-name CLI 覆盖
```

### 已知限制（诚实声明）

- Cadence 16.6 未实测：BGA 四边标签渲染方向、MOCK_TEXT P 指令渲染（一行可改 X/T 指令）
- entity/pc.db 为最小 ASCII 声明（真实库二进制）
- M7 GUI 无 PySide6 环境未实测（降级占位）
- pin_mismatch 762 个反映既有匹配质量问题（后续单独评审）

测试：662 passed / 5 skipped / 0 failed。

---

## Phase XVII 三期：GND 聚类 + 8 版本对比包（2026-08-12）

> 测试 684 passed / 5 skipped。

### 新功能/配置

```bash
# GND 分布 + 聚类（就近共用，用户问题4）：GND 19→97
python -m cis2hdl convert <input>.DSN --output out/ --hdl-lib ... --gnd-distribute
# → routing.yaml gnd_distribution.cluster_radius=2000（0=关闭聚类）

# 电线化简（p0 模式，与默认同基线）：WIRE -32%
python -m cis2hdl convert <input>.DSN --output out/ --hdl-lib ... --wire-simplify
```

### 对比分析包（8 版本）

`HG5015_tests/output_phaseXVII_compare/`：v1 默认 / v2 短网先布 / v3 非均匀轨道 / v4 组合 / v5 detour+化简 / v6 网络名跨页 / **v7 p0+化简（-32%）** / **v8 GND 分布+聚类（GND 97）** + README + metrics_summary + SPN A/B 模板。

### 说明

- v5（detour+simplify）WIRE=6764 高于 v1（p0）=5031 是**布线模式差异**（detour stub 引出段），非功能问题；同基线化简对比看 v7（-32%）
- 三类合并功能均已实现：电线合并（v7 -32%）、连接点合并（T/X 真交点+dot_merge）、GND 聚类（v8）

测试：684 passed / 5 skipped / 0 failed。

---

## Phase XXI Cadence 16.6 实测 9 类问题修复（2026-08-14）

> 用户对 output_phaseXXII_compare 全量实测（逐页）反馈：SPCOCN-542/545 报错刷屏
> （P5-P24 全部页面，100% mock _PH 元件）+ 8 类视觉/布局问题。主理人齐活林
> 根因调查 + 工程师寇豆码实施 + QA 严过关两轮验证闭环。

### 本次修复（默认开启）

- **SPCOCN-542/545 报错消除**：mock symbol.css 补 4 个默认属性 P 声明
  （JEDEC_TYPE/PACKAGE_TYPE/DESCRIPTION/SN_NUM + MOCK_TEXT），对齐真实库 9 属性
  → Cadence 不再视实例属性为"未声明默认属性"删除（542）→ 545 STICKY 提示消失
- **MOCK 标识标签方式**：T 指令字号 59→**89**（1.5x）+ CSA 实例属性标签
  `FORCEPROP 1 LAST MOCK_TEXT MOCK` + DISPLAY 1.5 + **PAINT PINK**（04p4 先例，
  最接近红色；symbol 内 T 颜色受 Cadence 限制仍绿系，属性标签可上色）
- **引脚名锚点**：X PIN_TEXT 移到 tip 外 px±80（J4/S2 A1/A2 不再偏右）；C 短号贴
  outline 边（x0+25/x1-25，防外列 px 拉远后出框）
- **IC3 引脚名恢复**：pstchip.dat AMS1117 primitive（INPUT/OUTPUT/GND/TAP 引脚
  1-4）→ 替代 CH347 错误 fallback 引脚名（RST#/CTS/GPIO6）与占位 1-8
- **芯片尺寸拉宽**：字符宽 18→28、边距 355；U6H outline 宽 **3000**、U6I/U6A
  **2400**、U12 **1200**（按最长引脚名推断 + 用户目标值钳制）
- **引脚名零碰撞**：char_w 24/28 口径（字号 29 真实渲染宽）+ 列间距铁律
  `列距 ≥ max_len*28+255` + 重叠检测避让函数（用户 P13 授权）
- **U5_PH 310 键冲突修复**：BGA 引脚号（A7）与另一引脚功能名（A7）裸键覆盖
  → 名称键加 `"name:"` 前缀隔离（U5_PH 310 0、文本碰撞 0）
- **overlap_resolver 双重赋值 bug**：位移量从完整分离向量改为 real（减 margin），
  同坐标 J/T 组确定性偏移散开；max_passive_move 100→200
- **T 元件 4pin 高度**：n≤12 行距 100→50、y 起点 150→100 → 高度 400→250
- **电线穿元件体**：`wires_through_bodies` 检测 → aesthetic_report
  [WIRE_THROUGH_BODY] 节（P0 记录；完整绕障用 --routing detour）

### 测试与交付

- 全量 **840 passed / 6 skipped / 0 failed**（Phase XX 末 818 → 840，+22）
- 交付 `HG5015_tests/output_phaseXXIII_compare`（4 版本 + metrics + test_spn）
- QA 验证脚本 `scripts/verify_phaseXXI_package.py`（40 项全过）

### 详细文档

- [STATUS.md](STATUS.md) — §46-48 Phase XXI 全记录
- [ROADMAP.md](ROADMAP.md) — Phase XXI 排期与追加
- [changelog_master.md](changelog_master.md) — 全量变更日志
- `docs/archive/temp files/phase21-issues-and-plan.md` + `phase21-root-cause-evidence.md`

---

## Phase XXII 视觉/布局优化完整实现（2026-08-14）

> Phase XX 排期剩余任务（D1-D8）全量开发，产品经理 PRD → 架构师设计 →
> 工程师实施（3 轮含 QA 修复）→ QA 独立验证闭环。全量 **877 passed / 6 skipped**
> （Phase XXI 末 840 → 877，+37）。交付 `HG5015_tests/output_phaseXXIV_compare`
> （目录递增约定，用户防 Windows 重名）。

### 本轮实现（默认开启）

- **P0-1 三段式 stub 默认开（p0）**：DetourRouter 能力下沉到 WireLayoutEngine
  基类（Q2 统一实现）；**条件三段式**（QA 修复）——通畅 stub 1 段直连、仅受阻
  stub 走延伸→折线→调头，WIRE 段数收敛（10165 → 6708）
- **P0-2 避让 + 证据化豁免**：WIRE_THROUGH_BODY 报告**三口径 detected/exempt/
  violations**（QA 修复：旧 total 语义被误读）；豁免 reason∈{self-pin 自身引脚
  引出, power_symbol 电源网挂轨穿小体}；真违规 = violations
- **P0-3 net_name_endpoints 接线**：use_net_name 跨页悬空端补 SIG_NAME
  （单一调用点 + 去重）
- **P1-5 并联扩展到所有信号**：`plan_parallel_short` 路由前 hub 短接（非 GND
  同信号簇，PARALLEL_HUB_* 仅 route_map），L-path 2 段短接
- **P1-2 IO port 按网络聚类**：edge_layout 开启时按同网页内引脚 y 均值重排
- **P2-3 xcon 合并**：`_build_xcon_content` 全仓仅 1 处（xcon_writer 唯一源），
  内容字节级不变
- **P2-4 标签方向随元件**：--text-layout 开启后标签 R 行随元件旋转（默认关）
- **P1-7 aes LASTPIN miss 归零**：key 前置 + `_pin_offset_map` 同源 +
  OverlapResolver 位移后 snap50 → aes `[LASTPIN_MISS] total=0`

### QA 关键发现（工程师 3 轮修复）

- **WIRE +108% 收敛**：初版三段式对每根 stub 引出 → 条件三段式（QA round-2）
- **报告语义误读**：`[WIRE_THROUGH_BODY] total=N` 实际是**非豁免真违规数**
  （QA round-3 实锤）→ 三口径重构 + reason 豁免类别
- 未豁免 violations=506（v9_default）：电源网 trunk 穿体（电气正常）+ 密集页
  trunk 穿大体（trunk 级完整绕障属 detour，README 已知限制）

### 详细文档

- [STATUS.md](STATUS.md) — §49-51 Phase XXII 全记录
- [ROADMAP.md](ROADMAP.md) — Phase XXII 排期完成 + 剩余
- [changelog_master.md](changelog_master.md) — 全量变更日志
- `docs/archive/temp files/phase22-prd.md` / `phase22-system-design.md` / `phase22-qa-report.md`

---

## Phase XXIII 三项未开发任务完成（2026-08-14）

> Phase XX/XXI/XXII 排期清点后剩余的 3 项"增强/资源类"任务中，3 项代码类
> 全部完成（GND 分布增强 P1-3 / 电阻旋转感知 P1-4 / trunk 避让 R-2）。
> 全量 **929 passed / 6 skipped / 0 failed**（877 → 929，+52）。
> 交付 `HG5015_tests/output_phaseXXV_compare`（目录递增）。

### 本轮完成

- **P1-3 GND 分布增强**：`ensure_gnd_symbols` 密度补点（页面 1/4 分块 + 距符号 >1500 触发）+ GND 网 trunk 避让余量 + outlet 绕行；开关 `gnd.distribute_density`（默认关，--gnd-distribute 开启）
- **P1-4 电阻旋转感知**：`apply_passive_orientation` 二端元件（R/L/FB/BEAD）方向随连线（Δx>Δy 水平 / Δy>Δx 垂直 + outline swap）；开关 `placement.rotate_passives`（默认关，--rotate-passives 开启）；一致率 100%、310 重叠 0
- **R-2 trunk 避让**：`_avoid_outlines` span 感知推离（推离所有重叠 outline 的最大扩展）+ `route_nets` 冲突计数优先；**violations 506 → 457**（trunk 穿体彻底归 0，trunk_blocked=0）；WIRE 6708 → 6492（不增反降）；报告分项 trunk_blocked/non_trunk（QA 修正避免语义误读）

### 详细文档

- [STATUS.md](STATUS.md) — §52-54 Phase XXIII 全记录
- [ROADMAP.md](ROADMAP.md) — Phase XXIII 完成 + 剩余
- [changelog_master.md](changelog_master.md) — 全量变更日志
- `docs/archive/temp files/phase23-incremental-design.md` / `phase23-qa-report.md`
