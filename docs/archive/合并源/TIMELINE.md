# CIS2HDL 研发时间线（TIMELINE）

| 项目 | 值 |
|------|-----|
| 文档版本 | v1.0（2026-08-07 建立） |
| 项目版本 | v1.1.0（匹配系统 v2.0） |
| 状态 | 现行研发过程时间线（7/29 项目启动 → 8/7 v1.1.0） |
| 数据来源 | `docs/archive/日志/2026-07-29.md` ~ `2026-08-06.md`（9 份）+ [handoff-20260807-113237.md](handoff-20260807-113237.md) + 项目参数卡 v1.1.0 |
| 关联文档 | [STATUS.md](STATUS.md) · [KNOWN_ISSUES.md](KNOWN_ISSUES.md) · [CHANGELOG.md](CHANGELOG.md) |

---

## 1. 说明

- 时间线以 `docs/archive/日志/` 下 9 份日期日志为骨架串联，版本号以 [CHANGELOG.md](CHANGELOG.md) 与项目参数卡对齐。
- **2026-07-22 / 2026-07-23 两份日志为 waveform_viewer 项目（非 CIS2HDL）**，不并入主线，仅作归档记录。
- 测试数栏为当日记录值（历史口径）；现行权威基线为 **268 passed / 23 skipped / 0 failed（291 collected，2026-08-07）**，详见 [STATUS.md](STATUS.md)。

## 2. 主线时间线（CIS2HDL）

| 日期 | 版本 | 关键事件 / 决策 / 修复 | 测试数（历史口径） |
|------|------|------------------------|--------------------|
| 2026-07-29 | v0.1.0 | **项目启动（设计阶段）**：完成 Cadence SPB 生态（18 模块）、CIS vs HDL 格式、网表桥梁机制调研；搜索开源方案（OpenOrCadParser / Upverter / Universal-Netlist）与 Python 模糊匹配库；产出 8 份设计文档（README / RESEARCH_REPORT / PROJECT_OVERVIEW / SYSTEM_ARCHITECTURE / FRONTEND_DESIGN / BACKEND_DESIGN / CODING_STANDARDS / DEVELOPMENT_ROADMAP / CHANGELOG）。关键技术决策：PySide6、三段式解析、基类-注册模式、Pydantic IR。第四轮深度分析：universal-netlist dsn-format.md（1065 行完整 DSN 二进制格式）、公司 BOM.rpt、hdl_lib 135 器件类别、10 个 Cadence 开源设计 golden JSON | —（设计阶段） |
| 2026-07-30 | v0.2.0 → v0.3.0 | **Phase I-B：Binary DSN Parser 实施 + 诊断系统设计**。实现 OleReader(476 行)/BinaryReader(205 行)/结构体解析器(589 行)/DSNParser(235 行)/CrossValidator(191 行)/LayoutMapper(85 行)；新增 DIAGNOSTICS_AND_RECOVERY.md 设计。Phase I 验收 17/20。修复 2 个阻塞性 Bug（EDIF 递归解析、OleReader 回退路径）→ 76 collected/70 passed/6 skipped + 30/30 E2E。RTL8367RB 真实数据 4 轮 Engineer→QA 迭代 → Phase I 签收 ✅。GUI Crowz 风格重构 + Anthropic Token 体系重写（colors.py 20 色暖米色 + 5 层 Token + 12 QSS） | 45 → 76/76 |
| 2026-07-31 | v0.3.1 → v0.3.4 | **Phase II：Core Pipeline 完整开发 + 补完 + 签收**。测试重组（4 混合文件 → 13 模块化，93 passed）；参考库五阶段分析重构（File Index 472 行、18 份精读 1103 行、17 项改进建议、6 项 🔴 实现）；CLI 新增 `--hdl-lib` 支持。T01-T05 首批任务（HDLLibScanner/MatcherPipeline/ValidatorBase+ErrorDiagnosisEngine(39 错误码)+FileRecoveryStrategy/ConversionEngine 六阶段/GUI 面板）+ 8 项补完（ConfigValidator/StructuredReportGenerator/MatchConfirmDialog/CTW DSL 等）→ Phase II 签收 ✅（新增 31 文件、修改 10 文件，E2E Quality L=85% C=100%） | 93 → 76/76 |
| 2026-08-03 | v0.3.5 → v0.4.0 | **Cadence 兼容性修复 + Phase III/IV/V 开发**。审计参考项目发现 12 项差异（最关键：缺失 .xcon 文件），实施全部 12 项修复（xcon_writer.py、cds.lib 去 ./ 前缀、master.tag、CSAWriter 颜色、hdldirect.dat 等）；CSA 格式第二轮修复（C SIZE PAGE 边框、QUIT 终止符、FORCEADD body_name、坐标 sanity）；RTL 坐标 Bug 第三轮修复。Phase III T01-T05（OLB 解析器 20/21 Package、BatchConversionEngine、SchematicPreviewPanel、OLBIntegrityChecker、MultiSourceCrossValidator、HTML 报告导出）→ Phase III 16/16 完成；Phase IV 层次遍历 + 坐标映射 → 70/70 任务完成；Phase V 代码重构与参考比对（_audit_code 67 文件 62 项、normalize_value、ROTATION）；产出 VERIFICATION_GUIDE + verify_all.py（38/38） | 192 → 201 → 136/137 → 144 |
| 2026-08-04 | v0.4.1 → v0.4.6 → v0.5.0 | **HG5015 解析验证 + 匹配系统深度修复 + Phase VI CrossRef**。P4.1 CFB 修复：HG5015 从 0 页 → 20 页、682 instances、4067 nets；20 CSA 输出。匹配问题深度调研：446/730 失败 (61%) 三层根因（DSN RTL 解析缺陷、Cache 不完整、EDIF 映射不足）。Phase V 系列：V-A1/A2（EDIF 属性反注 + FallbackMatcher）匹配率 39%→63%；V-B1/B2（LibraryPart 修复、refdes 分离 993→1167）；F1-F4（LASTPIN SIG_NAME、TitleBlock、INSxxx 回注、Cache 渐进式）。**Phase VI CrossRef 驱动架构重构**：新增 cross_ref_parser.py，CrossRef CSV 注入 → 匹配率 880/914 (96.3%) | 122 → 123 → 97 → 144 → 97 |
| 2026-08-05 | v0.6.0 → v0.8.2 | **Phase VII-IX：匹配增强 + Pin 注入 + PST 网表集成**。Phase VII（v0.6.0）：prefix_filter +11 前缀、EDIF pin→net 注入（914 实例）。Phase VIII（v0.7.0）：Primitive 精准选择（FORCEADD 81.6% 精准 primitive）、cis_value 注入率 99.3% (883/889)、坐标映射对齐。Phase IX（v0.8.0→v0.8.2）：pstchip/pstxnet 解析器、JEDEC_TYPE 精确匹配、278→20 页 BUG 修复、No_Pin_Connections=0；v0.8.1 pstxnet 重写 + Unity Boost；v0.8.2 Value Hint（DZ_→zener 等）、输出去重 259→1、**24 页修复（20 原理图 + 4 信息页）**、match_rules.yaml 配置、HTML 报告增强。产出 handoff-20260805-103417 / 160515 | 97 → 109 |
| 2026-08-06 | v0.9.0 → v1.0.0 | **Phase X：Cadence SPB 16.6 实测 + MultiScorer 失败路线**。Phase X（v0.9.0）：实测分析 612 行 errors.txt；P0-1 FORCEADD body_name 用 primitive 名→cell 名（SPCOCN-515，492 实例无符号）；P0-2 LASTPIN SIG_NAME 问题（SPCOCN-543）；P1 ADD_COMMENT 格式化；5 Features（PHYS_DES_PREFIX 动态扫描、page.map、.cpc、.scr 25 文件 5348 行、extract_pkg_size）。**v1.0.0：MultiScorer 全库打分匹配**（6 维加权：footprint 0.25/prefix 0.20/pin_count 0.20/value 0.15/jedec 0.10/part_name 0.10；PrefixAffinityCalculator 学习矩阵）→ 声称 889/889 (100%)。**但深度分析发现 MultiScorer 导致匹配质量严重倒退**（大量跨类型错误：电容→电阻/电感、二极管→电阻、MARK→芯片）→ 输出 MATCHING_ANALYSIS_2026-08-06.md（15 页），为 v2.0 重构提供依据。产出 handoff-20260806-085237 / 161951 | 134/157 |
| **2026-08-07** | **v1.1.0** | **匹配系统 v2.0 完整重构（现行权威）**。Phase1 TypeHypothesis（类型假设排序，不锁死）+ Phase1.5 CandidatePool（候选池构建）+ Phase2A PassiveMatcher（被动 5 级确定性规则）+ Phase2B ActiveMatcher（主动 5 维类型内评分）；final_conf = phase1_prior × phase2_within（乘法，不用 max）；STOP_SEARCH=0.75 / NEEDS_REVIEW=0.40。**MultiScorer 已删除**、correlations.yaml 重置（删除 17 条 v1.0 跨类型错误学习记录）。15 个 P0 Bug 修复 + JEDEC→footprint 数据链路打通 + CSV(38 列)/HTML 报告增强。**PAINT WIRE 生成器代码彻底移除**（Cadence 16.6 不支持，SPCOCN-1891）。结果：889/889 全部获得结果、声称匹配率 92.4%（822/889）、quality=72%、**零跨类型错误**、NEEDS_REVIEW 67。产出 handoff-20260807-113237.md | **268 passed / 23 skipped / 0 failed（291 collected，权威基线）** |

## 3. 归档记录（非主线）

| 日期 | 内容 | 说明 |
|------|------|------|
| 2026-07-22 | waveform_viewer 项目工作日志（示波器波形 CSV→图片工具、UART 解码、测试 SOP 等） | 非 CIS2HDL 项目日志，详见 `docs/archive/日志/2026-07-22.md` |
| 2026-07-23 | waveform_viewer 项目工作日志（续） | 非 CIS2HDL 项目日志，详见 `docs/archive/日志/2026-07-23.md` |

---

*本文档由文档整合团队基于 9 份日期日志 + handoff 串联生成。测试数栏均为当日历史口径；现行权威基线见 STATUS.md。*
