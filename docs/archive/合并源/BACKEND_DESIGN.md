# CIS2HDL 后端引擎设计

> 版本: v1.1.0 | 日期: 2026-08-07 | 状态: 修订 | 更新: 匹配层改为 v2.0 两阶段；错误码 31→44；EDIF 角色改为 pin 连接注入（Stage 5.5）；新增 PST 数据源章节；HDLLibScanner 输出统一 ComponentDB

---

## 1. 总览

后端引擎实现完整的转换管道：**诊断 → 解析 → 扫描 → 匹配 → 校验 → 生成**（`ConversionEngine` 六阶段 `_stage_diagnose/_stage_parse/_stage_scan/_stage_match/_stage_validate/_stage_generate`）。

所有模块通过统一的中间表示（IR）进行通信。**器件库部分详见 [`COMPONENT_ARCHITECTURE.md`](COMPONENT_ARCHITECTURE.md)**。

### 核心架构原则

- **一个 ComponentDef 统治所有**：CIS 和 HDL 的器件使用完全相同的 Python 类，绝不按格式分叉
- **基类-注册模式**：解析器、匹配器、写入器均通过 `ParserBase`/`MatcherBase`/`WriterBase` 基类 + `Registry` 注册，不按器件类型分叉
- **格式只在边界层处理**：Parser 负责"格式 → IR"，Writer 负责"IR → 格式"，中间所有逻辑只操作 IR

---

## 2. 中间表示模型（IR）

### 2.1 设计原则

- 使用 **Pydantic BaseModel** 保证类型安全和自动验证
- 字段全类型注解
- 序列化支持（JSON/YAML 用于调试和规则存储）
- 坐标字段纳入 IR（Phase I 即具备）

### 2.2 核心模型定义

**器件库模型**（详见 `COMPONENT_ARCHITECTURE.md` §2）：

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

## 3. 解析层实现策略

### 3.0 双路并行架构

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

> **EDIF 角色演进（v1.1.0）**：早期 EDIF 承担"Phase I-A 先行验证"（快速逻辑验证）；后期主要角色改为 **pin 连接注入（Stage 5.5）**——在 `ConversionEngine._stage_generate` 中调用 `EDIFParser.extract_pin_net_map()` 将 pin→net 映射注入 `ComponentInstanceIR.pin_connections`（详见 `SYSTEM_ARCHITECTURE.md §2.1.1`）。

### 3.0a EDIF Parser（路径 A — 早期 Phase I-A 先行）

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

### 3.0b DSN ↔ EDIF 交叉验证器

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

> 多源三路比对（DSN/EDIF/PSTXNET，自动降级 2-source）见 `SYSTEM_ARCHITECTURE.md §2.1.1` 与 `core/diagnostics/multi_source.py`。

### 3.0c PST 辅助数据源（Phase IX）

PST 文件由 OrCAD Capture 的 PSTWRITER 生成，作为 DSN/EDIF 之外的第三数据源，主要服务匹配增强与 pin 连接补充：

| 解析器 | 输入 | 输出 | 用途 |
|--------|------|------|------|
| `PstchipParser` | `pstchip.dat`（LIBRARY_PARTS） | `{symbolic_name → PART_NAME/JEDEC_TYPE/VALUE/pin numbers}` | 向 `ComponentDef.extra_data` 注入 JEDEC 类型与标称值（Phase 1 先验 + Phase 2A 尺寸比对） |
| `PstxnetParser` | `pstxprt.dat`（EXPANDEDPARTLIST） | `{refdes → part_name/section/INSxxx}` | refdes → primitive 映射，桥接 pstxnet.dat 与 EDIF（v0.8.1 支持多行 PART_NAME） |
| `PstxnetNetlistParser` | `pstxnet.dat`（EXPANDEDNETLIST） | `{refdes → {pin → net}}` | pin→net 网络连接补充（Stage 5.5b 主数据源；DSN/EDIF 网络缺失时的兜底） |

> 注入路径：`ConversionEngine._stage_match` 注入 PST JEDEC 到 `extra_data`；`_stage_generate` 中 Stage 5.5（EDIF pin 注入）与 Stage 5.5b（PSTXNET pin 注入，Primary）共同补齐 `pin_connections`。

### 3.1 Binary DSN Parser（路径 B — Phase I-B 主力）

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
        #    → 详见 SYSTEM_ARCHITECTURE.md §2.1.1
        
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

> 二进制解析算法要点（OleReader `count_page_candidates()` 回退规则、`parse_strlst` 逐字节步骤、Cache uint16 陷阱、RTL 虚假实例过滤、EDIF 3023 实例、CrossValidator 8 项比对、MultiSourceCrossValidator）见 **`SYSTEM_ARCHITECTURE.md §2.1.1`**（唯一正式归宿，本节不重复展开）。

### 3.2 HDL 器件库扫描

**输出统一 `ComponentDB`**（v1.1.0；旧版 `HDLComponentDB` 已废弃——CIS 与 HDL 器件共用同一 Schema，见 `COMPONENT_ARCHITECTURE.md §2`）。

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
```

---

## 4. 匹配层实现

### 4.1 设计原则

- **匹配在 IR 层进行**：输入输出都是 `ComponentDef`，不感知数据来源格式
- **v2.0 两阶段架构**：Phase 1 类型假设生成 → Phase 1.5 候选池构建 → Phase 2A/2B 类型内匹配（被动确定性规则 / 主动加权评分）
- **final_conf = phase1_prior × phase2_within**；`STOP_SEARCH=0.75` / `NEEDS_REVIEW=0.40`
- **MultiScorer 已删除**：跨类型加权评分被证明结构上不可靠，前缀是硬约束而非软权重
- 详见 `COMPONENT_ARCHITECTURE.md` §4

### 4.2 匹配管道（v2.0 两阶段）

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

### 4.3 历史演进：旧版四级匹配器（v2.0 之前）

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

## 5. 生成层实现

> **落地位置（v1.1.0）**：生成层实际位于 `core/writer/`（旧设计 `generator/` 已废弃）。已落地写入器：`CPMWriter`（.cpm）、`SCHWriter`（.sch.N.M）、`CSAWriter`（.csa MACRO_DRAWING，当前主输出）、`CDSLibWriter`（cds.lib）、`XconWriter`（.xcon）、`CPCWriter`（.cpc）、`ScrWriter`（.scr）、`MappingCSVWriter`（{project}_mapping.csv）、`OutputManager`（DEHDL 目录树编排）、`ErrorLogger`（{project}_errors）。写入器注册统一在 `core/writer/base.py` 的 `WriterRegistry`；完整清单见 `SYSTEM_ARCHITECTURE.md §2.4`。

### 5.1 SCH 文件生成

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

### 5.2 坐标布局算法

由于 DSN 中有器件坐标，可直接映射到 SCH 坐标系：

> 坐标映射器 `LayoutMapper` 实际落地于 `core/parser/layout_mapper.py`（ConvertDocToUser 公式：用户坐标 = 文档坐标 × (1.0 / 物理粒度)，见 `ORCAD_SOURCE_ANALYSIS.md §10.2 + §13.2`）。CSA 输出的坐标映射另有 `core/writer/csa_writer.py._map_coords_to_dehdl()`（BoundingBox 居中缩放 ×0.7 + Y 轴翻转，fallback 网格布局 5 列 × 间距 2000×1500）。

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

### 5.3 CPM 文件生成

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

## 6. ConversionEngine（主控）

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

## 7. 诊断与容错管道（已落地 core/diagnostics/）

### 7.1 设计原则

对标 Cadence Professional 工具的 Project Manager → Check References → DRC 三层验证体系。

- **诊断优先于转换**：任何文件操作之前先运行完整的文件完整性校验
- **用户引导式错误处理**：每个错误/警告/信息都附带可操作的建议
- **降级优于失败**：当部分数据缺失时，给出明确的数据损失标注 + 降级路径
- **结构化输出**：所有诊断信息以 JSON 序列化，前端可渲染为彩色面板

### 7.2 诊断管道架构

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

### 7.3 错误诊断引擎（ErrorDiagnosisEngine）

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

### 7.4 文件恢复策略（FileRecoveryStrategy）

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

