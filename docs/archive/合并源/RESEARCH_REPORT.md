# CIS-to-HDL 原理图转换工具 — 技术调研报告

> 版本: v1.2 | 日期: 2026-07-29 | 更新: 添加完整DSN格式规范、网络命名规范、BOM格式、135器件库完整目录
>
> 修订: v1.3 | 日期: 2026-08-07 | StructureType 枚举按实际代码修正（删 PartInstance=11/SymbolPinScalar=26/SymbolPinBus=27，补 Junction=50）；器件库目录数 135→131（口径：排除备份目录）；§4.3 .sch 格式推断标注证伪（Cadence 不识别，现输出 .csa）

---

## 1. 项目背景与目标

### 1.1 课题来源

Mentor 任务：复习 Allegro Cadence 体系，实现原理图从 OrCAD Capture CIS 格式到 Cadence Design Entry HDL（原 Concept HDL）格式的转换。

### 1.2 核心挑战

- OrCAD Capture CIS 的原理图以 `.dsn`（二进制）和 `.olb`（二进制）格式存储
- Design Entry HDL 以 `.cpm`（文本）+ `.sch.N.M`（文本）+ `.sym/.ptf`（文本）分布式存储
- CIS 源文件器件命名不符合公司规范，需模糊匹配映射到 HDL 器件库
- 转换涉及三个核心维度：**器件寻找**、**引脚对应**、**网络名转换**

---

## 2. Cadence SPB 生态系统速查

### 2.1 完整的 18 个功能模块

| 编号 | 模块 | 职能 |
|:---:|------|------|
| 1 | Design Entry HDL | HDL 原理图编辑器（前 Concept HDL） |
| 2 | Design Entry CIS (Capture CIS) | CIS 原理图编辑器（前 OrCAD Capture） |
| 3 | DEHDL Rules Checker | HDL 电气规则检查 |
| 4 | Layout Plus | 原 OrCAD PCB 设计（已淘汰） |
| 5 | Layout Plus SmartRoute | 原 OrCAD 布线 |
| 6 | Library Explorer | 库浏览器 |
| 7 | Online Documentation | 在线文档 |
| 8 | Model Integrity | IBIS/SPICE 模型验证 |
| 9 | Package Designer | IC 封装设计 |
| 10 | **PCB Editor** | **PCB 版图编辑器（核心）** |
| 11 | PCB Librarian | 封装库开发 |
| 12 | PCB Router | 自动布线 |
| 13 | PCB SI | 信号完整性/电源完整性分析 |
| 14 | Allegro Physical Viewer | 只读版图浏览器 |
| 15 | **Project Manager** | **项目总控台** |
| 16 | SigXplorer | 网络拓扑提取与仿真 |
| 17 | PSpice / AMS Simulator | 模拟/混合信号仿真 |
| 18 | PCB Editor Utilities | 辅助工具集 |

### 2.2 CIS vs HDL 文件格式对比

| 维度 | OrCAD Capture CIS | Design Entry HDL |
|------|-------------------|------------------|
| **项目配置** | `.opj`（文本） | `.cpm`（文本） |
| **原理图主文件** | `.dsn`（二进制 CFB 容器） | `.sch.N.M`（文本，每页独立） |
| **器件库** | `.olb`（二进制，一个库一个文件） | `.sym` + `.ptf` + `.chk`（分散文本文件） |
| **库索引** | 无外部索引 | `cds.lib`（文本） + `lib.def` |
| **备份** | `.dbk` / `.obk` | 无特定备份格式 |

### 2.3 CIS 与 HDL 在数据流中的位置

```
CIS 路径:  .dsn + .olb → [Export Physical] → pstxnet/part/chip.dat → Allegro PCB Editor
HDL 路径:  .cpm + .sch + .sym → [Export Physical] → pstxnet/part/chip.dat → Allegro PCB Editor
                                           ↑
                                  网表层完全相同！
```

**关键洞察**：CIS 和 HDL 在网表层（`pstx*.dat` 三件套）说出同一种语言，因此 PCB 布线后端完全共享。差别仅在原理图编辑前端，这也是本转换工具的存在意义。

### 2.4 CIS 和 HDL 是否使用 VHDL/Verilog 语言？

**结论：不。两者都是图形化原理图工具，与 VHDL/Verilog 无关。**

- "Design Entry HDL" 中的 "HDL" 是历史命名巧合，不是 "Hardware Description Language"
- 但 Capture CIS 支持将原理图**导出**为 Verilog/VHDL 网表（用于 FPGA/ASIC 流程）
- Design Entry HDL 支持与 NC-Verilog 协同仿真
- 以上均为边缘功能，与本项目无关

---

## 3. 现有开源方案调研

### 3.1 OpenOrCadParser（C++20）

| 属性 | 值 |
|------|-----|
| 仓库 | `github.com/Werni2A/OpenOrCadParser` |
| 语言 | C++20, CMake 构建 |
| 许可证 | Apache 2.0 |
| 状态 | 活跃开发中（2024年6月仍在更新） |
| 覆盖 | `.dsn` 和 `.olb` 的完整二进制解析 |
| 输出 | XML 导出、结构树打印、文件提取 |

**架构要点**：
- 底层：Microsoft CFB（Compound File Binary）容器解析
- 中层：DSN/OLB 内部结构解码（基于 XSD 反向工程）
- 高层：提供 C++ API 供外部程序调用
- 依赖：Boost.ProgramOptions, compoundfilereader, fmt, spdlog, TinyXML2

**对本项目的价值**：最强的 DSN/OLB 解析能力，可作为后端 C++ 解析引擎直接嵌入或通过 Python binding 调用。

### 3.2 Upverter Universal Format Converter（Python 2）

| 属性 | 值 |
|------|-----|
| 仓库 | `github.com/bithium/schematic-file-converter` |
| 语言 | Python 2（历史项目，2011-2013） |
| 许可证 | Apache 2.0 |
| 状态 | 已停止维护 |
| 覆盖 | KiCad, gEDA, Eagle, Gerber, DSN（测试中） |

**架构要点**：
- 采用 parser → 内部 OpenJSON → writer 三段式架构
- DSN 解析器处于 "in testing" 阶段，不完整
- 无 HDL 输出支持

**对本项目的价值**：架构思想可借鉴（三段式转换管道），但代码过于陈旧（Python 2）。

### 3.3 Universal-Netlist MCP Server — 核心代码分析

| 属性 | 值 |
|------|-----|
| 仓库 | `github.com/IntelligentElectron/universal-netlist` |
| 语言 | TypeScript / Node.js |
| 覆盖 | Cadence CIS/HDL 网表 (.dat), Altium, KiCad, **DSN 二进制直接解析** |

**架构要点（源代码级）**：

```
src/parsers/cadence/dsn/
├── dsn-parser.ts          # 顶层调度器，协调各子解析器
├── binary-reader.ts       # DataStream 的 TypeScript 移植（从 OpenOrCadParser）
├── page-parser.ts         # 页面流解析 → 器件实例、网络、图形
├── component-builder.ts   # 从解析数据构建 Component 对象
├── net-builder.ts         # 构建 Net 连通性关系
├── pin-resolver.ts        # 引脚编号解析：Package pinMap → 物理引脚
├── cache-parser.ts        # 设计缓存解析 → CachedLibraryPart
├── library-parser.ts      # Library 流解析
├── generic-parser.ts      # 通用结构解析工具
├── structures.ts          # 底层二进制结构定义
└── structure-types.ts     # TypeScript 类型定义
```

**解析流程**：

```
.dsn 文件
  → OleReader (CFBF 容器打开)
    → parsePage() x N 页     → Wire, Instance, Net 信息
    → parsePackageStream()   → Device pinMap
    → parseCacheStream()     → CachedLibraryPart
    → parseLibraryStrLst()   → Library 引用
    → buildDeviceIndexMap()  → 引脚索引
    → buildNetConnectivity() → 网络连通性
    → buildComponents()      → 完整 Component 对象
  → ParsedNetlist
```

**对本项目的价值**：
- 最清晰的 DSN 解析参考实现（模块化、类型安全）
- BinaryReader 是 DataStream 的完整 TypeScript 移植，可直接参考设计 Python 版本
- 分离的 Page/Cache/Library/Package 解析器 → 架构设计直接可借鉴

### 3.4 OpenAllegroParser — Allegro 二进制解析

| 属性 | 值 |
|------|-----|
| 仓库 | `github.com/Werni2A/OpenAllegroParser` |
| 语言 | C++17 |
| 覆盖 | `.brd`, `.pad`, `.dra`, `.psm`, `.ssm`, `.fsm`, `.osm`, `.bsm`, `.mdd` |

**核心能力**：
- 解析 `.pad` 文件 → padstack 名称、钻孔信息、焊盘层定义、尺寸/形状
- 支持 `.pxml` XML 导出
- 参数暴力搜索（因部分结构动态大小无法确定）

**对本项目的价值**：HDL 器件库导入器可以直接参考 `.pad` 解析逻辑。

### 3.5 orcad-netlist — Python 网表解析器

| 属性 | 值 |
|------|-----|
| 仓库 | `github.com/...` (本地副本) |
| 语言 | Python 2 |
| 覆盖 | `pstchip.dat`, `pstxnet.dat`, `pstxprt.dat` |

**核心数据模型**：

```python
class Part:        # pstxprt.dat → 器件实例 + 属性
class Primitive:   # pstchip.dat → 物理器件管脚定义
# pstxnet.dat → net_name → [Node列表]
```

**Parsing 架构**：逐行状态机 + stripquotes 工具函数

**对本项目的价值**：最简洁的网表解析参考实现，可直接 Python 3 化。

### 3.6 python-altium — Python EDA 二进制解析架构

| 属性 | 值 |
|------|-----|
| 仓库 | `github.com/nicerloop/python-altium` |
| 语言 | Python 3 |
| 覆盖 | Altium `.SchDoc` → SVG |

**架构模式**：

```python
# OLE → Record Iterator → Properties Parser → Object Tree → Renderer
ole = OleFileIO(file)
stream = ole.openstream("FileHeader")
records = iter_records(stream)
records = (parse_properties(stream, r) for r in records)
sheet = Object(properties=next(records))
objects = [sheet]
for properties in records:
    obj = Object(properties=properties)
    objects[obj.properties.get_int("OWNERINDEX")].children.append(obj)
```

**核心设计**：`Object` 基类 + `properties` 字典 + `children` 列表 → 树形数据结构

**对本项目的价值**：Python 原生 OLE 解析模式可直接用于 DSN 解析（`olefile` 库读取 CFB）。

### 3.7 CadenceOSHW — 开源测试数据集合

| 属性 | 值 |
|------|-----|
| 仓库 | `github.com/Werni2A/CadenceOSHW` |
| 内容 | 收集的 Cadence 开源硬件项目、库文件 |

**对本项目的价值**：提供了大量可用于测试验证的 `.dsn`, `.brd` 文件链接（`repos_table.md`）。

### 3.8 Cadence Allegro 文件扩展名完整参考

| 文件 | 来源 |
|------|------|
| `cadence_allegro_file_extensions.txt` | Kumargs PCB Design Blog (2009) |

包含 `.brd`, `.dra`, `.mdd`, `.psm`, `.bsm`, `.osm`, `.ssm`, `.fsm`, `.pad`, `.scr`, `.tech`, `.mcm`, `.txt`, `.jrl`, `.tag`, `.ini`, `.geo`, `.color` 的完整用途说明。

| 方案 | 类型 | 能力 |
|------|------|------|
| Elgris E-studio Pro | 商业 | 专业 EDA 格式互转（含 CIS↔HDL） |
| cap2con.exe | Cadence 旧工具 | SPB 15.7 时代的原理图转换（已停止支持） |
| Cadence PCB Librarian Expert | Cadence 内置 | 可转库器件（.olb → .sym），但不能转完整原理图 |

---

## 4. 核心技术路径深度分析

### 4.1 解析层 — DSN/OLB 二进制格式（源码级）

#### 4.1.1 OLE/CFB 容器层

DSN 使用 **Microsoft Compound File Binary (CFB)** 格式，规范定义在 [MS-CFB](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-cfb/)。

**OleReader 实现（TypeScript 完整移植，可直接参考设计 Python 版）**：

```
构造函数流程:
  readFileSync(filePath)
  → validateMagic()              // D0CF11E0A1B11AE1 8字节魔数
  → parseHeader()                // 512字节头 → sectorSize, FAT, miniFAT, dirStart
  → buildFat()                   // 遍历 FAT sector 链，建立扇区映射表
  → readDirectories()            // 遍历目录扇区，128字节/entry，UTF16LE名称
  → buildMiniFat()               // mini stream FAT 链
  → readMiniStream()             // 根 entry 的小数据流

常用接口:
  - listAllEntries()             // → {path, entry}[]  层级路径列表
  - readStreamByPath(path)       // → Buffer           按路径读取流数据
  - readStream(name)             // → Buffer           按名称读取流数据
  - getDirectoryTree()           // → string           可读的目录树
```

**头部解析**（512 bytes @ offset 0）：
```
Offset 0-7:   魔数 D0 CF 11 E0 A1 B1 1A E1
Offset 26-27: majorVersion (uint16LE)
Offset 28-29: byteOrder 必须是 0xFFFE (little-endian)
Offset 30-31: sectorSizePower → sectorSize = 1 << power (通常512)
Offset 32-33: miniSectorSizePower → miniSectorSize (通常64)
Offset 48-51: dirStartSector (uint32LE)
Offset 56-59: miniStreamCutoff (uint32LE, 通常4096)
Offset 60-63: miniFatStartSector (uint32LE)
Offset 68-71: difatStartSector (uint32LE)
Offset 76-511: 前109个FAT扇区号 (uint32LE each)
```

**目录条目**（128 bytes/entry）：
```
Offset 0-63:   名称 (UTF16LE, 长度由 offset 64 指定)
Offset 64-65:  名称长度 (uint16LE, 含null终止符)
Offset 66:     类型 (1=Storage 2=Stream 5=Root)
Offset 68-71:  leftSiblingId (uint32LE, 红黑树)
Offset 72-75:  rightSiblingId (uint32LE)
Offset 76-79:  childId (uint32LE)
Offset 116-119: startSector (uint32LE)
Offset 120-123: streamSize (uint32LE)
```

**DSN 内部流结构（从实际 .dsn 文件推断）**：
```
Views/{DesignName}/Pages/PAGE1       ← 每页原理图 (type 2)
Views/{DesignName}/Pages/PAGE2       ← ...
Views/{DesignName}/Hierarchy/Hierarchy ← 层次信息
Packages/{PkgName}                   ← 器件封装定义
Packages/{PkgName}_1                 ← 多单元器件的单元1
{DesignName}.DBFile/Cache            ← 缓存 (CachedLibraryPart)
{DesignName}.DBFile/Library          ← 库引用 (strLst 字符串表)
Views/{DesignName}/LFile             ← 布局文件
```

#### 4.1.2 BinaryReader — 类型化二进制读取

**核心 API（OpenOrCadParser DataStream → TypeScript BinaryReader → Python BinaryReader）**：

```python
class BinaryReader:
    """位置跟踪的二进制 Buffer 读取器。所有整数为 little-endian。"""
    
    def __init__(self, buffer: bytes, offset: int = 0): ...
    def tell(self) -> int: ...           # 当前位置
    def remaining(self) -> int: ...      # 剩余字节数
    def is_eof(self) -> bool: ...        # 是否到末尾
    def seek(self, offset: int): ...     # 跳转到绝对位置
    def skip(self, n: int): ...          # 跳过 n 字节
    def peek(self, n: int) -> bytes: ... # 预览不移动位置
    
    # 类型化读取 (全部 little-endian)
    def read_uint8(self) -> int: ...
    def read_uint16(self) -> int: ...
    def read_uint32(self) -> int: ...
    def read_int8(self) -> int: ...
    def read_int16(self) -> int: ...
    def read_int32(self) -> int: ...
    
    # 字符串读取
    def read_string_zero_term(self) -> str: ...     # null终止字符串
    def read_string_len_term(self) -> str: ...      # uint16长度前缀，无null终止
    def read_string_len_zero_term(self) -> str: ... # uint16长度前缀+null终止
    
    def read_bytes(self, n: int) -> bytes: ...
    def discard_bytes(self, n: int): ...
```

#### 4.1.3 DSN Structure Parsing — 通用解析框架

**所有 DSN 内部结构的通用解析模式**：

```
1. autoReadPrefixes(reader, futureData, structureType)
   → 读取结构类型前缀链
   → 每项前缀：读取 blockSize → FutureDataList.push(preambleOffset, blockSize)
   
2. readPreamble(reader)
   → 验证魔数 FF E4 5C 39 (4 bytes)
   → reader.readUint32() → 偏移量
   → reader.readUint32() → 未知字段
   
3. futureData.checkpoint()
   → 验证当前位置与 FutureData 的预期 stopOffset 匹配
   
4. 读取结构体特有字段 (特定顺序的 typed reads)
   
5. futureData.checkpoint()
   → 再次验证
```

**StructureType 枚举（关键类型，按 cis2hdl/core/parser/dsn/structures.py 实际枚举核对）**：
```python
class StructureType(IntEnum):
    Page = 10                # 页面容器
    PlacedInstance = 13      # 放置的器件实例 (核心!)
    T0x10 = 16               # 引脚-网络连接点 (核心!)
    WireScalar = 20          # 标量连线
    WireBus = 21             # 总线连线
    Port = 23                # 端口
    LibraryPart = 24         # 缓存库部件
    Package = 31             # 封装定义
    Device = 32              # 器件定义 (含 pinMap)
    Global = 37              # 全局网络标记 (如VCC/GND)
    OffPageConnector = 38    # 跨页连接器
    SymbolDisplayProp = 39   # 符号显示属性
    Alias = 49               # 网络别名
    Junction = 50            # 连接点
    TitleBlock = 65          # 标题栏
```
<!-- 已修改：按实际枚举删除 PartInstance=11、SymbolPinScalar=26、SymbolPinBus=27（实际代码中不存在），补 Junction=50；原有注释保留 -->

#### 4.1.4 关键结构体字段详解

**PlacedInstance（结构体Type=13）—— 原理图上的每个器件**：
```
读取顺序:
  reader.skip(8)                              # unknown
  pkgName = reader.readStringLenZeroTerm()    # 封装名
  dbId = reader.readUint32()                  # 数据库ID
  reader.skip(8)                              # unknown
  locX = reader.readInt16()                   # 放置X坐标
  locY = reader.readInt16()                   # 放置Y坐标
  reader.skip(4)                              # unknown
  lenProps = reader.readUint16()              # 显示属性数量
  symbolDisplayProps: [SymbolDisplayProp]     # 循环读取
  reader.skip(1)                              # unknown
  reference = reader.readStringLenZeroTerm()  # 位号! (REFDES)
  partValueIdx = reader.readUint32()          # Value的strLst索引
  reader.skip(10)                             # unknown
  lenT0x10s = reader.readUint16()             # 引脚连接点数量
  t0x10s: [T0x10]                             # 循环读取
  sourcePackage = reader.readStringLenZeroTerm() # 源封装
  reader.skip(2)                              # unknown
```

**T0x10（结构体Type=16）—— 引脚到网络的连接点**：
```
读取顺序:
  pinIndex = reader.readUint16()              # 1-based逻辑引脚索引
      特殊处理: if pinIndex >= 32768: pinIndex = 65536 - pinIndex
  pointX = reader.readInt16()                 # 连接点X
  pointY = reader.readInt16()                 # 连接点Y
  netId = reader.readUint32()                 # 网络ID (key!)
  reader.skip(4)                              # unknownInt
  lenProps = reader.readUint16()              # 显示属性
  symbolDisplayProps: [SymbolDisplayProp]
```

**SymbolDisplayProp（结构体Type=39）**：
```
读取顺序:
  reader.skip(4)                              # id
  nameIdx = reader.readUint32()               # 属性名 strLst 索引
  x = reader.readInt16()
  y = reader.readInt16()
  rotFontBitField = reader.readUint16()       # 低14位=字体索引, 高2位=旋转
  propColor = reader.readUint8()
  reader.skip(2)                              # visibility
  reader.skip(1)                              # assumed 0x00
```

**Wire（结构体Type=20/21）**：
```
读取顺序:
  segmentId = reader.readUint32()
  id = reader.readUint32()
  reader.skip(4)                              # color
  startX = reader.readInt32()
  startY = reader.readInt32()
  endX = reader.readInt32()
  endY = reader.readInt32()
  reader.skip(1)
  lenAliases = reader.readUint16()
  aliases: [Alias]                            # 网络名标注
  lenSDPs = reader.readUint16()               # display props
```

**Package（结构体Type=31）**：
```
  name = reader.readStringLenZeroTerm()
  reader.readStringLenZeroTerm()              # sourceLibrary (skip)
  refDes = reader.readStringLenZeroTerm()
  reader.readStringLenZeroTerm()              # unknownStr1
  pcbFootprint = reader.readStringLenZeroTerm()
  lenDevices = reader.readUint16()
  devices: [Device]
```

**Device（结构体Type=32）—— 含pinMap**：
```
  unitRef = reader.readStringLenZeroTerm()    # 单元引用
  refDes = reader.readStringLenZeroTerm()     # 位号前缀
  pinCount = reader.readUint16()
  for i in range(pinCount):
      strLen = reader.readInt16()
      if strLen == -1: pinMap[i] = null       # 空引脚标记
      else:
          reader.seek(back 2)
          pinName = reader.readStringLenZeroTerm()
          reader.skip(1)                       # bitMapPinGrpCfg
          pinMap[i] = pinName
```

#### 4.1.5 Component Building（从解析数据到完整器件）

```
PageData (per page):
  ├── name: str
  ├── netTable: Map<int, string[]>     # netId → [net_name, net_alias...]
  ├── wires: Wire[]                     # 线段的坐标信息
  ├── placedInstances: PlacedInstance[] # 器件列表
  ├── globals: GraphicInst[]           # 全局信号(VCC/GND)
  ├── ports: GraphicInst[]             # 端口
  └── offPageConnectors: GraphicInst[] # 跨页连接器

Component Building 流程:
  1. 遍历所有 pages 中的 PlacedInstance
  2. 对每个 inst, 通过 findCachedPart() 查找:
     a. exact pkgName match in cachedParts
     b. sourcePackage + ".Normal" variant
     c. stripped sourcePackage (去尾 _N suffix)
  3. 从 strLst[partValueIdx] 获取 value
  4. 从 prefixProperties 获取 MPN (Part Number / Manufacturer PN)
  5. DNS 标记清除: 移除 DNI/DNM/DNP/DNS/_NC 后缀
  6. 引脚名解析:
     a. 从 CachedLibraryPart.pinNames[T0x10.pinIndex] 获取逻辑引脚名
     b. 从 pinMap 通过 resolvePinNumber() 获取物理引脚编号
  7. 网络连接:
     a. 通过 netTable[T0x10.netId] 获取网络名
     b. 处理 OffPageConnector/Global 的跨页网络合并
  8. 引脚名歧义消除: 重复引脚追加 #pinNum

结果: ComponentDetails = { refdes: { pins: {pinNum: {name, net}} } }
```

#### 4.1.6 网表解析 (pstxprt/pstxnet/pstchip.dat)

**orcad-netlist 脚本的解析架构**（Python 2 → 直接 Python 3 移植）：

```python
class Part:        # pstxprt.dat 解析结果
    name_: str     # 位号 (如 "C1")
    desc_: str     # 描述 (如 "'100NF_0402C-S_10%_16V-0402C-S'")
    properties_: dict  # 属性字典

class Primitive:   # pstchip.dat 解析结果
    name_: str     # 器件名
    pins_: list    # 引脚编号列表
    properties_: dict

# 解析函数签名:
# parseXprt(file) → partsList: dict[str, Part]
# parseXnet(file) → netsList: dict[str, list[str]]  # netName → ["U3.17", ...]
# parseChip(file) → primitiveList: dict[str, Primitive]
```

**状态机解析模式**：
```python
while True:
    line = file.readline().strip()
    if line == "PART_NAME":
        # 进入器件解析状态
    elif line == "NET_NAME":
        # 进入网络解析状态
    elif line == "primitive":
        # 进入原始器件解析状态
    elif line == "END.":
        break
```

#### 4.1.7 Altium .SchDoc → Python OLE 解析模式

**可直接复用的 OLE 解析架构**：

```python
from olefile import OleFileIO

def read_schdoc(file_path: str) -> Object:
    ole = OleFileIO(file_path)
    
    # 1. 读取 FileHeader 流
    stream = ole.openstream("FileHeader")
    records = iter_records(stream)
    records = (parse_properties(stream, record) for record in records)
    
    header = next(records)
    parse_header(header)
    header.check_unknown()
    
    # 2. 构建对象树
    sheet = Object(properties=next(records))
    objects = [sheet]
    for properties in records:
        obj = Object(properties=properties)
        owner_idx = obj.properties.get_int("OWNERINDEX")
        objects[owner_idx].children.append(obj)
        objects.append(obj)
    
    # 3. 解析 Additional 流 (可选)
    if ole.exists("Additional"):
        # 同上模式
        ...
    
    return sheet
```

**Object 基类设计模式**：
```python
class Object:
    """Altium 原理图对象的通用容器"""
    def __init__(self, *, properties=None):
        self.properties = properties  # PropertyList 实例
        self.children: list[Object] = []  # 子对象列表
    
# 树形结构: Sheet → [Component, Wire, NetLabel, Port, ...]
# 通过 OWNERINDEX 属性建立父子关系
```

### 4.2 匹配层 — 器件模糊搜索（源码级增强）

#### 问题场景

CIS 原理图的器件命名不规范，如 `RES_0603_10K` 需映射到 HDL 规范库中的 `RES_0603_10K_5%_1/10W`。

#### 从 reference code 中提取的匹配增强思路

**component-builder.ts 的 MPN/Value 提取方法**：
- `MPN_KEYS = {"Part Number", "PART_NUMBER", "MPN", "Manufacturer PN"}` ← prefixProperties 中识别
- `DNS_MARKERS = /(?:,\s*(?:DNI|DNM|DNP|DNS|NC)|...)/gi` ← 清洗 Do-Not-Stuff 标记
- `findCachedPart()` 使用三种 key 策略：exact pkgName → sourcePackage.Normal → stripped sourcePackage

**应用到匹配器，三级 key 查找策略**：
```python
def find_match_candidate(cis_part: ComponentIR, hdl_db: HDLComponentDB):
    # Strategy 1: Exact pkgName (= sourcePackage)
    if match := hdl_db.get_exact(cis_part.part_name):
        return match
    
    # Strategy 2: sourcePackage + variation (.Normal suffix pattern)
    variant = cis_part.part_name.rsplit(".", 1)[-1] if "." in cis_part.part_name else "Normal"
    sp_key = f"{cis_part.source_package}.{variant}"
    if match := hdl_db.get_exact(sp_key):
        return match
    
    # Strategy 3: Stripped sourcePackage (remove trailing _N unit suffix)
    stripped = re.sub(r'_\d+$', '', cis_part.source_package)
    ...
```

**pin-resolver.ts 的引脚解析逻辑**：
- `pinMap: (string | null)[]` — null 标记空引脚
- `deviceUnitRefs` — 处理多 unit 器件（每个 unit 有独立 pinMap）
- `resolvePinNumber()` 通过 sourcePackage + unitRef 组合 key 查找

#### 推荐算法组合

```
第1轮: 精确匹配 → 指纹哈希（Footprint + Value + Pin Count）
        + 三级 key 查找策略 (来自 component-builder.ts)
第2轮: 模糊匹配 → rapidfuzz token_sort_ratio 器件名模糊匹配
第3轮: 特征提取 → 正则解析阻值/容值/封装/引脚数，结构化比对
        + MPN key 匹配 (来自 component-builder.ts)
第4轮: 人工确认 → 低于阈值的候选 → GUI 交互确认
```

### 4.3 生成层 — HDL 文件格式

#### 需要生成的文件清单

| 文件 | 格式 | 内容 |
|------|------|------|
| `{project}.cpm` | 文本（INI-like） | 项目配置（库引用、字体、网格、设计名） |
| `cds.lib` | 文本（DEFINE 语法） | 库注册索引 |
| `lib.def` | 文本 | 库定义 |
| `worklib/{design}/top.sch.1.1` | 文本（结构块） | 原理图第 1 层第 1 页 |
| `worklib/{design}/top.sch.1.2` | 文本 | 原理图第 1 层第 2 页 |
| `worklib/{design}/sub.sch.2.1` | 文本 | 子模块页 |
| `worklib/{design}/sub.sym` | 文本 | Block 符号 |
| `component_lib/*/XXX.sym` | 文本 | 器件符号 |
| `component_lib/*/XXX.ptf` | 文本 | 器件 Part Table |
| `component_lib/*/XXX.chk` | 文本 | 器件校验文件 |

#### .sch 文件格式特征（从公开样本推断）

> ⚠️ **推断已被 binary_diff_report 证伪**：Cadence DEHDL 不识别本推断格式，实际转换输出为 `.csa`（MACRO_DRAWING）原生格式，不再生成 `.sch`。以下推断仅作历史参考保留。

```
VERSION 6
BEGIN SCHEMATIC
  BEGIN ATTR                ← 属性块
    DeviceFamilyName "xxx"
  END ATTR
  BEGIN NETLIST             ← 网络清单块
    SIGNAL net_name
    SIGNAL bus_name(7:0)
    PORT Input port_name
    PORT Output port_name
    BEGIN BLOCKDEF ...      ← Block 符号定义
    END BLOCKDEF
    BEGIN BLOCK refdes ...  ← 器件实例
      PIN pin_name net_name
    END BLOCK
    ...
  END NETLIST
  BEGIN SHEET 1 WIDTH HEIGHT  ← 页面图形
    BEGIN INSTANCE refdes x y R0   ← 器件放置
    END INSTANCE
    BEGIN BRANCH net_name          ← 连线
      WIRE x1 y1 x2 y2
    END BRANCH
    IOMARKER x y signal R0 28      ← 端口标记
  END SHEET
END SCHEMATIC
```

---

## 4.3 网络命名规范（来自 universal-netlist 分析标准）

### 4.3.1 地网络命名标准

| 名称 | 典型用途 |
|------|---------|
| `GND` | 默认地 |
| `VSS` | 模拟/电源地 |
| `AGND` | 模拟地 |
| `DGND` | 数字地 |
| `PGND` | 电源地 |
| `SGND` | 信号地 |
| `CGND` | 机壳地 |

### 4.3.2 电源轨命名推荐

| 前缀 | 含义 | 示例 |
|------|------|------|
| `PP` | 正电源轨 | `PP3V3`, `PP5V`, `PP1V8` |
| `PN` | 负电源轨 | `PN5V`, `PN12V` |
| `LD_` | 负载侧（电流检测后） | `LD_PP3V3` |

### 4.3.3 信号命名陷阱（必须在转换时检测）

| 坏名 | 为什么歧义 | 应改为 |
|------|-----------|--------|
| `-RESET`, `+SENSE` | 前缀 +/- 被读为电源极性 | `nRESET`, `RESET_L`, `SENSE` |
| `PN_BUS`, `PPI_CLK` | 与 PP/PN 电源前缀冲突 | `PERIPH_BUS`, `PERIPH_CLK` |
| `VIN_SEL`, `VOUT_EN` | VIN/VOUT 被读为电源轨 | `U5_VIN_SEL`, `U5_VOUT_EN` |
| `VCC_OK`, `VDD_GOOD` | VCC/VDD 被读为电源轨 | `PG_VCC_CORE`, `PG_VDD_IO` |

### 4.3.4 差分对规范

必须使用一致的 `_P` / `_N` 后缀：`USB_DP, USB_DN` / `PCIE0_TX_P, PCIE0_TX_N`

### 4.3.5 总线规范

使用 `NAME[0]..NAME[N]` 或 `NAME_0..NAME_N`，不允许跳位。

### 4.3.6 对转换工具的启示

转换工具必须在 NetNameValidator 中检查：
- 网络名是否以 `+`/`-`/`PP`/`PN`/`VCC`/`VDD`/`VIN`/`VOUT` 开头（逻辑信号）
- 地网络是否使用了标准名称
- 差分对后缀是否一致
- DNS 标记是否存在于结构化字段（而非仅图形标注）

---

## 4.4 BOM 输出格式标准（来自公司实际文件）

### 4.4.1 BOM.rpt 格式

```
TITLE:                 Bill of Materials
DATE:                  08/13/2025
DESIGN:                switch_practice
TEMPLATE:              D:\software1\Cadence\SPB_16.6\share\cdssetup\template.bom

BOM_SEQ   SN_NUM        TYPE_NAME   SPECIFICATION   PACKAGE_TYPE   Ref Des        Qty  BOM_IGNORE
========  ============  ==========  =============   ============   =============  ===  ==========
AA01      M01.010301    片式电容    100nF ±10% 16V  C0402          C1,C2,...      64   ?
                                    0402(X7R)
```

### 4.4.2 BOM_SEQ 编码（完整确认）

| BOM_SEQ | 含义解析 |
|---------|---------|
| **AA01** | A(贴片) + A(电容) + 01(0402封装) |
| **AA02** | A(贴片) + A(电容) + 02(0603封装) |
| **AA03** | A(贴片) + A(电容) + 03(0805封装) |
| **AB01** | A(贴片) + B(电阻) + 01(0402封装) |
| **AC00** | A(贴片) + C(集成电路) + 00(非标准封装) |
| **AD00** | A(贴片) + D(晶体/晶振) + 00 |
| **AE00** | A(贴片) + E(二极管) + 00 |
| **AF00** | A(贴片) + F(三极管/MOS管) + 00 |
| **AI00** | A(贴片) + I(电感) + 00 |
| **AJ00** | A(贴片) + J(LED灯) + 00 |
| **AK00** | A(贴片) + K(插针/插座) + 00 |
| **AN00** | A(贴片) + N(BOM不出) + 00 |

### 4.4.3 SN_NUM 编码

| SN_NUM | 含义 |
|--------|------|
| M01.010301 | M01(物料大类) . 01(电容子类) 03(0805) 01(序列) |
| M02.010055 | M02(电阻大类) . 01(0402) 0055(序列) |
| M01.020079 | M01(电容) . 02(0603) 0079(序列) |

---

## 4.5 公司 HDL 器件库完整目录（131个器件类，口径：排除备份目录）

### 4.5.1 无源器件（Passive Components）

| 器件目录名 | 类型 | 封装 |
|-----------|------|------|
| `capacitor` | 电容 | 0402/0603/0805/1206/1210/1808/1812/0201 + 电解 |
| `resistor` | 电阻 | 0402/0603/0805/1206/1210/... |
| `inductor` | 电感 | 通用 |
| `inductor_gm` | 共模电感 | 通用 |
| `fb` | 磁珠 | 通用 |
| `crystal` | 无源晶振 | 通用 |
| `osc` | 有源晶振 | 通用 |
| `c_transformer` | 电流变压器 | 通用 |
| `v_transformer` | 电压变压器 | 通用 |
| `network_tf` | 网络变压器 | 通用 |
| `diode` | 二极管 | 通用 |
| `led` | LED灯 | 通用 |
| `n_mos` | N沟道MOS管 | 通用 |
| `p_mos` | P沟道MOS管 | 通用 |
| `npn` | NPN三极管 | 通用 |
| `pnp` | PNP三极管 | 通用 |
| `optocoupler` | 光耦 | 通用 |
| `fuse` | (不在列表中，通过temp/) |
| `connector` | 接插件 | 通用 |
| `con3` | 3针接插件 | 通用 |
| `rj11` | RJ11插座 | 通用 |
| `rj45` / `rj45_1x5` | RJ45插座 | 通用 |
| `key` | 按键开关 | 通用 |
| `filter` | 滤波器 | 通用 |
| `diplexer` | 双工器 | 通用 |

### 4.5.2 电源器件（Power）

| 器件目录名 | 类型 |
|-----------|------|
| `dc_dc` | DC-DC转换器 |
| `ldo` | LDO稳压器 |
| `auxiliary` | 辅助电源 |
| `power_dip4` | 4脚DIP电源模块 |

### 4.5.3 IC器件（按功能分类）

**网络交换芯片**：
`88e6071`, `88e6320`, `bcm53125`, `bcm56150k`, `bcm56760`, `bcm88470`, `mt7531ae`, `rtl8305nb`, `rtl8367`, `rtl8367n`, `zl88601`

**CPU/MCU**：
`zx279128s`, `zx279200`, `lpc176x`, `hc32f005c6ua`, `mimxrt1011dae5a`, `ec340egc`

**WiFi/射频**：
`rtl8192fr`, `rtl8192xar`, `rtl8812fr`, `rtl8814`, `rtl8832ar`, `mt7603`, `mt7613`, `mt7916an`, `mt7976cn`, `mt7976dan`, `mt7976dn`, `mt7981b`, `fem_2g`, `fem_5g`

**以太网PHY**：
`rtl8201f`, `rtl8211f`, `rtl8221b`, `rtl8290b`, `b50210sb0`, `b50285`

**PON/GPON**：
`rtl9601d`, `rtl9607`, `rtl9607dq`, `rtl9617b`, `gn25l95`, `gn25l99`, `gn28l95`, `gpy211`, `en7571n`, `cw30p10d`, `bosa`, `udt26a05l05gt07`

**SLIC/语音**：
`le9622`, `le9643`, `si32178`, `si32919`, `si3402`, `pef3100x`, `pef32001`, `pef32002`

**其他IC**：
`att7022e` (电能计量), `ds1302` (RTC), `eeprom`, `flash`, `ft232rl` (USB-UART), `hdc1080` (温湿度), `lm75` (温度), `pcf8591` (ADC/DAC), `sgm41282c` (电池管理), `ad7170` (ADC), `abs10` (整流桥)

**逻辑/放大器**：
`logic_gate`, `amplifier`

**电源管理IC**：
`an7552ct`, `an8855h`, `tmi39610`, `tmi7608r`, `uc2843`, `ux3328`, `jwh5125ch`

**FPGA/CPLD**：
`lcmxo2`, `lcmxo3`

**DDR/存储**：
`ddr`, `w634gu6qb`, `fm15l023uk6`

**接口**：
`interface`, `catv`, `rs232`

**其他**：
`reset` (复位IC), `pusb3f96` (USB保护), `rtc7646` / `rtc7676e` (RTC芯片), `pq2016`, `mald_02101c`

### 4.5.4 特殊符号

| 器件目录名 | 类型 | 说明 |
|-----------|------|------|
| `vcc_circle` | 电源符号 | 圆形VCC标记 |
| `gnd_earth` | 地符号 | 大地 |
| `gnd_power` | 地符号 | 电源地 |
| `mark` | 标记 | PCB标记 |
| `hole` | 安装孔 | 机械孔 |
| `screw` | 螺丝孔 | 机械孔 |
| `BGA353C65P23X20_1500X1300X140` | BGA封装 | 353脚BGA |
| `flan` | 法兰/屏蔽 | 机械 |
| `temp` | 临时/测试库 | 包含 connector, db9, diode, diplexer, interface, ldo, led, mod, mt7603, osc, p_mos, rtl8192xar |

### 4.5.5 命名规律总结

1. **芯片 IC**：全小写，使用芯片型号（如 `rtl8367`, `zx279128s`）
2. **无源器件**：功能名小写（`capacitor`, `resistor`, `inductor`）
3. **分立器件**：`n_mos`, `p_mos`, `npn`, `pnp`, `diode`
4. **特殊符号**：描述性命名（`vcc_circle`, `gnd_power`）
5. **封装专用**：IPC标准命名（`BGA353C65P23X20_1500X1300X140`）

### 4.5.6 对模糊匹配的启示

CIS 源器件名可能是任意格式（如 `RES_0603_10K`），HDL 目标库的命名更加规范。匹配策略应：
- 提取 CIS 器件名中的关键词（`RES`→`resistor`, `CAP`→`capacitor`, 芯片型号保持原样）
- 芯片型号直接小写化后精确/模糊匹配
- 无源器件需要 Value + Footprint 组合匹配 part.ptf 中的行

### 5.1 后端

| 组件 | 技术 | 理由 |
|------|------|------|
| 核心语言 | Python 3.12+ | 快速原型、丰富生态、跨平台 |
| DSN/OLB 解析 | C++ 桥梁调用 OpenOrCadParser | 已有成熟的 C++ 解析器 |
| 或纯 Python | python-ppmd（CFB 解析） + 自定义解码 | 避免 C++ 编译依赖 |
| 模糊匹配 | rapidfuzz | 高性能、C 扩展 |
| 正则引擎 | re (built-in) | 特征提取 |
| 中间表示 | Python dataclasses / Pydantic | 类型安全的数据模型 |
| 验证 | pytest | 标准测试框架 |

### 5.2 前端

| 组件 | 技术 | 理由 |
|------|------|------|
| GUI 框架 | PySide6 (Qt for Python) | 跨平台、成熟组件库、原生性能 |
| 或备选 | Tauri + React | 现代化 Web 前端 + Rust 后端 |
| 原理图预览 | 自绘 Canvas / QGraphicsView | DSN 图形渲染 |
| 差异显示 | 自研 diff 视图 | 转换前后对比 |

### 5.3 推荐最终选型：Python + PySide6

- Python 生态在 EDA 辅助工具领域最丰富
- PySide6 提供 TreeView（项目管理）、QGraphicsView（原理图渲染）、TableView（数据表格）等原生组件
- 跨平台（Windows/Linux/macOS）
- 可通过 pybind11 桥接 OpenOrCadParser 的 C++ 解析能力

---

## 6. 风险与难点评估

| 风险项 | 严重程度 | 应对策略 |
|--------|:--------:|----------|
| DSN 二进制格式复杂度 | 高 | EDIF 先行快速验证逻辑 → Binary DSN 解析基于逻辑验证结果推进；两路交叉校验 |
| 公司 HDL 器件库规范未知 | 高 | 预留可配置的匹配规则引擎 |
| 多 Part 器件（如 74HC00）映射 | 中 | 单独处理 Section 拆分逻辑 |
| 总线格式差异 | 中 | 建立 CIS↔HDL 总线格式转换规则表 |
| 电源网络隐式连接 | 中 | 从 pstchip.dat 推断电源管脚，显式添加 |
| 特殊字符/非法命名 | 低 | 建立非法字符清洗映射表 |
| 跨页 Off-Page Connector | 低 | 同名信号自动连接的 HDL 特性天然支持 |

---

## 7. 参考文献与资源

1. OpenOrCadParser: https://github.com/Werni2A/OpenOrCadParser
2. Upverter Universal Format Converter: https://github.com/bithium/schematic-file-converter
3. Universal-Netlist MCP: https://github.com/IntelligentElectron/universal-netlist
4. Cadence Community: cap2con discussion - https://community.cadence.com/
5. OrCAD XSD 文件: `C:\Cadence\SPB_17.4\tools\capture\tclscripts\capDB\`
6. 《Cadence 16.6电路设计与仿真从入门到精通》
7. Cadence SPB 官方文档: https://www.cadence.com/
8. Elgris E-studio: https://www.elgris.com/content/edif_translators.html
