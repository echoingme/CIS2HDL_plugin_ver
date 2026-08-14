# CIS2HDL 文档体系整合总档（consolidation260807）

> **文档介绍**：本档定位为 CIS2HDL docs 体系整合的完整方案与执行记录总档，将 2026-08-07 首次整合（方案 + 执行报告）与二次合并（方案 + 执行报告）共 4 份文档全文保真收录、分卷组织，并预留后续 plan/report 追加区（Part V）。
>
> **来源清单（4 份）**：
> 1. `docs_consolidation_plan_2026-08-07.md`（289 行）→ **Part I　首次整合方案**
> 2. `docs_consolidation_report_2026-08-07.md`（89 行）→ **Part II　首次整合执行报告**
> 3. `docs_merge_plan_2026-08-07.md`（74 行）→ **Part III　二次合并方案**
> 4. `docs_merge_report_2026-08-07.md`（63 行）→ **Part IV　二次合并执行报告**
>
> **合并原则**：全文保真（源文档每行原样收录，不做内容删减）+ 分卷组织（Part I~IV 对应 4 份源文档）+ 标题降级（源 H1→H2、H2→H3、H3→H4）+ 表格/代码块/列表/引用原样保留、代码围栏配对核对。
>
> **后续 plan/report 追加说明**：本档建立（2026-08-07）之后的整合工作统一追加写入 **Part V（后续工作记录）**；后续产生的 plan/report 类内容（如废弃设计合并、过程文档合并、README 等更新）追加至 Part V，并同步更新本文档头部"来源清单"与文末"合并保全声明"中的行数统计。

## 目录

- [Part I　首次整合方案（原 docs_consolidation_plan_2026-08-07.md 全文）](#part-i)
- [Part II　首次整合执行报告（原 docs_consolidation_report_2026-08-07.md 全文）](#part-ii)
- [Part III　二次合并方案（原 docs_merge_plan_2026-08-07.md 全文）](#part-iii)
- [Part IV　二次合并执行报告（原 docs_merge_report_2026-08-07.md 全文）](#part-iv)
- [Part V　后续工作记录（2026-08-07 追加）](#part-v)
- [合并保全声明](#merge-declaration)

<a id="part-i"></a>

## Part I　首次整合方案（原 docs_consolidation_plan_2026-08-07.md 全文）

> **来源**：`docs_consolidation_plan_2026-08-07.md`（289 行）全文收录；标题按"源 H1→H2"规则整体降级一级。

## CIS2HDL docs 目录文档体系整合方案

- **编制**：章成文（主理人/总编辑）· 专业文档生成团队
- **日期**：2026-08-07
- **状态**：待用户确认（本方案仅为调研产出，**未对任何文件做改动**）
- **调研规模**：docs/ 目录 78 份文件全量精读（7 路并行检索）+ 与代码库逐项核对 + 2 项实测验证（测试基线、GUI 框架）

---

### 一、调研概况

| 项 | 结果 |
|---|---|
| 精读文件数 | 78 份（md 60 / txt 9 / csv 2 / py 2 / mermaid 4 / pdf 1 / docx 1） |
| 核对代码范围 | cis2hdl/core/{parser,matcher,writer,validator,ir,engine,db,diagnostics}、gui/、config/、tests/、HG5015_tests/、docs_for_reference/ |
| 实测验证 | ① `pytest tests/unit tests/integration tests/e2e -q` → **268 passed / 23 skipped / 0 failed**；② GUI 框架 grep 验证 → **PySide6**（handoff 中 PyQt5/tkinter 记载均错） |
| 处置判定 | 权威保留（更新）21 份 ｜ 合并后归档 8 份 ｜ 直接归档 32 份 ｜ 移出/删除候选 10 份 ｜ 待新增 6 份 |

> 7 份精读报告原始出处：doc-researcher-1~7（本方案已交叉合并，冲突点以代码与实测为准裁决）。

---

### 二、全局诊断（十大核心问题）

#### P1 版本号四处口径混乱（最严重）
- `pyproject.toml`=0.3.5 ｜ `cis2hdl/__init__.py`=0.5.0 ｜ README badge=0.3.5 ｜ `CHANGELOG.md` 最新条目=v0.9.0（2026-08-06）
- **真实最新 = v1.1.0（匹配系统 v2.0）**，证据：代码 matcher/ 目录 v2.0 模块齐备、handoff-20260807 标题与正文、docs/MEMORY.md
- CHANGELOG 缺 v1.0.0 / v1.1.0 条目，且自身有重复 v0.5.0 条目 ×2、0.4.5 日期乱序
- **裁决**：CHANGELOG 为唯一版本权威，需补录；建立"三处同步"强制规则（__init__.py / pyproject / CHANGELOG / README）

#### P2 测试数多口径并存（至少 6 个数字）
137（08-03）→ 192（validation_report）→ 243/6（handoff，248 collected）→ 255/13（test_output_round2，268 collected）→ **268/23（本次实测，291 collected）**
- 差异根源：范围（unit vs unit+integration vs +e2e）+ 时点（同一天测试持续新增）
- **裁决**：统一命令 `pytest tests/unit/ tests/integration/ tests/e2e/ -q`，文档引用必须同时记录 collected/passed/skipped 三项与日期；历史数字标注"历史口径"

#### P3 匹配架构描述大面积过时
- SYSTEM_ARCHITECTURE / COMPONENT_ARCHITECTURE / BACKEND_DESIGN / PHASE2_DESIGN / _comparison_report / _reference_index 均写"四级管道（Exact→Fuzzy→Feature→Manual）"
- 实际已重构为 **v2.0 两阶段**（TypeHypothesis → CandidatePool → PassiveMatcher 5 级 / ActiveMatcher 5 维，final_conf=prior×within，STOP_SEARCH=0.75 / NEEDS_REVIEW=0.40）；MultiScorer 已删除
- **裁决**：全部升级为 v2.0 描述；system_design08061513.md（v0.9.0 方案）整体归档为"失败路线"演进史

#### P4 目录/路径描述与实际大面积偏离
- 文档写 `core/generator/`（实际 `core/writer/`）、`core/engine.py`（实际 `core/engine/` 目录）、`core/version/`（不存在）、`core/layout/`（不存在）、`cli/`（不存在，CLI 走 `__main__.py`）
- **README 文档索引全部失效**：指向不存在的 `design/`、`specs/` 子目录（实际平铺 docs/）
- GUI 描述差异：FRONTEND_DESIGN 依赖树含不存在的 status_indicator.py / models/；实际多了 sidebar/summary_bar/diagnostic_panel 等 10 个文件
- **裁决**：SYSTEM_ARCHITECTURE 包结构树按实际代码重画；README 索引修正；FRONTEND_DESIGN 并入 UI_DESIGN_SPEC；未落地项（version/layout）标注"规划未实施"

#### P5 重复文件（docs 与工作记忆目录）
- docs/ 下 9 份日期日志与 `D:\26暑假\.workbuddy\memory\` 同名文件**字节级重复**；docs/MEMORY.md 与工作记忆 MEMORY.md 相同（5763B，同为 08-07 08:56）
- 07-22 / 07-23 两份日志实为 **waveform_viewer 项目**（非 CIS2HDL），归属错误
- **裁决**：工作记忆目录为源；docs 内拷贝归档；waveform_viewer 两份移出

#### P6 验证指南数字失真（会导致"工具正确但验证误判失败"）
- VERIFICATION_GUIDE：声称 136 tests、引用 3 个不存在的测试文件（test_config/test_csa_writer/test_edif_parser）、主验证对象 RTL8367RB 已被 HG5015 取代
- VERIFICATION_GUIDE_HG5015：声称 20 pages/1001 inst/4115 nets，**实际 24 CSA（20 原理图+4 信息页）/889 元件/3717 网络**（已核对 HG5015_tests 输出目录）
- **裁决**：两份合并为一份，以 HG5015 为主验证对象，预期值刷新为 24/889/3717

#### P7 错误码口径 31 vs 39
- CODING_STANDARDS / DIAGNOSTICS / SYSTEM_ARCHITECTURE / BACKEND 写 31；PHASE2_DESIGN 已更新 31→39
- **裁决**：以 39 为准（与 error_diagnosis.py 实际一致），全部文档统一

#### P8 PAINT WIRE 状态矛盾（需产品决策）
- 8-06 handoff：PAINT WIRE"已移除（SPCOCN-1891）"；docs/MEMORY： "7 页 16 段已渲染"；ROADMAP_AUDIT：X-8 记录"7页16段"
- **代码核验**：`csa_writer.py` `_build_wire_segments()` 生成器存在（L793-844）但**无任何调用点** → 当前实际不输出；dsn_parser wire_net_map 始终构建
- "7页16段"未在任何本地文件中出现（应来自 Cadence 侧会话日志，未入库）
- **裁决**：方案建议"如实标注为未启用"，是否接线/移除由用户决策（见决策点 D2）

#### P9 技术债散落各处无汇总
- _audit_code 未修复项：C3 run_stage dict dispatch、B5 session_name 'ProjectMgr3606' 硬编码、B3 page_name='DDR3' 默认值、F2 _Countable
- handoff-20260807 已知限制 12 项（含 P0：v2.0 输出未二次实测、conversion_engine 调试 print 待清理、CHANGELOG/ROADMAP 待更新）
- errors08060847 反映的 CSA 尾部页崩溃（bad token ×237 等）、DSN refdes 乱码（可读率 12.7%）等遗留证据
- 潜在缺陷：weights.yaml 头注释仍写"MultiScorer dimension weights"，且 GUI 权重编辑写入该文件但 ActiveMatcher 用硬编码权重、**GUI 编辑实际不生效**
- **裁决**：新建 KNOWN_ISSUES.md（技术债清单）统一收纳，替代散落记录

#### P10 文档缺失两块
- 缺 docs 目录自身的**文档索引**（_reference_index.md 是参考项目索引，不是 docs 索引）
- 缺**研发过程时间线**（信息散在 9 份日志 + 5 份 handoff 中）
- **裁决**：新建 DOCS_INDEX.md（文档地图）与 TIMELINE.md（7/29→8/7 时间线，已从 R6 报告中取得现成骨架）

---

### 三、目标文档体系（整合后 docs/ 目录结构）

```
docs/
├── README.md                    ← 项目门户（更新：版本/测试/索引路径/匹配描述）
├── DOCS_INDEX.md                ← 【新增】文档地图（本体系索引，含归档区索引）
├── STATUS.md                    ← 【新增】项目当前状态（版本 v1.1.0 / 测试 268+23 / 阶段完成度 / 遗留 12 项）
├── KNOWN_ISSUES.md              ← 【新增】技术债与已知问题清单（收纳 P9 全部散落项）
├── TIMELINE.md                  ← 【新增】研发过程时间线（7/29 启动 → 8/7 v2.0）
│
├── 1_需求/
│   ├── PROJECT_OVERVIEW.md      ← 需求总纲（更新：功能状态、版本口径）
│   └── PRD_v0.5.1_incremental.md← 历史 PRD（归档保留，标注已执行/已撤销项）
│
├── 2_架构设计/
│   ├── SYSTEM_ARCHITECTURE.md   ← 架构权威（重画包结构树、匹配 v2.0、吸收 2608041210 解析算法笔记）
│   ├── COMPONENT_ARCHITECTURE.md← 器件模型权威（更新匹配章节；吸收 _audit_code 技术债）
│   ├── BACKEND_DESIGN.md        ← 后端详设（更新匹配/错误码 39/EDIF 角色/PST；与 SYSTEM_ARCHITECTURE 去重）
│   ├── system_design.md         ← 匹配 v2.0 设计权威（修正类图 6 处方法名、补 fixed_prefixes/RD/weights.yaml）
│   ├── MATCHING_ANALYSIS_2026-08-06.md ← v2.0 根因分析权威（加注 type_gate.yaml 实现差异）
│   ├── class-diagram.mermaid    ← 按代码修正方法名后保留
│   ├── sequence-diagram.mermaid ← 修正 2 处（_from_yaml / match_typed 非链调用）后保留
│   ├── DIAGNOSTICS_AND_RECOVERY.md ← 诊断系统设计（标注"已全部实施"、错误码 39）
│   └── PHASE2_DESIGN.md         ← 历史设计+验收记录（归档）
│
├── 3_规范标准/
│   ├── CODING_STANDARDS.md      ← 编码规范（修正异常层次、错误码 31→39）
│   ├── DEVELOPMENT_SOP.md       ← 流程 SOP（修正环境命令、补 CHANGELOG 纪律）
│   ├── HDL_SCHEMATIC_STANDARDS.md ← 排版/库/BOM 规范（吸收 test1.md Cadence 经验 + _comparison 格式差异表）
│   └── 硬件设计规范.docx / .pdf ← 外部权威（公司 DEHDL 设计规范，保留引用）
│
├── 4_研发管理/
│   ├── CHANGELOG.md             ← 唯一版本权威（补录 v1.0.0/v1.1.0、合并重复 v0.5.0、修正日期乱序）
│   ├── ROADMAP_AUDIT_2026-08-03.md ← 阶段状态主文档（补 Phase VI-X + v1.1.0 章节）
│   ├── DEVELOPMENT_ROADMAP.md   ← 初始设计愿景（标注历史边界，保留四阶段总览）
│   ├── DEVELOPMENT_SOP 相关（见 3_）
│   └── fix_proposal.md          ← 兼容性修复档案（吸收 HDL_OUTPUT_FIX_PLAN，标注 12 项全部已实施）
│
├── 5_调研参考/
│   ├── ORCAD_SOURCE_ANALYSIS.md ← 权威（修正 standard 计数/章节编号）
│   ├── REFERENCE_READING_NOTES.md ← 权威（补 writer 映射）
│   ├── RESEARCH_REPORT.md       ← 更新（StructureType 修正、器件数 135→131、.sch 推断标注废弃）
│   ├── FILE_INDEX_AND_MAPPING.md ← 更新（按 08-07 代码树刷新清单；吸收 _reference_index / reference_project_file_list）
│   └── _ref_file_list.csv       ← 保留（参考库结构索引）
│
├── 6_验证测试/
│   └── VERIFICATION_GUIDE.md    ← 合并 HG5015 版为唯一验证指南（HG5015 主对象，预期 24 CSA/889/3717）
│
├── 7_文档工具/
│   ├── _gen_cmp_pt1.py          ← 保留（可复用对比报告生成脚本）
│   └── _gen_imp.py              ← 保留（可复用改进方案生成脚本）
│
├── archive/                     ← 【新增】历史归档区（见处置表 C/B 类）
│   ├── 日志/（9 份日期日志，含 waveform_viewer 2 份移至其项目目录）
│   ├── handoff/（4 份历史交接；handoff-20260807 暂留根目录作状态源，STATUS.md 建成后归档）
│   ├── 废弃设计/（system_design08061513 + 旧 mermaid ×2 + MATCHING_DIAGNOSIS + CIS2HDL_IMPROVEMENT_DOC）
│   ├── 过程文档/（_ 前缀 9 份 + 2608041210report + test1 + test1.txt + temp.txt + binary_diff_report + validation_report + FILE_COLLECTION_CHECKLIST + reference_project_file_list + PRD + PHASE2_DESIGN）
│   ├── 运行快照/（_rtl_result / hg5015_verify / convert_output / test_output / test_output_round2 / tests_output / errors08060847）
│   └── 清单快照/（_cis2hdl_file_list.csv）
│
└──（待删除确认项见处置表 D 类，不建目录）
```

**设计原则**：
1. docs/ 根目录只保留"现行权威文档"（≤30 份），全部历史进 archive/，删除候选需用户逐项确认
2. 权威文档头部统一加「文档元信息块」（版本/日期/状态/关联文档），防止再次漂移
3. 文档命名规范：正式文档无前缀；历史文档归档时不改名（保留原始文件名便于检索与追溯）
4. 文档交叉引用统一用相对路径 + 章节锚点

---

### 四、逐份处置表（78 份）

#### A. 权威保留（更新后，21 份）

| # | 文件 | 更新要点 |
|---|---|---|
| 1 | README.md | 版本 0.3.5→v1.1.0；测试 201→268+23；索引路径修正（docs/ 平铺）；匹配描述改 v2.0；CLI 已实现 |
| 2 | PROJECT_OVERVIEW.md | 功能表标注实现状态（F21 CLI 已实现）；版本口径对齐；保留需求基线 |
| 3 | SYSTEM_ARCHITECTURE.md | 包结构树重画（writer/、engine/ 目录、无 version/layout/cli）；匹配 v2.0；错误码 39；吸收 2608041210 解析算法 |
| 4 | COMPONENT_ARCHITECTURE.md | 匹配章节改 v2.0；ComponentDBSerializer 标注未落地；IR 模型补充 extra_data 字段 |
| 5 | BACKEND_DESIGN.md | 匹配层 v2.0；错误码 39；EDIF 角色改为 pin 注入；补 PST 数据源；与 SYSTEM_ARCHITECTURE 去重 |
| 6 | system_design.md | 类图 6 处方法名按代码修正；补 fixed_prefixes/RD 前缀/weights.yaml 说明 |
| 7 | MATCHING_ANALYSIS_2026-08-06.md | 加注：passive_types 缺 led 为分析遗漏，实现版见 type_gate.yaml |
| 8 | class-diagram.mermaid | 方法名按 passive/active/type_hypothesis/pipeline 实际签名修正（后续建议脚本生成） |
| 9 | sequence-diagram.mermaid | `_from_prefix`→`_from_yaml`；match_typed 标注为预留 API 非链调用 |
| 10 | CHANGELOG.md | **补录 v1.0.0（MultiScorer 时代）与 v1.1.0（匹配 v2.0）条目**；合并重复 v0.5.0；修正 0.4.5 日期；统一测试数口径 |
| 11 | ROADMAP_AUDIT_2026-08-03.md | 补 Phase VI-X 完成状态 + v1.1.0 章节；清理 IX 遗留表自相矛盾行 |
| 12 | DEVELOPMENT_ROADMAP.md | 标注"设计愿景（历史）"边界；补 Phase VI-X 概要；或与 AUDIT 分工（见决策点 D3） |
| 13 | CODING_STANDARDS.md | 异常层次按 exceptions.py 实际修正；错误码 31→39 |
| 14 | DEVELOPMENT_SOP.md | 环境命令路径修正（cis2hdl/ 非 src/）；CHANGELOG 补录纪律 |
| 15 | HDL_SCHEMATIC_STANDARDS.md | 补"输出以 CSA 原生格式为准"；吸收 test1.md UPREV/SPCOCN 经验表；补 _comparison 格式差异节 |
| 16 | fix_proposal.md | 吸收 HDL_OUTPUT_FIX_PLAN（同批同源）；12 项全部标注"✅ 已实施（代码核实）" |
| 17 | DIAGNOSTICS_AND_RECOVERY.md | 标注"规划模块已全部落地"；错误码 39；交互原型更新为 CSA 时代 |
| 18 | ORCAD_SOURCE_ANALYSIS.md | 修正 standard 计数（91→88）、元件数（124→123）；整理章节编号；保留权威 |
| 19 | REFERENCE_READING_NOTES.md | 映射表补充 csa/scr/xcon/cpc/output_manager 新 writer |
| 20 | RESEARCH_REPORT.md | StructureType 列表修正（删 11/26/27、补 Junction=50）；器件数 135→131；.sch 推断标注已废弃 |
| 21 | FILE_INDEX_AND_MAPPING.md | 当前项目文件清单按 08-07 代码树刷新（补 matcher v2.0 / PST / writer 新文件）；吸收 _reference_index 器件目录表 |
| 22 | UI_DESIGN_SPEC.md | Token 层数 5→7、Colors 20→22、版本号更新；吸收 FRONTEND_DESIGN 交互流程章节 |
| 23 | VERIFICATION_GUIDE.md（合并后） | 以 HG5015 为主验证对象；预期值 24 CSA/889/3717；测试命令与基线更新；吸收 test1.txt BOM 对比方法论；吸收 VERIFICATION_GUIDE_HG5015 |
| 24 | MEMORY.md | 数字同步（测试 268/23、行数统计、candidate_selector 现状）；标注与 .workbuddy/memory 的去重关系 |
| 25 | handoff-20260807-113237.md | 暂留根目录为状态源；STATUS.md 建成后移入 archive/handoff/ |
| 26 | _ref_file_list.csv | 保留（参考库结构索引） |
| 27 | _gen_cmp_pt1.py | 保留（可复用脚本） |
| 28 | _gen_imp.py | 保留（可复用脚本） |
| 29 | 硬件设计规范.docx | 保留（母本，外部权威引用） |
| 30 | 硬件设计规范.pdf | 保留（阅读/归档版） |

#### B. 合并后归档（8 份：独有信息先提炼进目标文档）

| # | 文件 | 合并去向 |
|---|---|---|
| 1 | FRONTEND_DESIGN.md | 交互流程/状态图并入 UI_DESIGN_SPEC.md；依赖树废弃 |
| 2 | HDL_OUTPUT_FIX_PLAN.md | 并入 fix_proposal.md |
| 3 | _comparison_report.md | CSA 格式逐行对比并入 HDL_SCHEMATIC_STANDARDS.md；其余归档 |
| 4 | _reference_index.md | 参考项目清单并入 FILE_INDEX_AND_MAPPING.md |
| 5 | reference_project_file_list.md | 并入 FILE_INDEX_AND_MAPPING.md |
| 6 | 2608041210report.md | HG5015 二进制解析算法并入 SYSTEM_ARCHITECTURE.md 解析器章节 |
| 7 | test1.txt | BOM 交叉验证方法论并入 VERIFICATION_GUIDE.md |
| 8 | VERIFICATION_GUIDE_HG5015.md | 并入 VERIFICATION_GUIDE.md（见 A-23） |

#### C. 直接归档（32 份：移入 docs/archive/，不改内容）

日志 9 份（2026-07-29 ~ 08-06，其中 07-22/07-23 移至 waveform_viewer 项目或工作记忆）｜ handoff 历史 4 份（20260805×2、20260806×2）｜ 废弃设计 4 份（system_design08061513.md、class-diagram08061513.mermaid、sequence-diagram08061513.mermaid、MATCHING_DIAGNOSIS_2026-08-04.md）｜ 过程文档 10 份（_audit_code、_audit_tests、_implementation_log、_improvement_plan、_qa_report、_refactor_log、_test_reorg_log、test1.md、temp.txt、PHASE2_DESIGN.md）｜ 历史需求 1 份（PRD_v0.5.1_incremental.md）｜ 调研历史 2 份（CIS2HDL_IMPROVEMENT_DOC.md、FILE_COLLECTION_CHECKLIST.md）｜ 修复快照 2 份（binary_diff_report.md、validation_report.md）｜ 运行快照 7 份（_rtl_result.txt、hg5015_verify.txt、convert_output.log、errors08060847.txt、test_output.txt、test_output_round2.txt、tests_output.txt）

#### D. 移出 / 删除候选（10 份，**需用户确认**，见决策点 D1）

| # | 文件 | 建议 |
|---|---|---|
| 1 | 2026-07-22.md | 移出（waveform_viewer 项目日志，且与工作记忆重复） |
| 2 | 2026-07-23.md | 移出（同上） |
| 3 | _rtl_result.txt | 删除候选（一次性调试输出，证据已被 hg5015_verify 覆盖） |
| 4 | hg5015_verify.txt | 删除候选（一次性快照） |
| 5 | convert_output.log | 删除候选（一次性运行日志） |
| 6 | test_output.txt | 删除候选（测试快照，数字已入 STATUS） |
| 7 | test_output_round2.txt | 删除候选（同上） |
| 8 | tests_output.txt | 删除候选（早期快照） |
| 9 | _cis2hdl_file_list.csv | 删除候选或重新生成（8-03 快照已过期，含 .venv 噪音与 nul 条目） |
| 10 | docs.rar（cis2hdl 根目录） | 确认内容后归档或删除（疑似 docs 压缩备份） |

#### E. 待新增（6 份）

| # | 文件 | 内容 |
|---|---|---|
| 1 | DOCS_INDEX.md | 文档地图：全部现行权威 + 归档区索引 + 文档元信息规范 |
| 2 | STATUS.md | 当前状态：v1.1.0 / 测试 268+23（291 collected）/ 阶段完成度 / 12 项遗留（源自 handoff-20260807） |
| 3 | KNOWN_ISSUES.md | 技术债清单：_audit_code 未修复 4 项 + handoff 限制 12 项 + 错误日志证据 3 类 + weights.yaml 潜在缺陷 |
| 4 | TIMELINE.md | 7/29→8/7 研发时间线（含版本/测试数/关键决策演进，骨架已从日志串联） |
| 5 | 版本同步检查单（并入 DEVELOPMENT_SOP） | 版本发布四步：__init__.py / pyproject / CHANGELOG / README 同步 + 测试基线记录 |
| 6 | 测试口径说明（并入 VERIFICATION_GUIDE） | 标准命令 + collected/passed/skipped 三要素记录法 |

---

### 五、执行方案（经用户确认后实施）

#### 阶段 0：确认与冻结
- 用户确认本方案 + 4 个决策点（见第七节）→ 冻结处置表

#### 阶段 1：归档执行（低风险，先做）
- 建 `docs/archive/{日志,handoff,废弃设计,过程文档,运行快照,清单快照}/` 子目录
- 按处置表 C 类移动（git mv 或移动后提交，保留历史）；D 类删除项单独确认后执行
- 产出：docs/ 根目录立即可读性提升，为后续修订提供干净工作区

#### 阶段 2：并行修订（Workflow F，按无依赖簇并行，每簇一个支笔生）
- **簇 A 门户与状态**（README / PROJECT_OVERVIEW / STATUS / DOCS_INDEX / TIMELINE / KNOWN_ISSUES）
- **簇 B 版本与研发管理**（CHANGELOG 补录 / ROADMAP_AUDIT / DEVELOPMENT_ROADMAP / MEMORY）
- **簇 C 架构设计**（SYSTEM_ARCHITECTURE / COMPONENT / BACKEND / 吸收 2608041210 与 _audit_code 技术债）
- **簇 D 匹配设计**（system_design / MATCHING_ANALYSIS / 两张 mermaid 按代码修正）
- **簇 E 规范标准**（CODING_STANDARDS / DEVELOPMENT_SOP / HDL_SCHEMATIC_STANDARDS / DIAGNOSTICS_AND_RECOVERY / fix_proposal 合并）
- **簇 F 调研验证**（ORCAD_SOURCE_ANALYSIS / RESEARCH_REPORT / REFERENCE_READING_NOTES / FILE_INDEX / VERIFICATION_GUIDE 合并 / UI_DESIGN_SPEC 合并）
- 每簇任务说明附带「项目参数卡」（版本 v1.1.0、测试 268/23、错误码 39、匹配 v2.0 口径、目录结构实测）与核对证据清单

#### 阶段 3：质量审核（严审之，逐簇串行）
- 6 维审核：逻辑一致性（数字/版本跨文档一致）、规范符合性、参数合理性、内容完整性、格式规范性、跨章一致性
- 重点核对项：版本号四文件一致、测试口径三要素齐全、错误码统一 39、匹配描述统一 v2.0、HG5015 预期值 24/889/3717、交叉引用指向正确
- REVISE 退回 ≤2 轮；终审后生成「审核报告」附于 DOCS_INDEX

#### 阶段 4：终验与交付
- 全量回归：`pytest tests/unit/ tests/integration/ tests/e2e/ -q`（预期 268 passed / 23 skipped 无回归）
- 输出完整文档集 + 审核报告 + 处置执行记录（archive 映射表）
- 交付清单：docs/ 新体系 + 本方案执行报告

---

### 六、风险与约束

| 风险 | 应对 |
|---|---|
| 归档后原引用失效 | archive/ 下保留原始文件名；DOCS_INDEX 提供"旧名→新位置"映射表 |
| 版本/测试数字再次漂移 | STATUS.md 每月或每版本刷新；SOP 强制同步检查单 |
| 并行修订引入新矛盾 | 全部修订统一以"项目参数卡"为准；阶段 3 串行总审核兜底 |
| 用户未确认项（D1 删除） | 默认保守：只归档不删除，直到用户明确确认 |
| PAINT WIRE 决策未定 | 方案默认"文档如实标注未启用"，不触碰代码 |
| 本方案外发现（weights.yaml GUI 失效等） | 全部登记入 KNOWN_ISSUES.md，不擅自修改代码 |

---

### 七、决策结论（用户已确认，2026-08-07）

| 决策点 | 用户结论 | 执行含义 |
|---|---|---|
| **D1 归档与删除策略** | **全部归档不删除** | 所有历史文档（含运行快照、_ 前缀临时文档、waveform_viewer 2 份日志）移入 docs/archive/ 分区；**不物理删除任何文件**；docs.rar 不动 |
| **D2 PAINT WIRE** | **彻底移除生成器代码** | 删除 csa_writer.py 中 `_build_wire_segments()` 及相关函数；核对其输入（dsn_parser wire_net_map）是否仍有其他消费者，无则一并清理；文档统一按"已移除"口径（与 handoff-20260806 一致） |
| **D3 路线图** | **内容保全式合并为 ROADMAP** | 将 DEVELOPMENT_ROADMAP + ROADMAP_AUDIT 合并为 `ROADMAP.md`（**不改写/重构原有内容，全部细节保留**，含 Phase VI-X/v1.1.0 补充）；合并前与项目代码逐项对比核查 |
| **D4 验证指南** | **合并为一份，历史内容完整保留** | VERIFICATION_GUIDE + VERIFICATION_GUIDE_HG5015 合并为一份；数字按实际更新（24 CSA/889/3717、测试 268+23）；**过往历史内容不删除，作为历史信息分节保留** |

---

*本文档由专业文档生成团队调研产出（78 份全量精读 + 代码核对 + 2 项实测），未对任何文件进行改动。后续执行需用户确认后启动。*

<a id="part-ii"></a>

## Part II　首次整合执行报告（原 docs_consolidation_report_2026-08-07.md 全文）

> **来源**：`docs_consolidation_report_2026-08-07.md`（89 行）全文收录；标题按"源 H1→H2"规则整体降级一级。

## CIS2HDL docs 目录文档体系整合执行报告

- **执行团队**：专业文档生成团队（章成文主理 · 苏寻源/支笔生/严审之）
- **执行日期**：2026-08-07
- **前置方案**：`docs_consolidation_plan_2026-08-07.md`（用户确认 4 个决策点：全归档不删除 / PAINT WIRE 彻底移除 / ROADMAP 内容保全式合并 / 验证指南合并且历史内容完整保留）

---

### 一、执行总览

| 阶段 | 内容 | 结果 |
|------|------|------|
| 调研 | 78 份文档全量精读（7 路并行）+ 代码库核对 + 实测（测试基线 / GUI 框架） | ✅ |
| 方案 | 整合方案 + 4 决策点确认 | ✅ |
| 归档 | 39 份历史文档 + 10 份合并源 → archive/ 8 分区，**零删除** | ✅ |
| 代码清理 | PAINT WIRE 生成器 3 函数移除（csa_writer.py -149 行） | ✅ 回归 268/23 |
| 文档修订 | 8 路并行簇：更新 16 份 + 新建 6 份 + 内容保全合并 2 份 | ✅ |
| 质量审核 | A1 全局口径 + A2 重点深审 → 14 项必须修改 → FIX 执行 → R2 二轮复核 | ✅ 全部落地 |
| 终验 | `pytest tests/unit/ tests/integration/ tests/e2e/ -q` | ✅ 268 passed / 23 skipped / 0 failed |

**docs 目录终态**：根目录 34 项（29 份权威文档 + 2 脚本 + 1 清单 + archive/ + 2 规范文件），archive/ 8 分区 61 份（日志 9 / handoff 4 / 废弃设计 5 / 过程文档 14 / 运行快照 8 / 清单快照 1 / 合并源 10 + 计数含子目录项）。

---

### 二、78 份文件去向总表

#### A. 权威保留并更新（16 份）
README.md（版本/测试/索引/匹配 v2.0）｜PROJECT_OVERVIEW.md（功能状态标注）｜SYSTEM_ARCHITECTURE.md（包结构重画/匹配 v2.0/错误码 44/解析算法）｜COMPONENT_ARCHITECTURE.md（匹配 v2.0/未落地标注）｜BACKEND_DESIGN.md（匹配 v2.0/EDIF 角色/PST 数据源）｜system_design.md（类图 6 处代码修正）｜MATCHING_ANALYSIS_2026-08-06.md（加注实现差异）｜CHANGELOG.md（**补录 v1.0.0/v1.1.0**、合并重复 v0.5.0）｜CODING_STANDARDS.md（错误码 44/异常层次/§8.1）｜DEVELOPMENT_SOP.md（四文件版本同步检查单）｜HDL_SCHEMATIC_STANDARDS.md（新增 Cadence 兼容性经验速查）｜DIAGNOSTICS_AND_RECOVERY.md（已落地标注）｜fix_proposal.md（12 项 ✅ + 根因链附录）｜ORCAD_SOURCE_ANALYSIS.md（计数修正）｜REFERENCE_READING_NOTES.md（映射补充）｜RESEARCH_REPORT.md（StructureType 修正）｜FILE_INDEX_AND_MAPPING.md（清单刷新）｜UI_DESIGN_SPEC.md（吸收 FRONTEND_DESIGN §13）｜VERIFICATION_GUIDE.md（**合并版**：Part I HG5015 现行 + Part II 历史保留）｜MEMORY.md（数字同步）

#### B. 新建（6 份）
STATUS.md（当前状态权威）｜DOCS_INDEX.md（文档地图 + 归档索引）｜TIMELINE.md（7/29→8/7 时间线）｜KNOWN_ISSUES.md（技术债六类）｜ROADMAP.md（**两份路线图内容保全式合并**，1622 行，源文档零遗漏）

#### C. 归档（archive/，共 49 份，零删除）
- **日志/**（9）：2026-07-22~08-06（其中 07-22/23 为 waveform_viewer 项目日志，已标注）
- **handoff/**（4）：20260805×2、20260806×2（历史交接快照）
- **废弃设计/**（5）：system_design08061513 + 旧 mermaid ×2 + MATCHING_DIAGNOSIS + CIS2HDL_IMPROVEMENT_DOC
- **过程文档/**（14）：_ 前缀 ×9 + 2608041210report + test1.md + temp.txt + PHASE2_DESIGN + PRD_v0.5.1 + FILE_COLLECTION_CHECKLIST + binary_diff_report + validation_report
- **运行快照/**（8）：7 份原始 txt + 1 份新存档（291-collected 实测）
- **清单快照/**（1）：_cis2hdl_file_list.csv
- **合并源/**（10）：DEVELOPMENT_ROADMAP / ROADMAP_AUDIT / FRONTEND_DESIGN / HDL_OUTPUT_FIX_PLAN / _comparison_report / _reference_index / reference_project_file_list / 2608041210report / test1.txt / VERIFICATION_GUIDE_HG5015（各主目标见 DOCS_INDEX §归档索引）

#### D. 保留不动（5）
_gen_cmp_pt1.py / _gen_imp.py（可复用脚本）｜_ref_file_list.csv（参考库索引）｜硬件设计规范.docx / .pdf（外部权威规范）

---

### 三、关键裁决记录

| 项 | 裁决 | 依据 |
|---|---|---|
| 版本号 | **v1.1.0 为唯一当前版本**；CHANGELOG 补录 v1.0.0/v1.1.0 为版本权威 | 代码 matcher v2.0 模块 + handoff-20260807 + MEMORY |
| 测试数 | **268 passed / 23 skipped / 0 failed（291 collected）**；历史数字标注口径（137/192/242/243/255） | 多次 pytest 实测（本次终验复现） |
| 错误码 | **44 条**（39 漏算 OLB 51-55；31 为 docstring 旧口径） | error_diagnosis.py 程序化统计 |
| 匹配架构 | v2.0 两阶段（TypeHypothesis→CandidatePool→Passive/Active）取代"四级管道"；MultiScorer 已删除 | core/matcher/ 代码 |
| PAINT WIRE | **生成器已彻底移除**（Cadence 16.6 不支持 SPCOCN-1891）；"7页16段"为历史临时状态 | 用户决策 + 代码清理 + 回归 |
| HG5015 输出 | **24 CSA（20 原理图+4 信息页）/ 889 元件 / 3717 网络**；匹配 889/889、92.4%、quality 72% | HG5015_tests 输出目录核对 |
| GUI 框架 | **PySide6**（handoff 中 PyQt5/tkinter 记载均误） | gui/ 代码 grep |
| 匹配率口径 | 92.4%（822/889）为当前；99.9% 为 Phase VIII 历史口径 | R2 复核确认 |

---

### 四、代码改动记录

| 文件 | 改动 | 验证 |
|---|---|---|
| `cis2hdl/core/writer/csa_writer.py` | 移除 PAINT WIRE 死代码块（`_build_wire_segments` / `_compute_wire_transform` / `_transform_wire_coord`，L789-938，-149 行） | 全量回归 268/23 零回归；grep 确认无残留引用 |
| 说明 | `dsn_parser.py` 的 `wire_net_map` 保留（L708 有网名注入 IR 的消费方） | 未改动 |

---

### 五、遗留事项（已登记 docs/KNOWN_ISSUES.md）

- **P0**：v2.0 输出在 Cadence SPB 16.6 二次实测；conversion_engine.py 调试 print 清理
- **P1**：67 个 NEEDS_REVIEW 元件（T*/D*/J* 库覆盖）；weights.yaml GUI 权重编辑失效（ActiveMatcher 用硬编码）；error_diagnosis.py docstring "31"→44 同步；ROADMAP 未在 KNOWN_ISSUES 索引补充（已办结项）
- **P2**：信息页 CSA 占位符；元件 rotation 数据；错误码口径收口复核；GUI candidate_selector 未完整测试
- **信息缺口 [待填写]**：PROJECT_OVERVIEW F15/F19/F22/F23 状态；KNOWN_ISSUES G1-G6（含 24 CSA 信息页 TitleBlock 内容等）

---

### 六、质量审核轨迹

1. **A1 全局口径审核**（8 维扫描 + 错误码专项）→ REVISE 5 项
2. **A2 重点文档深审**（ROADMAP 保全度/VERIFICATION_GUIDE 结构/STATUS 一致性/DOCS_INDEX 路径/KNOWN_ISSUES 溯源）→ REVISE 9 项
3. **FIX 执行**：14 项全部落地（主理人补修 SYSTEM_ARCHITECTURE:427 1 处）
4. **R2 二轮复核**：14+1 项全部 PASS；全局扫描 5/6 干净；主理人收口 SYSTEM_ARCHITECTURE:641/L3 两处后定稿

---

*本报告由专业文档生成团队产出。文档体系整合已完成，重要技术决策请经专业人员核验后再投入实际使用。*

<a id="part-iii"></a>

## Part III　二次合并方案（原 docs_merge_plan_2026-08-07.md 全文）

> **来源**：`docs_merge_plan_2026-08-07.md`（74 行）全文收录；标题按"源 H1→H2"规则整体降级一级。

## CIS2HDL docs 根目录二次整合方案（md ≤ 10 份）

- **编制**：章成文（主理人）· 专业文档生成团队
- **日期**：2026-08-07
- **目标**：docs/ 根目录 md/mermaid 从 **27 份 → 10 份**
- **原则**：内容保全式合并（沿用 ROADMAP 合并模式，不删原文）；历史文档归档不删除

---

### 一、现状（27 份，约 14,000 行 / 700KB）

| 类别 | 文件 | 体量 |
|---|---|---|
| 门户/状态/导航 | README(136) STATUS(145) DOCS_INDEX(146) KNOWN_ISSUES(112) TIMELINE(41) MEMORY(81) | ~660 行 |
| 研发管理 | ROADMAP(1622) CHANGELOG(1440) handoff-20260807(797) PROJECT_OVERVIEW(249) fix_proposal(419) | ~4530 行 |
| 架构设计 | SYSTEM_ARCHITECTURE(797) BACKEND_DESIGN(962) COMPONENT_ARCHITECTURE(564) DIAGNOSTICS_AND_RECOVERY(467) UI_DESIGN_SPEC(683) | ~3470 行 |
| 匹配系统 | system_design(896) MATCHING_ANALYSIS(681) class-diagram.mermaid(186) sequence-diagram.mermaid(70) | ~1830 行 |
| 规范标准 | CODING_STANDARDS(586) DEVELOPMENT_SOP(403) HDL_SCHEMATIC_STANDARDS(443) | ~1430 行 |
| 调研参考 | ORCAD_SOURCE_ANALYSIS(1327) RESEARCH_REPORT(955) REFERENCE_READING_NOTES(1111) FILE_INDEX_AND_MAPPING(586) | ~3980 行 |
| 验证 | VERIFICATION_GUIDE(964) | 964 行 |

---

### 二、目标结构（10 份 md）

| # | 保留文件 | 构成（内容保全式合并） | 预估体量 |
|---|---|---|---|
| 1 | **README.md** | 门户 + 文档导航（吸收 **DOCS_INDEX.md**）+ 需求基线（吸收 **PROJECT_OVERVIEW.md**） | ~450 行 |
| 2 | **STATUS.md** | 当前状态权威（不变） | 145 行 |
| 3 | **ROADMAP.md** | 路线图 + 附录：研发时间线（吸收 **TIMELINE.md**） | ~1700 行 |
| 4 | **CHANGELOG.md** | 版本史（不变） | 1440 行 |
| 5 | **KNOWN_ISSUES.md** | 技术债（不变） | 112 行 |
| 6 | **VERIFICATION_GUIDE.md** | 验证指南（不变） | 964 行 |
| 7 | **ARCHITECTURE.md** | **五合一**：SYSTEM_ARCHITECTURE + BACKEND_DESIGN + COMPONENT_ARCHITECTURE + DIAGNOSTICS_AND_RECOVERY + UI_DESIGN_SPEC → Part I 架构总览 / Part II 后端详设 / Part III 器件模型 / Part IV 诊断体系 / Part V GUI 设计 | ~3500 行 |
| 8 | **MATCHING.md** | **四合一**：system_design + MATCHING_ANALYSIS + class-diagram.mermaid + sequence-diagram.mermaid → Part I 根因分析 / Part II v2.0 设计 / Part III 类图 / Part IV 时序图 | ~1900 行 |
| 9 | **STANDARDS.md** | **三合一**：CODING_STANDARDS + DEVELOPMENT_SOP + HDL_SCHEMATIC_STANDARDS → Part I 编码规范 / Part II 开发流程 / Part III 原理图规范 | ~1450 行 |
| 10 | **RESEARCH.md** | **四合一**：ORCAD_SOURCE_ANALYSIS + RESEARCH_REPORT + REFERENCE_READING_NOTES + FILE_INDEX_AND_MAPPING → Part I 格式分析 / Part II 技术调研 / Part III 参考库笔记 / Part IV 文件索引 | ~4000 行 |

> 合并方式与 ROADMAP 一致：**源文档章节逐节保留（仅调标题层级），新增"合并说明/交叉索引/矛盾裁决"章节**，不改写原文句子；被合并的 16 份源文档 + 3 份吸收源文档在合并完成后移入 `archive/二次合并源/`（零删除）。

### 三、归档清单（合并后移入 archive/二次合并源/）

被合并源 16 份：SYSTEM_ARCHITECTURE、BACKEND_DESIGN、COMPONENT_ARCHITECTURE、DIAGNOSTICS_AND_RECOVERY、UI_DESIGN_SPEC、system_design、MATCHING_ANALYSIS、class-diagram.mermaid、sequence-diagram.mermaid、CODING_STANDARDS、DEVELOPMENT_SOP、HDL_SCHEMATIC_STANDARDS、ORCAD_SOURCE_ANALYSIS、RESEARCH_REPORT、REFERENCE_READING_NOTES、FILE_INDEX_AND_MAPPING
吸收源 3 份：DOCS_INDEX、PROJECT_OVERVIEW、TIMELINE
独立归档 2 份：fix_proposal.md（12 项已实施的历史修复档案）、handoff-20260807-113237.md（状态已提炼入 STATUS）、MEMORY.md（工作记忆，.workbuddy/memory 为源）
→ 共 21 份入 `archive/二次合并源/`

### 四、根目录终态

```
docs/
├── README.md  STATUS.md  ROADMAP.md  CHANGELOG.md  KNOWN_ISSUES.md
├── VERIFICATION_GUIDE.md  ARCHITECTURE.md  MATCHING.md  STANDARDS.md  RESEARCH.md   ← 10 份 md ✅
├── _gen_cmp_pt1.py  _gen_imp.py  _ref_file_list.csv   ← 非 md 保留
├── 硬件设计规范.docx / .pdf                             ← 外部权威规范
└── archive/                                            ← 归档区（新增 二次合并源/ 分区）
```

### 五、执行步骤（确认后启动）

1. **并行合并**（Workflow F）：4 个合并簇（ARCHITECTURE/MATCHING/STANDARDS/RESEARCH）+ 1 个门户簇（README 吸收 + ROADMAP 吸收）并行，每位成员持同一参数卡
2. **审核**：严审之统一审核（合并保全度：源文档章节 100% 覆盖；交叉引用更新；口径一致性 v1.1.0/268+23/错误码 44）
3. **归档**：21 份源文档移入 archive/二次合并源/；DOCS_INDEX 并入 README 后不再独立存在（README 承担导航职责）
4. **终验**：pytest 回归（预期 268/23）+ DOCS_INDEX 内链接可用性抽查 + 交付报告

### 六、决策点（待用户确认）

- **D1 合并粒度**：推荐本方案 10 份（调研类 RESEARCH 保留为合并大文档）；备选：更激进 8 份（RESEARCH 整体归档，仅 DOCS_INDEX 索引）
- **D2 大文档组织**：推荐"内容保全式分卷"（Part 结构，原文保留）；备选"重写精简版"（信息密度高但放弃原文保真）
- **D3 立即执行**：确认后即按第五节执行

---

*本文档为方案稿，未对任何文件做改动。*

<a id="part-iv"></a>

## Part IV　二次合并执行报告（原 docs_merge_report_2026-08-07.md 全文）

> **来源**：`docs_merge_report_2026-08-07.md`（63 行）全文收录；标题按"源 H1→H2"规则整体降级一级。

## CIS2HDL docs 根目录二次整合执行报告

- **执行团队**：专业文档生成团队（章成文主理 · 支笔生 ×5 · 严审之）
- **执行日期**：2026-08-07
- **目标**：docs/ 根目录 md/mermaid 27 份 → **10 份**（用户确认：含调研大文档 / 内容保全式分卷 / 立即执行）

---

### 一、执行结果

| 指标 | 结果 |
|---|---|
| 根目录 md 数量 | **10 份** ✅（原 27 份） |
| 新增合并大文档 | 4 份（ARCHITECTURE 3689 行 / MATCHING 1995 行 / STANDARDS 1580 行 / RESEARCH 4163 行） |
| 合并源归档 | **22 份** → `archive/二次合并源/`（零删除） |
| 质量审核 | 整体 **PASS**（6 维全过，无必须修改项） |
| 终验 | `pytest` 全量 **268 passed / 23 skipped / 0 failed**（零回归） |

### 二、根目录终态（10 份 md）

| # | 文件 | 构成 |
|---|---|---|
| 1 | README.md | 门户 + 文档导航（吸收 DOCS_INDEX）+ 需求基线 F01-F23（吸收 PROJECT_OVERVIEW） |
| 2 | STATUS.md | 当前状态权威（v1.1.0 / 268+23 / 错误码 44 / 匹配 889·92.4%·72%） |
| 3 | ROADMAP.md | 路线图（Part I 愿景 + Part II 审计 + Part III 裁决）+ 附录研发时间线（吸收 TIMELINE） |
| 4 | CHANGELOG.md | 版本史（v0.1.0→v1.1.0） |
| 5 | KNOWN_ISSUES.md | 技术债六类（P0×2/P1×5/P2×5）+ 信息缺口 |
| 6 | VERIFICATION_GUIDE.md | 验证指南（Part I 现行 HG5015 + Part II 历史保留） |
| 7 | ARCHITECTURE.md | 五合一：系统架构/后端详设/器件模型/诊断体系/GUI 设计 |
| 8 | MATCHING.md | 四合一：根因分析/v2.0 设计/类图/时序图 |
| 9 | STANDARDS.md | 三合一：编码规范/开发流程/原理图规范 |
| 10 | RESEARCH.md | 四合一：格式分析/调研报告/参考库笔记/文件索引 |

非 md 保留：`_gen_cmp_pt1.py`、`_gen_imp.py`、`_ref_file_list.csv`、`硬件设计规范.docx/.pdf`、`archive/`（8 分区 73 份）

### 三、合并方式与质量保障

- **内容保全式分卷**：每份合并大文档 = 源文档章节逐节保留（仅调标题层级）+ Part 0 合并说明（原则/权威口径/章节映射表/交叉引用处理）+ 末尾合并保全声明（章节覆盖证明）
- **保全度实证**：RESEARCH 四源 0 行缺失（4162/4162）；MATCHING 两 mermaid 图逐字节一致；ARCHITECTURE 43 H2/94 H3/14 H4 全保留；STANDARDS 22/22 H2 覆盖
- **顺带修复的源文档缺陷**（已在合并文档注明）：BACKEND_DESIGN 游离 ``` 围栏；ORCAD_SOURCE_ANALYSIS §9.7 起未闭合围栏（89→90 恢复配对，§10~§18 标题还原）
- **交叉引用**：源文档互链改为新 Part 锚点；指向外部文档的引用统一为"合并文档名（原源文档 §N）"格式

### 四、归档区终态（archive/ 8 分区，共 73 份）

| 分区 | 数量 | 内容 |
|---|---|---|
| 二次合并源 | 22 | 四大合并文档源 + 门户吸收源 + 独立归档（fix_proposal/handoff-20260807/MEMORY） |
| 合并源 | 10 | 第一轮合并源（ROADMAP/VERIFICATION_GUIDE 等） |
| 过程文档 | 14 | _ 前缀审计文档 + 交接报告 + 任务书等 |
| 日志 | 9 | 日工作日志（07-22~08-06） |
| 运行快照 | 8 | 原始输出 + 测试快照（含 291-collected 存档） |
| 废弃设计 | 5 | v0.9.0 旧设计 + 旧 mermaid + 历史诊断 |
| handoff | 4 | 历史交接文档 |
| 清单快照 | 1 | _cis2hdl_file_list.csv |

### 五、遗留与建议

- **建议项（审核提出，未纳入本次）**：README LICENSE 徽章指向不存在的 LICENSE 文件（原 README 遗留，建议补 LICENSE 或移除徽章）
- **既有 P0 工单**：v2.0 输出 Cadence 16.6 二次实测；conversion_engine 调试 print 清理（详见 KNOWN_ISSUES.md）

---

*本文档由专业文档生成团队产出。文档体系整合完成，重要技术决策请经专业人员核验。*

<a id="part-v"></a>

## Part V　后续工作记录（2026-08-07 追加）

> **说明**：本章节记录本档（consolidation260807）建立（2026-08-07 16:30）之后的整合工作，为"后续 plan/report 统一写入本档"的**第一条记录**；后续整合工作继续追加至本节，并同步更新头部"来源清单"、目录与文末"合并保全声明"中的统计。

### 5.1 废弃设计合并（deprecated_designs_master.md）

- **产物**：`docs/archive/废弃设计/deprecated_designs_master.md`（2238 行）
- **源文档**：5 份（共 2146 行），板块 A~D 全文保真归档，零丢失，源文档不删除
- **合并方式**：板块化智能合并（按主题板块组织同期/同类内容；条目对比合并，同主题多源描述信息点全保留）；旧口径内容原样保留并加注记

| 板块 | 源文件 | 源行数 | 收录行数 | 保全状态 |
|---|---|---|---|---|
| A | `system_design08061513.md` | 585 | 585 | ✅ 0 丢失 |
| B | `MATCHING_DIAGNOSIS_2026-08-04.md` | 371 | 371 | ✅ 0 丢失 |
| C | `CIS2HDL_IMPROVEMENT_DOC.md` | 999 | 999 | ✅ 0 丢失 |
| D | `class-diagram08061513.mermaid` | 109 | 109 | ✅ 0 丢失 |
| D | `sequence-diagram08061513.mermaid` | 82 | 82 | ✅ 0 丢失 |
| **合计** | — | **2146** | **2146** | **逐源 0 丢失** |

### 5.2 过程文档合并（process_docs_master.md）

- **产物**：`docs/archive/过程文档/process_docs_master.md`（4111 行）
- **源文档**：14 份（共 3857 行），6 大板块全文保真归档，零丢失，源文档不删除
- **顺带修复**：`_improvement_plan.md` 末段代码围栏未闭合（源文档原有问题），合并时补闭合围栏并注明（process_docs_master.md L1464），源内容逐行未改动

| 板块 | 源文件（源行数） |
|---|---|
| A 代码与测试审计 | `_audit_code.md`(318) / `_audit_tests.md`(281) / `_qa_report.md`(172) |
| B 修复与重构记录 | `_refactor_log.md`(101) / `_implementation_log.md`(190) / `_test_reorg_log.md`(82) |
| C 改进方案与需求 | `_improvement_plan.md`(185) / `PRD_v0.5.1_incremental.md`(298) / `test1.md`(597) / `FILE_COLLECTION_CHECKLIST.md`(231) |
| D 验证与差异报告 | `validation_report.md`(89) / `binary_diff_report.md`(187) |
| E 设计文档 | `PHASE2_DESIGN.md`(929) |
| F 工作笔记 | `temp.txt`(197) |
| **合计** | 14 份，**3857** |

### 5.3 方案报告总档建立（本文件）

- 本文件 `docs_consolidation260807.md`：4 份 plan/report 源（共 515 行）→ Part I~IV（全文保真，标题降级一级），Part V（本节）为后续工作记录区
- 本条为本档建立后的**首条**后续工作记录

### 5.4 三文档元信息更新

| 文档 | 更新内容 | 状态 |
|---|---|---|
| `docs/README.md` | 导航更新为 **9 份权威文档** + `archive/` 4 分区新结构 + 新增合并档说明（deprecated_designs_master / process_docs_master / 本总档） | ✅ |
| `docs/ARCHITECTURE.md` | 验证无需改动，引用路径全部有效 | ✅ 无需改动 |
| `docs/changelog_master.md` | 仅元信息 13 处更新（来源路径 → `docs/archive/handoff&logs/` 等）；板块 1~9 与附录 A 一字未动；6417 → 6418 行 | ✅ |

### 5.5 后续追加说明

本节为"后续 plan/report 统一写入本档"的**第一条记录**（2026-08-07 16:30 之后）。后续整合工作（废弃设计合并、过程文档合并、README 等更新）继续追加至本节，并同步更新头部"来源清单"、目录与文末"合并保全声明"中的统计。

<a id="merge-declaration"></a>

## 合并保全声明

| 源文档 | 收录位置 | 源行数 | 收录行数 | 保全状态 |
|---|---|---|---|---|
| `docs_consolidation_plan_2026-08-07.md` | Part I | 289 | 289 | ✅ 全文收录（标题降级，无删减） |
| `docs_consolidation_report_2026-08-07.md` | Part II | 89 | 89 | ✅ 全文收录（标题降级，无删减） |
| `docs_merge_plan_2026-08-07.md` | Part III | 74 | 74 | ✅ 全文收录（标题降级，无删减） |
| `docs_merge_report_2026-08-07.md` | Part IV | 63 | 63 | ✅ 全文收录（标题降级，无删减） |
| **合计（源内容行）** | — | **515** | **515** | — |

> **核对说明**：
> - 4 份源文档共 515 行，正文内容逐行原样收录于 Part I~IV；仅标题按"源 H1→H2"规则整体降级一级（行数不变）。
> - 表格、代码块、列表、引用等正文元素原样保留；代码围栏计数：Part I 含 1 对、Part III 含 1 对，共 2 对（偶数，配对核对通过）。
> - 源文档（4 份）保持只读、未做任何修改；本总档为唯一新增产物。
> - 本档追加后续内容时，应同步更新本声明表格（源行数/收录行数）与头部"来源清单"。

*本档由专业文档生成团队（章成文主理 · 支笔生）于 2026-08-07 建立。*
