# ARCHITECTURE（系统架构与设计总文档）

> **文档名**: ARCHITECTURE（系统架构与设计总文档）
> **版本口径**: v1.1.0（匹配系统 v2.0 两阶段，MultiScorer 已删除；测试 268/23（291）；错误码 44；PAINT WIRE 已移除；GUI 基于 PySide6；目录结构实测 cis2hdl/{config,core,gui,utils}）
> **合并日期**: 2026-08-07
> **合并原则**: 内容保全（Content Preservation）—— 5 份源文档的原文逐节保留，不做改写或重构；仅调整标题层级、新增合并说明/交叉引用章节、处理跨文档引用。
> **合并来源**:
>   - `docs/SYSTEM_ARCHITECTURE.md`（v1.1.0，2026-08-07，797 行）→ Part I 系统架构总览
>   - `docs/BACKEND_DESIGN.md`（v1.1.0，2026-08-07，962 行）→ Part II 后端详细设计
>   - `docs/COMPONENT_ARCHITECTURE.md`（v1.1.0，2026-08-07，564 行）→ Part III 器件模型与数据库
>   - `docs/DIAGNOSTICS_AND_RECOVERY.md`（v1.1.0，2026-08-07，467 行）→ Part IV 诊断与恢复体系
>   - `docs/UI_DESIGN_SPEC.md`（v1.1.0，2026-08-07，683 行）→ Part V GUI 设计规范
> **文档结构**:
>   - **Part 0** 合并说明（新增：合并原则、Part 结构总表、章节映射表、交叉引用处理说明、重复内容注记）
>   - **Part I** 系统架构总览（原 SYSTEM_ARCHITECTURE.md 全文，逐节保留）
>   - **Part II** 后端详细设计（原 BACKEND_DESIGN.md 全文，逐节保留）
>   - **Part III** 器件模型与数据库（原 COMPONENT_ARCHITECTURE.md 全文，逐节保留）
>   - **Part IV** 诊断与恢复体系（原 DIAGNOSTICS_AND_RECOVERY.md 全文，逐节保留）
>   - **Part V** GUI 设计规范（原 UI_DESIGN_SPEC.md 全文，逐节保留）
>   - **合并保全声明**（文档末尾：源文档章节数与合并后位置，证明 100% 覆盖）

---

## Part 0 合并说明（新增章节）

> 本章为 2026-08-07 合并时新增的合并说明，非任何源文档原文。其作用：说明合并原则与权威口径、给出 Part 结构总表与章节映射表、说明交叉引用处理规则、标注重复内容与合并注记。

### 0.1 合并原则与权威口径

本合并文档采用**内容保全式分卷**：5 份源文档的章节逐节完整保留（含表格、代码块、ASCII 图、附录），仅调整标题层级（原 `##` → `###`、`###` → `####`、`####` → `#####`，原文档标题置于各 Part「原文档标题与头部（原文保留）」节），并在各 Part 前标注来源与重叠注记。全文不删除、不改写源文档任何句子。

合并后的**权威口径（v1.1.0，2026-08-07 实测）**如下：

| 口径项 | 权威值 | 说明 |
|--------|--------|------|
| 版本 | v1.1.0 | 匹配 v2.0；各 Part 原文中的 v1.0/v0.x 描述为历史演进，保留原文不动 |
| 匹配架构 | v2.0 两阶段（Phase 1/1.5/2A/2B） | MultiScorer 已删除；旧版四级管道（Exact→Fuzzy→Feature→Manual）仅为历史描述（Part II §4.3） |
| 错误码 | **44**（v1.1.0 口径） | 旧口径 31 / 39（39 漏算 OLB 51-55）为历史描述 |
| 测试基线 | 268 passed / 23 skipped（291 collected） | 2026-08-07 实测 |
| PAINT WIRE | **已移除** | 仅作为历史实测记录保留于相关原文 |
| GUI 框架 | PySide6（Qt 6 for Python） | `cis2hdl/gui/`；Token 体系位于 `colors.py` |
| 目录结构 | cis2hdl/{config,core,gui,utils} | 无 version/layout/cli/generator 目录；生成层为 core/writer/，CLI 走 python -m cis2hdl convert |

### 0.2 Part 结构总表

| Part | 主题 | 源文档 | 版本 / 日期 | 源行数 |
|:----:|------|--------|------------|:------:|
| Part I | 系统架构总览 | `SYSTEM_ARCHITECTURE.md` | v1.1.0，2026-08-07 | 797 |
| Part II | 后端详细设计 | `BACKEND_DESIGN.md` | v1.1.0，2026-08-07 | 962 |
| Part III | 器件模型与数据库 | `COMPONENT_ARCHITECTURE.md` | v1.1.0，2026-08-07 | 564 |
| Part IV | 诊断与恢复体系 | `DIAGNOSTICS_AND_RECOVERY.md` | v1.1.0，2026-08-07 | 467 |
| Part V | GUI 设计规范 | `UI_DESIGN_SPEC.md` | v1.1.0，2026-08-07 | 683 |

### 0.3 章节映射表（源文档章节 → Part 内位置）

> 各源文档章节编号在合并后**原样保留**，故「Part X 内位置」即「Part X §源章节编号」。下表逐条列出每份源文档的 H2 主章节及其在 Part 内的位置。

**源文档：SYSTEM_ARCHITECTURE.md（→ Part I）**

| 源文档章节 | Part 内位置 |
|-----------|------------|
| 1 架构总览 | Part I §1 |
| 2 分层设计 | Part I §2 |
| 3 中间表示模型（IR） | Part I §3 |
| 4 模块划分 | Part I §4 |
| 5 前后端同步开发策略 | Part I §5 |
| 6 部署与分发 | Part I §6 |

**源文档：BACKEND_DESIGN.md（→ Part II）**

| 源文档章节 | Part 内位置 |
|-----------|------------|
| 1 总览 | Part II §1 |
| 2 中间表示模型（IR） | Part II §2 |
| 3 解析层实现策略 | Part II §3 |
| 4 匹配层实现 | Part II §4 |
| 5 生成层实现 | Part II §5 |
| 6 ConversionEngine（主控） | Part II §6 |
| 7 诊断与容错管道（已落地 core/diagnostics/） | Part II §7 |

**源文档：COMPONENT_ARCHITECTURE.md（→ Part III）**

| 源文档章节 | Part 内位置 |
|-----------|------------|
| 0 核心结论（回答架构关键问题） | Part III §0 |
| 1 CIS 和 HDL 器件库格式差异 | Part III §1 |
| 2 统一器件数据模型（单一数据源设计） | Part III §2 |
| 3 器件数据库设计（统一管理） | Part III §3 |
| 4 匹配层设计（基于统一模型） | Part III §4 |
| 5 自定义元件支持 | Part III §5 |
| 6 解析器与写入器注册架构 | Part III §6 |
| 7 完整数据流 | Part III §7 |
| 8 文件完备性对器件库的影响分析 | Part III §8 |

**源文档：DIAGNOSTICS_AND_RECOVERY.md（→ Part IV）**

| 源文档章节 | Part 内位置 |
|-----------|------------|
| 0 现状审查结论 | Part IV §0 |
| 1 CIS 项目文件完整清单 | Part IV §1 |
| 2 文件校验与诊断系统设计 | Part IV §2 |
| 3 用户交互流程设计 | Part IV §3 |
| 4 与 Cadence 专业工具的功能对比 | Part IV §4 |
| 5 推荐新增模块开发计划 | Part IV §5 |
| 6 可选的增强文件清单（完整） | Part IV §6 |
| 7 自检清单 | Part IV §7 |

**源文档：UI_DESIGN_SPEC.md（→ Part V）**

| 源文档章节 | Part 内位置 |
|-----------|------------|
| 1 设计哲学 | Part V §1 |
| 2 Token 体系总览 | Part V §2 |
| 3 颜色系统 | Part V §3 |
| 4 间距系统（4px 网格） | Part V §4 |
| 5 圆角规范（外圆角 > 内圆角） | Part V §5 |
| 6 字体、阴影与排版 | Part V §6 |
| 7 布局尺寸 | Part V §7 |
| 8 组件样式规范 | Part V §8 |
| 9 状态指示 | Part V §9 |
| 10 布局架构 | Part V §10 |
| 11 QSS 样式表清单 | Part V §11 |
| 12 合规检查清单 | Part V §12 |
| 13 交互流程设计（原 FRONTEND_DESIGN） | Part V §13 |

### 0.4 交叉引用处理说明

合并时对源文档内部的互链与外部引用做了统一处理（仅调整引用文字，不改写被引内容）：

| 引用类型 | 处理规则 | 示例 |
|---------|---------|------|
| 源文档互链（5 份之间） | 改为新文档内引用「见 Part X §N」 | `BACKEND_DESIGN` 中「详见 `SYSTEM_ARCHITECTURE.md §2.1.1`」→「见 Part I §2.1.1」 |
| 指向本簇外部合并文档 | 标注合并文档名（原源文档名） | `CODING_STANDARDS §5.1` → `STANDARDS.md（原 CODING_STANDARDS §5.1）`；`ORCAD_SOURCE_ANALYSIS §10.2+§13.2` → `RESEARCH.md（原 ORCAD_SOURCE_ANALYSIS …）` |
| 指向已归档文档 | 标注归档路径 archive/合并源/（原文档名）.md | `docs/2608041210report.md` → `archive/合并源/2608041210report.md`；`FRONTEND_DESIGN.md` → `archive/合并源/FRONTEND_DESIGN.md` |
| 代码/配置路径（core/、cis2hdl/、config/ 等） | 保持原文不动 | `core/diagnostics/error_diagnosis.py` 等 |

### 0.5 重复内容与合并注记

5 份源文档在以下主题存在重叠（匹配层描述、错误码表、诊断管道、GUI 目录结构等）。按内容保全原则，**重叠原文均保留不动、不做删减**，仅在 Part 首部加「重叠注记」，统一以 v1.1.0 新口径为准：

| 重叠主题 | 出现位置 | 权威口径 |
|---------|---------|---------|
| 匹配层 v2.0 两阶段 | Part I §2.2 / Part II §4 / Part III §4 | v2.0 两阶段；MultiScorer 已删除 |
| 错误码 44 | Part I §2.7 / Part II §7.3 / Part IV §4 | 44（旧口径 31/39 为历史） |
| 诊断三层管道 | Part I §2.7 / Part IV §2 | 已落地 core/diagnostics/ 14 模块 |
| GUI 目录结构 | Part I §4.1 / Part V §13.6.2 | 2026-08-07 实测（cis2hdl/gui/） |
| 二进制解析算法要点 | Part I §2.1.1 / Part II §3.1 | Part I §2.1.1 为唯一正式归宿（原文档声明） |

---

## Part I 系统架构总览（原 SYSTEM_ARCHITECTURE.md 全文，逐节保留）

> **Part I 来源**: 原 `SYSTEM_ARCHITECTURE.md`（v1.1.0，2026-08-07，797 行）
> **历史边界注记**: 本部分为原 `SYSTEM_ARCHITECTURE.md` 全文，写作于 2026-08-07（v1.1.0 修订：匹配层改为 v2.0 两阶段；错误码统一为 44；包结构按实际代码校正）。原文所有句子、表格、代码块、ASCII 图均原样保留，仅调整标题层级以适配合并文档结构。
> **重叠注记**: 本部分 §2.2（匹配层 v2.0 两阶段）与 Part II §4 / Part III §4 有重叠；§2.7（诊断层 / 44 错误码）与 Part IV 有重叠；§4.1（顶层包结构）与 Part V §13.6.2（GUI 目录）有重叠。重叠原文均保留不动，以 v1.1.0 新口径为准。

### 原文档标题与头部（原文保留）

**原标题**: CIS2HDL 系统架构设计


> 版本: v1.1.0 | 日期: 2026-08-07 | 状态: 修订 | 更新: 匹配层改为 v2.0 两阶段架构；错误码统一为 44（旧口径 31/39）；包结构按实际代码校正；解析器章节并入 HG5015 二进制解析算法要点

---

### 1. 架构总览

#### 1.1 整体架构图

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

#### 1.2 架构设计原则

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

### 2. 分层设计

#### 2.1 Parser Layer（解析层）

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

#### 2.1.1 二进制解析算法要点（HG5015 实测，2026-08-04）

> 本节为 `archive/合并源/2608041210report.md` 中 HG5015 二进制解析算法要点的正式归宿；后端实现细节见 Part II §3（原 BACKEND_DESIGN.md）。

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

#### 2.2 Matcher Layer（匹配层）

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
- **旧版四级管道（Exact → Fuzzy → Feature → Manual）已被 v2.0 两阶段取代**：Exact/Fuzzy/Feature 在 v2.0 中降级为 ActiveMatcher 的类型内 matcher 链；完整历史描述保留于 Part II §4.3（历史演进）

#### 2.3 Validator Layer（校验层）

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

#### 2.5 Version Adapter Layer（版本适配层）【规划未实施】

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

#### 2.6 Layout Layer（排版层）【规划未实施】

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

#### 2.4 Writer Layer（生成层）

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

#### 2.7 Diagnostics Layer（诊断层）【新增】

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

### 3. 中间表示模型（IR）

#### 3.1 核心数据模型

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

#### 3.2 数据流

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

### 4. 模块划分

#### 4.1 顶层包结构

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

### 5. 前后端同步开发策略

#### 5.1 为什么推荐前后端同步开发？

| 优势 | 说明 |
|------|------|
| 即时验证 | 后端算法实现后立刻通过 GUI 操作验证正确性 |
| 减少返工 | 界面交互设计影响后端 API 设计，同步开发避免后期改接口 |
| 进度可见 | 每个阶段都有可视化成果，利于汇报和评审 |

#### 5.2 同步开发的三阶段策略

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

#### 5.3 前后端接口协议

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

### 6. 部署与分发

#### 6.1 推荐方案

- **开发阶段**：`pip install -e .` 开发模式安装
- **分发阶段**：PyInstaller 打包为独立 `.exe`（Windows），无需 Python 环境（`cis2hdl.spec` 已提供）
- **CLI 使用**：`python -m cis2hdl convert <input.dsn> [--output <dir>] [--hdl-lib <dir>] [--benchmark] [--max-workers <n>]`；无参数或 `python -m cis2hdl gui` 启动 GUI

#### 6.2 依赖管理

使用 `pyproject.toml` + `pip` 管理依赖，分三组：

```
[project]
dependencies = ["pyside6", "rapidfuzz", "pydantic", "pyyaml"]

[project.optional-dependencies]
dev = ["pytest", "pytest-qt", "black", "ruff", "mypy"]
cxx = ["pybind11"]  # C++ 桥梁依赖
```

## Part II 后端详细设计（原 BACKEND_DESIGN.md 全文，逐节保留）

> **Part II 来源**: 原 `BACKEND_DESIGN.md`（v1.1.0，2026-08-07，962 行）
> **历史边界注记**: 本部分为原 `BACKEND_DESIGN.md` 全文，写作于 2026-08-07（v1.1.0 修订：匹配层 v2.0 两阶段；错误码 31→44；EDIF 角色改为 pin 连接注入）。原文所有句子、代码块、表格均原样保留，仅调整标题层级以适配合并文档结构。
> **重叠注记**: 本部分 §4（匹配层）与 Part I §2.2 / Part III §4 有重叠；§7（诊断与容错管道、44 错误码）与 Part IV 有重叠。重叠原文均保留不动，以 v1.1.0 新口径为准。

### 原文档标题与头部（原文保留）

**原标题**: CIS2HDL 后端引擎设计


> 版本: v1.1.0 | 日期: 2026-08-07 | 状态: 修订 | 更新: 匹配层改为 v2.0 两阶段；错误码 31→44；EDIF 角色改为 pin 连接注入（Stage 5.5）；新增 PST 数据源章节；HDLLibScanner 输出统一 ComponentDB

---

### 1. 总览

后端引擎实现完整的转换管道：**诊断 → 解析 → 扫描 → 匹配 → 校验 → 生成**（`ConversionEngine` 六阶段 `_stage_diagnose/_stage_parse/_stage_scan/_stage_match/_stage_validate/_stage_generate`）。

所有模块通过统一的中间表示（IR）进行通信。**器件库部分详见 Part III（原 COMPONENT_ARCHITECTURE.md）**。

#### 核心架构原则

- **一个 ComponentDef 统治所有**：CIS 和 HDL 的器件使用完全相同的 Python 类，绝不按格式分叉
- **基类-注册模式**：解析器、匹配器、写入器均通过 `ParserBase`/`MatcherBase`/`WriterBase` 基类 + `Registry` 注册，不按器件类型分叉
- **格式只在边界层处理**：Parser 负责"格式 → IR"，Writer 负责"IR → 格式"，中间所有逻辑只操作 IR

---

### 2. 中间表示模型（IR）

#### 2.1 设计原则

- 使用 **Pydantic BaseModel** 保证类型安全和自动验证
- 字段全类型注解
- 序列化支持（JSON/YAML 用于调试和规则存储）
- 坐标字段纳入 IR（Phase I 即具备）

#### 2.2 核心模型定义

**器件库模型**（详见 Part III §2）：

```python
from cis2hdl.core.ir.component import ComponentDef, ComponentInstanceIR, PinDef, ElectricalType
```

**页面/设计模型**：

```python
from pydantic import BaseModel, Field

class NetConnection(BaseModel):
    refdes: str
    pin_number: str

class NetIR(BaseModel):
    """网络定义 — 使用 Cadence ISCF 内部的 4 类网络模型"""
    name: str
    category: str = "FLAT"               # FLAT/GROUND/POWER/BUS (参考 ISCF)
    connections: list[NetConnection] = Field(default_factory=list)
    is_bus: bool = False
    bus_members: list[str] = Field(default_factory=list)

class WireSegment(BaseModel):
    """走线线段 — 含坐标"""
    start_x: int; start_y: int
    end_x: int; end_y: int
    net_name: str = ""

class PageIR(BaseModel):
    page_id: str                        # "1.1" 表示第1层第1页
    page_name: str = ""
    width: int = 3520
    height: int = 2720
    instances: list[ComponentInstanceIR] = Field(default_factory=list)
    nets: list[NetIR] = Field(default_factory=list)
    wires: list[WireSegment] = Field(default_factory=list)
    ports: list[dict] = Field(default_factory=list)

class DesignIR(BaseModel):
    project_name: str
    source_format: str = "CIS"
    pages: list[PageIR] = Field(default_factory=list)
    component_db: 'ComponentDB' = Field(default_factory=lambda: ComponentDB())  # 器件库
    global_nets: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
```

---

### 3. 解析层实现策略

#### 3.0 双路并行架构

**两路数据源输出统一的 DesignIR，可交叉验证。**

```
路径 A: EDIF 文本解析（早期 Phase I-A 先行验证）
  test.edf → [EDIFParser] → DesignIR（逻辑完整，坐标缺失）
                                 ↓
                            交叉验证器 ←── DesignIR（逻辑 + 坐标）
                                 ↑
路径 B: Binary DSN 解析（主力，逻辑+坐标）
  test.dsn → [OleReader] → [BinaryReader] → [StructureParsers]
             → [DSNParser] → DesignIR（逻辑 + 坐标完整）

辅助数据源（PST / 交叉引用，v0.8+）：
  pstchip.dat  → [PstchipParser]      → JEDEC_TYPE / VALUE 增强
  pstxprt.dat  → [PstxnetParser]      → refdes → primitive / INSxxx 桥接
  pstxnet.dat  → [PstxnetNetlistParser] → pin → net 网络补充
```

> **EDIF 角色演进（v1.1.0）**：早期 EDIF 承担"Phase I-A 先行验证"（快速逻辑验证）；后期主要角色改为 **pin 连接注入（Stage 5.5）**——在 `ConversionEngine._stage_generate` 中调用 `EDIFParser.extract_pin_net_map()` 将 pin→net 映射注入 `ComponentInstanceIR.pin_connections`（详见 `Part I §2.1.1`）。

#### 3.0a EDIF Parser（路径 A — 早期 Phase I-A 先行）

**EDIF 2.0.0 格式**：Lisp-like S-expression 语法。文本格式、解析简单，可立即验证。

```python
class EDIFParser(ParserBase):
    FORMAT_NAME = "CIS_EDIF"
    FILE_EXTENSIONS = [".edf"]
    
    def parse(self, edif_path: Path) -> DesignIR:
        """解析 EDIF 文件为 IR。
        
        EDIF 顶层结构:
        (edif CAP2EDI
          (edifVersion 2 0 0)
          (design SCHEMATIC1
            (cell RES (cellType GENERIC)           ← 器件库定义
              (view CAPSYM (viewType NETLIST)
                (interface (port 1 ...) (port 2 ...)))))
            (cell PAGE1 (cellType GENERIC)          ← 原理图页
              (view SCHEMATIC (viewType NETLIST)
                (contents
                  (instance R1                      ← 器件实例
                    (viewRef CAPSYM (cellRef RES))
                    (property VALUE (string "10K"))
                    (property PCB Footprint (string "0603"))))
                  (net N00001                       ← 网络连接
                    (joined
                      (portRef 1 (instanceRef R1))
                      (portRef 2 (instanceRef C1))))))))
        """
        import sexpdata
        tree = sexpdata.loads(edif_path.read_text())
        # 提取: cells→器件库, instances→实例, nets→网络, properties→属性
        ...
```

**EDIF 提供**：器件实例/引脚/网络/属性/层次结构 — 全部逻辑数据，坐标缺失。
**EDIF 不提供**：图形坐标（器件位置、连线路径）。

**实现备注（v1.1.0）**：Windows 路径反斜杠替换（`\` → `/`）避免 sexpdata 解析异常；`extract_pin_net_map()` 静态方法提取 pin→net 映射供 Stage 5.5 注入。HG5015 实测：EDF → 1 页、3023 实例、862 网络。

#### 3.0b DSN ↔ EDIF 交叉验证器

**8 项比对**（`core/parser/cross_validator.py`）：

```python
class CrossValidator:
    """两路解析结果自动比对 — 8 项"""
    
    def validate(self, edif_ir: DesignIR, dsn_ir: DesignIR) -> ValidationReport:
        checks = [
            ("页数", len(edif_ir.pages), len(dsn_ir.pages)),
            ("实例数", len(edif_ir.all_instances), len(dsn_ir.all_instances)),
            ("网络数", len(edif_ir.all_nets), len(dsn_ir.all_nets)),
        ]
        for name, a, b in checks:
            if a != b:
                report.add_error(f"{name}: EDIF={a}, DSN={b}")
        # 第4项: Refdes 交集（逐实例引用比对）
        # 第5项: 逐器件引脚数 (_compare_per_device_pin_counts)
        # 第6项: 网络连接数 (_compare_net_connection_counts)
        # 第7项: 网络拓扑一致性 (_compare_net_connection_consistency, Jaccard 相似度)
        # 第8项: 器件类型分组 (_compare_by_device_type)
        ...
```

> 多源三路比对（DSN/EDIF/PSTXNET，自动降级 2-source）见 `Part I §2.1.1` 与 `core/diagnostics/multi_source.py`。

#### 3.0c PST 辅助数据源（Phase IX）

PST 文件由 OrCAD Capture 的 PSTWRITER 生成，作为 DSN/EDIF 之外的第三数据源，主要服务匹配增强与 pin 连接补充：

| 解析器 | 输入 | 输出 | 用途 |
|--------|------|------|------|
| `PstchipParser` | `pstchip.dat`（LIBRARY_PARTS） | `{symbolic_name → PART_NAME/JEDEC_TYPE/VALUE/pin numbers}` | 向 `ComponentDef.extra_data` 注入 JEDEC 类型与标称值（Phase 1 先验 + Phase 2A 尺寸比对） |
| `PstxnetParser` | `pstxprt.dat`（EXPANDEDPARTLIST） | `{refdes → part_name/section/INSxxx}` | refdes → primitive 映射，桥接 pstxnet.dat 与 EDIF（v0.8.1 支持多行 PART_NAME） |
| `PstxnetNetlistParser` | `pstxnet.dat`（EXPANDEDNETLIST） | `{refdes → {pin → net}}` | pin→net 网络连接补充（Stage 5.5b 主数据源；DSN/EDIF 网络缺失时的兜底） |

> 注入路径：`ConversionEngine._stage_match` 注入 PST JEDEC 到 `extra_data`；`_stage_generate` 中 Stage 5.5（EDIF pin 注入）与 Stage 5.5b（PSTXNET pin 注入，Primary）共同补齐 `pin_connections`。

#### 3.1 Binary DSN Parser（路径 B — Phase I-B 主力）

```python
# 三层解析架构
##############################################################################
# Layer 1: OleReader — CFB 容器层
##############################################################################

OLE_MAGIC = bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1])
HEADER_SIZE = 512
DIR_ENTRY_SIZE = 128
ENDOFCHAIN = 0xFFFFFFFE
FREESECT = 0xFFFFFFFF
NOSTREAM = 0xFFFFFFFF

class OleReader:
    """MS-CFB 复合文件读取器
    
    构造时自动解析: 头部→FAT→目录树→miniFAT→miniStream
    """
    
    def __init__(self, file_path: Path):
        self.buffer = file_path.read_bytes()
        self._validate_magic()
        self.header = self._parse_header()
        self.fat = self._build_fat()
        self.directories = self._read_directories()
        self.mini_fat = self._build_mini_fat()
        self.mini_stream = self._read_mini_stream()
    
    def list_all_entries(self) -> list[OlePathEntry]:
        """返回所有层级路径的条目列表"""
        ...
    
    def read_stream_by_path(self, path: str) -> bytes:
        """按层级路径读取流: 'Views/SCHEMATIC1/Pages/PAGE1'"""
        ...
    
    def read_stream(self, name: str) -> bytes:
        """按名称读取流 (扁平查找, 仅type=2)"""
        ...


##############################################################################
# Layer 2: BinaryReader — 类型化二进制读取
##############################################################################

class BinaryReader:
    """位置跟踪的二进制 Buffer 读取器。从 DataStream.cpp 移植。
    
    所有整数读取方法均为 little-endian。
    """
    
    def __init__(self, buffer: bytes, offset: int = 0):
        self._buf = buffer
        self._pos = offset
    
    def tell(self) -> int: ...
    def seek(self, offset: int): ...
    def skip(self, n: int): ...
    def peek(self, n: int) -> bytes: ...
    def is_eof(self) -> bool: ...
    
    def read_uint8(self) -> int: ...
    def read_uint16(self) -> int: ...
    def read_uint32(self) -> int: ...
    def read_int8(self) -> int: ...
    def read_int16(self) -> int: ...
    def read_int32(self) -> int: ...
    
    def read_bytes(self, n: int) -> bytes: ...
    def read_string_zero_term(self) -> str: ...
    def read_string_len_term(self) -> str: ...
    def read_string_len_zero_term(self) -> str: ...


##############################################################################
# Layer 3: DSN Structure Parsers — 结构体解析
##############################################################################

class StructureType(IntEnum):
    Page = 10
    PlacedInstance = 13
    T0x10 = 16
    WireScalar = 20
    WireBus = 21
    Port = 23
    LibraryPart = 24
    Package = 31
    Device = 32
    Global = 37
    OffPageConnector = 38
    SymbolDisplayProp = 39
    Alias = 49

# 通用解析框架
PREAMBLE_MAGIC = bytes([0xFF, 0xE4, 0x5C, 0x39])
PREAMBLE_STRIDE = 9

class FutureDataList:
    """结构体检查点边界追踪器 (移植自 C++ FutureData)"""
    
    def __init__(self, reader: BinaryReader): ...
    def push(self, preamble_offset: int, size: int): ...
    def checkpoint(self): ...  # 验证当前位置
    def read_rest_of_structure(self): ...  # 跳过剩余
    def get_max_stop_offset(self) -> int: ...

def read_preamble(reader: BinaryReader) -> None:
    """读取并验证结构体前导码 FF E4 5C 39 + offset + unknown"""
    magic = reader.read_bytes(4)
    if magic != PREAMBLE_MAGIC:
        raise ParseError(f"Expected preamble, got {magic.hex()}")
    reader.skip(4)  # offset
    reader.skip(4)  # unknown

def auto_read_prefixes(reader: BinaryReader, future_data: FutureDataList,
                       expected_type: StructureType | None = None):
    """自动读取结构体前缀链"""
    ...

# 各结构体解析函数 (严格的字节级实现)
def parse_symbol_display_prop(reader: BinaryReader) -> SymbolDisplayProp:
    """Type=39"""
    future_data = FutureDataList(reader)
    auto_read_prefixes(reader, future_data, StructureType.SymbolDisplayProp)
    read_preamble(reader)
    future_data.checkpoint()
    
    name_idx = reader.read_uint32()
    x = reader.read_int16()
    y = reader.read_int16()
    rot_font = reader.read_uint16()
    text_font_idx = rot_font & 0x3FFF
    rotation = rot_font >> 14
    prop_color = reader.read_uint8()
    reader.skip(2)  # visibility
    reader.skip(1)  # 0x00
    
    future_data.checkpoint()
    return SymbolDisplayProp(name_idx, x, y, text_font_idx, rotation, prop_color)

def parse_t0x10(reader: BinaryReader) -> T0x10:
    """Type=16 — 引脚到网络的关键连接点"""
    future_data = FutureDataList(reader)
    auto_read_prefixes(reader, future_data, StructureType.T0x10)
    read_preamble(reader)
    future_data.checkpoint()
    
    sth = reader.read_uint16()
    pin_index = sth if sth < 32768 else 65536 - sth  # 2's complement
    point_x = reader.read_int16()
    point_y = reader.read_int16()
    net_id = reader.read_uint32()
    reader.skip(4)
    
    sdps = [parse_symbol_display_prop(reader) 
            for _ in range(reader.read_uint16())]
    
    future_data.checkpoint()
    return T0x10(pin_index, point_x, point_y, net_id, sdps)

def parse_placed_instance(reader: BinaryReader) -> PlacedInstance:
    """Type=13 — 原理图上的每个器件"""
    future_data = FutureDataList(reader)
    prefix_props = auto_read_prefixes(reader, future_data,
                                       StructureType.PlacedInstance)
    read_preamble(reader)
    future_data.checkpoint()
    
    reader.skip(8)
    pkg_name = reader.read_string_len_zero_term()
    db_id = reader.read_uint32()
    reader.skip(8)
    loc_x = reader.read_int16()
    loc_y = reader.read_int16()
    reader.skip(4)
    
    sdps = [parse_symbol_display_prop(reader) 
            for _ in range(reader.read_uint16())]
    reader.skip(1)
    future_data.checkpoint()
    
    reference = reader.read_string_len_zero_term()  # ← 位号!
    part_value_idx = reader.read_uint32()
    reader.skip(10)
    
    t0x10s = [parse_t0x10(reader) 
              for _ in range(reader.read_uint16())]
    future_data.checkpoint()
    
    source_package = reader.read_string_len_zero_term()
    reader.skip(2)
    future_data.checkpoint()
    
    return PlacedInstance(pkg_name, db_id, reference, source_package,
                          part_value_idx, loc_x, loc_y, sdps, t0x10s,
                          prefix_props)

def parse_wire(reader: BinaryReader) -> Wire:
    """Type=20/21 — 线段"""
    ...
    return Wire(segment_id, wire_id, start_x, start_y, end_x, end_y, aliases)

def parse_package(reader: BinaryReader) -> Package:
    """Type=31 — 器件封装定义"""
    ...
    return Package(name, ref_des, pcb_footprint, devices)

def parse_device(reader: BinaryReader) -> Device:
    """Type=32 — 含 pinMap 的器件定义"""
    ...
    return Device(unit_ref, ref_des, pin_map)

def parse_global(reader: BinaryReader) -> GraphicInst:
    """Type=37 — 全局信号标记(VCC/GND)"""
    ...
    return GraphicInst(name, db_id, loc_x, loc_y, ..., pairing_id, sdps)

def parse_port(reader: BinaryReader) -> GraphicInst:
    """Type=23 — 端口"""
    ...
    return GraphicInst(...)

def parse_off_page_connector(reader: BinaryReader) -> GraphicInst:
    """Type=38 — 跨页连接器"""
    ...
    return GraphicInst(...)


##############################################################################
# DSN Parser 顶层调度器
##############################################################################

class DSNParser(ParserBase):
    FORMAT_NAME = "CIS_DSN"
    FILE_EXTENSIONS = [".dsn"]
    
    def parse(self, dsn_path: Path) -> DesignIR:
        """v1.1.0 实际管道：
        OleReader → strLst 加载 → Cache 解析 → 页面流发现 → 页面解析 →
        层次块展开 → IR 构建 → EDIF 类型映射
        """
        ole = OleReader(dsn_path)
        entries = ole.list_all_entries()
        
        # 0. 页面流发现（含回退路径）：
        #    主路径：CFB 树 Pages/ 下流条目
        #    回退路径：len(pages) < ole.count_page_candidates() 时，
        #      扫描 raw entries（PAGE 前缀 / VRTL 包含 / ^\d{2,3}- 编号模式）
        #    → 详见 Part I §2.1.1
        
        # 1. 解析 Hierarchy 流 → 规范网络名
        hier_entry = self._find_hierarchy(entries)
        canonical_nets = self._parse_hierarchy(ole, hier_entry)
        
        # 2. 解析所有 Page 流
        #    页面二进制解析：parse_page(buffer, page_id, strlst)
        #    PlacedInstance 双格式：标准内联（uint16 长度前缀）/ RTL strLst 索引
        #    虚假实例过滤：db_id == 0 跳过
        pages = []
        for entry in self._find_pages(entries):
            buffer = ole.read_stream_by_path(entry.path)
            pages.append(parse_page(buffer, entry.name, str_lst))
        
        # 3. 解析 Package 流 → pinMap
        pmd = PinMapData()
        cached_parts = {}
        for entry in self._find_packages(entries):
            buffer = ole.read_stream_by_path(entry.path)
            pkg, lib_parts = parse_package_stream(buffer)
            self._index_pin_maps(pmd, entry.path, pkg)
            self._index_cached_parts(cached_parts, lib_parts)
        
        # 4. 解析 Cache 流 → Package/LibraryPart/Device
        #    ⚠️ 字符串用 uint16 长度前缀（不是 uint32）
        #    HG5015 实测：39 packages / 47 components
        cache_parts = self._parse_cache(ole, entries)
        
        # 5. 解析 Library 流 → strLst 字符串表
        #    parse_strlst：HG5015 实测 5490 条；GBK 回退
        str_lst = self._parse_library(ole, entries)
        
        # 6. 构建 Component 详情 (pin names, values, nets)
        components = build_components(pages, component_pins, str_lst,
                                       cache_parts, pmd, device_index_map)
        
        # 7. 构建 Net 连通性
        nets = build_net_connectivity(pages, str_lst, canonical_nets)
        
        return self._assemble_design_ir(components, nets, pages, str_lst)
```

> 二进制解析算法要点（OleReader `count_page_candidates()` 回退规则、`parse_strlst` 逐字节步骤、Cache uint16 陷阱、RTL 虚假实例过滤、EDIF 3023 实例、CrossValidator 8 项比对、MultiSourceCrossValidator）见 **`Part I §2.1.1`**（唯一正式归宿，本节不重复展开）。

#### 3.2 HDL 器件库扫描

**输出统一 `ComponentDB`**（v1.1.0；旧版 `HDLComponentDB` 已废弃——CIS 与 HDL 器件共用同一 Schema，见 Part III §2）。

```python
class HDLLibScanner:
    """扫描 HDL 器件库目录，建立统一 ComponentDB"""
    
    def scan(self, lib_root: Path) -> ComponentDB:
        db = ComponentDB()
        for part_dir in self._iter_part_dirs(lib_root):
            component = ComponentDef(...)
            # 每器件目录三文件：
            #   chips.prt     → 引脚定义（PIN_NUMBER PIN_NAME TYPE）
            #   symbol.css    → 符号图形定义
            #   part.ptf      → 器件属性（Value/Footprint/BOM_SEQ/SN_NUM）
            chips = self._parse_chips_prt(part_dir / "chips/chips.prt")
            symbol = self._parse_symbol_css(part_dir / "sym_1/symbol.css")
            props = self._parse_part_ptf(part_dir / "part_table/part.ptf")
            ...
            db.add(component)
        return db
    
    def _parse_chips_prt(self, path: Path) -> list[PinDef]: ...
    def _parse_symbol_css(self, path: Path) -> SymbolLayoutIR: ...
    def _parse_part_ptf(self, path: Path) -> dict: ...
```

> 编码/递归/排除目录由 `ConversionEngine.scan_hdl_library()` 从全局 Config 读取（`chips_prt_encoding`/`symbol_css_encoding`/`part_ptf_encoding`/`recursive_scan`/`exclude_dirs`）。
<!-- 合并注记：原 BACKEND_DESIGN.md §3.2 末尾存在游离 ``` 围栏标记（源文档格式化缺陷，代码块已于前一行关闭），合并时移除该游离围栏，以免 §4 起正文被渲染为代码块；原文内容未删减。 -->

---

### 4. 匹配层实现

#### 4.1 设计原则

- **匹配在 IR 层进行**：输入输出都是 `ComponentDef`，不感知数据来源格式
- **v2.0 两阶段架构**：Phase 1 类型假设生成 → Phase 1.5 候选池构建 → Phase 2A/2B 类型内匹配（被动确定性规则 / 主动加权评分）
- **final_conf = phase1_prior × phase2_within**；`STOP_SEARCH=0.75` / `NEEDS_REVIEW=0.40`
- **MultiScorer 已删除**：跨类型加权评分被证明结构上不可靠，前缀是硬约束而非软权重
- 详见 Part III §4

#### 4.2 匹配管道（v2.0 两阶段）

```python
class MatcherPipeline:
    """v2.0 两阶段匹配管道（core/matcher/pipeline.py）"""

    def __init__(self):
        self._passive_matcher = PassiveMatcher()   # Phase 2A
        self._active_matcher = ActiveMatcher()     # Phase 2B
        self._manual = ManualMatchResolver()

    def run_batch(self, sources: list[ComponentDef],
                  db: ComponentDB) -> list[MatchResult]:
        """对每个 source：
        1. Phase 1: TypeHypothesisGenerator.generate(refdes, value, pst_data)
                    → 有序类型假设（prior ∈ [0.05, 1.0]）
        2. Phase 1.5: CandidatePoolBuilder.build(hypotheses)
                    → 按类型过滤的候选池，prior 降序
        3. Phase 2: 按类型池优先级搜索
           - 被动类型（capacitor/resistor/inductor/diode/zener/ferrite_bead/led）
             → PassiveMatcher 确定性 5 级
           - 主动类型（IC/connector/crystal/...）
             → ActiveMatcher 类型内 5 维评分
        4. final_conf = type_set.prior_conf × phase2_result.confidence
        5. 提前停止：PASSIVE_EXACT / 固定前缀命中 / final_conf ≥ 0.75
        6. 全部类型池耗尽 → NEEDS_REVIEW
        """
        ...
```

**v2.0 关键规则**：

| 规则 | 值 |
|------|----|
| 停止搜索阈值 `STOP_SEARCH` | 0.75 |
| 需人工确认阈值 `NEEDS_REVIEW` | 0.40 |
| 固定前缀 `fixed_prefixes` | `{LB: ferrite_bead, LED: led, FB: ferrite_bead, TP: test_point}` |
| 前缀重映射 | `RD → resistor` |
| Phase 2A 被动确定性 5 级规则（6 档置信度） | conf=1.00 / 0.95 / 0.80 / 0.70 / 0.60 / 0.40 |
| Phase 2B 主动类型内 5 维权重 | footprint:0.30 / value:0.15 / jedec:0.20 / pin_count:0.20 / part_name:0.15（MIN_WITHIN_SCORE=0.50） |
| 类型内 matcher 链 | Exact → Fuzzy → Feature → Value → Fallback |

#### 4.3 历史演进：旧版四级匹配器（v2.0 之前）

> 以下 ExactMatcher / FuzzyNameMatcher / FeatureExtractMatcher 为旧版"四级管道（Exact → Fuzzy → Feature → Manual）"组件。**v2.0 已弃用四级管道**：这些匹配器降级为 `ActiveMatcher` 的类型内 matcher 链（Exact → Fuzzy → Feature → Value → Fallback），不再作为顶层管道阶段。保留如下供历史参考。

```python
class ExactMatcher(MatcherBase):
    MATCHER_NAME = "exact"
    MATCHER_PRIORITY = 1
    
    def match(self, source: ComponentDef, candidates: list[ComponentDef]) -> MatchResult:
        fingerprint = source.fingerprint
        for c in candidates:
            if c.fingerprint == fingerprint:
                return MatchResult(
                    source=source, target=c,
                    confidence=1.0,
                    strategy=MatchStrategy.EXACT,
                )
        return MatchResult.no_match(source)
    
    def confidence_threshold(self) -> float:
        return 0.95
```

```python
from rapidfuzz import fuzz, process

class FuzzyNameMatcher(MatcherBase):
    MATCHER_NAME = "fuzzy"
    MATCHER_PRIORITY = 2
    
    def match(self, source: ComponentDef, candidates: list[ComponentDef]) -> MatchResult:
        names = [c.part_name for c in candidates]
        result = process.extractOne(
            source.part_name, names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=60,
        )
        if result:
            best_name, score, idx = result
            return MatchResult(
                source=source,
                target=candidates[idx],
                confidence=score / 100.0,
                strategy=MatchStrategy.FUZZY,
            )
        return MatchResult.no_match(source)
    
    def confidence_threshold(self) -> float:
        return 0.75
```

```python
import re

class FeatureExtractMatcher(MatcherBase):
    MATCHER_NAME = "feature"
    MATCHER_PRIORITY = 3
    
    # 解析常见无源器件参数
    RES_PATTERN = re.compile(
        r'(?P<value>\d+\.?\d*)\s*(?P<unit>[KM]?)\s*Ω?',
        re.IGNORECASE,
    )
    CAP_PATTERN = re.compile(
        r'(?P<value>\d+\.?\d*)\s*(?P<unit>[pnum]?)\s*F',
        re.IGNORECASE,
    )
    
    def match(self, source, candidates) -> MatchResult:
        features = self._extract(source)
        # 用特征字典比对
        scored = []
        for c in candidates:
            c_features = self._extract(c)
            score = self._feature_similarity(features, c_features)
            scored.append((score, c))
        
        scored.sort(reverse=True)
        if scored and scored[0][0] > 0.6:
            return MatchResult(
                source=source, target=scored[0][1],
                confidence=scored[0][0],
                strategy=MatchStrategy.FEATURE,
            )
        return MatchResult.no_match(source)
    
    def confidence_threshold(self) -> float:
        return 0.60
```

> v2.0 另新增 `ValueMatcher`（part.ptf 电气值匹配，conf≥0.90）与 `FallbackMatcher`（refdes 前缀 + 本体兜底，conf≥0.50），与上述三器共同构成 `ActiveMatcher` 类型内链。

---

### 5. 生成层实现

> **落地位置（v1.1.0）**：生成层实际位于 `core/writer/`（旧设计 `generator/` 已废弃）。已落地写入器：`CPMWriter`（.cpm）、`SCHWriter`（.sch.N.M）、`CSAWriter`（.csa MACRO_DRAWING，当前主输出）、`CDSLibWriter`（cds.lib）、`XconWriter`（.xcon）、`CPCWriter`（.cpc）、`ScrWriter`（.scr）、`MappingCSVWriter`（{project}_mapping.csv）、`OutputManager`（DEHDL 目录树编排）、`ErrorLogger`（{project}_errors）。写入器注册统一在 `core/writer/base.py` 的 `WriterRegistry`；完整清单见 Part I §2.4。

#### 5.1 SCH 文件生成

```python
class SCHWriter(WriterBase):
    """将页面 IR 转换为 .sch.N.M 文件"""
    
    SCH_TEMPLATE = """\
VERSION 6
BEGIN SCHEMATIC
BEGIN ATTR
DeviceFamilyName "allegro"
END ATTR
BEGIN NETLIST
{signal_section}
{block_section}
END NETLIST
BEGIN SHEET {page_id} {width} {height}
{instance_section}
{branch_section}
{iomarker_section}
END SHEET
END SCHEMATIC
"""
    
    def write(self, page: PageIR, output_dir: Path) -> Path:
        content = self.SCH_TEMPLATE.format(
            signal_section=self._build_signals(page),
            block_section=self._build_blocks(page),
            page_id=page.page_id.replace(".", " "),
            width=page.width,
            height=page.height,
            instance_section=self._build_instances(page),
            branch_section=self._build_branches(page),
            iomarker_section=self._build_iomarkers(page),
        )
        
        output_path = output_dir / f"top.sch.{page.page_id}"
        output_path.write_text(content, encoding="ascii")
        return output_path
    
    def _build_signals(self, page: PageIR) -> str:
        lines = []
        for net in page.nets:
            if net.is_bus:
                lines.append(f"SIGNAL {net.name}({len(net.bus_members)-1}:0)")
            else:
                lines.append(f"SIGNAL {net.name}")
        return "\n".join(lines)
    
    def _build_instances(self, page: PageIR) -> str:
        lines = []
        for inst in page.instances:
            # 需要坐标布局算法确定 x, y
            lines.append(f"BEGIN INSTANCE {inst.refdes} {inst.x} {inst.y} R0")
            lines.append(f"END INSTANCE")
        return "\n".join(lines)
    
    # ... 更多辅助方法
```

#### 5.2 坐标布局算法

由于 DSN 中有器件坐标，可直接映射到 SCH 坐标系：

> 坐标映射器 `LayoutMapper` 实际落地于 `core/parser/layout_mapper.py`（ConvertDocToUser 公式：用户坐标 = 文档坐标 × (1.0 / 物理粒度)，见 `RESEARCH.md`（原 `ORCAD_SOURCE_ANALYSIS.md` §10.2 + §13.2））。CSA 输出的坐标映射另有 `core/writer/csa_writer.py._map_coords_to_dehdl()`（BoundingBox 居中缩放 ×0.7 + Y 轴翻转，fallback 网格布局 5 列 × 间距 2000×1500）。

```python
class LayoutMapper:
    """将 CIS 坐标映射到 HDL 网格"""
    
    CIS_TO_HDL_SCALE = 1.0  # 可能需根据实际 DPI 调整
    
    def map_position(self, cis_x: int, cis_y: int) -> tuple[int, int]:
        """CIS 坐标 → HDL 网格坐标"""
        hdl_x = int(cis_x * self.CIS_TO_HDL_SCALE)
        hdl_y = int(cis_y * self.CIS_TO_HDL_SCALE)
        # 对齐到网格
        hdl_x = round(hdl_x / 16) * 16
        hdl_y = round(hdl_y / 16) * 16
        return hdl_x, hdl_y
```

#### 5.3 CPM 文件生成

```python
class CPMWriter(WriterBase):
    """生成 .cpm 项目配置文件"""
    
    def write(self, design: DesignIR, output_dir: Path,
              lib_refs: list[str]) -> Path:
        content = f"""\
START_DESIGN
  DESIGN_NAME "{design.project_name}"
  LIBRARY_NAME "worklib"
  CELL_NAME "{design.project_name}"
END_DESIGN

START_LIBS
{self._build_lib_refs(lib_refs)}
END_LIBS

START_FONTS
  CDS_ENABLE_FONTS 'ON'
END_FONTS
"""
        output_path = output_dir / f"{design.project_name}.cpm"
        output_path.write_text(content)
        return output_path
```

---

### 6. ConversionEngine（主控）

```python
class ConversionEngine:
    """后端主控引擎，前后端唯一接口"""
    
    def __init__(self):
        self.parser_registry = ParserRegistry()
        self.validator_registry = ValidatorRegistry()
        self.writer_registry = WriterRegistry()
        
        # v2.0：匹配走两阶段管道（Phase 1/1.5 在 run_batch 内按批初始化，
        # Phase 2A PassiveMatcher + Phase 2B ActiveMatcher 常驻）
        self.matcher_pipeline = MatcherPipeline()

    # ── 六阶段主流程（v1.1.0 实际方法，core/engine/conversion_engine.py）──
    def diagnose(self, input_files: list[Path]) -> DiagnosticReport:
        """Stage 1/6 — 六阶段诊断管道"""
        return self.diagnostic_pipeline.run(input_files)

    def parse(self, input_path: Path) -> DesignIR:
        """Stage 2/6 — 按扩展名选择解析器（DSN/EDIF/OLB/PST）"""
        parser = self.parser_registry.get_for_file(input_path)
        return parser.parse(input_path)

    def scan_hdl_library(self, lib_path: Optional[Path] = None) -> ComponentDB:
        """Stage 3/6 — 扫描 HDL 库 → 统一 ComponentDB（未传路径时用全局 Config）"""
        ...

    def match(self, design: DesignIR, hdl_db: ComponentDB) -> list[MatchResult]:
        """Stage 4/6 — v2.0 两阶段匹配（内部 _stage_match 注入 PST JEDEC 到 extra_data）"""
        ...

    def validate(self, design: DesignIR,
                 matches: list[MatchResult]) -> list[DiagnosisError]:
        """Stage 5/6 — ValidatorRegistry 按优先级批量校验"""
        ...

    def generate(self, design: DesignIR, matches: list[MatchResult],
                 output_dir: Path) -> ConversionReport:
        """Stage 6/6 — 经 OutputManager 生成 DEHDL 目录结构
        （output_root/<cell>.cpm、cds.lib、worklib/<cell>/sch_1/pageN.csa 等）
        内部包含 Stage 5.5（EDIF pin 注入）与 Stage 5.5b（PSTXNET pin 注入）
        """
        ...

    # ── 一键流程 / 人工裁决 ──
    def convert(self, input_path: Path, output_dir: Path,
                hdl_lib_path: Optional[Path] = None) -> ConversionReport:
        """一键转换：diagnose → parse → scan → match → validate → generate
        自动生成 {project}_mapping.csv 与 {project}_errors.{html,txt}
        """
        ...

    def convert_full(self, input_path: Path, ...) -> ConversionReport:
        """完整流程（含阶段回退/恢复）"""
        ...

    def accept_match(self, source_library_id: str,
                     target_library_id: str) -> MatchResult:
        """接受人工匹配（写入 ManualMatchResolver 规则表）"""
        ...

    # ── 内部六阶段（_stage_diagnose/_stage_parse/_stage_scan/
    #     _stage_match/_stage_validate/_stage_generate）──
    def _stage_match(self): ...
    def _stage_generate(self): ...
```

> CLI 入口：`python -m cis2hdl convert <input> [--output <dir>] [--hdl-lib <dir>] [--benchmark] [--max-workers <n>]`，由 `__main__.py` 调用 `ConversionEngine.convert()`；无参数 / `python -m cis2hdl gui` 启动 GUI。

---

### 7. 诊断与容错管道（已落地 core/diagnostics/）

#### 7.1 设计原则

对标 Cadence Professional 工具的 Project Manager → Check References → DRC 三层验证体系。

- **诊断优先于转换**：任何文件操作之前先运行完整的文件完整性校验
- **用户引导式错误处理**：每个错误/警告/信息都附带可操作的建议
- **降级优于失败**：当部分数据缺失时，给出明确的数据损失标注 + 降级路径
- **结构化输出**：所有诊断信息以 JSON 序列化，前端可渲染为彩色面板

#### 7.2 诊断管道架构

```python
class DiagnosticPipeline:
    """六阶段诊断管道（core/diagnostics/pipeline.py），协调所有诊断模块的顺序执行。
    
    Stage 1: FileInventory          → 每文件状态 (FOUND/MISSING/CORRUPTED)
    Stage 2: ProjectFileValidator   → 三层文件完整性校验
    Stage 3: DependencyResolver     → OLB 引用/层次引用/跨页引用分析
    Stage 4: ReadinessEvaluator     → 四维质量评分 (逻辑/坐标/匹配/符号)
    Stage 5: QualityEstimator       → 转换质量预估 (百分比量化)
    Stage 6: ReportGenerator        → 结构化报告输出 (JSON/HTML/PDF)
    
    任一阶段失败不阻塞后续阶段，所有错误累积到最终报告。
    """
    
    def __init__(self):
        self.file_inventory = FileInventory()
        self.file_validator = ProjectFileValidator()
        self.dependency_resolver = DependencyResolver()
        self.readiness_evaluator = ConversionReadinessEvaluator()
        self.quality_estimator = ConversionQualityEstimator()
        self.report_generator = StructuredReportGenerator()
    
    def run(self, input_files: list[Path]) -> DiagnosticReport: ...
```

#### 7.3 错误诊断引擎（ErrorDiagnosisEngine）

```python
@dataclass
class DiagnosisError:
    """单个诊断错误。对标 Canvas 错误码体系（v1.1 口径 44 条）。"""
    code: int                    # 错误码（v1.1 口径 44 条）
    severity: Severity           # FATAL / ERROR / WARNING / INFO
    category: str                # FILE / PARSE / MATCH / NET / PIN / SYMBOL
    message: str                 # 人可读描述
    detail: str = ""             # 技术细节
    suggestion: str = ""         # 修复建议
    source_file: str = ""        # 相关文件路径
    source_offset: int = 0       # 文件内偏移（如能定位）
    can_ignore: bool = False     # 是否允许用户忽略继续

class ErrorDiagnosisEngine:
    """44 错误码诊断引擎（v1.1 口径，旧版 31 条；39 为漏算 OLB 51-55 的旧口径，现为 44 条）。

    错误码按类别划分（参考 Canvas 错误码 + 扩充）：
    文件级错误 (FILE_MISSING, BAD_FORMAT, VERSION_MISMATCH, CFB_CORRUPT...)
    解析级错误 (PREAMBLE_MISMATCH, STRUCTURE_OVERFLOW, STRLST_INDEX_ERROR...)
    语义级错误 (PIN_NAME_MISSING, NET_NAME_INVALID, HIERARCHY_BROKEN...)
    生成级错误 (SYMBOL_GENERATION_FAILED, FILE_WRITE_ERROR...)

    完整错误码表以 core/diagnostics/error_diagnosis.py 的 ERROR_CODES 为准。
    """
    
    ERROR_CODES: dict[int, DiagnosisError] = {
        1: DiagnosisError(code=1, severity=Severity.FATAL, 
            category="FILE", message="DSN 文件缺失",
            suggestion="请提供 .dsn 原理图主文件"),
        2: DiagnosisError(code=2, severity=Severity.ERROR,
            category="FILE", message="CFB 文件头损坏（无效魔数）",
            suggestion="文件可能已损坏，请尝试从 .dbk 备份恢复"),
        # ... 共 44 条（v1.1 口径，代码 error_diagnosis.py 实注册 44 条）
    }
```

#### 7.4 文件恢复策略（FileRecoveryStrategy）

```python
class FileRecoveryStrategy:
    """多级降级转换路径。
    
    当检测到文件问题时的恢复优先级：
    1. DSN 损坏 → .dbk 备份恢复（零数据损失）
    2. DSN 不可用 → EDIF 逻辑转换（坐标损失，逻辑完整）
    3. DSN 部分损坏 → 跳过损坏页面（部分数据损失）
    4. OLB 缺失 → DSN Cache 嵌入式定义 + 默认符号（符号保真度损失）
    5. 符号缺失 → 通用矩形符号（图形信息损失）
    
    每条路径明确标注：数据损失程度 + 转换质量影响
    """
    
    RECOVERY_PATHS: list[RecoveryPath] = [
        RecoveryPath(
            id="DSN_RECOVER_FROM_BACKUP",
            condition=lambda inv: inv.has_corrupted_dsn and inv.has_backup,
            action="UseBackupDSN",
            data_loss=DataLossLevel.NONE,
            quality_impact="完全恢复，无数据损失"
        ),
        RecoveryPath(
            id="DSN_FALLBACK_TO_EDIF",
            condition=lambda inv: inv.has_corrupted_dsn and inv.has_edif,
            action="UseEDIFLogicOnly",
            data_loss=DataLossLevel.COORDINATES,
            quality_impact="坐标丢失：器件位置/连线路径不可用"
        ),
        # ... 共 5 条路径
    ]
```


## Part III 器件模型与数据库（原 COMPONENT_ARCHITECTURE.md 全文，逐节保留）

> **Part III 来源**: 原 `COMPONENT_ARCHITECTURE.md`（v1.1.0，2026-08-07，564 行）
> **历史边界注记**: 本部分为原 `COMPONENT_ARCHITECTURE.md` 全文，写作于 2026-08-07（v1.1.0 修订：匹配策略 v2.0 两阶段；ComponentDBSerializer 未落地标注）。原文所有句子、代码块、表格均原样保留，仅调整标题层级以适配合并文档结构。
> **重叠注记**: 本部分 §4（匹配层）与 Part I §2.2 / Part II §4 有重叠。重叠原文均保留不动，以 v1.1.0 新口径为准。

### 原文档标题与头部（原文保留）

**原标题**: CIS2HDL 器件库统一架构设计


> 版本: v1.1.0 | 日期: 2026-08-07 | 状态: 修订 | 更新: 匹配策略改为 v2.0 两阶段；ComponentDBSerializer/JSON 持久化标注未落地；IR 模型补充 extra_data 字段说明

---

### 0. 核心结论（回答架构关键问题）

| 问题 | 答案 |
|------|------|
| **CIS 和 HDL 的元件库格式是否统一？** | ❌ **完全不同**。CIS 用 `.olb` 二进制，HDL 用 `.sym`+`.ptf`+`chips.prt` 文本，必须转换 |
| **OLB 内容可以转换吗？** | ✅ 可以。OLB 内部的 Package(31)/Device(32)/LibraryPart(24) 结构包含完整器件定义 |
| **软件可以支持自定义元件吗？** | ✅ 必须支持。用户可在 HDL 库中自由增删 `.sym`/`.ptf`/`chips.prt` |
| **可以读取和存储元件吗？** | ✅ `HDLLibScanner` 读取 HDL 库 → 统一 `ComponentDB`（CIS 与 HDL 共用 Schema），CIS 侧从 .dsn Cache 提取 |
| **是否每个元件一套实现？** | ❌ **绝对不行**。所有器件在 IR 层统一为 `ComponentIR`，不按格式/类型分叉 |

---

### 1. CIS 和 HDL 器件库格式差异

#### 1.1 格式对比

```
┌─────────────────────────────────────────────────────────────────────┐
│                    器件库格式差异全景                                 │
├──────────┬──────────────────────────┬───────────────────────────────┤
│          │  CIS (.OLB)              │  HDL (.sym / .ptf / chips.prt)│
├──────────┼──────────────────────────┼───────────────────────────────┤
│ 文件结构  │ 单一 .olb 二进制文件      │ 每个器件一个目录，内含多个文本  │
│          │ (CFB 容器)               │ 文件                          │
├──────────┼──────────────────────────┼───────────────────────────────┤
│ 符号定义  │ 二进制 Package(31)        │ symbol.css（文本）             │
│          │ + Device(32) 结构        │                               │
├──────────┼──────────────────────────┼───────────────────────────────┤
│ 引脚定义  │ Device.pinMap[]          │ chips.prt（文本）              │
│          │ CachedLibraryPart.pinNames│                               │
├──────────┼──────────────────────────┼───────────────────────────────┤
│ 属性表   │ PlacedInstance.properties │ part.ptf（文本）               │
│          │ + strLst 字符串表         │                               │
├──────────┼──────────────────────────┼───────────────────────────────┤
│ 图形坐标  │ PlacedInstance.locX/Y     │ symbol.css 中定义             │
│          │ SymbolDisplayProp.x/y    │                               │
│          │ T0x10.pointX/Y           │                               │
├──────────┼──────────────────────────┼───────────────────────────────┤
│ 库索引   │ 无（嵌入在 .dsn 中）       │ cds.lib DEFINE 语法           │
└──────────┴──────────────────────────┴───────────────────────────────┘
```

#### 1.2 OLB 内部结构（代码验证）

OLB 和 DSN 使用**完全相同的 CFB 容器格式**，内部结构也一致（已验证于 OpenOrCadParser Database.hpp）。`dsn-parser.ts` 和 `cache-parser.ts` 的实现支持两类文件类型检测：

```typescript
// 来源: discovery.ts
private static isDSNFile(filePath: string): boolean {
    return path.extname(filePath).toLowerCase() === '.dsn';
}

private static isOLBFile(filePath: string): boolean {
    return path.extname(filePath).toLowerCase() === '.olb';
}
```

两者的解析流程完全相同：**OleReader → Cache Stream → Package(31) + Device(32) + LibraryPart(24)**。

#### 1.3 HDL 库内部结构（来自实践项目分析）

```
hdl_lib/{器件名}/
├── sym_1/
│   └── symbol.css          ← 符号图形定义
├── chips/
│   └── chips.prt           ← 引脚定义: PIN_NUMBER PIN_NAME TYPE (INPUT/OUTPUT...)
├── part_table/
│   └── part.ptf            ← 器件属性表: Value, Footprint, BOM_SEQ, SN_NUM
├── metadata/
│   └── pinlist.txt         ← 引脚列表（可选）
└── ...其他检查文件
```

---

### 2. 统一器件数据模型（单一数据源设计）

#### 2.1 核心原则：一个 ComponentIR 统治所有格式

**所有格式的器件在进入 IR 层后，使用完全相同的 Python 类，绝不按格式分叉。**

```python
# cis2hdl/core/ir/component.py

from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional

class ElectricalType(str, Enum):
    """统一的电气类型枚举 — 所有格式共用"""
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    BIDIR = "BIDIR"
    POWER = "POWER"
    GROUND = "GROUND"
    PASSIVE = "PASSIVE"
    NC = "NC"
    TRI_STATE = "TRI_STATE"
    OPEN_COLLECTOR = "OPEN_COLLECTOR"

class PinDef(BaseModel):
    """统一的引脚定义 — 所有格式的引脚都映射为此类型"""
    number: str                          # 引脚编号（物理引脚）
    name: str = ""                       # 引脚名称（逻辑引脚名）
    type: ElectricalType = ElectricalType.PASSIVE
    is_power: bool = False               # 是否为电源引脚
    position: Optional[tuple[float, float]] = None  # 符号中坐标

class ComponentDef(BaseModel):
    """统一的器件库定义 — CIS 库 和 HDL 库 统一为此结构
    
    这个类代表"器件库中的定义"，不是"页面上的实例"。
    ComponentInstanceIR 引用此定义。
    """
    # 身份标识
    library_id: str                      # 库内唯一ID（CIS: pkgName, HDL: 目录名）
    part_name: str                       # 器件名
    
    # 分类
    category: str = ""                   # 器件大类（capacitor/resistor/IC/connector...）
    
    # 封装
    footprint: str = ""                  # PCB 封装名
    footprint_alt: list[str] = Field(default_factory=list)  # 备用封装
    
    # 电气
    pins: list[PinDef] = Field(default_factory=list)
    pin_count: int = 0
    
    # 属性
    value: str = ""                      # 标称值（如 "10K", "100nF"）
    tolerance: str = ""                  # 精度（如 "5%", "1%"）
    mpn: str = ""                        # Manufacturer Part Number
    description: str = ""                # 器件描述
    
    # BOM（公司规范）
    bom_seq: str = ""                    # 自动生成: A(贴片)+A(电容)+01(0402)
    sn_num: str = ""                     # 物料编号
    
    # 多 Section 支持
    sections: int = 1                    # 多 Part 器件的 section 数（如 74HC00 有4个）
    section_pin_maps: dict[int, list[str]] = Field(default_factory=dict)  # section → pin 列表
    
    # 符号图形（可选，仅 CIS 有或 HDL symbol.css 导入时填写）
    symbols: list[dict] = Field(default_factory=list)
    
    # 来源追踪
    source_format: str = ""              # "CIS_OLB" / "HDL_LIB" / "CUSTOM"
    source_file: str = ""                # 来源文件路径
    
    # 匹配辅助字段（v2.0 新增，可扩展容器）
    extra_data: dict[str, str] = Field(default_factory=dict)
    #   常见键：
    #   - cis_value: str           CIS 原始标称值（如 "10UF"）
    #   - suggested_primitive: str 建议图元（如 "C_SC0603-TD_10UF"）
    #   - pst_jedec_type: str      PST 注入的 JEDEC 类型（如 "HSC0201-HDTA"）
    #   - pst_part_name: str       PST 注入的器件名
    #   - pst_value: str           PST 注入的标称值
    #   匹配器（PassiveMatcher/ActiveMatcher）通过 extra_data 读取注入信息，
    #   不修改核心字段；Phase 1 类型假设亦消费 pst_jedec_type/pst_part_name。
    
    @property
    def fingerprint(self) -> str:
        """匹配指纹：封装 + 值 + 引脚数"""
        return f"{self.footprint}|{self.value}|{self.pin_count}"


class ComponentInstanceIR(BaseModel):
    """统一的器件实例 — 原理图页面上的一个器件
    
    与 ComponentDef 分离：ComponentDef 是"库中的定义"，
    ComponentInstanceIR 是"页面上的一个具体实例"。
    多个实例可引用同一个 ComponentDef。
    """
    refdes: str                          # 位号 "R1", "U3"
    library_id: str                      # 引用 ComponentDef.library_id
    section: int = 1                     # 多 Section 器件的 section 编号
    
    # 页面坐标
    loc_x: int = 0
    loc_y: int = 0
    rotation: int = 0                    # 0, 90, 180, 270
    
    # 属性覆盖（实例级别可覆盖库定义中的属性）
    value_override: str = ""             # 如库定义中 value 为空，此处可填写
    properties: dict[str, str] = Field(default_factory=dict)
    
    # 引脚连接
    pin_connections: dict[str, str] = Field(default_factory=dict)  # pin_number → net_name
```

#### 2.2 为什么不是每个格式一套类

```
❌ 错误做法（会导致数据库管理混乱）：
   320 个器件类型 × 2 种格式 = 640 个类，完全失控

✅ 正确做法（本项目采用，已通过 Cadence TCL API 验证）：
   DBO 对象层次（Cadence 内部）：Design→Schematics→Pages→PartInsts/Wires/Globals/Ports...
   其中 PartInsts 统一用 ObjectType 31 (Package) 管理，不按器件类型分叉
   → 我们的 ComponentDef 完全复制此模式
```

#### 2.3 CDS 属性系统参考（来自 capDB/cdsprop.txt）

HDL 设计中的属性分为 5 大类（解析层需支持这些属性的映射）：

**电气属性**：ALLOW_CONNECT, BIDIRECTIONAL, DIR, DELAY, RISE, FALL, INPUT_LOAD, OUTPUT_LOAD

**物理属性**：LOCATION, LOCATION_CLASS, XY, ROT, SEC

**设计属性**：MODEL, PART_NUMBER, PHYS_DES_PREFIX, VALUE, VER, GROUP, ROOM

**显示属性**：5 种模式（0=不显示, 1=仅值, 2=名和值, 3=仅名, 4=有值时显示名和值）

**属性继承规则**：`inherit(body/pin/signal)`, `permit(body/pin/signal)`

#### 2.4 ISCF 网络分类模型（来自 Cadence 内部交换格式）

Cadence 内部将网络分为 4 类（ISCF 格式定义），直接影响我们的 `NetIR` 设计：

```python
class NetCategory(str, Enum):
    FLAT = "FLAT"          # 普通信号网络 → ISCF BEGIN_NETS
    GROUND = "GROUND"      # 地网络 → ISCF BEGIN_GROUND
    POWER = "POWER"        # 电源网络 → ISCF BEGIN_POWER
    BUS = "BUS"            # 总线 → ISCF BEGIN_BUSES

class NetIR(BaseModel):
    name: str
    category: NetCategory = NetCategory.FLAT      # ← 基于 ISCF 分类
    connections: list[NetConnection] = Field(default_factory=list)
    is_bus: bool = False
    bus_members: list[str] = Field(default_factory=list)
```

---

### 3. 器件数据库设计（统一管理）

#### 3.1 两个数据库，一个 Schema

```python
# cis2hdl/core/db/component_db.py

from typing import Optional
from pathlib import Path

class ComponentDB:
    """统一的器件数据库 — 可容纳 CIS 和 HDL 两种来源的器件"""
    
    def __init__(self):
        self._by_library_id: dict[str, ComponentDef] = {}
        self._by_part_name: dict[str, list[ComponentDef]] = {}  # 同名可能有多个
        self._by_footprint: dict[str, list[ComponentDef]] = {}
        self._by_category: dict[str, list[ComponentDef]] = {}
    
    def add(self, component: ComponentDef) -> None:
        """添加器件定义"""
        self._by_library_id[component.library_id] = component
        self._by_part_name.setdefault(component.part_name, []).append(component)
        self._by_footprint.setdefault(component.footprint, []).append(component)
        self._by_category.setdefault(component.category, []).append(component)
    
    def get_by_library_id(self, library_id: str) -> Optional[ComponentDef]:
        """精确查找"""
        return self._by_library_id.get(library_id)
    
    def search(self, part_name: str = "", footprint: str = "",
               category: str = "", pin_count: int = 0) -> list[ComponentDef]:
        """多条件搜索"""
        candidates = set()
        if part_name:
            for name, comps in self._by_part_name.items():
                if part_name.lower() in name.lower():
                    candidates.update(comps)
        if footprint:
            candidates &= set(self._by_footprint.get(footprint, []))
        if category:
            candidates &= set(self._by_category.get(category, []))
        if pin_count:
            candidates = {c for c in candidates if c.pin_count == pin_count}
        return list(candidates)
    
    def list_all(self) -> list[ComponentDef]:
        return list(self._by_library_id.values())
    
    def stats(self) -> dict:
        return {
            "total": len(self._by_library_id),
            "categories": {k: len(v) for k, v in self._by_category.items()},
        }


# 全局单例（按需创建，不强制全局变量）
# cis_db: ComponentDB  → 从 CIS .dsn 的 Cache 流提取
# hdl_db: ComponentDB → 从 HDL 库目录扫描
```

> ⚠️ **持久化现状（v1.1.0）**：`core/db/` 目前仅实现 `component_db.py`（内存数据库 + 索引）。§5.2 的 `ComponentDBSerializer`（JSON 保存/加载/合并，`persistence.py`）**未落地**——当前组件库在每次转换时由 `HDLLibScanner.scan()` 从 HDL 库目录重建，不依赖磁盘持久化。若需缓存加速，可参考 §5.2 设计实现。

#### 3.2 数据来源

```
┌─────────────────────────────────────────────────────────┐
│  器件数据来源与流向                                       │
├────────────────────┬────────────────────────────────────┤
│  CIS 侧             │  HDL 侧                            │
│                     │                                    │
│  .dsn               │  hdl_lib/                          │
│  └─ Cache Stream    │  ├── capacitor/                    │
│     ├─ Package(31)  │  │   ├── chips.prt  ──→ PinDef[]  │
│     │  └─ refDes    │  │   ├── symbol.css                │
│     │  └─ footprint │  │   └── part.ptf                 │
│     │  └─ devices[] │  │       └─→ ComponentDef          │
│     │     └─ pinMap │  │   （value, footprint, bom_seq）  │
│     ├─ Device(32)   │  ├── resistor/                     │
│     │  └─ unitRef   │  └── ...（135 个目录）              │
│     │  └─ pinMap[]  │                                    │
│     └─ LibraryPart  │          ↓                         │
│        └─ pinNames  │  HDLLibScanner.parse()             │
│        └─ defaultVal│          ↓                         │
│            ↓        │  ComponentDB(hdl)                  │
│  ComponentDB(cis)   │                                    │
│                     │  ┌────────────────────┐            │
│                     └──│    Matcher Pipeline │            │
│                        │  (CIS ↔ HDL 匹配)  │            │
│                        └────────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

---

### 4. 匹配层设计（基于统一模型）

#### 4.1 匹配在 IR 层进行

因为 CIS 和 HDL 的器件都已映射为 `ComponentDef`，匹配器**不需要知道数据来源**（v2.0 两阶段架构，`core/matcher/pipeline.py`）：

```python
class MatcherPipeline:
    """v2.0 两阶段匹配管道 — 所有匹配器的输入/输出都是 ComponentDef

    Phase 1:  TypeHypothesisGenerator — refdes 前缀 + PST + value + 学习先验
              → 有序类型假设（prior_conf ∈ [0.05, 1.0]）
    Phase 1.5: CandidatePoolBuilder — 按类型假设过滤 HDL 候选池
    Phase 2A: PassiveMatcher — 被动器件确定性规则 5 级级联
    Phase 2B: ActiveMatcher — 主动器件类型内 5 维加权评分
    final_conf = phase1_prior_conf × phase2_within_conf
    STOP_SEARCH = 0.75 ｜ NEEDS_REVIEW = 0.40
    """

    def run_batch(self, sources: list[ComponentDef],
                  db: ComponentDB) -> list[MatchResult]:
        # 每个 source：生成类型假设 → 构建候选池 → 按优先级搜索
        # 被动类型走 PassiveMatcher（确定性规则）
        # 主动类型走 ActiveMatcher（类型内评分）
        # final_conf ≥ 0.75 或命中 PASSIVE_EXACT/固定前缀 → 提前停止
        # 全部类型池耗尽 → NEEDS_REVIEW
        ...
```

#### 4.2 匹配策略（v2.0 两阶段）

| 阶段 | 组件 | 策略 | 关键参数 |
|:----:|------|------|---------|
| Phase 1 | `TypeHypothesisGenerator` | refdes 前缀 → YAML 类型规则 → PST JEDEC 提升 → value 提示 → 学习先验（`PrefixAffinityCalculator`） | prior ∈ [0.05, 1.0]；`type_gate.yaml` |
| Phase 1.5 | `CandidatePoolBuilder` | 按类型假设过滤 HDL 候选池 | 按 prior_conf 降序 |
| Phase 2A | `PassiveMatcher` | 被动器件（C/R/L/D/FB/LED）确定性规则 5 级级联（6 档置信度；值/尺寸布尔约束，非加权评分） | conf=1.00(值+尺寸双精确) / 0.95(多候选 JEDEC tiebreak) / 0.80(值精确尺寸未知) / 0.70(值精确尺寸近似) / 0.60(尺寸精确值近似) / 0.40(前缀兜底) |
| Phase 2B | `ActiveMatcher` | 主动器件（IC/连接器/晶振…）类型内 matcher 链（Exact→Fuzzy→Feature→Value→Fallback）+ 5 维加权评分 | footprint:0.30 / value:0.15 / jedec:0.20 / pin_count:0.20 / part_name:0.15；MIN_WITHIN_SCORE=0.50 |
| 收尾 | `ManualMatchResolver` | 自动匹配失败 → GUI 人工确认；支持规则持久化（YAML） | strategy=MANUAL |

**v2.0 关键规则**：

- **final_conf = phase1_prior × phase2_within**；`final_conf ≥ STOP_SEARCH(0.75)` 或命中 `PASSIVE_EXACT` 即提前停止；`< NEEDS_REVIEW(0.40)` 判为 `NEEDS_REVIEW`
- **固定前缀绑定** `fixed_prefixes = {LB: ferrite_bead, LED: led, FB: ferrite_bead, TP: test_point}`；`RD → resistor`
- **MultiScorer 已删除**：跨类型加权评分被证明结构上不可靠（前缀是硬约束而非软权重）
- 旧版四级管道（Exact → Fuzzy → Feature → Manual）已被 v2.0 两阶段取代，Exact/Fuzzy/Feature 在 v2.0 中作为 ActiveMatcher 类型内链组件；历史描述见 Part II §4.3

---

### 5. 自定义元件支持

#### 5.1 用户自定义元件流程

```
用户操作:
1. 在 HDL 库目录中创建新目录: hdl_lib/my_custom_led/
2. 创建文件:
   ├── chips.prt    ← 手工编辑引脚定义
   ├── symbol.css   ← 手工定义图形符号
   └── part.ptf     ← 手工填写属性

工具操作:
3. HDLLibScanner → 自动扫描新目录 → 加入 ComponentDB
4. Matcher → 自动识别新器件名，尝试匹配
```

#### 5.2 元件数据库持久化

> ⚠️ **未落地（v1.1.0）**：`cis2hdl/core/db/persistence.py` 尚未实现，`core/db/` 仅含 `component_db.py`。以下为**设计参考**（规划未实施），当前组件库由 `HDLLibScanner.scan()` 每次从 HDL 库目录重建，不依赖磁盘持久化。

```python
# cis2hdl/core/db/persistence.py   ← 规划未实施（设计参考）

import json
from pathlib import Path

class ComponentDBSerializer:
    """器件数据库 JSON 序列化 — 支持保存/加载/合并"""
    
    @staticmethod
    def save(db: ComponentDB, path: Path) -> None:
        data = [comp.model_dump() for comp in db.list_all()]
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    
    @staticmethod
    def load(path: Path) -> ComponentDB:
        db = ComponentDB()
        data = json.loads(path.read_text())
        for item in data:
            db.add(ComponentDef(**item))
        return db
    
    @staticmethod
    def merge(target: ComponentDB, source: ComponentDB) -> ComponentDB:
        """合并两个数据库（自定义库 + 标准库）"""
        for comp in source.list_all():
            if comp.library_id not in target._by_library_id:
                target.add(comp)
        return target
```

---

### 6. 解析器与写入器注册架构

#### 6.1 基类-注册模式

```python
# cis2hdl/core/parser/base.py

from abc import ABC, abstractmethod
from pathlib import Path

class ParserBase(ABC):
    FORMAT_NAME: str = ""
    FILE_EXTENSIONS: list[str] = []
    
    @abstractmethod
    def parse(self, path: Path) -> DesignIR:
        ...

class ParserRegistry:
    _parsers: dict[str, ParserBase] = {}
    
    @classmethod
    def register(cls, parser: ParserBase):
        cls._parsers[parser.FORMAT_NAME] = parser
    
    @classmethod
    def get_for_file(cls, path: Path) -> ParserBase:
        ext = path.suffix.lower()
        for parser in cls._parsers.values():
            if ext in parser.FILE_EXTENSIONS:
                return parser
        raise ValueError(f"No parser for {ext}")

# 注册（在 __init__.py 中自动执行）
ParserRegistry.register(EDIFParser())        # .edf
ParserRegistry.register(DSNParser())         # .dsn
ParserRegistry.register(HDLNetlistParser())  # pstx*.dat (可选)
```

#### 6.2 解析器清单

| 解析器 | 输入 | 输出 | 器件提取方式 |
|--------|------|------|-------------|
| `EDIFParser` | `.edf` | `DesignIR` | S-expression 提取 cell/instance/pin/net；后期承担 pin 连接注入（Stage 5.5） |
| `DSNParser` | `.dsn` | `DesignIR` | OleReader → Cache Stream → Package(31)+Device(32)+LibraryPart(24) → ComponentDef[] |
| `HDLLibScanner` | HDL 库目录 | `ComponentDB` | 文本解析 chips.prt + symbol.css + part.ptf → ComponentDef[]（统一 ComponentDB） |
| `PstchipParser` | `pstchip.dat` | JEDEC_TYPE/VALUE 映射 | PST 数据源，补充封装尺寸与标称值（用于匹配增强） |
| `PstxnetParser` | `pstxprt.dat` | refdes → primitive 映射 | PST 数据源，refdes → 器件名/INSxxx（桥接 pstxnet/EDIF） |
| `PstxnetNetlistParser` | `pstxnet.dat` | pin → net 映射 | PST 数据源，网络连接补充（Stage 5.5b 主数据源） |

---

### 7. 完整数据流

```
.dsn 二进制 ──→ OleReader ──→ BinaryReader
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              Page Stream   Cache Stream  Library Stream
              (PlacedInst,   (Package(31), (strLst 字符串表)
               Wire, Net)    Device(32),
                             LibraryPart(24))
                    │            │            │
                    ▼            ▼            ▼
              PageData      ComponentDB    字符串索引
                    │         (CIS器件库)      │
                    └────────────┬────────────┘
                                 ▼
                          component-builder
                          结合 Cache 和 strLst
                          生成 ComponentDef[]
                                 │
                                 ▼
                            DesignIR
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              CPMWriter    SCHWriter    CDSLibWriter
              (.cpm)       (.sch.N.M)   (cds.lib)
```

---

### 8. 文件完备性对器件库的影响分析

#### 8.1 输入完整度 → 器件匹配能力矩阵

| 提供文件 | 可提取信息 | 匹配策略可用（v2.0 两阶段口径） | 匹配质量 |
|---------|-----------|-------------|:--:|
| 仅 .dsn | 位号、坐标、引脚编号、引脚-网络连接 | 仅类型内精确（Phase 2，无封装/值 → Phase 1 先验弱） | 低（无引脚名/封装/值） |
| .dsn + .edf | 以上 + 引脚名 + 属性 + 网络名 | Phase 1 + 类型内链（有器件名/value） | 中（有器件名模糊匹配） |
| .dsn + .olb | 以上 + 引脚名 + 封装 + 默认值 + 符号 | Phase 1 + 完整类型内链（Exact/Fuzzy/Feature/Value） | 高（有完整属性特征提取） |
| .dsn + .olb + .edf | 以上 + 交叉验证 | v2.0 两阶段全管道（含 PST 交叉验证） | 最高（多路验证一致） |

#### 8.2 OLB 缺失时的降级器件数据流

```
无 OLB 时:
  DSN Cache → Package(31) 的 .name/.refdesPrefix/.pcbFootprint
           → Device(32) 的 .pinMap → 仅引脚编号（无引脚名）
           → LibraryPart(24) 的 .pinNames → ❌ 不可用（无OLB）
           → LibraryPart(24) 的 .defaultVal → ❌ 不可用（无OLB）

有 OLB 时:
  OLB Cache → [同上] + LibraryPart.pinNames → ✅ 完整引脚名
           → LibraryPart.defaultVal → ✅ 默认器件值
           → LibraryPart.symbolGraphics → ✅ 符号图形坐标

→ 匹配层设计需接受"引脚名可能为空"的 ComponentDef
→ 符号生成需接受"无原始符号→使用默认矩形符号"的降级路径
```

- [x] CIS 和 HDL 器件库格式完全确认不同（OLB 二进制 vs sym/ptf/prt 文本）
- [x] OLB 内部结构已通过代码验证（Package/Device/LibraryPart = 三种结构体）
- [x] 所有器件映射到统一的 `ComponentDef`（绝不分格式创建类）
- [x] 用户可自定义器件：在 HDL 库目录添加文件 → HDLLibScanner 自动识别
- [ ] 器件数据库可持久化：JSON 序列化（ComponentDBSerializer）— **未落地**（core/db/ 仅 component_db.py；当前每次由 HDLLibScanner 重建）
- [x] 匹配层在 IR 层进行，不感知格式差异
- [x] 解析器/写入器使用基类-注册模式，不按器件类型分叉
- [x] **OLB 缺失降级路径已设计**：从 DSN Cache 提取基础信息 → 引脚名缺失标注 → 默认符号替代
- [x] **输入完整度对匹配质量的影响已评估**（§8.1 输入完整度矩阵，v2.0 两阶段口径）
- [x] **所有器件相关诊断信息接入 ErrorDiagnosisEngine 44 错误码（v1.1 口径）**

## Part IV 诊断与恢复体系（原 DIAGNOSTICS_AND_RECOVERY.md 全文，逐节保留）

> **Part IV 来源**: 原 `DIAGNOSTICS_AND_RECOVERY.md`（v1.1.0，2026-08-07，467 行）
> **历史边界注记**: 本部分为原 `DIAGNOSTICS_AND_RECOVERY.md` 全文，写作于 2026-08-07（v1.1.0，状态：生效，规划模块已全部落地）。原文所有句子、代码块、表格、交互原型 ASCII 图均原样保留，仅调整标题层级以适配合并文档结构。
> **重叠注记**: 本部分 §2（三层诊断管道、44 错误码）与 Part I §2.7 / Part II §7 有重叠；§0.1「已有能力」表引用 Part I §2.3、Part II §3.0b、Part V §2 等。重叠原文均保留不动，以 v1.1.0 新口径为准。

### 原文档标题与头部（原文保留）

**原标题**: CIS2HDL 文件完整性校验与诊断系统设计


> 版本: v1.1.0 | 日期: 2026-08-07 | 状态: 生效
> 基于对现有设计文档的全面审查 — 发现错误处理/文件校验/用户反馈机制存在重大设计空白
> 规划落地: 规划模块已全部落地（2026-08-07 核实：diagnostics/ 14 个模块存在）

---

### 0. 现状审查结论

#### 0.1 已有能力

| 能力 | 位置 | 状态 |
|------|------|:--:|
| Python 异常层次定义 | STANDARDS.md（原 CODING_STANDARDS §5.1） | 📄 设计稿 |
| Validator Layer 框架 | Part I §2.3 | 📄 设计稿（Phase II） |
| EDIF↔DSN 交叉验证器 | Part II §3.0b / 已实现 | ✅ 代码 |
| BinaryReader 边界检查 | dsn/binary_reader.py | ✅ 代码 |
| FutureDataList 检查点 | dsn/structures.py | ✅ 代码 |
| Pydantic 自动类型验证 | IR 模型层 | ✅ 代码 |
| UI 颜色语义（红/橘/金） | Part V §2 | 📄 设计稿 |

#### 0.2 关键空白（对标 Cadence Allegro 专业工具）

| 空白领域 | 严重程度 | Cadence 对标功能 | 当前缺失 |
|----------|:--------:|-----------------|---------|
| **文件清单与完整性校验** | 🔴 CRITICAL | `Project Manager → Check References` | 完全缺失：不告知用户缺了什么文件 |
| **多文件依赖解析** | 🔴 CRITICAL | DSN 内部引用 OLB 库的自动查找 | `.dsn` 内部引用的 `.olb` 文件路径未知 |
| **分文件逐项读取报告** | 🔴 CRITICAL | Packager-XL 的逐文件状态 | 无结构化读取状态报告 |
| **解析失败诊断与引导** | 🔴 CRITICAL | Canvas 44 错误码体系 | 无用户友好的错误分类和修复建议 |
| **降级转换路径** | 🟠 MAJOR | Cadence `Partial Design` 模式 | 无可选文件列表或降级策略 |
| **前置条件检查器** | 🟠 MAJOR | DRC 规则预检查 | 无法在转换前告知用户问题 |
| **增量恢复与断点续转** | 🟡 MINOR | SDM 版本管理 | 无中间结果保存机制 |
| **转换报告（结构化）** | 🟡 MINOR | Packager-XL Report | 仅有基础日志，无结构化报告 |

> **核心结论**：当前程序只能处理"完美输入"，对不完整输入、损坏数据、引用缺失等现实场景完全没有应对设计。

---

### 1. CIS 项目文件完整清单

#### 1.1 CIS 项目标准文件结构

一个完整的 OrCAD Capture CIS 项目由以下文件组成：

```
MyProject/
├── MyProject.opj              ← 项目配置文件（文本）
├── MyProject.dsn              ← 原理图主文件（CFB 二进制容器）★
├── MyProject.dsn.lck          ← 文件锁（OrCAD 打开时存在）
├── MyProject-DBK/             ← 自动备份目录
│   ├── MyProject.dbk          ← DSN 备份×1（前一次保存）
│   ├── MyProject.dbk.001      ← DSN 备份×2
│   └── ...
├── Library/                   ← 本项目的器件库
│   ├── MyLib.olb              ← 自定义器件库（CFB 二进制）
│   └── CAPSYM.olb             ← 系统符号库引用（电源/端口符号）
├── Simulation/                ← 仿真配置（PSpice）
│   ├── PROFILE.sim
│   ├── PROFILE.prp
│   └── ...
└── Outputs/                   ← 网表/报告输出目录
    ├── MyProject.edf          ← EDIF 导出（文本）
    └── allegro/               ← PCB 网表
        ├── pstxnet.dat        ← 网络连接网表
        ├── pstxprt.dat        ← 器件-封装网表
        └── pstchip.dat        ← 器件引脚网表
```

#### 1.2 DSN 文件内部结构（CFB 容器）

`.dsn` 是 MS-CFB 复合容器，内部包含多个流：

```
MyProject.dsn (CFB Container)
├── Root Entry
├── Views/
│   └── SCHEMATIC1/             ← 原理图视图
│       └── Pages/              ← 页面流目录
│           ├── PAGE1           ← 第1页（Type=10 页面结构体流）
│           ├── PAGE2           ← 第2页
│           └── PAGE3           ← 第3页
├── Cache/                      ← 设计缓存（器件定义）
│   ├── Package1                ← 器件封装（Type=31）
│   ├── Package2
│   └── ...
├── Library/                    ← 字符串表
│   └── strLst                  ← 全局字符串索引表
├── Hierarchy/                  ← 层次结构信息
│   └── Hierarchy               ← 层次树定义
└── Metadata                    ← 元数据
    ├── DesignProperties        ← 设计属性
    └── Annotation              ← 位号分配信息
```

#### 1.3 ⚠️ DSN 内部对 OLB 文件的隐含依赖

`.dsn` 内部的 `PlacedInstance.source_package` 和 `Package.name` 字段引用了器件库（`.olb`）中的器件定义。转换需要知道：

| 依赖类型 | 引用来源 | 如何满足 |
|----------|---------|---------|
| **器件符号定义** | `PlacedInstance.pkgName` → `.olb` 中的 Package | 提供对应的 `.olb` 文件 |
| **器件引脚映射** | `PlacedInstance.t0x10.pinIndex` → Device.pinMap | `.olb` 的 Cache 流 |
| **属性默认值** | CachedLibraryPart.defaultVal | `.olb` 的 Library 流 |
| **标准符号** | CAPSYM.olb（VCC/GND/Port 符号） | Cadence 安装目录自带 |

**如果 `.olb` 缺失**，器件将有：
- ✅ 位号（reference）
- ✅ 放置坐标（locX/Y）
- ✅ 引脚连接（T0x10.netId）
- ❌ 引脚名称（pinNames 缺失）
- ❌ 符号图形（symbol graphics 缺失）
- ❌ 属性默认值（value/footprint 可能为空）

#### 1.4 完整文件依赖分析表

| 文件 | 格式 | 提供信息 | 必需性 | 缺失后果 |
|------|:--:|---------|:------:|---------|
| **P0 核心必选** |
| `*.dsn` | 二进制 CFB | 全部逻辑 + 坐标 + 属性 | 🔴 **强制** | 无法进行任何转换 |
| **P1 强烈建议** |
| `*.opj` | 文本 INI | 项目配置、库路径、页面尺寸 | 🟠 **建议** | 使用默认配置；可能丢失库路径引用 |
| `*.olb` (项目库) | 二进制 CFB | 器件符号、引脚名、属性 | 🟠 **建议** | 器件无引脚名/符号/默认值（见 1.3） |
| `CAPSYM.olb` | 二进制 CFB | 电源/地/Port 等系统符号 | 🟠 **建议** | 可用默认符号替代；可能缺失 Port 方向 |
| **P2 可选增强** |
| `*.edf` | 文本 S-expr | 完整逻辑验证基线 | 🟡 **可选** | EDIF↔DSN 交叉验证不可用（不影响转换） |
| `*.dbk` / `*.dbk.001` | 二进制 CFB | 备份版 dsn（结构完全相同） | 🟡 **可选** | DSN 损坏时的恢复备选 |
| `pstxnet.dat` | 文本 | 网络连接的第三方验证 | 🟡 **可选** | 额外验证不可用 |
| `pstxprt.dat` | 文本 | 器件-封装映射验证 | 🟡 **可选** | 额外验证不可用 |
| `pstchip.dat` | 文本 | 引脚定义验证 | 🟡 **可选** | 额外验证不可用 |
| **P3 增强可选（仿真/制造）** |
| `*.sim` | 键值对 | 仿真配置 | ⚪ **高级** | 无损基本转换 |
| `*.cir` | SPICE 文本 | 仿真激励文件 | ⚪ **高级** | 无损基本转换 |
| `*.net` | SPICE 文本 | 仿真网表 | ⚪ **高级** | 无损基本转换 |
| `*.bom` / `.xlsx` | 文本/XLSX | BOM 材料清单 | ⚪ **高级** | 从 DSN 重新提取 |

---

### 2. 文件校验与诊断系统设计

#### 2.1 系统架构：三层诊断管道

对标 Cadence 的 `Project Manager → Check References → DRC` 三层验证：

```
用户输入文件集
      ↓
┌──────────────────────────────────────────────────────────────┐
│ Layer 1: File Integrity Check (文件完整性校验)               │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│ │ 文件存在  │ │ 格式验证  │ │ 版本检测  │                     │
│ │ 性检查   │ │ (魔数/头) │ │ (CFB版)   │                     │
│ └──────────┘ └──────────┘ └──────────┘                     │
│     ↓              ↓           ↓                            │
│  FILE_MISSING   BAD_FORMAT  VERSION_MISMATCH                │
└────────────────────┬─────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────────┐
│ Layer 2: Dependency Resolution & Cross-Reference Check       │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│ │ OLB引用  │ │ 层次引用  │ │ 跨页引用  │ │ 全局网络  │        │
│ │ 解析     │ │ 解析     │ │ 解析     │ │ 解析     │        │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
│     ↓              ↓           ↓           ↓                │
│  MISSING_OLB  BROKEN_HIER  DANGLING_OFFPAGE  UNCONNECTED    │
└────────────────────┬─────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────────┐
│ Layer 3: Data Completeness Report (数据完整度评估)           │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│ │ 逻辑数据  │ │ 坐标数据  │ │ 属性数据  │ │ 图形数据  │        │
│ │ 完整度   │ │ 完整度   │ │ 完整度   │ │ 完整度   │        │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
│     ↓              ↓           ↓           ↓                │
│  百分比评分      百分比评分   百分比评分    百分比评分         │
└────────────────────┬─────────────────────────────────────────┘
                     ↓
            ┌────────────────┐
            │ Conversion     │
            │ Readiness       │  ← 综合评分 + 建议
            │ Assessment     │
            └────────────────┘
```

#### 2.2 新增模块设计

##### 2.2.1 `FileInventory` — 文件清单与状态追踪

```python
@dataclass
class FileStatus:
    """单个文件的解析状态。"""
    path: Path
    file_type: str               # "DSN", "OLB", "OPJ", "EDF", "DBK", "PSTXNET", "PSTXPRT", "PSTCHIP", "SIM", "CIR"
    status: FileState            # FOUND / MISSING / CORRUPTED / PARTIAL / UNSUPPORTED_VERSION
    size: int = 0
    summary: str = ""            # 人可读摘要
    error_detail: str = ""       # 失败原因
    data_quality: float = 0.0    # 0.0-1.0 数据质量评分

@dataclass
class ProjectInventory:
    """CIS 项目文件清单。"""
    project_root: Path
    files: dict[str, FileStatus]  # key = relative path
    dsn_internal: DSNInternalInventory  # DSN 内部引用清单
    missing_olbs: list[str]         # 引用但缺失的 OLB 名称
    missing_hdl_equivalents: list[str]  # 转换所需但缺失的 HDL 对应物
```

##### 2.2.2 `DSNInternalInventory` — DSN 内部引用清单

```python
@dataclass
class DSNInternalInventory:
    """DSN 内部流结构和引用清单。"""
    streams_found: dict[str, bool]   # Root/Views/Pages/Cache/Library/Hierarchy→是否成功读取
    pages_parsed: int                # 成功解析的页面数
    total_pages: int                 # 总页面数
    instances_parsed: int            # 成功解析的器件实例数
    total_instances: int             # 总器件实例数
    olb_references: list[str]        # 引用的 OLB 名称列表
    referenced_packages: dict[str, tuple[str, int]]  # package→(OLB名, 实例数)
    strlst_entries: int              # 字符串表条目数
    cache_entries: int               # 缓存中的 Package 数
```

##### 2.2.3 `ConversionReadinessEvaluator` — 转换就绪度评估器

```python
class ConversionReadinessEvaluator:
    """综合评估当前文件集是否足以进行转换。"""
    
    def evaluate(self, inventory: ProjectInventory) -> ReadinessReport:
        """返回结构化评估报告。
        
        评估维度：
        - 逻辑完整性：器件/引脚/网络是否完整可读
        - 坐标可用性：器件位置/连线路径是否可用
        - 器件可匹配性：引脚名/属性是否足以匹配到 HDL 库
        - 符号可生成性：是否有足够信息生成 HDL 符号
        """
    
    def suggest_next_steps(self, report: ReadinessReport) -> list[ActionItem]:
        """根据评估结果生成用户操作建议。
        
        示例：
        - "缺少器件库文件 CAP01631.olb，请上传该文件以获取引脚名称和器件属性"
        - "已解析 14/14 个器件，但 3 个缺少引脚名。请提供对应的 .olb 文件"
        - "当前文件集可完成基本转换（逻辑正确但器件符号使用默认样式）"
        - "已满足完整转换条件，可以开始转换"
        """
```

##### 2.2.4 `FileRecoveryStrategy` — 文件损坏恢复策略

```python
class FileRecoveryStrategy:
    """当核心文件损坏时的恢复策略。"""
    
    AVAILABLE_STRATEGIES = {
        "DSN_CORRUPTED": [
            ("USE_BACKUP", "从 .dbk 备份文件恢复"),
            ("USE_EDIF_FALLBACK", "使用 .edf 文件完成逻辑转换（坐标将丢失）"),
            ("PARTIAL_PARSE", "尝试跳过损坏页面解析其余内容"),
            ("ATTEMPT_REPAIR", "尝试修复损坏的 CFB 扇区"),
        ],
        "OLB_MISSING": [
            ("USE_CACHE_EMBEDDED", "使用 DSN 内部 Cache 中的器件定义（可能不完整）"),
            ("USE_DEFAULT_SYMBOL", "使用默认矩形符号替代缺失符号"),
            ("SKIP_WITH_WARNING", "跳过该器件并列出缺失项"),
        ],
    }
```

---

### 3. 用户交互流程设计

#### 3.1 文件导入阶段的诊断面板

```
┌──────────────────────────────────────────────────────────────┐
│  📁 项目文件状态                                              │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ✅ DSN 文件              MyProject.dsn          3页 42器件   │
│  ✅ EDIF 文件             MyProject.edf          42器件       │
│  ❌ 器件库 1              CAP01631.olb           未找到       │
│  ⚠️  器件库 2              Discrete.olb           解析警告     │
│  ℹ️  PCB 网表              pstxnet.dat            未提供       │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 📊 数据完整度：逻辑 92%  |  坐标 100%  |  属性 67%    │ │
│  │                                                          │ │
│  │ 🔴 缺失: CAP01631.olb — 3 个器件将无引脚名称              │ │
│  │ 🟡 可选: pstxnet.dat — 可用于交叉验证网络连接             │ │
│  │                                                          │ │
│  │ [上传缺失文件]  [忽略并继续]  [查看详情]                   │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  📋 建议操作：                                                │
│  ─────────────────────────────────────────────────────        │
│  1. 上传 CAP01631.olb 获取引脚名称和器件属性                  │
│  2. (可选) 上传 pstxnet.dat 启用交叉验证                      │
│                                                               │
│  [开始转换]  [仅逻辑转换（无符号）]  [取消]                    │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

#### 3.2 转换后报告面板

```
┌──────────────────────────────────────────────────────────────┐
│  📊 转换报告 — MyProject (2026-07-30 14:30)                  │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ╔══════════════════════════════════════════════════════════╗ │
│  ║  ✅ 转换完成  ║  ✅ 42/42 器件   ║  ⚠️  3 警告    ║     ║ │
│  ╚══════════════════════════════════════════════════════════╝ │
│                                                               │
│  ┌─ 页面 ───────────────────────────────────────────────────┐ │
│  │ ✅ PAGE1 (02_Power)         12 器件, 8 网络              │ │
│  │ ✅ PAGE2 (03_RTL8367RB)      18 器件, 24 网络             │ │
│  │ ✅ PAGE3 (04_MDI)            12 器件, 15 网络             │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─ 匹配结果 ───────────────────────────────────────────────┐ │
│  │ ✅ R1  (RES_10K)         → standard/resistor       1.00  │ │
│  │ ✅ C5  (CAP_100nF)       → standard/capacitor      1.00  │ │
│  │ ⚠️  U3  (LM358)          → manual confirmation     0.65  │ │
│  │ ❌ U7  (CAP01631)        → NO MATCH FOUND                │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─ 警告详情 ───────────────────────────────────────────────┐ │
│  │ ⚠️  U3 (LM358): 引脚名不匹配，需人工确认                  │ │
│  │ ⚠️  CAP01631.olb 缺失: U7 使用默认通用符号                 │ │
│  │ ⚠️  NET_003: 网络名含非法字符，已自动清洗为 NET_003_X     │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─ 生成文件 ───────────────────────────────────────────────┐ │
│  │ ✅ MyProject.cpm             ✅ cds.lib                  │ │
│  │ ✅ top.sch.1.1               ✅ top.sch.1.2              │ │
│  │ ✅ top.sch.1.3               ⚠️  sym/ (3个默认符号)      │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  📋 后续建议：                                                │
│  ─────────────────────────────────────────────────────        │
│  1. 确认 U3 (LM358) 的引脚映射                                │
│  2. 提供 CAP01631.olb 替换 U7 的默认符号                      │
│  3. 运行 Packager-XL 验证生成的设计                           │
│                                                               │
│  [导出报告 HTML]  [导出报告 PDF]  [打开输出目录]               │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

> **注**：以上交互原型为 `.sch.*` 时代的设计快照（历史快照，现输出为 CSA 原生格式 `.csa`，2026-08-07 核实）。

---

### 4. 与 Cadence 专业工具的功能对比

#### 4.1 对标分析

| Cadence 功能 | 功能描述 | 本项目状态 | 优先级 | 对应模块 |
|-------------|---------|:--:|:------:|---------|
| **Project Manager → Check References** | 检查设计引用的所有文件是否存在 | ❌ 缺失 | 🔴 P0 | `FileInventory` |
| **Packager-XL Pre-check** | 打包前检查所有器件/引脚/网络的完整性 | ❌ 缺失 | 🔴 P0 | `ConversionReadinessEvaluator` |
| **DRC (Design Rule Check)** | 7 种规则检查（已在 RESEARCH.md（原 ORCAD_SOURCE_ANALYSIS §11.4）记录） | 📄 设计稿 | 🟠 P1 | `validator/` 层 |
| **Canvas 44 错误码** | 明确的错误码和修复建议 | ❌ 缺失 | 🟠 P1 | `ErrorDiagnosisEngine` |
| **Export Physical 验证** | 导出网表并验证 | 📄 设计稿 | 🟡 P2 | `pstxnet.dat` 验证 |
| **SDM 版本管理** | 设计生命周期管理 | ❌ 缺失 | 🟡 P2 | — |
| **Partial Design Mode** | 允许部分设计打开/编辑 | ❌ 缺失 | 🟡 P2 | `FileRecoveryStrategy` |
| **Backup/AutoSave** | .dbk 自动备份 | 仅读取 | ⚪ P3 | — |
| **Constraint Manager** | 约束规则管理 | ❌ 不适用 | — | — |

#### 4.2 当前设计文档中缺失的顶层能力

| 缺失能力 | 说明 | 影响 |
|---------|------|------|
| **文件清单与状态追踪** | 没有中心化的文件状态管理系统 | 用户不知道哪些文件可用、哪些缺失 |
| **结构化错误报告** | 仅有日志，无结构化报告 | 无法程序化地分析转换质量 |
| **用户引导系统** | 无"下一步操作建议" | 用户遇到问题后只能自己排查 |
| **降级转换路径** | 不支持"部分数据可用时尽可能转换" | 一个文件缺失就完全无法工作 |
| **数据质量量化** | 无百分比/评分体系 | 无法量化"当前能转多少" |
| **可选文件利用** | 未设计可选数据的利用管道 | `.dbk`/pstx*/`.cir` 等未被利用 |
| **多语言编码处理** | 字符串表可能含 GBK/Shift-JIS | 属性值可能乱码 |
| **CFB 版本兼容** | 仅支持单一 CFB 版本 | 不同 OrCAD 版本的 DSN 可能不兼容 |
| **增量转换** | 不支持"已转换3/5页，继续" | 大工程转换中断后需重来 |
| **配置校验** | Config 单例未经校验 | 路径错误/格式不合法时无提示 |

---

### 5. 推荐新增模块开发计划

#### 5.1 Phase I-B 追加（当前阶段立即补充）

| 模块 | 文件 | 描述 | 估算 |
|------|------|------|:--:|
| `FileInventory` | `core/diagnostics/file_inventory.py` | 文件清单与状态追踪 | ~200 行 |
| `DSNInternalInventory` | `core/diagnostics/dsn_inventory.py` | DSN 内部引用清单提取 | ~150 行 |
| `DiagnosticReport` | `core/diagnostics/diagnostic_report.py` | 结构化诊断报告数据模型 | ~100 行 |

#### 5.2 Phase II 追加

| 模块 | 文件 | 描述 | 估算 |
|------|------|------|:--:|
| `ConversionReadinessEvaluator` | `core/diagnostics/readiness.py` | 转换就绪度综合评分 | ~250 行 |
| `FileRecoveryStrategy` | `core/diagnostics/recovery.py` | 损坏/缺失文件的降级策略 | ~200 行 |
| `ErrorDiagnosisEngine` | `core/diagnostics/error_diagnosis.py` | 44 错误码体系 + 修复建议 | ~300 行 |
| `StructuredReportGenerator` | `core/diagnostics/report_gen.py` | HTML/JSON 结构化报告输出 | ~200 行 |
| GUI 诊断面板 | `gui/panels/diagnostic_panel.py` | 文件状态树 + 质量评分条 + 操作建议 | ~400 行 |
| GUI 转换报告面板 | `gui/panels/report_panel.py` | 彩色状态 + 折叠详情 + 导出 | ~350 行 |

#### 5.3 总计新增工作量

| 阶段 | 后端 | 前端 | 合计 |
|------|:---:|:---:|:---:|
| Phase I-B 追加 | ~450 行 | — | ~450 行 |
| Phase II 追加 | ~950 行 | ~750 行 | ~1,700 行 |
| **合计** | **~1,400 行** | **~750 行** | **~2,150 行** |

---

### 6. 可选的增强文件清单（完整）

#### 6.1 可选但可增强转换质量的文件

| 文件 | 格式 | 提供能力 | 增强效果 |
|------|:--:|---------|---------|
| `*.dbk` / `*.dbk.001` | 二进制 CFB | DSN 备份（结构完全相同） | 🛡️ **容错**：DSN 损坏时自动恢复 |
| `*.edf` | 文本 S-expr | 完整逻辑数据 | 🔍 **交叉验证**：自动比对 EDIF↔DSN 一致性 |
| `pstxnet.dat` | 文本 | 网络连接关系 | ✅ **验证**：第三方格式确认连接正确性 |
| `pstxprt.dat` | 文本 | 器件-封装映射 | ✅ **验证**：验证 PCB 封装引用 |
| `pstchip.dat` | 文本 | 引脚定义 | ✅ **验证**：验证引脚编号/名称 |
| `*.bom` / `*.xlsx` | 文本/XLSX | BOM 材料清单 | 📋 **增强**：保留原始 BOM 格式 |
| `*.olb` (标准库) | 二进制 CFB | 标准符号定义 | 🎨 **符号增强**：使用原始符号图形 |
| `*.sim` | 键值对文本 | 仿真配置 | ⚡ **仿真**：保留仿真设置 |
| `*.cir` | SPICE 文本 | 仿真激励 | ⚡ **仿真**：保留仿真电路 |
| `*.prp` | S-expr 文本 | 属性映射 | 📋 **属性完善**：保留 PSpice 属性映射 |

#### 6.2 转换输出可选增强

| 可选输出 | 用途 | 需额外输入 |
|---------|------|-----------|
| `*.sym` 符号文件 | 生成自定义符号 | `.olb` 文件或手动定义 |
| `*.ptf` 属性表 | 多封装器件配置 | `.olb` 或公司库规范 |
| `*.bom` BOM 文件 | 材料清单 | `.bom` 模板或公司 BOM 规范 |
| `*.vhd` / `*.v` | FPGA 仿真存根 | 器件引脚定义完整时 |
| `report.html` | 转换报告 | 所有输入文件 |

---

### 7. 自检清单

- [x] 完成现状审查：识别 8 个关键空白（0.2 节）
- [x] CIS 项目文件完整清单（1 节）
- [x] DSN 内部结构与隐含依赖分析（1.2-1.3 节）
- [x] 必需/建议/可选文件分级表（1.4 节）
- [x] 三层诊断管道架构设计（2.1 节）
- [x] 新增模块接口定义（2.2 节）
- [x] 用户交互流程设计（3 节：导入诊断面板 + 转换报告面板）
- [x] 与 Cadence 专业工具的对标分析（4 节：9 项对标 + 10 项缺失）
- [x] 新增模块开发计划与工作量估算（5 节）
- [x] 完整可选文件增强清单（6 节）

## Part V GUI 设计规范（原 UI_DESIGN_SPEC.md 全文，逐节保留）

> **Part V 来源**: 原 `UI_DESIGN_SPEC.md`（v1.1.0，2026-08-07，683 行）
> **历史边界注记**: 本部分为原 `UI_DESIGN_SPEC.md` 全文，写作于 2026-08-07（v1.1.0，状态：强制生效；基于 Anthropic Design Language；整合原 FRONTEND_DESIGN v2.0，该源文档已归档 archive/合并源/FRONTEND_DESIGN.md）。原文所有句子、代码块、Token 表、ASCII 图均原样保留，仅调整标题层级以适配合并文档结构。
> **重叠注记**: 本部分为 GUI 设计唯一权威，无重大主题重叠；§13.6（文件依赖）中的 GUI 目录结构与 Part I §4.1 顶层包结构有轻微重叠，以 Part I §4.1（2026-08-07 实测）为准。

### 原文档标题与头部（原文保留）

**原标题**: CIS2HDL 用户界面设计规范


> 版本: v1.1.0 | 日期: 2026-08-07 | 状态: 强制生效
> 基于: Anthropic Design Language（工具优先模式）
> 实现: `cis2hdl/gui/colors.py` — 完整 Token 体系
> 整合说明: 本文档为 UI 设计规范唯一权威，整合原 UI_DESIGN_SPEC（v3.0，2026-07-30）与 FRONTEND_DESIGN（v2.0，2026-07-30，已归档 archive/合并源/FRONTEND_DESIGN.md）；交互流程设计见「13. 交互流程设计（原 FRONTEND_DESIGN）」。

---

### 1. 设计哲学

CIS2HDL 是 EDA 专业工具，遵循 Anthropic Design Language 的**"工具优先"模式**：
- **密度优先**：信息密度高于留白美学，功能完整性优先
- **暖色克制**：暖米色底色 + 单一橙色 CTA，拒绝多彩
- **Token 一切**：颜色/间距/字体/圆角全部通过 Python 常量引用，禁止硬编码
- **红色强制**：所有不可逆操作用红色按钮强调，不用克制灰色

参考来源：Anthropic 官方前端设计规范（SKILL.md、design-rules.md、systems.md、typography-cn.md、dashboard.md）

---

### 2. Token 体系总览

所有样式定义集中在 `cis2hdl/gui/colors.py`，通过 7 层 Token 常量类管理：

| 层 | 类名 | Token 数 | 作用域 |
|----|------|:--:|------|
| 颜色 | `Colors` | 22 | 背景/强调/辅助/文字/语义/边框 |
| 间距 | `Spacing` | 7 | 4px 网格系统 |
| 圆角 | `Radius` | 5 | 外圆角 > 内圆角 |
| 字号 | `FontSize` | 5 | 双数体系 (10-20px) |
| 字体 | `Fonts` | 2 | UI / MONO 字体栈 |
| 阴影 | `Shadow` | 3 | 卡片/悬浮/浮层阴影 |
| 布局 | `Layout` | 9 | 尺寸/高度/宽度常量 |

---

### 3. 颜色系统

#### 3.1 颜色 Token（22 色 Anthropic 暖米色体系）

```python
class Colors:
    # 背景层级 — 暖色分层，不用纯白
    BG_BASE     = "#ECE9E0"  # 页面底色（暖米色）
    BG_RAISED   = "#F5F3EC"  # 卡片/面板背景
    BG_OVERLAY  = "#FFFFFF"  # 浮层（Dropdown/Tooltip）
    BG_INVERTED = "#1E1D19"  # 深色区块（代码预览/终端）

    # 强调色系 — 暖橙唯一 CTA
    ACCENT       = "#D97757"  # 主 CTA（暖橙色）
    ACCENT_HOVER = "#C96442"  # 橙色 hover 态
    ACCENT_MUTED = "#F0D5C8"  # 橙色弱态（进度条轨道/图标背景）

    # 辅助色 — 图表/波形/状态
    AUX_BLUE   = "#6A9BCC"   # 辅助蓝
    AUX_GREEN  = "#788C5D"   # 辅助绿
    AUX_SAND   = "#C4B99A"   # 沙棕（禁用态/空状态）
    AUX_GRAY   = "#9B9890"   # 中灰

    # 文字层级 — 暖色调深字
    TEXT_PRIMARY   = "#141413"   # 主文字
    TEXT_SECONDARY = "#6B6860"   # 次要文字
    TEXT_MUTED     = "#9D9A91"   # 最淡文字
    TEXT_INVERTED  = "#C9C5B8"   # 深色背景文字

    # 语义色 — 强制红色危险操作
    ERROR    = "#C0453A"   # 错误/危险（红色）
    SUCCESS  = "#6B8F47"   # 成功（绿色）
    WARNING  = "#C9943A"   # 警告（黄褐）
    INFO     = "#5A89B8"   # 信息（蓝色）

    # 边框层级 — 透明度替代实色
    BORDER_SUBTLE  = "#D8D5CC"   # 柔和边框（默认）
    BORDER_DEFAULT = "#C4C0B5"   # 标准边框
    BORDER_STRONG  = "#A8A499"   # 强调边框（焦点态）
```

#### 3.2 颜色使用规则

| 规则 | 说明 |
|------|------|
| **底色不用纯白** | 页面背景用 `BG_BASE`，卡片用 `BG_RAISED`，禁止 `#FFFFFF` 做页面底色 |
| **主 CTA 只用橙色** | 主按钮/激活态用 `ACCENT`，禁止蓝色/青色做主按钮 |
| **危险操作强制红色** | 删除/覆盖/不可逆操作用 `ERROR`，不用灰色或中性色 |
| **边框用透明度** | 优先 `rgba()` 透明度边框，减少实色分割线 |
| **颜色不超过 5 种** | 图表/波形/信号线配色从辅助色轮候，禁止彩虹色 |

#### 3.3 辅助函数

```python
def rgb(hex_color: str) -> str:
    """#D97757 → 217, 119, 87"""
    ...

def rgba(hex_color: str, alpha: float) -> str:
    """#D97757, 0.15 → rgba(217, 119, 87, 0.15)"""
    ...
```

---

### 4. 间距系统（4px 网格）

```python
class Spacing:
    XS   = 4    # 极紧凑（图标与文字间距）
    SM   = 8    # 紧凑（同类元素间距）
    MD   = 12   # 默认内间距
    BASE = 16   # 标准内边距（卡片/面板）
    LG   = 24   # 区块间距（数据密集）
    XL   = 32   # 区块间距（工具优先）
    XXL  = 64   # 页面级间距
```

#### 使用规则

| 场景 | Token | 值 |
|------|-------|:--:|
| 卡片内边距 | `Spacing.BASE` | 16px |
| 卡片间距 | `Spacing.LG` | 24px |
| 同类元素间距 | `Spacing.SM` | 8px |
| 栅格上下间距 | 大于左右间距 | 上=SM, 左=XS |
| 按钮水平内边距 | `Spacing.LG` | 24px |
| 按钮垂直内边距 | `Spacing.SM` | 8px |

> ⚠️ 所有间距必须是 4 的倍数。工具优先模式下留白可压缩至 `Spacing.MD`(12px)。

---

### 5. 圆角规范（外圆角 > 内圆角）

```python
class Radius:
    SM   = "4px"     # 内圆角：进度条、小标签
    MD   = "8px"     # 中圆角：按钮、输入框
    LG   = "12px"    # 外圆角：卡片、面板
    XL   = "16px"    # 大圆角：对话框、Modal
    FULL = "9999px"  # 全圆角：头像、Badge
```

#### 使用规则

| 场景 | Token | 说明 |
|------|-------|------|
| 进度条、标签 | `SM` | 内层小元素 |
| 按钮、输入框 | `MD` | 交互控件 |
| 卡片、面板 | `LG` | 外层容器 |
| 对话框 | `XL` | 弹窗 |
| 状态圆点 | `FULL` | 圆形 |

> ⚠️ 嵌套元素的内圆角必须小于外圆角（内 `MD` + 外 `LG`）。

---

### 6. 字体、阴影与排版

#### 6.1 字号 Token（双数体系）

```python
class FontSize:
    XXS = 10   # 微小：版本号、角标
    XS  = 12   # 辅助：表格数据、输入框、日志
    SM  = 14   # 正文：按钮、导航、Tab
    MD  = 16   # 标题：面板标题、指标数值
    LG  = 20   # 大标题：品牌标识
```

#### 6.2 字体 Token

```python
class Fonts:
    UI   = '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif'
    MONO = '"JetBrains Mono", "Cascadia Code", "Consolas", monospace'
```

#### 使用规则

| 用途 | 字体 | 字号 | 字重 |
|------|------|:--:|:--:|
| 品牌名称 | `Fonts.UI` | `LG`(20) | 600 |
| 面板标题 | `Fonts.UI` | `MD`(16) | 600 |
| 指标数值 | `Fonts.UI` | `MD`(16) | 700 |
| 正文/导航 | `Fonts.UI` | `SM`(14) | 400 |
| 表格/日志 | `Fonts.UI`/`MONO` | `XS`(12) | 400 |
| 辅助文字 | `Fonts.UI` | `XS`(12) | 400 |
| 版本号/角标 | `Fonts.UI` | `XXS`(10) | 400 |

> ⚠️ 字号必须是双数，最小不低于 10px。中文 UI 字体字重用 400（视觉上等同于 semibold）。

#### 6.3 阴影 Token

```python
class Shadow:
    CARD    = "0 1px 4px rgba(20,20,19,0.06)"    # 卡片常态
    RAISED  = "0 4px 12px rgba(20,20,19,0.10)"   # 卡片悬浮
    OVERLAY = "0 8px 32px rgba(20,20,19,0.20)"   # Modal/Drawer
```

| 场景 | Token | 说明 |
|------|-------|------|
| 卡片常态 | `Shadow.CARD` | 默认卡片阴影 |
| 卡片悬浮 | `Shadow.RAISED` | hover 提升层级 |
| Modal/Drawer | `Shadow.OVERLAY` | 浮层阴影 |

> ⚠️ 阴影必须引用 `Shadow` Token，禁止硬编码 `box-shadow`/`QGraphicsDropShadowEffect` 数值。

---

### 7. 布局尺寸

```python
class Layout:
    SIDEBAR_WIDTH    = 240      # 侧边栏宽度
    SUMMARY_BAR_H    = 96       # 指标条高度
    METRIC_CARD_MIN  = 160      # 指标卡片最小宽
    TAB_HEIGHT       = 38       # Tab 标签高度
    LOG_COLLAPSED_H  = 36       # 日志折叠高度
    LOG_EXPANDED_H   = 160      # 日志展开高度
    WINDOW_MIN_W     = 1200     # 最小窗口宽
    WINDOW_MIN_H     = 800      # 最小窗口高
    BUTTON_MIN_H     = 32       # 按钮最小高度
```

---

### 8. 组件样式规范

#### 8.1 按钮（三种）

```
主按钮（Primary — STYLE_BUTTON_PRIMARY）:
  background: ACCENT (#D97757)
  color: BG_OVERLAY (#FFFFFF)
  border: none; border-radius: Radius.MD (8px)
  padding: Spacing.SM(8) Spacing.LG(24)
  font-weight: bold; min-height: 32px
  :hover → ACCENT_HOVER (#C96442)
  :disabled → ACCENT_MUTED (#F0D5C8)

次按钮（Secondary — STYLE_BUTTON_SECONDARY）:
  background: BG_OVERLAY (#FFFFFF)
  color: ACCENT (#D97757)
  border: 1px solid ACCENT
  border-radius: Radius.MD (8px)
  padding: Spacing.SM(8) Spacing.LG(24)
  min-height: 32px
  :hover → background: rgba(ACCENT, 0.08)

危险按钮（Danger — STYLE_BUTTON_DANGER）:
  background: ERROR (#C0453A)  ← 强制红色
  color: BG_OVERLAY (#FFFFFF)
  border: none; border-radius: Radius.MD (8px)
  padding: Spacing.SM(8) Spacing.LG(24)
  font-weight: bold; min-height: 32px
  :hover → #A83830
```

#### 8.2 卡片

```
（STYLE_CARD）:
  background: BG_RAISED (#F5F3EC)
  border: 1px solid BORDER_SUBTLE (#D8D5CC)
  border-radius: Radius.LG (12px)
  padding: Spacing.BASE (16px)
  shadow: 0 1px 4px rgba(20,20,19,0.06) — 使用 Shadow.CARD
```

#### 8.3 侧边栏

```
（STYLE_SIDEBAR）:
  width: Layout.SIDEBAR_WIDTH (240px)
  background: BG_RAISED (#F5F3EC)
  border-right: 1px solid BORDER_SUBTLE
  导航项: 36px 高, flat, 选中态左侧 2px ACCENT 条
```

#### 8.4 Tab 控件

```
（STYLE_TAB_WIDGET）:
  QTabBar::tab: 8px 20px padding, 14px font
  未选中: TEXT_SECONDARY
  选中: TEXT_PRIMARY + 底部 2px ACCENT 线条
  :hover: TEXT_PRIMARY
  QTabWidget::pane: 无边框, 透明背景
```

#### 8.5 进度条

```
（STYLE_PROGRESS）:
  轨道: rgba(ACCENT, 0.12), 无边框, 4px 圆角, 6px 高
  chunk: ACCENT (#D97757), 4px 圆角
```

#### 8.6 菜单栏与状态栏

```
（STYLE_MENUBAR）:
  background: BG_RAISED; border-bottom: 1px solid BORDER_SUBTLE
  item:selected → rgba(ACCENT, 0.10)

（STYLE_STATUSBAR）:
  background: BG_RAISED; border-top: 1px solid BORDER_SUBTLE
  font-size: XS(12); color: TEXT_SECONDARY
```

#### 8.7 日志面板

```
（STYLE_LOG）:
  卡片: BG_RAISED + BORDER_SUBTLE + Radius.LG(12px)
  内容: MONO 字体, XS(12px)字号, TEXT_PRIMARY 颜色
  折叠态: 36px 标题栏; 展开态: 160px
```

#### 8.8 指标卡片

```
（STYLE_SUMMARY_BAR / metric_card）:
  background: BG_RAISED; border: 1px solid BORDER_SUBTLE
  border-radius: Radius.MD(8px); padding: MD(12) BASE(16)
  值: MD(16px) Bold TEXT_PRIMARY
  标签: XS(12px) TEXT_MUTED
```

---

### 9. 状态指示

| 状态 | 颜色 Token | 色值 |
|------|-----------|------|
| 成功/已加载 | `ACCENT` | #D97757（暖橙圆点） |
| 警告/待确认 | `WARNING` | #C9943A |
| 错误/未匹配 | `ERROR` | #C0453A |
| 信息/处理中 | `TEXT_MUTED` | #9D9A91 |
| 已匹配 | `SUCCESS` | #6B8F47 |

---

### 10. 布局架构

```
┌──────────────────────────────────────────────────────┐
│  Menu Bar (STYLE_MENUBAR)                            │
├─────────────┬────────────────────────────────────────┤
│  SIDEBAR    │  Summary Bar (4 指标卡片)              │
│  240px      ├────────────────────────────────────────┤
│  ┌────────┐ │  TabContainer                          │
│  │CIS2HDL │ │   [诊断] [预览] [匹配]* [差异]*        │
│  └────────┘ │  ┌──────────────────────────────────┐  │
│             │  │ 当前 Tab 内容（卡片容器）         │  │
│  项目信息    │  └──────────────────────────────────┘  │
│  导航菜单    ├────────────────────────────────────────┤
│  快捷按钮    │  Log Panel（可折叠卡片）               │
│  v1.1.0     │                                        │
├─────────────┴────────────────────────────────────────┤
│  Status Bar (STYLE_STATUSBAR)                        │
└──────────────────────────────────────────────────────┘
```

---

### 11. QSS 样式表清单

所有 QSS 通过 `colors.py` 中的 `STYLE_*` 字典动态生成：

| 样式表 | 覆盖范围 |
|--------|---------|
| `STYLE_BASE` | 全局默认样式 |
| `STYLE_SIDEBAR` | 侧边栏 |
| `STYLE_CARD` | 通用卡片 |
| `STYLE_TAB_WIDGET` | Tab 控件 |
| `STYLE_SUMMARY_BAR` | 指标条 + 指标卡片 |
| `STYLE_BUTTON_PRIMARY` | 主按钮 |
| `STYLE_BUTTON_SECONDARY` | 次按钮 |
| `STYLE_BUTTON_DANGER` | 危险按钮 |
| `STYLE_LOG` | 日志面板 |
| `STYLE_PROGRESS` | 进度条 |
| `STYLE_MENUBAR` | 菜单栏 |
| `STYLE_STATUSBAR` | 状态栏 |

---

### 12. 合规检查清单

- [ ] 所有颜色必须来自 `Colors` 22 色板，无硬编码 hex
- [ ] 所有间距使用 `Spacing` Token，为 4 的倍数
- [ ] 所有圆角使用 `Radius` Token，内圆角 < 外圆角
- [ ] 所有字号使用 `FontSize` Token，双数，≥ 10px
- [ ] 界面文字使用 `Fonts.UI` 字体栈
- [ ] 等宽文字使用 `Fonts.MONO` 字体栈
- [ ] 所有阴影使用 `Shadow` Token，无硬编码 box-shadow
- [ ] 页面底色不用纯白（用 `BG_BASE` 或 `BG_RAISED`）
- [ ] 主 CTA 用橙色（`ACCENT`），不用青色/蓝色
- [ ] 危险操作按钮用红色（`STYLE_BUTTON_DANGER`）
- [ ] 全部 QSS 通过 `colors.py` 中的 `STYLE_*` 引用，不内联
- [ ] 透明度优先用 `rgba()` 函数，减少实色边框
- [ ] 按钮高度 ≥ 32px（`BUTTON_MIN_H`）

---

### 13. 交互流程设计（原 FRONTEND_DESIGN）

> 说明: 本章由原 `FRONTEND_DESIGN.md`（v2.0，2026-07-30，源文档已归档 archive/合并源/FRONTEND_DESIGN.md）整合吸收，原文内容保全保留。其中「13.6 文件依赖」为原文档依赖树，与实际结构有出入，以「13.6.2 当前实际 GUI 结构」为准。

#### 13.1 技术选型

| 组件 | 技术 | 理由 |
|------|------|------|
| GUI 框架 | PySide6 (Qt 6 for Python) | 成熟、跨平台、原生性能、丰富的布局和控件 |
| 主窗口 | QMainWindow + QDockWidget | 可停靠面板，灵活布局 |
| 列表/表格 | QTreeView + QTableView + 自定义 Model | 项目管理、数据展示 |
| 原理图渲染 | QGraphicsView + QGraphicsScene | 矢量渲染，缩放平移 |
| 差异显示 | 自研 DiffWidget | 左右对比视图 |
| 进度 | QProgressBar + QThread worker | 非阻塞后台转换 |
| 图标 | Qt 内置图标 + 自定义 SVG | 无额外依赖 |

#### 13.2 界面布局

##### 13.2.1 主窗口布局

```
┌─────────────────────────────────────────────────────────────┐
│  Menu Bar:  File  Edit  View  Convert  Tools  Help         │
├─────────────────────────────────────────────────────────────┤
│  Toolbar:  [Open] [Save] [Convert ▶] [Preview] [Report]    │
├──────────┬────────────────────────────────────┬─────────────┤
│ Project  │                                    │  Properties │
│ Panel    │        Main Work Area              │  Panel      │
│ (Left)   │                                    │  (Right)    │
│          │   ┌──────────────────────────┐     │             │
│  📁 CIS  │   │                          │     │  Component: │
│   ├─p1   │   │    Schematic Preview /   │     │  Name: R1   │
│   ├─p2   │   │    Match Review /        │     │  Value:10K  │
│   └─p3   │   │    Diff View             │     │  Foot: 0603 │
│          │   │                          │     │  ...        │
│  📁 HDL  │   │                          │     │             │
│   ├─...  │   └──────────────────────────┘     │             │
│          │                                    │             │
├──────────┴────────────────────────────────────┴─────────────┤
│  Log / Status Bar                                           │
│  [INFO] 14:23:01 Parsing complete: 3 pages, 142 components  │
│  [WARN] 14:23:05 U3 (LM358) needs manual pin mapping        │
│  [ OK ] 14:23:10 Conversion finished. 0 errors, 3 warnings  │
└─────────────────────────────────────────────────────────────┘
```

##### 13.2.2 面板说明

| 面板 | 位置 | 职能 |
|------|------|------|
| **Project Panel** | 左侧 | 树形展示 CIS 源项目结构（页面、器件、网络）和 HDL 目标结构预览 |
| **Main Work Area** | 中央 | 根据当前 Tab 显示原理图预览、匹配确认、或转换差异对比 |
| **Properties Panel** | 右侧 | 展示当前选中器件/网络的详细属性 |
| **Log Panel** | 底部 | 实时日志输出，支持按级别筛选（INFO/WARN/ERROR） |
| **Toolbar** | 顶部 | 常用操作快捷按钮 |
| **Status Bar** | 最底部 | 当前状态、进度条、转换统计摘要 |

#### 13.3 核心界面流程

##### 13.3.1 转换工作流（六步）

```
Step 1: Open Project
  ├─ 用户选择 .dsn 文件
  ├─ 系统解析 DSN，填充 Project Panel
  └─ 状态栏显示解析结果摘要

Step 2: Configure
  ├─ 用户指定 HDL 目标器件库路径
  ├─ 用户配置转换选项（输出目录、命名规则等）
  └─ 可选：加载已有映射规则文件

Step 3: Run Matching
  ├─ 系统后台运行匹配管道
  ├─ Main Area 切换到 Match Review 视图
  │   ├─ 左侧：CIS 器件列表（标注匹配置信度颜色）
  │   ├─ 右侧：HDL 候选器件列表
  │   └─ 底部：引脚映射预览
  └─ 用户逐一确认/修正低置信度匹配

Step 4: Validate & Preview
  ├─ 系统运行校验管道
  ├─ Main Area 切换到 Preview 视图
  │   └─ 展示目标 HDL 工程文件树
  └─ 任何校验错误/警告高亮显示

Step 5: Generate
  ├─ 用户点击 "Convert" 按钮
  ├─ 进度条显示生成进度
  └─ 完成后显示 Generation Report

Step 6: Review Report
  ├─ 统计摘要：转换器件数/成功/警告/失败
  ├─ 详细列表：每个器件的映射结果
  └─ 可导出为 PDF/HTML
```

##### 13.3.2 界面状态图（IDLE→LOADED→MATCHING→VALIDATED→COMPLETE）

```
                    ┌──────────┐
                    │  IDLE    │
                    └────┬─────┘
                         │ Open Project
                         ▼
                    ┌──────────┐
                    │ LOADED   │
                    └────┬─────┘
                         │ Configure & Run Match
                         ▼
                    ┌──────────┐
                    │ MATCHING │◄──── 人工确认循环 ────┐
                    └────┬─────┘                       │
                         │ All confirmed                │
                         ▼                             │
                    ┌──────────┐                       │
                    │ VALIDATED│                       │
                    └────┬─────┘                       │
                         │ Generate                    │
                         ▼                             │
                    ┌──────────┐                       │
                    │ COMPLETE │                       │
                    └──────────┘                       │
                         │                             │
                         └─── 可返回重新匹配 ──────────┘
```

#### 13.4 关键组件设计

##### 13.4.1 Project Panel (QTreeView)

```python
class ProjectTreeModel(QAbstractItemModel):
    """CIS 项目结构树模型"""
    
    # 树结构
    # 📁 Project "my_design"
    #   ├─ 📄 Page 1 (top.sch.1.1)  → SchematicPageIR
    #   │   ├─ 🔲 R1 (RES_0603_10K)
    #   │   ├─ 🔲 R2 (RES_0603_1K)
    #   │   ├─ 🔳 U1 (LM358)
    #   │   └─ ...
    #   ├─ 📄 Page 2 (top.sch.1.2)
    #   └─ ...
    
    # 每个节点包含：
    # - 图标（颜色表示匹配状态：绿=已匹配，黄=待确认，红=未匹配）
    # - 名称
    # - 位号/器件名
```

##### 13.4.2 Match Review Panel (QSplitter)

```python
class MatchReviewPanel(QWidget):
    """器件匹配确认面板"""
    
    # 布局：三栏
    # ┌──────────────┬──────────────┬──────────────┐
    # │ CIS Devices   │ HDL Candidates│ Pin Mapping  │
    # │ (QListWidget) │ (QListWidget) │ (QTableWidget)│
    # │               │               │               │
    # │ R1 (matched)  │ RES_0603_10K │ CIS Pin  HDL  │
    # │ R2 (pending)  │ RES_0603_1K  │ 1     →  1    │
    # │ U1 (unmatched)│ RES_0402_10K │ 2     →  2    │
    # │ ...           │ ...           │               │
    # └──────────────┴──────────────┴──────────────┘
    #                          [Accept] [Skip] [Manual]
```

##### 13.4.3 Diff View (QSplitter)

```python
class DiffView(QWidget):
    """转换前后差异对比"""
    
    # 左右分屏
    # ┌──────────────────┬──────────────────┐
    # │ CIS Source        │ HDL Target       │
    # │ ┌──────────────┐ │ ┌──────────────┐ │
    # │ │ R1 RES_0603   │ │ │ R1 RES_0603  │ │ ← 绿色：匹配
    # │ │ R2 CAP_0805   │ │ │ R2 CAP_0805  │ │ ← 绿色
    # │ │ U3 LM358N     │ │ │ U3 ⚠ MANUAL │ │ ← 黄色：待确认
    # │ │ C5 100nF      │ │ │ --- MISSING  │ │ ← 红色：缺失
    # │ └──────────────┘ │ └──────────────┘ │
    # └──────────────────┴──────────────────┘
```

##### 13.4.4 Log Panel (QPlainTextEdit + Filter)

```python
class LogPanel(QWidget):
    """实时日志面板"""
    
    # 功能：
    # - QPlainTextEdit 只读输出
    # - 工具栏：[INFO ✓] [WARN ✓] [ERROR ✓] [Clear]
    # - 使用 HTML 富文本着色
    # - 支持复制/导出
```

#### 13.5 交互设计原则

| 原则 | 实现 |
|------|------|
| **非阻塞** | 所有耗时操作在 QThread worker 中执行，GUI 始终响应 |
| **可撤销** | 匹配确认支持撤销/重做（Undo/Redo 栈） |
| **进度可见** | QProgressBar 显示当前操作进度，状态栏显示预估剩余时间 |
| **批量操作** | 支持 Ctrl/Shift 多选 → 批量确认匹配 |
| **搜索过滤** | 器件列表、日志面板支持实时搜索和正则过滤 |
| **键盘快捷键** | 核心操作有快捷键（Ctrl+O 打开, Ctrl+R 转换等） |

#### 13.6 文件依赖（原 FRONTEND_DESIGN §6，与实际结构有出入，以正文为准）

> ⚠️ 以下 13.6.1 为原 FRONTEND_DESIGN 依赖树（历史保留，仅供参考；源文档已归档 archive/合并源/FRONTEND_DESIGN.md）；实际结构以 13.6.2 为准。

##### 13.6.1 原 FRONTEND_DESIGN 依赖树（历史，与实际结构有出入）

```
gui/
├── __init__.py
├── app.py                   # QApplication, 主入口
├── main_window.py           # 主窗口
├── panels/
│   ├── __init__.py
│   ├── project_panel.py     # 项目结构树
│   ├── match_review.py      # 匹配确认
│   ├── preview_panel.py     # 转换预览
│   └── log_panel.py         # 日志面板
├── dialogs/
│   ├── __init__.py
│   ├── settings_dialog.py   # 设置对话框
│   └── match_confirm.py     # 确认对话框
├── widgets/
│   ├── __init__.py
│   ├── diff_view.py         # 差异对比视图
│   └── status_indicator.py  # 状态指示器
└── models/
    ├── __init__.py
    ├── project_tree.py      # 项目树 Model
    └── match_table.py       # 匹配表 Model
```

##### 13.6.2 当前实际 GUI 结构（2026-08-07 实测）

```
cis2hdl/gui/
├── __init__.py
├── app.py                   # QApplication, 主入口
├── main_window.py           # 主窗口（804 行）
├── colors.py                # Token 体系（310 行，7 类）
├── candidate_selector.py    # 候选选择（798 行）
├── panels/
│   ├── __init__.py
│   ├── sidebar.py           # 侧边栏
│   ├── summary_bar.py       # 指标条
│   ├── tab_container.py     # Tab 容器
│   ├── project_panel.py     # 项目结构树
│   ├── match_review.py      # 匹配确认
│   ├── preview_panel.py     # 转换预览
│   ├── log_panel.py         # 日志面板
│   ├── report_panel.py      # 报告面板
│   ├── diff_view.py         # 差异对比视图
│   ├── schematic_view.py    # 原理图视图
│   ├── diagnostic_panel.py  # 诊断面板
│   ├── error_diagnostic_panel.py  # 错误诊断面板
│   └── rules_panel.py       # 规则面板
├── dialogs/
│   ├── __init__.py
│   ├── settings_dialog.py   # 设置对话框
│   ├── match_confirm.py     # 匹配确认对话框
│   └── recovery_dialog.py   # 恢复对话框
└── widgets/
    ├── __init__.py
    └── conversion_worker.py # 转换后台线程

注: 不存在 models/ 目录与 status_indicator.py（原 FRONTEND_DESIGN 依赖树中的这两项已核实不存在）。
```

---

## 合并保全声明（内容保全证明）

本合并文档由 5 份源文档内容保全式合并而成。下表逐份列出源文档的章节数（代码块外 H1/H2/H3/H4 标题）与合并后位置，证明 **100% 覆盖**：

| 源文档 | H1（标题） | H2 | H3 | H4 | 源正文行数 | 合并后位置 | 覆盖 |
|--------|:--:|:--:|:--:|:--:|:--:|-----------|:--:|
| `SYSTEM_ARCHITECTURE.md` | 1 | 6 | 18 | 0 | 797 | Part I（§1~§6 各节原样保留） | 100% |
| `BACKEND_DESIGN.md` | 1 | 7 | 19 | 0 | 962 | Part II（§1~§7 各节原样保留） | 100% |
| `COMPONENT_ARCHITECTURE.md` | 1 | 9 | 17 | 0 | 564 | Part III（§0~§8 各节原样保留） | 100% |
| `DIAGNOSTICS_AND_RECOVERY.md` | 1 | 8 | 17 | 4 | 467 | Part IV（§0~§7 各节原样保留） | 100% |
| `UI_DESIGN_SPEC.md` | 1 | 13 | 23 | 10 | 683 | Part V（§1~§13 各节原样保留） | 100% |
| **合计** | **5** | **43** | **94** | **14** | **3473** | Part I ~ Part V | 100% |

> **校验方法**：对 5 份源文档的代码块外全部标题（H1~H4）逐条在合并文档中进行存在性核对；全部 43 个 H2 主章节 + 全部 H3/H4 子章节均在对应 Part 内原样出现（仅标题层级 +1、标题文字不变）。源文档正文句子、表格、代码块、ASCII 图未做任何删减或改写（交叉引用文字除外，见 §0.4）。

---

# Phase XI P0 A-D 架构补充（2026-08-10 追加）

> 本节由软件交付团队追加，记录 P0 A-D 实施后的架构变化。完整设计见
> `docs/system_design.md`（691 行权威设计）与 `docs/class-diagram.mermaid`、
> `docs/sequence-diagram.mermaid`（类图/时序图）。

## P0 新增/修改模块

### Writer Layer 重构（核心：共享连接模型）

```
cis2hdl/core/writer/
├── connectivity_model.py   [新增] DesignConnectivity 共享模型
│                             (ConnectivityModelBuilder 聚合 cells/nets/instances/pins)
├── con_writer.py           [新增] ConWriter → <cell>.con (Cadence S-Expr)
├── xcon_writer.py          [重写] XconWriter → <cell>.xcon (CS Schema XML)
├── csv_writer.py           [新增] PageCsvWriter → pageN.csv (CONNECTIVITY)
├── cpc_writer.py           [重写] CpcWriter → pageN.cpc (#ISCELL/#CELL)
├── coord_transform.py      [新增] CoordTransform：体坐标统一变换
├── wire_layout.py          [新增] WireLayoutEngine：拓扑合成（主干+支线+DOT+SIG_NAME）
├── csa_writer.py           [改造] +LASTPIN/WIRE/DOT/SIG_NAME/QUIT
└── output_manager.py       [改造] write_con/xcon/csv/cpc 委托新 writer
```

### 关键架构决策

| 决策 | 说明 |
|------|------|
| 共享连接模型 | con/xcon/csv/cpc 全部消费同一个 `DesignConnectivity`（由 `ConnectivityModelBuilder` 从 DesignIR 构建），保证 4 文件 ID/名称/引脚三方一致 |
| 三态网络命名 | `net_utils.py`：CSV 显示名（`GND_POWER\g`）/ con 内部名（小写 `$→_` 去 `\g` 加 pageN_ 前缀）/ SIG_NAME 三态统一生成 |
| 坐标唯一原则 | 实例只有一个"体坐标"（CoordTransform），LASTPIN/WIRE/csv 头行坐标全部由"体坐标 + symbol.css C 指令偏移"派生 |
| 电源符号特例 | gnd_power/vcc_circle 不进 con cells/instances，进 csv/cpc(#ISCELL)/csa |
| DSN 旁路 | `use_dsn_components=False`（默认）：输入 .dsn 时优先同名 .EDF；pstxnet.dat 仍为权威 pin→net（Stage 5.5b） |

### Parser Layer 补充

- `edif_parser.py`：`_parse_page` 返回 `list[PageIR]`（page 块优先 + legacy 回退）；`_get_page_blocks`/`_page_block_name`/`_page_block_size`/`_parse_page_block`；wires 提取（P0-A1）、off_pages（P0-A3）
- `symbol_css.py`：`SymbolCssPinParser` 解析 `C x y "pinname"` 引脚偏移（5115 条 C 指令实测）
- `ir/design.py`：WireSegment 支持 polyline/page_id、NetIR.wires、PageIR.off_pages/width/height

### 数据流（P0 后）

```
CIS(.dsn) ──use_dsn_components=False──► 同名 .EDF 优先
    │
    ├─ EDIFParser ─► DesignIR(24页/3023实例/862nets/2516wires/522offpages)
    ├─ CrossRef CSV ─► ComponentCatalog（权威 BOM，889 refdes，清除 EDIF 占位）
    ├─ pstxnet.dat ─► Stage 5.5b 主注入（2771 pin→net，权威网络）
    └─ pstchip/pstxprt ─► Stage 5.5c 校验

DesignIR + Catalog + PST → ConnectivityModelBuilder → DesignConnectivity
    ├─ ConWriter → 5015.con（Cadence S-Expr）
    ├─ XconWriter → 5015.xcon（XML）
    ├─ PageCsvWriter → pageN.csv（24 页）
    ├─ CpcWriter → pageN.cpc（24 页）
    └─ CSAWriter → pageN.csa（含 WIRE/LASTPIN/DOT/SIG_NAME）
```

---

# Phase XI P1 架构补充（2026-08-10 追加）

> 记录 P1 第二轮修复的架构变化。详见 changelog_master.md P1 记录。

## P1 模块变化

| 文件 | 变化 | 目的 |
|------|------|------|
| output_manager.py | +`_extract_page_number()` + write_page_map 排序 | P1-1 真实页码 |
| hdl_lib ch347/rf_sw/rj45_2x2_led | +$LOCATION/VALUE/PART_NAME/PATH | P1-2 默认属性 |
| csa_writer.py | 主路径统一 `$LOCATION` | P1-3 单 section |
| ir/component.py | +mirror/nc_pins 字段 | P1-4 存储 |
| edif_parser.py | transform orientation → rotation/mirror | P1-4 解析 |
| conversion_engine.py | pstxnet NC → nc_pins | P1-4 标记 |
| symbol_css.py | SymbolPin +electrical_type/pin_shape | P1-4 电气类型 |
| cpc_writer.py | _ISCELL_CELLS 移除 mark | P1-5 #CELL |

## 数据流补充（P1-4 存储层）

```
EDIF (transform (orientation R90/MY...))
  └─► ComponentInstanceIR.rotation (角度) / mirror (1=X/2=Y)
pstxnet.dat net="NC"
  └─► ComponentInstanceIR.nc_pins (set[str])
OLB/符号库 pin 类型
  └─► PinDef.type (ElectricalType) ◄── SymbolPin.electrical_type (打通)
```

## 关键架构决策

| 决策 | 说明 |
|------|------|
| $LOCATION 统一 | $LOCATION/LOCATION 是实例级属性，无法推导 → 统一 $LOCATION（DEHDL 标准） |
| 页码独立提取 | page.map 页码从 page_name 提取，与 title block / EDIF 内部 id 解耦 |
| 存储先行 | rotation/mirror/NC/电气类型先存入 IR，消费（sym_N 视图映射）后续做 |
| U6A-I 口径 | CrossRef U6A-I 权威；pstxnet 母 U6 重复数据在注入时自然排除（无 U6A-I 对应实例） |

---

# Phase XI P2 架构补充（2026-08-10 追加）

## P2 模块变化

| 文件 | 变化 | 目的 |
|------|------|------|
| coord_transform.py | +`rotate_point`/`rotate_bbox` | P2-1 引脚偏移旋转变换 |
| conversion_engine.py | 占位 orientation 保留（ins_to_refdes）+ catalog 恢复 | P2-1 数据链路 |
| connectivity_model.py | InstanceRecord +rotation/mirror | P2-1 传递 |
| csa_writer.py | pin 偏移 rotate_point + NC 排除 net_pin_map | P2-1/P2-2 |

## 数据流（P2-1 旋转链路）

```
EDIF (orientation R90/MY...)
  → ComponentInstanceIR.rotation/mirror   (P1-4 解析)
  → 清空占位前保留 (key=ins_to_refdes 映射的真实 refdes)
  → catalog 实例重建时恢复 rotation/mirror
  → InstanceRecord.rotation/mirror        (connectivity_model)
  → csa_writer: rotate_point(offset, rot, mirror) → LASTPIN 坐标
```

## 关键决策

| 决策 | 说明 |
|------|------|
| 几何旋转而非切换 sym_N | sym_N 语义混合（capacitor 旋转视图 vs dc_dc 器件变体），切换有歧义；几何旋转数学等价（R90 (0,-75)→(75,0) = sym_2） |
| NC 引脚排除网络 | NC 无连接：不生成 SIG_NAME/WIRE，保留 LASTPIN 引脚存在 |
| ins_to_refdes 桥接 | EDIF 占位 INS### 与真实 refdes 经 pstxprt 映射（914/914 完全交集） |

---

# Phase XI 收尾架构补充（2026-08-10 追加）

## 收尾模块变化

| 文件 | 变化 | 目的 |
|------|------|------|
| edif_parser.py | +design_off_pages（view→contents→offPageConnector） | P0-A3 765 完整 |
| connectivity_model.py | PageConnectivity+off_pages | P0-C5 传递 |
| csa_writer.py | +_emit_ioport_block +_get_pin_name_map | P0-C5 IOPORT + CH347 |
| chips_prt.py | 功能名保留到 PinDef.name | CH347/电气类型源 |
| dsn/structures.py | +_parse_placed_instance_rtl | T04 RTL 恢复 |
| dsn/page_parser.py | _is_valid_result 放宽 | T04 引脚级实例 |
| file_inventory.py | VRTL 识别 | T05 |

## 数据流（收尾）

```
EDIF 顶层 cell view→contents→(offPageConnector ×243) → design_off_pages
PageIR.off_pages(522) → PageConnectivity.off_pages → csa_writer → IOPORT 块
chips.prt PIN_NUMBER↔功能名 → PinDef(number, name) → csa_writer 偏移桥接
DSN RTL PlacedInstance(_RtlStructure) → 实例(8367: 578)
```

---

# Phase XII 匹配率修复架构补充（2026-08-10 追加）

## 模块变化

| 文件 | 变化 | 目的 |
|------|------|------|
| ir/design.py | +`invalidate_caches()` | R1: 重建后失效 all_instances/all_nets 缓存 |
| ir/match.py | +`MatchStrategy.POWER_SYMBOL` | R2: 电源符号确定性匹配策略 |
| diagnostics/quality.py | total_count 页求和 + `_count_matched_instances()` | R1: 按实例计数（305 电源符号共享 3 key） |
| engine/conversion_engine.py | +`_append_power_symbol_matches` +`_build_fallback_table` +`invalidate_caches()` 调用 +`report.pages=len(pages)` | R2/R6/R8 |
| matcher/match_config.py | defaults 补 RD + `_DEFAULT_FIXED_PREFIXES` + yaml 缺失 warning | R3 |
| matcher/pipeline.py | top3 选中候选用 `_matched_row` 数据 | R5 |
| writer/mapping_csv_writer.py | 电源符号豁免 INFO_LOSS | R2 |
| diagnostics/report_gen.py | match-main 浅灰 + conf 分级色 + 两个新板块 | R7/R8 |
| config/type_gate.yaml | Z 前缀加 filter 候选 | R4 |

## 数据流（R2 电源符号匹配链路）

```
EDIF portImplementation (GND/DGND/VCC_CIRCLE)
  → 保留实例（catalog 重建不清除）
  → _append_power_symbol_matches(): 每种库 id → 确定性 MatchResult
      GND/DGND → gnd_power, VCC_CIRCLE → vcc_circle, GND_EARTH → gnd_earth
      conf=1.0, strategy=POWER_SYMBOL
  → match_results (+3 key) → mapping CSV / HTML 报告 / quality 计数
  → mapping_csv_writer: 电源符号豁免 Missing_Value/No_Pin_Connections 检查
```

## 数据流（R5 top3 候选一致性）

```
PassiveMatcher 命中 → result.extra_data["_matched_row"]（实际匹配 ptf 行）
  → _match_single all_type_results 携带 value/jedec/package_type/footprint
  → _generate_cross_type_top3: 选中候选保留实际行数据（ptf_rows[0] 仅空值回退）
  → report_gen 候选行与主行一致（C102: 8.2PF/0201-RF/C0201）
```

## 关键决策

| 决策 | 说明 |
|------|------|
| 电源符号确定性匹配而非走匹配管线 | 电源符号无 value/引脚连接，语义上等价于"库内确定性映射"，conf=1.0 合理 |
| 按实例计数而非按 MatchResult 计数 | 305 个电源实例共享 3 个唯一 key，按结果数会低估 302 个 |
| 不移除 R 前缀 PF/NH 值匹配 | R186 值 2.4PF 是源数据异常，加匹配会引入跨类型错误（v2.0 铁律） |
| report.pages 用总页数 | 4 个信息页在 Catalog 重建后无实例，但 CSA 仍生成 24 页；页数口径统一 |

---

# Phase XIII Cadence 实测反馈修复架构补充（2026-08-11 追加）

## 模块变化

| 文件 | 变化 | 目的 |
|------|------|------|
| connectivity_model.py | +`_real_page_number` + `page_order` 排序 | T0: page_num 按页名数字（四方一致） |
| coord_transform.py | +`_snap25`（map_page/map_point 吸 25 网格） | T1: 消除 off-grid（SPCOCN-1329） |
| csa_writer.py | LASTPIN 内联各 FORCEADD 块；IOPORT 模板对齐 04p4；组件 R 1/2/3 旋转行；fallback 按 pin_number；IOPORT 入 net_pin_map | T1/T2/T3 |
| wire_layout.py | +`route_nets`（车道差异化 _LANE=50/_TOL=25）+`_lane_free` 闭区间 | T4 + R2 短路修复 |

## 数据流（T2 LASTPIN 内联）

```
第1遍: 计算 pin_coords/net_pin_map/source_pins（不输出）
第2遍: 每实例 FORCEADD 块 + 旋转行 R 1/2/3 + 该实例 LASTPIN（$PN=2 / SIG_NAME=3）
     → IOPORT 块（FORCEPROP 1 LASTPIN HDL_PORT/VHDL_PORT）
文件尾: WIRE / DOT / SIG_NAME-on-wire
```

## 数据流（T4 布线车道差异化）

```
net_pin_map + body_outlines
  → route_nets: 按(跨度,引脚数)排序先布长网
  → 每网候选 trunk（中位 y/x 吸网格）→ _lane_free 闭区间检查
     （±25 内 + span 重叠/相接 → 冲突 → trunk += lane*50）
  → 与已布网及元件体均不冲突的车道
  → WIRE 段（端点 = 引脚坐标，硬约束保持）
```

## 关键决策

| 决策 | 说明 |
|------|------|
| LASTPIN 内联而非集中 | Cadence LASTPIN 绑定最近 FORCEADD；集中文件尾会挂到 IOPORT 上被删（SPCOCN-543） |
| mirror 保守不输出 | 04p4/8367 无镜像参考语法；只按 rotation 旋转保证"渲染=坐标"一致，MY/MX 留 P1 |
| 吸网格在坐标源头 | 引脚坐标吸 25 后 LASTPIN 与 WIRE 端点同步移动，保持精确重合（连接硬约束） |
| trunk 车道 _LANE=50 | 不同网 trunk 间距 50（2 格），避免共线；闭区间判定防端点相接短路 |
| fallback 按 pin_number | _fallback_pin_offsets 键是数字，按 pin_name 查永远 (0,0)（U6G 中心塌缩根因） |

---

# Phase XIV 布线美观化架构补充（2026-08-11 追加）

## 模块架构（D5 基类-注册模式）

```
router_base.py: WireRouterBase(ABC) + ROUTER_REGISTRY + register_router 装饰器 + create_router 工厂
    ├── WireLayoutEngine (p0/p0_lane)  ← 现有 P0 车道法（默认，回归零影响）
    ├── DetourRouter (detour)          ← 继承 p0 + stub L/Z 正交绕障
    └── EDIFWireRouter (edif_reuse)    ← 消费 NetIR.wires 折线 + 端点重定

依赖注入：csa_writer._route_page 通过 create_router(mode) 获取 router，
          不 import 具体类；异常 → logger.warning → p0_lane 重试（fallback_to_p0）
```

## 数据流（D1 文本去冲突）

```
page 全部可见文本（$LOCATION/VALUE/SIG_NAME/PIN_TEXT/PORT）
  → TextItem(anchor/movable/priority/net_key)  → bbox 估算（0.65 字宽/1.2 行高/12 padding/75 min_w）
  → O(n²) 碰撞检测 → 优先级迭代微调（SIG_NAME 沿 trunk 移 → VALUE/LOCATION 就近 8 方向 25 网格 → PIN_TEXT 禁动）
  → 对齐（网络名 x=snap25(trunk_min_x+375)/Port 等间距/差分对 P上N下）
  → offsets → csa_writer 标签行（DISPLAY/FORCEPROP）→ LASTPIN/WIRE 坐标不动
```

## 数据流（D3 人工匹配→自动配线）

```
--export-unmatched → unmatched 清单（refdes/引脚数/引脚名/建议候选）
用户填写 manual_matches.yaml（refdes → library_id/section）
  → ConversionEngine._stage_match 后注入覆盖 → catalog 重建（invalidate_caches）
  → pin_coords 用真实符号 css 偏移重算 → LASTPIN/WIRE 全量重算 → 正确连线
校验：引脚数不匹配 → warning 不注入
```

## 数据流（D4 电源匹配）

```
--extra-hdl-lib 挂载 practice hdl_lib（dc_dc 18 变体/ldo/power_dip4）
  → power_ic.yaml 按引脚数+引脚名匹配候选 → power_ic_scorer 评分 → 注入匹配结果
HG5015 U*（26 个 conf=0.4475 部分匹配）→ 候选 dc_dc/ldo（映射规则待 Cadence 实测）
```

## 关键决策

| 决策 | 说明 |
|------|------|
| 所有新功能独立模块+配置开关默认关 | 用户强制：随时增删功能、可回退、高内聚低耦合 |
| wire_layout 保持几何合成 | 布线策略抽象到 Router，wire_layout 只做几何 |
| 标签移动不碰 LASTPIN/WIRE | DEHDL 连接=坐标重合硬约束，标签优化只在 DISPLAY/FORCEPROP 行 |
| 重叠检测只报告不移动 | CIS 原布局是工程师画的，自动移动需 --aesthetic-placement 显式开启 |
| 人工匹配优先于占位 sym | 用户确认的匹配最可靠；占位 sym/EDIF 反推为备选 |
| 'p0' 别名注册 | CLI 默认 mode=p0 与 p0_lane 映射，消除双重回退 warning |

---

# Phase XV Cadence 实测修复架构补充（2026-08-11 追加）

## 模块变化

| 文件 | 变化 | 目的 |
|------|------|------|
| csa_writer.py | `_lastpin_pn` 对齐 04p4（去 PAINT/J 0/R 1）；`_dehdl_rotation`（90↔270 互换）；占位符号集成（_needs_placeholder/_placeholder_for_irec）；IOPORT 边缘分布（_ioport_position_cfg edge_layout）；GND 分布（gnd_distribution） | P0-A/B/E/F + P1-C/D |
| placeholder_lib.py（新） | PlaceholderLibrary：按 EDIF 引脚名/数量生成占位符号（css C 命令 + outline + chips.prt + PLACEHOLDER 标注） | P0-F 主芯片占位 |
| detour_router.py | `_stub_lead_cfg` + override `_route_horizontal/_route_vertical`（lead-out 背离元件体 + lead_map 差异化） | P1-G stub 引出段 |
| wire_layout.py | 保持 P0 单一职责（引出段在 DetourRouter override） | 零回归 |
| config.py | RoutingConfig + stub_lead/lead_differentiate/ioport/gnd_distribution/placeholder 配置类 | 全配置化 |
| __main__.py | --aesthetic 自动启用 detour + ioport.edge_layout + gnd_distribution | 用户"没区别"根因 |

## 数据流（P0-F 占位符号）

```
实例匹配无具体符号（U6 等，原 fallback CH347）
  → _needs_placeholder（无符号 or 引脚不匹配 + 非被动元件）
  → PlaceholderLibrary.symbol_for(pin_names) → PlaceholderSymbol
      （css C 命令按引脚分布 + outline 贴合引脚数 + chips.prt 引脚名表）
  → _placeholder_for_irec memo → body/pin_coords 用占位符号偏移
  → LASTPIN/WIRE 连接成立；元件名/属性标注 PLACEHOLDER
```

## 数据流（P1-G stub 引出段）

```
DetourRouter.route_nets → super() P0 lane 布线
  → override _route_horizontal/_route_vertical：
      每 stub：lead-out 背离元件体（pin_bodies 方向提示）
             → lead_map 差异化（相邻引脚 lead 交替）
             → 引出段 + 垂直 stub 到 trunk
  → detour 绕障（lane 感知）→ dedupe → DOT
```

## 关键决策

| 决策 | 说明 |
|------|------|
| LASTPIN 格式对齐 04p4 | 04p4 实证：$PN 块无 PAINT、R 1、J 0——Cadence 属性绑定 |
| 占位符号替代 CH347 fallback | 错误符号比无符号更误导；占位贴合引脚数/名 + PLACEHOLDER 标注 |
| rotation 90↔270 互换 | OrCAD EDIF orientation 与 DEHDL R 行符号约定相反（L20 实证） |
| aesthetic 自动启用美观布线 | 用户反馈"没区别"根因：aesthetic 未设 mode=detour |
| GND 每芯片分布 | 规范：每芯片附近接地；电气不变（同网 SIG_NAME） |
| stub 引出段在 DetourRouter | wire_layout 保持单一职责（几何合成），P0 零回归 |

---

# Phase XVI 镜像归一化 + IOPORT 核对架构补充（2026-08-11 追加）

## 模块变化

| 文件 | 变化 | 目的 |
|------|------|------|
| coord_transform.py | `rotate_point` 顺序修正（镜像在前旋转在后）+ `apply_edif_orientation` 表驱动入口 + `closest_rotation_for_mirror` | T1 数学基础（EDIF 2.0.0 标准） |
| csa_writer.py | Pass1 镜像引脚精确变换 + `_mirror_rline[refdes]` + Pass2 等效 R 行发射；电源符号 LASTPIN 镜像一致 | T1 集成 + GND 一致修复 |
| ioport_audit.py（新） | IOPORTAuditor（audit_page/finalize/write）+ UnwiredIoport/NameConflict/OrphanIoport | T2 三节检测 |
| aesthetic_report.py | add_mirror + [MIRROR] 节（exact/approx 标注） | T1 报告 |
| config.py + routing.yaml | MirrorCfg（normalize/report）+ IoportCfg 扩展（audit/skip_orphan/manual_names） | 配置开关 |

## 数据流（T1 镜像归一化）

```python
EDIF orientation（R90/R180/R270/MX/MY/MYR90/MXR90）
  → irec.rotation / irec.mirror（edif_parser 已提取）
  → Pass1 _compute_pin_geometry：
      normalize_mirror = cfg.mirror.normalize and mirror
      mirror 实例：off = rotate_point(css_off, rot, mirror)   # 镜像在前旋转在后
                  _mirror_rline[refdes] = _dehdl_rotation(closest_rotation_for_mirror(...))
      → pin_coords（电气硬约束源）→ net_pin_map → WIRE
  → Pass2 _emit_conn_instance_block：mirror 实例 R 行 = _mirror_rline[refdes]
  → aesthetic_report [MIRROR] 节（exact/approx）
```

## 数据流（T2 IOPORT 审计）

```python
DesignConnectivity（stage 后，pin_connections 已注入）——数据源铁律
  → audit_page（每页）：IOPORT 引脚 ∈ routed wires 端点（多引脚网）；单引脚网豁免
  → finalize（全局）：canonical(name) 分组 → 网名一致性 + 孤立 connector
  → ioport_audit_report.txt（SUMMARY/UNWIRED/NAME_CONFLICT/ORPHAN/FIX_SUGGESTION）
```

## 关键决策

| 决策 | 说明 |
|------|------|
| 镜像归一化而非 M 行 | DEHDL MY/MX 语法未验证；引脚坐标精确变换保电气，渲染用最接近旋转近似（chirality 无法纯旋转表达） |
| 镜像在前旋转在后 | EDIF 2.0.0 标准（MXR90 = MX∘R90）；旧实现顺序相反但无组合路径，无回归 |
| 电源符号 LASTPIN 镜像一致 | 与 Pass1 pin_coords 同源（rotate_point(0,±50,mirror)），否则 LASTPIN≠WIRE 断线 |
| 审计基于连通性模型 | raw EDIF 实例 pin_connections 未注入 → 孤立检测 100% 误报 |
| 网名不一致只报告 | 跨页改名有电气风险，manual_names 人工裁决后覆盖 |

---

# Phase XVII 新需求架构补充（2026-08-12 追加）

> 软件交付团队追加（调研+方案阶段，未实现）。方案详见 `docs/archive/temp files/system_design0812-phase17.md`。

## 模块架构（M1-M8，全部独立 + 配置开关）

```
cis2hdl/
├── core/
│   ├── geometry/
│   │   └── collision.py          # M2 统一碰撞库（新）
│   ├── writer/
│   │   ├── mock_icon_lib.py      # M1 temp_lib 模拟图标生成器（新）
│   │   ├── placement_fitter.py   # M3 尺寸适配+挤压+腾挪（新）
│   │   ├── wire_simplifier.py    # M4 电线化简（SKiDL cleanup_wires 移植，新）
│   │   ├── net_name_connect.py   # M5 网络名跨页（新）
│   │   └── pin_connect_audit.py  # M6 引脚连接审计（新）
│   └── config/
│       └── routing.yaml          # +temp_lib/placement/wire_simplify/pin_audit 节
└── gui/
    └── panels/
        └── chip_config_panel.py  # M7 芯片/connector 配置面板（新）
```

## 数据流（M1 temp_lib 模拟图标）

```
匹配结果（未匹配/低置信 refdes）
  → 引脚数据（pin_number/pin_name 来自 EDIF）
  → MockLibrary.symbol_for(refdes, section, pins)
      → 按硬件规范（宽 6/10/24 格、引脚左右边缘、短线外引 50、pitch≥50）
      → symbol.css + chips.prt + entity/master.tag → output/temp_lib/
  → csa_writer FORCEADD <CELL>..1 + CDS_LIB temp_lib + R 行（旋转/镜像）
  → pin_coords/net_pin_map/WIRE 同源（LASTPIN==WIRE 硬约束）
  → NOTE 文本"模拟图标，无标准电气特性"（M8）
```

## 数据流（M2 统一碰撞 + M3 腾挪）

```
geometry: rect/point/segment/label
  → collision.detect_collisions(a, b, margin=25)   # 单一统一函数（用户问题10）
      → 元件vs元件（原 OverlapDetector 复用）
      → 线vs元件 / 线vs线（stub/trunk 避让）
      → DOT vs 元件 / GND vs 元件 / 标签vs标签（text_layout 复用）
  → placement_fitter.resolve(collisions, movable={GND, 标签, 低优先级元件})
      → 沿最小分离向量移动（最多 N 轮）
      → 固定件（芯片/连接器本体）默认不移动（电气安全）
```

## 数据流（M7 GUI 配置 → 转换）

```
GUI 面板（match_review 三栏扩展）
  → 选中元件 → 候选列表（temp_lib 优先）
  → 引脚映射表（CIS引脚 ↔ 目标引脚，下拉可编辑）→ pin_map
  → [分析] → pin_connect_audit: 已接/悬空/不匹配清单
  → [保存] → chip_config.yaml {matches: [{refdes, library_id, pin_map, hanging: []}]}
  → --chip-config 注入 → D3 注入点（_stage_match 后覆盖，同 manual_matches）
  → 重跑转换 → CSA(CDS_LIB temp_lib) + 报告 [PIN_AUDIT]/[HANGING]
```

## 关键决策

| 决策 | 说明 |
|------|------|
| 模拟图标替代占位符号 | mock_icon_lib 按规范绘制（placeholder 仅为逃生舱） |
| 可见文本标注而非属性 | PLACEHOLDER 属性被 Cadence 删（SPCOCN-542）；改图形内 NOTE 文本 |
| 网络名替代 IOPORT | 用户要求 + 规范 §3.2"同层不加 port" |
| 化简后处理而非全量 A* | SKiDL cleanup_wires 移植（MIT）；A* 留远期自动布局 |
| 统一碰撞函数 | 用户问题 10：单一 detect_collisions 反复调用，不按类型各写一个 |
| 悬空引脚直接悬空 | 保留 LASTPIN 不画 WIRE；报告 [HANGING] 待 Allegro 布线 |
| 匹配管线不动 | csv/html/top3 照常生成（硬约束） |
| 引脚数不匹配→占位/temp_lib | LASTPIN 前校验命中 css 引脚，未命中不发射（修 SPCOCN-543） |

---

# Phase XVII 开发架构补充（2026-08-12 追加）

> 软件交付团队。P0 修复 + M1-M8 实现完成（662 passed / 5 skipped）。

## 模块架构（最终落地）

```
cis2hdl/
├── core/
│   ├── writer/
│   │   ├── mock_icon_lib.py      # M1 temp_lib 模拟图标（BGA 四边/功能名/MOCK_TEXT）
│   │   ├── wire_simplifier.py    # M4 SKiDL cleanup_wires 移植
│   │   ├── net_name_connect.py   # M5 网络名跨页（CSA+con 去 IOPORT）
│   │   ├── pin_connect_audit.py  # M6 引脚四状态审计
│   │   ├── overlap_resolver.py   # M3 腾挪（只移 GND/标签）
│   │   ├── overlap_detector.py   # M2 统一 detect_collisions
│   │   ├── csa_writer.py         # P0-1~4 + M1/M4/M5/M6/M8 接入
│   │   ├── placeholder_lib.py    # P0-2 PLACEHOLDER 声明 + entity
│   │   └── text_layout.py        # P0-4 标签随旋转
│   ├── matcher/
│   │   └── manual_matches.py     # M8 v2.0 + load_merged
│   └── engine/
│       └── conversion_engine.py  # --chip-config 注入点
├── gui/
│   └── panels/
│       └── chip_config_panel.py  # M7 PySide6 配置面板
└── config/
    └── routing.yaml              # +temp_lib/wire_simplify/pin_audit/chip_config/ioport.use_net_name
```

## 数据流（M1 temp_lib 模拟图标，最终）

```
未匹配/低置信芯片（引脚数据来自 EDIF）
  → MockIconLibrary.symbol_for(refdes, section, pins)
      → distribute_mock_pin_offsets：三档（≤12 两列 / 12-64 四列 / >64 BGA 四边）
      → 功能名标签（去重 GND/GND_2）+ MOCK_TEXT 字号 24
      → symbol.css + chips.prt + entity → output/temp_lib/
  → csa_writer：mock 实例 CDS_LIB temp_lib（placeholder 仍 hdl_lib）
  → OutputManager.write_cdslib：DEFINE temp_lib temp_lib
  → pin_coords/net_pin_map/WIRE 同源（LASTPIN==WIRE 硬约束）
```

## 数据流（M5 net_name_connect，用户 D2 同步去 con）

```
DesignConnectivity（conn.nets pages）→ 跨页裸网名判定（数据源铁律）
  → ioport_skip_plan：use_net_name=true 时 CSA 不生成 IOPORT 块
  → net_name_labels：线上 SIG_NAME 标签补充（688 条实测）
  → con 层同步去除 IOPORT（用户 D2：con 层也可以去除）
  → CLI --use-net-name 旗标 + routing.yaml ioport.use_net_name
```

## 数据流（M8 统一配置文件）

```
chip_config.yaml（v2.0）          manual_matches.yaml（v1.0 兼容）
  └→ ManualMatchesConfig.load：v2.0 解析 / v1.0 自动升级
       └→ load_merged：v2.0 覆盖 v1.0 同 refdes
            └→ apply_manual_matches（_stage_match 后注入）
                 → MatchResult（pin_map/hanging/placement 全消费）
                 → csa_writer：hanging 保留 LASTPIN 不生成 WIRE
  candidate_selector._save_to_yaml → 统一 chip_config.yaml（删 mapping_rules）
```

## 关键决策（含裁决修正）

| 决策 | 说明 |
|------|------|
| **SIG_NAME PAINT 恢复** | 实读 04p4 golden 推翻"PAINT 是根因"假设；SIG_NAME 块本带 PAINT（L365/L12），$PN 块无（L63）；恢复为 golden 一致 |
| SPCOCN-543 真实根因 | 坐标未命中 + 旋转组合（方案 B/C/D）；PAINT 无关 |
| mock CDS_LIB temp_lib | mock 实例引用 temp_lib + cds.lib DEFINE（P1-2 修复） |
| Config 顶层子节合并 | 修复 12 个子节静默失效 bug（默认值掩盖） |
| 只移 GND/标签 | 芯片本体不动（D10）；M3 贪心腾挪 |
| wire_simplify 默认关 | 可回退；WIRE -32% 实测 |
| use_net_name 默认关 | CLI 旗标 + yaml 双通道 |

---

# Phase XVII 三期架构补充：GND 聚类（2026-08-12 追加）

## 数据流（R3 GND 聚类合并）

```
芯片 GND 引脚分组（每芯片 ≥1）→ chip_gnd_pins
  → 贪心最近邻聚类（cluster_radius=2000，曼哈顿距离）：
      距现有簇质心 ≤ 半径 → 入簇；否则新建簇
  → 每簇 1 个共享 GND 符号：
      _outward_point（芯片外引）+ _gnd_symbol_body（避 outline/引脚 margin 25/50）
  → 簇分组键 GND\g@<refdes1>_<refdes2>（trunk 局部化）
  → Pass2 _emit_power_symbol_block（GND_POWER body，refdes 属性区分）
  → 电气不变：SIG_NAME GND\g 全局连接
```

## 配置

```yaml
gnd_distribution:
  enabled: false          # CLI --gnd-distribute
  cluster_radius: 2000    # R3 聚类半径（用户 D4；0=关闭聚类回退每芯片 1 个）
  near_chip_offset: 100 / distance_threshold: 2000 / max_per_chip: 1
```

## 关键决策

| 决策 | 说明 |
|------|------|
| 贪心最近邻而非 KMeans | 引脚数少（页均 <100），O(n²) 足够；KMeans 需 sklearn 依赖 |
| 合成 GND 复用 GND_POWER body | 避免新建符号库；refdes 属性区分；Cadence 兼容 |
| cluster_radius 默认 2000 | 用户 D4"先试不行反馈" |
| 0=关闭聚类 | 回退每芯片 1 个（Phase XV 行为），可回退 |
