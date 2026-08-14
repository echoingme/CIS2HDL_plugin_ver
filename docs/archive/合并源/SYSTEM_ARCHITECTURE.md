# CIS2HDL 系统架构设计

> 版本: v1.1.0 | 日期: 2026-08-07 | 状态: 修订 | 更新: 匹配层改为 v2.0 两阶段架构；错误码统一为 44（旧口径 31/39）；包结构按实际代码校正；解析器章节并入 HG5015 二进制解析算法要点

---

## 1. 架构总览

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     CIS2HDL Application                     │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────┐  ┌─────────────────────────────┐ │
│  │     Frontend (GUI)     │  │    CLI Mode (optional)      │ │
│  │     PySide6 / Qt       │  │    argparse + logging       │ │
│  │  ┌───────────────────┐ │  └──────────────┬──────────────┘ │
│  │  │ Project Panel     │ │                 │                │
│  │  │ Match Review      │ │                 │                │
│  │  │ Preview / Diff    │ │                 │                │
│  │  │ Log / Report      │ │                 │                │
│  │  └───────┬───────────┘ │                 │                │
│  └──────────┼─────────────┘                 │                │
│             │           Controller Layer      │                │
│             └───────────────┬────────────────┘                │
│                             ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                   Core Engine                            │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │ │
│  │  │ Parser   │  │ Matcher  │  │ Validator│  │ Generator│ │ │
│  │  │ Layer    │─▶│ Layer    │─▶│ Layer    │─▶│ Layer    │ │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │ │
│  │       │              │              │              │      │ │
│  │       ▼              ▼              ▼              ▼      │ │
│  │  ┌──────────────────────────────────────────────────┐    │ │
│  │  │           Intermediate Data Model (IR)            │    │ │
│  │  │         Pydantic / dataclasses                    │    │ │
│  │  └──────────────────────────────────────────────────┘    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                             │                                 │
│  ┌──────────────────────────┴──────────────────────────────┐ │
│  │                   Plugin / Extension Layer               │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │ │
│  │  │ DSN      │  │ OLB      │  │ SCH      │  ...          │ │
│  │  │ Parser   │  │ Parser   │  │ Writer   │               │ │
│  │  └──────────┘  └──────────┘  └──────────┘               │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 架构设计原则

| 原则 | 说明 |
|------|------|
| **高内聚低耦合** | 每个层职责单一，层间通过明确的接口通信 |
| **基类-注册模式** | 解析器、匹配器、导出器、诊断器、版本适配器均通过注册机制扩展 |
| **管道式处理** | 数据流经诊断 → 解析 → 扫描 → 匹配 → 校验 → 生成六阶段（对应 `ConversionEngine` 的 `diagnose/parse/scan_hdl_library/match/validate/generate`），诊断贯穿全管道 |
| **中间表示解耦** | 所有层通过统一的 IR（Intermediate Representation）通信 |
| **版本适配器分离** | 目标版本（16.6）与其兼容版本（17.2/17.4）通过适配器解耦 |
| **诊断优先** | 文件完整性校验 + 依赖解析 + 数据质量评估必须先于任何转换操作执行 |
| **用户引导** | 所有错误/警告/信息必须包含可操作的建议，不静默失败 |

---

## 2. 分层设计

### 2.1 Parser Layer（解析层）

**职责**：将 CIS 二进制格式解析为标准 IR 数据模型。

```
┌──────────────────────────────────────────┐
│            Parser Registry               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ DSNParser│ │ OLBParser│ │ ...      │ │
│  └────┬─────┘ └────┬─────┘ └──────────┘ │
│       │             │                    │
│       ▼             ▼                    │
│  ParserBase(ABC)    ParserBase(ABC)     │
│  + parse() → IR     + parse() → IR      │
└──────────────────────────────────────────┘
```

**接口定义**：

```python
class ParserBase(ABC):
    """所有解析器的基类"""
    
    @abstractmethod
    def parse(self, file_path: Path) -> DesignIR:
        """解析文件，返回中间表示"""
        ...
    
    @abstractmethod
    def supported_formats(self) -> list[str]:
        """返回支持的文件扩展名列表"""
        ...
```

**已落地的解析器（core/parser/）**：

| 解析器 | 输入 | 输出 | 实现策略 |
|--------|------|------|----------|
| `EDIFParser` | `.edf` | `DesignIR` | `sexpdata` S-expression 文本解析；早期承担 Phase I-A 快速逻辑验证，后期主要承担 **pin 连接注入（Stage 5.5，`extract_pin_net_map`）** |
| `DSNParser` | `.dsn` | `DesignIR` | 纯 Python CFB 解析：OleReader → BinaryReader → StructureParsers（Phase I-B 主力） |
| `OLBParser` | `.olb` | `LibraryIR` | 与 DSN 相同的 CFB 容器解析（core/parser/olb/olb_parser.py + olb_reader.py） |
| `HDLLibScanner` | HDL 库目录 | `ComponentDB` | 扫描 `chips.prt` + `symbol.css` + `part.ptf` → 统一 ComponentDB |
| `ChipsPrtParser` | `chips.prt` | `list[PinIR]` | 纯文本解析，提取管脚名/编号/电气类型 |
| `SymbolCssParser` | `symbol.css` | `SymbolLayoutIR` | 纯文本解析，提取符号外形/管脚位置/Label位置 |
| `PartPtfParser` | `part.ptf` | `list[PartProperty]` | 纯文本解析，提取器件属性表 |
| `PstchipParser` | `pstchip.dat` | `PstchipEntry` 映射 | PST 数据源，提取 PART_NAME / JEDEC_TYPE / VALUE / pin numbers（Phase IX） |
| `PstxnetParser` | `pstxprt.dat` | refdes → primitive 映射 | PST 数据源，refdes → 器件名/层次 section/内部实例 ID（INSxxx），多行 PART_NAME 兼容 |
| `PstxnetNetlistParser` | `pstxnet.dat` | pin → net 映射 | PST 数据源，`NET_NAME` + `NODE_NAME <refdes> <pin>` 展开网络连接（Stage 5.5b 主数据源） |
| `CrossValidator` | EDIF DesignIR + DSN DesignIR | `ValidationReport` | **8 项比对**：页数/实例数/网络数/Refdes 交集/逐器件引脚数/网络连接数/网络拓扑一致性（Jaccard）/器件类型分组 |

> 注：解析器注册统一在 `core/parser/base.py` 的 `ParserRegistry` 完成，由 `ConversionEngine._bootstrap_parsers()` 引导注册。PST 三解析器（pstchip/pstxprt/pstxnet）作为辅助数据源，主要服务于匹配阶段（JEDEC/VALUE 注入）与生成阶段（pin 连接注入）。

### 2.1.1 二进制解析算法要点（HG5015 实测，2026-08-04）

> 本节为 `docs/2608041210report.md` 中 HG5015 二进制解析算法要点的正式归宿；后端实现细节见 `BACKEND_DESIGN.md §3`。

**OleReader.count_page_candidates() 回退算法**（`core/parser/dsn/ole_reader.py`）

当 CFB 树中 `Pages/` 下流条目数量不足时，DSN 页面流发现启用回退路径：扫描 raw 目录条目（不依赖 Red-Black Tree），按 4 条规则统计页面候选流：

```python
# 4 条匹配规则
1. name_upper.startswith("PAGE")
2. "VRTL" in name_upper
3. re.match(r'^\d{2,3}-', entry.name)   # "01-Cover_Page" 等
4. stream_size > 2000 且不在系统流名称中
```

回退触发条件：`len(pages) < ole.count_page_candidates()`。

**Library 流 strLst 解析**（`core/parser/dsn/library_parser.py`，约 90 行）

`parse_strlst(library_bytes) → list[str]` 逐字节算法：

```
1. skip(48)  — 跳过 header (introduction + version + timestamps)
2. text_font_len = read_uint16()
3. skip((text_font_len - 1) * 60)  — 跳过 LOGFONTA 结构体（60字节/个）
4. some_len = read_uint16()
5. skip(some_len * 2)  — 跳过 some_data
6. skip(8)  — 跳过 unknown
7. 跳过 8 个 part field strings（uint16 len + len bytes + 0x00）
8. skip(156)  — 跳过 PageSettings
9. str_lst_len = read_uint32()
10. 逐条读取：uint16 slen + slen bytes Latin-1 + 0x00
11. GBK 回退：Latin-1 结果中非可打印字符 > 20% 时，尝试 raw.decode("gbk")
```

**HG5015 实测**：5490 条 strLst 条目。

**Cache 流解析**（`core/parser/dsn/cache_parser.py`，约 320 行）

`parse_cache_stream(cache_bytes) → CacheParsedData`：

```
1. skip(4) — Cache header (0x0000 + unknown uint16)
2. 循环 parse_cache_entry() 直到 EOF
3. sequential 解析失败 → 暴力 preamble 扫描恢复

Cache Entry 格式：
  - Variable metadata (3 variants, probe detection)
  - Twin ID check (id0 vs id1, uint32×2)
  - 不匹配 → 子循环 (package names + source library paths)
  - Structure header (some_id0 + some_id1 + struct_type uint16)
  - Standard prefix chain + preamble + structure body
```

**关键陷阱**：Cache 流所有字符串使用 **uint16 长度前缀**（不是 uint32！）。`read_string_len_zero_term()`（uint32）会因 0x00 高字节截断字符串。**HG5015 实测**：39 packages / 47 components 提取到 component_db。

**RTL 格式虚假实例过滤**（`core/parser/dsn/structures.py` + `page_parser.py`）

- PlacedInstance 双格式：标准格式内联字符串（uint16 长度前缀）；RTL 格式 strLst 索引解析（uint16 值 > 200 时为 strLst 索引）
- 虚假实例过滤：`db_id == 0` 的实例跳过（HG5015 中 1001 实例 → 993 有效）
- strLst 阈值 100 → 200，NUL/控制字符检测，GBK 编码回退

**EDIF 解析**：HG5015-BE36_V10.EDF → 1 页、3023 实例、862 网络；Windows 路径反斜杠替换（`\` → `/`）避免 sexpdata 解析异常。

**MultiSourceCrossValidator**（`core/diagnostics/multi_source.py`）

- 三路比对：DSN / EDIF / PSTXNET
- 支持自动降级（pstxnet.dat 不存在时 2-source 模式）
- 内联实现引脚/网络/类型比对（避免 ValidationReport 类型适配）

### 2.2 Matcher Layer（匹配层）

**职责**：将 CIS 器件与 HDL 库器件进行匹配映射。

```
┌──────────────────────────────────────────────────────────────┐
│              Matcher Pipeline (v2.0 两阶段)                    │
│                                                               │
│  Phase 1:  TypeHypothesisGenerator                            │
│            refdes 前缀 + PST JEDEC + value 提示 + 学习先验      │
│            → 有序类型假设列表（prior_conf ∈ [0.05, 1.0]）       │
│                │                                              │
│  Phase 1.5: CandidatePoolBuilder                              │
│            按类型假设过滤 HDL 候选池，按 prior_conf 降序        │
│                │                                              │
│  Phase 2A:  PassiveMatcher（被动器件 C/R/L/D/FB/LED）          │
│            确定性规则 5 级级联（无加权评分）                     │
│            conf=1.00/0.95/0.80/0.70/0.60/0.40                 │
│                │                                              │
│  Phase 2B:  ActiveMatcher（主动器件 IC/连接器/晶振…）           │
│            类型内 5 维加权评分                                 │
│            footprint:0.30 value:0.15 jedec:0.20               │
│            pin_count:0.20 part_name:0.15                     │
│                │                                              │
│  final_conf = phase1_prior_conf × phase2_within_conf          │
│  STOP_SEARCH = 0.75 ｜ NEEDS_REVIEW = 0.40                    │
│                │                                              │
│  未达阈值 → ManualMatchResolver（GUI 人工确认，strategy=MANUAL）│
└──────────────────────────────────────────────────────────────┘
```

**接口定义**：

```python
class MatcherBase(ABC):
    """所有匹配器的基类"""
    
    @abstractmethod
    def match(self, source: ComponentIR, candidates: list[ComponentIR]) -> MatchResult:
        """尝试匹配，返回结果（含置信度）"""
        ...
    
    @abstractmethod
    def confidence_threshold(self) -> float:
        """匹配置信度阈值，低于此值进入下一阶段"""
        ...
```

**v2.0 匹配架构（已落地，core/matcher/）**：

| 阶段 | 组件 | 职责 | 关键参数 |
|:----:|------|------|---------|
| Phase 1 | `TypeHypothesisGenerator` | 生成有序类型假设（refdes 前缀 → YAML 规则 → PST 提升 → value 提示 → 学习先验） | `type_hypothesis.py`；prior ∈ [0.05, 1.0] |
| Phase 1.5 | `CandidatePoolBuilder` | 按类型假设构建 HDL 候选池 | `candidate_pool.py`；按 prior_conf 降序 |
| Phase 2A | `PassiveMatcher` | 被动器件确定性规则 5 级级联 | conf=1.00(值+尺寸双精确) / 0.95(多候选 JEDEC tiebreak) / 0.80(值精确尺寸未知) / 0.70(值精确尺寸近似) / 0.60(尺寸精确值近似) / 0.40(前缀兜底) |
| Phase 2B | `ActiveMatcher` | 主动器件类型内评分（Exact→Fuzzy→Feature→Value→Fallback 链 + 5 维加权） | footprint:0.30 / value:0.15 / jedec:0.20 / pin_count:0.20 / part_name:0.15；MIN_WITHIN_SCORE=0.50 |
| 收尾 | `ManualMatchResolver` | 自动匹配失败 → 人工确认；支持规则导入/导出（YAML） | strategy=MANUAL；规则持久化 `~/.cis2hdl/mappings.yaml` |

**v2.0 关键规则**：

- **final_conf = phase1_prior × phase2_within**：`final_conf ≥ STOP_SEARCH(0.75)` 或命中 `PASSIVE_EXACT`/固定前缀类型即提前停止搜索；全部类型池耗尽后取最优，`< NEEDS_REVIEW(0.40)` 判为 `NEEDS_REVIEW`
- **固定前缀绑定** `fixed_prefixes = {LB: ferrite_bead, LED: led, FB: ferrite_bead, TP: test_point}`；`RD → resistor`（RD 前缀重映射）
- **MultiScorer 已删除**：v2.0 移除跨类型加权评分（被证明结构上不可靠——前缀是硬约束而非软权重），改为类型池内评分
- **旧版四级管道（Exact → Fuzzy → Feature → Manual）已被 v2.0 两阶段取代**：Exact/Fuzzy/Feature 在 v2.0 中降级为 ActiveMatcher 的类型内 matcher 链；完整历史描述保留于 `BACKEND_DESIGN.md §4.3`（历史演进）

### 2.3 Validator Layer（校验层）

**职责**：校验数据完整性和转换可行性。

```
┌────────────────────────────────────────────┐
│          Validator Registry                │
│  ┌──────────────┐ ┌──────────────┐        │
│  │ PinValidator │ │ NetValidator │ ...    │
│  └──────────────┘ └──────────────┘        │
└────────────────────────────────────────────┘
```

**校验项**：

| 校验器 | 检查内容 |
|--------|----------|
| `PinNumberValidator` | 引脚编号是否在目标器件中存在 |
| `PinCountValidator` | 引脚总数是否匹配 |
| `NetNameValidator` | 网络名是否含非法字符 |
| `PowerPinValidator` | 电源引脚是否正确处理 |
| `MultiSectionValidator` | 多 Section 器件（如 74HC00）拆分正确性 |
| `DesignRuleValidator` | 单节点网络、未连接引脚等警告 |

### 2.5 Version Adapter Layer（版本适配层）【规划未实施】

> ⚠️ **规划未实施**：`core/` 下不存在 `version/` 目录，`SPB16_6Adapter/SPB17_2Adapter/SPB17_4Adapter` 尚未落地。当前版本差异由 `core/config.py` 与 writer 参数（如字体/网格/CPM 格式）间接控制，本层保留为设计意图。

**职责**：隔离 Cadence SPB 版本差异，使生成层与目标版本解耦。

```
┌──────────────────────────────────────┐
│         VersionAdapter Registry       │
│  ┌────────────┐ ┌────────────┐       │
│  │ 16.6 Adptr │ │ 17.2 Adptr │ ...   │
│  └────────────┘ └────────────┘       │
└──────────────────────────────────────┘
```

**接口定义**：

```python
class VersionAdapter(ABC):
    """版本适配器基类"""
    VERSION: ClassVar[str] = ""
    
    @abstractmethod
    def grid_size(self) -> float: ...
    @abstractmethod
    def cpm_format(self) -> str: ...
    @abstractmethod
    def font_support(self) -> str: ...
```

**已规划适配器**：

| 适配器 | 版本 | 优先级 |
|--------|:----:|:------:|
| `SPB16_6Adapter` | 16.6 | P0（主目标） |
| `SPB17_2Adapter` | 17.2 | P1 |
| `SPB17_4Adapter` | 17.4 | P2 |

### 2.6 Layout Layer（排版层）【规划未实施】

> ⚠️ **规划未实施**：`core/` 下不存在 `layout/` 目录，下表排版器均未独立落地。坐标映射职责当前由 `core/parser/layout_mapper.py`（CIS 文档坐标 → HDL 网格坐标，ConvertDocToUser 公式）与 `core/writer/csa_writer.py` 的 `_map_coords_to_dehdl()`（BoundingBox 居中缩放 ×0.7 + Y 轴翻转）承担。

**职责**：根据公司规范自动排版原理图。

| 排版器 | 功能 |
|--------|------|
| `NetNameAligner` | 网络名统一对齐到 7.5 格点 |
| `PortAligner` | Port 等间距对齐 |
| `OverlapDetector` | 标签碰撞检测与微调 |
| `GridSnapper` | 所有坐标强制对齐到网格 |
| `BOMSEQGenerator` | 根据器件类型和封装自动生成 BOM_SEQ 编码 |
| `RefDesAssigner` | 自动分配位号前缀 |

### 2.4 Writer Layer（生成层）

**职责**：将 IR 转换为 HDL 文件格式并写入磁盘。生成层实际落地于 `core/writer/`（即旧设计中的 `generator/`，该目录名已废弃）。

```
┌────────────────────────────────────────────────┐
│              Writer Registry                    │
│  ┌────────────┐ ┌────────────┐ ┌─────────────┐ │
│  │ CPMWriter  │ │ SCHWriter  │ │ CSAWriter   │ │
│  └────────────┘ └────────────┘ └─────────────┘ │
│  ┌────────────┐ ┌────────────┐ ┌─────────────┐ │
│  │ CDSLibWriter│ │ XconWriter │ │ CPCWriter   │ │
│  └────────────┘ └────────────┘ └─────────────┘ │
│  ┌────────────┐ ┌────────────┐ ┌─────────────┐ │
│  │ ScrWriter  │ │ MappingCSV │ │ OutputManager│ │
│  └────────────┘ └────────────┘ └─────────────┘ │
└────────────────────────────────────────────────┘
```

**已落地写入器（core/writer/）**：

| 写入器 | 输出 | 说明 |
|--------|------|------|
| `CPMWriter` | `.cpm` | Cadence Project Manager 工程文件 |
| `SCHWriter` | `.sch.N.M` | 原理图页面文件 |
| `CSAWriter` | `.csa` | MACRO_DRAWING 格式原理图（当前主输出，含 ADD_COMMENT/EDIT PAGE NAME） |
| `CDSLibWriter` | `cds.lib` | 库定义文件 |
| `XconWriter` | `.xcon` | 跨页连接器输出 |
| `CPCWriter` | `.cpc` | 元件/引脚约束文件 |
| `ScrWriter` | `.scr` | 脚本输出 |
| `MappingCSVWriter` | `{project}_mapping.csv` | 4 段式映射报告（概览/逐器件映射/异常/文件清单） |
| `ErrorLogger` | `{project}_errors.{html,txt}` | 转换错误日志（双格式） |
| `OutputManager` | 输出目录树 | Cadence DEHDL 目录结构编排（temp/worklib/sch_1 等） |

> 注：旧设计中规划的 `SYMWriter/PTFWriter` 未落地（符号输出由 CSAWriter 以 MACRO_DRAWING 方式承载）。写入器注册统一在 `core/writer/base.py` 的 `WriterRegistry` 完成，由 `ConversionEngine._bootstrap_writers()` 引导注册。

**接口定义**：

```python
class WriterBase(ABC):
    """所有输出器的基类"""
    
    @abstractmethod
    def write(self, ir: DesignIR, output_dir: Path) -> list[Path]:
        """将 IR 写入指定目录，返回生成的文件路径列表"""
        ...
```

---

### 2.7 Diagnostics Layer（诊断层）【新增】

**职责**：转换前的文件完整性校验 + 依赖解析 + 数据质量评估 + 转换后的结构化报告。对标 Cadence Project Manager → Check References + Packager-XL Pre-check。

```
┌───────────────────────────────────────────────────────────┐
│                Diagnostics Pipeline                        │
│                                                            │
│  Layer 1: File Integrity Check                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                  │
│  │FileExist │ │FormatChk │ │VersionChk│                   │
│  │  Checker │ │ (Magic)  │ │ (CFB ver)│                   │
│  └──────────┘ └──────────┘ └──────────┘                  │
│       ↓             ↓            ↓                         │
│─────────────────────────────────────────────────────────────│
│  Layer 2: Dependency Resolution & Cross-Reference           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │OLB Ref   │ │Hierarchy │ │OffPage   │ │Global Net│    │
│  │Resolver  │ │Check     │ │Check     │ │Check     │    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
│       ↓             ↓            ↓            ↓           │
│─────────────────────────────────────────────────────────────│
│  Layer 3: Data Completeness & Quality                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │Logic %   │ │Coord %   │ │Match %   │ │Symbol %  │    │
│  │Score     │ │Score     │ │Score     │ │Score     │    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
│       ↓             ↓            ↓            ↓           │
│  ┌──────────────────────────────────────────────────┐    │
│  │    Conversion Readiness Evaluator               │    │
│  │    综合评分 + 可操作建议 + 降级路径推荐            │    │
│  └──────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────┘
```

**已落地的诊断模块（core/diagnostics/）**：

| 模块 | 输入 | 输出 | 实现策略 |
|------|------|------|----------|
| `DiagnosticPipeline` | 输入文件集 | 六阶段诊断报告（文件清单 → 三层校验 → 依赖 → 就绪度 → 质量 → 报告） | 顺序执行 + 错误累积，任一阶段失败不阻塞后续 |
| `FileInventory` | 用户提供的文件集 | `ProjectInventory`（逐文件状态） | 魔数检测 + CFB 头部解析 + 版本检测 |
| `DSNInternalInventory` | DSN CFB 容器 | OLB 引用清单 + Package 表 + 流结构完整性 | OleReader → 目录树映射 |
| `ProjectFileValidator` | 文件集 | 错误码列表 + FILE_MISSING/BAD_FORMAT/VERSION_MISMATCH | 三层顺序检查 |
| `ConversionReadinessEvaluator` | ProjectInventory | 四维评分 + 转换可行性判断 + ActionItem 列表 | 加权评分算法 |
| `ErrorDiagnosisEngine` | 任何阶段的异常 | **44 错误码**结构化错误报告 + 修复建议（v1.1.0 权威口径；旧口径 31/39，39 漏算 OLB 51-55） | 错误分类 + 建议模板匹配；完整表见 `core/diagnostics/error_diagnosis.py` |
| `FileRecoveryStrategy` | 损坏/缺失文件信息 | 降级路径列表（每条标注数据损失） | 策略优先级排序 + 损失评估 |
| `ConversionQualityEstimator` | DesignIR + 匹配结果 | 四维质量评估报告 | 逐项统计 + 百分比计算 |
| `StructuredReportGenerator` | 全部诊断结果 | JSON 结构化报告（前端渲染为 HTML/PDF） | 模板渲染 |
| `IncrementalConversionTracker` | 转换状态 | `.cis2hdl_state.json` 断点记录 | JSON 持久化 |
| `History` | 转换历史 | 历史记录持久化 | JSON/文件存储 |
| `MultiSourceCrossValidator` | .dsn + .edf + pstx* | 三路逐项比对差异报告 | 全字段 diff；pstxnet 缺失时自动降级为 2-source |
| `OLBIntegrityChecker` | .olb 文件 | Package/Device/LibraryPart 三层完整性报告 | 结构体解析 + 一致性问题检测 |
| `ConfigValidator` | Config 单例 | 路径/编码/参数合法性报告 | 文件系统检查 + 格式验证 |

---

## 3. 中间表示模型（IR）

### 3.1 核心数据模型

```
DesignIR
├── metadata: ProjectMetadata (项目名、版本、创建时间等)
├── pages: list[PageIR] (原理图页列表)
│   ├── page_id: str
│   ├── hierarchy_path: str (如 "1.1", "2.3")
│   ├── instances: list[ComponentInstanceIR]
│   │   ├── refdes: str (如 "R1", "U3")
│   │   ├── part_name: str
│   │   ├── footprint: str
│   │   ├── value: str
│   │   ├── properties: dict
│   │   └── pin_connections: list[PinConnection]
│   ├── nets: list[NetIR]
│   │   ├── net_name: str
│   │   ├── is_bus: bool
│   │   ├── bus_members: list[str]
│   │   └── connections: list[(refdes, pin_number)]
│   ├── ports: list[PortIR]
│   └── graphics: list[GraphicElementIR]
├── hierarchy: HierarchyTree
└── global_properties: dict

LibraryIR
├── parts: list[PartIR]
│   ├── part_name: str
│   ├── symbols: list[SymbolIR]
│   │   ├── pins: list[PinIR]
│   │   │   ├── number: str
│   │   │   ├── name: str
│   │   │   ├── type: ElectricalType
│   │   │   └── position: (x, y)
│   │   └── graphics: list
│   └── properties: dict
└── packages: list[PackageIR]

MatchResult
├── source: ComponentIR (CIS 器件)
├── target: ComponentIR (HDL 器件)
├── confidence: float (0.0 - 1.0)   # final_conf = phase1_prior_conf × phase2_within_conf
├── strategy: MatchStrategy (PASSIVE_EXACT/PASSIVE_EXACT_MULTI/PASSIVE_VALUE_ONLY/
│                            PASSIVE_VALUE_NEAR/PASSIVE_SIZE_ONLY/PASSIVE_PREFIX_ONLY/
│                            ACTIVE_WITHIN_TYPE/NEEDS_REVIEW/MANUAL)
├── phase1_type: str                # Phase 1 命中的类型
├── phase1_prior_conf: float        # 类型先验置信度
├── phase2_within_conf: float       # 类型内匹配置信度
├── phase2_strategy_detail: str     # 类型内匹配细节（维度得分等）
├── top3_candidates: list[dict]     # 跨类型 Top-3 候选（按 final_conf 降序）
├── pin_mapping: dict[CIS_pin → HDL_pin]
└── warnings: list[str]
```

> **ComponentDef.extra_data**（v2.0 新增）：`ComponentDef` 上的可扩展字段容器，挂载匹配辅助数据。常见键包括 `cis_value`（CIS 原始标称值）、`suggested_primitive`（建议图元）、`pst_jedec_type` / `pst_part_name`（PST 注入的 JEDEC 类型与器件名）、`pst_value` 等。匹配器通过 `extra_data` 读取 PST/EDIF 注入信息而不修改核心字段。

### 3.2 数据流

```
.dsn ──▶ [DSNParser] ──▶ DesignIR ──┐
.olb ──▶ [OLBParser] ──▶ LibraryIR ─┤
HDL lib dir ──▶ [HDLLibScanner] ──▶ ComponentDB ─────┤
PST 数据源 ──▶ [Pstchip/Pstxnet/PstxnetNetlist] ─────┤
                                                     ▼
                     ┌─────────────── [Diagnostics Pipeline] ◄── 用户文件集
                     │                          │
                     │               ┌──────────┴──────────┐
                     │               ▼                      ▼
                     │       ReadinessReport       StructuredReport
                     │               │
                     ▼               ▼
                                [Matcher Pipeline (v2.0 两阶段)]
                                                     │
                                                     ▼
                                           list[MatchResult]
                                                     │
                                                     ▼
                                           [Validator Pipeline]
                                                     │
                                                     ▼
                                        ValidatedDesignIR
                                                     │
                                                     ▼
                                           [Writer Pipeline]
                                                     │
                    ┌─────────────────────────────────┤
                    ▼                ▼                ▼
              .cpm + cds.lib    .sch.N.M          .csa
                                                     │
                                                     ▼
                                            ConversionReport
                                            (结构化诊断报告)
```

---

## 4. 模块划分

### 4.1 顶层包结构

> 以下结构为 **2026-08-07 实测代码**（v1.1.0）。旧文档中的 `generator/`、`version/`、`layout/`、`cli/` 目录均不存在；生成层实际为 `core/writer/`，CLI 走 `python -m cis2hdl convert`（`__main__.py`），版本适配层与排版层为规划未实施。

```
cis2hdl/
├── __init__.py                # 包入口（__version__）
├── __main__.py                # CLI 入口：无参/GUI → `python -m cis2hdl`；转换 → `python -m cis2hdl convert`
├── config/                    # 配置与规则
│   ├── __init__.py
│   ├── type_gate.yaml         # 类型门控规则（Phase 1 类型假设）
│   └── weights.yaml           # 权重配置
├── core/                      # 核心引擎
│   ├── __init__.py
│   ├── config.py              # 全局 Config 单例（路径/编码/参数）
│   ├── exceptions.py          # 异常体系
│   ├── net_utils.py           # 网络工具
│   ├── ir/                    # 中间表示模型
│   │   ├── __init__.py
│   │   ├── component.py       # ComponentDef, ComponentInstanceIR, PinDef, ElectricalType（统一器件模型）
│   │   ├── design.py          # DesignIR, PageIR, NetIR, WireSegment
│   │   └── match.py           # MatchResult, MatchStrategy, PinMapping
│   ├── db/                    # 器件数据库
│   │   ├── __init__.py
│   │   └── component_db.py    # ComponentDB（统一器件数据库 — CIS + HDL 共用 Schema）
│   │                          # ⚠️ persistence.py（ComponentDBSerializer JSON 持久化）未落地
│   ├── engine/                # 主控引擎
│   │   ├── __init__.py
│   │   ├── conversion_engine.py  # ConversionEngine（六阶段 diagnose/parse/scan_hdl_library/
│   │   │                       #   match/validate/generate；convert/convert_full/accept_match）
│   │   └── batch_engine.py       # 批量转换引擎
│   ├── parser/                # 解析层
│   │   ├── __init__.py
│   │   ├── base.py            # ParserBase(ABC) + ParserRegistry
│   │   ├── edif_parser.py     # EDIFParser（sexpdata → IR；Stage 5.5 pin 连接注入）
│   │   ├── hdl_scanner.py     # HDLLibScanner → ComponentDB
│   │   ├── chips_prt.py       # ChipsPrtParser
│   │   ├── symbol_css.py      # SymbolCssParser
│   │   ├── part_ptf.py        # PartPtfParser
│   │   ├── pstchip_parser.py       # PstchipParser（pstchip.dat → JEDEC_TYPE/VALUE）
│   │   ├── pstxnet_parser.py       # PstxnetParser（pstxprt.dat → refdes→primitive）
│   │   ├── pstxnet_netlist_parser.py # PstxnetNetlistParser（pstxnet.dat → pin→net）
│   │   ├── cross_validator.py # CrossValidator（8 项比对）
│   │   ├── cross_ref_parser.py # 交叉引用解析
│   │   ├── component_catalog.py  # 元件目录
│   │   ├── layout_mapper.py   # LayoutMapper（CIS 坐标 → HDL 网格）
│   │   ├── dsn/               # Binary DSN 解析（三层架构）
│   │   │   ├── __init__.py
│   │   │   ├── ole_reader.py      # OleReader（CFB 容器；count_page_candidates 回退算法）
│   │   │   ├── binary_reader.py   # BinaryReader（类型化二进制）
│   │   │   ├── structures.py      # StructureParsers + FutureDataList + read_preamble/auto_read_prefixes
│   │   │   ├── page_parser.py     # 页面流解析（标准内联 + RTL strLst 索引双格式）
│   │   │   ├── cache_parser.py    # Cache 流 → Package/Device/LibraryPart
│   │   │   ├── library_parser.py  # Library 流 → strLst（parse_strlst）
│   │   │   ├── property_audit.py  # 属性审计
│   │   │   └── dsn_parser.py      # 顶层调度器
│   │   └── olb/               # OLB 解析
│   │       ├── __init__.py
│   │       ├── olb_parser.py  # OLBParser（Phase III）
│   │       └── olb_reader.py  # OLB CFB 读取
│   ├── matcher/               # 匹配层（v2.0 两阶段）
│   │   ├── __init__.py
│   │   ├── base.py            # MatcherBase(ABC)
│   │   ├── registry.py        # MatcherRegistry
│   │   ├── pipeline.py        # MatcherPipeline（Phase 1/1.5/2A/2B 编排）
│   │   ├── type_hypothesis.py # TypeHypothesisGenerator（Phase 1）
│   │   ├── candidate_pool.py  # CandidatePoolBuilder（Phase 1.5）
│   │   ├── passive_matcher.py # PassiveMatcher（Phase 2A 确定性 5 级）
│   │   ├── active_matcher.py  # ActiveMatcher（Phase 2B 类型内 5 维评分）
│   │   ├── exact.py           # ExactMatcher（类型内链）
│   │   ├── fuzzy.py           # FuzzyNameMatcher（类型内链）
│   │   ├── feature.py         # FeatureExtractMatcher（类型内链）
│   │   ├── value_matcher.py   # ValueMatcher（类型内链）
│   │   ├── fallback.py        # FallbackMatcher（类型内链）
│   │   ├── prefix_filter.py   # 前缀提取 + 固定前缀（extract_prefix / is_passive_prefix）
│   │   ├── scoring.py         # PrefixAffinityCalculator（Phase 1 先验调整；MultiScorer 已删除）
│   │   └── match_config.py    # MatchConfig（type_gate.yaml 加载）
│   ├── validator/             # 校验层
│   │   ├── __init__.py
│   │   ├── base.py            # ValidatorBase(ABC)
│   │   ├── registry.py        # ValidatorRegistry
│   │   ├── pin_validator.py
│   │   ├── net_validator.py
│   │   └── power_validator.py
│   ├── writer/                # 生成层（旧设计 generator/ 已废弃改名）
│   │   ├── __init__.py
│   │   ├── base.py            # WriterBase(ABC) + WriterRegistry
│   │   ├── cpm_writer.py      # CPMWriter（.cpm）
│   │   ├── sch_writer.py      # SCHWriter（.sch.N.M）
│   │   ├── csa_writer.py      # CSAWriter（.csa MACRO_DRAWING，主输出）
│   │   ├── cdslib_writer.py   # CDSLibWriter（cds.lib）
│   │   ├── xcon_writer.py     # XconWriter（.xcon）
│   │   ├── cpc_writer.py      # CPCWriter（.cpc）
│   │   ├── scr_writer.py      # ScrWriter（.scr）
│   │   ├── mapping_csv_writer.py # MappingCSVWriter（{project}_mapping.csv）
│   │   ├── error_logger.py    # ErrorLogger（{project}_errors.{html,txt}）
│   │   └── output_manager.py  # OutputManager（DEHDL 目录树编排）
│   └── diagnostics/           # 诊断层
│       ├── __init__.py
│       ├── pipeline.py            # DiagnosticPipeline（六阶段顺序编排）
│       ├── file_inventory.py      # FileInventory
│       ├── file_validator.py      # ProjectFileValidator（三层文件校验）
│       ├── error_diagnosis.py     # ErrorDiagnosisEngine（44 错误码，v1.1.0；39 为历史口径）
│       ├── recovery.py            # FileRecoveryStrategy
│       ├── quality.py             # ConversionQualityEstimator
│       ├── report_gen.py          # StructuredReportGenerator
│       ├── tracker.py             # IncrementalConversionTracker
│       ├── history.py             # History
│       ├── multi_source.py        # MultiSourceCrossValidator
│       ├── olb_integrity.py       # OLBIntegrityChecker
│       ├── config_validator.py    # ConfigValidator
│       └── diagnostic_report.py   # DiagnosticReport 模型
├── gui/                       # 前端 GUI（PySide6/Qt）
│   ├── __init__.py
│   ├── app.py                 # QApplication 入口（run_gui）
│   ├── main_window.py         # 主窗口
│   ├── colors.py              # 配色
│   ├── candidate_selector.py  # 候选选择器
│   ├── panels/                # 面板组件
│   │   ├── __init__.py
│   │   ├── sidebar.py         # 侧边栏
│   │   ├── summary_bar.py     # 摘要栏
│   │   ├── tab_container.py   # 标签容器
│   │   ├── project_panel.py   # 项目面板
│   │   ├── match_review.py    # 匹配确认面板
│   │   ├── preview_panel.py   # 预览面板
│   │   ├── log_panel.py       # 日志面板
│   │   ├── report_panel.py    # 报告面板
│   │   ├── diff_view.py       # 差异对比
│   │   ├── schematic_view.py  # 原理图预览
│   │   ├── diagnostic_panel.py # 诊断面板
│   │   ├── error_diagnostic_panel.py # 错误诊断面板
│   │   └── rules_panel.py     # 规则面板
│   ├── dialogs/               # 对话框
│   │   ├── __init__.py
│   │   ├── settings_dialog.py # 设置对话框
│   │   ├── match_confirm.py   # 匹配确认对话框
│   │   └── recovery_dialog.py # 恢复对话框
│   └── widgets/               # 自定义控件
│       ├── __init__.py
│       └── conversion_worker.py # 转换后台线程
└── utils/                     # 工具模块
    ├── __init__.py
    └── naming.py              # 命名规范处理（normalize_value 等）

# 项目根目录（参考）
tests/                     # 测试套件
scripts/                   # 工具脚本（verify_multi_source.py 等）
docs/                      # 文档
docs_for_reference/        # 参考工程（OpenOrCadParser / CIStoHDL_standard 等）
HG5015_tests/              # HG5015 实测数据
```

**规划未实施说明**：

| 原设计目录/模块 | 现状 |
|----------------|------|
| `core/generator/` | ❌ 不存在；生成层实际为 `core/writer/`（csa_writer/sch_writer/cpm_writer/cdslib_writer/xcon_writer/cpc_writer/scr_writer/mapping_csv_writer/output_manager） |
| `core/version/`（VersionAdapter） | ❌ 不存在；版本差异由 `core/config.py` 与 writer 参数控制 |
| `core/layout/`（排版器） | ❌ 不存在；坐标映射由 `core/parser/layout_mapper.py` + `writer/csa_writer.py._map_coords_to_dehdl()` 承担 |
| `cli/` | ❌ 不存在；CLI 走 `python -m cis2hdl convert`（`__main__.py`） |
| `core/db/persistence.py`（ComponentDBSerializer） | ❌ 未落地；`core/db/` 仅 `component_db.py` |
| `utils/logger.py` / `utils/cfb_reader.py` | ❌ 不存在；`utils/` 仅 `naming.py` |
| `config/settings.py` / `mapping_rules.yaml` / `char_replace.yaml` | ❌ 不存在；`config/` 仅 `type_gate.yaml` + `weights.yaml` |

---

## 5. 前后端同步开发策略

### 5.1 为什么推荐前后端同步开发？

| 优势 | 说明 |
|------|------|
| 即时验证 | 后端算法实现后立刻通过 GUI 操作验证正确性 |
| 减少返工 | 界面交互设计影响后端 API 设计，同步开发避免后期改接口 |
| 进度可见 | 每个阶段都有可视化成果，利于汇报和评审 |

### 5.2 同步开发的三阶段策略

```
Phase I:  Foundation
  ├─ Backend:  IR 模型定义 + Parser 框架 + Generator 框架
  ├─ Frontend: 主窗口骨架 + 项目面板 + 文件选择对话框
  └─ 集成点:  文件选择 → 触发 DSN 文件结构打印（验证 Parser 可用）

Phase II:  Core Pipeline
  ├─ Backend:  Matcher Pipeline + Validator + 完整 Generator
  ├─ Frontend: 匹配确认面板 + 转换进度条 + 日志面板
  └─ 集成点:  完整的一键转换流程（含人工确认环节）

Phase III:  Polish
  ├─ Backend:  性能优化 + 边界情况处理 + 批量转换
  ├─ Frontend: 原理图预览 + 差异对比 + 报告生成 + 设置面板
  └─ 集成点:  全功能可用，交付测试
```

### 5.3 前后端接口协议

前后端通过 `ConversionEngine` 统一交互，前端不直接调用 Parser/Matcher/Writer。以下为 v1.1.0 实际方法（`core/engine/conversion_engine.py`）：

```python
class ConversionEngine:
    """前后端唯一的交互接口（v1.1.0 实测方法）"""

    # Stage 1 — 诊断
    def diagnose(self, input_files: list[Path]) -> DiagnosticReport: ...
    # Stage 2 — 解析
    def parse(self, input_path: Path) -> DesignIR: ...
    # Stage 3 — HDL 库扫描
    def scan_hdl_library(self, lib_path: Optional[Path] = None) -> ComponentDB: ...
    # Stage 4 — 匹配（v2.0 两阶段）
    def match(self, design: DesignIR, hdl_db: ComponentDB) -> list[MatchResult]: ...
    # Stage 5 — 校验
    def validate(self, design: DesignIR, matches: list[MatchResult]
                 ) -> list[DiagnosisError]: ...
    # Stage 6 — 生成
    def generate(self, design: DesignIR, matches: list[MatchResult],
                 output_dir: Path) -> ConversionReport: ...

    # 一键转换 / 完整流程 / 人工接受匹配
    def convert(self, input_path: Path, output_dir: Path,
                hdl_lib_path: Optional[Path] = None) -> ConversionReport: ...
    def convert_full(self, input_path: Path, ...) -> ConversionReport: ...
    def accept_match(self, source_library_id: str,
                     target_library_id: str) -> MatchResult: ...

    # 内部六阶段（_stage_*）
    def _stage_diagnose(self, input_files): ...
    def _stage_parse(self, input_path): ...
    def _stage_scan(self): ...
    def _stage_match(self): ...
    def _stage_validate(self): ...
    def _stage_generate(self): ...
```

> CLI 侧入口为 `python -m cis2hdl convert <input> [--output <dir>] [--hdl-lib <dir>] [--benchmark] [--max-workers <n>]`，由 `__main__.py` 调用 `ConversionEngine.convert()`。

---

## 6. 部署与分发

### 6.1 推荐方案

- **开发阶段**：`pip install -e .` 开发模式安装
- **分发阶段**：PyInstaller 打包为独立 `.exe`（Windows），无需 Python 环境（`cis2hdl.spec` 已提供）
- **CLI 使用**：`python -m cis2hdl convert <input.dsn> [--output <dir>] [--hdl-lib <dir>] [--benchmark] [--max-workers <n>]`；无参数或 `python -m cis2hdl gui` 启动 GUI

### 6.2 依赖管理

使用 `pyproject.toml` + `pip` 管理依赖，分三组：

```
[project]
dependencies = ["pyside6", "rapidfuzz", "pydantic", "pyyaml"]

[project.optional-dependencies]
dev = ["pytest", "pytest-qt", "black", "ruff", "mypy"]
cxx = ["pybind11"]  # C++ 桥梁依赖
```
