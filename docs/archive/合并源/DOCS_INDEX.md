# CIS2HDL 文档地图（DOCS_INDEX）

| 项目 | 值 |
|------|-----|
| 文档版本 | v1.0（2026-08-07 建立） |
| 项目版本 | v1.1.0（匹配系统 v2.0） |
| 状态 | 现行文档地图（docs/ 目录索引 + archive/ 归档区索引 + 元信息块规范） |
| 关联文档 | [README.md](README.md) · [STATUS.md](STATUS.md) · [KNOWN_ISSUES.md](KNOWN_ISSUES.md) · [TIMELINE.md](TIMELINE.md) |

---

## 1. docs/ 现行权威文档清单

> 全部现行权威文档位于 `docs/` 根目录平铺存放（已核实：`design/`、`specs/` 子目录不存在，相关文档均在 `docs/` 根与 `docs/archive/` 下）。以下按内容主题分为 7 组，路径均为实际路径。

### 1.1 门户与状态

| 文档 | 一句话定位 |
|------|-----------|
| [`README.md`](README.md) | 项目门户：概述、核心能力、状态 badge、常用文档入口、技术栈、快速开始 |
| [`STATUS.md`](STATUS.md) | **当前状态权威**：版本 v1.1.0、测试基线 268+23、阶段完成度、匹配指标、12 项遗留 |
| [`DOCS_INDEX.md`](DOCS_INDEX.md) | 本文档：docs 目录地图 + archive 归档区索引 + 文档元信息块规范 |
| [`TIMELINE.md`](TIMELINE.md) | 研发时间线：7/29 项目启动 → 8/7 v1.1.0（日期/版本/事件/测试数） |
| [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) | 技术债与已知问题清单（六类，含状态/优先级/来源/建议动作） |

### 1.2 需求

| 文档 | 一句话定位 |
|------|-----------|
| [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) | 需求总纲：业务/功能/非功能需求 F01-F23、术语表、参考基准数据（含 §3.5 实现状态） |

### 1.3 架构设计

| 文档 | 一句话定位 |
|------|-----------|
| [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md) | 系统架构权威：四层架构、IR 模型、模块划分、包结构 |
| [`COMPONENT_ARCHITECTURE.md`](COMPONENT_ARCHITECTURE.md) | 器件模型权威：CIS/HDL 器件格式对比、ComponentDef 模型、数据库设计 |
| [`BACKEND_DESIGN.md`](BACKEND_DESIGN.md) | 后端详细设计：IR、解析/匹配/校验/生成各层接口 |
| [`system_design.md`](system_design.md) | 匹配 v2.0 设计权威：两阶段架构类图/时序图/任务分解 |
| [`MATCHING_ANALYSIS_2026-08-06.md`](MATCHING_ANALYSIS_2026-08-06.md) | v1.0 vs v2.0 匹配系统根因分析（MultiScorer 失败路线复盘） |
| [`class-diagram.mermaid`](class-diagram.mermaid) | 匹配 v2.0 类图（Mermaid） |
| [`sequence-diagram.mermaid`](sequence-diagram.mermaid) | 匹配 v2.0 时序图（Mermaid） |
| [`DIAGNOSTICS_AND_RECOVERY.md`](DIAGNOSTICS_AND_RECOVERY.md) | 诊断系统设计：文件完整性、错误码、降级恢复路径 |
| [`FRONTEND_DESIGN.md`](archive/合并源/FRONTEND_DESIGN.md) | 前端 GUI 设计源文档：PySide6 布局、交互流程、组件设计（已归档 archive/合并源/） |

### 1.4 规范标准

| 文档 | 一句话定位 |
|------|-----------|
| [`CODING_STANDARDS.md`](CODING_STANDARDS.md) | 编码规范：命名、代码复用、变量定义、框架设计、UI 颜色引用 |
| [`UI_DESIGN_SPEC.md`](UI_DESIGN_SPEC.md) | UI 设计规范：Anthropic Token 体系、配色、组件样式、PySide6 实现指南 |
| [`DEVELOPMENT_SOP.md`](DEVELOPMENT_SOP.md) | 开发流程 SOP：功能开发、Bug 修复、Code Review、强制 CHANGELOG+文档+回归测试 |
| [`HDL_SCHEMATIC_STANDARDS.md`](HDL_SCHEMATIC_STANDARDS.md) | HDL 原理图标准：排版自动化、库导入、BOM_SEQ、版本兼容 |
| [`硬件设计规范.docx`](硬件设计规范.docx) / [`硬件设计规范.pdf`](硬件设计规范.pdf) | 外部权威：公司 DEHDL 设计规范（母本/阅读版） |

### 1.5 研发管理

| 文档 | 一句话定位 |
|------|-----------|
| [`CHANGELOG.md`](CHANGELOG.md) | 唯一版本权威：所有版本变更记录（已补录 v1.0.0/v1.1.0 ✅，2026-08-07） |
| [`ROADMAP.md`](ROADMAP.md) | **合并后权威路线图**：Part I 初始愿景 + Part II 阶段审计 + Part III 最新状态/裁决（源文档 DEVELOPMENT_ROADMAP.md / ROADMAP_AUDIT_2026-08-03.md 已归档 archive/合并源/） |
| [`ROADMAP_AUDIT_2026-08-03.md`](archive/合并源/ROADMAP_AUDIT_2026-08-03.md) | 阶段审计源文档（已并入 ROADMAP.md Part II/III，源文件存于 archive/合并源/） |
| [`DEVELOPMENT_ROADMAP.md`](archive/合并源/DEVELOPMENT_ROADMAP.md) | 初始设计愿景源文档（已并入 ROADMAP.md Part I，源文件存于 archive/合并源/） |
| [`fix_proposal.md`](fix_proposal.md) | Cadence 兼容性修复档案（P0×4/P1×4/P2×4，12 项已实施） |
| [`MEMORY.md`](MEMORY.md) | 项目长期记忆：关键决策、版本演进、遗留事项（与 .workbuddy/memory 去重关系待标注） |
| [`handoff-20260807-113237.md`](handoff-20260807-113237.md) | 匹配 v2.0 交接文档：STATUS.md 的状态源（建成后拟移入 archive/handoff/） |

### 1.6 调研参考

| 文档 | 一句话定位 |
|------|-----------|
| [`RESEARCH_REPORT.md`](RESEARCH_REPORT.md) | 技术调研报告：Cadence 生态、开源方案、技术路径 |
| [`ORCAD_SOURCE_ANALYSIS.md`](ORCAD_SOURCE_ANALYSIS.md) | OrCAD 源文件深度分析：28,205 个安装文件（XSD/HDL/cds.lib/BOM） |
| [`REFERENCE_READING_NOTES.md`](REFERENCE_READING_NOTES.md) | 参考项目精读笔记：CIStoHDL_standard 逐文件分析 |
| [`FILE_INDEX_AND_MAPPING.md`](FILE_INDEX_AND_MAPPING.md) | 文件索引与映射：当前项目/参考库文件清单与映射关系 |
| [`_ref_file_list.csv`](_ref_file_list.csv) | 参考库结构索引（CSV） |

### 1.7 验证测试

| 文档 | 一句话定位 |
|------|-----------|
| [`VERIFICATION_GUIDE.md`](VERIFICATION_GUIDE.md) | 验证指南唯一权威：Part I 现行 HG5015（24 CSA/889/3717）+ Part II 历史（RTL8367RB/HG5015） |
| [`VERIFICATION_GUIDE_HG5015.md`](archive/合并源/VERIFICATION_GUIDE_HG5015.md) | HG5015 验证指南源文档（已并入 VERIFICATION_GUIDE.md Part II.2，源文件存于 archive/合并源/） |
| [`2608041210report.md`](archive/合并源/2608041210report.md) | HG5015 DSN 二进制解析算法报告（8/4，已归档 archive/合并源/） |

### 1.8 文档工具

| 文档 | 一句话定位 |
|------|-----------|
| [`_gen_cmp_pt1.py`](_gen_cmp_pt1.py) | 可复用对比报告生成脚本 |
| [`_gen_imp.py`](_gen_imp.py) | 可复用改进方案生成脚本 |

---

## 2. docs/archive/ 归档区索引

> 归档区存放全部历史文档（只归档不删除）。子目录 → 内容 → 旧名 → 新位置映射如下。历史文档保留原始文件名便于检索与追溯。

| 子目录 | 内容 | 映射说明 |
|--------|------|----------|
| `archive/日志/` | 9 份日期工作日志（2026-07-22 ~ 2026-08-06） | 原 `docs/2026-07-29.md` 等 9 份日志 → `docs/archive/日志/`。其中 **2026-07-22.md / 2026-07-23.md 为 waveform_viewer 项目日志（非 CIS2HDL）**，仅归档不并入主线（详见 TIMELINE） |
| `archive/handoff/` | 4 份历史交接文档（handoff-20260805-103417 / 20260805-160515 / 20260806-085237 / 20260806-161951） | 原 `docs/handoff-20260805-*.md` 与 `docs/handoff-20260806-*.md` → `docs/archive/handoff/`。**handoff-20260807-113237.md 暂留 docs/ 根作 STATUS 状态源** |
| `archive/废弃设计/` | 5 份废弃设计（system_design08061513.md、class-diagram08061513.mermaid、sequence-diagram08061513.mermaid、MATCHING_DIAGNOSIS_2026-08-04.md、CIS2HDL_IMPROVEMENT_DOC.md） | v0.9.0 时代匹配方案与旧图，已被匹配 v2.0 取代 → `docs/archive/废弃设计/` |
| `archive/过程文档/` | 过程临时文档（_audit_code.md、_audit_tests.md、_implementation_log.md、_improvement_plan.md、_qa_report.md、_refactor_log.md、_test_reorg_log.md、binary_diff_report.md、validation_report.md、FILE_COLLECTION_CHECKLIST.md、PHASE2_DESIGN.md、PRD_v0.5.1_incremental.md、temp.txt、test1.md） | 带 `_` 前缀的审计/过程文档与一次性报告 → `docs/archive/过程文档/`（其中 _audit_code.md 技术债已收纳进 KNOWN_ISSUES） |
| `archive/运行快照/` | 8 份运行/测试快照（_rtl_result.txt、convert_output.log、errors08060847.txt、hg5015_verify.txt、test_output.txt、test_output_round2.txt、test_output_20260807_291collected.txt、tests_output.txt） | 一次性调试输出与测试快照 → `docs/archive/运行快照/`（errors08060847.txt 为 CSA 尾部页历史缺陷证据，见 KNOWN_ISSUES ③；test_output_20260807_291collected.txt 为 291-collected 运行快照，2026-08-07 实测） |
| `archive/合并源/` | 10 份合并源文档（DEVELOPMENT_ROADMAP.md、ROADMAP_AUDIT_2026-08-03.md、FRONTEND_DESIGN.md、HDL_OUTPUT_FIX_PLAN.md、_comparison_report.md、_reference_index.md、reference_project_file_list.md、2608041210report.md、test1.txt、VERIFICATION_GUIDE_HG5015.md） | 各合并源主目标：DEVELOPMENT_ROADMAP.md / ROADMAP_AUDIT_2026-08-03.md → ROADMAP.md；FRONTEND_DESIGN.md → UI_DESIGN_SPEC.md（前端 GUI 设计，§13 交互流程）；HDL_OUTPUT_FIX_PLAN.md → fix_proposal.md（附录根因链）；_comparison_report.md → HDL_SCHEMATIC_STANDARDS.md（比特级比对来源）；_reference_index.md / reference_project_file_list.md → FILE_INDEX_AND_MAPPING.md（A.1 参考库索引）；2608041210report.md → SYSTEM_ARCHITECTURE.md（HG5015 解析算法正式归宿）；test1.txt → VERIFICATION_GUIDE.md 九（BOM 交叉验证方法论）；VERIFICATION_GUIDE_HG5015.md → VERIFICATION_GUIDE.md Part II.2 |
| `archive/清单快照/` | 1 份文件清单快照（_cis2hdl_file_list.csv） | 2026-08-03 全量文件清单快照（含 .venv 噪音与 nul 条目，已过期） → `docs/archive/清单快照/` |

---

## 3. 文档元信息块规范

**适用范围**：docs/ 下全部现行权威文档（README、STATUS、PROJECT_OVERVIEW、架构/规范/管理/调研/验证类文档）建议在文档开头放置元信息块，防止版本/数字口径漂移。

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

*本文档为 docs/ 目录地图，随文档新增/归档更新。*
