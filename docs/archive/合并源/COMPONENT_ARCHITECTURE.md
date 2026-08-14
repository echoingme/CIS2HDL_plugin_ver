# CIS2HDL 器件库统一架构设计

> 版本: v1.1.0 | 日期: 2026-08-07 | 状态: 修订 | 更新: 匹配策略改为 v2.0 两阶段；ComponentDBSerializer/JSON 持久化标注未落地；IR 模型补充 extra_data 字段说明

---

## 0. 核心结论（回答架构关键问题）

| 问题 | 答案 |
|------|------|
| **CIS 和 HDL 的元件库格式是否统一？** | ❌ **完全不同**。CIS 用 `.olb` 二进制，HDL 用 `.sym`+`.ptf`+`chips.prt` 文本，必须转换 |
| **OLB 内容可以转换吗？** | ✅ 可以。OLB 内部的 Package(31)/Device(32)/LibraryPart(24) 结构包含完整器件定义 |
| **软件可以支持自定义元件吗？** | ✅ 必须支持。用户可在 HDL 库中自由增删 `.sym`/`.ptf`/`chips.prt` |
| **可以读取和存储元件吗？** | ✅ `HDLLibScanner` 读取 HDL 库 → 统一 `ComponentDB`（CIS 与 HDL 共用 Schema），CIS 侧从 .dsn Cache 提取 |
| **是否每个元件一套实现？** | ❌ **绝对不行**。所有器件在 IR 层统一为 `ComponentIR`，不按格式/类型分叉 |

---

## 1. CIS 和 HDL 器件库格式差异

### 1.1 格式对比

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

### 1.2 OLB 内部结构（代码验证）

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

### 1.3 HDL 库内部结构（来自实践项目分析）

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

## 2. 统一器件数据模型（单一数据源设计）

### 2.1 核心原则：一个 ComponentIR 统治所有格式

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

### 2.2 为什么不是每个格式一套类

```
❌ 错误做法（会导致数据库管理混乱）：
   320 个器件类型 × 2 种格式 = 640 个类，完全失控

✅ 正确做法（本项目采用，已通过 Cadence TCL API 验证）：
   DBO 对象层次（Cadence 内部）：Design→Schematics→Pages→PartInsts/Wires/Globals/Ports...
   其中 PartInsts 统一用 ObjectType 31 (Package) 管理，不按器件类型分叉
   → 我们的 ComponentDef 完全复制此模式
```

### 2.3 CDS 属性系统参考（来自 capDB/cdsprop.txt）

HDL 设计中的属性分为 5 大类（解析层需支持这些属性的映射）：

**电气属性**：ALLOW_CONNECT, BIDIRECTIONAL, DIR, DELAY, RISE, FALL, INPUT_LOAD, OUTPUT_LOAD

**物理属性**：LOCATION, LOCATION_CLASS, XY, ROT, SEC

**设计属性**：MODEL, PART_NUMBER, PHYS_DES_PREFIX, VALUE, VER, GROUP, ROOM

**显示属性**：5 种模式（0=不显示, 1=仅值, 2=名和值, 3=仅名, 4=有值时显示名和值）

**属性继承规则**：`inherit(body/pin/signal)`, `permit(body/pin/signal)`

### 2.4 ISCF 网络分类模型（来自 Cadence 内部交换格式）

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

## 3. 器件数据库设计（统一管理）

### 3.1 两个数据库，一个 Schema

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

### 3.2 数据来源

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

## 4. 匹配层设计（基于统一模型）

### 4.1 匹配在 IR 层进行

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

### 4.2 匹配策略（v2.0 两阶段）

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
- 旧版四级管道（Exact → Fuzzy → Feature → Manual）已被 v2.0 两阶段取代，Exact/Fuzzy/Feature 在 v2.0 中作为 ActiveMatcher 类型内链组件；历史描述见 `BACKEND_DESIGN.md §4.3`

---

## 5. 自定义元件支持

### 5.1 用户自定义元件流程

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

### 5.2 元件数据库持久化

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

## 6. 解析器与写入器注册架构

### 6.1 基类-注册模式

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

### 6.2 解析器清单

| 解析器 | 输入 | 输出 | 器件提取方式 |
|--------|------|------|-------------|
| `EDIFParser` | `.edf` | `DesignIR` | S-expression 提取 cell/instance/pin/net；后期承担 pin 连接注入（Stage 5.5） |
| `DSNParser` | `.dsn` | `DesignIR` | OleReader → Cache Stream → Package(31)+Device(32)+LibraryPart(24) → ComponentDef[] |
| `HDLLibScanner` | HDL 库目录 | `ComponentDB` | 文本解析 chips.prt + symbol.css + part.ptf → ComponentDef[]（统一 ComponentDB） |
| `PstchipParser` | `pstchip.dat` | JEDEC_TYPE/VALUE 映射 | PST 数据源，补充封装尺寸与标称值（用于匹配增强） |
| `PstxnetParser` | `pstxprt.dat` | refdes → primitive 映射 | PST 数据源，refdes → 器件名/INSxxx（桥接 pstxnet/EDIF） |
| `PstxnetNetlistParser` | `pstxnet.dat` | pin → net 映射 | PST 数据源，网络连接补充（Stage 5.5b 主数据源） |

---

## 7. 完整数据流

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

## 8. 文件完备性对器件库的影响分析

### 8.1 输入完整度 → 器件匹配能力矩阵

| 提供文件 | 可提取信息 | 匹配策略可用（v2.0 两阶段口径） | 匹配质量 |
|---------|-----------|-------------|:--:|
| 仅 .dsn | 位号、坐标、引脚编号、引脚-网络连接 | 仅类型内精确（Phase 2，无封装/值 → Phase 1 先验弱） | 低（无引脚名/封装/值） |
| .dsn + .edf | 以上 + 引脚名 + 属性 + 网络名 | Phase 1 + 类型内链（有器件名/value） | 中（有器件名模糊匹配） |
| .dsn + .olb | 以上 + 引脚名 + 封装 + 默认值 + 符号 | Phase 1 + 完整类型内链（Exact/Fuzzy/Feature/Value） | 高（有完整属性特征提取） |
| .dsn + .olb + .edf | 以上 + 交叉验证 | v2.0 两阶段全管道（含 PST 交叉验证） | 最高（多路验证一致） |

### 8.2 OLB 缺失时的降级器件数据流

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
