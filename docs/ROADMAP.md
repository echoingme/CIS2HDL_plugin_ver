# ROADMAP（开发路线图与阶段状态总览）

> **文档名**: ROADMAP（开发路线图与阶段状态总览）
> **合并日期**: 2026-08-07
> **合并来源**:
>   - `docs/DEVELOPMENT_ROADMAP.md`（v4.0，2026-07-30 起草，止于 Phase V，含四阶段总览与任务分解 B1.x/D1.x/F1.x）
>   - `docs/ROADMAP_AUDIT_2026-08-03.md`（v0.4.0，2026-08-03 起草，Phase I-IV 全量清点 79 项 + Phase V-X 追加，含验证步骤与文件修改清单）
>   - `docs/TIMELINE.md`（v1.0，2026-08-07 建立，研发过程时间线，附录全文并入）
> **合并原则**: 内容保全（Content Preservation）—— 源文档的原文逐段保留，不做改写或重构；仅新增 **Part III「合并裁决与最新状态」** 与 **附录「研发过程时间线」** 附加章节。如合并中有意省略（如纯重复），均在 Part III 说明其合并去向。
> **附录**: 附录含研发时间线（2026-08-07 并入）
> **文档结构**:
>   - **Part I** 初始路线图（原 DEVELOPMENT_ROADMAP.md 全文，逐节保留）
>   - **Part II** 阶段完成状态审计（原 ROADMAP_AUDIT_2026-08-03.md 全文，逐节保留）
>   - **Part III** 合并裁决与最新状态（新增章节：重复内容对照、阶段完成度汇总、矛盾点裁决、代码核查、当前状态摘要）
>   - **附录** 研发过程时间线（原 TIMELINE.md 全文，逐行保留）

---

## Part I 初始路线图（原 DEVELOPMENT_ROADMAP.md 全文，逐节保留）

> **历史边界注记**: 本部分为原 `DEVELOPMENT_ROADMAP.md` 全文，写作于 2026-07-30 至 2026-08-03。其内容反映 7/30 起草时的规划与 8/3 前的完成状态；后续各阶段（Phase VI-X、匹配系统 v2.0）的进度以 **Part II / Part III** 为准。原文所有句子、任务编号、表格、代码块均原样保留，仅调整标题层级以适配合并文档结构。

### 原文档标题与头部（原文保留）

**原标题**: CIS2HDL 开发路线图

> 版本: v4.0 | 日期: 2026-07-30 | 更新: 全面融入诊断/校验/容错/文件完整性校验系统（15 个新模块）
> 参考: `../docs/ORCAD_SOURCE_ANALYSIS.md`（§0-§18）, `../design/COMPONENT_ARCHITECTURE.md`, `../design/DIAGNOSTICS_AND_RECOVERY.md`

---

### 阶段总览（原文）

```
Phase I: Foundation         ██████████░░░░░░░░░░  预计 4-5 周 (+诊断基础)
Phase II: Core Pipeline     ░░░░░░░░░░████████░░  预计 4-5 周 (+诊断/校验引擎)
Phase III: Polish & Release ░░░░░░░░░░░░░░░░████  预计 2-3 周
────────────────────────────────────────────────
总计                                          10-13 周
```

#### 技术基线（已通过调研验证）

| 验证维度 | 结果 | 证据（ORCAD_SOURCE_ANALYSIS.md） |
|---------|:--:|------|
| Binary DSN 解析 | ✅ | §1 DSN XSD 18 元素全量 + §10 DBO 对象层次 |
| EDIF 逻辑提取 | ✅ | §12 EDIF 12 条规律 + cap2edi.log 0 error |
| HDL symbol.css 生成 | ✅ | §2 C/L/A/T/P/M/X 指令 + §17 .baselined 格式 |
| 坐标映射 | ✅ | §13 8 种坐标系统 + §10 ConvertDocToUser 公式 |
| 器件匹配 | ✅ | §9 CTW 21 器件 PIN_ALIAS + §8 30+ OLB 库 |
| 网络分类 | ✅ | §11 ISCF 4 类网络模型 (FlatNet/GroundNet/PowerNet/BUS) |
| 属性传递 | ✅ | §10 CDS 属性 3 层 + §8 allegro.cfg 100+ 属性 |
| 页面生成 | ✅ | §16 creferhdl 12 种页面尺寸 + §15 属性系统 |

---

### Phase I: Foundation（基础设施 + 双路解析）（原文）

#### 目标

建立项目骨架，实施 **EDIF 快速验证 + Binary DSN 完整解析** 双路并行。第 1 周产出可验证的逻辑数据，第 2-4 周产出含坐标的完整 HDL 工程。

#### Phase I-A（第 1 周）：EDIF 快速验证路径

| 编号 | 任务 | 优先级 | 参考 |
|:----:|------|:------:|------|
| B1.1 | 创建 Python 包结构，配置 `pyproject.toml` | P0 | SYSTEM_ARCHITECTURE §4.1 |
| B1.2 | 实现 IR 核心模型：`ComponentDef`、`ComponentInstanceIR`、`PinDef`、`ElectricalType`（统一器件模型，绝不分格式/类型分叉） | P0 | COMPONENT_ARCHITECTURE §2 |
| B1.2a | 实现 `ComponentDB`：多索引数据库（library_id / part_name / footprint / category），支持 JSON 持久化 | P0 | COMPONENT_ARCHITECTURE §3 |
| B1.2b | 实现 `DesignIR`、`PageIR`、`NetIR`（使用 ISCF 4 类网络模型：FLAT/GROUND/POWER/BUS） | P0 | ORCAD_SOURCE §11 + BACKEND_DESIGN §2 |
| **B1.3e** | **实现 `EDIFParser`**：`sexpdata` 解析 .edf S-expression → DesignIR + ComponentDB。EDIF 12 条结构规律已确认。 | **P0** | ORCAD_SOURCE §12 |
| B1.4 | 实现 `ParserBase` ABC + `ParserRegistry`（基类-注册模式） | P0 | SYSTEM_ARCHITECTURE §6 |
| B1.5 | 实现 `WriterBase` ABC + `WriterRegistry` | P0 | SYSTEM_ARCHITECTURE §6 |
| B1.6 | 实现 `CPMWriter`：生成 .cpm。参考 `cdssetup/cds.cpm`（1,547 行）完整配置 | P0 | ORCAD_SOURCE §16 + BACKEND_DESIGN §5.3 |
| B1.7 | 实现 `CDSLibWriter`：生成 cds.lib。参考 `DEFINE standard ../library/standard` 语法 | P0 | ORCAD_SOURCE §2.5 |
| B1.8 | 实现 `SCHWriter`（逻辑版）：生成不含坐标的 .sch（NETLIST + SHEET 骨架） | P0 | BACKEND_DESIGN §5.1 |
| B1.9 | 前后端集成：打开 .edf → 解析 → Project Panel 展示结构 | P0 | UI_DESIGN_SPEC |
| B1.10 | 单元测试：EDIF 解析结果与 cap2edi.log 人工核对 | P0 | ORCAD_SOURCE §12.4 |

**Phase I-A 验收**：
- [ ] .edf 正确解析全部器件/网络/引脚/属性
- [ ] 生成不含坐标的 HDL 工程骨架，Project Manager 可打开

#### Phase I-B（第 2-4 周）：Binary DSN 完整解析

| 编号 | 任务 | 优先级 | 参考 |
|:----:|------|:------:|------|
| **B1.11** | **实现 `OleReader`**：MS-CFB 容器（512B头部→FAT→目录树128B/entry UTF16LE→miniFAT→miniStream），从 OleReader.ts 移植 | **P0** | ORCAD_SOURCE §1 + BACKEND_DESIGN §3.1 |
| **B1.12** | **实现 `BinaryReader`**：uint8/16/32, int8/16/32, read_string_zero_term/len_term/len_zero_term，从 DataStream.hpp 移植 | **P0** | ORCAD_SOURCE §10 + BACKEND_DESIGN §3.1 |
| **B1.13** | **实现 `StructureParsers`**：PlacedInstance(13) / T0x10(16) / Wire(20/21) / Package(31) / Device(32) / Global(37) / OffPage(38) / SymbolDisplayProp(39) / Alias(49) / LibraryPart(24) / Port(23) / TitleBlock(65) — 共 12 种核心类型 | **P0** | ORCAD_SOURCE §11 + BACKEND_DESIGN §3.1 |
| B1.13a | 实现 `FutureDataList`：检查点边界追踪器（PREAMBLE_MAGIC FF E4 5C 39 验证） | P0 | BACKEND_DESIGN §3.1 |
| B1.13b | 实现 `read_preamble` / `auto_read_prefixes` 通用解析框架 | P0 | BACKEND_DESIGN §3.1 |
| **B1.14** | **实现 `DSNParser` 顶层调度器**：Page流 + Cache流（Package/Device/LibraryPart） + Library流（strLst 字符串表）→ 完整 DesignIR（含坐标） | **P0** | ORCAD_SOURCE §10 + BACKEND_DESIGN §3.1 |
| **B1.15** | **实现 EDIF ↔ DSN 交叉验证器**：自动比对器件数/引脚数/网络数/连接关系，不一致报错 | **P0** | BACKEND_DESIGN §3.0b |
| B1.16 | 实现 `LayoutMapper`：CIS 坐标 → HDL 网格。使用 `ConvertDocToUser` 公式（文档坐标 × 1.0/物理粒度 = 用户坐标）。参考 Canvas 48 快捷键中的网格设置。 | P0 | ORCAD_SOURCE §10 + §13 |
| B1.17 | 完整 `SCHWriter`：注入坐标（PlacedInstance.locX/Y + Wire.startX/Y endX/Y）+ Wire 连线 + 属性显示（5 种模式） | P0 | ORCAD_SOURCE §10.1 |
| B1.18 | 实现 `SYMWriter`（符号图形）+ `PTFWriter`（多物理表）。参考 symbol.css C/L/A/T/P/M/X 指令 + part.ptf MULTI_PHYS_TABLE 格式。 | P1 | ORCAD_SOURCE §2 + §17 |
| **B1.19** | **实现 `FileInventory` + `DSNInternalInventory` + `DiagnosticReport`：文件清单追踪 + DSN 内部引用发现 + 数据完整度评分。** 对标 Cadence Project Manager Check References。 | **P0** | DIAGNOSTICS §2.2 |
| **B1.20** | **实现 `ProjectFileValidator`：输入文件集完整性校验（必选 .dsn 存在性/格式验证/版本检测/OLB 引用解析）** | **P0** | DIAGNOSTICS §2.1 Layer 1 |
| **B1.21** | **DSN 内部依赖解析：提取 OLB 引用列表 + Package 引用表 + 层次引用 → 生成缺失文件建议清单** | **P0** | DIAGNOSTICS §2.1 Layer 2 |
| B1.22 | 实现完整的 `SCHWriter`：注入坐标（PlacedInstance.locX/Y + Wire.startX/Y endX/Y）+ Wire 连线 + 属性显示（5 种模式）| P0 | ORCAD_SOURCE §10.1 |
| B1.23 | 实现 `SYMWriter`（符号图形）+ `PTFWriter`（多物理表）。参考 symbol.css C/L/A/T/P/M/X 指令 + part.ptf MULTI_PHYS_TABLE 格式。 | P1 | ORCAD_SOURCE §2 + §17 |
| B1.24 | 集成测试：OleReader / BinaryReader / StructureParsers / DSNParser / 交叉验证器 / 文件清单校验 | P0 | — |

#### Phase I-B 新增：诊断基础设施 Layer 1（文件完整性）

| 编号 | 任务 | 优先级 | 参考 |
|:----:|------|:------:|------|
| **D1.1** | **实现 `FileInventory`**：文件清单与逐文件状态追踪（FileState: FOUND/MISSING/CORRUPTED/PARTIAL/UNSUPPORTED）。每个文件记录路径、类型、大小、解析摘要、数据质量评分。 | **P0** | DIAGNOSTICS §2.2.1 |
| **D1.2** | **实现 `DSNInternalInventory`**：DSN 内部流结构清单（Root/Views/Pages/Cache/Library/Hierarchy 各流是否成功读取）+ OLB 引用列表 + Package 引用映射 + 字符串表条目计数。 | **P0** | DIAGNOSTICS §2.2.2 |
| **D1.3** | **实现 `ProjectFileValidator`**：三层文件完整性校验 — (a) 文件存在性检查 (b) CFB 魔数/头部格式验证 (c) CFB 版本兼容性检测。生成 FILE_MISSING / BAD_FORMAT / VERSION_MISMATCH 错误码。 | **P0** | DIAGNOSTICS §2.1 Layer 1 |
| **D1.4** | **实现依赖解析引擎**：从 DSN Cache 流提取 Package→OLB 引用表 → 对照用户提供的文件集 → 生成 MISSING_OLB 清单。同时检测层次引用、跨页引用、全局网络引用。 | **P0** | DIAGNOSTICS §2.1 Layer 2 |
| **D1.5** | **实现 `ConversionReadinessEvaluator`**：综合评估四维度（逻辑完整性/坐标可用性/器件可匹配性/符号可生成性）→ 加权评分 → 生成是否可转换的判断 + 转换质量预估。 | **P0** | DIAGNOSTICS §2.2.3 |
| **D1.6** | **实现 `DiagnosticReport` 数据模型**：统一诊断报告结构（按文件/按严重度/按类别三种视图），含建议操作列表（ActionItem）。支持 JSON 序列化。 | **P0** | DIAGNOSTICS §2.2.3 |

#### Phase I 前端的诊断面板

| 编号 | 任务 | 优先级 | 依赖 |
|:----:|------|:------:|------|
| F1.1 | 创建 PySide6 应用骨架（`QApplication`, `QMainWindow`）。颜色、圆角、字体严格遵循 `UI_DESIGN_SPEC.md` v2.0。 | P0 | UI_DESIGN_SPEC |
| F1.2 | Project Panel（`QTreeView`）：树节点显示 Page→Component→Pin 层次 | P0 | F1.1 |
| F1.3 | 文件打开对话框（.edf / .dsn / .olb / .opj / pstx*）— 扩展支持所有文件类型 | P0 | F1.1 |
| F1.4 | Log Panel（`QPlainTextEdit` + 日志路由），等宽字体 + 颜色语义 | P0 | F1.1 |
| F1.5 | Toolbar + StatusBar | P1 | F1.1 |
| **F1.6** | **Diagnostic Panel（文件状态面板）**：彩色状态树（✅/❌/⚠️/ℹ️）+ 数据完整度评分条（逻辑/坐标/属性/符号 四维进度条）+ 缺失文件清单 + 建议操作按钮。**对标 Cadence Project Manager Check References。** | **P0** | DIAGNOSTICS §3.1 |
| F1.7 | 前后端集成：打开文件 → 执行 FileInventory + ProjectFileValidator → Diagnostic Panel 展示状态 → Project Panel 展示结构树 | P0 | F1.2, F1.6, D1.3

#### Phase I 最终验收

- [x] .edf 解析全部逻辑（器件/引脚/网络数量人工核对一致）— **已修复** EDIF `_parse_page` 递归搜索 (2026-07-30)
- [x] .dsn 通过 OleReader→BinaryReader→StructureParsers→DSNParser 完整解析 — **已修复** DSN 页面流孤儿回退路径 (2026-07-30)
- [x] EDIF ↔ DSN 交叉验证通过（器件数/引脚数/网络数一致）— ✅ 2026-08-03 真实 RTL8367RB 数据验证: EDIF 751 inst/270 nets, DSN 6 pages/12 instances/423 nets (层次化设计, 实例数差异为顶层vs叶子)
- [x] FileInventory 正确识别所有输入文件状态（FOUND/MISSING/CORRUPTED）
- [x] DSNInternalInventory 正确提取 OLB 引用清单 + Package 引用表
- [x] ConversionReadinessEvaluator 给出四维评分并自动判断转换可行性
- [x] Diagnostic Panel 展示文件状态树 + 四维进度条 + 建议操作
- [x] Project Panel 展示含坐标的结构树
- [x] 生成含坐标的 .cpm + cds.lib + .sch 工程 — ✅ 2026-08-03 已多次转换 RTL8367RB, 202 tests pass
- [x] 生成的 HDL 工程可被 Project Manager 打开 — ✅ 2026-08-03 Cadence SPB 16.6 实测: UPREV已消除, SPCOCN-1891/515已修复
- [x] 所有 GUI 组件严格遵守 UI_DESIGN_SPEC v3.0（Anthropic Token 体系：20 色暖米色 + 4px 网格 + 4 档圆角 + 双数字号）
- [x] **QA 全量回归测试通过**：76/76 单元测试 + 真实 RTL8367RB 数据验证 (2026-07-30)
- [x] **GUI Anthropic 风格重构完成**：Sidebar + SummaryBar + TabContainer + LogPanel + 12 个 STYLE_* QSS 样式表 (2026-07-30)
- [x] **Token 体系实现**：`cis2hdl/gui/colors.py` 5 层 Token（Colors/Spacing/Radius/FontSize/Layout）+ rgb/rgba 辅助函数

---

### Phase II: Core Pipeline（核心管道 + 诊断引擎）✅ **已完成 (2026-07-31)**（原文）

#### 目标

实现器件匹配→校验→生成管道，GUI 匹配确认交互，**完整的诊断与容错引擎**，完整端到端可用。

#### 后端任务

| 编号 | 任务 | 优先级 | 参考 |
|:----:|------|:------:|------|
| B2.1 | 实现 `HDLLibScanner`：扫描 HDL 库目录（chips.prt + symbol.css + part.ptf）→ ComponentDB。124 个元件完整结构已确认。 | P0 | ORCAD_SOURCE §17 + COMPONENT_ARCHITECTURE §3 |
| B2.1a | 实现 `ChipsPrtParser`：解析 `FILE_TYPE=LIBRARY_PARTS; primitive→pin→body` 格式 | P0 | ORCAD_SOURCE §2.2 |
| B2.1b | 实现 `SymbolCssParser`：解析 C/L/A/T/P/M/X 图形指令 | P0 | ORCAD_SOURCE §2.1 |
| B2.1c | 实现 `PartPtfParser`：解析 MULTI_PHYS_TABLE 格式 | P0 | ORCAD_SOURCE §17.4 |
| B2.2 | 实现 `MatcherBase` ABC + `MatcherRegistry` | P0 | COMPONENT_ARCHITECTURE §4 |
| B2.3 | `MatcherPipeline` 四级链式：精确→模糊→特征→人工 | P0 | COMPONENT_ARCHITECTURE §4.2 |
| B2.4 | `ExactMatcher`：`ComponentDef.fingerprint` 哈希（封装+值+引脚数）+ CTW 21 器件 PIN_ALIAS 快速查表 | P0 | ORCAD_SOURCE §9.4 |
| B2.5 | `FuzzyNameMatcher`：rapidfuzz `token_sort_ratio`，器件名模糊匹配。启用 CTW 器件模板的 DEVNAME 候选。 | P0 | ORCAD_SOURCE §9.4 |
| B2.6 | `FeatureExtractMatcher`：正则提取阻值/容值/封装/引脚数，结构化比对 | P0 | — |
| B2.7 | `ManualMatchResolver`：生成确认请求 → GUI 交互，置信度 < 0.60 时触发 | P0 | — |
| B2.8 | `ValidatorBase` ABC + `ValidatorRegistry` | P0 | — |
| B2.9 | `PinValidator`：参考 DRC capDevicePinMismatch.tcl（GetDevice→GetPackage→比较引脚名和类型） | P0 | ORCAD_SOURCE §11.4 |
| B2.9a | `NetNameValidator`：ISCF 4 类网络判定 + 非法字符清洗（EDIF 12 条规律中的 rename 语法） | P0 | ORCAD_SOURCE §11.3 + §12 |
| B2.9b | `PowerPinValidator`：参考 capCheckPackageOnPartWindowClose.tcl 的重复电源引脚检测 | P0 | ORCAD_SOURCE §15.2 |
| B2.10 | 完善 `SCHWriter`：基于 CTW 电路模板 DSL（BEGIN_CIRCUIT→BEGIN_DEVICE→BEGIN_CONNECTIONS→QUERY_REPLICATE_DEVICE）生成完整 HDL 页面 | P0 | ORCAD_SOURCE §9.5 |
| B2.11 | 网络名规范化：EDIF `rename` 语法→HDL 映射、总线 CIS `[N:M]` → HDL 格式转换、4 类网络分类标记 | P0 | ORCAD_SOURCE §12 |
| B2.12 | `ConversionEngine` 主控：Parser→Matcher→Validator→Generator 全管道 | P0 | BACKEND_DESIGN §6 |
| B2.13 | 集成测试：含单页/多页/总线/多 Part 器件的完整转换 | P0 | — |

#### Phase II 新增：诊断与容错引擎

| 编号 | 任务 | 优先级 | 参考 |
|:----:|------|:------:|------|
| **D2.1** | **实现 `ErrorDiagnosisEngine`**：31 错误码体系（对标 Canvas 31 错误码）。每个错误码含：错误名称、详细消息、严重级别、影响范围、修复建议。支持错误聚合（同类错误合并去重）。 | **P0** | DIAGNOSTICS §4.1 + ORCAD_SOURCE §10.5 |
| **D2.2** | **实现 `FileRecoveryStrategy`**：多级降级转换路径 — (a) DSN 损坏→从 .dbk 恢复 (b) DSN 不可用→EDIF 逻辑转换 (c) OLB 缺失→DSN 内部 Cache 嵌入式定义 (d) 符号缺失→默认矩形符号 (e) 跳过损坏页面。每路径标注数据损失程度。 | **P0** | DIAGNOSTICS §2.2.4 |
| **D2.3** | **实现 `ConversionQualityEstimator`**：输出四维质量预估报告 — 逻辑完整性%（无缺失的器件/引脚/网络数）、坐标可用性%（有坐标的器件占比）、匹配覆盖率%（已匹配 HDL 设备的器件占比）、符号保真度%（保留原始符号 vs 默认符号）。 | **P0** | DIAGNOSTICS §2.1 Layer 3 |
| **D2.4** | **实现 `StructuredReportGenerator`**：生成结构化转换报告（JSON 格式 → 前端可渲染为 HTML/PDF）。包含：文件清单状态表、逐页解析详情、匹配结果表（含置信度色标）、校验问题列表、生成文件清单、质量评估摘要。 | **P0** | DIAGNOSTICS §3.2 |
| **D2.5** | **实现异步诊断管道编排器 `DiagnosticPipeline`**：协调 FileInventory → ProjectFileValidator → DependencyResolver → ReadinessEvaluator → QualityEstimator → ReportGenerator 六个阶段的顺序执行，支持各阶段的超时/取消/重试。 | **P0** | DIAGNOSTICS §2.1 |
| **D2.6** | **实现 `IncrementalConversionTracker`**：断点续转支持 — 记录已转换页面/已匹配器件/已生成文件 → 转换中断后可从断点恢复，避免重复处理。使用 `.cis2hdl_state.json` 持久化。 | **P1** | DIAGNOSTICS §4.2 |
| **D2.7** | **实现 `ConfigValidator`**：配置校验器 — 验证 Config 单例中的所有路径（cadence_root/hdl_lib_path）是否存在、编码声明是否正确、网格/页面尺寸参数是否合法。CONFIG_INVALID → 阻止转换 + 提供修复建议。 | **P0** | DIAGNOSTICS §4.2 |

#### 前端任务

| 编号 | 任务 | 优先级 | 依赖 |
|:----:|------|:------:|------|
| F2.1 | Settings 对话框：HDL 库路径、输出目录、creferhdl 页面尺寸选择（A~F 12 种） | P0 | F1.1 |
| F2.2 | Match Review Panel（三栏：CIS 器件 / HDL 候选 / 引脚映射），参考 Canvas Symbol.panel 的引脚网格布局 | P0 | ORCAD_SOURCE §13.6 |
| F2.3 | Match Confirm 对话框（低置信度人工确认），保留用户裁决结果到映射规则 | P0 | F2.2 |
| F2.4 | Properties Panel（右侧）：器件属性详情，参考 Canvas Properties Dock | P1 | UI_DESIGN_SPEC |
| F2.5 | QThread Worker：后台转换 + QProgressBar（青色进度条） | P0 | F1.1 |
| F2.6 | Preview Panel：转换前预览 HDL 文件树 | P1 | F1.1 |
| **F2.7** | **Conversion Report Panel（转换报告面板）**：彩色状态总览 + 逐页面折叠详情 + 匹配结果置信度色标 + 校验问题表格 + 生成文件清单 + 后续操作建议。支持导出 HTML/PDF。 | **P0** | DIAGNOSTICS §3.2 + D2.4 |
| **F2.8** | **Error Diagnostic Panel（错误诊断面板）**：错误码分类树（31 错误码 × 3 级严重度）+ 每条错误的修复建议 + 一键定位源文件位置（若能定位）+ "忽略并继续"选项。 | **P0** | DIAGNOSTICS §3.1 + D2.1 |
| **F2.9** | **Recovery Strategy Dialog（恢复策略对话框）**：当检测到文件损坏/缺失时弹出 — 列出所有可选恢复路径 + 每条路径的数据损失标注 + 推荐策略高亮 + 用户一键选择执行。 | **P0** | DIAGNOSTICS §3.1 + D2.2 |
| F2.10 | 前后端全流程集成：诊断→匹配→确认→校验→生成 | P0 | D2.5, B2.12 |

#### Phase II 验收（2026-07-31 最终更新 — 真数据全量验证通过）

- [x] HDLLibScanner 扫描真实 HDL 库 — ✅ **198 组件从 110 目录**（116 唯一，capacitor/resistor/rtl8367/zx279128s 验证通过）
- [x] CTW 21 器件模板自动匹配覆盖率 — ✅ 6/6 实例全部匹配 rtl8367（FEATURE 策略，83% 匹配率）
- [x] 集成测试：真实 RTL8367RB DSN(667KB) E2E 六阶段管道 — ✅ **6 pages/423 nets/8 output/Logic=100%**
- [x] 损坏 DSN 降级测试 — ✅ 截断 DSN 正确处理 + 扇区损坏恢复 4/6 instances
- [x] OLB 文件解析 — ✅ LIBRARY2CLEAN.OLB 成功读取 52 raw entries
- [x] GBK 编码适配 — ✅ 193 part.ptf 文件全部解析 OK
- [x] 低置信度匹配弹出确认对话框（MatchConfirmDialog + MatchReviewPanel）
- [x] GUI 不冻结（QThread 后台处理 ConversionWorker）
- [x] ErrorDiagnosisEngine 覆盖 39 错误码，每条含修复建议（历史口径，现为 44 条）
- [x] FileRecoveryStrategy 5 条降级路径全部可用，每条标注数据损失
- [x] ConversionReport Panel 正确展示四维质量评估 + 逐页详情
- [x] 网络名符合 ISCF 4 类模型 + EDIF rename 规范
- [x] ConfigValidator 在所有配置错误时阻止转换 + 提供修复建议
- [x] StructuredReportGenerator：JSON + HTML 双格式报告
- [x] **代码全量审计与重构** — Architect 审计 75 文件/41 项发现, 8 任务执行 (配置统一/消重/拆分/文档化/清理依赖/GUI常量化/异常/性能优化), QA 76/76
- [x] 生成的 HDL 工程可在 Design Entry HDL 打开 — ✅ 2026-08-03 Cadence SPB 16.6 实测通过: UPREV消除, CSA格式修复(QUIT/C SIZE PAGE/body_name)
- [x] 属性符合 CDS 属性系统 — ✅ 2026-08-03: PART_NAME/VALUE/JEDEC_TYPE/PACKAGE_TYPE/SN_NUM/DESCRIPTION/CDS_LIB/LOCATION 全部正确定义

#### Phase II 代码统计

| 指标 | 数量 |
|------|:--:|
| 新增文件 | 33 |
| 修改文件 | 20+ |
| 单元测试 | 76 (0 fail) |
| 错误码 | 39（历史口径，现为 44 条） |
| 降级路径 | 5 |
| 匹配器 | 4 (Exact/Fuzzy/Feature/Manual) |
| 校验器 | 3 (Pin/Net/Power) |
| 管道阶段 | 6 (Diagnose→Parse→Scan→Match→Validate→Generate) |
| 真数据验证 | DSN+EDF+OLB+110HDL库, 6 page/423 net/8 file |
| GUI 面板 | Sidebar/SummaryBar/TabContainer/Diagnostic/Log/MatchReview/Report/ErrorDiagnostic |

- [x] **测试重组 (v0.3.2)**: 4 混合文件 → 13 模块化文件 (11 unit + 2 integration)，93 passed/0 failed，8 shared fixtures

---

### Phase III: Polish & Release（完善与发布）✅ **已完成 (2026-08-03)**（原文）

#### 目标

增强用户体验、性能优化、OLB 解析器、批量转换、独立打包。**16/16 任务全部完成。**

#### 后端任务

| 编号 | 任务 | 优先级 | 参考 |
|:----:|------|:------:|------|
| B3.1 | OLB 解析器：基于 OLB XSD（§1.2）解析 Library→Package→LibPart→SymbolPinScalar→图形元素（Line/Ellipse/Polygon/Arc/Rect） | P1 | ORCAD_SOURCE §1.2 + §11 |
| B3.2 | 批量转换引擎：多项目队列，进度跟踪 | P1 | — |
| B3.3 | 映射规则导入/导出（JSON/YAML），持久化用户自定义匹配 | P1 | COMPONENT_ARCHITECTURE §5.2 |
| B3.4 | 转换报告生成（HTML/PDF）。参考 template.bom 的列定义格式。 | P2 | ORCAD_SOURCE §9.7 |
| B3.5 | 性能优化：大型项目（>200 页）的内存和速度 | P1 | — |
| B3.6 | E2E 测试：RTL8367RB-VC-DEMO 真实 CIS 工程（5 页，已验证 EDIF 0 error） | P1 | ORCAD_SOURCE §12.4 |

#### Phase III 新增：高级诊断与报告

| 编号 | 任务 | 优先级 | 参考 |
|:----:|------|:------:|------|
| **D3.1** | **实现 `OLBIntegrityChecker`**：OLB 文件完整性校验 — 验证 Package(31)/Device(32)/LibraryPart(24) 三层结构的完整性和一致性。检测引脚缺失、符号缺失、属性缺失。 | **P1** | DIAGNOSTICS §1.3 + ORCAD_SOURCE §1.2 |
| **D3.2** | **实现 `MultiSourceCrossValidator`**：多数据源交叉验证 — 当用户同时提供 .dsn + .edf + pstxnet.dat 时，三路逐项比对器件/引脚/网络/属性/连接关系。任一路不一致触发详细差异报告。 | **P1** | DIAGNOSTICS §1.4 |
| **D3.3** | **实现 `ConversionHistoryManager`**：转换历史记录管理 — 记录每次转换的输入文件清单、匹配结果、解决的错误类型、用户裁决 → 供后续转换学习优化。支持查询、对比、回滚。 | **P2** | DIAGNOSTICS §4.1 |
| **D3.4** | **实现 `BatchConversionDiagnostics`**：批量转换诊断聚合 — 当批量转换多个项目时，汇总所有项目的诊断结果，生成批次级别的质量趋势报告（匹配率变化、常见错误类型 Top N）。 | **P2** | DIAGNOSTICS §4.2 |

#### 前端任务

| 编号 | 任务 | 优先级 | 参考 |
|:----:|------|:------:|------|
| F3.1 | 原理图预览（QGraphicsView 渲染 CIS DSN 页面），参考 orPrmViewer 的 Canvas 渲染配置和 orPrmQTree 四叉树空间索引 | P1 | ORCAD_SOURCE §13 |
| F3.2 | Diff View：转换前后器件/网络对比。使用语义色（成功=蓝色、差异=红色）。 | P1 | UI_DESIGN_SPEC |
| F3.3 | 批量转换队列管理界面 | P2 | — |
| F3.4 | 映射规则管理面板（增删改查） | P2 | — |
| F3.5 | 报告查看器（HTML 嵌入 PySide6 WebEngine） | P2 | — |
| F3.6 | UI/UX 打磨：快捷键（参考 Canvas 48 个快捷键）、错误提示（参考 Canvas 31 错误码） | P1 | ORCAD_SOURCE §13.7 + §10.5 |
| F3.7 | PyInstaller 打包为独立 .exe | P0 | — |

#### Phase III 验收

- [x] OLB 解析器提取器件符号定义 — ✅ 20/21 Package, 8图形元素, 已注册到ParserRegistry
- [x] 批量转换 10 个项目不崩溃 — ✅ BatchConversionEngine, 项目隔离, 单项目失败不中断队列
- [x] 原理图预览渲染正确（器件放置坐标 + 连线路径）— ✅ SchematicPreviewPanel + DiffViewPanel
- [x] 打包 .exe 在无 Python 环境的 Windows 运行 — ✅ cis2hdl.spec + scripts/build_exe.py
- [x] 用户手册和转换报告模板完成 — ✅ HTML报告自动生成, ConversionHistoryManager

#### Phase IV（Cadence 实测后发现的改进项）✅ **已完成 (2026-08-03)**（原文）

| 编号 | 任务 | 优先级 | 状态 | 说明 |
|:----:|------|:------:|:--:|------|
| **P4.1** | **DSN 层次块子页面遍历** | P1 | ✅ | DSNParser 新增 `_resolve_hierarchy()`/`_resolve_page_hierarchy()`/`_is_drawn_inst()` — 递归遍历 DrawnInst→子页面(最大2层)+坐标偏移+循环引用防护。RTL8367RB DSN 因 CFB 目录树损坏，当前顶层页面不可达，但机制对正常 DSN 有效。修改文件: `dsn_parser.py` |
| **P4.2** | **DSN→DEHDL 坐标系统映射** | P1 | ✅ | CSAWriter 新增 `_map_coords_to_dehdl()` — BoundingBox居中 → 缩放×0.7 → 平移映射 + Y轴取反。超出C SIZE PAGE边界回退网格布局。修改文件: `csa_writer.py` |

**全项目: 70/70 任务全部完成 ✅ (100%)**

#### Phase I-A 早期验收项（已追溯完成）

- [x] .edf 正确解析全部器件/网络/引脚/属性 — ✅ 2026-08-03: EDIF 751 inst/270 nets, E2E test verified
- [x] 生成不含坐标的 HDL 工程骨架，Project Manager 可打开 — ✅ 2026-08-03: Cadence实测通过

---

### 风险跟踪（原文）

| 风险 | 缓解措施 | 证据 |
|------|---------|------|
| Binary DSN 解析复杂度 | openOrCadParser C++ + universal-netlist TS 两份完整参考；EDIF 先行验证逻辑 | ORCAD_SOURCE §1 + §11 |
| PinMap 多 unit 器件不完整 | Device 结构体已确认；pinMap(null) 标记逻辑已验证 | ORCAD_SOURCE §17.1 |
| EDIF vs DSN 数据不一致 | Phase I-B 实施自动交叉验证器逐项比对；Phase II 增加 MultiSourceCrossValidator 三路比对 | BACKEND_DESIGN §3.0b + DIAGNOSTICS §1.4 |
| HDL 库结构不规则 | 先期与库管理员对接；124 个元件结构已确认 | ORCAD_SOURCE §17 |
| 网络名 CIS↔HDL 映射错误 | ISCF 4 类模型 + EDIF rename 语法双重验证 | ORCAD_SOURCE §11 + §12 |
| 大型项目性能 | 四叉树空间索引（orPrmQTree）+ 缓存策略 | ORCAD_SOURCE §13 |
| **用户输入不完整/文件损坏** | **FileInventory + ProjectFileValidator 自动检测 + FileRecoveryStrategy 5 级降级路径 + Diagnostic Panel 引导用户补齐** | **DIAGNOSTICS §1-3** |
| **OLB 缺失导致符号/属性丢失** | **DSN Cache 嵌入式器件定义 + 默认矩形符号 + 质量评分标注数据损失** | **DIAGNOSTICS §1.3** |
| **格式版本不兼容** | **CFB 版本检测 + VERSION_MISMATCH 错误码 + 版本升级建议** | **DIAGNOSTICS §2.1 Layer 1** |

---

### 技术文档交叉索引（原文）

| 开发任务 | 主要参考文档 |
|---------|------------|
| EDIF 解析 | ORCAD_SOURCE §12 EDIF 格式全量 + §12.4 cap2edi.log |
| Binary DSN 解析 | ORCAD_SOURCE §1 DSN XSD + §10 DBO 对象层次 + §11 XSD 全量 |
| symbol.css 生成 | ORCAD_SOURCE §2 HDL 格式 + §17 .baselined 文本 + §13 ConceptHDL 模板 |
| chips.prt 生成 | ORCAD_SOURCE §2.2 + §17.1 .baselined 格式 |
| 器件匹配 | COMPONENT_ARCHITECTURE §4 + ORCAD_SOURCE §9.4 CTW 21 器件 |
| 网络映射 | ORCAD_SOURCE §11.3 ISCF 4 类网络 + §12 EDIF 12 条规律 |
| 坐标转换 | ORCAD_SOURCE §13 8 种坐标系统 + §10 ConvertDocToUser |
| 属性系统 | ORCAD_SOURCE §10.6 CDS 属性 + §15.3 属性 3 层架构 |
| BOM 生成 | ORCAD_SOURCE §9.7 template.bom + §17.4 part.ptf |
| GUI 实现 | UI_DESIGN_SPEC v2.0（颜色/圆角/字体全部强制） |
| **文件校验与诊断** | **DIAGNOSTICS_AND_RECOVERY §1-6（文件清单/DSN内部结构/诊断管道/对标分析/开发计划）** |
| **错误码与修复** | **DIAGNOSTICS_AND_RECOVERY §4 + ORCAD_SOURCE §10.5 Canvas 31 错误码** |
| **降级与恢复** | **DIAGNOSTICS_AND_RECOVERY §2.2.4 + ORCAD_SOURCE §17.2 .baselined 备份** |

---

---

<br>
### Phase IV: Validation & Coverage Enhancement ✅ 已完成 (2026-08-03)（原文）

> 参考: `docs/ROADMAP_AUDIT_2026-08-03.md`（全量 79 项清点）

| 类别 | 任务数 | 状态 |
|------|:--:|:--:|
| CFB 容器修复 (B4.1) | 1 | ✅ |
| CrossValidator 比对增强 (B4.2-B4.6) | 5 | ✅ |
| MultiSource 实测 (B4.4/B4.7) | 2 | ✅ |
| 测试覆盖 | 1 | ✅ |
| **合计** | **9** | **100%** |

#### Phase IV 关键成果

- `ole_reader.py:count_page_candidates()` — CFB pages 回退路径（PAGE/VRTL/`^\d{2,3}-` 三规则 + >2000字节阈值）
- CrossValidator 从 4 项扩大到 **8 项**（引脚数/网络连接数/拓扑Jaccard/器件类型分组）
- MultiSourceCrossValidator：DSN/EDIF/PSTXNET 三路比对，自动降级
- 测试：144 passed + 1 skipped

#### Phase IV 预留（完成于 Phase V 前）

| ID | 任务 | 状态 |
|----|------|:--:|
| P4.1 | DSN 层次块子页面遍历 | ✅ 已实现 `_resolve_hierarchy()` |
| P4.2 | DSN→DEHDL 坐标映射 | ✅ 已实现 `_map_coords_to_dehdl()` |

---
<br>
### Phase V: HG5015 匹配增强与数据质量修复 (2026-08-04 起)（原文）

> **背景**: HG5015-BE36_V10 (20 页 / 993 实例 / 4115 网络) 实测发现 **匹配成功率仅 39%** (284/730)，446 个器件完全失败，0 个模糊匹配。
> 根因分析见 `output_hg5015/HG5015-BE36_V10_errors.txt` 及 `docs/2608041210report.md`。
> 三层根因：① DSN RTL 解析缺陷导致 library_id = 垃圾数据 ② Cache 仅 47 Package 无 LibraryPart ③ EDIF 映射覆盖不全。

#### 阶段总览（原文）

```
Phase V-A: P0 紧急修复    ████████░░░░░░░░  预计 2-3 天
Phase V-B: P1 短期增强    ░░░░░░░░█████░░░  预计 2-3 天
Phase V-C: P2 中期完善    ░░░░░░░░░░░░░████  预计 1 周
────────────────────────────────────────────────
总计                                           1-2 周
```

#### Phase V 关键指标（原文）

| 指标 | 修复前 | Phase V-A 后 | 最终目标 |
|------|:--:|:--:|:--:|
| 匹配成功率 | 39% (284/730) | **63% (352/559)** | 80%+ |
| 模糊匹配数 | 0 | **107** | 50+ |
| component_db 组件数 | 47 | 47 | 80+ |
| FallbackMatcher 命中 | 0 | **75** | 100+ |
| 警告数 | 1441 | **1310** | <500 |
| 坐标可用率 | 41% | 41% | 60%+ |

---
<br>
#### Phase V-A: P0 紧急修复（第 1-3 天）（原文）

##### V-A1: EDIF 属性反注增强 [P0]

**文件**: `cis2hdl/core/engine/conversion_engine.py:_map_edif_types_to_dsn()`

**当前问题**: 
- 仅替换"明显乱码"的 library_id（非 ASCII / >30 字符 / NUL 字节）
- INSxxx、C89、10868 等合法 ASCII 垃圾未被替换
- 不填充 footprint/value/pin_count 等匹配指纹

**修改方案**:
1. **扩展替换条件**: 对所有 library_id 匹配垃圾模式的实例执行替换：
   - 纯数字（`^\d+$`）
   - INS 前缀（`^INS\d+`）
   - refdes 格式（`^[A-Z]+\d+$`，如 C89/R42）
   - 信号名模式（含 `_` 分隔的大写名称）
   - 物理参数（含 mm/pF/nH 等单位）
   - 从 EDIF map 中找到对应 refdes 的 library_id 并替换
2. **填充属性字典**: 从 EDIF ComponentDef 提取 footprint/value/pin_count → `inst.properties`
3. **写入 EDIF 指纹**: `inst.properties['EDIF_LIBRARY_ID']` 同时新增 `inst.properties['EDIF_FINGERPRINT']`
4. **日志增强**: 详细记录每次替换前后的值，写入 ConversionLogger

**预估效果**: 匹配率 39% → 60-70%（EDIF 有 3023 实例 vs DSN 993）

**验收标准**:
- [ ] EDIF library_id 覆盖 DSN 实例超 90%
- [ ] 替换日志每条例含 before/after 值
- [ ] 单元测试覆盖所有垃圾模式识别

---
##### V-A2: 引入多层次 Fallback 匹配策略 [P0]

**新文件**: `cis2hdl/core/matcher/fallback.py`

**参考**: `docs_for_reference/CIStoHDL_standard/match_cis_to_hdl.py`

**设计方案**:

```
FallbackMatcher (优先级 4，在 Feature 之后)
├── extract_prefix(): 正则提取 refdes 前缀（C/R/U/D/Q/L/FB/Y/J/TP）
├── BODY_FALLBACK 映射表: 
│   {"C":["capacitor"],"R":["resistor"],"U":["amplifier","ldo","dc_dc"],
│    "D":["diode"],"Q":["n_mos","p_mos"],"L":["inductor"],
│    "FB":["fb"],"Y":["crystal","osc"],"J":["connector"]}
├── extract_pkg_size(): 从 footprint 提取封装尺寸（HSC0402 → 0402）
├── normalize_value(): 值规范化（4.7K → 4.7K, 100NF → 100NF）
└── 三级匹配:
    ├── exact:  fp_size in part_name + value match (conf=0.85)
    ├── size:   fp_size in part_name but value mismatch (conf=0.65)
    └── prefix: only category match via BODY_FALLBACK (conf=0.50)
```

**关键实现细节**：
- 使用 `filter_candidates_by_refdes()` 复用 `prefix_filter.py` 现有逻辑
- 候选过滤后按 `sort_candidates_by_prefix()` 排序
- `match()` 返回 `MatchResult(strategy=FALLBACK, confidence=...)` 
  - 需在 `MatchStrategy` 枚举中新增 `FALLBACK = "fallback"`
- `confidence_threshold()` 返回 `config.matching.fallback_threshold`（默认 0.50）
- 在 `MatcherPipeline.__init__()` 中添加 `self.add_stage(FallbackMatcher())`

**影响文件**:
- `cis2hdl/core/matcher/fallback.py` — **新建**
- `cis2hdl/core/matcher/pipeline.py` — 添加 FallbackMatcher stage
- `cis2hdl/core/ir/match.py` — 新增 MatchStrategy.FALLBACK
- `cis2hdl/core/config.py` — 新增 fallback_threshold
- `cis2hdl/core/matcher/__init__.py` — 导出 FallbackMatcher

**预估效果**: 额外提升 10-15% 匹配率

**验收标准**:
- [ ] FallbackMatcher 在 MatcherPipeline 中正确注册（优先级 4）
- [ ] BODY_FALLBACK 映射表覆盖全部 refdes 前缀
- [ ] extract_pkg_size() 正确提取 0201/0402/0603/0805 等尺寸
- [ ] 三级匹配（exact/size/prefix）返回正确置信度
- [ ] 单元测试：fake ComponentDef + 真实 HDL candidates → 验证三种匹配等级

---
<br>
#### Phase V-B: P1 短期增强（第 3-5 天）（原文）

##### V-B1: 修复 Cache 解析 — LibraryPart [P1]

**文件**: `cis2hdl/core/parser/dsn/cache_parser.py`

**当前问题**: LibraryPart 解析因长前缀 byte_offset boundary 不足以覆盖图元段而全部失败。
47 个 ComponentDef 仅含 Package 层数据，无 pin_names 和 default_value。

**修改方案**:
1. **研究参考**: 对比 `OpenOrCadParser:StreamCache.cpp` 中 LibraryPart 的 boundary 定义
2. **扩展 `_read_long_prefix()`**: 增加 `_LIBRARY_PART_BOUNDARY_EXTRA` 常量，在 LibraryPart 结构体中追加额外字节到 byte_offset
3. **调试输出增强**: 在解析 LibraryPart 失败时 hex dump 当前 reader 位置前后各 32 字节
4. **渐进式解析**: 即使图元段不完全，也尝试提取已解析的 pin_names 和 default_value
5. **fallback 策略**: LibraryPart 解析部分成功时，pins 使用序号名称（"1","2","3"...）兜底

**影响文件**:
- `cis2hdl/core/parser/dsn/cache_parser.py` — 修改 `_read_long_prefix()` + `_parse_library_part()`

**预估效果**: component_db 从 47 → 80+ 个完整定义

**验收标准**:
- [ ] 至少 50% 的 Cache LibraryPart 结构能成功解析
- [ ] 解析出的 ComponentDef 含非空 pin_names
- [ ] HG5015 测试: component_db 组件数增加到 80+
- [ ] 单元测试: fake Cache 流含 LibraryPart → 验证 pin_names 提取

---
##### V-B2: 改善 refdes 解析 — 区分 pkg_name 和 reference [P1]

**文件**: `cis2hdl/core/parser/dsn/structures.py:_parse_placed_instance_rtl()`

**当前问题**: RTL 格式中 `pkg_name=rtl.name` 和 `reference=rtl.name` 使用同一值（structures.py:989-991）。
导致 library_id 中混入大量非器件名的垃圾数据。

**根因**: strLst 是一个扁平字符串表，器件名、信号名、属性值、描述文本全部混合。
当前 `str_len > 200` 阈值只能区分"字符串长度"和"strLst 索引"，无法区分解析出字符串的语义类型。

**修改方案**:
1. **prefix_props 属性提取**: 在 `_build_page_ir()` 中更积极地从 prefix_props 解析 refdes/Package 属性
   - 当前的 prefix_props 解析使用 `pp.name.isdigit()` 判断 strLst 索引（line 605）
   - **需要增强**: 检查 prefix_props 中 name 为 "Reference" / "RefDes" / "Part Reference" 的条目
2. **相邻条目推断**: 在 strLst 中查找相邻的 refdes 模式字符串
   - 如果 `rtl.name` 匹配 `^[A-Z]+\d+$` 模式（如 "C89"），则尝试作为 reference 而非 pkg_name
   - 回退到 EDIF refdes → library_id 映射
3. **database_id 交叉引用**: `rtl.db_id` 可能与 Cache 中的 Device 结构对应
   - 检查 component_db 中是否有 `db_id == rtl.db_id` 的条目

**影响文件**:
- `cis2hdl/core/parser/dsn/structures.py` — `_parse_placed_instance_rtl()`
- `cis2hdl/core/parser/dsn/dsn_parser.py` — `_build_page_ir()`

**预估效果**: 减少 50%+ 的垃圾 library_id，匹配率提升 5-10%

**验收标准**:
- [ ] HG5015 错误日志中 INS/refdes/信号名 类型的未匹配条目减少 50%
- [ ] 合法 library_id（真实器件库名）的实例数增加
- [ ] 单元测试: 构造 RTL PlacedInstance + 已知 strLst → 验证 pkg_name ≠ reference

---
<br>
#### Phase V-C: P2 中期完善（第 5-12 天）（原文）

##### V-C1: pstxnet.dat 集成 [P2]

**新文件**: `cis2hdl/core/parser/pstxnet_parser.py`

**背景**: DSN 目录中通常有 Cadence Allegro 导出的 `.dat` 网表文件（`pstxnet.dat`/`pstxprt.dat`/`pstchip.dat`），含完整的 refdes→part_name→footprint→value 映射。

**参考**: `universal-netlist` 项目的 `.dat` 解析器（TypeScript 实现于 `src/parsers/cadence/dat/`）

**修改方案**:
1. 实现 `PstxnetParser`: 解析 pstxnet.dat/pstxprt.dat/pstchip.dat 三文件
2. 从 pstxprt.dat 提取 `REFDES → PART_NAME → FOOTPRINT` 映射
3. 从 pstchip.dat 提取 `PART_NAME → VALUE` 映射
4. 注入到 `_extract_cis_components()` 中作为 fourth data source

**影响文件**:
- `cis2hdl/core/parser/pstxnet_parser.py` — **新建**
- `cis2hdl/core/engine/conversion_engine.py` — 集成 pstxnet 数据源

**预估效果**: 额外提升 5-10% 匹配覆盖率

**验收标准**:
- [ ] pstxnet.dat 文件存在时自动加载
- [ ] 提取的 refdes→footprint→value 映射经过验证
- [ ] 单元测试: HG5015 的 .dat 文件（如存在）

---
##### V-C2: 坐标提取改进 [P2]

**文件**: `cis2hdl/core/parser/dsn/structures.py:_RtlStructure.parse()`

**当前问题**: 591/993 (59.5%) 实例坐标为 (0,0)。RTL 格式中坐标通过 `c2.lo` 和 `c3.lo` 提取（`_int16_from_u32(c2, 0)`）。

**调查方向**:
1. 检查字节序（大端/小端）是否正确
2. 验证 `shift` 参数（当前为 0）是否需要改为 16（c2.hi 中可能含坐标）
3. 检查 `c0` 字段是否包含备用坐标（当前仅作 db_id fallback）
4. 与 EDIF 中的坐标对比验证

**影响文件**:
- `cis2hdl/core/parser/dsn/structures.py` — `_RtlStructure.parse()`

**预估效果**: 坐标可用率从 41% → 60%+

**验收标准**:
- [ ] 坐标 (0,0) 实例数从 588 降至 400 以下
- [ ] 提取的坐标与 EDIF 一致性验证通过

---
<br>
#### Phase V 风险跟踪（原文）

| 风险 | 缓解措施 | 依赖 |
|------|---------|------|
| EDIF 数据中 refdes 与 DSN 不一致 | CrossValidator refdes 交集比对已有（比对项 #4） | Phase IV |
| FallbackMatcher 误匹配导致错误器件 | body_fallback 限制在被动器件（R/C/L/D/Q），IC 类回退到 manual | — |
| LibraryPart 解析仍不完整 | 渐进式解析 + pin 序号 fallback | V-B1 |
| pstxnet.dat 文件缺失 | 自动降级到 EDIF + Cache 双源 | V-C1 |
| 坐标字节序差异 | 同时尝试大端和小端两种读取方式 | V-C2 |

---
#### Phase V 数据流架构（修复后）（原文）

```
DSN 二进制
    ├─ Cache 流 → cache_parser → ComponentDB (≥80 组件，含 pin_names)
    ├─ strLst → _build_page_ir() → improved library_id（区分 pkg_name/refdes）
    └─ Page 流 → ComponentInstanceIR
              │
EDIF 文件 ───┤ → _map_edif_types_to_dsn() → 替换垃圾 library_id + 填充属性
              │
pstxnet.dat ─┤ → PstxnetParser → refdes→footprint→value 映射 (Phase V-C1)
              │
              ▼
_extract_cis_components() → 去重 ComponentDef[]（含正确 fingerprint）
              │
              ▼
MatcherPipeline (5 stages)
├─ [1] ExactMatcher   (fingerprint 哈希)
├─ [2] FuzzyNameMatcher (rapidfuzz token_sort_ratio)
├─ [3] FeatureExtractMatcher (正则特征提取)
├─ [4] FallbackMatcher (refdes前缀 + body_fallback + 三级匹配) ← NEW
└─ [5] ManualMatchResolver (用户裁决)
```

---
#### Phase V 合并开发日志（原文）

| 日期 | 阶段 | 说明 |
|------|------|------|
| 2026-08-04 | 调研 | 完成 HG5015 错误日志全量分析、匹配管道全链路追踪、参考代码调研 |
| 2026-08-04 | 路线图 | 合并 DEVELOPMENT_ROADMAP + ROADMAP_AUDIT → 追加 Phase V |
| 2026-08-04 | **V-A2** ✅ | FallbackMatcher 实现（~410行，C×44/R×27/L×3/X×1 命中） |
| 2026-08-04 | **V-A1** ✅ | EDIF 属性反注增强（5模式垃圾检测+PKG_TYPE属性注入） |
| 2026-08-04 | **实测** ✅ | HG5015: 39%→63%, 0→107模糊, 1441→1310警告 |
| 2026-08-04 | **V-B1** ✅ | LibraryPart 解析修复（三层渐进式：Normal→Heuristic→Minimal） |
| 2026-08-04 | **V-B2** ✅ | refdes/pkg_name 分离（5优先级：pattern→strLst→prefix_props→db_id→default） |
| 2026-08-04 | **V-C1** ✅ | PstxnetParser 可选集成（ParserRegistry注册, FullAdder 4条目解析成功） |
| 2026-08-04 | **V-B实测** ✅ | HG5015: 实例993→1167(refdes分离), C89/R42等110个Fallback(0.50), 123 tests |
| TBD | V-C2 | 坐标提取改进 |

---
<br>
### 会议/评审节点（原文）

| 节点 | 时间 | 内容 |
|------|------|------|
| 设计评审 | 当前 | 审核全部设计文档，批准后进入 Phase I |
| Phase I-A 验收 | 第 1 周结束 | 演示 EDIF 解析 → HDL 工程骨架 |
| Phase I-B 验收 | 第 5 周结束 | 演示 Binary DSN 完整解析 + 交叉验证 + 诊断基础 |
| Phase II 验收 | 第 10 周结束 | 演示完整转换流程（含匹配确认 + 诊断引擎 + 降级策略） |
| Phase III 交付 | 第 13 周结束 | 最终交付 .exe + 文档 + 高级诊断报告 |
| Phase V-A 验收 | 第 16 周结束 | EDIF 反注 + FallbackMatcher → 匹配率 70%+ |
| Phase V-B 验收 | 第 17 周结束 | Cache 修复 + refdes 分离 → 匹配率 80%+ |
| Phase V-C 交付 | 第 18 周结束 | pstxnet + 坐标 → 完整 HG5015 转换 |

---

## Part II 阶段完成状态审计（原 ROADMAP_AUDIT_2026-08-03.md 全文，逐节保留）

> **历史边界注记**: 本部分为原 `ROADMAP_AUDIT_2026-08-03.md` 全文，写作于 2026-08-03（更新至 Phase IV 完成），后续追加 Phase V-X 章节。所有句子、任务编号、表格、代码块均原样保留，仅调整标题层级以适配合并文档结构。原文中的重复表格（如 Phase VIII 十-H 后的 IX-7~IX-10 重复表）亦原样保留。

### 原文档标题与头部（原文保留）

**原标题**: CIS2HDL Roadmap 全量清点报告

> 日期: 2026-08-03 (更新: Phase IV 完成) | 版本: 0.4.0

---

### 一、清点结果总览（原文）

| Phase | 任务总数 | 已实现 | 未实现 | 通过率 |
|-------|:--:|:--:|:--:|:--:|
| Phase I Foundation | 22 | **22** | 0 | 100% |
| Phase II Core Pipeline | 30 | **30** | 0 | 100% |
| Phase III Polish | 16 | **16** | 0 | 100% |
| Phase IV Validation & Coverage | 9 | 9 | 0 | 100% |
| **合计** | **79** | **77** | **2** | **97%** |

---

### 二、Phase I 逐项清点 (22/22 ✅)（原文）

| ID | 任务 | 状态 |
|----|------|:--:|
| B1.1 | Python 包结构 + pyproject.toml | ✅ |
| B1.2 | IR 核心模型 (ComponentDef/PinDef/ElectricalType) | ✅ |
| B1.2a | ComponentDB 多索引数据库 | ✅ |
| B1.2b | DesignIR/PageIR/NetIR (ISCF 4类网络) | ✅ |
| B1.3e | EDIFParser | ✅ |
| B1.4 | ParserBase ABC + ParserRegistry | ✅ |
| B1.5 | WriterBase ABC + WriterRegistry | ✅ |
| B1.6 | CPMWriter | ✅ |
| B1.7 | CDSLibWriter | ✅ |
| B1.8 | SCHWriter (逻辑版) | ✅ |
| B1.9-B1.24 | DSN Parser + 诊断 + 交叉验证 | ✅ |
| D1.1-D1.6 | FileInventory + Readiness + 诊断面板 | ✅ |
| F1.1-F1.7 | GUI 骨架 + 诊断面板 + 集成 | ✅ |

**验证数据**: 2026-08-03 Cadence SPB 16.6 实测 — UPREV 消除, .cpm 正常打开

---

### 三、Phase II 逐项清点 (30/30 ✅)（原文）

见 `CHANGELOG.md` §Phase II 全面审计 (2026-08-03) 逐项清点表

**验证数据**: 201 tests passed, Cadence SPB 16.6 实测通过

---

### 四、Phase III 逐项清点 (16/16 ✅)（原文）

| ID | 任务 | 实现文件 | 状态 |
|----|------|---------|:--:|
| B3.1 | OLB 解析器 | `olb/olb_reader.py` + `olb_parser.py` | ✅ |
| B3.2 | 批量转换引擎 | `batch_engine.py` | ✅ |
| B3.3 | 映射规则导入导出 | `pipeline.py` (YAML export/import/save) | ✅ |
| B3.4 | HTML/PDF 报告导出 | `report_gen.py` (generate_html_file) | ✅ |
| B3.5 | 性能优化 | `config.py` + `conversion_engine.py` (benchmark/max_workers) | ✅ |
| B3.6 | E2E 测试 | `test_rtl8367rb_full.py` (9 tests) | ✅ |
| D3.1 | OLBIntegrityChecker | `olb_integrity.py` (三层校验) | ✅ |
| D3.2 | MultiSourceCrossValidator | `multi_source.py` (三路比对+PSTXNET) | ✅ |
| D3.3 | ConversionHistoryManager | `history.py` (50条/线程安全) | ✅ |
| D3.4 | BatchConversionDiagnostics | `batch_engine.py` (quality_trend/common_errors) | ✅ |
| F3.1 | 原理图预览 | `schematic_view.py` (QGraphicsView) | ✅ |
| F3.2 | Diff View | `diff_view.py` | ✅ |
| F3.3 | 批量转换队列UI | BatchConversionEngine (CLI) | ✅ |
| F3.4 | 映射规则管理面板 | `rules_panel.py` | ✅ |
| F3.5 | 报告查看器 | HTML自动生成 (无WebEngine依赖) | ✅ |
| F3.6 | UI/UX 快捷键 | `main_window.py` (Ctrl+1/2/3/D) | ✅ |
| F3.7 | PyInstaller 打包 | `cis2hdl.spec` + `scripts/build_exe.py` | ✅ |

---

### 五、Phase IV: Validation & Coverage Enhancement (9/9 ✅ — 2026-08-03)（原文）

#### 五-A、CFB 容器修复 (1/1)

| ID | 任务 | 实现文件 | 状态 |
|----|------|---------|:--:|
| B4.1 | CFB Pages回退路径增强 | `ole_reader.py` (新增 `count_page_candidates()`), `dsn_parser.py` (回退条件修复) | ✅ |

**验证数据**: DSN 解析覆盖率从 12/752 (1.6%) 提升（修复后通过 raw entries 回退恢复遗漏的页面流）

#### 五-B、CrossValidator 比对增强 (5/5)

| ID | 任务 | 实现文件 | 状态 |
|----|------|---------|:--:|
| B4.2 | DSN↔EDF 逐器件引脚数比对 | `cross_validator.py` (`_compare_per_device_pin_counts`) | ✅ |
| B4.3 | DSN↔EDF 网络连接数比对 | `cross_validator.py` (`_compare_net_connection_counts`) | ✅ |
| B4.5 | DSN↔EDF 网络连接一致性（Jaccard拓扑映射） | `cross_validator.py` (`_compare_net_connection_consistency`), `design.py` (`NetIR.connection_signature`, `DesignIR.net_connection_map()`) | ✅ |
| B4.6 | DSN↔EDF 按器件类型分组比对 | `cross_validator.py` (`_compare_by_device_type`), `design.py` (`DesignIR.instances_by_type()`) | ✅ |
| — | 新增 IR 辅助方法 | `design.py` (`instance_refdes_set`, `instances_by_refdes()`) | ✅ |

**比对项扩展**: CrossValidator 从 4 项 → **8 项**：
页数 + 实例数 + 网络数 + refdes 交集 + **引脚数** + **网络连接数** + **网络拓扑一致性** + **器件类型分组**

#### 五-C、MultiSourceCrossValidator 实测 (2/2)

| ID | 任务 | 实现文件 | 状态 |
|----|------|---------|:--:|
| B4.4 | MultiSourceCrossValidator 实际数据测试 | `multi_source.py` (增强 `_compare_dsn_edf` 内联引脚/网络/类型比对) | ✅ |
| B4.7 | MultiSource 全面测试（集成+E2E） | `tests/integration/test_multi_source_validator.py` (新建), `tests/e2e/test_rtl8367rb_full.py` (新增 `test_two_source_validation_enhanced`), `scripts/verify_multi_source.py` (新建) | ✅ |

#### 五-D、测试覆盖 (1/1)

| ID | 任务 | 实现文件 | 状态 |
|----|------|---------|:--:|
| — | CrossValidator 单元测试扩展 | `tests/unit/test_cross_validator.py` (6 tests: 新增引脚/类型/拓扑) | ✅ |

#### 五-E、Phase IV 汇总

| 类别 | 新增文件 | 修改文件 | 测试通过 |
|------|:--:|:--:|:--:|
| CFB 修复 | 0 | 2 | 144/145 |
| CrossValidator | 0 | 3 | 6/6 (unit) |
| MultiSource | 2 (script+integration test) | 2 | 3/3 (integration) + 1/1 (e2e) |

**参考项目研究**:
- OpenOrCadParser (C++): CFB RB-tree 目录结构、Structure Parsers 参考
- universal-netlist (TypeScript): DSN 格式规范、Cache 解析、Pin Resolution 管道
- OpenAllegroParser (C++): 与本 Phase 无直接关联（PCB 布局解析器）
- CIStoHDL_standard: `generate_hdl_sch.py` 坐标映射参考 (P4.2 预留)、`match_cis_to_hdl.py` 匹配逻辑参考

#### 五-F、P4.1/P4.2 预留 (2/2 — 仍为 P1)

| ID | 任务 | 说明 |
|----|------|------|
| **P4.1** | **DSN 层次块子页面遍历** | B4.1 的 CFB 回退修复后，PAGE1~PAGE6 流可被读取。但 DrawnInst 子页面的叶子器件提取依赖 `_resolve_hierarchy()`（已实现于 dsn_parser.py），需在实际数据上验证层次遍历的完整性。 |
| **P4.2** | **DSN→DEHDL 坐标映射** | DSN 原始坐标与 DEHDL C SIZE PAGE 坐标系不一致。参考 `generate_hdl_sch.py:83-123` 中 `map_cis_to_dehdl_coords()`。Phase IV 未纳入此项。 |

---

### 六、验证步骤（原文）

#### 1. 单元测试

```bash
cd D:\26暑假\cis2hdl
python -m pytest tests/unit/ tests/integration/ tests/e2e/ -v --tb=short
```

预期: 144 passed, 1 skipped

#### 2. CLi 转换验证

```bash
python -m cis2hdl convert \
  "tests/fixtures/RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN" \
  --output "output_test" \
  --hdl-lib "docs_for_reference/CIStoHDL_standard/hdl_lib" \
  --benchmark
```

验证输出: 6 pages, 12 instances, 423 nets, .cpm/cds.lib/.xcon/.dcf/page1~6.csa

#### 3. 输出格式验证

```bash
# 检查 .cpm 有 cpm_version '16.6'
grep "cpm_version" output_test/8367.cpm

# 检查 cds.lib 无 ./ 前缀
cat output_test/cds.lib

# 检查 .xcon 存在且可解析
python -c "import xml.etree.ElementTree as ET; ET.parse('output_test/worklib/8367/sch_1/8367.xcon'); print('OK')"

# 检查 CSA 有 QUIT 和 C SIZE PAGE
grep "C SIZE PAGE" output_test/worklib/8367/sch_1/page1.csa
grep "QUIT" output_test/worklib/8367/sch_1/page1.csa

# 检查 FORCEADD 使用 HDL 库名 (非 DSN 层级名)
grep FORCEADD output_test/worklib/8367/sch_1/page1.csa
```

#### 4. Cadence SPB 16.6 实测

- 拷贝整个 `output_test` 文件夹到有 Cadence 的电脑
- 双击 `8367.cpm` 由 Project Manager 打开
- 确认: 不弹 UPREV、不报 SPCOCN-1891/515
- 双击页面进入 Design Entry HDL 查看原理图

#### 5. GUI 手动验证

```bash
python -m cis2hdl gui
```

- 打开 `tests/fixtures/RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN`
- 确认 Diagnostics Tab 显示文件状态 (6 pages)
- 切换到 Preview Tab 查看原理图预览
- 切换到 Errors Tab 查看错误面板
- 设置 HDL 库路径后点击 Convert
- 确认 Report Tab 显示质量评估
- 切换到 Diff Tab 查看转换差异
- 确认 Rules Tab 显示匹配规则

#### 6. Benchmark 验证

```bash
python -m cis2hdl convert \
  "tests/fixtures/RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN" \
  --output "output_bench" \
  --hdl-lib "docs_for_reference/CIStoHDL_standard/hdl_lib" \
  --benchmark
```

输出应包含各阶段耗时: Diagnose/Parse/Scan/Match/Validate/Generate

#### 7. OLB 解析验证

```bash
python -c "
from cis2hdl.core.parser.olb.olb_parser import OLBParser
from pathlib import Path
p = OLBParser()
ir = p.parse(Path('tests/fixtures/LIBRARY2CLEAN.OLB'))
print(f'Packages: {len(ir.component_db.list_all())}')
"
```

预期: 20 Packages

#### 8. E2E 测试验证

```bash
python -m pytest tests/e2e/test_rtl8367rb_full.py -v
```

预期: 9 tests passed

#### 9. Batch 转换验证

```bash
python -c "
from cis2hdl.core.engine.batch_engine import BatchConversionEngine, ProjectSpec
from pathlib import Path

specs = [ProjectSpec(
    dsn_path=Path('tests/fixtures/RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN'),
    output_dir=Path('output_batch_1'),
    hdl_lib_path=Path('docs_for_reference/CIStoHDL_standard/hdl_lib')
)]
engine = BatchConversionEngine()
report = engine.batch_convert(specs)
print(report.summary())
"
```

预期: 1/1 success

#### 10. PyInstaller 打包验证 (需在 Cadence 机器)

```bash
pip install pyinstaller
python scripts/build_exe.py --onefile
```

预期: 生成 `dist/CIS2HDL.exe`

---

### 七、Phase V: 匹配系统修复 (v0.4.6 — 2026-08-04)（原文）

#### 七-A、诊断结论

完整诊断文档: `docs/MATCHING_DIAGNOSIS_2026-08-04.md`

**DSN 二进制解析在三个维度上不可靠**：

| 维度 | 可靠率 | 原因 |
|------|:--:|------|
| refdes | 14% | strLst 条目为 OrCAD 内部 ID/占位符 (INSxxx, 纯数字, 信号名) |
| 坐标 | 35% | 760/1167 = (0,0)，RTL 格式坐标字段布局不同 |
| 页面归属 | ~5% | 95% 实例被错误归入 `14-SOC_GPIO` 页面 |

**根本原因**: HG5015 的 DSN 二进制使用 RTL 变体格式，与标准 OrCAD PlacedInstance 布局根本不同——标准格式的 `pkgName`/`reference` 是独立字段，但 RTL 格式只有一个压缩的 name 字段。

#### 七-B、P0 修复已完成 (2026-08-04)

| ID | 任务 | 文件 | 状态 |
|----|------|------|:--:|
| P0-1 | Cross Reference CSV 解析器 | `cross_ref_parser.py` (新建 ~450行) | ✅ |
| P0-1a | CrossRef 注入管线 (Stage 2.5) | `conversion_engine.py` | ✅ |
| P0-2 | FeatureExtractMatcher 去假阳性 | `feature.py` (early return + value-only搜索) | ✅ |
| P0-3 | FallbackMatcher refdes 路径修复 | `fallback.py` (part_name 优先于 library_id) | ✅ |
| P0-4 | ChipsPrtParser JEDEC_TYPE 提取 | `chips_prt.py` (新增 _RE_JEDEC_TYPE) | ✅ |
| P1-3 | part.ptf `=` 分隔符兼容 | `part_ptf.py` (re.findall fallback) | ✅ |

**测试**: 97/97 零回归 | **匹配率**: 31精确+77模糊=108/724 (15%)，但无假阳性 | **CrossRef 注入率**: 仅 14%

---

### 八、Phase VI: CrossRef 驱动架构重构 (v0.5.0 — 当前阶段)（原文）

#### 八-A、架构决策

**放弃 DSN 二进制作为组件数据源**。DSN 仅保留网络拓扑（Wire/Net 端点坐标）功能。

**新数据源模型（高内聚低耦合）**：

```
┌──────────────────────────────────────────────────────────┐
│                  各自独立的解析模块                        │
├───────────────┬───────────────┬───────────────┬──────────┤
│ CrossRef CSV  │   EDIF        │    DSN        │  OLB     │
│ → 元件身份    │ → 网络连接    │ → Wire/Net    │ → 符号   │
│ → 坐标(100%) │ → pin↔net    │ → 页面结构    │ → 引脚   │
│ → 页面归属   │ → footprint   │ → (仅拓扑)    │ → 图形   │
├───────────────┴───────────────┴───────────────┴──────────┤
│                     统一数据模型                          │
│        DesignIR + ComponentDef + ComponentInstanceIR      │
├──────────────────────────────────────────────────────────┤
│                    转换管线 (6 阶段)                       │
│  CrossRef → ScanHDL → Match → Validate → CSAWrite        │
└──────────────────────────────────────────────────────────┘
```

#### 八-B、任务分解

##### V-A: CrossRef 驱动管线重构 (P0 — 核心架构)

| ID | 任务 | 新建/修改 | 文件 | 说明 |
|----|------|:--:|------|------|
| VA-1 | 新建 CrossRef 组件目录解析器 | **新建** | `cis2hdl/core/parser/component_catalog.py` | 基于 CrossRef CSV 构建完整的 ComponentCatalog: `{refdes: CatalogEntry(value, footprint, loc_x, loc_y, page_name, library_path)}`。独立模块，零依赖。 |
| VA-2 | DSN 解析器瘦身——移除实例解析 | **修改** | `dsn/structures.py` | 删除 `_RtlStructure`, `_parse_placed_instance_rtl()`, `_split_rtl_pkg_name_reference()`, `PlacedInstance` 相关代码。保留 `Wire`, `Net`, `Port`, `Global`, `TitleBlock` 等网络/图形结构体解析。 |
| VA-3 | DSN 页面解析器瘦身 | **修改** | `dsn/page_parser.py` | 删除 PlacedInstance 调度路径。保留 Wire/Port/Global/TitleBlock/GraphicInst 解析。 |
| VA-4 | DSN 主解析器瘦身 | **修改** | `dsn/dsn_parser.py` | 删除 EDIF 类型映射、component_db 查询、实例展开相关代码。保留：OLE 读取、strLst 加载（仅供诊断）、页面流发现、网络解析。 |
| VA-5 | 转换引擎重构 | **修改** | `cis2hdl/core/engine/conversion_engine.py` | 新管线: Stage1 解析CrossRef→Catalog, Stage2 扫描HDL, Stage3 解析DSN→网络拓扑, Stage4 合并Catalog+网络, Stage5 匹配, Stage6 生成CSA。删除 `_extract_cis_components()` 的 DSN 实例遍历逻辑。删除 `_map_edif_types_to_dsn()`。 |
| VA-6 | CrossRef 为主数据源模式 | **修改** | `conversion_engine.py` | Stage 4 合并: 从 Catalog 构建 ComponentInstanceIR (refdes/value/坐标/页面), 从 DSN 网络拓扑提取 pin↔net 映射, 按页面+坐标近邻合并。 |
| VA-7 | 删除无效测试和回退逻辑 | **修改** | `tests/` | 删除测试 DSN RTL 解析的用例。更新转换测试以预期新管线行为。 |

##### V-B: 新匹配管线 (P0 — 匹配率跃升)

| ID | 任务 | 新建/修改 | 文件 | 说明 |
|----|------|:--:|------|------|
| VB-1 | ValueMatcher 电气值匹配 | **新建** | `cis2hdl/core/matcher/value_matcher.py` | 基于 part.ptf 料表数据的精确值匹配。CIS "0.2pF" → HDL capacitor part.ptf 查找 "0.2PF" → 精确匹配(conf=1.0)。独立于 FallbackMatcher。 |
| VB-2 | 匹配管线调整 | **修改** | `matcher/pipeline.py` | 新增 ValueMatcher 为第 3.5 阶段 (Exact→Fuzzy→Feature→**Value**→Fallback→Manual)。 |
| VB-3 | 匹配统计增强 | **修改** | `conversion_engine.py` | 增加按匹配策略分组的详细统计输出。 |

##### V-C: 信息页 + 图形 (P1 — 完整性)

| ID | 任务 | 新建/修改 | 文件 | 说明 |
|----|------|:--:|------|------|
| VC-1 | TitleBlock 解析增强 | **修改** | `dsn/structures.py`, `dsn/page_parser.py` | 正确调度 Cover/Clock/Power/Block 4 页的 TitleBlock(64/65) + GraphicInst 解析。解析文本行、线条、矩形。 |
| VC-2 | CSA 信息页输出 | **修改** | `csa_writer.py` | TitleBlock 文本 → ADD_COMMENT；GraphicInst → 基本图形（边框/线条）。 |
| VC-3 | OLB 符号图形集成 | **修改** | `gui/panels/schematic_view.py` | 将 OLBParser 解析的 8 种图形渲染到预览面板。 |

##### V-D: 清理与文档 (P2)

| ID | 任务 | 新建/修改 | 文件 | 说明 |
|----|------|:--:|------|------|
| VD-1 | 代码彻底清理 | **修改** | 全部 `dsn/` 文件 | 确保无死代码、无未使用的 import、无过期注释。所有函数文档字符串更新。 |
| VD-2 | 更新项目文档 | **修改** | `CHANGELOG.md`, `__init__.py`, `MEMORY.md` | 版本号 v0.5.0。记录架构变更和破坏性修改。 |
| VD-3 | 转换验证 | **测试** | HG5015 全量转换 | 预期匹配率 ≥90%，坐标 100% 正确，页面归属 100% 正确。 |

#### 八-C、新模块架构（低耦合设计）

```
cis2hdl/core/parser/
├── cross_ref_parser.py       → CrossRef CSV 解析 (独立)
├── component_catalog.py      → 统一组件目录 (独立，组合 CrossRef + pstxprt)
├── edif_parser.py            → EDIF 网络连接 (独立)
├── dsn/
│   ├── ole_reader.py         → CFB 容器读取 (独立)
│   ├── dsn_parser.py         → 页面流发现 + 网络解析 (依赖 ole_reader)
│   ├── page_parser.py        → Wire/Port/TitleBlock 解析 (依赖 structures)
│   └── structures.py         → 二进制结构体定义 (独立)
├── hdl_scanner.py            → HDL 库扫描 (独立)
└── pstxnet_parser.py         → pstxprt.dat 解析 (可选，独立)

cis2hdl/core/matcher/
├── exact.py                  → 指纹精确匹配
├── fuzzy.py                  → 名称模糊匹配
├── feature.py                → 电气特征匹配
├── value_matcher.py          → [NEW] 值精确匹配
├── fallback.py               → 前缀回退匹配
└── pipeline.py               → 匹配管线编排

cis2hdl/core/engine/
└── conversion_engine.py      → 转换管线编排 (6阶段)
```

**关键原则**：
- 每个解析模块**零相互依赖**，仅依赖 `core/ir/` 数据模型
- 数据融合在 `conversion_engine.py` 的 Stage 4 中完成
- 各模块可独立测试、独立替换、独立对接 GUI
- `component_catalog.py` 是唯一元件身份权威来源

#### 八-D、数据流设计

```
Stage 1: Parse
  CrossRef CSV ──→ ComponentCatalog {refdes → CatalogEntry}
  DSN ──→ NetTopology {page → [Wire, Net, Port]}
  HDL Lib ──→ ComponentDB {library_id → ComponentDef}
  [OPTIONAL] EDIF ──→ NetConnections {refdes → {pin → signal}}

Stage 2: Merge (在 conversion_engine 中)
  FOR each page in CrossRef (grouped by page_name):
    FOR each refdes in page:
      CREATE ComponentInstanceIR(
        refdes=refdes,
        value=CatalogEntry.value,
        loc_x=CatalogEntry.x_mils,
        loc_y=CatalogEntry.y_mils,
        page_name=CatalogEntry.page_name
      )
    END FOR
  END FOR
  ATTACH pin_connections from EDIF or DSN (by refdes)

Stage 3: Match
  FOR each ComponentInstanceIR:
    prefix = extract_refdes_prefix(refdes)  # "C"→capacitor
    value = instance.value_override          # "0.2P"→电容值
    MATCH against HDL ComponentDB
    ↓
    Exact/Fuzzy/Feature/Value/Fallback

Stage 4: Generate CSA
  USE CrossRef coordinates (100% accurate)
  USE matched HDL library_id (from Stage 3)
  USE DSN net topology (wire paths + net aliases)
```

#### 八-E、预期效果

| 指标 | 修复前 (v0.4.6) | 预期 (v0.5.0) |
|------|:--:|:--:|
| refdes 准确率 | 14% | **100%** |
| 坐标准确率 | 35% | **100%** |
| 页面归属准确率 | 5% | **100%** |
| 自动匹配率 | 15% | **≥90%** |
| 假阳性匹配 | 0 (已修复) | **0** |
| 测试通过率 | 97/97 | **97/97 (零回归)** |

#### 八-F、待明确事项

| # | 事项 | 优先级 |
|---|------|:--:|
| 1 | DSN 网络拓扑（Wire 端点坐标）能否正确提取？ | P0 — 影响 CSA 网络线生成 |
| 2 | 无 EDIF 时，网络连接如何重建？（仅靠 DSN Wire 坐标近邻匹配） | P1 |
| 3 | CrossRef 和 EDIF 的 refdes 一致性如何？（是否需要 fuzzy mapping） | P1 |
| 4 | 没有 CrossRef CSV 时的回退方案？（保留现有 DSN 路径作为 legacy 模式） | P2 |

---

### 九、Phase VII: 匹配增强 + Pin 连接注入 (v0.6.0 — 2026-08-05)（原文）

#### 九-A、已完成

| ID | 任务 | 文件 | 状态 |
|----|------|------|:--:|
| P7-1 | PREFIX_TO_CATEGORY 扩展 11 个新前缀 | `prefix_filter.py` | ✅ |
| P7-2 | _PREFIX_TO_HINT 同步 + ROUTE 过滤 | `component_catalog.py` | ✅ |
| P7-3 | "0" 值元件 prefix_zero tier 增强 | `fallback.py` | ✅ |
| P7-4 | EDIFPin 连接提取管线 | `edif_parser.py` + `conversion_engine.py` | ✅ |
| P7-5 | CHANGELOG/MEMORY 更新 | 文档 | ✅ |

**验证数据**: 122/122 测试零回归，实例数 914→889，匹配率 96.3%→99.9%

#### 九-B、DSN 文件价值评估

**结论：DSN 对当前项目作用有限，可以降级为辅助角色。**

| 维度 | 评估 |
|------|------|
| 组件身份 (refdes/value) | ❌ RTL 格式产生大量乱码（INSxxx/纯数字/信号名），已放弃 |
| 坐标 | ❌ 760/1167 为 (0,0)，坐标精度仅 35%。**CrossRef CSV 提供 100% 准确坐标** |
| 页面归属 | ❌ 95% 实例被错误归入 `14-SOC_GPIO` 页面。**CrossRef CSV 提供 100% 准确页面归属** |
| 网络拓扑 (Wire/Net) | ✅ 3717 nets 从 DSN Wire/Port/Alias 成功重建 |
| 信息页文本 | ✅ `_extract_info_page_graphics()` 提取 TitleBlock 文本 |

**核心决策**：CrossRef CSV = 主数据源（身份+坐标+页面），DSN = 网络拓扑补充。无需再恢复 DSN 的 PlacedInstance 解析。

**坐标系说明**：
- CrossRef CSV 坐标单位：英寸×100（如 165.00 = 165.00 英寸）
- DEHDL C SIZE PAGE 范围：左下(-10750, 0) ~ 右上(0, 8275)，DEHDL 内部单位
- 坐标映射参考：`generate_hdl_sch.py:83-123` 的 `map_cis_to_dehdl_coords()` 函数
  - 计算 CIS 全局包围盒 → 按 0.7 比例缩放 → 居中映射到 C 纸可用区域
  - 当前 csa_writer.py 使用该映射逻辑（`_map_coords_to_dehdl()`）

#### 九-C、已知限制

| # | 限制 | 影响 | 计划 |
|---|------|------|------|
| L1 | **EDIF INSxxx→real_refdes 映射缺失** | EDIF 使用内部 ID (INS277)，真实 refdes (C122) 仅以 display string 出现。908 refdes × 2771 pin 连接已提取但无法匹配到 Catalog refdes | Phase VIII 研究替代方案 |
| L2 | **OLB 符号匹配到通用名** | CSA FORCEADD 使用 "capacitor..1" 而非 "CAPACITOR_0402..1"，DEHDL 可能找不到正确符号图形 | Phase VIII 通过 part.ptf value 匹配选择具体 primitive |
| L3 | **坐标映射待验证** | DSN→DEHDL 坐标映射在 Cadence SPB 16.6 中实测验证尚未完成 | Phase VIII 实测校准 |

---

### 十、Phase VIII: 精准匹配 + 坐标校准 + OLB Primitive 选择 (v0.7.0 — 2026-08-05 ✅)（原文）

#### 十-A、目标

| 指标 | 修复前 (v0.6.0) | 实际 (v0.7.0) |
|------|:--:|:--:|
| 匹配置信度≥0.6 | 763/889 (86%) | **888/889 (99.9%)** |
| OLB Primitive 精准选择 | 0% (全部通用名) | **81.6%** (CAPACITOR_0402×321 + RESISTOR_0402×171) |
| 坐标映射 | 理论就绪 | **与 generate_hdl_sch.py 对齐** |
| 元件标称值 | 部分缺失 | **99.3%** (883/889) |

#### 十-B、已完成任务 (5/5 ✅)

| ID | 任务 | 文件 | 状态 |
|----|------|------|:--:|
| VA-1 | HDL Scanner 存储所有 primitives | `hdl_scanner.py` | ✅ |
| VA-2 | ValueMatcher/FallbackMatcher primitive 选择 | `value_matcher.py` + `fallback.py` | ✅ |
| VA-3 | CSA writer body_name 解析 | `csa_writer.py` | ✅ |
| VB-1~3 | 坐标映射校准 | `csa_writer.py` (已对齐) | ✅ |
| VC-1~3 | 元件标称值 100% 注入 | `mapping_csv_writer.py` | ✅ |

#### 十-C、遗留 Phase IX 任务

| ID | 任务 | 状态 | 优先级 |
|----|------|:--:|:--:|
| IX-1 | EDIF INSxxx→real_refdes 映射 (display string 提取) | ✅ v0.7.1 | P1 |
| IX-2 | FallbackMatcher unity boost (单一候选 conf→0.65) | ✅ v0.7.1 | P1 |
| IX-3 | 质量指标重算（Stage 1 DSN→Stage 6 Catalog 数据） | ✅ v0.7.2 | P0 |
| IX-4 | Missing_Footprint 抑制（Catalog 模式） | ✅ v0.7.2 | P1 |
| IX-5 | INDUCTOR/DIODE/CONNECTOR 无尺寸变体精准匹配 | ✅ v0.8.1 | P2 |
| IX-6 | Cadence SPB 16.6 实测验证 | 📋 | P0 |
| IX-7 | 125 模糊匹配逐类审计 | ✅ v0.8.2 | P1 |
| IX-8 | 无 CrossRef CSV 时的 legacy DSN 回退 | 📋 | P2 |
| IX-9 | J* 连接器匹配不一致（con3 vs connector） | ✅ v0.8.2 | P1 |
| IX-10 | R* 电阻 FallbackMatcher vs ValueMatcher 不一致 | ✅ v0.8.2 (NH/UH→inductor) | P1 |

#### 十-F、Phase IX 新增任务 (v0.8.x — 2026-08-05)

| ID | 任务 | 状态 | 优先级 |
|----|------|:--:|:--:|
| IX-11 | pstchip.dat 解析器 (JEDEC_TYPE/VALUE/pins) | ✅ v0.8.0 | P0 |
| IX-12 | pstxnet.dat 网络连接解析器 | ✅ v0.8.0 | P0 |
| IX-13 | pstxprt→pstchip 查找桥 (build_pstchip_lookup) | ✅ v0.8.0 | P0 |
| IX-14 | PST 数据注入管线 (Stage 2.3/2.5b/5.5b) | ✅ v0.8.0 | P0 |
| IX-15 | JEDEC_TYPE 精确匹配 (exact.py fallback) | ✅ v0.8.0 | P0 |
| IX-16 | 278页→24页 BUG 修复 (file_inventory + xref共享) | ✅ v0.8.2 | P1 |
| IX-17 | Value match warning 消息修复 | ✅ v0.8.0 | P1 |
| IX-18 | DZ_前缀→zener 映射 | ✅ v0.8.0 | P2 |
| IX-19 | VALUE→CATEGORY 映射表 (DZ/MJ8/TESTPOINT/NH) | ✅ v0.8.2 | P2 |
| IX-20 | 输出文件去重 (output_files dedup) | ✅ v0.8.2 | P1 |
| IX-21 | CSA页面编号修复 (page_name→数字) | ✅ v0.8.2 | P1 |
| IX-22 | 信息页 ADD_COMMENT 标题 | ✅ v0.8.2 | P3 |
| IX-23 | PST 单元测试 (test_pst_parsers.py, 12 tests) | ✅ v0.8.2 | P1 |
| IX-24 | xref页面共享 (同页归并) | ✅ v0.8.2 | P1 |

#### 十-G、最终状态 (v0.8.2)

| 指标 | 值 |
|------|:--:|
| 页面 | 24 (20原理图 + 4信息页) |
| CSA文件 | 24 page1-page24.csa |
| 匹配成功 | 845/889 (95.1%) |
| 匹配失败 | 44 |
| 网络 | 3717 nets |
| Pin连接 | 2713 EDIF + 14 PSTXNET |
| No_Pin_Connections | 0 |
| Value match误报 | 0 |
| 测试 | 109 passed, 6 skipped |

#### 十-H、遗留事项

| ID | 任务 | 优先级 |
|----|------|:--:|
| IX-6 | Cadence SPB 16.6 实测验证 | P0 |
| IX-8 | 无 CrossRef CSV 时的 legacy DSN 回退 | P2 |
| T04-2 | test_pst_matching.py (匹配测试) | P2 |
| T04-3 | test_file_inventory.py 修改 | P3 |
| — | 信息页 TitleBlock 深度解析 (参考OpenOrCadParser StructTitleBlock) | P3 |

**验证数据**: 97 tests passed, 823 refdes × 1818 pstxnet connections, EDIF 2713 + PSTXNET 14 pin injections

| IX-7 | 125 模糊匹配逐类审计 | 📋 | P1 |
| IX-8 | 无 CrossRef CSV 时的 legacy DSN 回退 | 📋 | P2 |
| IX-9 | J* 连接器匹配不一致（con3 vs connector） | 📋 待修 | P1 |
| IX-10 | R* 电阻 FallbackMatcher vs ValueMatcher 不一致 | 📋 待修 | P1 |

#### 十-D、质量指标说明（v0.7.2 修复后）

| 指标 | 旧值 (DSN-based) | 新值 (Catalog-based) | 含义 |
|------|:--:|:--:|------|
| 逻辑完整性 | 70% | **100%** | Catalog 提供完整组件身份 |
| 坐标可用性 | 100% (碰巧) | **100%** | CrossRef CSV 提供 100% 坐标 |
| 匹配覆盖率 | 88% | **99.9%** | 实际匹配管线结果 |
| 符号保真度 | 28% | **50%** | 使用 HDL 符号（非原始 CIS OLB） |
| 综合质量 | 75% | **98%** | 加权综合分 |

#### 十-E、当前匹配低置信度根因分析

| 现象 | 根因 | 修复方向 |
|------|------|------|
| J* → con3 (50%) vs connector (70%) | FeatureExtractMatcher vs FallbackMatcher 路径不同 | 统一 J* 优先级 |
| R* → 100% VALUE vs 65% FALLBACK | 部分电阻值不在 HDL part.ptf 中 | 扩展 part.ptf 或 fuzzy 值匹配 |
| D* → 全 50-55% | 二极管 value="DZ_L"/"DZ3" 为型号非电气值 | 型号→二极管类型映射 |
| Missing_Footprint ×889 | Catalog 不含 PCB footprint（设计如此） | 已抑制警告 |
| 标签不匹配 | 硬件设计中 ET=变压器, XS=接插件 但 HDL 库使用不同命名 | 映射表对齐 |

| # | 事项 | 优先级 |
|---|------|:--:|
| 1 | CrossRef CSV 坐标 (英寸×100) 到 DEHDL C-page 坐标的精确映射参数？ | P0 |
| 2 | Cadence SPB 16.6 实测验证坐标和 primitive 选择是否正确？ | P0 |
| 3 | EDIF display string 提取真实 refdes 的可靠性？ | P1 |
| 4 | 是否需要为 HDL 库中每个 primitive 单独创建 ComponentDef？ | P1 |

---

### 十一、Phase X: Cadence SPB 16.6 实测兼容性修复 (v0.9.0 — 2026-08-06)（原文）

#### 十一-A、实测环境

- **Cadence 版本**: SPB 16.6 (Allegro Design Entry HDL)
- **测试项目**: output_final/5015.cpm
- **测试数据源**: errors.txt (612 行错误日志)
- **文件路径**: E:\26summer\CIS2HDL\tests\fixtures\output_final\

#### 十一-B、实测发现的问题总览

| # | 错误码 | 严重度 | 现象 | 影响页面 |
|---|--------|:--:|------|------|
| 1 | SPCOCN-515 | **ERROR** | CAPACITOR_0402.SYM.1.1 / RESISTOR_0402.SYM.1.1 找不到 | page6/8/10-13/15/17 |
| 2 | SPCOCN-543 | WARNING | SIG_NAME 属性被删除 (N35175\g, N29334\g, 3V3_PERg) | 多个页面 |
| 3 | SPCOCN-1909 | **ERROR** | page23.csa line 2: Unknown word ADD_COMMENT | page23 |
| 4 | SPCOCN-1910 | **ERROR** | page24.csa line 1: bad token, syntax error | page24 |
| 5 | SPCOCN-1908 | **ERROR** | page23.csa line 2: { and } don't match | page23 |
| 6 | SPCOCN-542 | INFO | HOLE 组件默认属性被删除 | page13/15 |
| — | — | 观察 | 绝大多数元件无 symbol 显示 | 全局 |
| — | — | 观察 | page 名称仍为 page1/2/3... | 全局 |
| — | — | 观察 | 信息页完全空白 (仅 C SIZE PAGE) | page1-4 |
| — | — | 观察 | 连线和网络完全缺失 | 全局 |
| — | — | 观察 | 二十几页空白，连 C SIZE PAGE 都没有 | page23+ |

#### 十一-C、根因分析

##### 根因 1 (P0): FORCEADD body_name 使用了 primitive 名而非 cell 名

**核心发现**: 通过对比参考实现 (`docs_for_reference/CIStoHDL_standard/worklib/out_hdl/sch_1/page1.csa`) 与当前输出，确认了关键格式差异：

| 维度 | 参考实现 (正常) | 当前输出 (错误) |
|------|------|------|
| FORCEADD | `CAPACITOR..1` (cell 名) | `CAPACITOR_0402..1` (primitive 名) |
| PART_NAME | `CAPACITOR_0201` (primitive 名) | `CAPACITOR_0402` (同 body) |
| 符号解析 | Cadence 在 `hdl_lib/capacitor/` 找到 cell | Cadence 寻找 `hdl_lib/CAPACITOR_0402/` → 找不到 |

**DEHDL 库结构**:

```
hdl_lib/
├── capacitor/           ← cell 名 = "capacitor"
│   ├── chips/
│   │   └── chips.prt    ← 定义 primitive: CAPACITOR_0402, CAPACITOR_0603...
│   └── sym_1/
│       └── symbol.css   ← 符号图形
```

FORCEADD `CAPACITOR_0402..1` → Cadence 查找 cell `CAPACITOR_0402` → 不存在 → **SPCOCN-515**

**源码位置**: `cis2hdl/core/writer/csa_writer.py:_resolve_body_name()` (line 597-635)
- Line 616-618: `selected_primitive_body` 被直接返回为 FORCEADD body_name **【错误】**
- 该值应仅用于 PART_NAME 属性，不应替代 cell/library_id
- Line 630: 回退路径 `hdl_id.rsplit("/", 1)[-1]` 返回 cell 名，行为正确

**影响范围**:
- CAPACITOR_0402 (321 实例) → 全部无符号
- RESISTOR_0402 (171 实例) → 全部无符号
- 其他返回 cell 名的组件 (DIODE, INDUCTOR, LED, HOLE, CATV, INTERFACE 等) → **正常显示符号**

##### 根因 2 (P0): LASTPIN SIG_NAME 方案与参考实现不一致

**核心发现**: 参考实现 `generate_hdl_sch.py` **完全没有任何 LASTPIN 或 SIG_NAME 生成**。原始 CIS2HDL 工具不通过 CSA 注入 pin 连接。

当前实现的问题:
1. **`\g` 后缀误用**: DEHDL CSA 中 `\g` 表示 global signal (GND/VCC)，但 N35175 等是普通网络
2. **反斜杠逃脱 bug**: `sig_name.replace("\\", "\\\\")` + `f"...\\g"` → 在某些网络名下产生 `3V3_PERg`（缺少反斜杠）
3. **网络名不匹配**: EDIF 的 N35175/N29334/N1402987 是 EDIF 内部标识符，不是真实设计网络名
4. **`.con` 文件无网络定义**: worklib/5015/sch_1/5015.con 中 nets/instances 均为空 → Cadence 找不到这些网络 → 删除 SIG_NAME

**源码位置**: `csa_writer.py` line 431-452

##### 根因 3 (P1): CSA 语法错误 (page23/page24)

**分析**: 当前 D:\26暑假 版本的 page23.csa 和 page24.csa 语法正确（FILE_TYPE header 完整）。错误可能来自:
- 旧版本输出被复制到 Cadence 机器
- 文件复制过程中损坏（编码转换、路径截断等）
- 建议: 重新生成最新输出并验证复制完整性

##### 根因 4 (P1): ADD_COMMENT 格式不一致

两处 ADD_COMMENT 生成使用不同格式:
- Line 257: `ADD_COMMENT (-9500 7800) 0 "[page_name]";` — 坐标含括号
- Line 558: `ADD_COMMENT {pos} 0 "{escaped}";` — 纯数字坐标

参考实现中未使用 ADD_COMMENT（信息页通过其他方式处理）。

##### 根因 5 (P1): 信息页文本乱码

page1.csa 中 ADD_COMMENT 行包含乱码:
- `"ÂWrgò4qjd"` — 非预期的 TITLE123 文本
- 原因: DSN TitleBlock 二进制文本使用 OrCAD 专有编码，未正确解码
- `_extract_info_page_graphics()` (page_parser.py) 提取的字节被当作 Latin-1/UTF-8 解析

##### 根因 6 (P2): 网络连线完全缺失

参考实现中也不包含网络连线。DEHDL 的连线通常在:
1. 设计过程中手动绘制
2. 或通过 `.con` 文件中的约束定义
3. 或通过 PAINT WIRE 命令在 CSA 中绘制

当前 CSA 仅有 LASTPIN SIG_NAME（且被删除），无 PAINT WIRE 命令 → 无可见连线。

##### 根因 7 (P2): PAGE_NUMBER 命名

SET PAGE_NUMBER 使用 P1-P24，EDIT PAGE NAME 正确设置。用户报告 page 名称显示为 page1/2/3 可能是 Cadence DEHDL 的默认行为 — 它使用 PAGE_NUMBER 而非 EDIT PAGE NAME 作为 Tab 标签。

#### 十一-D、修复方案

##### 修复 1 (P0): 分离 FORCEADD body_name 与 PART_NAME

**修改文件**: `cis2hdl/core/writer/csa_writer.py`

**方案**: `_resolve_body_name()` 返回 cell/library_id，新增 `_resolve_part_name()` 返回 primitive 名。

```python
# Line 296: 使用 cell 名做 FORCEADD
body_name: str = self._resolve_body_name(inst)  # 修改为返回 cell 名

# Line 380-383: PART_NAME 使用 primitive 名
part_name: str = self._resolve_prop(props, "PART_NAME")
if not part_name:
    part_name = self._resolve_primitive_name(inst)  # 新增方法
```

**`_resolve_body_name()` 修改** (line 597-635):
- 移除 `selected_primitive_body` 的提前返回（line 616-618）
- 始终返回 `comp.library_id.rsplit("/", 1)[-1].upper()` (cell 名)

**新增 `_resolve_primitive_name()`**:
- 检查 `comp.extra_data["selected_primitive_body"]` → 返回 primitive 名
- 检查 JEDEC_TYPE → 查找对应 primitive
- 回退到 body_name（通用 cell 名）

##### 修复 2 (P0): LASTPIN SIG_NAME 策略调整

**方案 A (推荐)**: 移除 CSA 中的 LASTPIN SIG_NAME 生成，与参考实现对齐。
- 优点: 零风险，消除所有 SPCOCN-543 警告
- 缺点: 丢失 pin 连接信息
- 后续: 可通过完善 `.con` 文件定义网络来恢复连通性

**方案 B**: 修复 LASTPIN 格式。
- 移除 `\g` 后缀（普通网络不应使用全局标记）
- 修复反斜杠逃脱逻辑
- 问题: EDIF 网络名仍与设计不匹配，Cadence 仍会删除

**建议**: 采用方案 A（移除），后续通过独立的 `.con` 文件生成来支持网络连接。

##### 修复 3 (P1): 信息页重构

1. 移除 ADD_COMMENT 中包含乱码的行
2. 仅保留 page_name 标题注释（格式标准化）
3. 后续: 研究 TitleBlock 文本编码解码

##### 修复 4 (P1): ADD_COMMENT 格式标准化

统一为 `ADD_COMMENT X Y "text";` 格式（无括号），X 和 Y 使用有效 DEHDL C SIZE PAGE 坐标。

##### 修复 5 (P2): SET PAGE_NUMBER 改为页标题

将 `SET PAGE_NUMBER` 从 `P1` 改为实际标题（如 `01-Cover_Page`），使 DEHDL 页面标签显示有意义的名称。

#### 十一-E、任务分解 (全部完成 ✅)

| ID | 任务 | 优先级 | 状态 |
|----|------|:--:|:--:|
| **X-1** | `_resolve_body_name()` 改为返回 cell 名 | **P0** | ✅ |
| **X-2** | 新增 `_resolve_part_name()` 返回 primitive 名 | **P0** | ✅ |
| **X-3** | PART_NAME 属性使用 primitive 名 | **P0** | ✅ |
| **X-4** | 移除 LASTPIN SIG_NAME 生成 | **P0** | ✅ |
| **X-5** | ADD_COMMENT 格式标准化 | P1 | ✅ |
| **X-6** | 信息页乱码文本过滤 | P1 | ✅ |
| **X-7** | SET PAGE_NUMBER 改为页标题 | P2 | ✅ |
| **X-8** | **PAINT WIRE 连线渲染** (DSN Wire→CSA) | P2 | ✅ |
| **X-9** | 全量回归测试 (134/134) | **P0** | ✅ |
| **X-10** | Cadence SPB 16.6 二次实测 | **P0** | 📋 待执行 |

#### 十一-F、实际效果 (v0.9.0)

| 指标 | 修复前 | 修复后 |
|------|:--:|:--:|
| SPCOCN-515 错误 | 8 页面报错 | **0** |
| SPCOCN-543 警告 | 10 条 SIG_NAME 删除 | **0** |
| SPCOCN-1909/1910/1908 | page23/24 语法错误 | **0** |
| 元件 symbol 显示率 | ~20% | **~95%** |
| 页面名称 | P1/P2/... | **01-Cover_Page**/... |
| PAINT WIRE 线段 | 0 | **7 页 16 段** (DSN Wire 驱动) |
| 全量测试 | n/a | **134 passed, 0 failed** |

#### 十一-G、风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|:--:|------|------|
| cell 名大小写不匹配 | 中 | FORCEADD 仍失败 | Cadence 不区分大小写（已验证 CAPACITOR/capacitor 均可用） |
| 移除 LASTPIN 丢失 Pin 数据 | 低 | 网络连接信息丢失 | 当前 LASTPIN 本就被删除，无实际损失；后续通过 .con 恢复 |
| 回归 bug | 低 | 匹配管线或坐标映射受影响 | 全量 109 测试 + 新增 CSA 格式测试 |
| Cadence 二次实测仍有问题 | 中 | 需要多轮迭代 | 保留 errors.txt 对比基准 |

#### 十一-H、文件修改清单

| 文件 | 修改类型 | 变更内容 |
|------|:--:|------|
| `cis2hdl/core/writer/csa_writer.py` | **修改** | X-1~X-8 全部修改（FORCEADD/PART_NAME/LASTPIN移除/ADD_COMMENT/PAGE_NUMBER/PAINT WIRE） |
| `cis2hdl/core/parser/dsn/dsn_parser.py` | **修改** | wire_net_map 始终构建 + IRWireSegment net_name 填充 (X-8) |
| `CHANGELOG.md` | **修改** | v0.9.0 条目 |
| `ROADMAP_AUDIT_2026-08-03.md` | **修改** | Phase X 条目 (本文) |
| `.workbuddy/memory/MEMORY.md` | **修改** | 项目记忆更新 |
| `.workbuddy/memory/2026-08-06.md` | **修改** | 日工作日志 |

---

## Part III 合并裁决与最新状态（新增章节）

> **说明**: 本部分为 2026-08-07 合并时新增的附加章节（非两份源文档原文）。其作用：① 说明两份文档的重复内容与以何者为准；② 汇总 Phase I→X + 匹配系统 v2.0 的完成度；③ 裁决原文中的矛盾点；④ 记录合并时的代码核查结果；⑤ 给出当前状态摘要；⑥ 附"源文档章节 → ROADMAP 位置"映射表，证明内容保全 100% 覆盖。

### III.1 两份文档重复内容对照表

| 主题 | DEVELOPMENT_ROADMAP.md（Part I） | ROADMAP_AUDIT_2026-08-03.md（Part II） | 合并裁决 |
|------|------|------|------|
| Phase I 任务分解 | B1.1~B1.24 + D1.1~D1.6 + F1.1~F1.7 完整表格 | 二、Phase I 逐项清点（22/22）汇总表 | 两者互补：Part I 为完整任务定义，Part II 为清点结论。均已保留。 |
| Phase II 任务分解 | B2.1~B2.13 + D2.1~D2.7 + F2.1~F2.10 完整表格 | 三、Phase II 逐项清点（30/30）——指向 CHANGELOG 清点表 | 同上。 |
| Phase III 任务分解 | B3.1~B3.6 + D3.1~D3.4 + F3.1~F3.7 完整表格 | 四、Phase III 逐项清点（16/16）——含实现文件列 | 两者对应同一组任务；Part II 补充了"实现文件"列。均已保留。 |
| Phase IV 完成状态 | "Phase IV: Validation & Coverage Enhancement"（9 项 + 144 passed + P4.1/P4.2 预留） | 五、Phase IV（9/9，含五-A~五-F 分项清点 + 实现文件 + 验证数据） | 纯重复主题：均已保留；**以 AUDIT（Part II）为权威口径**（更详尽），Part I 保留 DEVELOPMENT_ROADMAP 的原始表述。 |
| P4.1/P4.2 预留 | Part I "Phase IV 预留（完成于 Phase V 前）"表 + "Phase IV（Cadence 实测后发现的改进项）"表 | Part II 五-F "P4.1/P4.2 预留 (2/2 — 仍为 P1)" | 重复主题：均已保留；Part I 记其最终完成（✅ 已实现），Part II 记其早期预留状态（仍为 P1）。以完成状态为准。 |
| Phase V 匹配增强 | Part I "Phase V: HG5015 匹配增强与数据质量修复"（V-A1/A2、V-B1/B2、V-C1/C2 详细任务书） | Part II 七、Phase V: 匹配系统修复（v0.4.6，诊断结论 + P0-1~P1-3 修复清单） | 主题相关但内容不同：Part I 为 8/4 起的详细任务书，Part II 为 8/4 的修复完成清单（DSN 不可靠诊断 + CrossRef 修复）。均已保留。 |
| Phase VI 任务分解 | （Part I 未覆盖，止于 Phase V） | Part II 八、Phase VI（V-A/V-B/V-C/V-D 任务分解 + 架构） | 仅存在于 Part II，无重复。 |
| Phase VII~X 追加 | （Part I 未覆盖） | Part II 九、十、十一 | 仅存在于 Part II，无重复。 |
| 验证步骤 | （Part I 无独立章节） | Part II 六、验证步骤（10 步） | 仅存在于 Part II。 |

> **有意省略说明**: 本次合并**未省略任何源文档章节/任务编号/表格/附录**。两份文档的全部内容均已按上述对照逐节保留于 Part I / Part II。唯一的形式调整是标题层级（原文 `#`→`###`、`##`→`###`/`####` 等）以适配合并文档结构，未删减、未改写任何句子。

### III.2 阶段完成度汇总表

> 日期/版本/状态以**项目参数卡 v1.1（权威口径）**为准；各阶段更细的完成内容见 Part I / Part II 对应章节。

| 阶段 | 日期 | 版本 | 完成内容摘要 | 状态 |
|------|------|------|------|:--:|
| Phase I Foundation | 2026-07-30 | v0.3.0 | 双路解析 + 诊断基础设施 Layer 1 + GUI 骨架 | ✅ |
| Phase II Core Pipeline | 2026-07-31 | v0.3.2 | 匹配→校验→生成管道 + 诊断/容错引擎 | ✅ |
| Phase III Polish & Release | 2026-08-03 | — | OLB 解析器 + 批量转换 + 打包（16/16 任务） | ✅ |
| Phase IV Validation & Coverage | 2026-08-03 | — | P4.1/P4.2 + CFB 修复 + CrossValidator 8 项（70/70） | ✅ |
| Phase V 匹配增强（V-A/B/C） | 2026-08-03 起重构 | — | HG5015 匹配修复（FallbackMatcher/EDIF 反注/Cache 修复/refdes 分离） | ✅ |
| Phase VI CrossRef 驱动架构重构 | 2026-08-04 | v0.5.0 | CrossRef 主数据源，匹配 15%→96.3% | ✅ |
| Phase VII 匹配增强 + Pin 连接注入 | 2026-08-05 | v0.6.0 | PREFIX 扩展 + EDIFPin 连接管线 | ✅ |
| Phase VIII 精准匹配 + 坐标校准 | 2026-08-05 | v0.7.0 | 888/889（99.9%），OLB Primitive 精准选择 | ✅ |
| Phase IX PST 集成 | 2026-08-05 | v0.8.x | pstchip/pstxnet 解析 + 数据注入 + 24 页修复 | ✅ |
| Phase X Cadence SPB 16.6 实测修复 | 2026-08-06 | v0.9.0 / v1.0.0 | 实测 8 项修复（FORCEADD/LASTPIN/ADD_COMMENT/PAINT WIRE 等） | ✅ |
| 匹配系统 v2.0 | 2026-08-07 | v1.1.0 | 匹配系统 v2.0 完成（PAINT WIRE 移除） | ✅ |

### III.3 矛盾点裁决表

| # | 主题 | 源文档记载 | 最新状态（权威口径） | 裁决 |
|---|------|------|------|------|
| 1 | PAINT WIRE 连线 | ROADMAP_AUDIT 十一-F 记 "PAINT WIRE 线段 0 → **7 页 16 段** (DSN Wire 驱动)"（v0.9.0 实测后） | **PAINT WIRE 生成器已于 2026-08-07 移除**（匹配系统 v2.0） | 以"已移除"为最新状态；原文"7 页 16 段"作为 v0.9.0 历史实测记录保留于 Part II，不删除。 |
| 2 | 测试数量（时间线） | Part I Phase II 记 76/76、93 passed；AUDIT Phase II 记 201 tests；AUDIT Phase IV 记 144 passed + 1 skipped；AUDIT Phase VIII 记 109 passed；AUDIT Phase X 记 134 passed、0 failed | **268 passed / 23 skipped / 0 failed（291 collected）**（v1.1.0 测试基线） | 以 268/23/0 为最新基线；历史数字为各阶段即时值，按时间递增保留原文。 |
| 3 | 错误码数量 | Part I D2.1 目标 "31 错误码体系（对标 Canvas 31 错误码）"；Part I Phase II 验收记 "ErrorDiagnosisEngine 覆盖 39 错误码" | **44**（v1.1.0，代码 error_diagnosis.py 实注册 44 条） | 以 44 为最新；39 为历史口径（漏算 OLB 51-55）；31 为早期对标目标值（对标 Canvas），原文保留。 |
| 4 | Phase III 清点数量 | ROADMAP_AUDIT 四、标题记 "16/16 ✅"，但逐项表格实际列出 **17 行**（B3.1~B3.6=6、D3.1~D3.4=4、F3.1~F3.7=7） | 参数卡 v1.1 记 "Phase III（16/16 任务）✅" | 以 16/16 为官方口径；表格 17 行为原文档实际内容，原文照录未改动。 |
| 5 | 匹配率口径 | Part I Phase V 记 HG5015 39%→63%；AUDIT 七-B 记 15%（108/724）；AUDIT 八-E 记 v0.5.0 预期 ≥90%；AUDIT 九-A 记 96.3%→99.9% | 匹配覆盖 889/889、声称匹配率 **92.4%（822/889）**、quality **72%** | 以 92.4%（822/889）为当前权威口径；99.9% 为 Phase VIII（v0.7.0）置信度≥0.6 历史口径；各阶段目标/实测值不同属正常演进，原文保留。 |
| 6 | 综合质量 | AUDIT 十-D 记 v0.7.2 综合质量 **98%**（Catalog-based 新值，旧值 75%） | **quality 72%**（参数卡 v1.1.0） | 以参数卡 v1.1.0 的 72% 为当前权威口径；98% 为 v0.7.2 时的历史口径（口径/计算可能已调整），原文保留。 |
| 7 | 清点总览合计 | AUDIT 一、记 "合计 79、已实现 77、未实现 2、通过率 97%" | — | 原文照录；79 项 = Phase I 22 + Phase II 30 + Phase III 16 + Phase IV 9（与各章标题一致）。 |
| 8 | 目录结构 / 命名 | AUDIT 各表使用 `writer/`、`parser/`、`diagnostics/` 等路径写法 | 实测目录：cis2hdl/{config,core,gui,utils}；core/{parser,matcher,writer,validator,ir,engine,db,diagnostics}；**无 version/layout/cli/generator 目录**（生成器写作 writer/） | 目录结构核查通过（见 III.4）；原文路径写法照录。 |
| 9 | 测试数字 144→268 | AUDIT 五-E 记 CFB 修复测试通过 144/145、六、验证步骤预期 144 passed 1 skipped | 268 passed / 23 skipped / 0 failed（v1.1.0） | 历史基线按时间演进，原文保留，以最新为权威。 |

### III.4 代码核查结果（2026-08-07 合并时抽查）

**核查范围**: ROADMAP_AUDIT 四、Phase III 逐项清点的实现文件（7 项）+ 十一-H Phase X 文件修改清单（2 项代码文件），在 `D:\26暑假\cis2hdl\cis2hdl\` 下抽查存在性。

| 文件（源文档记载） | 实际路径 | 存在性 |
|------|------|:--:|
| `olb/olb_reader.py` | `cis2hdl/core/parser/olb/olb_reader.py` | ✓ |
| `olb_parser.py` | `cis2hdl/core/parser/olb/olb_parser.py` | ✓ |
| `batch_engine.py` | `cis2hdl/core/engine/batch_engine.py` | ✓ |
| `history.py` | `cis2hdl/core/diagnostics/history.py`（注：实际位于 diagnostics/ 子目录） | ✓ |
| `schematic_view.py` | `cis2hdl/gui/panels/schematic_view.py` | ✓ |
| `diff_view.py` | `cis2hdl/gui/panels/diff_view.py` | ✓ |
| `rules_panel.py` | `cis2hdl/gui/panels/rules_panel.py` | ✓ |
| `cis2hdl/core/writer/csa_writer.py`（Phase X） | `cis2hdl/core/writer/csa_writer.py` | ✓ |
| `cis2hdl/core/parser/dsn/dsn_parser.py`（Phase X） | `cis2hdl/core/parser/dsn/dsn_parser.py` | ✓ |

**目录结构核查**（与项目参数卡 v1.1 一致）:
- `cis2hdl/` 顶层 = `{config, core, gui, utils}` ✓
- `cis2hdl/core/` = `{config.py, db, diagnostics, engine, exceptions.py, ir, matcher, net_utils.py, parser, validator, writer}` ✓
- 不存在 `version/`、`layout/`、`cli/`、`generator/` 目录（生成器模块写作 `writer/`）✓

> 核查结论：Phase III 实现文件 7/7 存在，Phase X 代码修改文件 2/2 存在，目录结构与参数卡一致。

### III.5 当前状态摘要（2026-08-07）

| 项目 | 值 |
|------|------|
| 当前版本 | **v1.1.0**（匹配系统 v2.0，2026-08-07） |
| 测试基线 | **268 passed / 23 skipped / 0 failed**（291 collected） |
| 错误码 | **44** |
| 匹配率 | 匹配覆盖 **889/889**、声称匹配率 **92.4%（822/889）**、quality **72%**（99.9% 为 Phase VIII（v0.7.0）置信度≥0.6 历史口径） |
| 综合质量 | **72%**（参数卡 v1.1.0 口径） |
| PAINT WIRE | **已移除**（2026-08-07，匹配系统 v2.0 完成时） |
| 目录结构 | cis2hdl/{config,core,gui,utils}；无 version/layout/cli/generator |

> **阶段状态一句话**: Phase I→X 全部完成（✅），匹配系统 v2.0（v1.1.0）为当前最新里程碑；PAINT WIRE 生成器已移除，原文相关记载（Part II 十一-F"7 页 16 段"）作为历史实测记录保留。

---

## Part IV v2c 修复检查项（2026-08-07 追加）

> 本节由软件交付团队 v2c 迭代（2026-08-07 20:59）追加。基于用户对 `output_v2b` 报告的逐项反馈（6 类问题）与 STATUS §5 遗留 #3/#4/#5/#8/#9。实现已完成并重跑验证（`HG5015_tests/output_v2c`），下表记录检查项与验收结论。

| ID | 检查项 | 来源 | 验收结论（output_v2c 实测） | 状态 |
|----|--------|------|---------------------------|:---:|
| V-1 | HTML 报告用 phase1_type 替代 hdl_category（DISCRETE 误导） | 用户反馈 A.1 | Type 列显示 capacitor/connector（phase1_type）；HTML 无 DISCRETE | ✅ |
| V-2 | 统计卡重排：CIS 解析 → HDL 输出 → 输出 三组，数字在上文字在下，圆角小方块 | 用户反馈 A.2 | 三组齐全（CIS 24/889/3717 → HDL 24/822/3717 → 输出 82/0/111）；card-value 统一在上 | ✅ |
| V-3 | Top-1 排版深浅反转：主行深色、候选行浅色 | 用户反馈 A.3 | 主行 `match-main` 深色 #2B2926、Top-1 头/Rank 行浅色 | ✅ |
| V-4 | top-X 候选行信息补全（value/footprint/jedec/category/pin_count/conf/dims） | 用户反馈 A.4 | 候选行含 value/jedec/package_type/pin_count | ✅ |
| V-5 | 0402C-S 之谜：HDL 封装显示与匹配行脱节 | 用户反馈 A.5 | 根因=hdl_scanner 取 ptf 首行 + _enrich_result 取首个 value 行；修复后 C1 显示 C0603（v2b 误报 0402C-S/C0402）；PASSIVE_EXACT 判定保持 | ✅ |
| V-6 | J10 类空 footprint 连接器匹配（`*` 通配符模糊路径） | 用户反馈 A.6 | 新增 `_match_footprint_wildcard`（footprint 无尺寸 + part_name 别名 + pin 兼容，within=0.85）；J10 0.43→0.731，J4/J7/J9/J13/J26 同步提升 | ✅ |
| V-7 | #3 NEEDS_REVIEW 质量（67 个） | STATUS #3 | R6 通配符只抬升可命名元件；67 构成不变（T32/D15/L15/S3/Z2）——**未达 ≤40，需后续**（passive L5 下限或扩别名/库） | ⚠️ 遗留 |
| V-8 | #5 U* IC conf 偏低（0.35-0.48） | STATUS #5 | 占位符回退 + 评分修复后 M1-M6 conf 0.48-0.58→0.82；U* 方向正确 | ✅ |
| V-9 | #8 hdl_category=DISCRETE | STATUS #8 | 与 V-1 同源，已随 phase1_type 显示修复 | ✅ |
| V-10 | #9 rank1_primitive 空 | STATUS #9 | cross-type top3 富化后 0/889 空（v2b 889/889 空） | ✅ |
| V-11 | conversion_engine 调试 print 清理 | STATUS #2 | L899/L1407 `>>>` print 已改 logger | ✅ |
| V-12 | 重新运行 HG5015 转换（output_v2c） | 用户流程要求 | 转换成功：24 页/889 元件/3717 网络/outputs=87/quality 72%；与 v2b 同 hdl_lib 可比 | ✅ |

**v2b vs v2c 量化对比（同一 hdl_lib，mapping CSV 对齐）**

| 指标 | output_v2b（基线） | output_v2c（v2c） | 变化 |
|------|:---:|:---:|:---:|
| conf 均值 | 0.860 | 0.864 | +0.004 |
| conf ≥0.75 分桶 | 613 | 619 | +6 |
| conf 0.40-0.75 分桶 | 209 | 203 | -6 |
| NEEDS_REVIEW | 67 | 67 | 不变 |
| rank1_primitive 空 | 889 | **0** | -889 |
| 提升元件数 | — | 12（J4/J7/J9/J10/J13/J26 + M1-M6） | — |

> **遗留确认**：V-7（NEEDS_REVIEW 67）与 Warnings 口径（v2b 卡片 115 → v2c 111，Errors=0；用户反馈的 138 为更早口径，errors.log 中 HTML 类标签不计入卡片数值，待与用户核对）。C1 案例 PASSIVE_EXACT 判定正确（10UF+0603 双精确），v2b 显示 0402C-S 系报告取值 bug 而非匹配 bug。

### III.6 内容保全检查与源文档 → ROADMAP 位置映射表

**保全检查结论**: 已对照两份源文档逐节核对，**未遗漏任何章节/任务编号/表格/附录/代码块**。两份文档的全部内容均已保留。以下映射表证明 100% 覆盖。

**源文档 A: DEVELOPMENT_ROADMAP.md（42KB，2026-07-30 起草）**

| 源文档章节 | ROADMAP 位置 |
|------|------|
| 标题 + 头部（版本 v4.0 / 日期 / 参考） | Part I「原文档标题与头部」 |
| 阶段总览（代码块） | Part I「阶段总览」 |
| 技术基线（已通过调研验证） | Part I「技术基线」 |
| Phase I: Foundation — 目标 | Part I「Phase I」→「目标」 |
| Phase I-A（B1.1~B1.10）+ 验收 | Part I「Phase I-A」 |
| Phase I-B（B1.11~B1.24） | Part I「Phase I-B」 |
| Phase I-B 新增：诊断基础设施（D1.1~D1.6） | Part I「Phase I-B 新增」 |
| Phase I 前端的诊断面板（F1.1~F1.7） | Part I「Phase I 前端诊断面板」 |
| Phase I 最终验收（勾选项） | Part I「Phase I 最终验收」 |
| Phase II — 目标 / 后端任务（B2.1~B2.13） | Part I「Phase II」 |
| Phase II 新增：诊断与容错引擎（D2.1~D2.7） | Part I「Phase II 新增」 |
| Phase II 前端任务（F2.1~F2.10） | Part I「Phase II 前端任务」 |
| Phase II 验收 + 代码统计 + 测试重组 | Part I「Phase II 验收 / 代码统计」 |
| Phase III — 目标 / 后端任务（B3.1~B3.6） | Part I「Phase III」 |
| Phase III 新增：高级诊断与报告（D3.1~D3.4） | Part I「Phase III 新增」 |
| Phase III 前端任务（F3.1~F3.7）+ 验收 | Part I「Phase III 前端任务 / 验收」 |
| Phase IV（Cadence 实测后改进项 P4.1/P4.2）+ 全项目 70/70 + Phase I-A 早期验收项 | Part I「Phase IV（Cadence 实测后发现的改进项）」 |
| 风险跟踪（9 行） | Part I「风险跟踪」 |
| 技术文档交叉索引（13 行） | Part I「技术文档交叉索引」 |
| Phase IV: Validation & Coverage Enhancement（9 项） | Part I「Phase IV: Validation & Coverage Enhancement」 |
| Phase V: HG5015 匹配增强（背景/总览/关键指标/V-A1~V-C2/风险/数据流/合并开发日志） | Part I「Phase V」全部子节 |
| 会议/评审节点（8 行） | Part I「会议/评审节点」 |

**源文档 B: ROADMAP_AUDIT_2026-08-03.md（38KB，2026-08-03 起草）**

| 源文档章节 | ROADMAP 位置 |
|------|------|
| 标题 + 头部（日期 / 版本 0.4.0） | Part II「原文档标题与头部」 |
| 一、清点结果总览（Phase I-IV 79 项表） | Part II「一、清点结果总览」 |
| 二、Phase I 逐项清点（22/22） | Part II「二、Phase I 逐项清点」 |
| 三、Phase II 逐项清点（30/30） | Part II「三、Phase II 逐项清点」 |
| 四、Phase III 逐项清点（16/16，含实现文件） | Part II「四、Phase III 逐项清点」 |
| 五、Phase IV（五-A~五-F 全部分项表） | Part II「五、Phase IV」全部子节 |
| 六、验证步骤（10 步） | Part II「六、验证步骤」1~10 |
| 七、Phase V: 匹配系统修复（七-A 诊断结论 + 七-B P0 修复） | Part II「七、Phase V: 匹配系统修复」 |
| 八、Phase VI: CrossRef 驱动架构重构（八-A~八-F 全部） | Part II「八、Phase VI」全部子节 |
| 九、Phase VII（九-A~九-C 全部） | Part II「九、Phase VII」全部子节 |
| 十、Phase VIII（十-A~十-H 全部，含重复表 IX-7~IX-10） | Part II「十、Phase VIII」全部子节 |
| 十一、Phase X（十一-A~十一-H 全部） | Part II「十一、Phase X」全部子节 |

> 映射表覆盖源文档 A 全部 21 个章节/小节 + 源文档 B 全部 12 个章节/小节，无遗漏。

---

## 附录：研发过程时间线（原 TIMELINE.md 全文）

> **附录说明**: 本附录为原 `docs/TIMELINE.md`（v1.0，2026-08-07 建立）全文并入（2026-08-07），内容逐行保留，仅调整标题层级以适配合并文档结构；原 TIMELINE.md 已归档 `archive/二次合并源/`。测试数栏均为当日历史口径；现行权威基线见 STATUS.md。

### 原文档标题与头部（原文保留）

**原标题**: CIS2HDL 研发时间线（TIMELINE）

| 项目 | 值 |
|------|-----|
| 文档版本 | v1.0（2026-08-07 建立） |
| 项目版本 | v1.1.0（匹配系统 v2.0） |
| 状态 | 现行研发过程时间线（7/29 项目启动 → 8/7 v1.1.0） |
| 数据来源 | `docs/archive/日志/2026-07-29.md` ~ `2026-08-06.md`（9 份）+ [handoff-20260807-113237.md](handoff-20260807-113237.md) + 项目参数卡 v1.1.0 |
| 关联文档 | [STATUS.md](STATUS.md) · [KNOWN_ISSUES.md](KNOWN_ISSUES.md) · [CHANGELOG.md](CHANGELOG.md) |

---

### 1. 说明

- 时间线以 `docs/archive/日志/` 下 9 份日期日志为骨架串联，版本号以 [CHANGELOG.md](CHANGELOG.md) 与项目参数卡对齐。
- **2026-07-22 / 2026-07-23 两份日志为 waveform_viewer 项目（非 CIS2HDL）**，不并入主线，仅作归档记录。
- 测试数栏为当日记录值（历史口径）；现行权威基线为 **268 passed / 23 skipped / 0 failed（291 collected，2026-08-07）**，详见 [STATUS.md](STATUS.md)。

### 2. 主线时间线（CIS2HDL）

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

### 3. 归档记录（非主线）

| 日期 | 内容 | 说明 |
|------|------|------|
| 2026-07-22 | waveform_viewer 项目工作日志（示波器波形 CSV→图片工具、UART 解码、测试 SOP 等） | 非 CIS2HDL 项目日志，详见 `docs/archive/日志/2026-07-22.md` |
| 2026-07-23 | waveform_viewer 项目工作日志（续） | 非 CIS2HDL 项目日志，详见 `docs/archive/日志/2026-07-23.md` |

---

*本文档由文档整合团队基于 9 份日期日志 + handoff 串联生成。测试数栏均为当日历史口径；现行权威基线见 STATUS.md。*





---

## Part V Phase XI：DEHDL 原理图连线显示 + 100% 网络转换 + 网表导出（2026-08-10 规划）

> 本节由软件交付团队（齐活林/高见远/寇豆码）追加。基于：
> - 用户第二轮需求：**Design Entry HDL 原理图内显示电路连接线与跨页连接符（非 PCB Editor）**；
>   网络和连接 **100% 转换成功**；正确导出网表（Packager-XL）与 export physical；暂不考虑 PCB 封装覆盖率
> - `docs/archive/temp files/HG5015_output_v2c_质量评估报告.md`（第一轮评估）
> - `docs/archive/temp files/DEHDL连线与100%网络转换方案.md`（第二轮连线/跨页/网表方案）
> - Cadence 实测报错 `HG5015_tests/output_v2c/errors.txt`（用户提供）
> - 架构师调研：`CIS 信息完整清单 vs 解析器覆盖对照`（2026-08-10，含 DSN/EDIF 实测数据）

### XI.0 需求与成功标准

| 目标 | 成功标准 | 当前状态 |
|------|----------|:---:|
| 原理图正确显示所有符号 | DEHDL 打开后元件符号可见、属性正确（无 SPCOCN-542 删除） | ❌ 有 SPCOCN-542 |
| 原理图显示电路连接线 | CSA 生成 `WIRE 16 -1 (x1 y1)(x2 y2);` + `LASTPIN $PN/SIG_NAME` + `DOT` | ❌ 无连线 |
| 跨页连接符 | 生成 GND_POWER/VCC_CIRCLE（\g 全局）+ IOPORT/INPORT/OUTPORT | ❌ 缺失 |
| 页面命名正确 | page.map 格式正确 + 与 CSA 编号一致 | ❌ 错位 |
| 100% 网络转换 | con 网络数/连接数与源完全一致（pstxnet 590/2821） | ⚠️ P0 修复后 2771/2821 |
| 正确导出网表 | Packager-XL Export Packager Files 成功，无 Error | ❌ con 格式不兼容 |
| export physical | 生成 pstx 三件套可被 Allegro 读取 | ❌ |

### XI.1 关键技术结论（已确认，实测证据）

| #   | 结论                                                                                                  | 证据                                                   |
| --- | --------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| 1   | **SPCOCN-1891 是错误诊断**：`PAINT WIRE;` 命令在 CSA 中不存在；真实命令是 `WIRE 16 -1 (x1 y1)(x2 y2);`，16.6 完全支持       | 4 个真实 Cadence 工程逆向（04p4/8367/switch_practice/V2801S） |
| 2   | **推翻 v0.9.0 移除连线决策**：连线功能应重做                                                                        | 同上 + changelog 中 PAINT WIRE 报错记录                     |
| 3   | CSA 连线四条命令：`WIRE 16 -1` / `DOT 1` / `LASTPIN $PN` / `LASTPIN SIG_NAME`（几何重合建立连接）                    | 真实 pageN.csa 实测                                      |
| 4   | **con 不是 Cadence 格式**：需重写为 `("S2" "dc_dc" "hdl_lib" "sym_1" (terms ...))` + `(pins (conn ...))`     | 8367.con/04p4.con 对比                                 |
| 5   | **xcon 空骨架**：需填充 lastids/cells/terms/nets/instances/netScopes                                       | 8367.xcon 对比                                         |
| 6   | **pageN.csv 完全缺失**：DEHDL 页面网络/引脚连接文件，必补                                                             | 真实工程同目录存在                                            |
| 7   | **EDIF 是连线理想数据源**：2516 个 figure WIRE + 4257 点 + 836/862 网有坐标；765 个 OFF_PAGE_CONNECTOR；4625 个网络名标签坐标 | HG5015 EDF 实测                                        |
| 8   | **DSN 对 RTL 变体是负资产**：HG5015 实例=0（PlacedInstance 解析被移除）、wire 仅 16 段垃圾、3717 假网络来自误解析                  | DSN 解析器实测                                            |
| 9   | 页面命名错位：`write_page_map()` 用 enumerate idx 当页码（output_manager.py L666-671）                           | page.map vs CSA 对比                                   |
| 10  | SPCOCN-542：symbol.css 未声明默认属性被 FORCEPROP 覆盖即删；单 section 应写 `$LOCATION`                              | 3 元件 symbol.css 对比                                   |
| 11  | 跨页连接两种方式：电源地 = GND_POWER/VCC_CIRCLE（`SIG_NAME xxx\g` 全局）；普通信号 = IOPORT/INPORT/OUTPORT（standard 库）   | 04p4 工程 + standard 库                                 |

### XI.2 任务分解（P0-P3）

#### P0-A：EDIF 连线数据解析（连线显示基石）
| 子任务 | 内容 | 文件 |
|--------|------|------|
| P0-A1 | `_parse_net` 提取 `(figure WIRE (path (pointList (pt x y)…)))` 折线坐标，写入 PageIR.wires（扩展 WireSegment 支持 polyline + 网络名 + 页面归属） | edif_parser.py、ir/design.py |
| P0-A2 | `_parse_page` 识别 `(page …)` 块：按 page 划分 PageIR（24 页不再塌缩成 1 页），读 pageSize/boundingBox 设定 width/height | edif_parser.py |
| P0-A3 | 解析 OFF_PAGE_CONNECTOR portRef（765 个，无 instanceRef 即跨页点），IR 增加 off_page 承载 | edif_parser.py、ir/design.py |
| P0-A4 | 修正 docstring "Coordinates absent in EDIF"（与文件事实不符） | edif_parser.py |
| P0-A5 | 网络名转义还原（`&3V3_SOC` → `3V3_SOC`）、网络名标签坐标（display origin）提取 | edif_parser.py |

#### P0-B：con/xcon/pageN.csv 重构（网表导出核心）
| 子任务 | 内容 | 文件 |
|--------|------|------|
| P0-B1 | `_build_con_content` 重写为 Cadence S-expr：cells(`("S2" "dc_dc" "hdl_lib" "sym_N" (terms …))`) + nets(`("N2" "name" -1 -1 scope)`) + instances(`("I1" "pageN_i1" "S1" (pins (conn …)))`)，lastIds 正确 | output_manager.py |
| P0-B2 | `_build_xcon_content` 填充 XML：lastids/cells/terms/nets/instances/netScopes/pages | output_manager.py |
| P0-B3 | 新增 pageN.csv 生成器：`FILE_TYPE = CONNECTIVITY;` + 网络编号清单 + 实例引脚→网络映射 | 新文件 writer/csv_writer.py |
| P0-B4 | 网络名清洗（$xxx/&xxx 非法名转合法）+ 电源网 `\g` 后缀 + con scope=2 | net_utils.py、output_manager.py |

#### P0-C：CSA 连线生成（原理图显示）
| 子任务 | 内容 | 文件 |
|--------|------|------|
| P0-C1 | csa_writer 输出 `LASTPIN $PN`（引脚号）+ `LASTPIN SIG_NAME`（网络名） | csa_writer.py |
| P0-C2 | csa_writer 输出 `WIRE 16 -1`（数据源：EDIF WIRE 优先 → DSN ports 补充 → 拓扑合成兜底） | csa_writer.py、新 wire_layout.py |
| P0-C3 | `DOT 1` 连接点（T 形/十字交叉） | csa_writer.py |
| P0-C4 | 电源/地符号 GND_POWER/VCC_CIRCLE + `HDL_POWER` 属性 + standard 库 | csa_writer.py、库 |
| P0-C5 | 跨页端口 IOPORT/INPORT/OUTPORT + OFFPAGE TRUE | csa_writer.py |

#### P0-D：EDIF 注入完整化 + DSN 去留判定
| 子任务   | 内容                                                                                                       | 文件                                 |
| ----- | -------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| P0-D1 | EDIF pin_connections 完整注入 PageIR（1466→2771，P0 修复后已验证）                                                    | conversion_engine.py               |
| P0-D2 | **DSN 去留判定**：对 RTL 变体（HG5015 实例=0），推荐全面转 EDIF+pstxnet，禁用 DSN 元件源（避免 3717 假网络污染）；标准变体保留 DSN Wire/NetTable | dsn_parser.py、conversion_engine.py |

#### P1（第二轮）：Cadence 实测报错修复
| 子任务 | 内容 | 文件 |
|--------|------|------|
| P1-1 | write_page_map 页码修复（enumerate idx → _extract_page_number + 排序） | output_manager.py L666-671 |
| P1-2 | symbol.css 补默认属性声明（ch347/rf_sw/rj45_2x2_led：PART_NAME/PATH/LOCATION/VALUE "?"） | hdl_lib 库文件 |
| P1-3 | csa_writer 单 section 改 `$LOCATION` | csa_writer.py L433-456 |
| P1-4 | 元件旋转/镜像、NC 标志、SymbolPin 电气类型存储 | structures.py、cache_parser.py |
| P1-5 | cpc 实例列表（#ISCELL/#CELL） | output_manager.py |

#### P2（后续）
- xcon netScopes 全局登记；总线支持（BUS 段）；多 section 引脚偏移
- DSN Net Name Table/Hierarchy/PageSettings 解析（标准变体）
- OLB SymbolPin port_type/pin_shape 电气类型

#### P3（低/信息）
- J47/PWC3_A 厚膜电路 = 库缺失（hdl_lib 无此符号，用户确认可不处理）
- 跨页连接符单独立项跟踪

### XI.3 交付清单

| # | 交付物 | 说明 |
|---|--------|------|
| 1 | 连线显示（WIRE/LASTPIN/DOT 在 DEHDL 可见） | P0-A + P0-C 完成 + Cadence 实测 |
| 2 | 100% 网络转换（con 590 网/2821 连接） | P0-B + P0-D 完成 |
| 3 | Packager-XL 导出网表成功 | P0-B（con 格式合法）+ 实测 |
| 4 | export physical 成功 | 同上 |
| 5 | 页面命名修复（hierarchy viewer 标题正确） | P1-1 |
| 6 | 无 SPCOCN-542（属性不丢失） | P1-2/P1-3 |
| 7 | 跨页连接符显示 | P0-C4/C5 |
| 8 | 回归测试全绿 + 新测试 | P0-P1 各子任务 |
| 9 | 更新 STATUS/ROADMAP/changelog | 每次改动后 |

### XI.4 验收方法（诚实标准）

- **连线显示**：必须在 Cadence DEHDL 打开后**目视确认 WIRE 可见**，而非仅文件无语法错误。无 Cadence 环境的阶段，用"CSA 含 WIRE 命令 + 坐标与引脚重合"静态断言，并明确标注"待 Cadence 实测"。
- **100% 网络**：断言 `con nets == pstxnet 网络数(590)` 且 `conn 连接数 == 2821`，不允许"约"或"近似"。
- **网表导出**：Packager-XL Export 后 netrev.lst 无 Error；未实测前标注"待实测"。
- **回归**：`pytest tests/ -q` 全绿；新增测试覆盖 P0-A/B/C 各子任务。
- **诚实原则**：任何未在 Cadence 实测的项目，一律标注"待 Cadence 实测"，不宣称"已成功"。

### XI.5 风险与依赖

| 风险 | 等级 | 缓解 |
|------|:---:|------|
| EDIF WIRE 坐标关联网络需几何推断（页面层 wire 无显式 net 名） | 中 | 坐标重叠 + 网络名标签 string 邻近匹配 |
| 拓扑合成兜底（EDIF wire 缺失的网络）形状不自然 | 中 | 优先 EDIF 坐标；兜底用 L 型/星型 |
| con/xcon/pageN.csv 格式细节需 Cadence 实测验证 | 高 | 以 8367/04p4 参考工程为模板；分步实测 |
| hdl_lib 缺 standard 库端口符号 | 中 | 拷入参考 standard 库 + cds.lib DEFINE |
| DSN 去留决策影响既有测试 | 中 | 保留标准变体路径；RTL 走 EDIF 主链 |

*本文档由软件交付团队基于第二轮需求与调研追加（2026-08-10）。测试数栏为历史口径；现行权威基线见 STATUS.md。*

### XI.6 P0 A-D 实施完成记录（2026-08-10 追加）

> 本节由软件交付团队追加，记录 P0 A-D 全部实施完成情况。实现依据为
> `docs/system_design.md`（架构师高见远 691 行权威设计，含 con/xcon/csv/cpc/csa
> 精确格式模板 + 坐标换算 + 拓扑合成算法 + 验收断言 A1-A9）。

| 任务 | 状态 | 实测结果 | 备注 |
|------|:---:|----------|------|
| P0-A1 EDIF figure WIRE 提取 | ✅ | 2516 折线全提取（与文件一致） | WireSegment polyline |
| P0-A2 EDIF page 块识别 | ✅ | 24 页不塌缩，页面尺寸从 pageSize 读取（4 种） | 替换硬编码 3520×2720 |
| P0-A3 OFF_PAGE_CONNECTOR | ⚠️ 部分 | 522/765（接口层 243 待 P0-C5 核对） | 差异已知 |
| P0-A4 docstring 更正 | ✅ | — | — |
| P0-A5 网络名 & 转义还原 | ✅ | `&3V3_SOC`→`3V3_SOC` | — |
| P0-B1 con 重写 Cadence S-expr | ✅ | 590 唯一网/687 记录/889 实例/2771 conn；S-Expr 可解析 | 新 con_writer.py |
| P0-B2 xcon 填充 | ✅ | lastids/cells/nets/aliases/instances/netScopes/pages 全填充；XML 可解析 | 重写 xcon_writer.py |
| P0-B3 pageN.csv 生成器 | ✅ | 每页 FILE_TYPE=CONNECTIVITY + 0"NC" + $PN + END. | 新 csv_writer.py |
| P0-B4 网络名清洗 + \g + scope | ✅ | con N1 全局 scope=2、N2 局部 pageN_ scope=0 | net_utils.py 三态命名 |
| P0-C1 csa LASTPIN $PN/SIG_NAME | ✅ | 每页 LASTPIN（2129 总数） | csa_writer.py |
| P0-C2 csa WIRE 16 -1 | ✅ | 3706 端点覆盖 93% LASTPIN；多引脚网引脚均为端点 | wire_layout.py 拓扑合成 |
| P0-C3 DOT 连接点 | ✅ | ≥2 段交点打 DOT | 保守策略 |
| P0-C4 电源/地符号 | ✅ | SIG_NAME 带 \g（97 个）；cpc #ISCELL | — |
| P0-C5 跨页端口 | ⚠️ 简化 | SIG_NAME 标签表达跨页网名（未放 IOPORT 符号） | DEHDL 可用 SIG_NAME 跨页 |
| P0-D1 EDIF 注入完整化 | ✅ | 2771 pins → 889 实例 | 此前完成 |
| P0-D2 DSN 禁用 EDIF+pstxnet 主链 | ✅ | use_dsn_components=False 默认；无 3717 假网络；RTL8367RB 兼容 | conversion_engine.py |

**诚实验收结论**（对照 XI.4）：
- ✅ con nets==590（A1 达成）、conn 2771 vs 2821 目标（A2 差 50，U6 主芯片在 CrossRef Catalog 缺失所致）
- ✅ instances 889 vs 906 目标（A3 差 17，同因：U6 + 25 J-jumper 不在 Catalog）
- ✅ 无 3717 DSN 假网络（P0-D2 生效）
- ✅ 全量测试 364 passed / 23 skipped（+41 新测试：28 unit + 13 e2e）
- ⚠️ **连线显示与网表导出均未在 Cadence 16.6 实测**——静态断言（格式/坐标/语法）通过，需用户在有 Cadence 环境实测确认

**遗留问题**（不夸大，如实记录）：
1. U6 主芯片 + 25 个 J-jumper 未在 CrossRef Catalog（con instances 889 vs 906）——需补齐 Catalog 或按 pstxnet 补充
2. 自动网名未转 UN$ 形式（`$50N80178` 等）——net_utils 待增强
3. P0-A3 off_page 522 vs 765（接口层差异）
4. P0-C5 未放置 IOPORT 符号（用 SIG_NAME 替代）——如需显式端口符号待后续

### XI.7 P0 遗留三问题修复（2026-08-10 追加）

> 用户实测反馈三个问题（详见 docs/archive/temp files/P0遗留三问题分析.md），
> 架构师设计（docs/phaseXI_P0_fix_design.md + phaseXI_P0_fix_evidence.md），
> 总监 + 工程师实施。

| 问题 | 根因 | 修复 | 状态 |
|------|------|------|:---:|
| ① 25 个 ROUTE 跳线被跳过（889 vs 906） | component_catalog `_SKIP_REFDES_VALUES={"ROUTE"}` 把 0Ω 跳线（COPPER0201）当布线标记 | `_SKIP_REFDES_VALUES` 置空 + `_PREFIX_TO_HINT["ROUTE"]="resistor"` + hint 特判 | ✅ 914 实例/2821 conn |
| ② 电源符号未进 csa/csv/cpc | P0-D2 清空实例时丢电源符号 + POWER_SYMBOL_CELLS 缺 gnd/dgnd + EDIF 电源符号 0 引脚 | conversion_engine 保留电源实例 + connectivity_model 识别扩展 + csv/csa 电源符号专用块 + 放置策略 | 🔄 工程师实施中 |
| ③ 自动网名未转 UN$ | con_name 简单清洗 `$21N109399`→`21n109399`（数字开头） | connectivity_model build() 对 $ 网名用首连接推导 `unnamed_<page>_<cell>_i<k>_<pin>`（csv 显示 UN$ 形式） | ✅ 166 个 unnamed_/UN$ 一致 |

**新增数据源确认**（用户新导出）：
- `entire.csv`：OrCAD 完整导出（906 PARTINST + 2821 PININST + 坐标 + 页面名）——与 pstxnet 2821 完全一致，权威数据源
- `error.txt`：`ORCAP-11007 TitleBlock Page '01-Cover_Page' contains an invalid Page Number`——源设计标题栏页码无效（建议 Capture Tools→Annotate 修复，与转换器无关）
- `HG5015-BE36_V10_0.DBK`：OrCAD 自动备份文件（可忽略）

**8367/HG5015 混用检查结论**：无数据混用错误——代码中 8367 仅出现在注释/示例；格式规则通用，数据全部来自 HG5015 实测。唯一需 Cadence 实测确认：con 电源页局部网（pageN_ 前缀）数量 97 个是否必要（8367 模式）。

### XI.8 P1 第二轮修复完成（2026-08-10 追加）

> P1 五子任务全部实施完成（总监独立实施 + 架构师设计交叉验证 + QA 独立验收）。
> 详细记录见 changelog_master.md。目标：修复 Cadence 实测报错（页码/属性/连线/电气）。

| 子任务 | 内容 | 状态 | 实测结果 |
|--------|------|:---:|----------|
| P1-1 | write_page_map 页码修复（_extract_page_number + 排序） | ✅ | page.map 1-24 真实页码排序（01→1...24→24） |
| P1-2 | symbol.css 补默认属性（ch347/rf_sw/rj45_2x2_led） | ✅ | 4 属性全补，SymbolCssParser 可读 |
| P1-3 | csa_writer 单 section 改 $LOCATION | ✅ | 全部 csa 用 $LOCATION（0 裸 LOCATION）；**实例级属性**证据 |
| P1-4 | 旋转/镜像/NC/电气类型存储 | ✅ | EDIF orientation 783 rot + 217 mirror；67 NC 引脚；SymbolPin 字段 |
| P1-5 | cpc mark 改 #CELL | ✅ | _ISCELL_CELLS 移除 mark（8367/04p4 双实证） |

**关键结论**：
1. **P1-3 决定性发现**：$LOCATION vs LOCATION 是 OrCAD 源实例级属性（同 body 不同实例
   不同），非 section/symbol.css 规则 → 统一 $LOCATION（DEHDL 标准，04p4 绝大多数用）
2. **U6 双口径实测**：pstxnet 同时含母 U6 + U6A-I（引脚 100% 重叠）；con 2821 =
   3352 - 531 母 U6 重复 → **无引脚丢失**，U6A-I 口径正确（推翻架构师"531 丢失"判断）
3. **ORCAP-11007**：源设计 TitleBlock 页码无效，P1-1 容错（不依赖 title block），
   用户侧 Tools→Annotate 修复

**测试**：387 passed / 23 skipped（+19 新 P1 测试）

**遗留（诚实声明）**：
1. rotation/mirror 数据已存储但 **csa 输出未消费**（DEHDL 旋转用 sym_N 视图，待映射）
2. NC 标志已存储但 csa/csv 未专门渲染
3. 全部静态验证，**待 Cadence 实测**

### XI.9 P2 核心开发完成 + Phase XI 深度分析（2026-08-10 追加）

> P2 三项核心（rotation→sym_N / NC 渲染 / xcon netScopes）完成。设计详见
> STATUS.md §12。本节约束 Phase XI 全任务清点审查结论与遗留深度分析。

#### P2 状态

| P2 项 | 状态 | 实测 |
|-------|:---:|------|
| P2-1 rotation→sym_N 视图映射 | ✅ | 50.1% 元件旋转正确（C97 R90 引脚横向验证） |
| P2-2 NC 标记渲染 | ✅ | SIG_NAME NC 10→0，LASTPIN 保留，con 2821 保持 |
| P2-3 xcon netScopes 增强 | ✅ 确认完成 | 双层结构与 8367 一致（49 全局网） |
| P2-4 总线支持 | ⬜ 缺样本 | 8367/HG5015 均 0 总线 |
| P2-5 多 section 引脚偏移 | ⬜ 缺样本 | HG5015 无真实多 section IC |
| P2-6 DSN 标准变体 | ⬜ 缺样本 | 需非 RTL DSN 测试文件 |
| P2-7 OLB 电气类型接通 | ⬜ 部分 | 字段/类型已有，消费待接 |

#### Phase XI 全任务清点审查（对照 XI.2 P0-P3）

**已闭环**：P0-A1/A2/A4/A5、P0-B1-B4、P0-C1-C4、P0-D1/D2、P1-1~P1-5、P2-1/2/3 ✅（26 项）
**部分完成**：P0-A3（off_page 522/765）、P0-C5（跨页端口 SIG_NAME 简化）⚠️（2 项）
**未开发（缺条件）**：P2-4/5/6、P2-7（接通）、P3-1（用户确认可不处理）（5 项）

#### Phase XI 深度分析：遗留工作与阻塞原因

| 遗留 | 原因 | 可否当下解决 | 缺什么 |
|------|------|:---:|--------|
| ① 连线显示待 Cadence 实测 | 无 Cadence 16.6 环境 | ❌ 需用户环境 | 装有 SPB 16.6 的电脑 + 手工打开工程验证 |
| ② 网表导出（Packager-XL）待实测 | 同上 | ❌ 需用户环境 | Cadence 环境执行 Export |
| ③ P0-A3 off_page 522/765 | EDIF off_page 接口层与连接层差异 | ✅ 可分析 | 需核对 off_page 与跨页端口的映射 |
| ④ P0-C5 跨页 IOPORT 符号 | 用 SIG_NAME 替代（简化） | ✅ 可做 | standard 库 IOPORT 符号 + csa_writer 放置逻辑 |
| ⑤ P2-4 总线支持 | 样本缺失 | ❌ 缺样本 | 带总线（BUS）设计的 OrCAD 工程 |
| ⑥ P2-5 多 section 偏移 | 样本缺失 | ❌ 缺样本 | 含多 section IC（同 refdes 多 section）的工程 |
| ⑦ P2-6 DSN 标准变体 | 样本缺失 | ❌ 缺样本 | 标准变体 DSN 测试文件 |
| ⑧ P2-7 OLB 电气类型接通 | 未接通 symbol_css 消费 | ✅ 可做 | 实现 OLB→SymbolPin 类型映射 |
| ⑨ 信息页 CSA 占位符 | TitleBlock 文本解析待完善 | ✅ 可做 | 深度解析 EDIF 信息页文本 |
| ⑩ 旋转镜像在 csv 头行未消费 | rotation 仅用于 csa 引脚 | ✅ 可做 | csv 头行坐标同样旋转变换 |

**结论**：Phase XI 核心功能（连线生成 + 100% 网络 + 属性/方向/NC 修复）代码级全部落地。
剩余阻塞全部集中在：①Cadence 实测（需用户环境）；②缺带特殊设计（总线/多 section/标准 DSN）
的测试样本。可当下推进的代码项为 P2-7 接通、P0-C5 IOPORT、信息页 CSA、csv 旋转（低优先）。

**测试**：395 passed / 23 skipped（+8 P2 测试）

### XI.10 收尾五项完成（2026-08-10 追加）

> 对应 system_design.md T01-T05。P0-A3/P0-C5 完整实现 + P2-7 分析 + CH347 + T17。

| 项 | 状态 | 实测 |
|----|:---:|------|
| P0-A3 off_page 765 完整 | ✅ | 522 页级 + 243 设计级 = 765 |
| P0-C5 IOPORT 跨页端口 | ✅ | 522 个 IOPORT 块，SIG_NAME 共存 |
| P2-7 OLB 电气类型 | ✅ 分析 | csa 无消费点；chips.prt PINUSE 为源 |
| CH347 引脚桥接 | ✅ | 多引脚 IC 塌缩 0% |
| T04/T17 DSN RTL 恢复 | ✅ | 8367 实例 0→578 |
| fixture 补齐 | ✅ | 跳过 23→1 |

**测试**：424 passed / 1 skipped（395→424，+29）
**遗留**：①Cadence 实测（需用户环境）②8367 pstxnet 导出测试（需用户 pstx 文件）③U6 主芯片无匹配符号（数据限制）

---

### XI.11 Phase XII：匹配率修复 + HTML 报告重构（2026-08-10 追加）

> 用户反馈 output_phaseXI_final 匹配率骤降 50%（913/3023）+ GND INFO_LOSS 刷屏 + 报告 6 类问题。
> 团队：齐活林（根因分析）+ 寇豆码（实现）+ 严过关（QA 复核）。测试 424/1 全绿。

#### 根因（三叠加缺陷）

| # | 缺陷 | 影响 |
|---|------|------|
| R1 | `DesignIR.all_instances` cached_property 缓存 EDIF 占位（3023），Catalog 重建（1219）后不失效 | coverage 分母 3023 → 50% |
| R2 | 电源符号（GND/DGND/VCC_CIRCLE 305）不在 ComponentCatalog → 无 MatchResult | ~430 条 INFO_LOSS 警告 |
| R3 | PyYAML 未安装 → type_gate.yaml 静默失效 → 缺 RD/fixed_prefixes | RD25 conf=0.0 |

#### 修复项

| 项 | 状态 | 实测 |
|----|:---:|------|
| R1 缓存失效 + 按实例计数 | ✅ | Match Coverage **100% (1219/1219)** |
| R2 电源符号匹配（POWER_SYMBOL conf=1.0） | ✅ | GND/DGND/VCC INFO_LOSS **→0**；305 行 matched |
| R3 PyYAML + defaults 加固 | ✅ | RD25 conf 0.0→**0.651** |
| R4 Z 前缀加 filter 候选 | ✅ | Z1/Z2 0.24→**0.4632**（filter） |
| R5 top3 选中候选行数据一致性 | ✅ | C102 主行/候选行一致（8.2PF/0201-RF/C0201） |
| R6 report.pages 24 | ✅ | CIS 24 / HDL 24 一致 |
| R7 match-main 浅灰 + conf 分级色 | ✅ | 100%绿/70%琥珀/40%橙 可分辨 |
| R8 Output File Types + Default Fallback 板块 | ✅ | 报告 Match Results 上方新增两板块 |

#### 验证

- Quality 77%→**84%**；警告 448→**140**；pages 20→**24**；测试 **424/1**
- 剩余低置信度 132 个 = 源数据/库限制（T*32/J*26/U*24/L*18/D*15/R*11 源值异常/C*3/S*3），非算法缺陷

---

### XII.1 Phase XIII：Cadence 16.6 实测反馈修复（2026-08-11 追加）

> 用户用 Cadence 16.6 实测 output_phaseXII_final3，逐页记录大量问题（errors.txt）。
> 架构师高见远完成根因分析（docs/archive/temp files/system_design0811-phase13.md），工程师实施，QA 回归。

#### 用户实测反馈（五类）

| 现象 | 用户描述 |
|------|---------|
| 页面错位 | 信息页（page2/3）出现 U6G/U6A 芯片；page11/17/19 空白；page5 与 CIS 第13页相似 |
| SPCOCN-543/541 | 每页大量 pin property SPN/$PN/SIG_NAME deleted from IOPORT |
| 芯片中心锚点 | U6G/U6A/U6B/U5/U19 等芯片几何正中一个电线锚点 |
| 电线悬空/差一点 | 大量电线没接端口，引脚与电线端点很近但差一点（电线偏上） |
| 布线杂乱 | 电线高度重合遮挡、右上角一排排重叠孤立 IO 口、SPCOCN-503/1329 |

#### 根因（架构师确认）

| # | 根因 | 位置 |
|---|------|------|
| R0 页面错位 | page_num=page_idx+1（EDIF 解析顺序）vs page.map 页名数字排序 | connectivity_model.py L427/541 |
| R1 LASTPIN 集中文件尾 | 所有 LASTPIN 绑定到最后一个 FORCEADD（IOPORT）→ 属性被删；IOPORT LASTPIN 级别 3 ≠ 04p4 级别 1；引脚/标签坐标错 | csa_writer L1058-1075/L1407 |
| R2 旋转未输出 | 算旋转但不输出 R 行 → Cadence 按默认视图渲染，引脚差一个旋转位移；body off-grid（-2611 非 25 网格） | csa_writer L1018-1043 / coord_transform L112 |
| R3 fallback 键错 | fallback 按 pin_name 查但字典键是数字 → 未匹配芯片全 (0,0) 中心塌缩 | csa_writer L1038-1040 |
| R4 布线杂乱 | 多网 trunk 共线（page12 44 条 y=4400）、未传 body_outlines、IOPORT 未入网 | wire_layout L141 / csa_writer L1086 |

#### 修复项（T0-T4，见 system_design0811-phase13.md）

| 项 | 内容 |
|----|------|
| T0 页面错位 | page_num 按页名数字序号（四方一致：csa/con/xcon/page.map） |
| T1 基础设施 | body 吸 25 网格 + 组件旋转行 R 1/2/3 输出（mirror 保守不输出） |
| T2 Q1 | LASTPIN 内联各 FORCEADD 块 + IOPORT 模板对齐 04p4（级别 1、引脚/标签坐标、删 outline） |
| T3 Q3 | fallback 按 pin_number 查 + 未匹配芯片周边分布 + 占位轮廓 |
| T4 Q4 | route_nets 车道差异化 + 传 body_outlines + IOPORT 接入 WIRE |

#### 验收

- page2.csa=02-Block_Diagram 无元件；SPCOCN-543 大量消除；U6G 引脚不再全 (0,0)；WIRE 全 on-grid；无多网共 trunk；IOPORT 有 WIRE
- 全量测试 424/1 保持；HG5015 重新转换验证

---

### XIII.1 Phase XIV：布线美观化开发（2026-08-11 追加）

> 用户确认四项开发（P0 保留 / P1 正交绕障 / EDIF 折线复用 / A* 远期）+ 新需求
> （元件/标签去重叠、人工匹配→自动配线、跨页网优化、电源匹配）。架构师 system_design0811-phase14.md，测试 496/1。

#### 开发项与状态

| 项 | 状态 | 实测 |
|----|:---:|------|
| D5 配置开关+模块化（WireRouterBase 注册表/回退） | ✅ | routing.yaml 全默认关；'p0' 别名修复无 warning |
| P1a 正交绕障（detour_router.py） | ✅ | --routing detour 转换成功，端点保持+snap25 |
| P1b EDIF 折线复用（edif_wire_reuse.py） | ✅ | --routing edif_reuse 成功（2516 段折线复用+端点重定） |
| D1 文本去冲突+对齐（text_layout.py） | ✅ | --text-layout 成功；网络名 7.5 格点/差分对 P上N下/PIN_TEXT 禁动 |
| D2 元件重叠检测（aesthetic_report.txt） | ✅ | 实测检出 C23/C26 占位重叠 + fix_hint |
| D3 人工匹配→自动配线（manual_matches.py） | ✅ | --manual-matches/--export-unmatched 落地 |
| D4 电源芯片匹配（power_ic.yaml + power_ic_scorer） | ✅ 框架 | practice dc_dc/ldo 候选清单已采集；映射规则待 Cadence 实测 |
| T8 跨页网优化（IOPORT 对齐） | ✅ | cross_page_opt 测试通过 |

#### 验证

- 测试 **496 passed / 1 skipped**（433→496，+63）
- HG5015 5 模式转换全成功（p0 无回归 24 页/84%）
- 遗留：--aesthetic-placement（力导自动布局）/ A* 迷宫 远期；D4 映射规则待实测

#### 路线图后续

```
[下轮]  --aesthetic-placement 力导自动布局（M2）+ 差分对布局约束
[远期]  A* 迷宫（布局重排后折线失效场景）
        D4 电源映射规则（Cadence 实测后写）
        manual_matches GUI（转换器界面人工确认匹配）
```

---

### XIV.1 Phase XV：Cadence 实测 7 问题修复（2026-08-11 追加）

> Cadence 16.6 实测（errors.txt）7 大类问题：SPCOCN-543 刷屏/电容偏下/IO口挤右上角/单 GND/元件翻转/CH347 未匹配/电线贴引脚。
> 研究 phaseXV-cadence-issues-analysis.md + 用户决策（GND 每芯片/IO 网络名优先/占位符号）。测试 519/5。

#### 修复项与状态

| 项 | 状态 | 实测 |
|----|:---:|------|
| P0-A LASTPIN 格式对齐 04p4 | ✅ | $PN 块 PAINT=0、R 1/J 0 各 2009 行 |
| P0-B 电容"差一点" | ✅ | A 修复自愈 |
| P0-E rotation 90↔270 | ✅ | _dehdl_rotation（L20 实证） |
| P0-F 占位符号 | ✅ | PLACEHOLDER 19 处、CH347 归零 |
| P1-C IO口边缘分布 | ✅ | IOPORT 右缘单列等间距（x=-600 统一） |
| P1-D GND 每芯片分布 | ✅ | GND 38→1082 |
| P1-G stub 引出段 | ✅ | WIRE 段 4879→11348（+132%） |
| aesthetic 启用美观布线 | ✅ | 用户"没区别"根因修复 |

#### 遗留（诚实）

- L20 mirror 翻转：M 行（MY/MX）语法待 Cadence 验证后启用（P1 远期）
- IOPORT 522 是否含页内网：EDIF off_page 语义需进一步核对
- A* 迷宫仍远期（布局重排场景）

#### 路线图后续

```
[下轮]  Cadence 复测 output_phaseXV_{final,aes}
        mirror M 行验证（若 L20 仍翻转）
        IOPORT 页内网语义核对
[远期]  A* 迷宫 / EDIF 折线反推引脚（P2）
```

---

### XV.1 Phase XVI：镜像归一化 + IOPORT 一致性核对（2026-08-11 追加）

> 用户确认排期两项遗留（L20 翻转 / IOPORT 522 语义）。架构师 system_design0811-phase16.md，测试 581/5。

#### 修复项与状态

| 项 | 状态 | 实测 |
|----|:---:|------|
| rotate_point 镜像顺序修正（EDIF 标准：镜像在前旋转在后） | ✅ | MX/MY/MYR90/MXR90 全对（独立验证 4/4） |
| closest_rotation_for_mirror（等效 R 行） | ✅ | 竖直双引脚 4 类镜像全精确（MX→R2/MY→无/MYR90→R3/MXR90→R1） |
| csa_writer Pass1/Pass2 镜像集成 | ✅ | R2(180°) 121→190（MX 类生效） |
| [MIRROR] 报告节 | ✅ | total=154 exact=134 approx=20（标注人工复核） |
| ioport_audit 三节检测 | ✅ | unwired=0 / conflict=1(wps/WPS) / orphan=7(auto-net) |
| GND 符号 mirror 一致（主理人修） | ✅ | 电源 LASTPIN∈WIRE 22/22（a5 断言捕获） |

#### 验证

- 测试 **581 passed / 5 skipped**（519→581，+62）
- HG5015：24 页/84%；0 off-grid、0 短路
- 遗留：20 个 approx 镜像方向待 Cadence 复核；orphan 7 待 skip_orphan 启用

#### 路线图后续

```text
[下轮]  Cadence 复测 output_phaseXVI_final2（镜像方向/连接）
        ioport.skip_orphan=true 启用（消 orphan 7）
        manual_names 网名覆盖（wps/WPS 人工裁决）
[远期]  A* 迷宫（布局重排场景）/ --aesthetic-placement 力导布局
```

---

### XVI.1 Phase XVII：两版实测报错修复 + 新需求（temp_lib/GUI 配置/模拟原理图）（2026-08-12 追加）

> 用户提供两版 Cadence 16.6 实测报错（aes 12:00 / aes6 17:18）+ 四项新需求 + A* 美化布线开源方案调研。
> 团队完成：16 条问题根因分析（架构师）+ 14 条代码核对（工程师）+ A* 开源深度调研（研究员）。
> 阶段性质：**调研+方案交付**（未改源码）；方案文档 `docs/archive/temp files/system_design0812-phase17.md`。

#### 报错根因（代码级）

| # | 根因 | 位置 | 状态 |
|---|------|------|:---:|
| SPCOCN-542 PLACEHOLDER 未声明被删 | csa_writer.py:2141 + placeholder_lib.py:326 | 🔴 待修 |
| SPCOCN-543 SIG_NAME PAINT 违 golden | csa_writer.py:2609-2622 | 🔴 待修 |
| SPCOCN-543 旋转实例/引脚数不匹配 | csa_writer.py:1719-1774/2952 | 🔴 待修（A/B 实测） |
| SPCOCN-515 占位库缺失 | csa_writer.py:1237-1248 | ✅ 17:18 已修 |
| 模拟图标引脚向内/重叠 | placeholder_lib.py:75-83 | 🔴 待修（M1） |

#### 新需求实现路线

```text
[Phase XVII 实现顺序]
  M1 mock_icon_lib（temp_lib 模拟图标，替代占位符号）       ← P0
  M2 collision.py + M3 placement_fitter（统一重叠检测+腾挪） ← P1
  M4 wire_simplifier（SKiDL cleanup_wires 移植：共线/DOT 合并/GND 聚类） ← P1
  M5 net_name_connect（网络名替代 IOPORT）                  ← P1
  M6 pin_connect_audit + M7 GUI 配置面板                    ← P1
  SPCOCN-542/543 修复（PLACEHOLDER 声明/SIG_NAME PAINT/未命中不发射） ← P0 先行
[下轮]  用户确认 7 项决策 → M1+M4 开发 → QA 回归
[远期]  A* 迷宫（自动布局场景）/ --aesthetic-placement 力导布局
```

#### 待用户决策（7 项）

①SPN 删除 A/B 实测 ②IOPORT→网络名 con/xcon 策略 ③temp_lib 引脚标签（功能名 vs 引脚号） ④GND 合并半径（建议 2000） ⑤电线最长长度（建议 5000） ⑥GUI 框架（PySide6） ⑦chip_config.yaml 优先级

---

### XVI.2 Phase XVII 开发完成（2026-08-12 追加）

> P0 修复 + M1-M8 全部实现并 QA 闭环（662 passed / 5 skipped / 0 failed）。

#### 完成项

| 项 | 状态 | 实测 |
|----|:---:|------|
| SPCOCN-543（坐标命中校验/旋转 SIG_NAME 移 WIRE/引脚数不匹配跳 LASTPIN） | ✅ | 596 SIG_NAME 块全 golden；$PN 2204 块无 PAINT |
| SPCOCN-542（PLACEHOLDER 声明 + entity） | ✅ | placeholder 属性块 04p4 格式 |
| GND 避让 + 标签随旋转 | ✅ | GND 不落芯片/标签随 R 行 |
| M1 temp_lib 模拟图标（BGA 四边/功能名/MOCK_TEXT） | ✅ | 82 cell 全 CDS_LIB temp_lib |
| M2 统一碰撞 + M3 腾挪（芯片不动） | ✅ | detect_collisions 统一函数 |
| M4 wire_simplifier（cleanup_wires 移植） | ✅ | WIRE -32%（开启时） |
| M5 net_name_connect（con 同步去 IOPORT） | ✅ | IOPORT 522→0 |
| M6 pin_connect_audit | ✅ | 2821 引脚四状态报告 |
| M7 GUI 面板（PySide6） | ✅ | 无头降级占位 |
| M8 文件合并（chip_config v2.0） | ✅ | v1.0 自动升级 + v2.0 覆盖 |

#### 路线图后续

```text
[下轮]  Cadence 16.6 实测（重点：①BGA 四边标签渲染方向 ②MOCK_TEXT P 指令渲染
        ③电源/元件 SIG_NAME golden 格式验证 ④mock 图标 CDS_LIB temp_lib 可达性）
        pin_mismatch 762 个匹配质量评审（J4 等 connector 匹配错误 cell）
[远期]  力导布局（--aesthetic-placement，α 调度）/ A* 迷宫（自动布局场景）
        M7 GUI 交互实测（PySide6 环境）
```

---

### XVI.3 Phase XVII 二期完成（2026-08-12 追加）

> 非均匀轨道 + 短网先布 A/B + Cadence 对比分析包（677 passed / 5 skipped）。

#### 完成项

| 项 | 状态 |
|----|:---:|
| 非均匀轨道（_collect_tracks + _find_lane 轨道优先） | ✅ |
| 短网先布（_net_priority_key 负号键 + --net-order） | ✅ |
| 6 版本对比输出（v1-v6） | ✅ |
| Cadence 对比分析包（README + metrics + SPN A/B 模板） | ✅ |
| M7 GUI 实测 | ⚠️ PySide6 环境缺失降级 |

#### 路线图后续

```text
[下轮]  用户在 Cadence 16.6 打开 output_phaseXVII_compare/ 对比 v1-v6
        （重点：布线顺序 v1vs2、对齐 v1vs3、化简 v1vs5、跨页 v1vs6）
        SPN A/B 4 组模板实测（test_spn_g1~g4.csa）
        M7 GUI 交互实测（PySide6 环境）
[远期]  力导布局（--aesthetic-placement）/ A* 迷宫（自动布局场景）
```

---

### XVI.4 Phase XVII 三期完成（2026-08-12 追加）

> GND 聚类合并 + 对比包 v7/v8（684 passed / 5 skipped）。

#### 完成项

| 项 | 状态 |
|----|:---:|
| GND 聚类合并（cluster_radius=2000，就近共用） | ✅ |
| v7 p0+simplify（与 v1 同基线，WIRE -32%） | ✅ |
| v8 gnd-distribute（GND 19→97） | ✅ |
| 对比包扩充至 8 版本 | ✅ |

#### 路线图后续

```text
[下轮]  用户 Cadence 16.6 实测 8 版本对比（v1-v8）
        SPN A/B 4 组模板实测（test_spn_g1~g4.csa）
        M7 GUI 交互实测（PySide6 环境）
[远期]  力导布局（--aesthetic-placement）/ A* 迷宫（自动布局场景）
```

---

# Phase XX 排期：视觉/布局优化（08-13 全面清点后规划）

> 用户实测确认：报错类（A1-A8）已清零；B 类视觉问题为下一阶段主战场。
> 每项标注优先级（P0=影响可用性 / P1=影响可读性 / P2=锦上添花）。

## P0 批次（先做，直接影响连线正确性）

| # | 任务 | 对应反馈 |
|---|------|---------|
| P0-1 | 三段式 stub **默认开**（消除线头/重合线/延伸后连接） | B6、V1-3、V2-4 |
| P0-2 | 避让**默认开**（电线不穿元件，margin/edge_clearance） | B11、V2-3 |
| P0-3 | net_name_endpoints **接线到 csa_writer**（use_net_name 悬空端补网络名，消除 gnd signal 归属错） | B15、V4-1/2/3 |
| P0-4 | J/T/S 匹配修复（J4 等强制 mock，connector_pin_check 生效） | B7、V1-5、V15 |
| P0-5 | resolve_passives **默认开**（被动件重叠消除 ≤50） | B13、V17 |

## P1 批次（可读性优化）

| # | 任务 | 对应反馈 |
|---|------|---------|
| P1-1 | 引脚标签布局（orient 随 side：左侧 0°/右侧 0°/标签在框内对齐） | B5、V1-1/2 |
| P1-2 | IO port 就近放置（按网络聚类，缩短电线） | B8、V1-6 |
| P1-3 | GND 分布增强（密度+避让+接入电路） | B9、V2-1/2/7 |
| P1-4 | 电阻/LB 旋转感知（方向随连线） | B10、V1-3、V7-2 |
| P1-5 | 并联扩展到**所有信号**（不只 GND 端） | B12、V2-5/6、V3 |
| P1-6 | wire simplify 阈值调优（max_wire_len 生效） | B14、V3 |

## P2 批次（体验）

| # | 任务 |
|---|------|
| P2-1 | 542/545 属性提示抑制（STICKY 或文档说明） |
| P2-2 | origin 库结构补全（entity/part_table/chips）或 Project Setup 指引确认 |
| P2-3 | C5：两套 xcon 生成器合并重构 |
| P2-4 | 标签文字方向随元件（text_layout 统一） |

## 执行原则

1. 每项完成后重建 output_phaseXX_compare（**新目录名**，避免 Windows 重名混淆）
2. 每项附防回归测试；全量测试保持 800+ 绿
3. 报错类回归（A1-A8）永不回退——P0 改动后必须重跑 1158/543 语义校验

## Phase XX 追加（08-13 用户决策）

| # | 任务 | 状态 |
|---|------|:---:|
| P0-6 | **mock_all 全量模拟图标**（后端默认，已实现） | ✅ |
| P2-5 | **GUI 面板**：mock_all 复选框 + 手动选择元件匹配（替代自动 mock） | 🟡 待开发 |

## Phase XX 追加（08-13 17:30 用户复测）

| # | 任务 | 状态 |
|---|------|:---:|
| P0-7 | **OverlapResolver 接线**（J/T/电容避让） | ✅ 已实现（overlap.resolve=true；此前死代码） |
| P1-7 | 剩余 7 处 LASTPIN miss（C228/C263 等 resolve 位移 ±25 边缘） | 🟡 待查（default 模式 0；aes 模式边缘） |
| P2-6 | **MOCK 颜色做"属性文本标签"**（symbol 内 T 颜色受限，改 CSA 实例属性标签实现纯红） | 🟡 待实施 |
| P0-4+ | 匹配质量：AMS1117 需 hdl_lib 真实符号（IC3 引脚名 1-8 根因） | 🟡 待实施 |

---

# Phase XXI：Cadence 16.6 最新实测 9 类问题修复（2026-08-14）

> 用户对 output_phaseXXII_compare 全量实测（逐页反馈），报错类 + 视觉类
> 9 项全部闭环。全量 **840 passed / 6 skipped / 0 failed**。

## 本次完成（默认开启）

| # | 任务 | 状态 |
|---|------|:---:|
| P0-A | **SPCOCN-542/545 报错消除**：mock symbol.css 补 9 P 属性（JEDEC_TYPE/PACKAGE_TYPE/DESCRIPTION/SN_NUM + MOCK_TEXT） | ✅ |
| P0-B | **MOCK 标签方式**：T 字号 89（1.5x）+ CSA 实例属性标签（DISPLAY 1.5 + PAINT PINK） | ✅ |
| P1-C | J4/S2 引脚名锚点 px±80、C 短号贴 outline 边 | ✅ |
| P0-D | **IC3 引脚名 pstchip 恢复**（GND/OUTPUT/TAP/INPUT）+ 错误 fallback 覆盖 | ✅ |
| P0-E | 尺寸拉宽：U6H 3000 / U6I 2400 / U6A 2400 / U12 1200 | ✅ |
| P0-F | **引脚名零碰撞**（char_w 28 + 列距铁律 + 重叠避让函数）+ U5_PH 310 键冲突修复（`name:` 前缀） | ✅ |
| P0-G | **overlap_resolver 双重赋值 bug** + 同坐标确定性偏移 + max_move 200 | ✅ |
| P1-H | T 元件 n≤12 行距 50（4pin 高 400→250） | ✅ |
| P2-I | 电线穿元件体检测 → aesthetic_report [WIRE_THROUGH_BODY] | ✅ |

## 剩余/待用户

| # | 项 | 说明 |
|---|----|------|
| R-1 | **Cadence 16.6 复测** | 确认 542 消失、MOCK PINK 色、IC3 GND 引脚、引脚名不重叠 |
| R-2 | SPCOCD-553 Hotfix | 需装 SPB16.60 最新 Hotfix（官方 1604223） |
| R-3 | ORIGIN 库 | 输出包已自包含，需 Project Setup 手动添加 |
| R-4 | 并联全信号（P1-5 旧项） | 用户反复强调，仍排期 |
| R-5 | net name 悬空线补网络名（P0-3 旧项） | 仍排期 |
| R-6 | GUI mock_all 开关（P2-5 旧项） | 待开发 |

## 执行记录

- 根因调查：`docs/archive/temp files/phase21-issues-and-plan.md` + `phase21-root-cause-evidence.md`
- 交付：`HG5015_tests/output_phaseXXIII_compare`（新目录名）
- QA：`scripts/verify_phaseXXI_package.py`（40 项全过）
- Git：`5e80e5e` + `a830c26`

---

# Phase XXII：视觉/布局优化完整实现（2026-08-14）

> Phase XX 排期剩余任务 D1-D8 全量开发完成。全量 **877 passed / 6 skipped**。

## 本轮完成（D1-D8）

| # | 任务 | 状态 |
|---|------|:---:|
| P0-1 | 三段式 stub 默认开（**条件三段式**：通畅 1 段/受阻引出，WIRE 6708） | ✅ |
| P0-2 | 避让默认开（**三口径报告 + 证据化豁免** self-pin/power_symbol） | ✅ |
| P0-3 | net_name_endpoints 接线（use_net_name 悬空端补 SIG_NAME） | ✅ |
| P1-5 | 并联扩展到所有信号（plan_parallel_short hub 短接） | ✅ |
| P1-2 | IO port 按网络聚类（edge_layout 按引脚 y 均值重排） | ✅ |
| P2-3 | 两套 xcon 生成器合并（xcon_writer 唯一源，字节级不变） | ✅ |
| P2-4 | 标签文字方向随元件（--text-layout 开启生效，默认关） | ✅ |
| P1-7 | aes 模式 LASTPIN miss 归零（key 前置+同源+snap50） | ✅ |

## 剩余/待下轮

| # | 项 | 状态 | 说明 |
|---|----|:---:|------|
| R-1 | **Cadence 16.6 复测 output_phaseXXIV_compare** | 🟡 待用户 | 无线头/并联短接/violations 目视/xcon 打开 |
| R-2 | **violations=506 收敛**（trunk 级避让） | 🟡 待评估 | 电源网 trunk 穿体（电气正常）+ 密集页 trunk 穿大体；trunk 级完整绕障属 detour 模式，可评估 p0 加强 |
| R-3 | P0-4+ AMS1117 真实符号（hdl_lib） | 🟡 可选 | 现 mock 图标 + pstchip 真实引脚名已可读；需真实 SOT223 符号资源 |
| R-4 | P2-5 GUI 面板（mock_all 复选框） | 🟡 依赖环境 | 无 PySide6；chip_config.yaml CLI 等价路径 |
| R-5 | P2-2 origin 库 entity/part_table 补全 | ⚪ 待确认 | 用户复测无 ORIGIN 报错则无需开发 |
| R-6 | P1-3 GND 分布增强 / P1-4 电阻旋转感知 | ⚪ 低优先级 | 基础版已交付，增强与聚类/标签联动评估 |
| R-7 | 三段式折线避其他网段（busy_h/v 已做，个别共线段） | 🟡 待上报 | Cadence 目视发现后 T01 增强 |
| R-8 | SPCOCD-553 Hotfix（16.6 官方） | 🟡 待用户 | SPB16.60 最新 Hotfix 1604223 |

## 执行记录

- PRD：`docs/archive/temp files/phase22-prd.md`（D1-D8 + Q1-Q8）
- 设计：`docs/archive/temp files/phase22-system-design.md`（T01-T05 任务分解）
- QA：`docs/archive/temp files/phase22-qa-report.md`（独立验证 + Round-3 报告语义实锤）
- 交付：`HG5015_tests/output_phaseXXIV_compare`
- Git：`b7c28b0` + `b8ef8d0` + `4dfb333`

---

# Phase XXIII：三项未开发任务完成（2026-08-14）

> Phase XX/XXI/XXII 清点剩余代码类任务全量完成。全量 **929 passed / 6 skipped**。

## 本轮完成

| # | 任务 | 状态 | 验收 |
|---|------|:---:|------|
| P1-3 | GND 分布增强（密度补点/trunk 避让/outlet 绕行） | ✅ | 机制+开关+单测 14；真实补点 2（数据特性）；--gnd-distribute 开启 |
| P1-4 | 电阻旋转感知（方向随连线） | ✅ | 一致率 100% ≥ 80%；310 重叠 0；--rotate-passives 开启 |
| R-2 | trunk 避让（span 感知推离+冲突计数） | ✅ | **violations 506→457**，trunk 穿体=0，WIRE 6492 不增反降 |

## 剩余/待下轮（未开发清点 v2 更新）

| # | 项 | 状态 | 说明 |
|---|----|:---:|------|
| R-1 | **Cadence 16.6 复测 output_phaseXXV_compare** | 🟡 待用户 | GND 密度/旋转/穿体目视 |
| R-2' | violations=457 进一步收敛（stub 穿体） | 🟡 待评估 | trunk 穿体=0 已达成；剩余为 stub 段（真实库引脚/电源网长 stub），完整绕障属 detour |
| R-3 | P0-4+ AMS1117 真实符号（hdl_lib） | 🟡 可选 | 需外部 SOT223 素材；mock+pstchip 已可读 |
| R-4 | **GUI 完整重设计** | 🔴 文档先行 | phase23-plugin-architecture §6 已规划；后端插件化后 S9 实现 |
| R-5 | P2-2 origin 库补全 | ⚪ 待确认 | 复测无 ORIGIN 报错则免开发 |
| R-6 | P1-3 密度阈值增强 | 🟡 可选 | 当前触发严格（>1500）；如需更强可调阈值/按页平均密度 |
| R-7 | 三段式折线避其他网段 | 🟡 待上报 | Cadence 目视发现后 T01 增强 |
| R-8 | SPCOCD-553 Hotfix（16.6 官方） | 🟡 待用户 | SPB16.60 Hotfix 1604223 |
| R-9 | **插件化重构（cis2hdl_plugin_ver）** | 🟡 已规划 | phase23-plugin-architecture v2：独立文件夹+pluggy+yaml profile+GUI 文档先行 |

## 执行记录

- 设计：`docs/archive/temp files/phase23-incremental-design.md`（T1/T2/T3 函数级方案）
- QA：`docs/archive/temp files/phase23-qa-report.md`（独立验证：三项 PASS + 3 非阻塞遗留）
- 交付：`HG5015_tests/output_phaseXXV_compare`
- Git：`8e72e73`（三项实现）+ `6ee1b3c`（QA round-1 non_trunk）
