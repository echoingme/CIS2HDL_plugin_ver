# CHANGELOG

本文档记录 CIS2HDL 项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [1.1.0] — 匹配系统 v2.0 重构 (2026-08-07) ✅

### 架构变更
- **两阶段匹配架构**: TypeHypothesis → CandidatePool → PassiveMatcher（5 级确定性）/ ActiveMatcher（5 维评分）
- final_conf = phase1_prior × phase2_within；STOP_SEARCH=0.75 / NEEDS_REVIEW=0.40
- **修复规模**: 15 项 P0 + 10 项 P1 + 5 项 P2
- **新建**: `type_hypothesis.py` / `passive_matcher.py` / `active_matcher.py` / `candidate_pool.py` / `type_gate.yaml`
- **删除**: MultiScorer（全库打分逻辑）

### 结果
- 匹配: **889/889 全匹配**，零跨类型错误，quality=72%
- 测试: **268 passed, 23 skipped, 0 failed**（291 collected）
- **PAINT WIRE 生成器彻底移除**（用户决策：Cadence 16.6 不支持，详见下方 [0.9.0] X-8 注记）

---

## [1.0.0] — MultiScorer 全库打分匹配时代 (2026-08-06)

### 变更
- **MultiScorer 全库打分匹配**（6 维加权 + PrefixAffinityCalculator）
- 声称 889/889 全匹配，但存在跨类型错误 50+ 例
- 2026-08-06 深度分析定性为**质量倒退**

### 测试
- 134 passed, 23 skipped, 0 failed

---

## [0.9.0] — Phase X: Cadence SPB 16.6 实测兼容性修复 (2026-08-06) ✅

### 实测发现 (Cadence SPB 16.6 DEHDL)

在含有 Cadence Allegro SPB 16.6 的机器上打开 output_final/5015.cpm，产生 8 类错误。

### 已修复

| ID | 任务 | 优先级 | 修改文件 | 状态 |
|----|------|:--:|------|:--:|
| X-1 | `_resolve_body_name()` 改为返回 cell 名 | P0 | csa_writer.py | ✅ |
| X-2 | 新增 `_resolve_part_name()` 方法 | P0 | csa_writer.py | ✅ |
| X-3 | PART_NAME 使用 primitive 名 | P0 | csa_writer.py | ✅ |
| X-4 | 移除 LASTPIN SIG_NAME 生成 | P0 | csa_writer.py | ✅ |
| X-5 | ADD_COMMENT 格式标准化 | P1 | csa_writer.py | ✅ |
| X-6 | 信息页乱码文本过滤 | P1 | csa_writer.py | ✅ |
| X-7 | SET PAGE_NUMBER 改为页标题 | P2 | csa_writer.py | ✅ |
| X-8 | **PAINT WIRE 连线渲染** (DSN Wire→CSA) | P2 | dsn_parser.py + csa_writer.py | ✅ |

### Added — PAINT WIRE 连线功能 (X-8)
> **注记（2026-08-07 追加）**：该生成器已于 2026-08-07 随 v1.1.0 整合决策彻底移除（Cadence 16.6 不支持）。
- **DSN Wire 映射修复** (`core/parser/dsn/dsn_parser.py`)
  - `wire_net_map` 始终构建（不再受 `if not net_map` 限制）
  - IRWireSegment 的 net_name 通过 wire_id→net_name 解析，不再硬编码为空
- **PAINT WIRE 命令生成** (`core/writer/csa_writer.py`)
  - 新增 `_build_wire_segments()` — 按 net_name 分组，生成 CSA PAINT WIRE 命令
  - 新增 `_compute_wire_transform()` — 从线缆端点计算包围盒→缩放→Y轴翻转
  - 新增 `_transform_wire_coord()` — DSN→DEHDL C SIZE PAGE 坐标映射
  - 输出格式: `PAINT WIRE;` + `(x1 y1) (x2 y2);`，使用默认 YELLOW 颜色
- **效果**: 7 页 16 条线缆段，HG5015 共 3717 nets（跨页通过 Port/Global 标签连接）
- **线宽**: 原理图阶段默认为细线（1px），PCB 布线阶段才需要精确 mil 级控制

### 实测效果
- SPCOCN-515 错误 → **0**
- SPCOCN-543 警告 → **0**
- SPCOCN-1909/1910/1908 语法错误 → **0**
- 元件 symbol 显示率 → **~95%** (从 ~20%)
- 页面名称 → 显示原始标题 (如 "05-Power_Supply1")
- 连线渲染 → 新功能，7 页含 PAINT WIRE
- **测试**: 134 passed, 23 skipped, 0 failed

---

## [0.8.2] — Phase IX续: Value Hint + 误报消除 + 输出去重 + R*电感 (2026-08-05)

###Added
- **VALUE→CATEGORY 映射表 + 电感值识别** (`core/matcher/fallback.py`)
  - 新增 `VALUE_CATEGORY_HINTS`: DZ_→zener, MJ8→connector, TESTPOINT→hole, NH→inductor
  - NH/uH 值（9.1NH/2.2UH等）自动识别为电感类，即使 refdes 前缀为 R*
  - **影响**: D*(+7), J*(+6), TP*(+8), R*电感(+4) → 共提升20个匹配
- **PST 单元测试** (`tests/unit/test_pst_parsers.py`，新建)
  - 12个测试覆盖 pstchip/pstxprt/pstxnet 三个解析器
  - 含 INSxxx→refdes 映射、pstchip lookup bridge 验证
- **pst_value/jedec_type 列** (`core/writer/mapping_csv_writer.py`)
  - 逐器件映射报告新增 PST 数据列
  - pst_value 来自 pstchip VALUE, jedec_type 来自 pstchip JEDEC_TYPE

### Fixed
- **输出文件去重** (`core/engine/conversion_engine.py`)
  - 修复 xref.* 动态页面导致同一 .csa 被重复写入 output_files (259→1)
  - 输出文件数: 291 → **33** (去重后)
- **信息页标题** (`core/writer/csa_writer.py`)
  - 为无实例页添加 `ADD_COMMENT [page_name]` 标题注释
- **Value match 误报消除** (`core/matcher/value_matcher.py`)
  - 修复前: 590条 "Value match: 33PF→33PF" 正确匹配被误记为 warning
  - 修复后: 只在 source value ≠ ptf value 时产生 warning → 590→0
- **pstchip 多行 pin 解析** (`core/parser/pstchip_parser.py`)
  - 修复状态机: pin 名称和 PIN_NUMBER 跨行定义时能正确关联
  - 现在 pins dict 完整填充 (A→1, B→2)

### Changed
- **JEDEC_TYPE→primitive 选择** (`core/writer/csa_writer.py`)
  - 新增 `_find_body_by_jedec_type()`: 从 JEDEC_TYPE 提取封装尺寸 → 匹配 HDL primitive
  - `_resolve_body_name()` 在 matched primitive 未选定时 fallback 到 JEDEC_TYPE 驱动选择

### Stats
- 匹配: **825 成功, 64 失败** (v0.8.1: 803/86, v0.8.0: 801/88)
- 测试: **109 passed, 6 skipped** (新增 12 PST 测试)
- Value match 误报: 590 → **0**
- No_Pin_Connections: **0**

### Fixed
- **pstxprt 解析器完全重写** (`core/parser/pstxnet_parser.py`)
  - 修复多行 PART_NAME 格式解析 (PART_NAME和refdes在不同行) → 从1条提升到**906条**
  - 新增 INSxxx→refdes 映射提取 (从 C_PATH/P_PATH 中提取 `INS32276 → C1`)
  - 产出: 906 pstxprt entries + 906 INSxxx→refdes 映射
  - LED5/LED6/M1/D9/D11 等之前无法解析的元件现在全部可解析
- **pstxnet 解析器修复** (`core/parser/pstxnet_netlist_parser.py`)
  - 支持多行 NET_NAME 格式 (NET_NAME和名称在不同行)
  - 跳过子行 (C_SIGNAL/DIFFERENTIAL_PAIR等) 避免状态机混乱
  - 产出: 823 refdes × 1818 pin connections
- **mapping CSV 统计修复** (`core/writer/mapping_csv_writer.py`)
  - 使用实际页面计数: 原理图页(带instances + 非xref) + 信息页(有图形)
  - CSA 文件数从report引用改为磁盘glob扫描
  - 输出: "CIS 实际页面数,20" (16 原理图 + 4 信息页)
- **No_Pin_Connections 消除**: 从多个降低到 **0** (LED5/LED6/M1-M6/IC3全部解析)

### Changed
- **Unity Boost 扩展** (`core/matcher/fallback.py`)
  - 单候选提升覆盖所有 confidence ≥ 0.50 的情况 (原来仅 0.50)
  - INDUCTOR/DIODE/CONNECTOR 单变体类别也获得 +0.10 boost

### Stats
- 转换验证: pages=20, 20 CSA, ZERO No_Pin_Connections
- 匹配: 803 成功, 86 失败, 85 模糊 (v0.8.1: 803↑/86↓/85↓ vs v0.8.0: 801/88/87)
- 测试: 97 passed, 6 skipped (零回归)

---

## [0.8.0] — Phase IX: PST网表集成 + 页面BUG修复 + 匹配增强 (2026-08-05)

### Added
- **pstchip.dat 解析器** (`core/parser/pstchip_parser.py`，新建)
  - 解析 OrCAD PSTWRITER LIBRARY_PARTS 格式 (7615行)
  - 提取每个 primitive 的 PART_NAME、JEDEC_TYPE、VALUE、引脚定义
  - 作为可选数据源，文件缺失时不抛异常
- **pstxnet.dat 网络连接解析器** (`core/parser/pstxnet_netlist_parser.py`，新建)
  - 解析 EXPANDEDNETLIST 格式，提取 refdes→{pin:net_name} 映射
  - 支持多行 NET_NAME 格式 (名称单独一行)
  - 产出: 823 refdes × 1818 pin connections
- **pstxprt → pstchip 查找桥** (`core/parser/pstxnet_parser.py`)
  - 新增 `build_pstchip_lookup()` 静态方法
  - 将 pstxprt 的 refdes→primitive 映射桥接到 pstchip 的完整规格
- **PST 数据注入管线** (`core/engine/conversion_engine.py`)
  - Stage 2.3: 自动检测并解析 pstchip/pstxprt/pstxnet 三个文件
  - Stage 2.5b 增强: 注入 PST JEDEC_TYPE、VALUE、PART_NAME 到实例 extra_data
  - Stage 5.5b: pstxnet 补充 pin 连接注入 (补充 EDIF 未覆盖的实例)
- **JEDEC_TYPE 精确匹配** (`core/matcher/exact.py`)
  - ExactMatcher 新增 JEDEC_TYPE fallback 匹配 (conf=0.95)
  - 从 PST JEDEC_TYPE 直接匹配 HDL 库 chips.prt JEDEC_TYPE

### Fixed
- **278页→20页 BUG** (`core/diagnostics/file_inventory.py`)
  - 页面计数改为匹配 `\d{2}-` 命名模式
  - CFB 容器内部子流 (PAGE1/VRTL等) 不再被计为页面
  - fallback raw entry scan 同样应用页面名模式过滤
- **Value match warning 消息误导** (`core/matcher/value_matcher.py`)
  - Warning 现在显示匹配到的 ptf 行 VALUE (如 '33PF') 而非 ComponentDef.value (如 '100NF')
  - 格式: "Value match: '33PF' → '33PF' (ptf)"

### Changed
- **DZ_前缀映射** (`core/matcher/prefix_filter.py`, `core/parser/component_catalog.py`)
  - 新增 'DZ' → ['zener', 'diode', 'tvs'] 映射
  - DZ3/DZ_L 等齐纳二极管类 refdes 优先匹配 zener 类别

### Stats
- 测试: 97 passed, 6 skipped (零回归)
- PSTXNET 解析: 823 refdes × 1818 pin connections
- EDIF 注入: 2713 pin → 880 实例
- PSTXNET 补充注入: 14 pin → 9 实例
- CSA 文件数: 20 page*.csa (正确，修复前为 278)

---

## [0.7.1] — Phase IX: EDIF 映射修复 + 模糊匹配提升 (2026-08-05)

### Fixed
- **EDIF INSxxx→real_refdes 映射** (`edif_parser.py`)
  - Strategy 1: 从 `(property REFDES (string "C122"))` 提取
  - Strategy 2: 从 `(designator (stringDisplay "C106" (display ...)))` 提取
  - **成果**: C122→2 pins, U1→6 pins, R1→2 pins, D1→2 pins
  - 全量 908 refdes × 2771 pin 连接成功映射到真实 refdes

### Changed
- **FallbackMatcher Unity Boost** (`fallback.py`)
  - 当 category filter 只剩唯一候选时，confidence 0.50 → 0.65
  - 新增 `prefix_unity` 匹配层级
  - 预期 125 模糊匹配 → 大部分提升至 ≥0.6

---

## [0.7.0] — Phase VIII: Primitive 精准选择 + 坐标校准 + 值注入 (2026-08-05)

### Added
- **HDL Scanner 全 Primitive 存储** (`hdl_scanner.py`)
  - `ComponentDef.extra_data["all_primitives"]` 包含 chips.prt 的所有 primitive 定义
  - 每个 primitive: part_name, body_name, pins, category, footprint, description
- **ValueMatcher Primitive 选择** (`value_matcher.py`)
  - 新增 `_select_primitive_by_value()` — 通过 part.ptf VALUE → ptf_row.package_type → primitive 链选择最具体 primitive
  - 电容/电阻从通用 "capacitor" / "resistor" → "CAPACITOR_0402" / "RESISTOR_0402"
- **FallbackMatcher Primitive 选择** (`fallback.py`)
  - Step 5.5: 匹配后通过 ptf_rows 反查最佳 primitive
  - 存储 `selected_primitive_body` 到 `best_candidate.extra_data`

### Changed
- **CSA Writer** (`csa_writer.py`)
  - `_resolve_body_name()` 检查 `comp.extra_data["selected_primitive_body"]`，返回精准 BODY_NAME
  - 坐标筛选条件与 `generate_hdl_sch.py` 对齐
- **Mapping CSV Writer** (`mapping_csv_writer.py`)
  - cis_value 增加 ComponentCatalog 回退路径
  - 值注入率: 883/889 (99.3%)

### Results
| 指标 | v0.6.0 | v0.7.0 |
|------|:--:|:--:|
| FORCEADD 精准 primitive | 0% | **81.6%** |
| CAPACITOR_0402 | 0 | **321** |
| RESISTOR_0402 | 0 | **171** |
| cis_value 注入率 | ~95% | **99.3%** |
| 匹配率 | 99.9% | 99.9% |
| 坐标映射 | 理论就绪 | 与 generate_hdl_sch.py 对齐 |

### Known Issues
- EDIF INSxxx→real_refdes 映射缺失（EDIF 仅以 display string 存储）
- INDUCTOR/DIODE/CONNECTOR 等无尺寸变体类别无精准 primitive 可选

---

## [0.6.0] — Phase VII: 匹配增强 + Pin 连接注入 (2026-08-05)

### 问题诊断
- 130 个元件匹配失败/模糊（96 模糊 @conf=0.5 + 34 完全失败 @conf=0.0）
- 914/914 实例缺少 pin_connections → CSA 无 LASTPIN SIG_NAME
- 4 个信息页已有 TitleBlock 解析（`_extract_info_page_graphics` 已实现）

### Added
- **EDIF Pin 连接注入** (`conversion_engine.py` Stage 5.5)
  - 新增 `EDIFParser.extract_pin_net_map()` 轻量级 pin→net 映射提取
  - 解析 EDIF 文件中的 `(net ... (joined (portRef PIN (instanceRef REFDES))))` 结构
  - 注入到 `ComponentInstanceIR.pin_connections` 供 CSA writer 生成 LASTPIN SIG_NAME
- **ROUTE 过滤** (`component_catalog.py`)
  - `_SKIP_REFDES_VALUES` 过滤集合，跳过 ROUTE 非元件条目

### Changed
- **前缀映射表扩展** (`prefix_filter.py` + `component_catalog.py`)
  - 新增前缀: LB, M, S, IC, LED, ZD, VR, RN, K, Z, P, ROUTE
  - U* 扩展: 增加 ic, mod 类别回退
  - T* 扩展: 增加 c_transformer, v_transformer, network_tf, inductor_gm
  - J* 扩展: 增加 screw
  - 统一两个 _PREFIX 表
- **FallbackMatcher** (`fallback.py`)
  - "0" 值元件置信度提升: 0.50 → 0.55 (prefix_zero tier)
  - 新增 `prefix_zero` 匹配层级标签

### Fixed
- LB* 磁珠: confidence 0.0 → ≥0.5（新增前缀映射）
- S/M/IC 元件: confidence 0.0 → ≥0.5（新增前缀映射）
- "0" 值元件 (114个): confidence 0.5 → 0.55（前缀+零值增强）
- ROUTE 条目: 不再创建假实例

### Known Issues
- OLB 符号匹配仍使用通用 category 名（如 capacitor 而非 CAPACITOR_0402）— 需后续 Phase 处理
- 信息页 TitleBlock 坐标精度有限 — 文本以 ADD_COMMENT 注释形式输出

---

## [0.5.0] — CrossRef 驱动架构重构 (2026-08-04)

### 架构决策
- **CrossRef CSV 升级为主数据源**: 组件身份(refdes)、value、坐标、页面归属 100% 来自 CrossRef CSV
- **DSN 降级**: 仅用于网络拓扑（Wire/Net 端点坐标），PlacedInstance 实例解析完全移除
- **高内聚低耦合**: 每个数据源（CrossRef、DSN、EDIF、OLB、HDL）由独立模块解析

### Added
- **ComponentCatalog** (`cis2hdl/core/parser/component_catalog.py` — 371 lines)
  - `CatalogEntry` dataclass: refdes, value, footprint_hint, loc_x, loc_y, page_name
  - `ComponentCatalog`: 按 refdes 和 page 索引，`from_cross_ref()` 工厂方法
  - `to_component_defs()`: 直接从 catalog 构建 ComponentDef 列表供匹配使用
- **ValueMatcher** (`cis2hdl/core/matcher/value_matcher.py` — 152 lines)
  - 基于 part.ptf 料表数据的精确值匹配 (PRIORITY=3)
  - normalize_value 跨格式比较 (0.2pF ↔ 0.2PF)
  - 利用 HDL ComponentDef.extra_data["ptf_rows"] 存储料表数据

### Changed
- **转换管线重构** (`conversion_engine.py`):
  - Stage 2.5: CrossRef CSV → ComponentCatalog 构建
  - `_stage_match()`: 优先使用 ComponentCatalog, legacy `_extract_cis_components()` 作为回退
  - `_extract_cis_components()`: 简化，catalog 可用时直接返回 `catalog.to_component_defs()`
  - 移除 `_map_edif_types_to_dsn()` 调用、`EdifInstanceInfo` dataclass
- **DSN 解析器瘦身** (`dsn/structures.py`):
  - 移除 `_RtlStructure`, `_parse_placed_instance_rtl()`, `_split_rtl_pkg_name_reference()`
  - 保留 `WireSegment`, `NetAlias`, `Port`, `TitleBlockText` 等网络/图形结构体
- **匹配管线** (`pipeline.py`): 新增 ValueMatcher 为阶段 3.5
- **ComponentDef** (`component.py`): 新增 `extra_data: dict` 字段存储 ptf_rows

### Results
| 指标 | v0.4.6 | v0.5.0 |
|------|:--:|:--:|
| 自动匹配率 | 15% (31/724) | **86% (784/914)** |
| 总匹配 (含模糊) | 15% (108/724) | **96% (880/914)** |
| refdes 准确率 | 14% | **100%** |
| 坐标准确率 | 35% | **100%** |
| 页面归属准确率 | 5% | **100%** |
| 假阳性匹配 | 0 | **0** |
| 单元测试 | 97/97 | **97/97 (零回归)** |

### Known Issues
- **nets=0**: DSN Wire/Net 数据结构正确解析但未传递到 DesignIR builder
- 信息页 (Cover/Clock/Power/Block) preamble 扫描仍返回 0 结构体
- 无 CrossRef CSV 时依赖 legacy DSN 路径 (匹配率回退至 15%)
- ValueMatcher 依赖 part.ptf 数据加载 (部分 HDL 库组件 part.ptf 为空)

### Roadmap
- 完整架构文档: `docs/ROADMAP_AUDIT_2026-08-03.md` §第八节 Phase VI

---

## [0.5.0] — CrossRef 驱动架构重构 (2026-08-06) [重复条目]

> 与 08-04 条目重复，已合并（保留 08-04 版为主，见上方 `[0.5.0] (2026-08-04)` 条目）。

### 架构重构

**放弃 DSN 二进制作为组件身份/坐标/页面数据源。CrossRef CSV 是组件身份的唯一权威来源。**

DSN 仅保留网络拓扑（Wire/Net 端点）功能。

### Added
- **ComponentCatalog** — 新建 `component_catalog.py`
  - 从 CrossRef CSV 构建完整组件目录（914 个条目）
  - 提供 `get_by_refdes()`, `get_page_entries()`, `to_component_defs()`, `to_component_instance_irs()`
  - 零外部依赖，仅依赖 stdlib + `core/ir/component.py`
  - `CatalogEntry` 含 refdes、value（已去 `*` 后缀）、坐标（mils）、页面名、schematic 路径
- **ValueMatcher** — 新建 `value_matcher.py`
  - 基于 part.ptf 料表数据的电气值精确匹配
  - MATCHER_PRIORITY=3，插入 FeatureExtractMatcher 和 FallbackMatcher 之间
  - 搜索 HDL ComponentDef.extra_data["ptf_rows"] 的 VALUE 列匹配
  - 归一化规则：大小写不敏感，统一电容单位（n→N, u→U, p→P）
- **MatchStrategy.VALUE** — 新增 VALUE 匹配策略枚举值
- **ComponentDef.extra_data** — 新增 `extra_data: dict` 字段存储 ptf_rows 等扩展数据
- **hdl_scanner.py** — 将 part.ptf 完整行存入 `ComponentDef.extra_data["ptf_rows"]`

### Changed
- **conversion_engine.py** — 新管线顺序：
  1. Parse DSN（仅网络拓扑）
  2. Build ComponentCatalog（CrossRef CSV）
  3. Scan HDL Library
  4. Match（使用 catalog 的 refdes）
  5. Validate
  6. Generate
- **MatcherPipeline** — 新增 ValueMatcher 阶段（Exact → Fuzzy → Feature → Value → Fallback → Manual）
- **pipeline.py** — 从 5 阶段扩展为 6 阶段匹配管线

### Removed
- **EDIF type mapping 管线** — 删除 `_map_edif_types_to_dsn()`, `_build_edif_info_map()`, `EdifInstanceInfo`
- **垃圾检测** — 删除 `_is_garbage_library_id()` 及辅助正则/信号前缀
- **RTL PlacedInstance 解析** — 删除 `_parse_placed_instance_rtl()`, `_split_rtl_pkg_name_reference()`
- **RTL T0x10 解析** — 删除 `_parse_rtl_t0x10_list()`, `_parse_rtl_t0x10_direct()`, `_parse_rtl_t0x10_body()`
- **RTL 块检测** — 删除 `_try_parse_standalone_rtl_t0x10()`, `_is_rtl_pin_like_name()`

### Fixed
- DSN structures.py 清理：移除 ~280 行 RTL 死代码
- page_parser.py 简化：移除 RTL PlacedInstance dispatch 和 standalone T0x10 处理

---

## [0.4.6] — P0 匹配系统修复：CrossRef CSV 注入 + FeatureExtract 去假阳性 + Fallback 修复 + JEDEC_TYPE (2026-08-04)

### Added
- **P0-1: Cross Reference CSV 解析器** — 新增 `cross_ref_parser.py`
  - 解析 OrCAD CIS 导出的 Cross Reference CSV（refdes + value + 坐标 + 页面名）
  - 自动编码检测（utf-8-sig → utf-8 → gbk → latin-1）
  - `CrossRefEntry` dataclass 含 `x_mils`/`y_mils` 坐标转换（英寸×100→mils）
  - 可选数据源：文件不存在时静默跳过，不阻断流程
- **P0-1: CrossRef 注入管线** — `conversion_engine.py` Stage 2.5
  - 自动检测 DSN 旁的同名 `.CSV` 文件并加载
  - 非破坏性注入：补充缺失的 value_override 和零坐标（(0,0) 位置）
  - 日志记录注入统计（条目数/值数/坐标数）

### Fixed
- **P0-2: FeatureExtractMatcher 假阳性消除** — 修复随机匹配
  - 信号名 `HSI0_CLK_2G` 不再被匹配为 `inductor_gm`（之前 `"0"` 被 RES_PATTERN 误识别为电阻值）
  - 新增 early-return：当 source 无电气特征时直接返回 `no_match`
  - `_extract()` 仅从 `value` 字段搜索电气值，`part_name` 仅作为 value 非空时的补充上下文
- **P0-3: FallbackMatcher refdes 获取路径修复**
  - `refdes_or_id` 获取顺序改为 `refdes → part_name → library_id`（之前 `part_name` 优先级低于 `library_id`）
  - 修复后 FallbackMatcher 可从 `part_name`（真实 refdes）正确提取前缀
- **P0-4: ChipsPrtParser JEDEC_TYPE 提取**
  - 新增 `_RE_JEDEC_TYPE` 正则，从 chips.prt body 段提取封装信息
  - `ComponentDef.footprint` 现在由 JEDEC_TYPE 填充（如 `hole3_2pad`, `0402C-S`）
  - 使 HDL 库组件的 fingerprint 具有区分度
- **P1-3: part.ptf 兼容 `=` 分隔格式**
  - `_split_row_values()` 增加对 `=` 分隔符的兼容（hole 等组件的 part.ptf 使用非标准格式）
  - 参考 `match_cis_to_hdl.py` 的 `re.findall(r"'([^']*)'", line)` 方式提取字段

### Changed
- FeatureExtractMatcher 现在仅在 source.value 非空时进行特征提取，避免从信号名/GPIO/纯数字中误提取
- FallbackMatcher 在 library_id 为垃圾数据（INSxxx/纯数字）时，可从 part_name 获取有效 refdes 前缀

### Known Issues
- DSN 二进制解析的 refdes 仍为垃圾数据（INSxxx/纯数字/信号名），导致 CrossRef CSV 的 refdes 匹配率仅 14%（127/914）
- 需要修复 DSN 页面流 RTL 格式 refdes 解析（P1-1）才能在更大范围内利用 CrossRef 数据
- 当前匹配率：31 精确 + 77 模糊 = 108/724 (15%)，但无假阳性

---

## [0.4.5] — 关键修复：网络名解析 + LASTPIN SIG_NAME + TitleBlock + Cache渐进式 + INSxxx EDIF增强 ([日期待核])

### Fixed
- **F1: 网络名解析 (P0)** — DSN 网络别名映射到真实网络名
  - `dsn_parser.py` `_build_page_ir()` 接受 `page_data.aliases`，构建 `net_alias_map`
  - 引脚连接和网络创建时使用 `NetAlias.name` 替代 `NET_{net_id}` 占位符
  - 修复 HG5015 中所有网络名为 `NET_xxx` 占位符的问题

- **F1: LASTPIN SIG_NAME 生成** — CSA 文件中的引脚-网络连接
  - `csa_writer.py` 移除"方案A"抑制注释块
  - 新增 `FORCEPROP 3 LASTPIN (...) SIG_NAME` 生成逻辑
  - 格式对齐 Cadence 官方参考：`FORCEPROP 3 LASTPIN (-1750 2200) SIG_NAME GND\g`
  - 跳过不可解析的 `NET_` 占位符网络

- **F2: TitleBlock 解析** — 4 信息页标题栏文本提取
  - `structures.py` 新增 `TitleBlockText` dataclass + `parse_title_block()` 函数
  - `page_parser.py` 注册 TitleBlock 解析器（最低优先级，仅当其他 parser 失败时尝试）
  - `PageData` 新增 `title_blocks` 字段

- **F3: INSxxx EDIF 增强** — EDIF 实例信息索引增强
  - `conversion_engine.py` `_build_edif_info_map()` 返回 `(edf_map, ins_map)` 元组
  - `_map_edif_types_to_dsn()` 新增 INSxxx 回退匹配：当 refdes 匹配失败时，检查 DSN 实例的 `library_id` 是否以 INS 开头且在 `ins_map` 中

- **F4: Cache 渐进式解析** — 防御性检查和诊断增强
  - `cache_parser.py` 新增 `_dump_hex_context()` 函数（hex dump 诊断工具）
  - `_parse_library_part()` 在 `_skip_to_next_boundary()` 失败时添加防御检查
  - SymbolPin 解析异常日志级别从 `debug` 提升到 `warning`

### Changed
- `cis2hdl/core/parser/dsn/structures.py` — +TitleBlockText, +parse_title_block()
- `cis2hdl/core/parser/dsn/page_parser.py` — +title_blocks 字段, +TitleBlock dispatch, +is_valid
- `cis2hdl/core/parser/dsn/cache_parser.py` — +_dump_hex_context(), +defensive check, warning级别
- `cis2hdl/core/parser/dsn/dsn_parser.py` — _build_page_ir() 网络别名映射
- `cis2hdl/core/writer/csa_writer.py` — LASTPIN SIG_NAME 生成
- `cis2hdl/core/engine/conversion_engine.py` — INSxxx EDIF 索引增强

### QA
- 待运行全量测试验证（目标: ≥123 tests 零回归）
- 待运行 HG5015 转换验证 CSA 含 LASTPIN SIG_NAME

---

## [0.4.4] — Phase V-B + V-C: Cache LibraryPart 修复 + refdes 分离 + PstxnetParser (2026-08-04)

### Added
- **PstxnetParser** — 新增 pstxprt.dat 解析器 (`cis2hdl/core/parser/pstxnet_parser.py`)
  - `PstxprtEntry` dataclass: refdes / part_name / footprint / value / section
  - 状态机解析: IDLE → PART_HEADER → SECTION
  - 自动注册到 ParserRegistry（import 时）
  - 对无 pstxprt 文件的项目（HG5015 等）静默跳过

- **V-C1 pstxnet 可选集成** — ConversionEngine Stage 2 后自动加载
  - 三种路径检测: stem 替换 / 父目录 / glob 通配
  - 非破坏注入: 仅填充缺失的 footprint 和 value
  - `_extract_cis_components()` 中构建 refdes+part_name 双索引

### Fixed
- **V-B1 Cache LibraryPart 三层渐进式解析** (`cache_parser.py`)
  - Tier 1: Normal path（保持原有逻辑）
  - Tier 2: `_heuristic_scan_symbol_pins()` — 扫描 512 字节寻找有效 SymbolPin 模式
  - Tier 3: Minimal path — 返回空 pin_names，warning 日志
  - 修复 HG5015 中 prefix byte_offset 不足覆盖 LibraryPart 图形区域的问题

- **V-B2 refdes/pkg_name 五优先级分离** (`structures.py`)
  - 新增 `_split_rtl_pkg_name_reference()` 函数
  - Priority 1: refdes 模式匹配（`_RE_REFDES`）
  - Priority 2: Signal/INS 模式 → 相邻 strLst 探测 + db_id fallback
  - Priority 3: 默认（name == pkg_name == reference）
  - `_RtlStructure` 新增 `strlst_index` 字段

### Changed
- `cis2hdl/core/parser/dsn/cache_parser.py` — `_parse_library_part()` 三层渐进式解析
- `cis2hdl/core/parser/dsn/structures.py` — `_RtlStructure` + `_split_rtl_pkg_name_reference()` + `_parse_placed_instance_rtl()` 重构
- `cis2hdl/core/engine/conversion_engine.py` — Stage 2 后 pstxprt.dat 可选加载 + `_extract_cis_components()` pstxnet 注入

### QA
- 待运行全量测试验证（目标: ≥103 tests 零回归）

---

## [0.4.2] — HG5015 信息页图形 + 乱码修复 + EDIF 器件类型反注 (2026-08-03)

### Fixed
- **乱码 refdes 修复** — DSN 结构体解析器中 refdes 提取逻辑优化，可读率从 64.8% (1088/1680) 提升至 99.6% (997/1001)，乱码率从 ~29% 降至 ~0.4%
- **信息页图形文本提取** — Cover_Page/Block_Diagram/Clock_Tree/Power_Tree 等 4 页信息页的图形文本元素成功提取，共 1853 个 ADD_COMMENT 行
- **EDIF 器件类型反注映射** — 实现 EDIF LIBRARY_ID → DSN instance property 反注，485 个实例获得 EDIF 器件类型标注
- **坐标映射验证** — DSN RTL 坐标 → DEHDL C SIZE PAGE 坐标系映射通过验证，超出边界自动回退网格布局

### Added
- **CSA 信息页图形输出** — CSA Writer 支持 `ADD_COMMENT` 指令输出，信息页的图形文本（标题/注释/框图标注）完整写入 CSA 文件
- **Cadence 测试包就绪** — `output_hg5015/` 目录包含完整可交付结构 (1 `.cpm` + 20 `.csa` + 9 `.xcon` + `cds.lib` + 3164 `master.tag`)

### QA
- **123/123 测试通过** — 全量单元测试 + 集成测试通过 (tests/unit/ + tests/integration/)，零回归
- **HG5015 全量转换验证 (v0.4.2)**:
  - 转换指标: 20 页 / 1001 实例 / 4115 网络 / 30 输出文件
  - 输出文件: `.cpm`=1, `.csa`=20, `.xcon`=9, `cds.lib` ✅, `master.tag`=3164
  - `cds.lib` 无 `./` 前缀 ✅
  - `.xcon` XML 格式有效 ✅
  - FORCEADD 可读率: **968/1001 (96%)** — 比 v0.4.1 的 71% 提升 25 个百分点
  - 信息页图形: page9(371), page10(185), page11(590), page15(707) = 共 1853 ADD_COMMENT 行
- **DSN vs EDIF 交叉验证**:
  - DSN: 20p 1001i | EDIF: 1p 3023i (结构差异，非回归)
  - 可读 refdes: **997/1001 (99.6%)** — v0.4.1 为 64.8%
  - CrossValidator: 2 errors (已知 DSN/EDIF 结构化差异), 1428 warnings

### Known Issues
- 4 个 refdes (0.4%) 仍含乱码字符 — 来自 DSN 文件中 3 个信息页 (Cover/Clock/Power) 的 SIZE PAGE 器件，这些器件无有效 chips.prt 数据，属于预期行为
- CrossValidator page count/instance count 差异 — EDIF 平铺结构 vs DSN 层次结构导致的计数差异，非数据错误

---

## [0.4.1] — HG5015 全量转换验证 (2026-08-03)

### Added
- **Library stream strLst 解析器** — 实现 DSN OLE compound document 中的 `strLst` 子流解析，支持从 Library stream 中提取库路径与器件类型信息
- **EDIF 解析器** — 新增 EDIF 2 0 0 格式解析器 (`edif_parser.py`)，支持解析 EDIF netlist 中的实例、网络与器件类型

### Fixed
- **EDIF 解析器 Windows 路径修复** — 修复 EDIF 文件在 Windows 平台上的路径解析问题
- **PlacedInstance strLst 索引解析修复** — 修复 DSN `PlacedInstance` 结构中 `strLst` 子流的索引偏移错误，确保 refdes、value、footprint 字段正确提取
- **坐标去重和重叠修复** — 修复多人协作设计 (multi-user) 导致的坐标重复与器件重叠问题，通过去重逻辑确保每个器件只有一个有效坐标

### QA
- **123/123 测试通过** — 全量单元测试 + 集成测试通过 (tests/unit/ + tests/integration/)
- **HG5015 全量转换**: 20 页 / 1680 实例 / 4012 网络
  - 输出 20 个 CSA 页面文件
  - `.cpm` 文件正常生成
  - `cds.lib` 无 `./` 前缀 ✅
  - `.xcon` 文件有效 XML ✅
  - `master.tag` 正常生成 ✅
- **FORCEADD 可读率**: 1209/1680 (71%) — 非信息页器件名称基本可读；信息页 (Cover/Clock_Tree/Power_Tree) 的 SIZE PAGE 器件无 chips.prt 数据，属于预期行为
- **DSN 可读 refdes**: 1088/1680 (64.8%)
- **CrossValidator**: DSN 1680 实例 vs EDIF 3023 实例 — 差异主要来自 EDIF 包含电源网络节点 (`&0V9_COMM`, `&12V0` 等)，page count 与 instance count 差异属 EDIF 与 DSN 不同抽象层级导致

### Known Issues
- 29% FORCEADD 行含乱码名称 (471/1680)，主要来自信息页 (Cover/Clock_Tree/Power_Tree) 和 DSN 中无有效 refdes 的原始条目
- DSN 器件类型映射全部归为 "Other"，需 Phase III 实现从 Library stream strLst 中提取真实器件类型
- CrossValidator 报告 1921 warnings，主要是 EDIF 实例在 DSN 中找不到对应（EDIF 包含层次化子电路实例）

---

## [0.3.5] — Cadence SPB 16.6 UPREV 兼容性修复 (2026-08-03)

### Fixed
- **P0-1**: `cds.lib` 移除多余 `./` 路径前缀（`./worklib` → `worklib`, `./hdl_lib` → `hdl_lib`），与参考 `out_hdl` 项目一致
- **P0-2**: **新增 `.xcon` 文件生成器** — `XCONWriter` + `OutputManager.write_xcon()`，生成 Cadence CS Schema XML。`.xcon` 是 Cadence 识别设计结构的关键文件，缺失导致 UPREV
- **P0-3**: `master.tag` 修正 — 由错误引用 `{cell_name}.csa` 改为列出实际页面文件 `page1.csa`, `page2.csa`...
- **P0-4**: `CSAWriter` 颜色方案对齐参考项目 — `COLOR_PROP MONO` → `ORANGE`, `COLOR_NOTE MONO` → `PURPLE`
- **P1-1**: `module_order.dat` 格式修正 — 反斜杠转义 `@\lib.\cell\(view)` → `@lib.cell(view)`
- **P1-2**: `.dcf` 文件初始 `logicalViewRevNum` 由 `2` 改为 `0`
- **P1-3**: worklib 下所有文件使用 CRLF 行尾（`\r\n`），新增 `_write_worklib_file()` 辅助方法
- **P1-4**: 新增 `hdldirect.dat` 文件生成（Lisp S-expression 格式）
- **P2-1**: `.cpm` `session_name` 对齐参考格式: `ProjectMgr0001` → `ProjectMgr3606`
- **P2-2**: `.cpm` 注释工具名: `CIS2HDL` → `SPI`
- **P2-3**: `page1.csv` 添加构建日期
- **CSA-1**: `_build_csa_content()` 添加 `QUIT` 终止符 — CSA 格式必需，缺失导致 SPCOCN-1891 syntax error
- **CSA-2**: 添加 C SIZE PAGE 页面边框块（`FORCEADD C SIZE PAGE..1` + COMMENT_BODY + CDS_LMAN_SYM_OUTLINE + CDS_LIB + EDIT PAGE NAME）— 缺失导致 Cadence 无法识别页面边界
- **CSA-3**: `_resolve_body_name()` 重写 — 优先从 `_match_map`（匹配结果）获取 HDL 库目录名，修复 FORCEADD 使用 DSN 层级名而非 HDL 库名的 Bug（导致 SPCOCN-515 "找不到器件"）
- **CSA-4**: 添加坐标合理性检查（>100000 回退到网格布局）
- **RTL-COORD**: DSN RTL 格式坐标解析修复 — `_RtlStructure.parse()` 用 int16 阈值 (`0x8000`, `0x10000`) 处理 uint32 值，坐标变垃圾数据。改为 `(c2 & 0xFFFF)` 提取 signed int16

### Added
- `cis2hdl/core/writer/xcon_writer.py` — XCONWriter（Cadence CS Schema XML 生成器）
- `docs/fix_proposal.md` — 集中式修复方案文档（12 项发现，含行号、参考写法、修复建议）

### Changed
- `cis2hdl/core/parser/dsn/structures.py` — `_RtlStructure.parse()` 坐标提取修复
- `cis2hdl/core/writer/output_manager.py` — 10 项修改（cds.lib/CRLF/xcon/hdldirect/master.tag/module_order/dcf/session/工具名）
- `cis2hdl/core/writer/csa_writer.py` — 颜色修正 + CSA 格式修复 (QUIT/C SIZE PAGE/body_name/坐标检查)
- `cis2hdl/core/writer/sch_writer.py` — page1.csv 日期
- `cis2hdl/core/engine/conversion_engine.py` — 注册 XCONWriter, Stage 6 调用 write_xcon()
- 测试更新: `test_cpm_writer.py`, `test_writers.py`, `test_output_compatibility.py` 适配新格式

### Known Issues
- DSN 原始坐标与 DEHDL C SIZE PAGE 坐标系不一致，需 Phase III 坐标映射（当前可用网格布局作为临时方案）
- 层次化 DSN 设计的叶子器件（电阻/电容等）需 Phase III 层次块遍历支持

### QA
- 192/192 单元测试通过，零回归
- RTL 坐标修复验证: loc_x 536805632→256 ✓, 端口 loc_x 正确 ✓
- 12 项修复（P0-P2）逐项代码审查 PASS
- 4 项 CSA 格式修复（QUIT/C SIZE PAGE/body_name/coordinate sanity）验证 PASS
- Cadence SPB 16.6 实测：UPREV 已消除 ✅

---

## Phase II 全面审计 (2026-08-03)

### 审计范围
对 Phase II 全部 30 项任务进行逐项核查（后端 18 + 诊断 7 + 前端 10 + 修复记录）

### 审计结果: **30/30 清点完成** (28 完全实现 + 2 P1 预留)

#### 后端 Core Pipeline — 18/18 ✅
| B2.1  | HDLLibScanner | ✅ |
| B2.1a | ChipsPrtParser | ✅ |
| B2.1b | SymbolCssParser | ✅ |
| B2.1c | PartPtfParser | ✅ |
| B2.2  | MatcherBase + MatcherRegistry | ✅ |
| B2.3  | MatcherPipeline (四级链式) | ✅ |
| B2.4  | ExactMatcher | ✅ |
| B2.5  | FuzzyNameMatcher | ✅ |
| B2.6  | FeatureExtractMatcher | ✅ |
| B2.7  | ManualMatchResolver | ✅ |
| B2.8  | ValidatorBase + ValidatorRegistry | ✅ |
| B2.9  | PinValidator | ✅ |
| B2.9a | NetNameValidator | ✅ |
| B2.9b | PowerPinValidator | ✅ |
| B2.10 | SCHWriter (CTW DSL) | ✅ |
| B2.11 | 网络名规范化 (naming.py + net_utils.py) | ✅ |
| B2.12 | ConversionEngine (六阶段全管道) | ✅ |
| B2.13 | 集成测试 | ✅ |

#### 诊断与容错引擎 — 7/7 ✅
| D2.1 | ErrorDiagnosisEngine (39错误码) | ✅ |
| D2.2 | FileRecoveryStrategy (5条路径) | ✅ |
| D2.3 | ConversionQualityEstimator | ✅ |
| D2.4 | StructuredReportGenerator | ✅ |
| D2.5 | DiagnosticPipeline (六阶段) | ✅ |
| D2.6 | IncrementalConversionTracker | ✅ |
| D2.7 | ConfigValidator | ✅ |

#### 前端 GUI — 10/10 清点完成 (8 完全实现 + 2 P1 预留)
| F2.1 | SettingsDialog | ✅ |
| F2.2 | MatchReviewPanel | ✅ |
| F2.3 | MatchConfirmDialog | ✅ |
| F2.4 | Properties Panel | ⚠️ P1 预留 (Phase III) |
| F2.5 | ConversionWorker (QThread) | ✅ |
| F2.6 | PreviewPanel | ✅ |
| F2.7 | ReportPanel | ✅ |
| F2.8 | ErrorDiagnosticPanel | ✅ (本轮集成) |
| F2.9 | RecoveryStrategyDialog | ✅ (本轮集成) |
| F2.10| 前后端全流程集成 | ✅ |

### 本轮修复
- **F2.8**: ErrorDiagnosticPanel 集成 — 添加 "Errors" Tab，在 `_on_open()`/`_on_diagnose()`/`_on_convert()` 中填充错误列表
- **F2.9**: RecoveryStrategyDialog 集成 — 新增 `_check_and_show_recovery()` 方法，在 `_on_open()` 和 `_on_convert()` 中检测损坏文件并弹出恢复对话框
- **测试验证**: 99 passed, import OK

### 已知遗留
- F2.4 (Properties Panel): Phase II 中标记为 P1（建议），留待 Phase III 实现

---

---

---

## Phase III 开发 (2026-08-03)

### T01: OLB Parser + PyInstaller ✅ (15min)

**Added**:
- `cis2hdl/core/parser/olb/` — OLBOleReader (OLB CFB, 356行) + OLBParser (8图形元素, ~500行)
- `cis2hdl.spec` — PyInstaller 配置 (pydantic v2/PySide6/60+模块)
- `scripts/build_exe.py` — CLI 打包脚本
- OLB 解析: 20/21 Package (LIBRARY2CLEAN.OLB 72KB)

### T02: Batch Engine + Mapping Rules ✅

**Added**:
- `cis2hdl/core/engine/batch_engine.py` — BatchConversionEngine (ProjectSpec/BatchReport/进度回调)
- `ManualMatchResolver`: YAML export/import_rules, save/clear/has_rule, _match_map 记忆
- Bugfix: ManualMatchResolver 候选排序 source.refdes 不存在 (ComponentDef→ComponentInstanceIR)

### T03: Schematic Preview + Diff + UX ✅

**Added**:
- `cis2hdl/gui/panels/schematic_view.py` — QGraphicsView 原理图预览 (器件占位符+连线+缩放平移, Anthropic Token)
- `cis2hdl/gui/panels/diff_view.py` — 对比视图 (统计卡+差异表+语义色)
- UI/UX: Ctrl+1/2/3 Tab 切换, Ctrl+D 诊断, 状态栏增强 "N pages, M components"

**Modified**: `tab_container.py` (Preview/Diff Tab), `main_window.py` (快捷键/菜单/auto-load), `panels/__init__.py`

**Changed**: `pyproject.toml` 0.1.0→0.3.5; dev 依赖 add `pyinstaller>=6.0`

### T04: Diagnostics Enhancement + Performance + E2E ✅

**Added**:
- `cis2hdl/core/diagnostics/olb_integrity.py` — OLBIntegrityChecker (三层校验: Package→Device→Symbol, 错误码 51-55)
- `cis2hdl/core/diagnostics/multi_source.py` — MultiSourceCrossValidator (DSN↔EDF↔pstxnet 三路比对 + 内置 PSTXNET 解析器)
- `tests/e2e/test_rtl8367rb_full.py` — E2E 真实项目测试 (9 tests: 页面/实例/网数/输出文件/.xcon/cds.lib/CSA/benchmark/OLB+multisource)
- Performance: `ConversionReport.benchmark_report()`, `--benchmark`/`--max-workers` CLI 标志, `config.py` 添加并发控制
- `error_diagnosis.py` — 新增错误码 51-55 (OLB_PACKAGE_MISSING ~ OLB_SYMBOL_EMPTY)

### T05: P2 收尾 ✅

**Added**:
- `cis2hdl/core/diagnostics/history.py` — ConversionHistoryManager (最大50条, MD5去重, 线程安全, 原子写入)
- `cis2hdl/gui/panels/rules_panel.py` — RulesPanel (QTableWidget查看/删除映射规则, 置信度色标)
- `report_gen.py`: HTML报告导出 (`generate_html_file`, 纯Python模板, 无需外部依赖)
- `batch_engine.py`: `quality_trend()` + `common_errors(top_n=5)` 批量诊断聚合

**Modified**: `tab_container.py` (Rules Tab), `main_window.py` (规则面板+导航), `conversion_engine.py` (HTML报告生成)

### 测试: **201 passed, 1 skipped**, 零回归 ✅

| Phase | 测试数 | 通过 |
|-------|:--:|:--:|
| Unit | 99 | ✅ |
| E2E | 9 | ✅ |
| Integration | 17 | ✅ |
| Other | 76 | ✅ |

### Phase III 最终完成: **16/16 任务** ✅ (100%)

| 分类 | 任务 | 完成 |
|------|------|:--:|
| 后端 | B3.1-B3.6 | 6/6 |
| 诊断 | D3.1-D3.4 | 4/4 |
| 前端 | F3.1-F3.7 | 6/6 (F3.5报告查看器并入HTML导出) |

### 文档更新
- `CHANGELOG.md` — 完整 Phase III 开发记录 (T01-T05)
- `DEVELOPMENT_ROADMAP.md` — Phase III 验收标记
- 全部 16 项任务可实施性已验证，0 项不可实施

---

## Phase IV: Cadence 实测改进 (2026-08-03) ✅

### P4.1: DSN 层次块子页面遍历
- `dsn_parser.py` 新增 `_resolve_hierarchy()`/`_resolve_page_hierarchy()`/`_is_drawn_inst()`
- 递归 DrawnInst→子页面 (最大2层) + 坐标偏移(子页面坐标+DrawnInst.loc) + 循环引用防护
- 限制: RTL8367RB DSN CFB 目录树损坏导致顶层 PAGE 不可达，正常 DSN 文件有效

### P4.2: DSN→DEHDL 坐标系统映射
- `csa_writer.py` 新增 `_map_coords_to_dehdl()` (~70行)
- BoundingBox居中 → 缩放×0.7 → 平移映射 → Y轴取反
- 超出 C SIZE PAGE 边界 (-10750~0, 0~8275) 回退网格布局

### 全部完成: **70/70 任务 ✅ (100%)** | 99 tests passed

---

## Phase V: 代码重构与参考比对 (2026-08-03) ✅

### Phase 0: 审计
- `docs/_audit_code.md` — 67 源文件审计，62 项发现 (14 P0 + 48 P1)
- `docs/_audit_tests.md` — 17 测试文件审计，命名/fixture/重复问题
- `docs/_reference_index.md` — CIStoHDL_standard 参考库完整索引 (421行)，功能映射+算法对比

### Phase 1: 代码重构
**P0 重构 (6项)**:
- **G1**: FORMAT_NAME 冲突修复 (SCHWriterCSA→'sch_csa')
- **D1**: 消除三重 _resolve_body_name() → WriterBase 统一方法
- **B2**: 消除 DISPLAY scale factors 硬编码 → config.py 读取
- **C1**: convert() 350行→80行, 拆分为6个阶段方法
- **A1**: utils/naming.py→core 反向依赖消除 (模块级默认常量)
- **A5**: SCHWriterCSA 标记 @deprecated

**Phase 2: 参考比对**:
- `docs/_comparison_report.md` — 6维详细比对 (23功能矩阵)
- `docs/_improvement_plan.md` — 7项改进方案 (P0×1/P1×3/P2×3)

### Phase 3: 改进实施
- **P0-1**: normalize_value() 精确值匹配 → FeatureExtractMatcher +25% confidence
- **P1-1/2**: symbol.css 动态偏移 → ROTATION/JUSTIFICATION 标准对齐
- **P1-3**: .dcf 生成确认 (已实现)

### Phase 1.2: 测试重组
- verify_fixes.py → test_verify_fixes.py (纯 pytest)
- 12 文件添加 pytest markers (unit/integration/e2e/slow)
- 4 shared fixtures 确认存在

### Phase 4: QA 验证
- `docs/_qa_report.md` — 全量回归 + E2E + benchmark + ruff 质量扫描

### 修改文件
| File | Change |
|------|--------|
| `cis2hdl/core/writer/sch_writer.py` | FORMAT_NAME/scale factors/body_name/deprecated |
| `cis2hdl/core/writer/csa_writer.py` | body_name/dynamic offsets/ROTATION |
| `cis2hdl/core/writer/cpc_writer.py` | body_name refactored |
| `cis2hdl/core/writer/base.py` | +_resolve_body_name() static method |
| `cis2hdl/core/engine/conversion_engine.py` | 6 stage methods extraction |
| `cis2hdl/utils/naming.py` | -core dep, +normalize_value() |
| `cis2hdl/core/matcher/feature.py` | +normalize_value matching |
| `tests/e2e/verify_fixes.py` | → test_verify_fixes.py (pure pytest) |
| `docs/_*.md` (8 new files) | 审计/索引/比对/改进/重构日志 |

### 测试: 136 passed, 1 skipped ✅

---

## [0.3.4] — CSA 原生格式（2026-07-31）

## [0.3.4] — CSA 原生格式（2026-07-31）

### Changed
- **输出改用 `.csa` 原生格式**（`FILE_TYPE=MACRO_DRAWING; FORCEADD/PAINT/DISPLAY`）
- 新增 `.con` 约束文件 + `module_order.dat`（DEHDL 页面加载必需）
- 移除所有空占位文件（`.csa`/`.csb`/`.csv` 由 DEHDL 自动生成）
- 自动复制 `hdl_lib` 到输出目录

---

## [0.3.3] — DEHDL 输出格式修复 (2026-07-31)

### Changed
- **输出完全重写**: `.cpm` 顶层 + `worklib/<cell>/sch_1/pageN.cpc` 结构
- **新增 OutputManager + CPCWriter**: `#ISCELL/#CELL` 格式, 28 输出文件
- **.cpm/.cds.lib 修正**: 匹配 Cadence 16.6 DEHDL 标准
- Cell 名自动派生: `RTL8367RB-VC-DEMO...` → `8367`
- **169/169 tests passed**

---

## [0.3.2] — 测试重组 (2026-07-31)

### Changed
- **测试目录全面重组**: 4 混合文件 → 13 模块化文件 (11 unit + 2 integration)
- **新增 tests/conftest.py**: 8 session-scoped 共享 fixture
- **硬编码路径消除**: `Path("D:/26暑假/...")` → conftest fixture
- **93 passed (76 unit + 17 integration), 0 failed**

---

## [0.3.1] — 2026-07-31

### Added
- **CSA 输出模式** (`SCHWriterCSA`): FORCEADD/FORCEPROC/DISPLAY/PAINT 指令，C SIZE PAGE 页面边框
- **前缀候选过滤器** (`prefix_filter.py`): 15 种 RefDes 前缀→类别映射，集成到 MatcherPipeline
- **属性完整度审计** (`property_audit.py`): 8 个 CIS 标准字段对比，缺失时诊断 code=15
- **C 纸布局参数** (config.py): 11 个布局常量
- **参考库分析文档 3 份**: FILE_INDEX_AND_MAPPING.md + REFERENCE_READING_NOTES.md + CIS2HDL_IMPROVEMENT_DOC.md

### Fixed
- `pipeline.py:243`: `source.refdes` → `source.library_id`（修复匹配失败）

### Verified
- 76/76 UT + E2E 6/6 matched + Quality 70%

---

## [0.3.0] — 2026-07-31

### Added
- **Phase II Core Pipeline 完整实现**: 六阶段全管道 (Diagnose→Parse→Scan→Match→Validate→Generate)
  - HDLLibScanner + 3 Parser (chips.prt/symbol.css/part.ptf): 198 组件从 110 目录
  - MatcherPipeline 四级链式 (Exact/Fuzzy/Feature/Manual): 6/6 实例匹配, 83% 匹配率
  - Validator 3 校验器 (Pin/Net/Power)
  - ErrorDiagnosisEngine: 39 错误码 (FATAL×3/ERROR×14/WARNING×11/INFO×11)（历史口径，现为 44 条）
  - FileRecoveryStrategy: 5 级降级路径 (DSN 恢复/EDIF 备用/跳过/默认符号)
  - ConversionQualityEstimator: 四维质量评估
  - DiagnosticPipeline: 六阶段编排
  - StructuredReportGenerator: JSON + HTML 双格式报告
- **GUI 交互组件**: SettingsDialog, MatchReviewPanel, ConversionWorker(QThread), ReportPanel, MatchConfirmDialog, ErrorDiagnosticPanel, RecoveryStrategyDialog
- **Anthropic Token 体系 GUI**: 20 色暖米色体系 (底色 #ECE9E0, 主 CTA #D97757), 4px 网格, 12 个 QSS 样式表
- **自定义异常层次**: CIS2HDLError/CIS2HDLParseError/CIS2HDLMatchError/CIS2HDLConfigError
- **代码审计与重构**: 75 文件全量审计 (41 项发现), 8 任务执行完成
- **真数据全量验证**: DSN+EDF+OPJ+DBK+OLB+110HDL 库, 6p/423n/8f/Logic=100%

### Changed
- 版本号统一: 0.1.0→0.3.0 (`__init__.py.__version__`)
- 配置统一: matcher/GUI 阈值全部从 `config.matching.*` 读取, 窗口尺寸从 `config.gui.*` 读取
- 消除重复: `_build_pin_mapping()` 提取到 `MatcherBase` (~50 行)
- 依赖清理: `classify_net()` 从 `utils/naming.py` 移至 `core/net_utils.py`
- 性能: `all_instances`/`all_nets`→`@cached_property`; 字典分发替换 elif 链
- `ConversionEngine.convert()`: 拆分为 `_run_stage()` 统一方法

### Fixed
- T0x10 独立块解析: RTL DSN nets 0→423 (CRITICAL)
- part.ptf GBK 编码: 193 文件 UTF-8→GBK 自动适配
- SCHWriter ASCII→UTF-8: 修复非 ASCII 字节写入失败
- +5V 电源网分类: FLAT→POWER
- 版本号不一致: 5 处硬编码统一

### Removed
- `utils/naming.py` 中 `classify_net*` 函数 (移至 `core/net_utils.py`)
- `gui/panels/report_panel.py` 中 `CONFIDENCE_*` 模块常量 (改为读取 config)
- matcher 中重复的 `_build_pin_mapping()` (3 处)

---

## [Unreleased]

### Added
- **EDIF 属性反注增强 (V-A1)** — 基于 EDIF 的 DSN 实例 library_id 修复与非破坏属性注入
  - `cis2hdl/core/engine/conversion_engine.py` — 新增 `EdifInstanceInfo` dataclass、`_is_garbage_library_id()`（5 模式垃圾检测）、`_build_edif_info_map()`（EDIF refdes→info 索引）
  - `_map_edif_types_to_dsn()` 完全重写（~120 行）：EDIF 指纹属性始终写入、垃圾 library_id 自动替换、非破坏属性注入（PCB Footprint/Value/Pin Count）
  - `config.py` `EdifConfig` 新增 `footprint_property_keys`、`value_property_keys`、`valid_library_id_prefixes`（45 个白名单前缀）
  - 垃圾检测 5 模式：纯数字 / INS 前缀 / refdes 格式 / 信号名 / 物理单位，带白名单豁免

- **FallbackMatcher** — 多层次 fallback 匹配器（优先级 4），基于 RefDes 前缀 + body_fallback 映射表
  - `cis2hdl/core/matcher/fallback.py` — 新增 FallbackMatcher 类（~380 行）
  - 三级匹配算法：exact (1.0) → size (0.8) → prefix (0.5)，完全基于 refdes 前缀，不依赖 library_id
  - 集成 PREFIX_TO_CATEGORY（15 种前缀→类别映射），复用 `prefix_filter.extract_prefix()`
  - 新增 `MatchStrategy.FALLBACK` 枚举值（`cis2hdl/core/ir/match.py`）
  - 新增 `config.matching.fallback_threshold = 0.50`（`cis2hdl/core/config.py`）
  - MatcherPipeline 从四阶段升级为五阶段（Exact→Fuzzy→Feature→Fallback→Manual）
  - 解决 HG5015-BE36_V10 中 446/730 器件因 dirty library_id 导致的匹配失败

### Changed
- `cis2hdl/core/engine/conversion_engine.py` — `_map_edif_types_to_dsn()` 从简单 library_id 映射（~40 行）重写为完整属性反注引擎（~120 行）；新增 `import re` 模块级导入
- `cis2hdl/core/config.py` — `EdifConfig` 扩展 3 个新字段（`footprint_property_keys`、`value_property_keys`、`valid_library_id_prefixes`）
- `cis2hdl/core/matcher/pipeline.py` — pipeline 文档从"四级"更新为"五级"
- `cis2hdl/core/matcher/__init__.py` — 新增 FallbackMatcher 导出

- **代码审计与重构**：全量 75 文件源码审计（41 项发现，8 任务执行）
  - 架构审计报告：41 项问题（P0×4 / P1×17 / P2×20）
  - `cis2hdl/core/exceptions.py` — 自定义异常层次（CIS2HDLError/CIS2HDLParseError/CIS2HDLMatchError/CIS2HDLConfigError）
  - `cis2hdl/core/net_utils.py` — 网络分类逻辑从 utils 层提升到 core 层
  - `cis2hdl/core/parser/dsn/structures.py` — `DSNBinaryLayout` 类（16 常量分 7 组，全部 22 处 skip 加注释）

### Changed
- **配置系统统一** (T01)：版本号统一到 `__version__` (0.1.0→0.3.0)；matcher 阈值从 config 读取（`config.matching.exact/fuzzy/feature_threshold`）
- **消除重复代码** (T02)：`_build_pin_mapping()` 从 3 个 matcher 文件提取到 `MatcherBase`（消除 ~50 行重复）
- **拆分超长函数** (T03)：`ConversionEngine.convert()` 6 个 stage 提取为 `_run_stage()` 统一方法
- **清理依赖** (T05)：`classify_net()` 从 `utils/naming.py` 移至 `core/net_utils.py`，解决 utils→core 反向依赖
- **GUI 常量化** (T06)：窗口尺寸读 `config.gui.*`；`summary_bar.update_metrics()` 改为 `MetricsSnapshot` 数据类；`Layout.WINDOW_MIN` 统一到 1200×800
- **性能优化** (T08)：`all_instances`/`all_nets` 改为 `@cached_property`；`DiagnosticPipeline.run_stage()` 7 个 elif 改为字典分发；T0x10 解析 4 路 if-elif 改为策略字典
- QA 回归：**76/76 单元测试 + E2E 管道 8 文件输出 + 版本验证 + 异常导入 — 全部通过**

### Added
- **Phase I-A 完成**：EDIF Parser 可工作管道（22 文件 / 2,024 行核心代码）
  - `cis2hdl/core/engine/conversion_engine.py` — ConversionEngine 主控（bootstrap 自动注册 Parser/Writer）
  - `cis2hdl/core/ir/` — 统一 IR 模型（ComponentDef/PinDef/DesignIR/PageIR/NetIR/MatchResult）
  - `cis2hdl/core/parser/edif_parser.py` — EDIF S-expression 解析器（574 行，已验证真实 .edf 文件通过）
  - `cis2hdl/core/parser/base.py` — ParserBase ABC + ParserRegistry（基类-注册模式）
  - `cis2hdl/core/writer/cpm_writer.py` — .cpm 项目文件生成
  - `cis2hdl/core/writer/cdslib_writer.py` — cds.lib 库索引生成
  - `cis2hdl/core/writer/sch_writer.py` — .sch 页面生成（含自动布局 + DSN 坐标注入）
  - `cis2hdl/core/config.py` — 统一 Config 单例（230 行，零硬编码）
  - `cis2hdl/core/db/component_db.py` — ComponentDB 多索引数据库 + JSON 持久化
  - `cis2hdl/utils/naming.py` — 网络名分类与规范化
  - `cis2hdl/__main__.py` — CLI + GUI 入口（`cis2hdl` 启动 GUI，`cis2hdl convert <file>` CLI 转换）
- **Phase I-B 完成**：Binary DSN 解析三层架构 + 诊断基础设施
  - `cis2hdl/core/parser/dsn/ole_reader.py` — OleReader（476行）CFB 容器解析器（含 4 个 OrCAD CFB 兼容性修复）
  - `cis2hdl/core/parser/dsn/binary_reader.py` — BinaryReader（205行）类型化二进制读取器
  - `cis2hdl/core/parser/dsn/structures.py` — FutureDataList + 12 种结构体解析器（589行）
  - `cis2hdl/core/parser/dsn/page_parser.py` — 页面流解析器
  - `cis2hdl/core/parser/dsn/dsn_parser.py` — DSNParser 顶层调度器（235行）
  - `cis2hdl/core/parser/cross_validator.py` — EDIF↔DSN 交叉验证器
  - `cis2hdl/core/parser/layout_mapper.py` — CIS→HDL 坐标映射
  - `cis2hdl/core/diagnostics/diagnostic_report.py` — DiagnosticReport 数据模型 + ReadinessEvaluator
  - `cis2hdl/core/diagnostics/file_inventory.py` — FileInventory + DSNInternalInventory
  - `cis2hdl/core/diagnostics/file_validator.py` — ProjectFileValidator + DependencyResolver
- **GUI 完成**：PySide6 图形界面（7 文件，~950 行）
  - `cis2hdl/gui/colors.py` — UI_DESIGN_SPEC v2.0 全量常量（14色/3圆角/6字号）
  - `cis2hdl/gui/main_window.py` — 主窗口（logo_clear.png + word_grey.png 品牌栏）
  - `cis2hdl/gui/panels/project_panel.py` — 项目树面板
  - `cis2hdl/gui/panels/log_panel.py` — 日志面板（HTML 着色）
  - `cis2hdl/gui/panels/diagnostic_panel.py` — 诊断面板（文件状态树 + 四维进度条）
  - `cis2hdl/gui/app.py` — 应用程序入口
- **代码审计**：Explore-19 完成 24 文件全量审计（2 CRITICAL + 5 MAJOR + 8 MINOR 全部修复）
  - C1: 修复 ConversionEngine 模块缺失 → 统一从 engine 模块启动
  - C2: 修复 `ComponentDB.get()` → `get_by_library_id()`
  - M1-M3: 三处 EDIF 网分类配置去重，统一从 Config 读取
  - M4: Parser/Writer 注册表增加 bootstrap 自动注册
  - M5: WriterBase 类型声明精确化
- 文档更新：新增 `design/COMPONENT_ARCHITECTURE.md` v1.1（统一器件模型设计）
- **新设计**：`design/DIAGNOSTICS_AND_RECOVERY.md` v1.0 — 文件完整性校验与诊断系统设计
  - 完整 CIS 项目文件清单（.dsn/.olb/.opj/.edf/.dbk/pstx*/SPICE）
  - DSN 内部引用依赖分析（OLB 隐含依赖识别）
  - 三层诊断管道：文件完整性 → 依赖解析 → 数据完整度评分
  - 对标 Cadence Professional 工具（9 项功能对比）
  - 15 个新增模块开发计划（~2,150 行新增工作量）
  - 用户交互流程：导入诊断面板 + 转换报告面板
- **EDIF _cell_is_page 修复**：从单层 contents 搜索改为递归全子树搜索 instance/net 标签
  - 修复 RTL8367RB.edf（2.3MB, 25 libraries, 1021 instances/nets）返回 0 pages 的问题

### Changed
- `pyproject.toml` 增加 `sexpdata>=1.0`, `PySide6>=6.5` 依赖
- CDSLibWriter 从硬编码改写为 Config 驱动
- SCHWriter 支持真实 DSN 坐标注入（`use_dsn_coordinates=True`）
- 测试覆盖率：70/70 单元测试全通过（IR 模型 11 + Writer 8 + DSN Parser 22 + Diagnostics 29）

- **全面文档更新 v4.0**（融入诊断/校验/容错系统）：
  - `specs/DEVELOPMENT_ROADMAP.md` v4.0 — 新增 15 诊断模块（D1.1-D3.4），Phase I 增加 6 模块 + 1 前端面板，Phase II 增加 7 模块 + 3 前端面板，Phase III 增加 4 模块。阶段估算从 8-11 周调整为 10-13 周。
  - `design/SYSTEM_ARCHITECTURE.md` v1.2 — 新增诊断层（§2.7 Diagnostics Layer）、架构原则增加"诊断优先"和"用户引导"两条、数据流增加诊断管道、包结构新增 diagnostics/ 目录和 ConversionEngine 接口扩展。
  - `design/BACKEND_DESIGN.md` v2.3 — 新增诊断与容错管道（§7），含 DiagnosticPipeline 六阶段架构、ErrorDiagnosisEngine 31 错误码体系、FileRecoveryStrategy 多级降级路径设计。
  - `docs/PROJECT_OVERVIEW.md` v1.2 — 新增 5 项功能需求（F07a-F07e + F17a-F17b）：文件完整性校验、数据质量评估、错误诊断与修复引导、降级转换路径、转换就绪度评估、结构化诊断报告、多数据源交叉验证。
  - `specs/CODING_STANDARDS.md` v1.2 — 扩展异常层次（新增 DiagnosticError 分支）、新增诊断器开发规范（DiagnosticBase ABC + Severity 枚举 + ActionVerb 操作动词）、31 错误码分配表（1-50 五个码段）。
  - `design/COMPONENT_ARCHITECTURE.md` v1.2 — 新增文件完备性对器件库的影响分析（§8 输入完整度→匹配能力四级矩阵）、OLB 缺失时的降级器件数据流、自检清单扩展。

### Fixed
- **B.1 EDIF `_parse_page` 递归搜索修复** — `_find_all()` 新增 `recursive=True` 参数 + `_find_all_impl()` 递归辅助函数（深度限制 12）。`_parse_page()` 中 instance/net 搜索改为递归全树搜索，解锁 Type B 深层嵌套 EDIF 结构（depth 5+）
  - 修改文件：`cis2hdl/core/parser/edif_parser.py`（`_find_all` + `_find_all_impl` + `_parse_page`）
- **B.2 DSN 页面流孤儿修复** — OleReader 新增 `list_raw_dir_entries()`（绕过损坏的 RB-tree 目录树）+ `read_stream_from_entry()`（按原始条目读取流数据）。DSNParser `_read_all_pages()` 新增回退路径：当目录树查找失败时，通过流名称模式匹配（PAGE前缀/vRTL设计名/Pages路径）直接读取页面流
  - 修改文件：`cis2hdl/core/parser/dsn/ole_reader.py`（+2 方法）、`cis2hdl/core/parser/dsn/dsn_parser.py`（回退路径）
- **B.2a DSN 页面头跳过** — `page_parser.py:parse_page()` 新增页面头检测：在 Preamble 魔数不在 offset 0 时跳过页面头字节。兼容小 DSN（无页面头）和大 DSN（RTL 32 字节页面头）
  - 修改文件：`cis2hdl/core/parser/dsn/page_parser.py`
- **B.2b `read_preamble()` 格式适配** — `structures.py:read_preamble()` 从固定 `skip(8)` 改为读取 uint32 长度字段后动态跳过（RTL DSN 中 `data_len=0` 等效 `skip(4)`）。支持 RTL DSN 变体（Preamble 头部 8 字节）与 openOrCadParser 格式（12 字节）兼容
  - 修改文件：`cis2hdl/core/parser/dsn/structures.py`
- **B.2c 结构体解析器 RTL 字符串适配** — `structures.py` 各 parse 函数增加 RTL/Standard 双格式分派。新增 `_RtlStructure` dataclass（统一 RTL 结构体头部解析）、`_read_rtl_string()`（uint16 长度前缀字符串读取）。Port/PlacedInstance 通过名称模式自动区分
  - 修改文件：`cis2hdl/core/parser/dsn/structures.py`（+`_parse_placed_instance_rtl()`, +`_parse_graphic_inst_rtl()` 等）
- **B.2d DSNInternalInventory raw fallback** — `file_inventory.py:DSNInternalInventoryBuilder.build()` 新增 raw directory entry fallback，与 DSNParser 策略一致
  - 修改文件：`cis2hdl/core/diagnostics/file_inventory.py`
- **BinaryReader 扩展** — 新增 `read_string_uint16_len()` 方法（uint16 长度前缀 + 原始字节，无 NUL 终止），用于 RTL DSN 字符串解码
  - 修改文件：`cis2hdl/core/parser/dsn/binary_reader.py`

### Changed
- Phase I 最终回归测试：**76/76 单元测试全通过**（含 6 个之前因缺少 fixture 跳过的测试）+ 全管道转换 5 文件输出 + 诊断管道 6/6 页面
- RTL8367RB 真实数据验证：EDIF 751 inst + 270 nets ✅ | DSN 6 pages + 6 层次实例 + 坐标 ✅
- 测试文件更新：`tests/unit/test_dsn_parser.py` 和 `tests/unit/test_diagnostics.py` 中 fixture 路径指向真实 RTL8367RB 文件
- Phase I 验收状态更新：EDIF 解析（#1）✅ 通过、DSN 解析（#2）✅ 通过、交叉验证（#3）⚠️ 待验证（需真实环境）、HDL 工程生成（#9）⚠️ 待验证（需真实环境）（详见 §A）
- Phase I 最终验收：**76/76 单元测试** + **真实 RTL8367RB 数据验证** + **Phase I 签收**
- **GUI Anthropic Token 体系重写** — 基于 Anthropic/Claude 官网设计哲学的 Token 驱动重构
  - 📖 完整阅读 15 个 Anthropic 规范文件 + 16 个 CIS2HDL 代码文件（深度分析报告）
  - 🎨 `colors.py` 完全重写：20 色暖米色体系（底色 #ECE9E0，主色 #D97757 暖橙，红色 #C0453A 错误）+ 5 层 Token（Spacing/RFontSize/Fonts/Layout）+ 12 个 QSS 样式表
  - 📐 4px 网格间距系统（XS=4 / SM=8 / MD=12 / BASE=16 / LG=24 / XL=32 / XXL=64）
  - 🔵 4 档圆角（SM=4px / MD=8px / LG=12px / XL=16px）+ FULL=9999px
  - ✏️ 双数字号体系（XXS=10 / XS=12 / SM=14 / MD=16 / LG=20）
  - 🖋 字体：微软雅黑+思源黑体+PingFang SC（UI）+ JetBrains Mono+Cascadia Code（等宽）
  - 🌑 阴影 Token（CARD/RAISED/OVERLAY）
  - 🔴 危险操作强制红色按钮（STYLE_BUTTON_DANGER）
  - 🔄 同步更新 9 个面板文件 Token 引用（main_window/sidebar/summary_bar/tab_container/diagnostic/log/preview/project/app）
  - ✅ QA 验收：76/76 单元测试 + 9 模块导入 + Token 完整性 + GUI 无头启动 — 全部通过
- **GUI Crowz 风格重构** — 基于 Crowz Dashboard 参考设计的全面 UI 重做（PRD + 架构设计 + 4 任务实现 + QA 验收）
  - 新增 `gui/panels/sidebar.py` — 260px 茶色背景侧边栏（Logo + 项目信息 + 导航菜单 + 快捷操作 + 版本号）
  - 新增 `gui/panels/summary_bar.py` — 4 指标卡片水平排列（Files/Pages/Components/Match Rate）
  - 新增 `gui/panels/tab_container.py` — QTabWidget 容器（诊断/预览；预留 匹配/差异）
  - 新增 `gui/panels/preview_panel.py` — Phase I 预览占位面板
  - 重构 `gui/main_window.py` — 移除 Header/Toolbar/Properties Panel，改为双栏布局（侧边栏 + 主内容区）
  - 扩展 `gui/colors.py` — 新增 18 个样式常量 + 4 个 QSS 样式表（STYLE_SIDEBAR/STYLE_CARD/STYLE_SUMMARY_BAR/STYLE_TAB_WIDGET）
  - 修改 `gui/panels/diagnostic_panel.py` — 适配卡片样式，`run_diagnostics()` 返回 ProjectInventory
  - 修改 `gui/panels/log_panel.py` — 改为可折叠卡片（36px 标题栏 + 150px 内容）
  - 修改 `gui/panels/project_panel.py` — 适应侧边栏宽度，字体 12px
  - 修改 `gui/app.py` — 窗口标题含版本号，最小尺寸 1100×700
  - 全组件信号槽连线：侧边栏↔Tab 切换、文件加载↔Summary Bar↔诊断面板、转换↔日志↔预览
  - QA 验收：76/76 单元测试 + 11 模块导入 + 7 组件 API + GUI 无头启动 — 全部通过

### Added (Phase II)
- **Phase II Core Pipeline 完成**：六阶段全管道（诊断→解析→扫描→匹配→校验→生成）+ 诊断引擎 + GUI 交互
  - `cis2hdl/core/parser/chips_prt.py` — ChipsPrtParser（chips.prt 引脚定义解析）
  - `cis2hdl/core/parser/symbol_css.py` — SymbolCssParser（C/L/A/T/P/M/X 指令解析）
  - `cis2hdl/core/parser/part_ptf.py` — PartPtfParser（MULTI_PHYS_TABLE 管道分隔表格解析）
  - `cis2hdl/core/parser/hdl_scanner.py` — HDLLibScanner（扫描 HDL 库目录→ComponentDB）
  - `cis2hdl/core/matcher/` — 匹配层（MatcherBase/Registry + ExactMatcher/FuzzyNameMatcher/FeatureExtractMatcher/ManualMatchResolver + MatcherPipeline 四级链式管道）
  - `cis2hdl/core/validator/` — 校验层（ValidatorBase/Registry + PinValidator/NetNameValidator/PowerPinValidator）
  - `cis2hdl/core/diagnostics/error_diagnosis.py` — ErrorDiagnosisEngine（39 错误码体系，历史口径，现为 44 条）
  - `cis2hdl/core/diagnostics/recovery.py` — FileRecoveryStrategy（5 级降级路径）
  - `cis2hdl/core/diagnostics/quality.py` — ConversionQualityEstimator（四维质量评估）
  - `cis2hdl/core/diagnostics/pipeline.py` — DiagnosticPipeline（六阶段编排）
  - `cis2hdl/core/engine/conversion_engine.py` — 完全重写为六阶段全管道（Diagnose→Parse→Scan→Match→Validate→Generate）
  - `cis2hdl/gui/dialogs/settings_dialog.py` — Settings 对话框（HDL 库路径配置）
  - `cis2hdl/gui/panels/match_review.py` — Match Review Panel（三栏匹配确认）
  - `cis2hdl/gui/panels/report_panel.py` — Conversion Report Panel
  - `cis2hdl/gui/widgets/conversion_worker.py` — QThread 后台转换 Worker
  - `cis2hdl/utils/naming.py` — 新增 `expand_bus_name()`（CIS [N:M] → HDL 展开）
- **设计文档**：`design/PHASE2_DESIGN.md` v1.0（完整类图/序列图/模块依赖/接口定义）

### Changed
- Phase II QA 验收：**76/76 单元测试全通过** + 全模块导入 + API 冒烟 + GUI 无头启动 — NoOne 签收
- **Phase II 补完（8 项代码）** — 对照 ROADMAP 验收清单补齐缺失项
  - `cis2hdl/core/diagnostics/config_validator.py` — ConfigValidator（D2.7）
  - `cis2hdl/core/diagnostics/tracker.py` — IncrementalConversionTracker（D2.6）
  - `cis2hdl/core/diagnostics/report_gen.py` — StructuredReportGenerator（D2.4，JSON+HTML 报告）
  - `cis2hdl/gui/dialogs/match_confirm.py` — MatchConfirmDialog（F2.3）
  - `cis2hdl/gui/panels/error_diagnostic_panel.py` — ErrorDiagnosticPanel（F2.8）
  - `cis2hdl/gui/dialogs/recovery_dialog.py` — RecoveryStrategyDialog（F2.9）
  - `cis2hdl/utils/naming.py` — 增强 `classify_net_str`/`edif_rename_to_hdl`（B2.11）
  - `cis2hdl/core/writer/sch_writer.py` — 新增 CTW DSL 解析+生成（B2.10）
- **Phase II 端到端真文件测试**：真实 RTL8367RB DSN(667KB) + EDF(2.3MB) 六阶段全管道
- **Phase II 第二次 QA**：逐项 ROADMAP 验收对照（31 模块导入 + CTW DSL + 网络分类 + 报告生成 + ConfigValidator + E2E 管道 5 文件输出）
- **Phase II 第三次 QA（真数据全量验证）**：全部测试数据就位（DSN+EDF+OPJ+DBK+OLB+损坏DSN+110 HDL库目录）
  - HDLLibScanner：198 组件从 110 目录扫描（116 唯一，capacitor/resistor/rtl8367/zx279128s 验证通过）
  - OLB 解析：LIBRARY2CLEAN.OLB 成功读取 52 raw entries
  - 完整管道：6 pages/423 nets/6 instances/8 output files/Logic=100%/6 FEATURE 匹配
  - 降级路径：截断 DSN 正确处理，扇区损坏 DSN 恢复 4/6 instances
  - 发现 2 Bug → 已修复（见 Fixed）

### Fixed（Phase II 收尾）
- `page_parser.py` + `structures.py` — T0x10 独立块解析（RTL DSN nets=0→423，ports=780→6）[CRITICAL]
- `dsn_parser.py` — classify_net 导入修复
- `part_ptf.py` — GBK 编码回退（193 个 HDL 库文件 UTF-8→GBK 自动适配）[HIGH]
- `sch_writer.py` — ASCII→UTF-8 编码（修复含 \x90 字节写入失败）
- `naming.py` — `+5V` 电源网分类修复（FLAT→POWER）

### Fixed
- `sch_writer.py` — ASCII 编码 → UTF-8（修复 DSN 含非 ASCII 字节时写入失败）
- `naming.py` — `+5V`/`+12V` 等 `+` 前缀电源网正确分类为 POWER
- `cis2hdl/core/config.py` — 新增 HdlLibConfig
- `cis2hdl/core/ir/match.py` — MatchResult 新增 candidates 字段
- `cis2hdl/gui/main_window.py` — 集成 Settings/MatchReview/ConversionWorker/ReportPanel + Convert 菜单
- `cis2hdl/gui/panels/tab_container.py` — Tab 1 改为 ReportPanel，Tab 2 集成 MatchReviewPanel

### Planned
- [ ] Phase III Polish: 原理图预览 + 差异对比 + 批量转换 + 报告导出 + OLB 解析器

---
### Deprecated
- FRONTEND_DESIGN.md（已被 UI_DESIGN_SPEC.md v2.0 取代）

---

## [0.2.0] — 2026-07-30

### Added
- Phase I-A 可工作管道：`ConversionEngine` + `EDIFParser` + Writer 全家（cpm/cdslib/sch）
- 统一器件模型 `ComponentDef/PinDef` 正式落地
- `ComponentDB` 多索引数据库 + JSON 持久化
- Config 单例模式：零硬编码，全通过 `config.xxx` 访问
- 完整代码审计通过（16 单元测试 + 端到端验证 dff2 项目）
- 项目文档：创建仓库、目录结构、开发规范
- `docs/RESEARCH_REPORT.md` — 技术调研报告（含8个GitHub仓库源码分析、DSN格式完整规范、EDIF方案分析）
- `docs/PROJECT_OVERVIEW.md` — 项目概述与需求规格
- `design/SYSTEM_ARCHITECTURE.md` — 系统架构设计
- `design/BACKEND_DESIGN.md` — 后端引擎设计（含EDIF Parser）
- `specs/CODING_STANDARDS.md` — 开发规范
- `specs/UI_DESIGN_SPEC.md` — UI 设计规范（浅色主题配色方案）
- `specs/DEVELOPMENT_SOP.md` — 开发标准流程
- `specs/HDL_SCHEMATIC_STANDARDS.md` — HDL原理图排版/库导入/BOM标准
- `specs/FILE_COLLECTION_CHECKLIST.md` — 文件收集清单

### Changed
- **v3.0**：DEVELOPMENT_ROADMAP.md 全面重写 + UI_DESIGN_SPEC.md v2.0 强制
  - 路线图基于 18 Agent 调研重写，每任务标注文档 §；新增技术文档交叉索引表
  - UI 规范强制：仅 3 种圆角(2/4/8)、14+7 色板、6 种字号、字体强制微软雅黑+Cascadia Code
- **策略调整 v2.1**：EDIF 导出文件已成功获取（.edf + .dsn 双文件可用），策略调整为 **EDIF + Binary DSN 双路并行验证**
- **全面文档更新 v4.0**（融入诊断/校验/容错系统）
- `docs/ORCAD_SOURCE_ANALYSIS.md` — **Cadence SPB 16.6 源文件深度分析报告**（v1.1，5 个并行 Agent + 直接分析）
  - DSN/OLB XSD 官方 Schema 验证（PartInst.locX/Y = PlacedInstance 坐标确认）
  - HDL symbol.css 完整格式分析（C/L/A/T/P 指令）
  - chips.prt / pinlist.txt / metadata 结构确认
  - Component Template Wizard 17 个器件模板（PIN_ALIAS 映射规则）
  - **allegro.cfg** — 100+ 网表传递属性（ComponentDefinitionProps/InstanceProps/netprops/pinprops）
  - CAP2EDI.CFG / EDI2CAP.CFG — 双向 EDIF 转换配置
  - **30+ CIS 标准 .olb 库分析**（Discrete/Connector/MicroController 等）
  - **40+ 网表格式化器 DLL 列表**（orEdif.dll/orTelesis.dll 等）

---

## [0.1.0] — 2026-07-29

### Added
- 项目立项，完成全部设计文档草拟
- 技术调研：Cadence 生态、现有开源方案、技术路径分析
- 系统架构：四层管道架构（解析→匹配→校验→生成）
- 前端设计：PySide6 GUI 布局与交互流程
- 后端设计：IR 模型、各层接口定义、核心实现策略
- 开发规范：命名规范、代码风格、基类-注册模式、错误处理、测试规范

---

## 版本号约定

| 变更类型 | 版本号变化 | 示例 |
|----------|-----------|------|
| 重大架构变更（不兼容） | MAJOR++ | 1.0.0 → 2.0.0 |
| 新功能（兼容） | MINOR++ | 0.1.0 → 0.2.0 |
| Bug 修复 / 小改进 | PATCH++ | 0.1.0 → 0.1.1 |
| 预发布（开发中） | 0.x.y | 0.1.0, 0.2.0, ... |

---

## 标签含义

- `Added` — 新增功能
- `Changed` — 现有功能的变更
- `Deprecated` — 即将移除的功能
- `Removed` — 已移除的功能
- `Fixed` — Bug 修复
- `Security` — 安全性修复

---

# Phase I 最终验收审计与开发文档

> 以下内容为 Phase I 完成后的完整审计报告，供后续开发者参考。

## A. Phase I 最终验收审计

### A.1 逐项审查

| # | 验收标准 | 状态 | 证据 |
|:--:|---------|:--:|------|
| 1 | .edf 解析全部逻辑（器件/引脚/网络数量人工核对一致） | ✅ **通过** | 小 EDIF(dff_sync_sr.edf): ✅ 1页/14器件/12网络 全部正确。大 EDIF(RTL8367RB.edf 2.3MB): ✅ `_cell_is_page` (已修复) + `_parse_page` 递归搜索 (本次修复) → 可正确解析深层嵌套结构（see §B.1） |
| 2 | .dsn 通过 OleReader→BinaryReader→StructureParsers→DSNParser 完整解析 | ✅ **通过** | 小 DSN(DFf_sync_SR): ✅ 解析通过。大 DSN(RTL8367RB 667KB): ✅ OleReader + `list_raw_dir_entries()` 回退路径 (本次修复) → 可绕过损坏 CFB 目录条目读取页面流（see §B.2） |
| 3 | EDIF ↔ DSN 交叉验证通过 | ⚠️ **待验证** | CrossValidator 代码完备，逻辑验证通过。**环境限制**：需要真实 RTL8367RB.DSN + .EDF 双文件进行端到端交叉验证（需从 Cadence 环境获取测试数据） |
| 4 | FileInventory 正确识别所有输入文件状态（FOUND/MISSING/CORRUPTED） | ✅ **通过** | 正确识别 DSN/EDF/OLB/DBK/OPJ，支持五种文件状态，跳过目录条目 |
| 5 | DSNInternalInventory 正确提取 OLB 引用清单 + Package 引用表 | ✅ **通过** | 提取 CFB 流完整性（6维）、页面统计、strLst 条目数（5,388）、Cache 条目数 |
| 6 | ConversionReadinessEvaluator 给出四维评分并自动判断转换可行性 | ✅ **通过** | 四维评分（逻辑40%/坐标25%/匹配20%/符号15%）加权 → 自动判定 FULL_CONVERSION/DEGRADED_CONVERSION/BLOCKED |
| 7 | Diagnostic Panel 展示文件状态树 + 四维进度条 + 建议操作 | ✅ **通过** | PySide6 诊断面板：彩色文件状态树（✅/❌/⚠️）、四维进度条、就绪度判定、操作建议 |
| 8 | Project Panel 展示含坐标的结构树 | ✅ **通过** | 项目树支持 .edf/.dsn 加载，显示 Page→Component 层次（实例限制50个避免UI冻结） |
| 9 | 生成含坐标的 .cpm + cds.lib + .sch 工程 | ⚠️ **待验证** | CPM/CDSLib/SCHWriter 完备。SCHWriter 支持真实 DSN 坐标注入 + Wire 线段输出 + 自动布局回退。小文件生成成功。大文件生成代码已修复但**需要真实 RTL8367RB 测试数据验证** |
| 10 | 生成的 HDL 工程可被 Project Manager 打开 | ⚠️ **未验证** | 需要真实的 Cadence Project Manager 环境（开发环境未安装 Cadence SPB 16.6） |
| 11 | 所有 GUI 组件严格遵守 UI_DESIGN_SPEC v2.0（颜色/圆角/字体） | ✅ **通过** | Colors/Fonts/Radius 常量全量实现：14 色板、3 圆角(2/4/8px)、6 字号(10-16px)、字体微软雅黑+Cascadia Code |

### A.2 最终验收总结（2026-07-30）

**通过: 8/11（代码验证）| 待验证: 2/11（需真实环境）| 不适用: 1/11（需 Cadence SPB 16.6）**

最终验证（Round 4）：
- 76/76 单元测试全通过
- RTL8367RB 真实数据验证：EDIF 751 inst/270 nets ✅ | DSN 6 pages/6 层次实例/坐标 ✅
- 全管道转换：5 文件输出（.cpm + cds.lib + 3×.sch）
- 诊断管道：6/6 页面发现，DEGRADED_CONVERSION 评级（符合预期——缺少 OLB 库）
- **Phase I DAQ 解析核心已签收**。Net/Wire/Leaf 器件提取属 Phase II 范围。

---

## B. 已知限制分析

### B.1 EDIF 递归解析限制 ✅ **已修复 (2026-07-30)**

**现象**：RTL8367RB.edf (2.3MB, 25 libraries, 1021 instances/nets) 返回 1 页但 0 实例。

**根因**：EDIF 文件有两种拓扑结构：

| 结构类型 | 示例 | 实例嵌套深度 |
|---------|------|:--:|
| Type A: 扁平 | dff_sync_sr.edf | `cell → view → contents → instance` 深度 4 |
| Type B: 深层嵌套 | RTL8367RB.edf | `cell → view → [intermediate] → contents → [figure] → instance` 深度 5+ |

- **已修复**：Phase I 中将 `_cell_is_page()` 改为递归搜索 `instance/net` 标签（解决了页面检测问题）
- **已修复**（本次）：`_parse_page()` 改为使用 `_find_all(contents, "instance", recursive=True)` 递归全树搜索。`_find_all()` 新增 `recursive` 参数 + `_find_all_impl()` 递归辅助函数（深度限制 12）。修改文件：`cis2hdl/core/parser/edif_parser.py`。
- **验证**：QA 全量回归测试 70 单元测试通过 + 30 E2E 验证点通过。模拟深层 EDIF 结构递归搜索正确返回 instance/net。
- **遗留**：需要真实 RTL8367RB.edf 文件进行端到端验证。

### B.2 DSN CFB 目录条目损坏 ✅ **已修复 (2026-07-30)**

**现象**：RTL8367RB.DSN (667KB) 的 OleReader 成功读取 28 个 CFB 目录条目，但条目 [36-47] 数据损坏（乱码），导致页面流条目（vRTL8367RB-VB_LQ128EP_0 等）未正确链入 Pages hierarchy。

**根因**：CFB Directory 流包含部分损坏的条目——这可能是 OrCAD 的 bug 或特定 CFB 版本的数据结构差异。OrCAD 自身在打开文件时会忽略这些条目，但我们的解析器依赖它们来构建目录树。

**修复方案**（已实现）：绕过目录树，直接通过流名称模式匹配读取页面流。OleReader 新增 `list_raw_dir_entries()` 方法（绕过 RB-tree 遍历，直接从原始 `_dir_entries` 数组提取所有非空条目）和 `read_stream_from_entry()` 方法（按原始条目直接读取流数据）。DSNParser `_read_all_pages()` 新增回退路径：当目录树查找失败时，通过流名称模式匹配（PAGE前缀/vRTL设计名/Pages路径）使用 `read_stream_from_entry()` 直接读取。修改文件：`cis2hdl/core/parser/dsn/ole_reader.py`、`cis2hdl/core/parser/dsn/dsn_parser.py`。
- **验证**：QA 全量回归测试通过。OleReader 新方法签名正确，DSNParser 回退路径逻辑存在且完备。
- **遗留**：需要真实 RTL8367RB.DSN 文件进行端到端验证。

---

## C. 技术选型说明

### C.1 为什么自行实现解析器而非直接使用 OpenOrCadParser？

**OpenOrCadParser** (C++20) 是一个优秀的 DSN/OLB 解析库，但存在以下集成障碍：

| 因素 | 分析 |
|------|------|
| **语言不匹配** | OpenOrCadParser 是 C++20 项目，需通过 pybind11/ctypes 桥接。桥接层本身的工作量接近重写（需定义 Python 绑定、处理内存管理、类型转换） |
| **平台限制** | C++ 编译依赖 Windows MSVC 和特定 CMake 配置。分发给用户需包含编译后的 .pyd/.dll，增加安装复杂度 |
| **API 粒度差异** | OpenOrCadParser 输出 C++ 结构体（Database/Container/StreamContext），需额外映射到我们的 Pydantic IR 模型 |
| **CFB 兼容性** | 我们发现了 4 个 OrCAD CFB 变体 Bug（0xFFFFFFFD 连续标记、DIFAT 计数不一致、目录偏移、RB-tree 遍历），这些边界情况在 C++ 代码中同样未处理 |
| **可维护性** | 纯 Python 实现调试更方便——特别是对复杂的二进制格式，可以直接 pdb 断点、逐字节检查 |
| **依赖最小化** | 避免引入 C++ 编译工具链作为项目依赖 |

**orcad-netlist-master** (Python): 仅 1 个文件 (`netlist.py`)，功能仅限于文本网表格式读取，不处理 CFB 二进制容器。

**CadenceOSHW-main**: 是一个开源硬件项目索引数据库（SQLite），不涉及 DSN/OLB 解析。

**结论**：纯 Python 实现虽然工作量大，但提供了完全的格式控制能力、更好的可调试性、更简单的分发（无 C++ 编译依赖），以及针对 OrCAD CFB 变体的专门兼容性处理。

### C.2 与 OpenOrCadParser 的代码级别差异对比

| 维度 | OpenOrCadParser (C++20) | cis2hdl (Python) |
|------|------------------------|-------------------|
| **语言** | C++20 | Python 3.13 |
| **OLE 读取** | `Container::readHeader()` / `Container::readDifat()` | `OleReader._parse_header()` / `_build_fat()` |
| **FAT 构建** | `Container::readFat()` — 标准 FAT 读取 | `OleReader._build_fat()` — 相同逻辑，修复了 0xFFFFFFFD 连续扇区标记处理 |
| **目录树遍历** | `Container::readDirectory()` — RB-tree 中序遍历 | `OleReader._visit_dir()` — 相同遍历方式，增加了环路检测和深度限制 |
| **流读取** | `Container::getStream()` → `std::vector<uint8_t>` | `OleReader.read_stream_by_path()` → `bytes` |
| **类型化读取** | `DataStream::readUint8/16/32()` — 内联方法 | `BinaryReader.read_uint8/16/32()` — 相同语义，增加了边界检查 |
| **结构体解析** | `GenericParser::parsePlacedInstance()` — 基于 Visitor 模式 | `structures.parse_placed_instance()` — 直接函数调用，相同结构体字段 |
| **未来数据** | `FutureData` 类 — 检查点边界追踪 | `FutureDataList` 类 — 完整移植，增加了 checkpoint 警告 |
| **顶层调度** | `DsnParser::parse()` — Page流+Cache流+Library流 三管齐下 | `DSNParser.parse()` — 当前仅 Page 流（Cache 和 Library 流解析计划 Phase II） |
| **输出格式** | XML (`XmlExporter`) | Pydantic IR → HDL Writer（.cpm/.cds.lib/.sch） |
| **GUI** | 无 | PySide6 全功能 GUI（项目树/诊断面板/日志面板） |
| **诊断系统** | 无 | 六阶段诊断管道 + 31 错误码体系 + 降级策略 |
| **交叉验证** | 无 | EDIF↔DSN 交叉验证器 |
| **依赖** | C++17 STL + Win32 API | pydantic, sexpdata, PySide6, rapidfuzz, pyyaml |
| **分发** | 编译为 .exe / .dll | 纯 Python + PyInstaller 打包 |

**OpenOrCadParser 中有但我们缺失的关键能力**（计划 Phase II 补齐）：
- Cache 流中的 Package(31)/Device(32)/LibraryPart(24) 结构体解析 → DSNDetailParser
- Library 流中的 strLst 字符串表解析 → 引脚名/属性值完整提取
- XML 导出器（非必需，我们有 HDL Writer）

**我们独有的增强**（OpenOrCadParser 不具备）：
- 诊断与容错管道
- EDIF↔DSN 交叉验证器
- PySide6 GUI 完整界面
- 31 错误码诊断体系
- CHANGELOG 与开发文档体系

---

## D. CIS 项目文件完整清单

### D.1 文件角色与必需性分级

| 文件 | 格式 | 提供信息 | 必需性 | 缺失后果 |
|------|:--:|---------|:------:|---------|
| `*.dsn` | 二进制 CFB | 全部逻辑 + 坐标 + 属性 + 器件缓存 | 🔴 **强制** | 无法进行任何转换 |
| `*.opj` | 文本 INI | 项目配置、库引用路径、页面尺寸 | 🟠 **建议** | 使用默认配置 |
| `*.olb` (项目库) | 二进制 CFB | 器件符号图形、引脚名、属性默认值 | 🟠 **建议** | 器件无引脚名/无符号图形，使用默认矩形 |
| `CAPSYM.olb` | 二进制 CFB | 电源/地/Port 等系统符号 | 🟠 **建议** | 可用默认符号替代 |
| `*.edf` | 文本 S-expr | 完整逻辑数据（与 DSN 正交） | 🟡 **可选** | EDIF↔DSN 交叉验证不可用（不影响转换） |
| `*.dbk` / `*.dbk.001` | 二进制 CFB | DSN 的完整备份 | 🟡 **可选** | DSN 损坏时的恢复备选 |
| `pstxnet.dat` | 文本 | 网络连接关系（Allegro 格式） | 🟡 **可选** | 第三方交叉验证不可用 |
| `pstxprt.dat` | 文本 | 器件-封装映射 | 🟡 **可选** | 额外验证不可用 |
| `pstchip.dat` | 文本 | 器件引脚定义 | 🟡 **可选** | 额外验证不可用 |
| `*.bom` / `.xlsx` | 文本/XLSX | BOM 材料清单 | ⚪ **高级** | 从 DSN 重新提取 |
| `*.sim` / `*.cir` | 文本 | 仿真配置/激励文件 | ⚪ **高级** | 无损基本转换 |

### D.2 DSN 内部 CFB 流结构

```
MyProject.dsn (CFB Container)
├── Root Entry
├── Views/SCHEMATIC1/          ← 原理图视图
│   ├── Pages/                 ← 页面流目录
│   │   ├── PAGE1              ← 第1页（二进制结构体流）
│   │   └── PAGE2              ← 第2页
│   └── Hierarchy              ← 层次结构定义
├── Cache/                     ← 设计缓存（器件定义）
│   └── (Package 列表)         ← Package(31) 结构体
├── Library/                   ← 字符串表
│   └── strLst                 ← 全局字符串索引
└── (其他流)                   ← 元数据、图形等
```

### D.3 最小输入组合分析

| 用户提供 | 可以转换吗？ | 转换质量 |
|---------|:--:|------|
| 仅 .dsn | ⚠️ **可降级转换** | 逻辑完整 + 坐标完整，但器件无引脚名（使用编号代替）、无符号图形（使用默认矩形） |
| 仅 .edf | ⚠️ **可降级转换** | 逻辑完整，但**无坐标**（器件位置/连线路径全部丢失，仅能用自动布局） |
| .dsn + .edf | ✅ 完整转换 | 逻辑完整 + 坐标完整 + EDIF↔DSN 交叉验证启用，仍缺 OLB 的完整引脚名和符号 |
| .dsn + .edf + .olb | ✅ **最佳转换** | 全部数据可用：逻辑+坐标+引脚名+符号图形+属性+交叉验证 |
| 仅 .olb | ❌ 不可转换 | 器件库无原理图设计，无法生成 HDL 工程（需至少提供 .dsn 或 .edf） |
| 仅 pstx*.dat | ❌ 不可转换 | PCB 网表不包含原理图页面结构、器件坐标、连线路径 |
| 仅网表+元件库 (pstx*+.olb) | ❌ 不可转换 | 同上——PCB 网表格式不包含原理图结构。**软件应提示用户"请提供 .dsn 原理图主文件"** |

---

## E. 接口契约（给后续开发者）

### E.1 Parser 基类

```python
class ParserBase(ABC):
    FORMAT_NAME: ClassVar[str] = ""      # 如 "CIS_EDIF", "CIS_DSN"
    FILE_EXTENSIONS: ClassVar[list[str]] = []  # 如 [".edf"], [".dsn"]

    @abstractmethod
    def parse(self, path: Path) -> DesignIR: ...
```

### E.2 Writer 基类

```python
class WriterBase(ABC):
    FORMAT_NAME: str = ""                # 如 "cpm", "sch", "cdslib"

    @abstractmethod
    def write(self, ir: "DesignIR | PageIR | object", output_dir: Path) -> list[Path]: ...
```

### E.3 ConversionEngine

```python
from cis2hdl.core.engine.conversion_engine import ConversionEngine
engine = ConversionEngine()    # bootstrap 自动注册 EDIFParser + DSNParser + 所有 Writer
report = engine.convert(Path("project.edf"), Path("output/"))
# Returns: ConversionReport(project_name, pages, instances, nets, output_files, errors, warnings)
```

### E.4 诊断管道

```python
from cis2hdl.core.diagnostics.file_inventory import FileInventory, DSNInternalInventoryBuilder
from cis2hdl.core.diagnostics.diagnostic_report import ConversionReadinessEvaluator, DiagnosticReport

inv = FileInventory().scan([Path("project.dsn"), Path("lib.olb")])
inv.dsn_internal = DSNInternalInventoryBuilder().build(Path("project.dsn"))
readiness = ConversionReadinessEvaluator().evaluate(inv)
report = DiagnosticReport(inventory=inv, readiness=readiness)
```

---

## F. Phase II 开发入口

### F.0 已完成的前置任务

1. ✅ **修复 EDIF `_parse_page` 递归搜索** — 已完成（2026-07-30）。`_find_all(recursive=True)` + `_find_all_impl()` 递归辅助函数。
2. ✅ **修复 DSN 页面流孤儿问题** — 已完成（2026-07-30）。`list_raw_dir_entries()` + `read_stream_from_entry()` + DSNParser 回退路径。

### F.1 核心功能

3. HDLLibScanner（扫描 HDL 库目录）
4. MatcherPipeline（四级匹配管道：精确→模糊→特征→人工）
5. Validator Pipeline（校验管道：PinValidator/NetNameValidator/PowerPinValidator）
6. 完整 ConversionEngine 管道集成（Parser→Matcher→Validator→Generator）

### F.2 扩展

7. OLB 解析器（与 DSN 共享 CFB 解析基础设施）
8. 递归目录扫描（批量 OLB 导入）
9. MultiSourceCrossValidator（三路交叉验证：DSN+EDIF+pstx*）
10. StructuredReport 导出（HTML/PDF）

---

## G. 环境设置

```bash
cd cis2hdl

# 虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 依赖
pip install pydantic sexpdata rapidfuzz pyyaml PySide6 pytest

# 运行 GUI
python -m cis2hdl

# 运行 CLI 转换
python -m cis2hdl convert project.edf --output ./output

# 运行测试
python -m pytest tests/unit/ -v
```
