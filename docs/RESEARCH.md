# RESEARCH（调研与参考知识总文档）

> **文档定位**：CIS2HDL 项目调研与参考知识总文档，由 4 份调研类文档内容保全式合并而成。
> **合并日期**：2026-08-07
> **合并原则**：内容保全式分卷 —— 源文档章节逐节保留（仅调标题层级），不改写原文句子；新增本合并说明、章节映射表与合并保全声明。
> **权威口径**：版本 v1.1.0；错误码 44；匹配 v2.0；DSN StructureType 实际枚举（Page10 / PlacedInstance13 / T0x10=16 / WireScalar20 / WireBus21 / Port23 / LibraryPart24 / Package31 / Device32 / Global37 / OffPageConnector38 / SymbolDisplayProp39 / Alias49 / Junction50 / TitleBlock65，无 11/26/27）；hdl_lib 器件数 131（排除备份）；standard/ 88；writer 层含 csa/sch/cpm/cdslib/xcon/cpc/scr/mapping_csv/output_manager。

---

## 合并说明

### 来源文档（4 份）

| 合并后 Part | 来源文档 | 行数 | 内容主题 |
|:---:|:---|:---:|:---|
| Part I | `ORCAD_SOURCE_ANALYSIS.md` | 1327 | Cadence SPB 16.6 源文件深度分析（XSD/HDL/cds.lib/器件模板/BOM/EDIF/TCL/SPICE） |
| Part II | `RESEARCH_REPORT.md` | 955 | 技术调研报告（Cadence 生态、开源方案、技术路径、网络命名、BOM、器件库目录） |
| Part III | `REFERENCE_READING_NOTES.md` | 1111 | 参考库逐文件精读笔记（CIStoHDL_standard 18 个文件条目） |
| Part IV | `FILE_INDEX_AND_MAPPING.md` | 586 | 文件索引与功能映射（参考库 ↔ 当前项目） |

### 合并规则

1. **内容保全**：四份源文档全部章节、表格、代码块、附录、目录树、器件清单逐节完整保留；仅调整标题层级（原文档 `#`→Part 首部来源说明、`##`→`###`、`###`→`####`、`####`→`#####`），不改写原文句子。
2. **Part 首部**：每个 Part 注明来源文档、原文档标题、合并方式与源文档注记。
3. **交叉引用**：源文档内互链改为新文档内引用（如"见 FILE_INDEX_AND_MAPPING"→"见 Part IV"、"见 REFERENCE_READING_NOTES.md"→"见 Part III"）。
4. **重复内容**：跨文档重复信息（如器件库目录 131、StructureType 枚举等）按来源分别保留，并在 Part 首部加注。
5. **源文档只读**：本次合并不修改、不删除任何源文档。
6. **格式修复（仅 Part I）**：ORCAD_SOURCE_ANALYSIS.md 自 §9.7 起存在未闭合代码围栏，导致源文档 §10~§18 标题落入代码块；合并时仅补一个 ``` 闭合标记（不改写任何内容行），恢复标题与代码块的正常显示。

---

## 章节映射表

| 合并后章节 | 来源文档 | 源章节 |
|:---|:---|:---|
| Part I | `ORCAD_SOURCE_ANALYSIS.md` | §0~§18（19 个一级章节，含编号跳跃 §9→§11→§10→§12） |
| Part II | `RESEARCH_REPORT.md` | §1~§7（含重复编号 §4.3×2、缺失 §5 标题） |
| Part III | `REFERENCE_READING_NOTES.md` | 文件 #1~#18（18 个精读条目） |
| Part IV | `FILE_INDEX_AND_MAPPING.md` | 参考库数据流总览 + Part A~D + 附录（数据结构对照） |

---

## Part I: Cadence 格式深度分析（来源：ORCAD_SOURCE_ANALYSIS.md）

> **来源文件**：`docs/ORCAD_SOURCE_ANALYSIS.md`（1327 行）
> **原文档标题**：《OrCAD SPB 16.6 源文件深度分析报告》
> **合并方式**：逐节保全，仅调标题层级（原文档 `#`→Part 首部来源说明、`##`→`###`、`###`→`####`、`####`→`#####`），不改写原文句子。
> **源文档注 1（编号跳跃）**：源文档 §9→§11→§10→§12 存在章节编号跳跃（§10 位于 §11 之后），为原始编号，本次合并原样保留（源文档内已有加注）。
> **源文档注 2（围栏修复）**：源文档自 §9.7 起存在一个未闭合的代码围栏（```），导致原文档中 §10~§18 的标题落入代码块内。本次合并仅补充该围栏的闭合标记（不改写任何内容行），使标题恢复为真实标题、代码块恢复为代码块；§17.2 目录计数 123 为 `cis_for_reference/hdl_lib/` 口径（排除备份），非公司 `hdl_lib` 的 131 口径。


> 版本: v1.0 | 日期: 2026-07-30 | 基于对 28,205 个 Cadence 安装文件的深度分析
>
> 修订: v1.0.1 | 日期: 2026-08-07 | 计数修正（standard/ 91→88、cis_for_reference/hdl_lib 124→123）；CTW 模板数量加注（以 6.3 节表格为准）；§10/§11 章节编号跳跃加注（内容不受影响）

---

### 0. 分析概要

| 指标 | 数值 |
|------|:---:|
| 分析文件总数 | 28,205 |
| 关键代码/配置文件 | ~500 |
| 分析耗时 | ~45 分钟（5 个并行 Agent + 直接读取） |

#### 关键目录与研究成果

| 目录 | 内容 | 项目价值 |
|------|------|:---:|
| `capDB/` | DSN/OLB XSD Schema + Cadence TCL API | ⭐⭐⭐⭐⭐ |
| `standard/` | HDL 标准符号库 (88 个符号目录) | ⭐⭐⭐⭐⭐ |
| `cdssetup/ctw/devices/` | 器件模板定义 (PIN_ALIAS 映射) | ⭐⭐⭐⭐⭐ |
| `cdssetup/template.bom` | BOM 模板格式 | ⭐⭐⭐⭐ |
| `capture/tclscripts/capDB/` | DSN/OLB 操作 TCL 脚本 | ⭐⭐⭐⭐ |
| `capture/netforms/` | 网表格式化器 DLL 列表 | ⭐⭐⭐ |

---

### 1. DSN/OLB 二进制格式 — 官方 XSD 验证

#### 1.1 PartInst 元素（DSN XSD, 行 1865-1965）

XSD 官方定义的器件实例属性与我们 Binary DSN Parser 的 PlacedInstance 完全一致：

```xml
<xs:element name="PartInst">
  <xs:attribute name="dbId" type="xs:long" />
  <xs:attribute name="deviceDesignator" type="xs:string" />
  <xs:attribute name="libName" type="xs:string" />
  <xs:attribute name="locX" type="xs:long" />     ← 坐标 X！
  <xs:attribute name="locY" type="xs:long" />     ← 坐标 Y！
  <xs:attribute name="name" type="xs:string" />
  <xs:attribute name="pkgName" type="xs:string" />
  <xs:attribute name="rotation" type="xs:long" />
  <xs:attribute name="mirror" type="xs:long" />
  <xs:attribute name="color" type="xs:long" />
```

子元素：
- `PCBLib` — 封装库引用
- `GraphicName` — 图形名称
- `PartInstUserProp` (name, val) — 用户属性（含 Value, MPN, PCB Footprint 等）
- `PartInstDisplayProp` (locX, locY, name, rotation) — **显示属性**（= SymbolDisplayProp!）
- `PartValue` — 器件值
- `Reference` — 位号

**结论**：XSD 官方格式与我们 Binary DSN Parser 的 `PlacedInstance` 结构体定义完全吻合，验证了分析路径正确。

#### 1.2 Package 元素（OLB XSD, 行 2698-2798）

```xml
<xs:element name="Package">
  <xs:attribute name="alphabeticNumbering" type="xs:long" />
  <xs:attribute name="isHomogeneous" type="xs:long" />
  <xs:attribute name="name" type="xs:string" />
  <xs:attribute name="refdesPrefix" type="xs:string" />
  <xs:attribute name="pcbLib" type="xs:string" />
  <xs:attribute name="pcbFootprint" type="xs:string" />
```

每个 Package 包含多个 `LibPart`：
- `NormalView` → `SymbolColor`, `SymbolBBox` (x1, x2, y1, y2), `IsPinNumbersVisible`, `IsPinNamesVisible`
- `ContentsLibName`, `ContentsViewName`

**结论**：Package = 我们的 `Package` Structure(31)，包含 `refdesPrefix`（位号前缀，如"R"/"C"/"U"）和 `pcbFootprint`。

#### 1.3 TCL API 验证

`capExportDesignCache.tcl` 确认：
- `ObjectType 31 = PACKAGE` — 与 StructureType 31 一致
- `NewCachesIter` → `NextCachedObject` API 遍历 Design Cache
- `GetName` 提取包名 → 创建 .olb → `CopyPackageAll`

`capDesignUtil.tcl` 确认 API：
- `searchText`, `replaceText` — 搜索替换
- `searchAlias`, `replaceAlias` — 别名操作
- `searchOffPageText`, `replaceOffPageText` — OffPage 操作
- `capVisitPageAliases`, `capVisitPageOffPages` — 页面遍历

---

### 2. HDL 文件格式 — 完整定义

#### 2.1 symbol.css 格式

基于对 `vcc_circle/sym_1/symbol.css`, `gnd/sym_1/symbol.css`, `offpage/sym_1..6/symbol.css` 的分析：

| 指令 | 语法 | 含义 |
|------|------|------|
| **C** | `C x y "TEXT" a b c d e f L` | 文本标签（C=Comment） |
| **L** | `L x1 y1 x2 y2 -1 width` | 线段（L=Line） |
| **A** | `A cx cy radius startAngle endAngle 0` | 弧线（A=Arc） |
| **T** | `T x y rotx roty fontsize ... ` + 续行文本 | 多行文本块 |
| **P** | `P "KEY" "VALUE" x y rotx roty fontsize ...` | 属性键值对 |

示例 — VCC_CIRCLE：
```
C 50 -50 "VCC_CIRCLE" 55 -65 0 1 15 0 L
L 50 -30 50 -50 -1 0
A 50 -15 15 0.00 359.91 0
P "HDL_POWER" "VCC_CIRCLE" 425 -125 0.00 0.00 41 0 0 0 0 0 0 0 32
P "BODY_TYPE" "PLUMBING" 55 -43 0.00 0.00 16 0 0 0 0 0 0 0 0
```

关键属性：
- `HDL_POWER` = 电源网络名称
- `BODY_TYPE` = "PLUMBING"（管道式图形）
- `OFFPAGE` = "TRUE"（跨页连接器标记）

#### 2.2 chips.prt 格式

```
FILE_TYPE=LIBRARY_PARTS;
primitive 'DEVICE_NAME';
  pin 'PIN_NAME'<pin_idx>:
    PIN_NUMBER='RANGE_OR_FIXED';
  end_pin;
  body
    BODY_NAME='...';
    SIZE='N';
    CLASS='IO/IN/OUT/...';
    JEDEC_TYPE='...';
  end_body;
end_primitive;
END.
```

#### 2.3 pinlist.txt 格式（Lisp-like）

```lisp
(Pinlist
    (Pin
        (Name G)
        (Type UNSPEC)
        (Location Top)
        (InputLoadLow )
        (CheckLoad Off)
        (CheckIO Off)
    )
)
```

#### 2.4 metadata/ 目录结构

每个 HDL 库器件目录包含：
```
{vcc_circle,gnd,offpage,...}/
├── metadata/
│   ├── master.tag          ← 主标签（二进制）
│   ├── pdv_validation.txt  ← PDV 验证信息
│   ├── pinlist.txt         ← 引脚列表
│   ├── revHistory.log      ← 修订历史
│   └── revision.dat        ← 版本数据
├── sym_1/
│   ├── master.tag
│   └── symbol.css          ← 符号图形（文本）
└── sym_N/                  ← 多视图（如 offpage 有 6 个视图）
```

#### 2.5 cds.lib 格式

```
DEFINE standard ../library/standard
SOFTINCLUDE ../library/vlog_cds.lib
SOFTINCLUDE $CHDL_LIB_INST_DIR/share/library/cds.lib
```

---

### 3. 器件模板系统（Component Template Wizard）

#### 3.1 器件定义文件（cdssetup/ctw/devices/）

17 个标准器件模板：<!-- 注：CTW 器件模板数量以 6.3 节表格 21 行为准（此处 17 为早期统计口径） -->

```
capacitor.txt   — DEVNAME='C', PIN_ALIAS '1','+'/'2','-'
resistor.txt    — DEVNAME='R', PIN_ALIAS '1','A'/'2','B'
inductor.txt    — DEVNAME='L'
diode.txt       — 二极管
opamp3.txt      — 3脚运放
opamp5/6/7.txt  — 多脚运放
transistor.txt  — 三极管
jfet.txt        — JFET
mos.txt         — MOS管
power.txt       — 电源
ground.txt      — 地
vdc/vpulse/vsinusoidal/vsquare/vvar.txt — 仿真源
varistor.txt    — 变阻器
capacitorvar/resistorvar.txt — 可变器件
```

#### 3.2 PIN_ALIAS 映射规则

```python
# 电阻引脚别名
PIN_ALIAS '1' = '1', 'A', 'A<0>', 'A<SIZE-1..0>'
#           物理 逻辑  标量  总线低位  总线范围
```

#### 3.3 BOM 模板（cdssetup/ctw/templates/）

10 个模板文件：
```
bulkcapsleft/right.txt           — 批量电容布置（左/右）
bypassinstcapsleft/right.txt     — 旁路电容（实例级）
bypasspincapsleft/right.txt      — 旁路电容（引脚级）
dpseries.txt                     — 差分对串联
```



### 4. template.bom 格式

```
FILE_TYPE=BOM;
BEGIN_BOM_PARMS;
    TITLE = "Bill of Materials";
    DATE = TRUE;
    DESIGN = TRUE;
    TEMPLATE = TRUE;
    COLUMN_SEP = ' ';
    COLUMN_PAD = ' ';
    ROW_SEP = '';
    HEADER_SEP = '=';
    MISSING_VALUE = "?";
    INST_RANGE = TRUE;
    RANGE_SEP = "-";
    RANGE_MIN = 3;
    PAGE_LENGTH = 0;
    CALLOUT_FILE = "bom.callouts";
    SPREADSHEET = FALSE;
...column definitions...
```

### 5. CIS 网表格式化器 DLL 列表

`capture/netforms/` 包含 60+ 个格式化器 DLL：

| DLL | 目标格式 |
|-----|---------|
| `orTelesis.dll` | Telesis 网表（Allegro 内部） |
| `orPadspcb.dll` | PADS PCB |
| `orPcad.dll` | PCAD |
| `orprotel2.dll` | Protel/Altium |
| `orEdif.dll` | EDIF |
| `orPldnet.dll` | PLD 网表 |
| `orVectron.dll` | Vectron |
| `orCadnetix.dll` | Cadnetix |

---

### 6. 对 cis2hdl 项目的关键启示

#### 6.1 Binary DSN Parser 验证 ✅

XSD 官方 Schema 完全验证了我们的 StructureParser 理解：
- PartInst.locX/Y = PlacedInstance.locX/Y
- PartInstDisplayProp = SymbolDisplayProp
- PartInstUserProp = prefixProperties (Value, MPN, PCB Footprint)
- Package.refdesPrefix = 位号前缀

#### 6.2 HDL 格式生成得到官方参考 ✅

- symbol.css 格式已完全掌握（C/L/A/T/P 指令）
- chips.prt 格式清晰
- pinlist.txt (Lisp-like) 确认
- metadata/ 目录结构可用

#### 6.3 器件模板可用 ✅

CTW 21 个标准器件模板可以直接用于：

| 器件 | DEVNAME | 引脚1 | 引脚2 | 引脚3 | 引脚4-7 |
|------|---------|-------|-------|-------|---------|
| 电阻 | R | 1/A/A<0>/A<SIZE-1..0> | 2/B/B<0>/B<SIZE-1..0> | — | — |
| 电容 | C | 1/+/A/A<0>/A<SIZE-1..0> | 2/-/B/B<0>/B<SIZE-1..0> | — | — |
| 电感 | L | 1/A/A<0>/A<SIZE-1..0> | 2/B/B<0>/B<SIZE-1..0> | — | — |
| 二极管 | D | A | B | — | — |
| 三极管/MOS | Q/M | S | G | D | — |
| JFET | J | S | G | D | — |
| 变阻器 | RVAR | A | B | — | — |
| 可变电容 | CVAR | 1/+/A | 2/-/B | — | — |
| 电源 | P | A/VOUT/A<0>/A<SIZE-1..0> | — | — | — |
| 地 | G | G/G<0>/G<SIZE-1..0> | — | — | — |
| 运放(3-pin) | E | PIN | NIN | OUT | 4=PVSS,5=NVSS |
| 运放(5-pin) | Opamp5 | +/PIN | -/NIN | OUT | 4=V+/PVSS,5=V-/NVSS |
| 运放(6-pin) | Opamp6 | +/PIN | -/NIN | OUT | 4=V+,5=V-,6=ISET |
| 运放(7-pin) | Opamp7 | +/PIN | -/NIN | OUT | 4=V+,5=V-,6=OS1,7=OS2 |
| 电压源 | VDC/VPULSE/VSIN/VSQUARE/VVAR | PVS | NVS | — | — |

#### 6.4 BOM 生成可用 ✅

template.bom 格式已确认，可作为 HDL 输出的一部分。

---

### 7. 关键文件位置速查

| 用途 | 路径 |
|------|------|
| DSN XSD (官方格式) | `capDB/dsn.xsd` |
| OLB XSD (官方格式) | `capDB/olb.xsd` |
| HSL 符号示例 | `standard/vcc_circle/sym_1/symbol.css` |
| 多视图符号 | `standard/offpage/sym_1..6/symbol.css` |
| 引脚定义 | `standard/gnd/metadata/pinlist.txt` |
| 器件模板 | `cdssetup/ctw/devices/*.txt` |
| BOM 模板 | `cdssetup/template.bom` |
| TCL API 参考 | `capDB/*.tcl` |
| cds.lib 格式 | `cdssetup/cds.lib` |

---

### 8. CIS 标准库结构（新增 — Explore-4 Agent 分析）

#### 8.1 library/ 主库（30+ .olb）

| 类别 | 文件 | 大小 | 对项目意义 |
|------|------|:--:|-----------|
| 放大器 | Amplifier.olb | 555K | OLB 器件符号参考 |
| 运算放大器 | OPAmp.olb | 1.2M | 多引脚器件参考 |
| 离散器件 | Discrete.olb | 2.8M | 电阻/电容/电感符号 |
| 连接器 | Connector.olb | 5.6M | 接插件符号参考 |
| 微控制器 | MicroController.olb | 3.3M | IC 符号参考（最高复杂度） |

#### 8.2 netforms/ — 网表格式化器 DLL（40+ 格式支持）

关键 DLL：
- `orEdif.dll` — EDIF 格式（我们 Phase I-A 所用格式的官方导出器）
- `orTelesis.dll` — Allegro 原生网表
- `orpads2k.dll` — PADS 2000

#### 8.3 allegro.cfg — **网表属性传递核心配置**

文件路径：`capture/allegro.cfg`

定义了 4 组 100+ 个在网表中传递的属性：

```ini
[ComponentDefinitionProps]    # 器件级定义属性
ALT_SYMBOLS, CLASS, PART_NUMBER, TOL, VALUE, POWER_GROUP, SWAP_INFO

[ComponentInstanceProps]      # 实例级属性
GROUP, ROOM, VOLTAGE, SIGNAL_MODEL, NO_XNET_CONNECTION

[netprops]                    # 网络属性（50+）
BUS_NAME, CLOCK_NET, DIFFERENTIAL_PAIR, IMPEDANCE_RULE, MATCHED_DELAY,
PROPAGATION_DELAY, SHIELD_NET, NET_PHYSICAL_TYPE, NET_SPACING_TYPE...

[pinprops]                    # 引脚属性
NO_DRC, NO_PIN_ESCAPE, NO_SHAPE_CONNECT, PIN_SIGNAL_MODEL
```

**对 cis2hdl 的启示**：HDL 生成时需确保这些属性被正确映射和传递。

#### 8.4 CAP2EDI.CFG + EDI2CAP.CFG — 双向 EDIF 转换配置

文件路径：`capture/CAP2EDI.CFG`, `capture/EDI2CAP.CFG`

#### 8.5 macros/ + skill/ — 自动化能力

- VBA 宏：buscnct.bas（总线连接）、custprop.bas（自定义属性）、Titleblock.bas（标题栏）
- SKILL 接口：`capture/skill/orCapSxIf.il` — OrCAD↔Allegro SKILL 桥接

---

### 9. 第二轮深度挖掘

#### 9.1 CAP2EDI.CFG — EDIF 导出配置

```ini
[OrCAD Reader]
MultipleLibraries = 1    # 多库模式
ConvertAll = 0
UniquePins = 0
PackagePinNumbersToDesignator = 0
OutputBackAnnotation = 0
```

#### 9.2 EDI2CAP.CFG — EDIF 导入配置

**对 cis2hdl 生成逻辑的关键参数**：

```ini
PinToPin = 0             # 引脚间距
Grid = 0                 # 网格大小
OrcadConventions = 1     # OrCAD 命名规范
UseDesignatorsForPackaging = 1
DesignatorsSameInHierarchy = 1  # 层次设计保持相同位号
BackgroundTextScale = 0.8
DefaultNetNameScale = 0.3
StandardPageSize = 0
PinDisplayStyle = orcad
```

#### 9.3 VBA 宏 — 坐标系统与布局算法

##### buscnct.bas — 总线连接（核心坐标参考）
- 坐标系：十进制英寸 (0.4, 0.1, -0.5)
- 总线间距：`BitYOffset = 0.1 + (Spacing/10)`
- 8 种方向组合
- `PlaceWire(0,0,WendX,WendY)`, `PlaceNetAlias(x,y,name)`, `PlaceBusEntry(x,y,rotate)`, `GoToRelative(dx,dy)`

##### PortIn.bas — 端口放置
- `PlacePort(x,y,"CAPSYM.OLB","PORTRIGHT-R",PortName)`
- 标签偏移：`Offset = 0.95 - (NameLength/20)`

#### 9.4 CTW 器件模板 — 21 个完整定义（详见第 5 节更新）

#### 9.5 CTW 电路模板 DSL — HDL 生成语言

```text
BEGIN_CIRCUIT NAME='BypassPinLeft'
  BEGIN_COMPONENTS
    BEGIN_DEVICE 'P1' DEVTYPE='P' PLACE=(100,400) ORIENT=V MAPID=1
      BEGIN_DEVICE_PROPERTIES HDL_POWER='5V' END_DEVICE_PROPERTIES
      BEGIN_CONNECTIONS PIN='1' NET='$UN1' END_CONNECTIONS
    END_DEVICE
    BEGIN_DEVICE 'C1' DEVTYPE='C' PLACE=(100,200) ORIENT=V MAPID=2
      QUERY_REPLICATE_DEVICE SHIFT=(-50, 0)
      BEGIN_CONNECTIONS PIN='1' NET='$UN1' PIN='2' NET='$UN2' END_CONNECTIONS
    END_DEVICE
  END_COMPONENTS
  PARENT_ASSOCIATION PIN
END_CIRCUIT
```

#### 9.6 Canvas DRC — 重叠检测

```tcl
proc asda_inst_overlap {designName msgType} {
    # sch::dbGetPageItems → asda_filter asda_isInst → sch::dbGetBBox
    # → asda_checkbbox_intersection 两两比对
}
```

#### 9.7 template.bom — 完整 BOM 模板

```
内置属性：BOM_PART, BOM_INST, BOM_QUANTITY, BOM_ITEM_NUM
列：WIDTH, TITLE, JUSTIFICATION, PROPERTY, TOTAL, SUBTOTAL, QUOTE
位号压缩：INST_RANGE=TRUE, RANGE_MIN=3
过滤：PROP="BOM_IGNORE" "TRUE" | PROP="VAR" "1"
```

---

### 11. XSD 全量解析 + ISCF 导出 + DRC 体系（Explore-2 完整报告）

#### 11.1 DSN 全量元素表

| XML元素 | 关键属性 | cis2hdl映射 |
|---------|---------|------------|
| **PartInst** | dbId, deviceDesignator, libName, **locX/Y**, name, pkgName, rotation, mirror | PlacedInstance |
| **WireScalar** | startX/Y, endX/Y, name, dbId | Wire |
| **Alias** | name, locX/Y, color, rotation + AliasBBox + AliasFont | 网络名标注 |
| **Junction** | locX/Y | 连接点 |
| **Global** | name | 全局信号(VCC/GND) |
| **Port** | name | 端口 |
| **OffPage** | name | 跨页连接器 |
| **BusEntry** | x1/y1/x2/y2, length | 总线入口 |
| **DrawnInst** | locX/Y, rotation, pkgName, ContentsViewName/Type | 层次块 |
| **PartValue** | name | 器件值 |
| **Reference** | name | 位号 |
| **PartInstUserProp** | name, val | 自定义属性 |
| **PartInstDisplayProp** | locX/Y, name, rotation, textJustification + PropFont/Color/DispType | SymbolDisplayProp |
| **NetScalar** | name + WireScalar子项 | Net |
| **GraphicLineInst** | start/end, lineStyle/Width | 图形线段 |
| **GraphicCommentTextInst** | locX/Y, textJustification + TextFont | 注释文本 |
| **TitleBlock** | name | 标题栏 |

#### 11.2 坐标系统确认

- 所有坐标使用 **xs:long** (整数)
- 字体系统：escapement, height, italic(0/1), name, orientation, weight, width
- 页面参数：ANSIGridRefs, BorderDisplayed, GridRefDisplayed, HorizontalLabelCount/Width, IsMetric, PinToPin, PageSize(A/B/C/D/E/Custom)

#### 11.3 ISCF — Cadence 内部交换格式（Explore-2 首曝）

**ISCF 是 Cadence 内部的设计数据交换格式，决定了网络如何分类：**

```
BEGIN_COMPPROPS     # 器件属性: RefDes:prop1,prop2,...
BEGIN_COMPPINS      # 器件引脚: RefDes((pinNum:pinLabel),...)
BEGIN_BUSES         # 总线: Bus1,Bus2,...
BEGIN_NETS          # 普通网络: NetName:RefDes(pin:label),...
BEGIN_GROUND        # 地网络 (同NETS格式)
BEGIN_POWER         # 电源网络 (同NETS格式)
```

**网络分类模型**（直接影响我们的 NetIR 设计）：
| 网络类型 | ISCF段 | 判定方式 |
|---------|--------|---------|
| FlatNet | BEGIN_NETS | 默认 |
| GroundNet | BEGIN_GROUND | 地网络 → GND/GND_EARTH/GND_POWER |
| PowerNet | BEGIN_POWER | 电源网络 → VCC/VDD/PP* |
| BUS | BEGIN_BUSES | 总线信号 |

**引脚分组**：SectionPin (分区引脚) + CommonPin (公共引脚) + InvisiblePin (不可见引脚如电源)

#### 11.4 DRC 规则体系（7种）

| DRC规则 | 文件 | 检查内容 |
|---------|------|---------|
| DevicePinMismatch | capDevicePinMismatch.tcl | 器件Instance与Package的Device引脚不匹配 |
| HangingWires | capHangingWires.tcl | 连线端点少于2个激活对象 → 悬空线 |
| PortPinMismatch | capPortPinMismatch.tcl | 层次块引脚与底层端口定义不一致 |
| InvalidPinNumber | capInvalidPinNumber.tcl | 无效引脚编号 |
| OverlapWires | capOverlapWires.tcl | 重叠连线 |
| PartRefPrefixMismatch | capPartReferencePrefixMismatch.tcl | Part Reference前缀不匹配 |
| ShortedDiscretePart | capShortedDiscretePart.tcl | 离散器件短路 |

**DRC 架构模式**：回调模式 (drcNamespace::functionName) + 2种遍历模式 (Occurrence/Page) + UI层/遍历引擎/规则实现三层分离

**DRC 物理坐标处理**：
- `ConvertDocToUser`: 文档坐标 × (1.0 / 物理粒度) = 用户坐标
- `NewERC`: 创建 ERC 标记到页面 → 参数含 errorName, msg, detail, location, ERCSymbol, rotation

---

### 10. TCL 脚本体系全析（Explore-8 Agent 完整报告）<!-- 注：章节编号待整理，内容不受影响（§10 位于 §11 之后，为原始编号跳跃所致） -->

#### 10.1 属性显示系统（Property Display Types）

OrCAD 定义了 **5 种属性显示类型**：

| 类型 | 代码 | 含义 | HDL 生成对应 |
|------|:--:|------|-------------|
| Do Not Display | 0 | 不显示 | 不写入 symbol.css |
| Value Only | 1 | 仅显示值（如 "10K"） | `P "KEY" "VALUE"` 单属性行 |
| Name and Value | 2 | 显示名和值（如 "Value=10K"） | 需要两行或拼接 |
| Name Only | 3 | 仅显示名称 | `P "KEY" ""` |
| Both If Value Exists | 4 | 有值时显示名和值 | 条件式生成 |

#### 10.2 坐标系统与几何操作

**坐标模型**：
- Point = `[list x y]` （TCL list 格式）
- BBox = `[list topLeft bottomRight]` = `[list [list x1 y1] [list x2 y2]]`

**坐标转换**：
- `ConvertDocToUser`: 文档坐标 / 物理粒度 = 用户坐标
- `$pPage GetPhysicalGranularity` → 缩放因子

**几何操作（capGeom.tcl）**：
- `capGeom::left/right/top/bottom` → 提取 BBox 边界
- `capGeom::width` → abs(left - right)
- `capGeom::height` → abs(top - bottom)
- `capGeom::bboxUnion` → 两 BBox 的并集
- `capDboGeom::rotation2DboRotation` → 90/180/270 → DboValue 常量

#### 10.3 DBO 数据库对象层次

```
Design (.dsn)
├── Views (Schematics)
│   └── Pages
│       ├── PartInsts          ← 器件实例（PlacedInstance）
│       ├── Wires              ← 导线
│       │   └── Aliases        ← 网络标签（网络名标注）
│       ├── Globals            ← 全局网络（VCC/GND 标记）
│       ├── Ports              ← 端口
│       ├── OffPageConnectors  ← 跨页连接器
│       ├── TitleBlocks        ← 标题栏
│       ├── BusEntries         ← 总线入口
│       └── CommentGraphics    ← 注释文本/图形
├── Cache
│   └── Packages（Type=31）    ← 器件封装定义
└── Library
    └── strLst                 ← 全局字符串表
```

#### 10.4 通用迭代器 API 模式

```tcl
# 标准 DBO 迭代器模式（Project Manager 使用的）
set iter [$object NewXXXIter $lStatus]
set obj [$iter NextXXX $lStatus]
while {$obj != $lNullObj} {
    # 处理 $obj
    set obj [$iter NextXXX $lStatus]
}
delete_DboXXXIter $iter
```

**已知迭代器**：
- `NewViewsIter` → View (Schematic)
- `NewPagesIter` → Page
- `NewPartInstsIter` → Part Instance（器件实例）
- `NewWiresIter` → Wire + `NewAliasesIter` → Alias
- `NewGlobalsIter` → Global
- `NewPortsIter` → Port
- `NewOffPageConnectorsIter` → OffPageConnector
- `NewCommentGraphicsIter` → Comment/Text
- `NewTitleBlocksIter` → TitleBlock
- `NewPackageNamesIter` → Package Names
- `NewPackagesIter` → Packages
- `NewPackageAliasesIter` → Package Aliases
- `NewPartsIter` / `NewSymbolsIter` → Library Parts/Symbols
- `NewDisplayPropsIter` → Display Properties
- `NewCachesIter` → Design Cache

#### 10.5 Canvas 系统（Design Entry HDL）

**UI Widget 目录**（来自 asda/init.tcl）：
- Design Explorer, Hierarchy Explorer, Project Explorer
- Navigation Table, Search Results Table
- Error Violation Dock (DRC 违规窗口)
- Constraint Manager Dock (约束管理器)
- Auto Shapes Dock, Special Bodies Dock
- Format Dock, Properties Dock（属性编辑 Widget）
- Selection Filter Dock
- TCL Window Dock, Session Log Dock

**Canvas 导出命令**：
- `exportPhysical` / `importPhysical` → 与 Allegro 网表交互
- `saveDesign` / `undo` / `redo` / `addConnection`
- `archive` / `updateAll` / `updateConstraints`
- `addLib` / `deleteLib` / `useLibs` / `removeLibs`
- `addComponent` / `openBoardFile` / `launchBoardFile`

**Canvas DRC 规则注册**：
- `sch::registerDesignRule $ruleName $ruleDescription $ruleProc $ruleType`
- 规则类型：电气（Electrical）和物理（Physical）

**导入错误码**（31 个）：

| 错误码 | 含义 | 级别 |
|:--:|------|:--:|
| 1-2 | 项目文件不存在 | ERROR |
| 3 | lib:cell 不在设计中 | ERROR |
| 4 | 页面文件不存在 | ERROR |
| 5,8,25,26 | 导入错误 | ERROR |
| 6 | 含层次块 | ERROR |
| 9,27 | 添加实例错误 | ERROR |
| 10 | 添加导线错误 | ERROR |
| 20 | 缺少页面边框 | ERROR |
| 21 | lib:cell:view 缺失 | ERROR |
| 28 | 重复页面 | ERROR |
| 22 | 导入成功 | LOG |
| 23 | 无法创建目录 | WARNING |
| 31 | 电压值无效 | WARNING |

#### 10.6 CDS 属性系统（全量属性列表）

**电气属性**：ALLOW_CONNECT, BIDIRECTIONAL, DIR, DELAY, RISE, FALL, INPUT_LOAD, OUTPUT_LOAD, IO_NET, NO_IO_CHECK, NO_LOAD_CHECK

**物理属性**：LOCATION, LOCATION_CLASS, XY, ROT, SEC, has fixed size

**设计属性**：MODEL, PART_NUMBER, PHYS_DES_PREFIX, VALUE, VER, GROUP, ROOM

**仿真属性**：CHIP_DELAY, CLOCK_DELAY, WIRE_DELAY, EVAL, PDELAY, PFALL, PRISE, TIMING_ASSERTION

**配置属性**：AUTO_GEN, LAST_MODIFIED, SCOPE, TERMINAL, NN, NEEDS_NO_SIZE, COMMENT_BODY

**继承规则**：`inherit(body/pin/signal)`, `permit(body/pin/signal)`, `filter`, `case_sensitive`, `parameter`

#### 10.7 关键 TCL API 速查表

| API | 用途 | cis2hdl 对应 |
|-----|------|-------------|
| `$lSession GetActiveDesign` | 获取活跃设计 | DSNParser.open() |
| `$dsn NewCachesIter` | 遍历设计缓存 | cache_parser.ts parseCacheStream() |
| `$p1 GetObjectType` | 获取对象类型 | StructureType enum |
| `$p1 GetName` / `GetText` | 获取名称/文本 | PlacedInstance.reference / strLst[] |
| `$lpart GetEffectivePropStringValue` | 获取属性值 | prefixProperties 解析 |
| `$lpart SetEffectivePropStringValue` | 设置属性值 | SCHWriter 生成 |
| `$lpart GetBoundingBox` | 获取 BBox | PlacedInstance.locX/Y + symbol BBox |
| `$lpart NewDisplayProp` | 创建显示属性 | SymbolDisplayProp 生成 |
| `$disProp SetDisplayType` | 设置显示类型(0-4) | symbol.css P 指令 |
| `$disProp SetLocation` | 设置显示位置 | symbol.css 坐标 |
| `$pPage MarkModified` | 标记页面修改 | 增量保存 |
| `$lSession SaveDesign / SaveLib` | 保存设计/库 | Writer 层输出 |
| `DboTclHelper_sReleaseAllCreatedPtrs` | 释放所有指针 | 垃圾回收 |
| `Menu "View::Zoom::Redraw"` | 重绘视图 | 预览刷新 |

#### 10.8 对 cis2hdl 的关键启示

1. **属性显示系统**定义了 5 种模式，HDL symbol.css 生成需支持这些模式
2. **坐标模型** (Point/BBox) 在 TCL 层和 C++ 层之间的转换通过 DboGeom 桥接
3. **Canvas 系统**的 widget 目录表明 HDL 编辑器是完整的 IDE，不仅仅是画布
4. **CDS 属性系统**定义了 HDL 设计中所有可用的属性及其继承规则
5. **迭代器 API 模式**统一了所有对象遍历，Binary DSN Parser 的 component-builder 本质上在复制这套模式
6. **Canvas 错误码**体系可帮助验证 HDL 生成输出的完整性

---

### 12. EDIF 格式深度分析 + 全部配置文件（Explore-12 完整报告）

#### 12.1 EDIF 样本分析 — 5个完整 .edf 文件（Actel/Altera/Xilinx + 纯VHDL）

| 文件 | 厂商 | 关键特征 |
|------|------|---------|
| Actel/SampleD/a8bitbcd.edf | Actel | outbuf/inbuf/dfc1原语，member索引MSB=3 |
| Altera/SampleE/a8bitbcd.edf | Altera | S_DFF/SOFT原语，rename重映射 |
| Xilinx/SampleC/a8bitbcd.edf | Xilinx | RLOC/HU_SET/loc约束，FPGA布局坐标 |
| Board/dff_sync_sr.edf | Xilinx 4000 | EQN布尔表达式原语，GND/VCC |
| pure_vhdl/counter_mux_top_level.edf | Xilinx Virtex | LUT INIT属性，MUXCY_L/XORCY进位链 |

#### 12.2 EDIF 格式结论

```
✅ EDIF 2.0.0 包含：器件实例、引脚引用、网络连接、属性、层次结构
❌ EDIF 2.0.0 不包含：图形坐标（器件位置、连线路径）
   → 原理图图形坐标必须从 Binary DSN 获取
   → 验证了 EDIF（逻辑）+ DSN（坐标）双路策略的必要性
```

**EDIF 12 条结构规律（已验证）**：
1. 顶层：(edif name) → (edifVersion 2 0 0) → libraries → (design)
2. 库：(library name (technology) cells)
3. 元件：(cell name (cellType GENERIC) (view viewName (viewType NETLIST) (interface ports) (contents)))
4. 端口：(port name (direction INPUT/OUTPUT)) [+property loc]
5. 实例：(instance name (viewRef netlist (cellRef cellName (libraryRef libName)))) [+property]
6. 网络：(net name (joined portRefs))
7. 总线：(port (array (rename busName "N:M") width)) → (member busName index)
8. 属性类型：string, integer → (property name (string/int value))
9. 重命名：(rename internalName "externalName")
10. 位置约束：RLOC="R0C0", HU_SET="BN2", loc="p25"（仅FPGA综合，非原理图坐标）
11. 层次：通过实例引用子模块 cellRef
12. EQN原语：(property EQN (string "(~I1*I3)+(~I1*I2)"))

#### 12.3 全部 10 个配置文件清单

| 文件 | 用途 |
|------|------|
| **CAP2EDI.CFG** | CIS→EDIF 导出（MultipleLibraries/ConvertAll/UniquePins） |
| **EDI2CAP.CFG** | EDIF→CIS 导入（PinToPin/Grid/BackgroundTextScale/PinDisplayStyle） |
| **allegro.cfg** | Allegro PCB 属性映射（5组100+属性） |
| cap2ment.cfg | CIS→Mentor 转换 |
| ment2cap.cfg | Mentor→CIS（PinToPin=0.1, UnitMeasurement=inch） |
| cap2view.cfg | CIS→Viewlogic 转换 |
| view2cap.cfg | Viewlogic→CIS 转换 |
| **variant.cfg** | 变体管理（Schematic Part→ALT_SYMBOLS, PCB Footprint→JEDEC_TYPE） |
| attach_props.cfg | Concept 属性附着（BIASVOLTAGE/BIASCURRENT/BIASPOWER） |
| synch_props.cfg | 约束管理器同步属性（VOLTAGE/DIFFERENTIAL_PAIR） |
| termination_discretes.cfg | 终端分立元件配置（RESISTOR/CAPACITOR/DISCRETE） |

#### 12.4 cap2edi.log 运行日志（我们的实际转换）

```
工具: OrCAD CAP2EDI SPB 16.60_1.089
日期: 2026-07-30
源文件: RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN
目标: RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.EDF
处理的页面: 05_LED, 04_MDI, 03_RTL8367RB, 02_Power, 01_Block_Diagram
结果: 0 errors, 0 warnings ✅
```

#### 12.5 EDIF 对 cis2hdl 的关键启示

1. **EDIF 可用于 Phase I-A 快速逻辑验证**（已验证 0 error 转换）
2. **EDIF 的 `rename` 语法直接对应 HDL 的网络名映射**
3. **EDIF 的 `(array (rename ...))` 语法对应 HDL 的总线定义**
4. **EDIF 不包含坐标 → Binary DSN 是坐标的唯一来源**

---

### 13. GUI 渲染与坐标系统全析（Explore-13 完整报告）

#### 13.1 Cadence 多坐标系总表

| 系统 | 坐标约定 | 原点 | 单位 |
|------|----------|------|------|
| **ConceptHDL (.tsg)** | X:Y 表达式 | 符号中心 | 英寸（stubLength, wireLength） |
| **Canvas Panel (.panel)** | Left,Top,Right,Bottom | 面板左上角 | 像素 |
| **FSP Config** | Left/Right/Distribute | — | 方向枚举 |
| **Symbol.panel** | 距原点距离(OutlineLeft等) | 符号原点 | 网格单位 |
| **orPrmViewer** | x,y UI坐标 | 画布左上角 | 逻辑像素 |
| **orPrmQTree** | left,top,right,bottom | 视口左上角 | 逻辑坐标 |
| **orPrmGeom (Tcl)** | `{x y}` 列表 / `{{x1 y1} {x2 y2}}` BBox | — | 逻辑值 |
| **orPrmPinLib** | 绝对坐标 | 引脚起点(0,0) | 逻辑像素 |

#### 13.2 坐标约定：Y轴向上

TCL 和 JavaScript 层均使用**左上角坐标系统**（Y值向下递增），因此：
- `top < bottom` 值
- 左上角为 `(left, top)`，右下角为 `(right, bottom)`

#### 13.3 空间索引 — 四叉树（orPrmQTree）

OrCAD 使用四叉树进行空间索引和碰撞检测：

```javascript
// 象限：NE(0), SE(1), SW(2), NW(3)
// 容差：selectionToleranceX=2, selectionToleranceY=2
// 最大深度：maxDepth=10

getShapesAt(point) → 点容差查询
getShapesIn(rect) → 矩形范围查询
orPrmRectIntersects(lhs, rhs) → AABB 交叉检测
```

#### 13.4 引脚几何库（30+ 预定义形状）

`orPrmPinLib.js` 定义了所有标准引脚形状：
- **线条类**：busEntryR/L (10px), shortLine (10px), longLine (30px)
- **多边形类**：inPoly (填充三角形), clockPoly, io/out/inDrawnPinPoly
- **椭圆类**：shortEllipse (4x4), longEllipse (4x4), pwrEllipse (10x6)
- **复合引脚模板**：visPas, visIO, visIn, visOut, globalPower, zeroLeak, busEntry 等 30+ 种

**对 cis2hdl 启示**：这些引脚形状定义可直接用于 SCH 生成器中的符号创建。

#### 13.5 ConceptHDL 符号模板（template.tsg）

```lisp
(origin center)                              # 原点在中心
(wireSpacing 0.2) (wireLength 0.1)           # 线间距和线长（英寸）
(labelHeight 0.082)                          # 标签高度

; 属性位置使用表达式坐标：
; (xright+xleft)/2:ytop → 水平居中于顶部
; 0:1.15*stubLength → 底部方向，R90旋转

; 引脚方向规则：
; input → left, output → right, io → top
```

#### 13.6 Canvas 面板系统（92 个 .panel 文件）

**关键面板示例 — Symbol.panel（484行）**：
- 属性网格列：Name(80), Value(80), Visibility(10), Location(30), Text Height(40), Alignment(40), Rotation(40), Parameter(40), Color(70), X(40), Y(40)
- 文本网格列：Text(120), Location(40), Text Height(40), Alignment(40), Rotation(40), Color(70), X(40), Y(40)
- 符号轮廓：Left, Top, Right, Bottom（距原点距离）
- "Set Origin" 和 "Set Size" 按钮

**SymbolViewer.panel**：图形视口 10,10→5000,5000（支持大偏移）

#### 13.7 Canvas 快捷键（48 个）

| 操作 | 快捷键 |
|------|--------|
| Add Component | P |
| Add Page | Ctrl+Shift+P |
| Bus Entry | F7 |
| Connect lines | F8 |
| Rotate Left | L |
| Rotate Right | R |
| Grid Settings | Alt+Shift+G |
| Zoom Fit | Ctrl+0 |
| Zoom In/Out | Ctrl+= / Ctrl+- |

#### 13.8 orPrmViewer 渲染配置

```javascript
CacheWidth: 4000, CacheHeight: 2000     // 渲染缓存
SymbolSizeScale: 1                        // 符号缩放
MinScale: 0.2, MaxScale: 4.0              // 缩放范围
InterSymbolGap: 50                        // 符号间距
WorkCanvasWidth: 1000, WorkCanvasHeight: 1000
```

#### 13.9 FSP 引脚方向配置

```ini
input_pin_dir = "Left"
output_pin_dir = "Right"
inoutput_pin_dir = "LeftAndRight"
supply_pin_dir = "Distribute"
nc_pin_dir = "Distribute"
global_power_pin_dir = "Distribute"
max_symbol_pins_left_right = 100
max_symbol_pins_top_bottom = 100
```

#### 13.10 完整 GUI Widget 布局图

```
┌──────────────────────────────────────────────────────────────┐
│  Menu Bar + Toolbar                                          │
├──────┬───────────────────────────────────┬───────────────────┤
│ D E  │                                   │ Constraint Mgr    │
│ E X  │                                   │ (右侧水平)         │
│ S P  │        Canvas Viewport            │                   │
│ I L  │         (主绘图区)                 │ Format            │
│ G O  │                                   │ (右侧水平)         │
│ N R  │                                   ├───────────────────┤
│   E  │                                   │ Selection Filter  │
│   R  │                                   │ (右侧水平)         │
│      │                                   ├───────────────────┤
│ Auto │                                   │ Properties        │
│Shapes│                                   │ (右侧水平)         │
│(左侧) │                                   │                   │
├──────┴───────────────────────────────────┴───────────────────┤
│ Violations / Find Results / Command Window / Session Log     │
│ (底部水平)                                                    │
└──────────────────────────────────────────────────────────────┘
```

---

### 14. PSpice/VHDL/Verilog 全析（Explore-14 完整报告）

#### 14.1 PSpice 仿真模型（.lib 文件）

**模型层次**：
```
Capture 原理图 → .prp 参数映射 → .lib 器件模型 → PSpice 仿真引擎
```

**关键模型**：
- Butterworth 滤波器：`Fc=1 ord=1` 参数化，使用 `E ... LAPLACE` VCVS 拉普拉斯传递函数
- uA741 运放：5 引脚 (non-inv, inv, V+, V-, out)
- LM339 比较器：BJT 晶体管级建模 (q1-q5)
- D1N914 二极管：多温度模型 (IS, RS, N, TT, CJO, VJ)

#### 14.2 FPGA 设计流程

```
Capture 原理图 → BCD.VHD 源 → Synplify 综合 → .edf 网表 
→ Preroute VHDL → 布局布线 → Postroute VHDL + SDF 延迟
```

**三个 FPGA 厂商使用相同的 BCD.VHD 源文件**：
```vhdl
entity BCD is port(
    CLEAR, CLOCK, ENABLE: in std_logic;
    RCO: out std_logic;
    BCD: out std_logic_vector(3 downto 0));
```

#### 14.3 TTL 库架构（TTL.VHD/HC.VHD/LS.VHD）

**建模模式**：
- 简单门：数据流 + AFTER 延迟（`AFTER 22 ns`）
- 时序器件：ORCAD_DFFPC 通用原语 + `GENERIC (trise_clk_q=>25 ns, tfall_clk_q=>40 ns)`
- 74HC 系列使用皮秒延迟（`AFTER 1500 ps`）

#### 14.4 ORCOMP.VHD — 底层原语库

定义了 `orcad_prims` 包：orcad_nand2, orcad_dffc, orcad_dffp, orcad_dqff, orcad_jkffc, orcad_dlatch, orcad_itsb — 所有支持 GENERIC 延迟建模。

#### 14.5 IEEE 1164 标准（ieee/ 目录）

```vhdl
TYPE std_ulogic IS ('U','X','0','1','Z','W','L','H','-');
SUBTYPE std_logic IS resolved std_ulogic;  -- resolution 函数
TYPE std_logic_vector IS ARRAY (NATURAL RANGE <>) OF std_logic;
```

12 个 VHDL 包：std_1164, std_arit, std_sign, std_unsi, std_misc, std_text, num_bit, numeric_, timing_b/p, prmtvs_b/p

#### 14.6 VBA 宏系统

| 宏 | 快捷键 | API |
|------|:--:|------|
| BusConnection | Ctrl+B | PlaceWire, PlaceNetAlias, PlaceBusEntry, GoToRelative |
| PropAdd | Shift+P | SetProperty (5对属性) |
| PlaceBusEntryArray | Ctrl+R | For I=LSB to MSB 批量放置 |
| PortIn | Ctrl+F8 | PlacePort("CAPSYM.OLB","PORTRIGHT-R") |
| PortOut | Ctrl+F9 | PlacePort("CAPSYM.OLB","PORTLEFT-L") |
| TitlblockProps | Ctrl+F7 | SetProperty(Title/DocNum/RevCode/CageCode/PageNum/PageCount) |

#### 14.7 PLDGATES.VHD — 可编程逻辑门

定义 AND2~AND16, NAND2~NAND16, OR2~OR16, NOR2~NOR16, XOR2~XOR16, XNOR2~XNOR16 — 全部 `AFTER 1 NS` 延迟。

---

### 15. TCL 基础设施全析（Explore-15 完整报告）

#### 15.1 capinit.tcl — 主初始化

- `capGetTclTkHome` → 查找外部 Tcl/Tk
- `capLoadTk` → 加载 tk84.dll
- `capTclTkInitialize` → 添加路径到 auto_path

#### 15.2 capAutoLoad — 自动加载注册表（18 个初始化文件）

| 文件 | 功能 |
|------|------|
| capAppLaunchMenu.tcl | Tcl/Tk Utilities 菜单注册 |
| capAutoISCFExport.tcl | ISCF 导出自动化 |
| capCheckPackageOnPartWindowClose.tcl | 关闭时检查重复电源引脚 |
| capCloseAllChildWindows.tcl | 关闭子窗口操作 |
| capCustomDRCInit.tcl | 自定义 DRC 懒加载 |
| capCustomizeNetONLInit.tcl | 网络名校正 |
| capCustomizePageInit.tcl | 页面自定义（条件加载） |
| capDevicePinMismatchInit.tcl | 器件引脚 DRC 注册 |
| capDiffAndMergeInit.tcl | 差异与合并 |
| capFindWindowExtension.tcl | 查找扩展 |
| capTCLMenu.tcl | 菜单作用域管理（2000+ 行） |
| capGenerateBOM.tcl | BOM 生成 |
| capObjectAlignment.tcl | 对象对齐/分布（2000+ 行） |
| capAppsManager.tcl | Tcl 应用仪表板 |
| capAdvancedSave.tcl | 高级保存/另存为 |

#### 15.3 属性系统三层架构

| 层 | 文件 | 内容 |
|:--:|------|------|
| 基础层 | **cdsprop.txt** | 60+ 属性定义（inherit/permit/filter/case_sensitive/parameter） |
| HDL 中心层 | **cdsprop.paf** | 属性属性文件（uppercasevalue, preservename 指示符） |
| Concept UI 层 | **property.dat** | 属性<->UI 控件映射（COMP/WIRE/PIN 所有权，locked/hidden 状态） |

附加：**propflow.txt** — 200+ 属性流转定义（CONCEPT→ALLEGRO→WINNING_VALUE），**properrors.txt** — 101-127 错误码

#### 15.4 包依赖图

```
capInit → capAutoLoad/* → capUtils/capForms/capDB/capDRC
         → orFlow (Altium→Capture)
         → orPrm* (WebComp/CGI/Designer/Streamer)
         → cdnTclEncrypted (加密 .tle)
         → capStartPage (EMA Web 仪表板)
```

#### 15.5 creferhdl — HDL 页面网格定义

`creferhdl/cref.dat` 定义了所有标准页面的网格和标志：
- A 尺寸: 左下(-3750,0) 右上(0,5000), x 标记在 -500,-1500,-2500,-3425
- A~F 标准尺寸 + Cadence 品牌变体 + Valid 变体
- OFFPAGE/端口/自定义标志符号配置

#### 15.6 capTCLMenu.tcl — 菜单作用域（2000+ 行）

根据当前视图切换菜单项：项目管理器/零件编辑器/原理图/属性编辑器。涵盖 File, Edit, View, Place, Tools, Analysis, Accessories 菜单。

---

### 16. 学习系统 + 加密组件 + 网表生成器 + FPGA 编译（Explore-18 完整报告）

#### 16.1 内建 PSpice 学习系统（caplearningresources）

**架构**：JSON TOC + Dojo UI + Tcl 后端桥接

**核心 API**（openopj.js）：
- `OpenOpjSim(Book, Ch, DesignFolder, Design, Schematic, Page, Profile)` → 打开设计+设置仿真
- `OpenOpjSimnLoadDat(...)` → 打开仿真+加载波形
- `OpenOpjSimnLoadOut(...)` → 打开仿真+加载文本输出
- 通过 `window.external.orPrmConnector` 调用 Tcl 的 `::learningResources::*` 命名空间

#### 16.2 加密 TCL 组件（6 个 .tle 包）

| 包名 | 版本 | 推测功能 |
|------|:--:|------|
| orCapTclAppRegistry | 1.0 | Tcl 应用注册表 |
| orDboServerBase | 1.0 | DBO 服务器基础 |
| orPrmDboGeom | **16.6** | 参数化 DBO 几何（与 capDboGeom.tcl 对应） |
| orPrmDboHierStreamer | **16.6** | 参数化 DBO 层次流 |
| orPrmDboStreamer | **16.6** | 参数化 DBO 流 |
| orPrmFieldMap | 1.0 | 参数字段映射（与 orPrmFieldMap.js 对应） |

#### 16.3 用户自定义网表生成器（usernetl/）

**两个 VB6 参考实现**，直接对应我们的 `Writer` 层设计：

**PCB-II 格式**：
```
( { OrCAD/PCB II Netlist Format ... } )
信号名非法字符 → 自动重命名为 X<N>
信号类型: L(local), P(power), S(supply), N(数字), U(未命名)
```

**Wirelist 格式**：
```
<<< Component List >>> PartName, Reference, ModuleName
<<< Wire List >>> NODE/REFERENCE/PIN#/PIN NAME/PIN TYPE/PART VALUE
PinMap: Input, BiDirectional, Output, Open Collector, Passive, Hi-Z, Open Emitter, Power
```

**DLL API（InitNetDLL → GetNetCount → MakeNetCurrent → FirstNetPin/NextNetPin → WriteNet → WriteNetListEnd → NetDLLCleanup）**：
- 属性迭代器：GetFirstPartProperty/GetNextPartProperty
- 网络遍历：FirstNet → NextNet → FirstNode → NextNode
- 文件输出：WriteString, WriteInteger, WriteCrLf, WriteSymbol

#### 16.4 FPGA 编译脚本（20 个 .cmd 文件）

| 厂商 | 脚本数 | FPGA系列 |
|------|:--:|------|
| Actel | 7 | ACT1/ACT2/ACT3/A3200DX/40MX/42MX/54SX |
| Altera | 1 | altera_p.vhd + altera_m.vhd → altlib |
| Xilinx | 9 | XC3000/4000E/EX/5200/9000/CoolRunner + UniSim/SimPrim/LogiBLOX/CoreLib |
| SDF 反标 | 5 | sdf.cmd → COMPILED_SDF_FILE + SCOPE（sdf文件 + 作用域 + 日志） |

#### 16.5 creferhdl 页面网格全量（12 种页面尺寸）

| 页面 | 坐标范围 | x 标记数 | y 标记数 |
|------|---------|:--:|:--:|
| A SIZE | (-3750,0) → (0,5000) | 4 | 4 |
| B SIZE | (-8000,0) → (0,5000) | 8 | 4 |
| C SIZE | (-10650,100) → (-75,8175) | 8 | 6 |
| D SIZE | (-14625,250) → (1875,10750) | 8 | 4 |
| E SIZE | (-10700,-8200) → (10750,7750) | 8 | 8 |
| F SIZE | (-9725,-6725) → (9750,6725) | 8 | 6 |
| CADENCE A | 多版本（含排除区域） | | |
| CADENCE B | 3 个版本（v3 含 2 个排除区域） | | |
| VALID A/B | 校验用页面变体 | | |

**符号定义**：INFLAG/OUTFLAG/BIFLAG (OFFPAGE 6版本), INPORT, OUTPORT, IOPORT, FLAG (12版本)

#### 16.6 libManagerReg.env — 库管理器配置

- 支持 20+ 个命名空间：Concept/Concept5x/Edif200/Edif300/Verilog/VerilogA/VHDL/NVerilog/CDBA/...
- 对话框尺寸：newlibrary(305x360), newcell(300x133), newview(300x200)
- 过滤器：library/category/cell/view/viewType/directory/file

---

### 17. 全量文件分析 + HDL 参考库完整结构（Explore-16 完整报告）

#### 17.1 .baselined 文件 — 关键发现：可读格式的器件定义基线

**546 个 .baselined 文件是 TEXT 格式的基线版本**，可直接阅读！

**chips.prt.baselined 格式**（88E6071 以太网交换机为例）：
```
FILE_TYPE=LIBRARY_PARTS;
primitive '88E6071';
  pin 'XTAL_OUT': PIN_NUMBER='(4)'; PIN_TYPE='ANALOG';
      NO_LOAD_CHECK='Both'; NO_IO_CHECK='Both';
      ALLOW_CONNECT='TRUE';
  pin 'VDD_CORE_1': PIN_NUMBER='(36)'; PINUSE='POWER';
  body PART_NAME='88E6071'; PHYS_DES_PREFIX='IC'; CLASS='IC';
end_primitive;
END.
```

**每个引脚的完整属性集**：PIN_NUMBER, PIN_TYPE(ANALOG/BIDIR/INPUT/OUTPUT), PINUSE(POWER/GROUND), NO_LOAD_CHECK, NO_IO_CHECK, NO_ASSERT_CHECK, NO_DIR_CHECK, ALLOW_CONNECT, OUTPUT_LOAD

**symbol.css.baselined 格式**（附加命令类型）：
| 命令 | 含义 |
|------|------|
| P | 属性定义（如 `CDS_LMAN_SYM_OUTLINE` 含符号边界坐标） |
| M | 移动/线条（路径构建） |
| L | 符号边缘到引脚连接线 |
| C | 引脚连接定义（含引脚名称和位置） |
| X | 文本元素（`PIN_TEXT` 标签） |

#### 17.2 123 个元件完整目录结构<!-- 注：计数口径为 cis_for_reference/hdl_lib/ 排除"备份"目录后 123（原 124 为旧口径） -->

```
cis_for_reference/hdl_lib/{器件名}/
├── cfg_package/expand.cfg     # 设计配置
├── chips/chips.prt             # 部件定义
├── chips/chips.prt.baselined  # 部件基线（可读文本！）
├── entity/
│   ├── pc.db                  # 部件数据库元数据
│   ├── verilog.v              # Verilog 存根（module + port list）
│   ├── vhdl.vhd               # VHDL 存根（entity + port STD_LOGIC）
│   └── vlog004u.sir           # 二进制符号实例记录
├── metadata/
│   ├── pinlist.txt            # 引脚列表
│   ├── pdv_validation.txt     # PDV 验证
│   ├── revHistory.log         # 修订历史
│   ├── revision.log           # 修订日志
│   └── revision.dat           # Lisp 风格版本数据
├── part_table/part.ptf        # 多物理表（MULTI_PHYS_TABLE）
├── sym_1/
│   ├── symbol.css             # 符号图形
│   └── symbol.css.baselined  # 符号基线（可读文本！）
└── master.tag                 # 版本标记
```

#### 17.3 revision.dat — Lisp 风格版本数据

```lisp
(Cell 88E6071_QFN64_0
  (RevisionInfoBlock
    (Baselined 0)
    (Revision 0.0.1)
    (CreateInfo (Time 01/11/21,10:34:14) (User Bacon) (Path hdllib_lib.88e6071))
  )
  (VersionInfoBlock (ToolName PDV) (Version 16.6-p001) (License PCB_librarian_expert))
)
```
工具：Part Developer (PDV)，版本 16.6-p001，许可证：PCB_librarian_expert

#### 17.4 part.ptf — 多物理表格式

```
FILE_TYPE = MULTI_PHYS_TABLE;
PART '88E6071'
:PACKAGE_TYPE | VALUE | DESCRIPTION | JEDEC_TYPE | SN_NUM = MANUFACTURER | BOM_SEQ | TYPE_NAME | SPECIFICATION | LIFE_CYCLE ;
 'QFN64' | '88E6071' | '集成电路88E6071-xx-NNC2I000 QFN64' | 'QFN50P900X900X100-65N' | 'M04.100659'(~88E6071) = '' | 'AC00' | '集成电路' | '88E6071-xx-NNC2I000 QFN64' | ''
END_PART
```

**字段**：PACKAGE_TYPE | VALUE | DESCRIPTION | JEDEC_TYPE | SN_NUM=MANUFACTURER | BOM_SEQ | TYPE_NAME | SPECIFICATION | LIFE_CYCLE

#### 17.5 Canvas UI XML 定义

**contextmenu.xml（1833 行）**：35+ 上下文菜单，含完整 ToolBarItems 和 ContextMenuItems

**cdnbde.xml（525 行）**：Block Diagram Editor 形状：
- **基本形状 14 种**：Rectangle, RoundRect, Resistor, Speaker, Oval, Pentagon, Hexagon, Octagon, RightTriangle, Cross, Star, Diamond, Triangle
- **连接器/箭头 15 种**：Wire, Bus, Bundle, PCIe 等箭头

**cpSchToolbars.xml**：原理图编辑器工具栏（Explorer, Autoshapes, Add Component, Draw Wire, Draw Bus, Connectors, Ground, Power, Add Note, Properties, Format, Special Bodies, Selection Filter, Constraint Manager）

#### 17.6 SDM 设计数据管理

`sdm_policy.xml`：定义完整设计生命周期（preliminary→release），包含 Block/Schematic/Symbol/Variant/Packaged/Layout 的 attachment/monitor/checkin-checkout 规则

#### 17.7 .sir 文件 — 二进制符号实例记录

- 1,718 个文件，约 3.3KB 每个
- 魔数：`bb 0c 00 00 00 6f 4d 67`

---

### 18. SPICE 仿真文件全析 + lman/locales 配置（Explore-17 完整报告）

#### 18.1 PSpice 文件生态（6 种文件，724 个文件总量）

| 文件 | 数量 | 格式 | 用途 |
|------|:--:|------|------|
| .net | 140 | SPICE 文本 | 扁平化网表（无 .END） |
| .cir | 145 | SPICE 文本 | 仿真入口（含 .lib/.TRAN/.AC/.DC/.INC/.END） |
| .prp | 141 | S-expression | 原理图属性→PSpice 参数映射 |
| .sim | 185 | 键值对+二进制标志 | 仿真设置 |
| .als | 69 | SPICE 文本 | 别名映射（cross-probing） |
| .mrk | 150 | 二进制 | 探针标记数据 |
| .prb | 153 | INI 风格文本 | 探针显示布局配置 |

#### 18.2 .prp — 属性映射文件（原理图↔PSpice 桥接）

**每个 .prp 文件定义了三层映射**：

```lisp
("devices"                           # 器件类型层
  ("R" ("spice_dsg" "R")             # R → SPICE标识 R
       ("model_params" ("VALUE" ("value" "0")) ("TC1" ("value" "0")))))

("instances"                         # 实例层
  ("R1" ("device_name" "R")
        ("pspice_path" "R_R1")       # 网表中引用名
        ("model_params"
            ("VALUE" ("value" "100") ("pspice_param" "VALUE")))))  # 原理图值→PSpice参数
```

**参数映射模式**：`value` = 原理图值，`pspice_param` = PSpice 仿真参数名。含 SMOKE 应力分析（POWER/VOLTAGE）、蒙特卡洛（distrib/TOLERANCE）支持。

#### 18.3 .net — SPICE 扁平化网表

```spice
* source DESIGNNAME
R_R1 N00475 N00484 100 TC=0,0           # 电阻
C_C1 0 N00484 1u IC=0V TC=0,0           # 电容
V_V1 N04788 0 AC 5 +SIN 0 5 50 0 0 0   # 交流正弦源
Q_Q2 NC NB NE Q2N2222                    # BJT
X_AND I0 I1 O $G_DPWR $G_DGND AND2      # 数字子电路
```

#### 18.4 .cir — 仿真入口文件

```spice
** Profile: "DESIGN-PROFILE"  [path/profil.sim]
.lib "nom.lib"
.TRAN 0 4m 0 4u                          # 瞬态分析
.AC DEC 100 10 100k                      # AC扫频
.DC LIN V_V1 -1 20 0.01                  # DC扫频
.INC "..\DESIGN.net"                     # 引用网表
.END
```

#### 18.5 .als — 交叉探测别名

```spice
.ALIASES
R_R2  R2(1=N04788 2=N04784)
Q_Q2  Q2(c=N13499 b=N07515 e=N09807) @DESIGN.PAGE(sch_1):PG1@LIB.DEVICE(chips)
.ENDALIASES
```

#### 18.6 .sim — 仿真配置文件

```
@Settings: 0 1        # 瞬态启用
@Settings: 2 1        # AC扫频启用
@Settings: 1 1        # DC扫频启用

@Analysis: 0 ENABLED  # 瞬态
+SWEEP_MODE SKIPBP USEINITCONDS DCANAL
+0 "run_time"          # TSTOP

@Analysis: 2 ENABLED  # AC
+SWEEP_TYPE NOISE_ENABLED 0
+0 "pts_per"           # 每倍频点数
+1 "start_freq"        # 起始频率
+2 "end_freq"          # 终止频率
```

#### 18.7 .prb — 探针显示布局

```ini
[DISPLAYS]
BEGIN DISPLAY DISPLAY_NAME
ANALYSIS TRANSIENT_ANALYSIS | AC_SWEEP | DC_SWEEP
BEGIN TRACE TRACE_EXPR
MARKERID ID_NUM           # 波形表达式: V(V1:+), DB(V(OUT)), -I(V2), NTOT(R1)
END TRACE TRACE_EXPR
END DISPLAY DISPLAY_NAME
```

#### 18.8 lman/ 目录 — Part Developer 配置（321 文件）

- **.panel** (~300): UI 面板（Lisp/Scheme 风格）
- **.mesg** (7): 消息目录（ERROR/WARNING/FATAL/INFO）
- **.cpm**: setup.cpm（270 行完整配置：引脚类型、网格、符号、CSV导入导出映射）

#### 18.9 文件层级关系图

```
DESIGN.dsn
  ├── DESIGN.net          (网表 — Capture 生成)
  ├── DESIGN_sch.prp      (属性映射 — Capture 生成)
  ├── DESIGN.als          (别名 — Capture 生成)
  └── PROFILE.sim         (仿真设置 — 用户定义)
       ├── PROFILE.cir    (电路文件 — PSpice 自动生成，INC .net)
       ├── PROFILE.mrk    (探针标记 — PSpice 生成)
       ├── PROFILE.prb    (探针布局 — PSpice 生成)
       ├── PROFILE.dat    (波形数据 — PSpice 生成)
       └── PROFILE.out    (文本输出 — PSpice 生成)
```
- 内容：编译后的符号定义二进制缓存
- 位置：`hdl_lib/*/entity/vlog004u.sir`


---

## Part II: 技术调研报告（来源：RESEARCH_REPORT.md）

> **来源文件**：`docs/RESEARCH_REPORT.md`（955 行）
> **原文档标题**：《CIS-to-HDL 原理图转换工具 — 技术调研报告》
> **合并方式**：逐节保全，仅调标题层级，不改写原文句子。
> **源文档注**：源文档存在两个 `## 4.3` 标题（§4.3 生成层 与 §4.3 网络命名规范）以及 `## 5` 标题缺失（5.1/5.2/5.3 为悬空小节）的编号现象，均按源文档原样保留；本 Part 器件库目录表（§4.5，131 器件类）与 Part IV A.1.2 存在跨文档重叠信息，均按来源分别保留。


> 版本: v1.2 | 日期: 2026-07-29 | 更新: 添加完整DSN格式规范、网络命名规范、BOM格式、135器件库完整目录
>
> 修订: v1.3 | 日期: 2026-08-07 | StructureType 枚举按实际代码修正（删 PartInstance=11/SymbolPinScalar=26/SymbolPinBus=27，补 Junction=50）；器件库目录数 135→131（口径：排除备份目录）；§4.3 .sch 格式推断标注证伪（Cadence 不识别，现输出 .csa）

---

### 1. 项目背景与目标

#### 1.1 课题来源

Mentor 任务：复习 Allegro Cadence 体系，实现原理图从 OrCAD Capture CIS 格式到 Cadence Design Entry HDL（原 Concept HDL）格式的转换。

#### 1.2 核心挑战

- OrCAD Capture CIS 的原理图以 `.dsn`（二进制）和 `.olb`（二进制）格式存储
- Design Entry HDL 以 `.cpm`（文本）+ `.sch.N.M`（文本）+ `.sym/.ptf`（文本）分布式存储
- CIS 源文件器件命名不符合公司规范，需模糊匹配映射到 HDL 器件库
- 转换涉及三个核心维度：**器件寻找**、**引脚对应**、**网络名转换**

---

### 2. Cadence SPB 生态系统速查

#### 2.1 完整的 18 个功能模块

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

#### 2.2 CIS vs HDL 文件格式对比

| 维度 | OrCAD Capture CIS | Design Entry HDL |
|------|-------------------|------------------|
| **项目配置** | `.opj`（文本） | `.cpm`（文本） |
| **原理图主文件** | `.dsn`（二进制 CFB 容器） | `.sch.N.M`（文本，每页独立） |
| **器件库** | `.olb`（二进制，一个库一个文件） | `.sym` + `.ptf` + `.chk`（分散文本文件） |
| **库索引** | 无外部索引 | `cds.lib`（文本） + `lib.def` |
| **备份** | `.dbk` / `.obk` | 无特定备份格式 |

#### 2.3 CIS 与 HDL 在数据流中的位置

```
CIS 路径:  .dsn + .olb → [Export Physical] → pstxnet/part/chip.dat → Allegro PCB Editor
HDL 路径:  .cpm + .sch + .sym → [Export Physical] → pstxnet/part/chip.dat → Allegro PCB Editor
                                           ↑
                                  网表层完全相同！
```

**关键洞察**：CIS 和 HDL 在网表层（`pstx*.dat` 三件套）说出同一种语言，因此 PCB 布线后端完全共享。差别仅在原理图编辑前端，这也是本转换工具的存在意义。

#### 2.4 CIS 和 HDL 是否使用 VHDL/Verilog 语言？

**结论：不。两者都是图形化原理图工具，与 VHDL/Verilog 无关。**

- "Design Entry HDL" 中的 "HDL" 是历史命名巧合，不是 "Hardware Description Language"
- 但 Capture CIS 支持将原理图**导出**为 Verilog/VHDL 网表（用于 FPGA/ASIC 流程）
- Design Entry HDL 支持与 NC-Verilog 协同仿真
- 以上均为边缘功能，与本项目无关

---

### 3. 现有开源方案调研

#### 3.1 OpenOrCadParser（C++20）

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

#### 3.2 Upverter Universal Format Converter（Python 2）

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

#### 3.3 Universal-Netlist MCP Server — 核心代码分析

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

#### 3.4 OpenAllegroParser — Allegro 二进制解析

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

#### 3.5 orcad-netlist — Python 网表解析器

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

#### 3.6 python-altium — Python EDA 二进制解析架构

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

#### 3.7 CadenceOSHW — 开源测试数据集合

| 属性 | 值 |
|------|-----|
| 仓库 | `github.com/Werni2A/CadenceOSHW` |
| 内容 | 收集的 Cadence 开源硬件项目、库文件 |

**对本项目的价值**：提供了大量可用于测试验证的 `.dsn`, `.brd` 文件链接（`repos_table.md`）。

#### 3.8 Cadence Allegro 文件扩展名完整参考

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

### 4. 核心技术路径深度分析

#### 4.1 解析层 — DSN/OLB 二进制格式（源码级）

##### 4.1.1 OLE/CFB 容器层

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

##### 4.1.2 BinaryReader — 类型化二进制读取

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

##### 4.1.3 DSN Structure Parsing — 通用解析框架

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

##### 4.1.4 关键结构体字段详解

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

##### 4.1.5 Component Building（从解析数据到完整器件）

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

##### 4.1.6 网表解析 (pstxprt/pstxnet/pstchip.dat)

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

##### 4.1.7 Altium .SchDoc → Python OLE 解析模式

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

#### 4.2 匹配层 — 器件模糊搜索（源码级增强）

##### 问题场景

CIS 原理图的器件命名不规范，如 `RES_0603_10K` 需映射到 HDL 规范库中的 `RES_0603_10K_5%_1/10W`。

##### 从 reference code 中提取的匹配增强思路

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

##### 推荐算法组合

```
第1轮: 精确匹配 → 指纹哈希（Footprint + Value + Pin Count）
        + 三级 key 查找策略 (来自 component-builder.ts)
第2轮: 模糊匹配 → rapidfuzz token_sort_ratio 器件名模糊匹配
第3轮: 特征提取 → 正则解析阻值/容值/封装/引脚数，结构化比对
        + MPN key 匹配 (来自 component-builder.ts)
第4轮: 人工确认 → 低于阈值的候选 → GUI 交互确认
```

#### 4.3 生成层 — HDL 文件格式

##### 需要生成的文件清单

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

##### .sch 文件格式特征（从公开样本推断）

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

### 4.3 网络命名规范（来自 universal-netlist 分析标准）

#### 4.3.1 地网络命名标准

| 名称 | 典型用途 |
|------|---------|
| `GND` | 默认地 |
| `VSS` | 模拟/电源地 |
| `AGND` | 模拟地 |
| `DGND` | 数字地 |
| `PGND` | 电源地 |
| `SGND` | 信号地 |
| `CGND` | 机壳地 |

#### 4.3.2 电源轨命名推荐

| 前缀 | 含义 | 示例 |
|------|------|------|
| `PP` | 正电源轨 | `PP3V3`, `PP5V`, `PP1V8` |
| `PN` | 负电源轨 | `PN5V`, `PN12V` |
| `LD_` | 负载侧（电流检测后） | `LD_PP3V3` |

#### 4.3.3 信号命名陷阱（必须在转换时检测）

| 坏名 | 为什么歧义 | 应改为 |
|------|-----------|--------|
| `-RESET`, `+SENSE` | 前缀 +/- 被读为电源极性 | `nRESET`, `RESET_L`, `SENSE` |
| `PN_BUS`, `PPI_CLK` | 与 PP/PN 电源前缀冲突 | `PERIPH_BUS`, `PERIPH_CLK` |
| `VIN_SEL`, `VOUT_EN` | VIN/VOUT 被读为电源轨 | `U5_VIN_SEL`, `U5_VOUT_EN` |
| `VCC_OK`, `VDD_GOOD` | VCC/VDD 被读为电源轨 | `PG_VCC_CORE`, `PG_VDD_IO` |

#### 4.3.4 差分对规范

必须使用一致的 `_P` / `_N` 后缀：`USB_DP, USB_DN` / `PCIE0_TX_P, PCIE0_TX_N`

#### 4.3.5 总线规范

使用 `NAME[0]..NAME[N]` 或 `NAME_0..NAME_N`，不允许跳位。

#### 4.3.6 对转换工具的启示

转换工具必须在 NetNameValidator 中检查：
- 网络名是否以 `+`/`-`/`PP`/`PN`/`VCC`/`VDD`/`VIN`/`VOUT` 开头（逻辑信号）
- 地网络是否使用了标准名称
- 差分对后缀是否一致
- DNS 标记是否存在于结构化字段（而非仅图形标注）

---

### 4.4 BOM 输出格式标准（来自公司实际文件）

#### 4.4.1 BOM.rpt 格式

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

#### 4.4.2 BOM_SEQ 编码（完整确认）

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

#### 4.4.3 SN_NUM 编码

| SN_NUM | 含义 |
|--------|------|
| M01.010301 | M01(物料大类) . 01(电容子类) 03(0805) 01(序列) |
| M02.010055 | M02(电阻大类) . 01(0402) 0055(序列) |
| M01.020079 | M01(电容) . 02(0603) 0079(序列) |

---

### 4.5 公司 HDL 器件库完整目录（131个器件类，口径：排除备份目录）

#### 4.5.1 无源器件（Passive Components）

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

#### 4.5.2 电源器件（Power）

| 器件目录名 | 类型 |
|-----------|------|
| `dc_dc` | DC-DC转换器 |
| `ldo` | LDO稳压器 |
| `auxiliary` | 辅助电源 |
| `power_dip4` | 4脚DIP电源模块 |

#### 4.5.3 IC器件（按功能分类）

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

#### 4.5.4 特殊符号

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

#### 4.5.5 命名规律总结

1. **芯片 IC**：全小写，使用芯片型号（如 `rtl8367`, `zx279128s`）
2. **无源器件**：功能名小写（`capacitor`, `resistor`, `inductor`）
3. **分立器件**：`n_mos`, `p_mos`, `npn`, `pnp`, `diode`
4. **特殊符号**：描述性命名（`vcc_circle`, `gnd_power`）
5. **封装专用**：IPC标准命名（`BGA353C65P23X20_1500X1300X140`）

#### 4.5.6 对模糊匹配的启示

CIS 源器件名可能是任意格式（如 `RES_0603_10K`），HDL 目标库的命名更加规范。匹配策略应：
- 提取 CIS 器件名中的关键词（`RES`→`resistor`, `CAP`→`capacitor`, 芯片型号保持原样）
- 芯片型号直接小写化后精确/模糊匹配
- 无源器件需要 Value + Footprint 组合匹配 part.ptf 中的行

#### 5.1 后端

| 组件 | 技术 | 理由 |
|------|------|------|
| 核心语言 | Python 3.12+ | 快速原型、丰富生态、跨平台 |
| DSN/OLB 解析 | C++ 桥梁调用 OpenOrCadParser | 已有成熟的 C++ 解析器 |
| 或纯 Python | python-ppmd（CFB 解析） + 自定义解码 | 避免 C++ 编译依赖 |
| 模糊匹配 | rapidfuzz | 高性能、C 扩展 |
| 正则引擎 | re (built-in) | 特征提取 |
| 中间表示 | Python dataclasses / Pydantic | 类型安全的数据模型 |
| 验证 | pytest | 标准测试框架 |

#### 5.2 前端

| 组件 | 技术 | 理由 |
|------|------|------|
| GUI 框架 | PySide6 (Qt for Python) | 跨平台、成熟组件库、原生性能 |
| 或备选 | Tauri + React | 现代化 Web 前端 + Rust 后端 |
| 原理图预览 | 自绘 Canvas / QGraphicsView | DSN 图形渲染 |
| 差异显示 | 自研 diff 视图 | 转换前后对比 |

#### 5.3 推荐最终选型：Python + PySide6

- Python 生态在 EDA 辅助工具领域最丰富
- PySide6 提供 TreeView（项目管理）、QGraphicsView（原理图渲染）、TableView（数据表格）等原生组件
- 跨平台（Windows/Linux/macOS）
- 可通过 pybind11 桥接 OpenOrCadParser 的 C++ 解析能力

---

### 6. 风险与难点评估

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

### 7. 参考文献与资源

1. OpenOrCadParser: https://github.com/Werni2A/OpenOrCadParser
2. Upverter Universal Format Converter: https://github.com/bithium/schematic-file-converter
3. Universal-Netlist MCP: https://github.com/IntelligentElectron/universal-netlist
4. Cadence Community: cap2con discussion - https://community.cadence.com/
5. OrCAD XSD 文件: `C:\Cadence\SPB_17.4\tools\capture\tclscripts\capDB\`
6. 《Cadence 16.6电路设计与仿真从入门到精通》
7. Cadence SPB 官方文档: https://www.cadence.com/
8. Elgris E-studio: https://www.elgris.com/content/edif_translators.html


---

## Part III: 参考库精读笔记（来源：REFERENCE_READING_NOTES.md）

> **来源文件**：`docs/REFERENCE_READING_NOTES.md`（1111 行）
> **原文档标题**：《参考库逐文件精读笔记》
> **合并方式**：逐条保全，仅调标题层级（源文档正文无 Markdown 章节标题，使用 `━━━ 文件 #N ━━━` 分隔线，原样保留），不改写原文句子。
> **源文档注**：本 Part 共 18 个文件精读条目（文件 #1~#18），与 Part IV 的文件清单存在跨文档重叠信息，均按来源分别保留。


> 版本: v1.0 | 日期: 2026-07-31 | 作者: 寇豆码（代码阅读分析师）
>
> 本文件包含对 `CIStoHDL_standard/` 参考库中全部文件的逐文件精读笔记。
>
> 修订: 2026-08-07 | 「与当前项目的映射」补充 v2.0 新 writer（csa/scr/xcon/cpc/output_manager）与 matcher v2.0 文件；其余精读笔记内容保留不动。

---

━━━ 文件 #1: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\match_cis_to_hdl.py ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\match_cis_to_hdl.py
  • 语言/格式: Python 3 (纯标准库，零外部依赖)
  • 行数估算: 481 行
  • 大小: 20,504 B (约20KB)

🎯 职责定位
  • 功能域: 器件匹配
  • 解决什么问题: 将从 OrCAD CIS 原理图导出的器件清单（DeviceList.csv）与 HDL 标准器件库（hdl_lib/）进行自动匹配，输出 CIS→HDL 的器件映射表。这是整个 CIStoHDL 转换流程的"心脏"——没有匹配结果，后续的 CSA/SCR 代码生成就无从进行。

🧠 核心算法

  **三重匹配策略（由高到低保真度）：**

  1. **Level 1: 精确匹配 (exact)** — 同时在 Footprint 封装尺寸和 Value 值两个维度上匹配成功时触发。
     - 从 CIS Footprint 字符串中提取尺寸代码（如 HSC0201-HDTB→0201，使用 `extract_pkg_size()`）
     - 在 HDL 库器件的 primitive 名称中搜索该尺寸代码（如 CAPACITOR_0201 中包含 0201）
     - 在 part.ptf 料表中搜索与 CIS Value 规范化的值匹配的库存行
     - 两个条件同时满足 → `exact` 等级

  2. **Level 2: 尺寸匹配 (size)** — Footprint 尺寸在 primitive 名称中找到，但 Value 值在 part.ptf 料表中找不到匹配项。
     - 此时仍选择该 primitive 作为匹配，但使用 part.ptf 的第一行作为参考行（ref_row）
     - SNUM 字段为空（因为没有精确的库存行对应）

  3. **Level 3: 前缀匹配 (prefix)** — 仅通过 RefDes 前缀（如 C→capacitor, R→resistor）找到对应的 HDL 库器件类别。
     - 使用 `body_fallback` 映射表进行回退匹配
     - 排序策略：优先选择 `body_fallback` 中指定的通用器件（如 capacitor/resistor），而非目录中碰到的第一个器件

  4. **Level 0: 未匹配 (none)** — 连前缀都无法匹配时。

  **关键数据结构：**
  - `catalog`: 两级索引 — `by_prefix[prefix]`（前缀→候选器件列表）+ `by_part_name[part_name]`（器件名→详细信息）
  - `primitives`: 从 chips.prt 解析的列表，每项含 `part_name/body_name/prefix/class`
  - `ptf_data`: 从 part.ptf 解析的 dict，`{PART_NAME: [row_dict, ...]}`
  - `body_fallback`: 硬编码的前缀→通用器件名映射表（两次出现：lines 224-234 和 293-303）

  **复杂度:** O(N×M×K)，其中 N=CIS器件数，M=候选HDL器件数，K=每个器件的primitive数。实际可接受因为 M、K 通常很小。

  **封装尺寸提取算法 (`extract_pkg_size()`):**
  - 优先级链：BGA→4位数字代码→SOT/QFN/MLF/TO封装名称→前10字符截断
  - 值得注意的是：BGA 只取"BGA+数字"（如 BGA96），不匹配完整的 BGA96-32-1609W

  **Value 规范化算法 (`normalize_value()`):**
  - 大写化 + 去空格
  - 将 "KOHM"/"MOHM" 标准化为 "K"/"M"（注意：不处理 "OHM"→"" 的规范化！）
  - 去除尾部 `*` 标记
  - 注意：PF→PF, NF→NF, UF→UF 实际无变化（本来就是大写），可能最初有其他意图

📡 对外接口
  • 暴露的函数/类:
    - `read_cis_data(csv_path)` → `list[dict]`: 读取 CIS 器件清单 CSV
    - `_read_file_auto_encoding(filepath)` → `str`: 自动编码检测文件读取器
    - `parse_chips_prt(filepath)` → `list[dict]`: 解析 chips.prt
    - `parse_part_ptf(filepath)` → `dict[str, list[dict]]`: 解析 part.ptf
    - `extract_pkg_size(footprint_str)` → `str`: 封装尺寸提取
    - `scan_hdl_library(lib_dir)` → `dict`: 扫描 HDL 库构建索引
    - `match_component(comp, catalog)` → `dict`: 核心匹配函数
    - `normalize_value(v)` → `str`: Value 规范化
    - `write_mapping_report(results, output_dir)`: 输出 CSV+TXT 报告
    - `format_string(fmt, values)`: 中文字符串安全格式化
    - `main()`: 主流程（4 步管线）
  • 输入契约: CIS CSV 必须包含 RefDes, Value, Footprint, RefDes-X, RefDes-Y 列；HDL 库每个目录下必须有 chips/chips.prt 和 part_table/part.ptf
  • 输出契约: 生成两个文件 — CIS_to_HDL_Mapping.csv（14列）和 CIS_to_HDL_Mapping.txt（格式化报告）

🔗 内部依赖
  • 依赖哪些模块: 纯标准库 — os, csv, re, sys, collections.defaultdict, locale
  • 被谁调用: 作为独立脚本运行，或被 run_tcl_export.bat 编排调用。输出被 generate_hdl_sch.py 和 generate_hdl_scr.py 消费

✨ 设计亮点

  1. **零外部依赖**: 仅使用 Python 标准库，这在 Windows/OrCAD 环境中极为重要，避免了依赖管理地狱。

  2. **编码自动回退**: `_read_file_auto_encoding()` 先尝试 UTF-8，失败后使用 `locale.getpreferredencoding()`（中文 Windows 为 GBK）。这是处理 Cadence 工具链生成文件（常混用编码）的实用方案。

  3. **全局配置集中化**: 顶部三个全局变量（PAGE_NUM, CIS_CSV, HDL_LIB_DIR, OUTPUT_DIR）统一管理所有路径。虽然看似"硬编码"，但在这种单页转换脚本中反而最实用。

  4. **前缀回退机制**: `body_fallback` 映射表提供了从 RefDes 前缀到语义级 HDL 器件类别的映射。如 C→[capacitor], R→[resistor], U→[amplifier, ldo, dc_dc, interface, logic_gate]。这比单纯按字母匹配要智能得多。

  5. **匹配等级符号化**: 用 ●/○/△/✕ 四个符号直观表示匹配质量，在 TXT 报告中一目了然。

  6. **异常处理器件命名规范**: 当 prefix 不在标准映射中时（如 FB→[fb], Y→[crystal,osc], J→[connector,rj45,...]），通过 `body_map` 字典优雅处理边缘情况。

⚠️ 潜在问题

  1. **body_fallback 代码重复（DRY 违规）**: 相同的 `body_fallback` 字典在 `match_component()` 中出现了两次（lines 224-234 用于无候选时的查找，lines 293-303 用于有候选但未匹配时的回退排序）。合并为一个模块级常量可减少维护负担。

  2. **extract_pkg_size 对非标准封装的处理**: 当 Footprint 不包含 BGA 也不包含 4 位数字时，回退到 `footprint_str[:10]` 截断或 SOT/QFN 等正则匹配。这可能在某些极端封装名称（如 "HSC0201-HDTB" 中的 "HSC-" 或 "HDTB" 部分）上产生意外结果。

  3. **normalize_value 不完整**: "KOHM"→"K", "MOHM"→"M" 但缺少 "OHM"→"" 的规则，可能导致 "10OHM" 和 "10" 的比较失败。

  4. **硬编码路径**: 全局变量中的 Windows 绝对路径（`C:\Users\zhong\Desktop\test\...`）使脚本不可移植。

  5. **候选器件匹配的"第一个匹配即返回"策略**: `match_component()` 在找到尺寸匹配后立即 `break`，不考虑多个候选 primitive 都有相同尺寸代码的情况。如果在 capacitor 下同时有 CAPACITOR_0201 和 CAPACITOR_0201_HV，只有第一个被选中。

  6. **part.ptf 解析对 SN_NUM 提取的正则脆弱性**: `sn_match = re.match(r"([^(~]+)", sn_field)` 假设 SN 字段格式为 "SN(~alias)"，但这个假设在其他器件库格式中可能不成立。

  7. **无进度条或 ETA**: 对于大批量器件匹配（如全板 >500 个器件），用户看不到进度。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/matcher/pipeline.py`（匹配管道）+ `cis2hdl/core/matcher/exact.py` + `cis2hdl/core/matcher/fuzzy.py` + `cis2hdl/core/matcher/feature.py`
    <!-- 已修改：补充 matcher v2.0 文件 —— 候选生成：type_hypothesis.py/candidate_pool.py/prefix_filter.py；匹配：passive_matcher.py/active_matcher.py/value_matcher.py/fallback.py；配置打分：match_config.py/scoring.py；基础：base.py/registry.py（v2.0 已重构为两阶段，原"四级管道"描述为历史口径） -->
  • 实现状态: 已实现但差异大
  • 关键差异:
    - 参考库：三重匹配（exact/size/prefix）在一个函数中
    - 当前项目：两阶段匹配管道（v2.0：TypeHypothesis→CandidatePool→PassiveMatcher/ActiveMatcher），各模块独立实现
    - 参考库的 `size` 匹配是当前项目 `exact` 匹配的一个子策略
    - 参考库的 `prefix` 回退映射表在当前项目中可能由 `fuzzy` 匹配覆盖
    - 参考库直接操作 CSV 文件；当前项目通过 IR 层（ComponentDef/MatchResult）解耦

---

━━━ 文件 #2: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\CIS_to_HDL_Mapping.txt ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\CIS_to_HDL_Mapping.txt
  • 语言/格式: 纯文本（格式化报告，由 match_cis_to_hdl.py 的 write_mapping_report() 生成）
  • 行数估算: 56 行
  • 大小: 6,134 B

🎯 职责定位
  • 功能域: 配置与映射（匹配结果样本）
  • 解决什么问题: 提供 human-readable 的 CIS→HDL 器件匹配结果，包含统计摘要和异常清单。这是理解匹配输出格式和匹配等级的"参考标准"。

🧠 核心算法
  • N/A（纯数据文件，非代码）
  • 但格式结构至关重要——它定义了 DEHDL 转换管道的"数据契约"

📡 对外接口
  • 暴露的函数/类: N/A
  • 输入契约: 由 match_cis_to_hdl.py 生成
  • 输出契约: 被人工阅读，或被 generate_hdl_sch.py/generate_hdl_scr.py 消费（通过同名的 .csv 版本）

🔗 内部依赖
  • 依赖哪些模块: 无（输出产物）
  • 被谁调用: 被 generate_hdl_sch.py 通过 CSV_MAPPING 路径间接引用

✨ 设计亮点

  1. **四等级符号系统**: ●/○/△/✕ 直观表达匹配质量，这在命令行输出中非常有效。
  2. **统计摘要前置**: 报告顶部直接给出 4 级统计数字，用户一眼看到全局匹配率。
  3. **固定列宽表格**: 140 字符定宽表格适合终端和纯文本阅读器。
  4. **异常器件专区**: 底部集中列出未匹配和前缀匹配的器件，用于人工审核。

⚠️ 潜在问题

  1. **中英文混合对齐问题**: 报告中使用 `format_string()` 的 `%` 格式化来处理中文对齐，但固定列宽假设每个中文字符占 2 个英文字符宽度——这在某些终端/字体下可能不准。
  2. **CSV 和 TXT 内容重复**: 两者包含完全相同的数据和统计，增加了维护成本。
  3. **数据样本局限性**: 仅 27 个器件、24 个 exact、2 个 size、1 个 prefix、0 个 none——覆盖率很高但没有复杂边缘案例（如大量未匹配器件）。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/ir/match.py` 中的 MatchResult + `cis2hdl/core/diagnostics/report_gen.py`
  • 实现状态: 已实现但差异大
  • 关键差异:
    - 参考库：静态 TXT 报告由 match_cis_to_hdl.py 内嵌生成
    - 当前项目：结构化 MatchResult IR + 独立的 report_gen.py 诊断管道
    - 当前项目多了 JSON/HTML 等多格式报告输出支持

---

━━━ 文件 #3: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\generate_hdl_sch.py ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\generate_hdl_sch.py
  • 语言/格式: Python 3 (纯标准库)
  • 行数估算: 368 行
  • 大小: 14,617 B (约15KB)

🎯 职责定位
  • 功能域: 代码生成（CSA 原理图宏）
  • 解决什么问题: 读取匹配结果（CIS_to_HDL_Mapping.csv），为每个器件生成 DEHDL 的 CSA 宏文件（FORCEADD/FORCEPROP 命令序列），同时生成配套的连通性文件（.csv）、配置（.cpc）、页面映射（page.map）等 DEHDL 项目文件。

🧠 核心算法

  **CSA 生成管线（5步）：**

  1. **读取映射表**: 从 CSV 读取 14 列数据（refdes, cis_value, cis_footprint, cis_x, cis_y, hdl_part, hdl_primitive 等）

  2. **坐标映射 (`map_cis_to_dehdl_coords()`)**: 
     - 收集所有器件的 CIS 坐标，计算包围盒（min/max）
     - 计算中心点 `cis_cx, cis_cy`
     - 计算缩放比例：`scale = min(page_w/cis_w, page_h/cis_h) * 0.7`（取宽高比中较小者 ×0.7 保证不超出页面）
     - C 纸可用区域：x∈[-10200, -550], y∈[400, 7200]
     - Y 轴取反（CIS 和 DEHDL 的 Y 方向相反）
     - 网格回退：没有 CIS 坐标的器件使用 `calc_position()` 按 COLS=5 的网格排列

  3. **symbol.css 属性偏移读取 (`get_prop_offsets()`)**: 
     - 解析 symbol.css 中的 `P "NAME" ...` 行
     - 提取每个属性的 (x, y, rot, just) 偏移量
     - 用于 FORCEPROP 时精确定位属性文本相对于器件原点的位置

  4. **CSA 宏生成 (`generate_csa()`)**: 
     - FILE_TYPE = MACRO_DRAWING 声明
     - 颜色设置（WIRE=YELLOW, PROP=ORANGE, BODY=GREEN 等）
     - 页面边框添加：C SIZE PAGE 符号 + CDS_LMAN_SYM_OUTLINE 属性
     - 每个器件循环：
       a. FORCEADD {cell_name}..1 — 添加器件实例
       b. FORCEPROP PATH — 设置实例标识
       c. FORCEPROP PART_NAME — 设置器件型号（primitive 名）
       d. FORCEPROP PACKAGE_TYPE / JEDEC_TYPE / DESCRIPTION / SN_NUM — 库存属性（INVISIBLE）
       e. FORCEPROP VALUE — 设置值属性（**可见**，DISPLAY 带缩放因子 0.851064）
       f. FORCEPROP $LOCATION — 设置位号（**可见**，GREEN 涂色）

  5. **辅助文件生成**:
     - `page1.csv`: 最小连通性文件（FILE_TYPE=CONNECTIVITY, NC 网络）
     - `page1.cpc`: 单元配置（`#ISCELL hdl_lib c#20size#20page * *`）
     - `page.map`: 页面映射（`1 1 DDR3\n`）
     - `master.tag`: 设计标签文件
     - `module_order.dat`: 模块顺序文件（Version 15.0 格式）

  **FORCEADD/FORCEPROP 指令格式解析：**
  ```
  FORCEADD CAPACITOR..1        ← 添加器件实例
  (-10500 7500);                ← 放置坐标
  FORCEPROP 1 LAST PATH I1     ← 设置属性（1=选择第一个属性实例）
  J 0                           ← 对齐方式 0
  (-10500 7500);                ← 属性位置
  DISPLAY INVISIBLE (x y);      ← 可见性控制
  ```

  **网格布局参数：**
  - COLS=5, SPACING_X=2000, SPACING_Y=1500
  - START_X=-10500, START_Y=7500

📡 对外接口
  • 暴露的函数/类:
    - `get_prop_offsets(body_name)` → `dict[str, tuple]`: symbol.css 解析器
    - `calc_position(index, total)` → `(int, int)`: 网格位置计算
    - `map_cis_to_dehdl_coords(components)`: 原地修改 components，添加 dehdl_x/dehdl_y
    - `generate_csa(components)` → `str`: CSA 宏内容生成
    - `generate_csv()` / `generate_cpc()` / `generate_page_map()` / `generate_master_tag()` / `generate_module_order()`: 辅助文件生成
    - `main()`: 主入口，支持 --page 和 --mapping 参数
  • 输入契约: 映射 CSV 必须包含 refdes, cis_value, cis_x, cis_y, hdl_part, hdl_primitive, hdl_package_type, hdl_jedec_type, hdl_description, hdl_sn_num, match_level 列
  • 输出契约: 在 `worklib/{DESIGN_NAME}/sch_{page}/` 下生成 page{N}.csa, page{N}.csv, page{N}.cpc, page.map, master.tag, module_order.dat

🔗 内部依赖
  • 依赖哪些模块: csv, os, locale, argparse（纯标准库）
  • 被谁调用: 独立运行，消费 match_cis_to_hdl.py 的 CSV 输出
  • 外部依赖: 需要访问 hdl_lib/ 下的 symbol.css 文件读取属性偏移

✨ 设计亮点

  1. **symbol.css 驱动的属性定位**: 不从代码硬编码属性偏移，而是从 symbol.css 动态读取。这是其"数据驱动"设计的关键——当 HDL 库器件符号更新时，生成器自动适应。

  2. **双坐标系策略**: 
     - 优先使用 CIS 原始坐标（通过缩放居中对齐到 C 纸）
     - 回退到规则网格布局（5 列）
     - 这种"保形布局"策略最大程度保留了原始设计的视觉结构

  3. **属性可见性分层**: VALUE 和 $LOCATION 设为可见（带缩放因子），其他属性（PATH, PART_NAME, PACKAGE_TYPE, SN_NUM 等）设为 INVISIBLE。这保持了 DEHDL 页面整洁。

  4. **模块化辅助文件**: 每个辅助文件由独立函数生成，返回字符串。这使得测试和替换（如为不同项目生成不同的 page.map）变得容易。

  5. **命令行参数化**: 虽然全局配置区有硬编码路径，但 main() 也支持 --page 和 --mapping 参数，提供了一定的灵活性。

  6. **编码兼容**: CSA 文件使用 `locale.getpreferredencoding()` 写入（与 match_cis_to_hdl.py 保持一致），辅助文件使用 UTF-8。

⚠️ 潜在问题

  1. **symbol.css 解析脆弱性**: `get_prop_offsets()` 依赖于 `.split('"')` 然后索引 parts[4] 获取坐标。如果 symbol.css 格式有微小变化（如引号内含空格），解析结果就会错误。缺少错误恢复机制。

  2. **硬编码的 DISPLAY 缩放因子**: `DISPLAY 0.851064` 和 `DISPLAY 0.468085` 是魔法数字，没有注释说明其来源或含义。这些可能是 DEHDL 内部渲染参数。

  3. **硬编码的 C 纸边框坐标**: 
     - 边框符号 "C SIZE PAGE..1" 放置于 (-250, 0)
     - 器件区域 (-10500~-2500, 100~7500)
     - 这些坐标针对特定 DSN 文件的全局坐标系统，不具备通用性

  4. **无未匹配器件处理逻辑**: 即使 match_level 为 "none"，器件仍会被添加到 CSA 文件中，使用默认的 "capacitor" 作为 cell_name。这可能导致 DEHDL 编译错误（cell 不存在）。

  5. **module_order.dat 保护不完整**: `if fname == "module_order.dat" and os.path.exists(fpath): continue` — 只保护 module_order.dat，不保护其他可能被用户修改的文件。

  6. **坐标映射的 Y 轴符号**: `dy = page_cy - dy * scale` 中 Y 取反是正确的，但逻辑隐藏在表达式内部，没有显式的坐标变换注释说明。

  7. **字符串转义问题**: CSA 内容如果包含特殊字符（如引号、分号），可能导致 DEHDL 宏解析错误。当前没有转义处理。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/writer/sch_writer.py`（SCH 原理图生成）+ `cis2hdl/core/parser/symbol_css.py`（symbol.css 解析）+ `cis2hdl/core/parser/layout_mapper.py`（坐标映射）
    <!-- 已修改：补充 v2.0 新 writer —— csa_writer.py（CSA 主输出）/ cpc_writer.py（.cpc 页面配置）/ output_manager.py（page.map、master.tag、module_order.dat）/ xcon_writer.py（.xcon 交叉连接） -->
  • 实现状态: 已实现但差异大
  • 关键差异:
    - 参考库：直接生成 CSA 宏文本（命令式）
    - 当前项目：CTW 模板 DSL（声明式），由 DEHDL 编译模板
    - symbol.css 解析在参考库中是 generate_hdl_sch.py 的子功能，当前项目独立为 symbol_css.py
    - 坐标映射在参考库中是 generate_hdl_sch.py 的子功能，当前项目独立为 layout_mapper.py
    - 当前项目的 sch_writer.py 覆盖了参考库中 generate_hdl_sch.py + generate_hdl_scr.py + page1.scr + place_parts.scr 的功能

---

━━━ 文件 #4: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\generate_hdl_scr.py ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\generate_hdl_scr.py
  • 语言/格式: Python 3 (纯标准库 + datetime)
  • 行数估算: 140 行
  • 大小: 4,760 B

🎯 职责定位
  • 功能域: 代码生成（SCR 交互式脚本）
  • 解决什么问题: 生成 Concept HDL 控制台可执行的 .scr 脚本，实现交互式逐器件放置。与 generate_hdl_sch.py 的"全自动宏模式"不同，.scr 脚本模式需要用户在 DEHDL 图形界面中手动点击每个器件的放置位置。

🧠 核心算法

  **SCR 生成流程：**

  1. **读取映射表**: 从 CIS_to_HDL_Mapping.csv 读取 8 个关键列
  2. **生成 SCR 头部注释**: 花括号 `{}` 包裹的注释块，含器件总数和时间戳
  3. **逐器件生成指令块**:
     - 注释块：`{ [idx/total] RefDes Value ... 匹配等级 }`
     - add 命令：`add <hdl_lib>{cell_name}` — 从 HDL 库添加器件
     - 属性设置：`: %Value:PROPERTY=value` 格式（DEHDL 控制台命令）
     - 用户提示：`{ >>> 请点击放置 {refdes} <<< }`
  4. **尾部**: 完成注释 + 结束符 `;`

  **SCR 命令格式解析：**
  ```
  {                        ← 注释块开始（DEHDL SCR 语法）
    [1/27] C460  100nF
    HDL器件: capacitor  Primitive: CAPACITOR_0201
    料号: M01.010024
    匹配等级: exact
  }
  add <hdl_lib>capacitor    ← 从 hdl_lib 库添加 capacitor 器件
  :%Value:PART_NAME=CAPACITOR_0201   ← 属性设置
  :%Value:VALUE=100nF
  :%Value:JEDEC_TYPE=0201
  :%Value:PACKAGE_TYPE=C0402
  :%Value:SN_NUM=M01.010024
  { >>> 请点击放置 C460 (100nF) <<< }
  ```

  **与 generate_hdl_sch.py 的关键区别：**
  | 维度 | generate_hdl_sch.py | generate_hdl_scr.py |
  |------|---------------------|---------------------|
  | 输出格式 | CSA 宏（FILE_TYPE=MACRO_DRAWING） | SCR 脚本（DEHDL 控制台命令） |
  | 放置方式 | 全自动（坐标由 map/calc 计算） | 交互式（用户手动点击） |
  | 属性设置 | FORCEPROP 指令 | :%Value: 格式 |
  | 坐标处理 | CIS→C纸映射+网格 | 无坐标（用户决定） |
  | symbol.css | 需要读取 | 不需要 |
  | 适用场景 | 批量自动转换 | 交互式逐个确认 |

📡 对外接口
  • 暴露的函数/类:
    - `generate_scr(components)` → `str`: 生成 SCR 脚本内容
    - `main()`: 主入口
  • 输入契约: 映射 CSV 必须包含 refdes, cis_value, hdl_part, hdl_primitive, hdl_package_type, hdl_sn_num, cis_fp_size, match_level
  • 输出契约: `place_parts.scr` 文件

🔗 内部依赖
  • 依赖哪些模块: csv, os, datetime（`__import__('datetime')` 用法不常见但有效）
  • 被谁调用: 独立运行。生成的 .scr 文件在 DEHDL 控制台通过 `script place_parts.scr` 执行

✨ 设计亮点

  1. **简洁明了**: 仅 140 行完成所有功能，代码量小意味着出 bug 概率低。

  2. **交互式确认模式**: 每个器件放置后提示用户手动点击，适合需要人工审核对齐的场景（如复杂 BGA 器件、模拟电路）。

  3. **进度注释清晰**: 每个器件都有 `[idx/total]` 标记和匹配等级标注，用户在执行 .scr 脚本时可以实时看到进度。

  4. **属性设置顺序合理**: PART_NAME → VALUE → JEDEC_TYPE → PACKAGE_TYPE → SN_NUM，从关键到辅助。

⚠️ 潜在问题

  1. **全局变量反模式**: `global total` 在 main() 中设置，generate_scr() 中使用——这是模块级共享状态的反模式。且 total 在 `if __name__ == "__main__"` 块中初始化为 0 但没有在 main() 执行前被正确初始化（generate_scr 中的 total 依赖于 main 先执行）。

  2. **硬编码路径**: `BASE_DIR = r"C:\Users\zhong\Desktop\CIS"` 硬编码，且与 generate_hdl_sch.py 中的路径不同（一个用 "test" 一个用 "CIS"）。

  3. **无未匹配器件处理**: 与 generate_hdl_sch.py 一样，match_level="none" 的器件也会生成 add 命令，可能导致 DEHDL 错误。

  4. **无坐标信息**: 没有从映射表中读取 cis_x/cis_y 坐标。映射 CSV 中实际有这些列，但在 generate_scr.py 中被忽略了。这意味着即使是已知坐标的器件也必须手动放置。

  5. **JEDEC_TYPE 误用**: `f":%Value:JEDEC_TYPE={cis_fp_size}"` — 将 CIS 的 fp_size 写入 JEDEC_TYPE 属性，但这可能是语义错误。fp_size 是封装尺寸（如 0201），JEDEC_TYPE 通常存储 JEDEC 标准封装名称。

  6. **`: %Value:` 格式可能错误**: 代码中是 `:%Value:`，但注释中是 `: %Value:`（有空格）。DEHDL 控制台语法对空格极敏感，需确认正确格式。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/writer/sch_writer.py`
    <!-- 已修改：补充 v2.0 新 writer —— scr_writer.py（DEHDL .scr 交互式放置脚本生成） -->
  • 实现状态: 部分实现
  • 关键差异:
    - 参考库：交互式 SCR 脚本，依赖用户手动点击
    - 当前项目：CTW 声明式模板 + 自动布局
    - 当前项目未实现交互式放置场景（SCH_WRITER 尚未包含 SCR 输出模式）
    - SCR 模式对于需要人工审核的复杂电路仍然有价值，当前项目可能需要补充此模式

---

━━━ 文件 #5: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\export_page13.py ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\export_page13.py
  • 语言/格式: Python 3 + pywin32 (Windows COM)
  • 行数估算: 462 行
  • 大小: 15,664 B

🎯 职责定位
  • 功能域: 数据导出（OrCAD Capture COM 自动化）
  • 解决什么问题: 通过 Windows COM 接口自动化操作 OrCAD Capture，打开工程文件 → 定位指定页面 → 提取所有器件的 CIS 属性 → 输出 CSV/TXT 器件清单和异常报告。这是整个 CIStoHDL 管线的数据入口。

🧠 核心算法

  **COM 自动化管线（6步）：**

  1. **COM 初始化 (`CoInitialize` + `DispatchEx`)**: 
     - 多 ProgID 候选（OrCAD.CaptureApp → Capture.Application）
     - 使用 `DispatchEx`（而非 `Dispatch`），创建独立 COM 进程

  2. **工程打开 (OpenProject/Open)**: 
     - 双方法回退：先尝试 `OpenProject`，失败则 `Open`

  3. **Design 对象获取 (6 种方法链式回退)**: 
     - `app.Session.ActiveDesign` → `app.Session.Designs.Item(1)` → `app.ActiveDesign` → `app.ActiveDocument` → `app.Design` → `app.Designs.Item(1)`
     - 这种"贪心回退"策略是 COM 自动化的经典模式——不同版本的 OrCAD Capture 有不同的对象层级结构

  4. **目标页面定位 (`find_target_page()`)**: 
     - 双层匹配：优先按 PageNumber，备选按 PageName
     - 遍历 design.Schematics → schematic.Pages → 比较 page.PageNumber/page.Name

  5. **器件属性提取 (三层策略)**:
     - **第一层: 页面对象枚举** — 尝试多种集合名（Objects/PageObjects/Instances/Items）
     - **第二层: 器件识别 (`is_component_object()`)** — 三种方法：ObjectType==1 / 有 Instance 子对象 / 有非空 Reference
     - **第三层: 属性读取 (`safe_get_prop()`)** — 先直接属性访问，失败则遍历 Properties 集合（CIS 扩展属性的常用访问方式）

  6. **异常检测**: 检查每个器件是否有 Footprint/SNUM/Value（或 TYPE_NAME），缺失则记入异常清单

  **关键数据结构：**
  - `components`: `list[dict]` — 每项 8 字段（RefDes/Value/Footprint/SNUM/PACKAGE_TYPE/Manufacturer/TYPE_NAME/DESCRIPTION）
  - `anomalies`: `list[(refdes, reason)]` — 异常器件列表

📡 对外接口
  • 暴露的函数/类:
    - `probe_com_object(obj, name, depth, max_depth)`: COM 对象探查（调试用）
    - `create_capture_app()` → `(app, progid)`: 创建 Capture 实例
    - `safe_get_prop(obj, prop_name, fallback="")` → `str`: 安全属性读取
    - `get_all_properties(instance)` → `dict`: 提取全部 8 个 CIS 字段
    - `is_component_object(obj)` → `(bool, instance_or_none)`: 器件判断
    - `get_available_pages(design)` → `list[(sname, pnum, pname)]`: 页面列表
    - `find_target_page(design, page_num, page_name)` → `(schematic, page)`: 页面定位
    - `enumerate_page_objects(page)` → `list`: 对象枚举
    - `main()`: 主流程 6 步管线
  • 输入契约: 需要 OrCAD Capture 已安装，工程文件 .opj 存在，目标页面存在
  • 输出契约: Page13_DeviceList.csv, Page13_DeviceList.txt, Page13_AnomalyList.txt

🔗 内部依赖
  • 依赖哪些模块: win32com.client, pythoncom（pywin32 包）, os, csv, sys, datetime
  • 被谁调用: 独立运行（必须在 Windows 原生 Python 中执行，WSL 不可用）。输出被 match_cis_to_hdl.py 消费
  • 外部依赖: OrCAD Capture 必须已安装且支持 COM Automation

✨ 设计亮点

  1. **多层回退策略**: 无论是 ProgID（2种）、工程打开（2种）、Design 获取（6种）还是对象枚举（4种集合名），都采用了链式回退。这种"兼容性优先于优雅"的设计在 COM 自动化中极为重要。

  2. **丰富调试输出**: 每个关键步骤都有 `[1/6]` 进度标记和 `[OK]/[FAIL]/[WARN]` 状态。COM 探测函数 (`probe_com_object`) 可以打印完整的 COM 对象成员树，极大降低了调试难度。

  3. **资源清理保证**: `finally` 块中总是调用 `app.Quit()` 和 `pythoncom.CoUninitialize()`，防止 COM 进程泄漏。

  4. **异常器件自动检测**: 不只导出数据，还自动检测缺少 Footprint/SNUM/Value 的器件并生成异常清单。这是"导出+质检"一体化的设计。

  5. **双格式输出**: CSV（机器可读）+ TXT（人类可读），与 match_cis_to_hdl.py 的输出风格完全一致。

⚠️ 潜在问题

  1. **pywin32 依赖**: 需要 `pip install pywin32`，在 OrCAD 环境中可能无法直接安装（如果 Python 是 OrCAD 自带的）。

  2. **COM 单线程公寓限制**: `pythoncom.CoInitialize()` 使用默认的 STA 模式。如果 OrCAD Capture 需要 MTA，可能导致问题。脚本中没有显式指定线程模型。

  3. **属性读取顺序依赖**: `safe_get_prop()` 先尝试直接属性访问，再遍历 Properties 集合。如果直接属性返回了错误值（如空字符串），而 Properties 集合中有正确值，就会丢失数据。

  4. **无器件坐标提取**: 没有提取器件的 X/Y 坐标（与 match_cis_to_hdl.py 中期望的 cis_x/cis_y 列不对应）。Page_DeviceList.csv 输出只有 8 列，缺少 RefDes-X 和 RefDes-Y。这会导致后续的坐标映射功能失效。

  5. **页面名称硬编码**: `TARGET_PAGE_NAME = "13-DDR3"` 硬编码。如果页面命名约定变化（如 "13-DDR4" 或 "14-DDR3"），脚本就无法定位。

  6. **ObjectType==1 判断不可靠**: `if ot == 1` 依赖于 OrCAD Capture 的内部约定，但 ObjectType 的值在不同版本的 Capture 中可能不同。

  7. **异常报告只检测缺失**: 不会检测格式错误（如 SNUM 格式不正确、Value 包含非法字符等）。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/parser/dsn/dsn_parser.py` + `cis2hdl/core/parser/dsn/ole_reader.py` + `cis2hdl/core/parser/dsn/page_parser.py`
  • 实现状态: 已实现但方式完全不同
  • 关键差异:
    - 参考库：通过 COM 接口使用 OrCAD 进程读取数据（依赖 OrCAD 运行时）
    - 当前项目：直接解析 DSN 二进制文件（OLE 复合文档 → 页面流），不依赖 OrCAD
    - 这是当前项目相对于参考库的**最大架构优势**：无需安装 OrCAD Capture，可在任何平台运行
    - 但当前项目也因此失去了 OrCAD COM 提供的语义层便利（如自动分辨器件/导线/网络标签）

---

━━━ 文件 #6: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\export_page13.tcl ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\export_page13.tcl
  • 语言/格式: TCL (Cadence DboTclHelper API)
  • 行数估算: 363 行
  • 大小: 12,913 B

🎯 职责定位
  • 功能域: 数据导出（TCL 自动化，特定页面 13-DDR3）
  • 解决什么问题: 通过 OrCAD Capture 内置 TCL 解释器和 DboTclHelper API，以无外部依赖的方式导出特定页面的器件属性。这是 COM 方式的替代方案——不依赖 Python/pywin32，直接在 Capture 内部运行。

🧠 核心算法

  **TCL 导出管线：**

  1. **C 字符串管理**: TCL 使用 DboTclHelper 的 C 字符串 API：
     - `DboTclHelper_sMakeCString` / `sGetConstCharPtr` / `sDeleteCString`
     - 每次属性读取都要 create→read→delete 三段式操作
     - 这是与 Python COM 方式最大的实现差异——TCL 必须手动管理 C 内存

  2. **Session 与 Design**: 
     - `DboTclHelper_sCreateSession` → `GetActivePMDesign`（GUI 模式）/ `GetDesignAndSchematics`（批处理模式）
     - 对比 Python COM 的 6 种 Design 获取方法，TCL 只有 2 种但更可靠

  3. **页面遍历**: 使用迭代器模式 — `NewViewsIter` → `NextView` → `DboViewToDboSchematic` → `NewPagesIter` → `NextPage`

  4. **器件属性提取（双策略）**:
     - RefDes: `GetReference`（直接）→ `GetReferenceDesignator`（通过 PlacedInst）
     - Value: `GetPartValue` → `GetEffectivePropStringValue "Value"`
     - Footprint: `GetPCBFootprint` → `GetEffectivePropStringValue "PCB Footprint"` → `GetEffectivePropStringValue "Footprint"`
     - CIS 扩展属性: `GetEffectivePropStringValue` → `PropertyValue`（双回退）

  5. **CSV 转义**: 手动实现引号和逗号转义——`[string map {\" \"\"} $field]`

  **关键 API 调用链：**
  ```
  DboTclHelper_sCreateSession
    → GetDesignAndSchematics(project_path)
    → NewViewsIter → NextView → DboViewToDboSchematic
      → NewPagesIter → NextPage → GetName
    → NewPartInstsIter → NextPartInst
      → GetReference / GetReferenceDesignator
      → GetPartValue / GetEffectivePropStringValue
      → GetPCBFootprint
  ```

📡 对外接口
  • 暴露的函数/类:
    - `make_cstr([str])` → C 字符串: 创建 C 字符串
    - `get_cstr(cstr)` → TCL 字符串: 读取 C 字符串
    - `cleanup_cstr(cstr)`: 释放 C 字符串内存
    - `get_eff_prop(handle, prop_name)` → str: 读取有效属性值
    - `get_prop_value(handle, prop_name)` → str: 通过 PropertyValue 读取
    - `get_str_prop(handle, method)` → str: 通过 getter 方法读取
    - `main()`: 主流程
  • 输入契约: 需要 OrCAD Capture 运行环境，.opj 工程文件存在
  • 输出契约: Page13_DeviceList.csv, Page13_DeviceList.txt, Page13_AnomalyList.txt（8 列，无坐标）

🔗 内部依赖
  • 依赖哪些模块: DboTclHelper, DboState, DboPartInstToDboPlacedInst, 等 Cadence TCL API
  • 被谁调用: Capture.exe -tcl export_page13.tcl 或 Capture GUI Tools→Tcl/Tk Scripts

✨ 设计亮点

  1. **零外部依赖**: 纯 Cadence TCL API，不需要 Python/pywin32，与 OrCAD 环境天然集成。

  2. **双运行模式**: 自动检测 GUI/批处理模式 — `GetActivePMDesign` 成功即 GUI 模式，失败则批处理模式。这比 Python COM 方式更优雅。

  3. **完整页面列表**: 在找不到目标页面时，自动打印所有可用页面。这是良好的调试体验设计。

  4. **迭代器模式**: 使用 DboPagePartInstsIter 迭代器而非一次性加载所有对象，内存友好。

⚠️ 潜在问题

  1. **C 字符串内存泄漏风险**: 如果脚本在某个 `make_cstr` 之后异常退出，对应的 C 字符串不会释放。虽然有 try-catch，但 TCL 的错误处理不如 Python 的 try-finally 可靠。

  2. **无坐标提取**: 与 export_page13.py 一样，不提取器件 X/Y 坐标。这使得该脚本只能用于匹配流程，不能用于布局转换。

  3. **页面名称硬编码**: `target_name = "13-DDR3"`，不可参数化。

  4. **CSV 转义简单**: 只处理逗号和引号，不处理换行符。如果属性值包含换行（如在 DESCRIPTION 字段中），CSV 格式会损坏。

  5. **`get_str_prop` 未使用**: 虽然定义了，但主流程中没有调用。可能是预留的扩展接口。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/parser/dsn/dsn_parser.py` + `cis2hdl/core/parser/dsn/page_parser.py`
  • 实现状态: 已实现但方式完全不同
  • 关键差异: 与文件 #5 相同——TCL 方式和 COM 方式都依赖 OrCAD 运行时，当前项目的二进制 DSN 解析器完全独立于 OrCAD。

---

━━━ 文件 #7: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\export_page.tcl ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\export_page.tcl
  • 语言/格式: TCL (Cadence DboTclHelper API)
  • 行数估算: 377 行
  • 大小: 13,481 B

🎯 职责定位
  • 功能域: 数据导出（TCL 自动化，通用参数化版本）
  • 解决什么问题: 与 export_page13.tcl 的功能相同，但增加了两个关键改进：(1) 提取器件 X/Y 坐标（RefDes-X, RefDes-Y），(2) GUI 模式下安全清理逻辑。这是 TCL 导出脚本的"最终改进版"。

🧠 核心算法

  与 export_page13.tcl **完全相同**的核心流程。以下仅列出差异点：

  **与 export_page13.tcl 的关键差异：**

  | 维度 | export_page13.tcl | export_page.tcl |
  |------|-------------------|-----------------|
  | 目标页面 | 13-DDR3 | 21-4GE |
  | CSV 列数 | 8 列（无坐标） | 10 列（含 RefDes-X, RefDes-Y） |
  | 坐标提取 | ❌ 无 | ✅ `GetLocation` → `sGetCPointX/sGetCPointY` |
  | GUI 模式标志 | ❌ 无 | ✅ `gui_mode` 变量追踪 |
  | GUI 清理 | 总是清理 Session | 跳过 Session 清理（防闪退） |
  | 输出文件名 | Page13_DeviceList.* | Page_DeviceList.* |
  | 输出目录 | Desktop/CIS | Desktop/test/OUT |

  **坐标提取实现（新增逻辑）：**
  ```tcl
  if {[catch {set lPoint [$lPartInst GetLocation $lStatus]}] == 0} {
      if {$lPoint != "NULL" && $lPoint != ""} {
          set x_pos [DboTclHelper_sGetCPointX $lPoint]
          set y_pos [DboTclHelper_sGetCPointY $lPoint]
      }
  }
  ```
  这是 TCL 版本中独有的能力——Python COM 版本的 export_page13.py **也没有**提取坐标。

📡 对外接口
  • 暴露的函数/类: 与 export_page13.tcl 完全相同
  • 输入契约: 与 export_page13.tcl 相同，此外需要器件有 Location 属性
  • 输出契约: Page_DeviceList.csv (10列), Page_DeviceList.txt (10列), Page_AnomalyList.txt

🔗 内部依赖
  • 依赖哪些模块: 与 export_page13.tcl 相同 + DboTclHelper_sGetCPointX/sGetCPointY
  • 被谁调用: 与 export_page13.tcl 相同

✨ 设计亮点

  1. **坐标提取是关键改进**: 有了 X/Y 坐标，match_cis_to_hdl.py 和 generate_hdl_sch.py 才能进行 CIS→DEHDL 坐标映射。这是整个自动化布局管线的关键数据。

  2. **GUI 模式安全退出**: `if {!$gui_mode} { ... cleanup ... }` — 在 GUI 模式下不清理 Session，防止 Capture 窗口意外关闭。这是从实践中总结的经验。

  3. **通用化命名**: 输出文件名为 `Page_DeviceList` 而非 `Page13_DeviceList`，使其可复用于任意页面。

  4. **输出目录分离**: 使用 `OUT` 子目录，与源文件隔离。

⚠️ 潜在问题

  1. **代码重复严重**: export_page.tcl 和 export_page13.tcl 有约 80% 的代码相同（helper 函数完全一样）。应该合并为一个参数化脚本。

  2. **坐标可能为空**: `GetLocation` 可能返回空（某些器件类型没有位置信息），但 CSV 中会用空字符串填充，可能在下游匹配时产生问题（如 match_cis_to_hdl.py 中 `if c.get("cis_x") and c.get("cis_y")` 判断）。

  3. **硬编码目标页面名**: 虽然命名通用化了，但 `target_name = "21-4GE"` 仍然是硬编码的。

  4. **输出文件名与 Python 版本的冲突**: Python 版本输出 `Page13_DeviceList.csv`，TCL 版本输出 `Page_DeviceList.csv`。如果两个脚本都在同一目录运行，文件名冲突或混淆。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/parser/dsn/dsn_parser.py` + `cis2hdl/core/parser/dsn/page_parser.py`
  • 实现状态: 已实现
  • 关键差异: 
    - TCL 脚本依赖 OrCAD 运行时；当前项目直接解析 DSN 二进制
    - TCL 通过 `GetLocation` 获取坐标；当前项目通过 DSN 二进制流解析坐标
    - 当前项目提取的坐标精度可能更高（从原始二进制解析，不受 TCL API 浮点精度限制）

---

━━━ 文件 #8: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\page1.scr ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\page1.scr
  • 语言/格式: DEHDL 宏脚本（MACRO_DRAWING 格式）
  • 行数估算: 1,448 行（27 个器件 × ~50 行/器件 + 头部 30 行）
  • 大小: 33,588 B (约34KB)

🎯 职责定位
  • 功能域: 代码生成（DEHDL 原理图页面宏）
  • 解决什么问题: 这是一个由 generate_hdl_sch.py 生成的**完整 DEHDL 原理图页面宏**。它包含了对 page1（DDR3 页面）上 27 个器件的完整 FORCEADD/FORCEPROP 指令序列。这是 CSA 代码生成器的**黄金标准输出**——理解这个文件就理解了 DEHDL 页面自动化的一切。

🧠 核心算法

  **文件结构解析（三段式）：**

  **第一段：宏头部 (lines 1-31)**
  ```
  FILE_TYPE = MACRO_DRAWING;        ← 声明为宏绘制文件
  SET COLOR_WIRE YELLOW;            ← 颜色配置
  SET COLOR_PROP ORANGE;
  SET COLOR_DOT WHITE;
  SET COLOR_ARC YELLOW;
  SET COLOR_BODY GREEN;
  SET COLOR_NOTE PURPLE;
  SET PROP_DISPLAY VALUE;           ← 默认显示 Value 属性
  SET PAGE_NUMBER P1;               ← 页面编号
  FORCEADD C SIZE PAGE..1           ← 添加 C 纸边框符号
  (2900 200);
  FORCEPROP 1 LAST COMMENT_BODY TRUE
  ...
  FORCEPROP 0 LAST EDIT PAGE NAME DDR3  ← 页面名称
  ```

  **第二段：器件实例循环 (lines 32-1447) — 27 个器件 × 5 行 × 5 列网格**

  每个器件的**标准指令模板**（共 19 条指令）：
  ```
  FORCEADD {PRIMITIVE_NAME}..1      ← 线 1: 添加器件实例（如 CAPACITOR_0201..1）
  (X Y);                             ← 线 2: 放置坐标

  // ---- 不可见属性 ----
  FORCEPROP 1 LAST PATH I{N}        ← 实例标识（I1, I1, I1... 注意全为 I1!）
  J 0                                ← Justification 0
  (X Y);
  DISPLAY 1.021277 (X Y);          ← 先以 1.02x 显示
  DISPLAY INVISIBLE (X Y);         ← 再隐藏（两步操作，可能是 DEHDL 内部协议）

  FORCEPROP 1 LAST PART_NAME {PN}   ← 型号名称
  ... (同上 J0 + DISPLAY 1.02x + INVISIBLE)

  FORCEPROP 1 LAST JEDEC_TYPE {SZ}  ← JEDEC 封装类型
  ...
  FORCEPROP 1 LAST PACKAGE_TYPE {PT} ← 封装类型
  ...
  FORCEPROP 1 LAST SN_NUM {SN}      ← 物料号
  ...
  FORCEPROP 1 LAST DESCRIPTION {D}  ← 描述
  ...

  // ---- 可见属性 ----
  FORCEPROP 1 LAST VALUE {V}        ← 值（可见）
  R 1                                ← Rotation 1
  J 1                                ← Justification 1（右上对齐）
  (X+offset Y+100);                 ← Y+100（向上偏移 100 单位）
  DISPLAY 0.851064 (X+offset Y+100); ← 以 0.85x 缩放显示

  FORCEPROP 1 LAST $LOCATION {Ref}  ← 位号（可见，绿色）
  R 1
  J 1
  (X+offset Y-100);                 ← Y-100（向下偏移 100 单位）
  DISPLAY 0.851064 (X+offset Y-100);
  PAINT GREEN (X+offset Y-100);     ← 绿色涂色

  // ---- 器件边框 ----
  FORCEPROP 1 LAST CDS_LMAN_SYM_OUTLINE {outline}
  J 0
  (X Y);
  DISPLAY 0.468085 (X Y);
  PAINT GREEN (X Y);
  DISPLAY INVISIBLE (X Y);

  // ---- 库引用 ----
  FORCEPROP 2 LAST CDS_LIB hdl_lib   ← 第二个属性实例
  J 0
  (X Y);
  DISPLAY INVISIBLE (X Y);
  ```

  **网格布局分析：**
  | 行(Y) | 列1(X=-11000) | 列2(X=-9000) | 列3(X=-7000) | 列4(X=-5000) | 列5(X=-3000) |
  |-------|---------------|-------------|-------------|-------------|-------------|
  | 7000  | C460 (0201)   | C54 (0201)  | C57 (0201)  | C52 (0402)  | C458 (0201) |
  | 5500  | C466 (0201)   | R281 (0201) | R270 (0201) | R278 (0201) | U5 (88E6320)|
  | 4000  | C55 (0201)    | R41 (0402)  | C455 (0402) | C456 (0201) | R282 (0201) |
  | 2500  | C465 (0201)   | C457 (0201) | C454 (0201) | R269 (0201) | C53 (0402)  |
  | 1000  | C469 (0201)   | C462 (0201) | C56 (0201)  | C468 (0201) | C467 (0201) |
  | -500  | R40 (0201)    | C459 (0201) | —           | —           | —           |

  **关键数值常量：**
  - DISPLAY 缩放因子: 0.851064（VALUE/$LOCATION）、0.468085（边框/库引用）、1.021277（隐藏前过渡）
  - 网格步长: X=2000, Y=1500（同 generate_hdl_sch.py 中 COMPONENT_SPACING_X/Y）
  - VALUE 偏移: (-5, +100) 或 (-50, +5)
  - $LOCATION 偏移: (-5, -100) 或 (-220, +5)
  - 电容 CDS_LMAN_SYM_OUTLINE: -50,0,50,-25
  - 电阻 CDS_LMAN_SYM_OUTLINE: -50,25,50,-25
  - 88E6320 CDS_LMAN_SYM_OUTLINE: -600,2250,600,-2250

  **第三段：结束 (line 1448)**
  ```
  QUIT
  ```

📡 对外接口
  • 暴露的函数/类: N/A（数据文件）
  • 输入契约: 由 generate_hdl_sch.py 生成，在 DEHDL 中通过打开项目时自动编译
  • 输出契约: 编译为 page1.csb（二进制页面文件）

🔗 内部依赖
  • 依赖哪些模块: 依赖 hdl_lib/ 下的所有器件（CAPACITOR_0201, RESISTOR_0201, CAPACITOR_0402, 88E6320 等）
  • 被谁调用: DEHDL (nconcepthdl) 在打开设计时自动读取并编译

✨ 设计亮点

  1. **DISPLAY INVISIBLE 两步操作**: 每个不可见属性先以放大比例显示（DISPLAY 1.021277），再设为 INVISIBLE。这可能是 DEHDL 内部协议：属性必须先在某个位置"存在"才能被隐藏。generate_hdl_sch.py 中跳过了这个中间 DISPLAY 步骤，直接 INVISIBLE — 可能是简化假设。

  2. **器件放置的规则网格**: 5 列 × 6 行网格，间距精确为 X=2000, Y=1500。这种规律性使 DEHDL 页面整洁且可预测。

  3. **CDS_LMAN_SYM_OUTLINE 区分器件类型**: 电容 (-50,0,50,-25)、电阻 (-50,25,50,-25)、BGA 芯片 (-600,2250,600,-2250)。outline 值似乎反映了器件的物理尺寸（相对放置点的边界框）。

  4. **$LOCATION 可见且着色**: 位号设为绿色可见，这是 DEHDL 原理图的标准约定——便于人工阅读和调试。

  5. **PATH 固定为 I1**: 所有器件的 PATH 都设为 I1，这表示它们都是"第一个实例"。在 CSA 宏的上下文中，每个 FORCEADD 创建独立的实例，所以 PATH=I1 是合理的。

⚠️ 潜在问题

  1. **与 generate_hdl_sch.py 输出不完全一致**: page1.scr 的 DISPLAY 顺序是 DISPLAY(1.02x) → DISPLAY INVISIBLE，而 generate_hdl_sch.py 的 generate_csa() 直接输出 DISPLAY INVISIBLE。需要确认 DEHDL 是否接受简化格式。

  2. **所有 PATH 都是 I1**: 当多个器件在同一页面时，PATH 应该递增（I1, I2, I3...）还是保持 I1？如果 PATH 必须唯一，这可能是 bug。generate_hdl_sch.py 中 PATH 是 `I{idx+1}`，正确处理了递增。

  3. **缺少 SN_NUM 为空时的处理**: page1.scr 中 R278 和 R41（size 匹配等级）没有 SN_NUM 行，generate_hdl_sch.py 中的处理逻辑是 `if hdl_sn: ...`，一致。

  4. **88E6320（U5）的 VALUE 和 $LOCATION 位置异常**: VALUE 在 (-3600, 3200)，$LOCATION 在 (-3600, 7770)，偏移量远大于其他器件（因为 BGA 的 CDS_LMAN_SYM_OUTLINE 很大）。

  5. **硬编码的页面名称 "DDR3"**: 第 29 行 `FORCEPROP 0 LAST EDIT PAGE NAME DDR3`。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/writer/sch_writer.py` (CTW 输出)
    <!-- 已修改：补充 v2.0 新 writer —— csa_writer.py（CSA 页面宏）/ cpc_writer.py（page1.cpc 页面配置）/ output_manager.py（page.map、master.tag、module_order.dat） -->
  • 实现状态: 已实现但差异大
  • 关键差异:
    - 参考库：直接生成 DEHDL 宏脚本（FORCEADD/FORCEPROP）
    - 当前项目：生成 CTW 模板 DSL，由 DEHDL 编译为等效的二进制页面
    - CTW 模板是声明式的，DEHDL 负责将其转化为 FORCEADD/FORCEPROP 指令
    - 当前项目需要确认 CTW 编译器是否能正确处理 DISPLAY 缩放因子、PAINT 颜色等细节

---

━━━ 文件 #9: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\place_parts.scr ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\place_parts.scr
  • 语言/格式: DEHDL 控制台 SCR 脚本（由 generate_hdl_scr.py 生成）
  • 行数估算: 384 行（27 个器件 × ~13 行/器件 + 尾部 3 行）
  • 大小: 8,889 B

🎯 职责定位
  • 功能域: 代码生成（DEHDL 交互式器件放置脚本）
  • 解决什么问题: 与 page1.scr 的"全自动宏模式"不同，这个 SCR 脚本需要用户在 DEHDL 图形界面中**手动点击**每个器件的放置位置。它提供属性设置（:`%Value:` 格式），但不包含坐标信息。

🧠 核心算法

  **SCR 脚本结构（已完全被 generate_hdl_scr.py 文档覆盖）：**
  
  每个器件块格式：
  ```
  {                                 ← 注释开始
    [N/27] RefDes  Value
    HDL器件: hdl_part  Primitive: hdl_primitive
    料号: hdl_sn_num               ← 仅 exact 匹配有此项
    匹配等级: match_level
  }
  add <hdl_lib>{cell_name}         ← 从库添加器件
  :%Value:PART_NAME=...            ← 属性设置（DEHDL 控制台命令）
  :%Value:VALUE=...
  :%Value:JEDEC_TYPE=...
  :%Value:PACKAGE_TYPE=...
  :%Value:SN_NUM=...               ← 仅 exact/size 匹配有此项
  { >>> 请点击放置 RefDes (Value) <<< }
  ```

  **匹配等级与 SN_NUM 的关系：**
  - `exact` 匹配：显示料号（共 24 个）
  - `size` 匹配（R278, R41）：显示"匹配等级: size"，无 SN_NUM 行
  - `prefix` 匹配（U5）：显示"匹配等级: prefix"，无 SN_NUM 行和无"料号"行

  **与 generate_hdl_scr.py 的输出对比：**
  - ✅ 完全一致：格式、顺序、属性映射
  - 验证了 generate_hdl_scr.py 的正确性

📡 对外接口
  • 暴露的函数/类: N/A（数据文件）
  • 输入契约: 在 DEHDL 控制台通过 `script place_parts.scr` 执行
  • 输出契约: 用户在 DEHDL 画布上手动点击放置 27 个器件

🔗 内部依赖
  • 依赖哪些模块: 依赖 hdl_lib/ 库在 DEHDL 中已配置；依赖 DEHDL 控制台环境
  • 被谁调用: DEHDL 控制台的 `script` 命令

✨ 设计亮点

  1. **交互式确认**: 每个器件放置后都有 `{ >>> 请点击放置 ... <<< }` 提示，用户可以看到具体要放哪个器件及其属性。

  2. **匹配等级透明**: 每个器件的注释中都标注了匹配等级，用户可以在放置时做出判断（如 prefix 匹配的 U5 可能需要人工检查）。

  3. **:`%Value:` 命令格式**: 这是 DEHDL 控制台的原生命令格式，比 CSA 宏的 FORCEPROP 更简洁。

⚠️ 潜在问题

  1. **`: %Value:` 空格问题**: 文件中使用 `:%Value:PART_NAME=...`（注意冒号后无空格），与 generate_hdl_scr.py 源码中的 `f":%Value:PART_NAME={hdl_primitive}"` 一致。需确认 DEHDL 接受此格式。

  2. **无错误处理**: 如果某个 `add` 命令失败（如库中无此器件），脚本会继续执行下一个，不会回滚。这可能使得部分页面处于不一致状态。

  3. **SN_NUM 字段不一致**: 在注释中用"料号"，在 `:%Value:` 命令中用 SN_NUM。两者语义相同但在文件中的命名不统一。

  4. **手动放置效率**: 对于 27 个器件的页面，手动点击 27 次。对于更大的页面（100+ 器件），这种方式不可行。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/writer/sch_writer.py`
    <!-- 已修改：补充 v2.0 新 writer —— scr_writer.py（DEHDL .scr 交互式放置脚本生成） -->
  • 实现状态: 部分实现
  • 关键差异:
    - 与 generate_hdl_scr.py 相同——当前项目的 CTW 模板模式覆盖了全自动放置，但缺少交互式 SCR 模式
    - SCR 模式对于需要人工审核的复杂电路（如模拟电路、BGA 布线）仍有价值

---

━━━ 文件 #10: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\place_parts_simple.scr ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\place_parts_simple.scr
  • 语言/格式: DEHDL 控制台 SCR 脚本（精简版）
  • 行数估算: 142 行（27 个器件 × ~5 行）
  • 大小: 1,754 B

🎯 职责定位
  • 功能域: 代码生成（极简交互式放置脚本）
  • 解决什么问题: place_parts.scr 的"精简版"——每个器件只有 `add` 命令，没有属性设置。适用于只需要快速放置器件符号、不需要设置属性的场景。或者是在属性已经通过 CSA 宏设置后，只需要调整位置时使用。

🧠 核心算法

  **极度精简的格式：**
  ```
  {
    N/27 RefDes - Value (cell_name)   ← 单行精简注释
  }
  add <hdl_lib>{cell_name}            ← 仅 add 命令，无属性
  ;                                    ← 分号分隔（原来的完整版用空行）
  ```

  **精简了什么：**
  | 维度 | place_parts.scr (完整版) | place_parts_simple.scr (精简版) |
  |------|--------------------------|-------------------------------|
  | 属性设置 | ✅ :`%Value:PART_NAME=...` 等 5-6 条 | ❌ 无 |
  | 料号信息 | ✅ 显示 | ❌ 不显示 |
  | 匹配等级 | ✅ 显示 | ❌ 不显示 |
  | 器件注释 | 5 行 | 1 行 |
  | 每器件行数 | ~13 行 | ~5 行 |

  **文件名推测的用法：**
  - `place_parts.scr` — 初始转换：添加器件 + 设置属性，手动放置
  - `place_parts_simple.scr` — 后续调整：只添加器件符号（属性可能由 CSA 宏或其他方式设置）

📡 对外接口
  • 暴露的函数/类: N/A
  • 输入契约: 在 DEHDL 控制台通过 `script place_parts_simple.scr` 执行
  • 输出契约: 27 个裸器件符号放置在画布上

🔗 内部依赖
  • 依赖哪些模块: 与 place_parts.scr 相同

✨ 设计亮点

  1. **极致精简**: 每个器件仅 5 行，文件大小只有完整版的 20%。加载和执行速度更快。

  2. **分号终止**: 每个 add 命令后紧跟 `;`，作为 DEHDL 控制台的命令分隔符。这是正确的 SCR 语法实践——完整版用空行分隔可能不够可靠。

  3. **适用场景清晰**: 适用于"属性已经正确，只需重新放置器件"的场景。这在迭代式设计调整中很常见。

⚠️ 潜在问题

  1. **无属性设置**: 放置后的器件没有 VALUE、PART_NAME、SN_NUM 等属性，需要后续手动设置或通过 CSA 宏批量设置。

  2. **缺少 `:{...}:` 注释块**: 精简版中的 `{}` 块是注释但格式不规范——缺少闭合的花括号层级。

  3. **无法追溯来源**: 没有匹配等级信息，用户不知道哪些器件是精确匹配、哪些是前缀匹配。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/writer/sch_writer.py`
    <!-- 已修改：补充 v2.0 新 writer —— scr_writer.py（DEHDL .scr 交互式放置脚本生成） -->
  • 实现状态: 部分实现
  • 关键差异: 精简版 SCR 是当前项目未覆盖的模式。如果要支持"仅重新放置"场景，需要在 sch_writer 中添加一个 `--placement-only` 或类似模式。

---

━━━ 文件 #11: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\diagnose_com.vbs ━━━

📋 文件身份
  • 路径: diagnose_com.vbs
  • 语言/格式: VBScript (Windows Script Host)
  • 行数估算: 134 行 | 大小: 3,904 B

🎯 职责定位
  • 功能域: 诊断（COM ProgID 注册表扫描）
  • 解决什么问题: 当 export_page13.py 无法创建 OrCAD Capture COM 实例时，扫描 Windows 注册表找 OrCAD 相关 ProgID 并逐个测试创建。8 个候选 ProgID 比 Python 版的 2 个更全面。

🧠 核心算法
  • 三步管线：(1) 注册表搜索 OrCAD/Capture 关键词 (2) 逐个 CreateObject 测试 8 个 ProgID (3) CLSID 搜索
  • ⚠️ 注册表枚举方式 `RegRead(key & "Enum\N" & i)` 在标准 Windows API 中不存在，步骤 1 和 3 实际上不会产生输出

📡 对外接口
  • 通过 `cscript diagnose_com.vbs` 运行，输出到标准输出

🔀 与当前项目的映射
  • 对应: `cis2hdl/core/diagnostics/config_validator.py`（已实现，但功能不同——当前项目校验配置而非诊断 OrCAD COM）

---

━━━ 文件 #12: Page13_AnomalyList.txt ━━━

📋 文件身份
  • 语言/格式: 纯文本 | 行数: 33 | 大小: 1,058 B
  • 功能域: 诊断（异常报告）

🎯 职责定位
  • 列出 Page 13 上所有 27 个器件都缺少 SNUM（物料号）。100% 异常率。

🔀 与当前项目的映射
  • 对应: `cis2hdl/core/diagnostics/quality.py`（已实现，多维度评分更全面）

---

━━━ 文件 #13: Page13_DeviceList.txt ━━━

📋 文件身份
  • 语言/格式: 纯文本定宽表格 | 行数: 36 | 大小: 4,851 B
  • 功能域: 器件属性清单

🎯 职责定位
  • 提供 Page 13 上 27 个器件的 RefDes/Value/Footprint（SNUM/PACKAGE_TYPE/Manufacturer/TYPE_NAME/DESCRIPTION 全为空）。由 TCL 脚本通过 `GetPartValue`/`GetPCBFootprint` 等 API 提取。

🔀 与当前项目的映射
  • 对应: `cis2hdl/core/ir/design.py` (DesignIR)（已实现，结构化 IR 替代中间文件）

---

━━━ 文件 #14: out_hdl.cpm ━━━

📋 文件身份
  • 路径: out_hdl.cpm | 语言/格式: DEHDL CPM 项目配置文件 | 行数: 39 | 大小: 832 B

🎯 职责定位
  • 功能域: 代码生成（DEHDL 项目配置）
  • DEHDL 项目文件格式：START_GLOBAL/START_CONCEPTHDL/START_PKGRXL/START_DESIGNSYNC/START_CONSTRAINT_MGR 五个段
  • 关键配置：`design_name 'out_hdl'`, `library 'hdl_lib' 'out_hdl_lib'`, `cpm_version '16.6'`
  • 由 SPI 机器生成，不可手动修改

🔀 与当前项目的映射
  • 对应: `cis2hdl/core/writer/cpm_writer.py`（已实现，模板化生成，支持配置参数）

---

━━━ 文件 #15: cds.lib ━━━

📋 文件身份
  • 路径: cds.lib | 语言/格式: Cadence 库配置文件 | 行数: 3 | 大小: 98 B

🎯 职责定位
  • 功能域: 库配置
  • 三行内容：`DEFINE out_hdl_lib worklib` / `INCLUDE $CONCEPT_INST_DIR/share/cdssetup/cds.lib` / `DEFINE hdl_lib hdl_lib`
  • 极简但关键：告诉 DEHDL 去哪里找库文件

🔀 与当前项目的映射
  • 对应: `cis2hdl/core/writer/cdslib_writer.py`（已实现，DEFINE 语句生成）

---

━━━ 文件 #16: c2esch.edif ━━━

📋 文件身份
  • 路径: c2esch.edif | 语言/格式: EDIF 3.0.0 (Lisp-like S 表达式) | 行数: 1,010 | 大小: 31,430 B

🎯 职责定位
  • 功能域: 数据导出（EDIF 中间格式）
  • 由 `c2esch` 工具从 OrCAD Capture 导出的 EDIF 中间文件
  • 包含两个库：`hdl_lib`（页面边框模板 C SIZE PAGE）+ `out_hdl_lib`（目标设计 out_hdl 的 sch_1 页）
  • 只有结构框架（totalPages 1, page SH_1），无实际器件/网络内容
  • 页面边框定义证实：C 纸区域为 x∈[-10750,0], y∈[0,8275]（与 generate_hdl_sch.py 中的坐标一致！）

🔀 与当前项目的映射
  • 对应: `cis2hdl/core/parser/edif_parser.py`（已实现，当前项目支持 EDIF 输入解析）

---

━━━ 文件 #17: run_tcl_export.bat ━━━

📋 文件身份
  • 路径: run_tcl_export.bat | 语言/格式: Windows Batch | 行数: 60 | 大小: 1,487 B

🎯 职责定位
  • 功能域: 流程编排（批处理启动器）
  • 三种执行模式：
    1. Tcl 批处理模式：`Capture.exe -tcl export_page13.tcl`（后台执行）
    2. Tcl 手动模式：提示用户在 GUI 中手动执行 Tcl 脚本
    3. COM 诊断模式：`cscript diagnose_com.vbs`
  • 关键路径：`C:\Cadence\SPB_16.6\tools\capture\Capture.exe`

🔀 与当前项目的映射
  • 对应: `cis2hdl/core/engine/conversion_engine.py`（已实现，Python 引擎管道替代批处理编排）

---

━━━ 文件 #18: CIS_to_HDL_Mapping.csv ━━━

📋 文件身份
  • 路径: CIS_to_HDL_Mapping.csv | 语言/格式: CSV (UTF-8-BOM) | 行数: 28 (+header) | 大小: 3,035 B

🎯 职责定位
  • 功能域: 匹配结果（机器可读）
  • 10 列：refdes/cis_value/cis_footprint/cis_fp_size/hdl_part/hdl_primitive/hdl_package_type/hdl_sn_num/match_level/note
  • 这是整个管线的"数据合约"——上游(match)的输出 = 下游(generate)的输入
  • 统计：24 exact + 2 size + 1 prefix = 27 器件全匹配（0 none）
  • 关键观察：
    - `100nF*` 和 `1uF*`（带 `*` 后缀）被 normalize_value 正确处理
    - `HSC0201-HDTB` → fp_size=0201（extract_pkg_size 正确提取）
    - `BGA96-32-1609W` → fp_size=BGA96（BGA 优先匹配）
    - `SC0201A` → fp_size=0201（4 位数字匹配）
  • U5(88e6320) 只有 prefix 匹配——芯片级器件的匹配是已知难点

🔀 与当前项目的映射
  • 对应: `cis2hdl/core/ir/match.py` (MatchResult)（已实现，结构化 IR 替代 CSV）



---

## Part IV: 文件索引与映射（来源：FILE_INDEX_AND_MAPPING.md）

> **来源文件**：`docs/FILE_INDEX_AND_MAPPING.md`（586 行）
> **原文档标题**：《文件索引与功能映射表》
> **合并方式**：逐节保全，仅调标题层级，不改写原文句子。
> **源文档注**：源文档内部原有的 `Part A~D` 小节编号（完整文件清单表 / 功能模块分组 / 功能映射表 / 阅读计划）为源文档内部编号，与合并后的 Part I~IV 编号层级不同，原样保留以免混淆；本 Part A.1/A.1.2 器件库目录（131）与 Part II §4.5 存在跨文档重叠信息，均按来源分别保留。


> 版本: v1.0 | 日期: 2026-07-31 | 作者: 高见远（首席架构师）
>
> 本文档基于对参考库 `CIStoHDL_standard/` 全部 30 个文件/目录的逐一分析，
> 以及对当前项目 `cis2hdl/` 源码树的扫描，建立完整的文件索引与功能映射。

---

### 参考库数据流总览

```
┌──────────────────────────────────────────────────────────────────┐
│  阶段 1: 数据导出 (Export)                                        │
│                                                                   │
│  HG5015-BE36_V10.DSN  ──→  export_page13.py  (COM)              │
│                      ──→  export_page13.tcl (TCL)               │
│                      ──→  export_page.tcl    (TCL)              │
│                          │                                        │
│                          ▼                                        │
│                   Page13_DeviceList.csv / .txt                    │
│                   Page13_AnomalyList.txt                          │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│  阶段 2: 器件匹配 (Match)                                         │
│                                                                   │
│  Page13_DeviceList.csv  ──→  match_cis_to_hdl.py                │
│  hdl_lib/ (100+ 目录)    ──→  (扫描 chips.prt + part.ptf)       │
│                          │                                        │
│                          ▼                                        │
│                   CIS_to_HDL_Mapping.csv / .txt                   │
│                   (三重匹配: Prefix + Footprint + Value)          │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│  阶段 3: 代码生成 (Generate)                                      │
│                                                                   │
│  CIS_to_HDL_Mapping.csv ──→  generate_hdl_sch.py                │
│                          ──→  generate_hdl_scr.py                │
│                          │                                        │
│                          ▼                                        │
│                   worklib/out_hdl/sch_1/page1.csa                 │
│                   worklib/out_hdl/sch_1/place_parts.scr           │
└──────────────────────────────────────────────────────────────────┘
```

---

### Part A: 完整文件清单表

#### A.1 参考库文件清单（CIStoHDL_standard/）

| # | 路径 | 大小 | 类型 | 功能域 | 优先级 |
|---|------|------|------|--------|:------:|
| 1 | `export_page13.py` | 15,664 B | Python | 数据导出（COM） | **高** |
| 2 | `generate_hdl_sch.py` | 14,617 B | Python | 代码生成（CSA） | **高** |
| 3 | `generate_hdl_scr.py` | 4,760 B | Python | 代码生成（SCR） | **高** |
| 4 | `match_cis_to_hdl.py` | 20,504 B | Python | 器件匹配 | **高** |
| 5 | `export_page.tcl` | 13,481 B | TCL | Cadence自动化 | **高** |
| 6 | `export_page13.tcl` | 12,913 B | TCL | Cadence自动化 | **高** |
| 7 | `test_tcl.tcl` | 996 B | TCL | 测试/调试 | 低 |
| 8 | `page1.scr` | 33,588 B | SCR | Cadence自动化 | **高** |
| 9 | `place_parts.scr` | 8,889 B | SCR | Cadence自动化 | 中 |
| 10 | `place_parts_simple.scr` | 1,754 B | SCR | Cadence自动化 | 低 |
| 11 | `test_place.scr` | 139 B | SCR | 测试/调试 | 低 |
| 12 | `diagnose_com.vbs` | 3,904 B | VBS | 诊断 | 中 |
| 13 | `run_tcl_export.bat` | 1,487 B | Batch | 流程编排 | 中 |
| 14 | `CIS_to_HDL_Mapping.txt` | 6,134 B | Data | 配置与映射 | **高** |
| 15 | `CIS_to_HDL_Mapping.csv` | 3,035 B | Data | 配置与映射 | **高** |
| 16 | `CIS_to_HDL_Mapping_Page13.csv` | 3,035 B | Data | 配置与映射 | 中 |
| 17 | `Page13_DeviceList.txt` | 4,851 B | Data | 配置与映射 | **高** |
| 18 | `Page13_DeviceList.csv` | 833 B | Data | 配置与映射 | **高** |
| 19 | `Page13_AnomalyList.txt` | 1,058 B | Data | 诊断 | 中 |
| 20 | `out_hdl.cpm` | 832 B | Output | 代码生成 | 中 |
| 21 | `cds.lib` | 98 B | Output | 配置与映射 | 低 |
| 22 | `c2esch.edif` | 31,430 B | Output | 数据导出 | 低 |
| 23 | `HG5015-BE36_V10.DSN` | 1.6 MB | Project | 项目文件 | **高** |
| 24 | `HG5015-BE36_V10_0.DBK` | 1.6 MB | Project | 项目文件 | 低 |
| 25 | `HG5015-BE36_V10.opj` | 4.8 KB | Project | 项目文件 | 中 |
| 26 | `HG5015-BE36_V10.EXP` | 65 KB | Project | 项目文件 | 低 |
| 27 | `tcl脚本导入orcad.docx` | 16 KB | Project | 文档 | 低 |
| 28 | `hdl_lib/` | 131 目录 | Library | 配置与映射 | **高** |
> 注（2026-08-07 代码核对）：`CIStoHDL_standard/hdl_lib/` 实际器件目录数为 **131**（排除"备份"目录，原"~100"为早期估计）；完整器件目录表见 A.1.2。
| 29 | `worklib/` | — | Output | 代码生成 | 中 |
| 30 | `adw/` | — | Output | 代码生成 | 低 |

#### A.1.2 参考库 HDL 器件目录表（吸收自 `_reference_index.md`，2026-08-03）

> 实际目录数核对（2026-08-07）：`CIStoHDL_standard/hdl_lib/` 排除"备份"后为 **131** 个器件目录（原文档写"70+ / 130"为旧口径）。每个器件遵循标准结构：`chips/chips.prt`、`entity/{verilog.v,vhdl.vhd,vlog004u.sir,pc.db}`、`metadata/{pinlist.txt,revision.dat,pdv_validation.txt}`、`part_table/part.ptf`、`sym_1/symbol.css`、`master.tag`，可选 `cfg_package/expand.cfg`、`sch_1/{.con,.dcf,.xcon}`。

| 目录名 | 类别 | 估计pins | 说明 |
|--------|------|---------|------|
| capacitor | 无源/电容 | 2 | 多 primitive (0201/0402/0603/0805) |
| resistor | 无源/电阻 | 2 | 多 primitive (0201~2512) |
| inductor | 无源/电感 | 2 | 基础电感 |
| diode | 半导体/二极管 | 2 | 二极管 |
| led | 半导体/LED | 2 | 发光二极管 |
| n_mos, p_mos | 半导体/MOSFET | 3 | MOS 管 |
| npn, pnp | 半导体/BJT | 3 | 三极管 |
| amplifier | 模拟/运放 | 5-8 | 运算放大器 |
| ldo | 电源/LDO | 3-6 | 低压差稳压器 |
| dc_dc | 电源/DC-DC | 5-12 | DC-DC 转换器 |
| connector | 连接器 | 2-100+ | 通用连接器(多 sym_) |
| crystal | 时钟/晶振 | 2-4 | 石英晶体振荡器 |
| interface | 通信/接口 | 4-28 | 接口芯片(RS485, CAN) |
| logic_gate | 逻辑/门 | 5-14 | 逻辑门电路 |
| flash, eeprom | 存储 | 8 | 存储器芯片 |
| fb | 无源/磁珠 | 2 | 铁氧体磁珠 |
| hole, mark | 辅助 | 1 | 安装孔/标记点 |
| 88e6071, 88e6320 | 芯片/交换机 | 100+ | 网络交换芯片 |
| bcm53125~bcm88470 | 芯片/博通 | 200-600+ | 博通系列(多 sym_) |
| b50210sb0, b50285 | 芯片/博通 | 300+ | 博通控制器 |
| bcm56150k | 芯片/博通 | 400+ | 博通交换(8 sym_) |
| bcm56760 | 芯片/博通 | 600+ | 博通大芯片(13 sym_) |
| an7552ct, att7022e | 芯片/通信 | 50+ | 通信处理芯片 |
| lpc176x, hc32 | 芯片/MCU | 50-100 | 微控制器 |
| ddr | 芯片/内存 | 78-200 | DDR 内存 |

#### A.1.3 参考库 worklib/out_hdl/sch_1 输出文件表（吸收自 `reference_project_file_list.md`，2026-08-03）

| 文件 | 大小 | 格式 | 说明 |
|------|------|------|------|
| `page1.csa` | 33,288 B | MACRO_DRAWING | ⭐ **CSA 页面主文件** |
| `page1.cpc` | 43 B | 页面配置 | `#ISCELL hdl_lib c#20size#20page *` |
| `page1.csv` | 123 B | 连通性 | `FILE_TYPE = CONNECTIVITY;` |
| `page2.csa` | 210 B | MACRO_DRAWING | 第二页（空页） |
| `page2.csb` | 512 B | 二进制 | Cadence 编译后的二进制页面 |
| `page2.cpc` | 0 B | 空文件 | |
| `page2.csv` | 118 B | 连通性 | |
| `out_hdl.dcf` | 2,937 B | S-expr | ⭐ **设计约束文件** (Cadence内部格式) |
| `out_hdl.dcf,1` | 572 B | S-expr | 约束备份 v1 |
| `out_hdl.dcf,2` | 537 B | S-expr | 约束备份 v2 |
| `out_hdl.xcon` | 3,313 B | S-expr | ⭐ **跨连接文件** |
| `out_hdl.xcon,1-3` | ~6 KB | S-expr | 跨连接备份 |
| `master.tag` | 38 B | text | 包含 `out_hdl.csa\nout_hdl.xcon\nout_hdl.dcf` |
| `module_order.dat` | 86 B | text | 模块顺序 |
| `page.map` | 10 B | text | 页面映射 `1 1 DDR3` |
| `hdldirect.dat` | 209 B | binary | HDL Direct 数据 |
| `pc.db` | 163 B | binary | 引脚约束数据库 |
| `verilog.v` | 216 B | Verilog | 生成的 Verilog 代码 |
| `viewprps.prp` | 157 B | text | 视图属性 |
| `vlog004u.sir` | 359 B | text | 符号实例报告 |
| `place_parts.scr` | 8,889 B | script | 器件放置脚本 |

---

#### A.2 当前项目核心文件清单（cis2hdl/）

| # | 路径 | 功能域 | 说明 |
|---|------|--------|------|
| 31 | `cis2hdl/core/engine/conversion_engine.py` | 流程编排 | 六阶段转换管道控制器 |
| 32 | `cis2hdl/core/parser/base.py` | 解析器 | 解析器注册表与基类 |
| 33 | `cis2hdl/core/parser/dsn/dsn_parser.py` | 解析器 | 二进制DSN顶层调度器 |
| 34 | `cis2hdl/core/parser/dsn/ole_reader.py` | 解析器 | OLE复合文档读取 |
| 35 | `cis2hdl/core/parser/dsn/page_parser.py` | 解析器 | DSN页面流解析 |
| 36 | `cis2hdl/core/parser/dsn/structures.py` | 解析器 | DSN数据结构定义 |
| 37 | `cis2hdl/core/parser/dsn/binary_reader.py` | 解析器 | 二进制流读取工具 |
| 38 | `cis2hdl/core/parser/edif_parser.py` | 解析器 | EDIF格式解析器 |
| 39 | `cis2hdl/core/parser/hdl_scanner.py` | 解析器 | HDL库扫描器（对应参考库match_cis_to_hdl.py的库扫描部分） |
| 40 | `cis2hdl/core/parser/chips_prt.py` | 解析器 | chips.prt文件解析 |
| 41 | `cis2hdl/core/parser/part_ptf.py` | 解析器 | part.ptf文件解析 |
| 42 | `cis2hdl/core/parser/symbol_css.py` | 解析器 | symbol.css文件解析 |
| 43 | `cis2hdl/core/parser/layout_mapper.py` | 解析器 | 坐标布局映射 |
| 44 | `cis2hdl/core/parser/cross_validator.py` | 解析器 | 跨格式校验 |
| 45 | `cis2hdl/core/matcher/__init__.py` | 匹配器 | 匹配器模块入口 |
| 46 | `cis2hdl/core/matcher/base.py` | 匹配器 | 匹配器基类 |
| 47 | `cis2hdl/core/matcher/pipeline.py` | 匹配器 | 匹配管道（v2.0 已重构为两阶段，原"四级链式"为历史口径；详见 A.2 补充） |
| 48 | `cis2hdl/core/matcher/exact.py` | 匹配器 | 精确指纹匹配 |
| 49 | `cis2hdl/core/matcher/feature.py` | 匹配器 | 特征提取匹配 |
| 50 | `cis2hdl/core/matcher/fuzzy.py` | 匹配器 | 模糊名称匹配 |
| 51 | `cis2hdl/core/matcher/registry.py` | 匹配器 | 匹配器注册表 |
| 52 | `cis2hdl/core/writer/base.py` | 代码生成 | Writer基类与注册表 |
| 53 | `cis2hdl/core/writer/cpm_writer.py` | 代码生成 | CPM项目文件生成 |
| 54 | `cis2hdl/core/writer/cdslib_writer.py` | 代码生成 | cds.lib库配置生成 |
| 55 | `cis2hdl/core/writer/sch_writer.py` | 代码生成 | SCH原理图生成（CTW模板） |
| 56 | `cis2hdl/core/db/component_db.py` | 数据库 | 统一元件数据库 |
| 57 | `cis2hdl/core/ir/component.py` | IR | 元件定义IR |
| 58 | `cis2hdl/core/ir/design.py` | IR | 设计IR（页面/网络） |
| 59 | `cis2hdl/core/ir/match.py` | IR | 匹配结果IR |
| 60 | `cis2hdl/core/diagnostics/pipeline.py` | 诊断 | 诊断管道 |
| 61 | `cis2hdl/core/diagnostics/report_gen.py` | 诊断 | 报告生成 |
| 62 | `cis2hdl/core/diagnostics/error_diagnosis.py` | 诊断 | 错误诊断引擎 |
| 63 | `cis2hdl/core/diagnostics/file_validator.py` | 诊断 | 文件校验 |
| 64 | `cis2hdl/core/diagnostics/config_validator.py` | 诊断 | 配置校验 |
| 65 | `cis2hdl/core/diagnostics/quality.py` | 诊断 | 质量评估 |
| 66 | `cis2hdl/core/diagnostics/recovery.py` | 诊断 | 错误恢复 |
| 67 | `cis2hdl/core/diagnostics/tracker.py` | 诊断 | 进度跟踪 |
| 68 | `cis2hdl/core/validator/base.py` | 校验 | 校验器基类 |
| 69 | `cis2hdl/core/validator/pin_validator.py` | 校验 | 引脚校验 |
| 70 | `cis2hdl/core/validator/power_validator.py` | 校验 | 电源校验 |
| 71 | `cis2hdl/core/validator/net_validator.py` | 校验 | 网络校验 |
| 72 | `cis2hdl/core/net_utils.py` | 工具 | 网络分类工具 |
| 73 | `cis2hdl/core/config.py` | 配置 | 全局配置 |
| 74 | `cis2hdl/utils/naming.py` | 工具 | 命名工具 |

#### A.2 补充（2026-08-07 代码树核对新增）

> 以下文件为按 08-07 实际代码树核对后新增的当前项目核心文件（原 #31~#74 表保持不变）。核对范围：`cis2hdl/core/{matcher,writer,parser,diagnostics}/`。

| # | 路径 | 功能域 | 说明 |
|---|------|--------|------|
| 75 | `cis2hdl/core/matcher/type_hypothesis.py` | 匹配器 v2.0 | 类型假设生成（Stage 1） |
| 76 | `cis2hdl/core/matcher/candidate_pool.py` | 匹配器 v2.0 | 候选池构建（Stage 1） |
| 77 | `cis2hdl/core/matcher/prefix_filter.py` | 匹配器 v2.0 | 前缀过滤（对应参考库 body_map/body_fallback） |
| 78 | `cis2hdl/core/matcher/passive_matcher.py` | 匹配器 v2.0 | 被动匹配 5 级（Stage 2） |
| 79 | `cis2hdl/core/matcher/active_matcher.py` | 匹配器 v2.0 | 主动匹配 5 维（Stage 2） |
| 80 | `cis2hdl/core/matcher/value_matcher.py` | 匹配器 v2.0 | Value 值匹配 |
| 81 | `cis2hdl/core/matcher/fallback.py` | 匹配器 v2.0 | 回退匹配 |
| 82 | `cis2hdl/core/matcher/match_config.py` | 匹配器 v2.0 | 匹配配置（STOP_SEARCH=0.75 / NEEDS_REVIEW=0.40） |
| 83 | `cis2hdl/core/matcher/scoring.py` | 匹配器 v2.0 | 打分（final_conf=prior×within） |
| 84 | `cis2hdl/core/writer/csa_writer.py` | 代码生成 | CSA 原理图页面生成（对应参考库 generate_hdl_sch.py / page1.scr） |
| 85 | `cis2hdl/core/writer/scr_writer.py` | 代码生成 | DEHDL .scr 交互式放置脚本（对应参考库 generate_hdl_scr.py） |
| 86 | `cis2hdl/core/writer/xcon_writer.py` | 代码生成 | .xcon 交叉连接文件生成 |
| 87 | `cis2hdl/core/writer/cpc_writer.py` | 代码生成 | .cpc 页面配置生成（expand.cfg） |
| 88 | `cis2hdl/core/writer/output_manager.py` | 代码生成 | 输出管理（page.map / master.tag / module_order.dat / .con） |
| 89 | `cis2hdl/core/writer/mapping_csv_writer.py` | 代码生成 | 映射结果 CSV 输出 |
| 90 | `cis2hdl/core/writer/error_logger.py` | 代码生成 | 写入错误日志 |
| 91 | `cis2hdl/core/parser/component_catalog.py` | 解析器 | 元件目录索引 |
| 92 | `cis2hdl/core/parser/cross_ref_parser.py` | 解析器 | 交叉引用解析 |
| 93 | `cis2hdl/core/parser/pstchip_parser.py` | 解析器 | pstchip.dat 解析 |
| 94 | `cis2hdl/core/parser/pstxnet_parser.py` | 解析器 | pstxnet.dat 解析 |
| 95 | `cis2hdl/core/parser/pstxnet_netlist_parser.py` | 解析器 | pstxnet 网表解析 |
| 96 | `cis2hdl/core/diagnostics/diagnostic_report.py` | 诊断 | 诊断报告输出 |
| 97 | `cis2hdl/core/diagnostics/file_inventory.py` | 诊断 | 文件清单盘点 |
| 98 | `cis2hdl/core/diagnostics/history.py` | 诊断 | 历史记录 |
| 99 | `cis2hdl/core/diagnostics/multi_source.py` | 诊断 | 多数据源诊断 |
| 100 | `cis2hdl/core/diagnostics/olb_integrity.py` | 诊断 | OLB 完整性检查 |

> 补充说明：`cis2hdl/core/parser/` 下另有 `dsn/`（二进制 DSN 解析，含 dsn_parser/ole_reader/page_parser/structures/binary_reader 等）与 `olb/`（OLB 库解析）两个子目录；匹配器 v2.0 已重构为**两阶段**（TypeHypothesis→CandidatePool→PassiveMatcher/ActiveMatcher），原"四级管道（Exact→Fuzzy→Feature→Manual）"描述为历史口径。

---

### Part B: 功能模块分组

#### B.1 参考库功能模块分组

```
┌─────────────────────────────────────────────────────────────────┐
│  1. 解析器 (Parser)                                              │
│     • export_page13.py   — COM方式从OrCAD Capture导出器件属性    │
│     • export_page.tcl    — TCL通用页面导出脚本                   │
│     • export_page13.tcl  — TCL特定页面(13-DDR3)导出脚本          │
│     • test_tcl.tcl       — TCL API可用性测试                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  2. 匹配器 (Matcher)                                             │
│     • match_cis_to_hdl.py — 核心匹配引擎                        │
│       ├── read_cis_data()      读取Page_DeviceList.csv           │
│       ├── parse_chips_prt()    解析HDL库chips.prt                │
│       ├── parse_part_ptf()     解析HDL库part.ptf                 │
│       ├── match_by_prefix()    前缀匹配 (RefDes→HDL器件类别)     │
│       └── match_by_footprint() 封装匹配 + Value值匹配            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  3. 代码生成器 (Code Generator)                                  │
│     • generate_hdl_sch.py — 生成DEHDL原理图CSA宏文件             │
│       ├── get_prop_offsets()    读取symbol.css属性偏移           │
│       ├── calc_position()       网格布局计算                     │
│       ├── map_cis_to_dehdl_coords() CIS→DEHDL坐标映射            │
│       └── generate_csa()        生成CSA文件(FORCEADD/FORCEPROP)  │
│     • generate_hdl_scr.py — 生成交互式放置SCR脚本                │
│     • out_hdl.cpm         — DEHDL项目配置文件                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  4. Cadence 自动化 (Cadence Automation)                          │
│     • page1.scr              — DEHDL页面宏绘制脚本               │
│     • place_parts.scr        — 批量器件放置脚本                  │
│     • place_parts_simple.scr — 简化版放置脚本                    │
│     • test_place.scr         — 放置测试                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  5. 诊断 (Diagnostics)                                           │
│     • diagnose_com.vbs        — COM ProgID注册表诊断             │
│     • Page13_AnomalyList.txt  — 器件异常报告(缺失SNUM)           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  6. 配置与映射 (Configuration & Mapping)                         │
│     • CIS_to_HDL_Mapping.txt      — 匹配结果(人类可读)           │
│     • CIS_to_HDL_Mapping.csv      — 匹配结果(机器可读)           │
│     • CIS_to_HDL_Mapping_Page13.csv — 同上的Page13副本           │
│     • Page13_DeviceList.txt       — 器件属性清单                 │
│     • Page13_DeviceList.csv       — 器件属性清单                 │
│     • cds.lib                     — Cadence库配置文件            │
│     • hdl_lib/                    — HDL标准器件库(100+目录)      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  7. 项目文件 (Project Files)                                     │
│     • HG5015-BE36_V10.DSN  — OrCAD Capture原始设计               │
│     • HG5015-BE36_V10.opj  — OrCAD项目文件                       │
│     • HG5015-BE36_V10.EXP  — 导出配置                            │
│     • run_tcl_export.bat   — 批处理启动器(流程编排)              │
│     • tcl脚本导入orcad.docx — 操作文档                           │
└─────────────────────────────────────────────────────────────────┘
```

#### B.2 当前项目功能模块分组

```
┌─────────────────────────────────────────────────────────────────┐
│  1. 解析器 (Parser)                  cis2hdl/core/parser/        │
│     • dsn/        — 二进制DSN解析 (OLE→页面流→IR)               │
│     • edif_parser.py  — EDIF格式解析                             │
│     • hdl_scanner.py  — HDL库扫描                                │
│     • chips_prt.py    — chips.prt解析                           │
│     • part_ptf.py     — part.ptf解析                            │
│     • symbol_css.py   — symbol.css解析                          │
│     • layout_mapper.py — 坐标映射                               │
│     • cross_validator.py — 跨格式校验                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  2. 匹配器 (Matcher)                  cis2hdl/core/matcher/     │
│     • pipeline.py   — 匹配管道（v2.0 两阶段，原"四级"为历史口径） │
│     • exact.py      — 指纹精确匹配 (P1)                         │
│     • fuzzy.py      — 模糊名称匹配 (P2)                         │
│     • feature.py    — 特征提取匹配 (P3)                         │
│     • registry.py   — 匹配器注册                                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  3. 代码生成器 (Writer)               cis2hdl/core/writer/      │
│     • cpm_writer.py   — CPM项目文件生成                         │
│     • cdslib_writer.py — cds.lib生成                           │
│     • sch_writer.py   — SCH原理图生成(CTW模板DSL)               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  4. 引擎 (Engine)                     cis2hdl/core/engine/       │
│     • conversion_engine.py — 六阶段转换管道                     │
│       (诊断→解析→扫描→匹配→校验→生成)                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  5. 诊断 (Diagnostics)                cis2hdl/core/diagnostics/  │
│     • pipeline.py    — 诊断管道                                 │
│     • report_gen.py  — 报告生成                                 │
│     • error_diagnosis.py — 错误诊断                             │
│     • quality.py     — 质量评估(对应参考库AnomalyList)          │
│     • recovery.py    — 错误恢复                                 │
│     • tracker.py     — 进度跟踪                                 │
│     • file_validator.py — 文件校验                             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  6. IR层 (Intermediate Representation)  cis2hdl/core/ir/        │
│     • component.py — 元件定义                                   │
│     • design.py    — 设计结构(页面/网络)                        │
│     • match.py     — 匹配结果                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  7. GUI (图形界面)                     cis2hdl/gui/              │
│     • app.py / main_window.py — 应用主窗口                      │
│     • panels/ — 面板组件(项目/诊断/日志/预览/匹配审查)          │
│     • dialogs/ — 对话框(设置/恢复/匹配确认)                     │
│     • widgets/ — 组件(转换Worker)                               │
└─────────────────────────────────────────────────────────────────┘
```

#### B.2 补充（2026-08-07 代码树核对，v2.0）

> 以下为按 08-07 实际代码树核对后新增/修正的模块文件，上方原 ASCII 分组图保持不动（其中"四级链式管道"已过时，v2.0 为两阶段）。

**匹配器 `core/matcher/`（v2.0 两阶段重构）**：
- Stage 1 候选生成：`type_hypothesis.py`、`candidate_pool.py`、`prefix_filter.py`
- Stage 2 匹配：`passive_matcher.py`（5 级）、`active_matcher.py`（5 维）、`value_matcher.py`、`fallback.py`
- 配置/打分：`match_config.py`（STOP_SEARCH=0.75 / NEEDS_REVIEW=0.40）、`scoring.py`（final_conf=prior×within）
- 原有：`exact.py`、`fuzzy.py`、`feature.py`、`base.py`、`registry.py`、`pipeline.py`

**代码生成器 `core/writer/`（新增 5 个核心 writer）**：`csa_writer.py`、`scr_writer.py`、`xcon_writer.py`、`cpc_writer.py`、`output_manager.py`（另有 `mapping_csv_writer.py`、`error_logger.py`）

**解析器 `core/parser/`（新增）**：`component_catalog.py`、`cross_ref_parser.py`、`pstchip_parser.py`、`pstxnet_parser.py`、`pstxnet_netlist_parser.py`（另有 `dsn/`、`olb/` 两个子目录）

**诊断 `core/diagnostics/`（新增）**：`diagnostic_report.py`、`file_inventory.py`、`history.py`、`multi_source.py`、`olb_integrity.py`

---

### Part C: 功能映射表

#### 参考库 → 当前项目 cis2hdl 对应关系

| 参考库文件 | 功能 | 当前项目对应文件 | 实现状态 | 备注 |
|-----------|------|-----------------|:------:|------|
| **数据导出层** |
| `export_page13.py` | OrCAD COM 属性导出 | `cis2hdl/core/parser/dsn/dsn_parser.py` | ✅ 已实现 | 参考库用COM读取；当前项目直接解析DSN二进制，无需OrCAD运行时 |
| `export_page.tcl` | TCL通用页面导出 | `cis2hdl/core/parser/dsn/page_parser.py` | ✅ 已实现 | TCL方式已由二进制DSN解析器替代 |
| `export_page13.tcl` | TCL特定页面导出 | 同上 + `dsn/ole_reader.py` | ✅ 已实现 | OLE复合文档→页面流→DesignIR |
| `run_tcl_export.bat` | 流程启动器 | `cis2hdl/core/engine/conversion_engine.py` | ✅ 已实现 | 批处理编排→Python引擎管道 |
| **器件匹配层** |
| `match_cis_to_hdl.py` | 核心匹配引擎 | `cis2hdl/core/matcher/pipeline.py` | ✅ 已实现 | 参考库:三重匹配; 当前:v2.0 两阶段管道（TypeHypothesis→CandidatePool→Passive/ActiveMatcher；原"四级管道"为历史口径） |
| `match_cis_to_hdl.py::read_cis_data()` | CSV读取 | `cis2hdl/core/parser/dsn/dsn_parser.py` | ✅ 已实现 | 不再依赖CSV中间文件 |
| `match_cis_to_hdl.py::parse_chips_prt()` | chips.prt解析 | `cis2hdl/core/parser/chips_prt.py` | ✅ 已实现 | 独立解析器，支持更多PINUSE类型 |
| `match_cis_to_hdl.py::parse_part_ptf()` | part.ptf解析 | `cis2hdl/core/parser/part_ptf.py` | ✅ 已实现 | 结构化解析，返回PartProperty |
| `match_cis_to_hdl.py::_read_file_auto_encoding()` | 自动编码检测 | `cis2hdl/core/parser/chips_prt.py` (内置) | ✅ 已实现 | UTF-8/GBK自动回退 |
| **代码生成层** |
| `generate_hdl_sch.py` | CSA原理图宏生成 | `cis2hdl/core/writer/sch_writer.py` | ✅ 已实现 | 参考库:CSA(FORCEADD); 当前:CTW模板DSL |
| `generate_hdl_sch.py::get_prop_offsets()` | symbol.css解析 | `cis2hdl/core/parser/symbol_css.py` | ✅ 已实现 | 独立解析器，返回SchematicSymbolDef |
| `generate_hdl_sch.py::map_cis_to_dehdl_coords()` | 坐标映射 | `cis2hdl/core/parser/layout_mapper.py` | ✅ 已实现 | 居中+缩放策略 |
| `generate_hdl_scr.py` | SCR交互脚本生成 | `cis2hdl/core/writer/sch_writer.py` | ⚠️ 部分实现 | SCR功能已被CTW模板替代，但交互式放置场景未覆盖 |
| `page1.scr` | DEHDL页面宏 | `cis2hdl/core/writer/sch_writer.py` (CTW输出) | ✅ 已实现 | SCR宏指令→CTW声明式模板 |
| `place_parts.scr` | 批量放置脚本 | `cis2hdl/core/writer/sch_writer.py` | ✅ 已实现 | 位置由CTW模板中的x/y坐标指定 |
| `out_hdl.cpm` | CPM项目配置 | `cis2hdl/core/writer/cpm_writer.py` | ✅ 已实现 | 模板化生成，支持配置参数 |
| `cds.lib` | 库配置 | `cis2hdl/core/writer/cdslib_writer.py` | ✅ 已实现 | DEFINE语句生成 |
| **诊断层** |
| `diagnose_com.vbs` | COM诊断 | `cis2hdl/core/diagnostics/config_validator.py` | ✅ 已实现 | COM ProgID扫描→配置校验 |
| `Page13_AnomalyList.txt` | 异常报告 | `cis2hdl/core/diagnostics/quality.py` | ✅ 已实现 | No_SNUM→质量评估报告 |
| `Page13_AnomalyList.txt` | 异常报告 | `cis2hdl/core/diagnostics/report_gen.py` | ✅ 已实现 | 统一报告生成 |
| **配置与映射** |
| `CIS_to_HDL_Mapping.txt/csv` | 映射结果 | `cis2hdl/core/ir/match.py` (MatchResult) | ✅ 已实现 | 结构化MatchResult替代CSV |
| `Page13_DeviceList.txt/csv` | 器件清单 | `cis2hdl/core/ir/design.py` (DesignIR) | ✅ 已实现 | IR替代中间文件 |
| `hdl_lib/` | HDL标准器件库 | `cis2hdl/core/parser/hdl_scanner.py` + `component_db.py` | ✅ 已实现 | 扫描→ComponentDB统一索引 |
| **项目文件** |
| `HG5015-BE36_V10.DSN` | 测试DSN | `cis2hdl/tests/fixtures/` | 🔶 待确认 | 需确认测试夹具路径 |
| `HG5015-BE36_V10.opj` | OrCAD项目 | 不需要 | N/A | opj仅OrCAD使用 |
| `test_tcl.tcl` | TCL测试 | 不需要 | N/A | TCL方式已废弃 |
| `tcl脚本导入orcad.docx` | 操作文档 | 不需要 | N/A | 已归档为参考 |

#### 新增能力（参考库未覆盖）

| 能力 | 当前项目实现 | 说明 |
|------|-------------|------|
| GUI 界面 | `cis2hdl/gui/` | 完整Tkinter GUI：项目面板、诊断面板、日志面板、匹配审查面板、报告面板 |
| 校验层 | `cis2hdl/core/validator/` | 引脚校验、电源校验、网络校验（参考库无此层） |
| 错误恢复 | `cis2hdl/core/diagnostics/recovery.py` | 转换失败后的自动恢复策略 |
| 进度跟踪 | `cis2hdl/core/diagnostics/tracker.py` | 六阶段进度实时跟踪 |
| EDIF 支持 | `cis2hdl/core/parser/edif_parser.py` | 参考库只有EDIF输出示例，当前项目支持EDIF输入解析 |

---

### Part D: 阅读计划

> ✅ **阅读计划已完成**（截至 2026-08-07）。精读产出已归档：逐文件精读见 Part III（本合并文档·参考库精读笔记）；7 路并行精读报告见 doc-researcher-1~7；本部分保留为历史参考，不再作为待办。

#### D.1 按优先级排序的阅读顺序

##### 🔴 Phase 1 — 必须精读（15 个文件）：理解核心数据流

| 阅读顺序 | 文件 | 理由 | 预计时间 |
|:------:|------|------|:------:|
| 1 | `match_cis_to_hdl.py` | **核心匹配引擎** — 整个流程的"心脏"。理解三重匹配算法、chips.prt/part.ptf解析方式、编码处理策略 | 45 min |
| 2 | `CIS_to_HDL_Mapping.txt` | **匹配结果样本** — 了解输入输出数据格式、匹配等级(●/○/△/✕)的含义 | 10 min |
| 3 | `generate_hdl_sch.py` | **CSA代码生成** — 了解FORCEADD/FORCEPROP命令格式、坐标映射、C纸布局 | 30 min |
| 4 | `generate_hdl_scr.py` | **SCR脚本生成** — 了解交互式放置流程、DEHDL控制台命令格式 | 15 min |
| 5 | `export_page13.py` | **COM导出** — 了解OrCAD COM接口使用方式、pywin32依赖、属性提取逻辑 | 25 min |
| 6 | `export_page13.tcl` | **TCL导出** — 了解DboTclHelper API用法、GetEffectivePropStringValue等关键函数 | 25 min |
| 7 | `export_page.tcl` | **TCL通用导出** — 与export_page13.tcl对比，理解参数化差异 | 20 min |
| 8 | `page1.scr` | **DEHDL宏脚本** — 完整FORCEADD/FORCEPROP/DISPLAY命令序列，理解DEHDL页面格式 | 20 min |
| 9 | `run_tcl_export.bat` | **流程启动器** — 理解原始工作流编排（三种执行模式） | 5 min |
| 10 | `Page13_DeviceList.txt` | **器件清单样本** — 理解CIS导出数据结构（RefDes/Value/Footprint/SNUM等8字段） | 5 min |
| 11 | `CIS_to_HDL_Mapping.csv` | **映射CSV** — 理解CSV列结构：cis_*/hdl_*/match_level | 5 min |
| 12 | `diagnose_com.vbs` | **COM诊断** — 理解注册表扫描逻辑、OrCAD ProgID候选列表 | 10 min |
| 13 | `Page13_AnomalyList.txt` | **异常报告** — 理解"缺失SNUM"等常见异常类型 | 5 min |
| 14 | `place_parts.scr` | **放置脚本样本** — 与generate_hdl_scr.py输出对比 | 10 min |
| 15 | `out_hdl.cpm` | **CPM输出样本** — 理解DEHDL项目文件格式 | 5 min |

##### 🟡 Phase 2 — 建议阅读（8 个文件）：理解周边逻辑

| 阅读顺序 | 文件 | 理由 |
|:------:|------|------|
| 16 | `hdl_lib/` 目录结构 | 理解HDL库组织方式：每个器件一个目录，含chips.prt/symbol.css/part.ptf |
| 17 | `HG5015-BE36_V10.opj` | OrCAD项目结构（XML格式） |
| 18 | `place_parts_simple.scr` | 简化SCR与完整版对比 |
| 19 | `CIS_to_HDL_Mapping_Page13.csv` | 确认与通用版的一致性 |
| 20 | `worklib/` 目录结构 | 理解DEHDL输出目录布局 |
| 21 | `cds.lib` | Cadence库引用格式 |

##### 🟢 Phase 3 — 可选阅读（5 个文件）：补充背景

| 阅读顺序 | 文件 | 理由 |
|:------:|------|------|
| 22 | `test_tcl.tcl` | TCL API测试，理解Capture TCL环境 |
| 23 | `test_place.scr` | 最小SCR测试 |
| 24 | `c2esch.edif` | EDIF输出格式参考 |
| 25 | `HG5015-BE36_V10.EXP` | 导出配置 |
| 26 | `tcl脚本导入orcad.docx` | 操作文档，历史参考 |

#### D.2 推荐阅读路径图

```
                        ┌──────────────────────┐
                        │  入口: run_tcl_export │
                        │       .bat           │
                        └──────┬───────────────┘
                               │
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
        ┌────────────┐  ┌────────────┐  ┌────────────┐
        │ COM 方式    │  │ TCL 方式    │  │ 诊断        │
        │ export_     │  │ export_     │  │ diagnose_   │
        │ page13.py   │  │ page13.tcl  │  │ com.vbs     │
        └──────┬─────┘  └──────┬─────┘  └────────────┘
               │               │
               └───────┬───────┘
                       ▼
              ┌─────────────────┐
              │ Page13_DeviceList│
              │ .csv / .txt      │
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │ ★ match_cis_to_  │  ← 核心！
              │    hdl.py        │
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │ CIS_to_HDL_      │
              │ Mapping.csv/.txt │
              └────────┬────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
   ┌───────────┐ ┌───────────┐ ┌─────────┐
   │ generate_ │ │ generate_ │ │ page1.  │
   │ hdl_sch.py│ │ hdl_scr.py│ │ scr     │
   └─────┬─────┘ └─────┬─────┘ └────┬────┘
         │             │            │
         ▼             ▼            ▼
   ┌───────────┐ ┌───────────┐ ┌─────────┐
   │ page1.csa │ │ place_    │ │ DEHDL   │
   │           │ │ parts.scr │ │ 直接执行 │
   └───────────┘ └───────────┘ └─────────┘
```

#### D.3 关键对比阅读点

| 对比维度 | 参考库实现 | 当前项目实现 | 重点关注 |
|---------|-----------|-------------|---------|
| 匹配策略 | 三重匹配(Prefix+Footprint+Value) | v2.0 两阶段管道（TypeHypothesis→CandidatePool→Passive/ActiveMatcher；原"四级管道(Exact→Fuzzy→Feature→Manual)"为历史口径） | 当前项目更精细，但参考库的Footprint尺寸提取逻辑值得借鉴 |
| 输出格式 | CSA宏(FORCEADD/FORCEPROP) | CTW模板DSL | 当前项目更声明式，需确认DEHDL对CTW的兼容性 |
| 坐标映射 | CIS坐标→C纸居中缩放 | layout_mapper.py | 算法逻辑一致，需确认缩放比例差异 |
| 库扫描 | walk目录+解析chips.prt+part.ptf | HDLLibScanner(扫描→ComponentDB) | 功能完整覆盖，当前项目多了symbol.css解析 |
| 编码处理 | _read_file_auto_encoding() | 内置于各解析器 | 需确认当前项目是否也支持GBK回退 |

---

### 附录: 数据流关键数据结构对照

#### A.1 匹配结果数据格式

**参考库 (CIS_to_HDL_Mapping.csv)**:
```
refdes,cis_value,cis_footprint,cis_fp_size,hdl_part,hdl_primitive,hdl_package_type,hdl_sn_num,match_level
C460,100nF,HSC0201-HDTB,0201,capacitor,CAPACITOR_0201,C0402,M01.010024,exact
```

**当前项目 (MatchResult)**:
```python
MatchResult(
    confidence=1.0,
    strategy=MatchStrategy.EXACT,
    source_library_id="CIS::C460",
    target_library_id="HDL::capacitor::CAPACITOR_0201",
    pin_mapping={},
    warnings=[],
)
```

#### A.2 器件数据格式

**参考库 (Page13_DeviceList.csv)**:
```
RefDes,Value,Footprint,SNUM,PACKAGE_TYPE,Manufacturer,TYPE_NAME,DESCRIPTION
C460,100nF,HSC0201-HDTB,,,,,,
```

**当前项目 (ComponentDef / ComponentInstanceIR)**:
```python
ComponentDef(
    library_id="capacitor::CAPACITOR_0201",
    part_name="CAPACITOR_0201",
    prefix="C",
    footprint="0201",
    ...
)
```

---

> **文档结束** — 此文件为 Phase 0 交付物；Phase 1 精读已完成（2026-08-07），本文件已于 2026-08-07 按实际代码树刷新并吸收 `_reference_index.md` / `reference_project_file_list.md`。


---

## 合并保全声明

> 本文件为 4 份调研文档的内容保全式合并。以下为章节覆盖证明，逐章核对无遗漏。

### Part I 覆盖证明（来源 ORCAD_SOURCE_ANALYSIS.md，共 19 个一级章节）

| 合并后章节 | 状态 |
|:---|:---:|
| `### 0. 分析概要` | ✅ 保留 |
| `### 1. DSN/OLB 二进制格式 — 官方 XSD 验证` | ✅ 保留 |
| `### 2. HDL 文件格式 — 完整定义` | ✅ 保留 |
| `### 3. 器件模板系统（Component Template Wizard）` | ✅ 保留 |
| `### 4. template.bom 格式` | ✅ 保留 |
| `### 5. CIS 网表格式化器 DLL 列表` | ✅ 保留 |
| `### 6. 对 cis2hdl 项目的关键启示` | ✅ 保留 |
| `### 7. 关键文件位置速查` | ✅ 保留 |
| `### 8. CIS 标准库结构（新增 — Explore-4 Agent 分析）` | ✅ 保留 |
| `### 9. 第二轮深度挖掘` | ✅ 保留 |
| `### 11. XSD 全量解析 + ISCF 导出 + DRC 体系（Explore-2 完整报告）` | ✅ 保留 |
| `### 10. TCL 脚本体系全析（Explore-8 Agent 完整报告）<!-- 注：章节编号待整理，内容不受影响（§10 位于 §11 之后，为原始编号跳跃所致） -->` | ✅ 保留 |
| `### 12. EDIF 格式深度分析 + 全部配置文件（Explore-12 完整报告）` | ✅ 保留 |
| `### 13. GUI 渲染与坐标系统全析（Explore-13 完整报告）` | ✅ 保留 |
| `### 14. PSpice/VHDL/Verilog 全析（Explore-14 完整报告）` | ✅ 保留 |
| `### 15. TCL 基础设施全析（Explore-15 完整报告）` | ✅ 保留 |
| `### 16. 学习系统 + 加密组件 + 网表生成器 + FPGA 编译（Explore-18 完整报告）` | ✅ 保留 |
| `### 17. 全量文件分析 + HDL 参考库完整结构（Explore-16 完整报告）` | ✅ 保留 |
| `### 18. SPICE 仿真文件全析 + lman/locales 配置（Explore-17 完整报告）` | ✅ 保留 |

> 核对要点 1：源文档 **§9→§11→§10→§12 章节编号跳跃**已全部保留（§9、§11、§10、§12 四个章节均在列，顺序与源文档一致）。
> 核对要点 2：源文档 §9.7 起未闭合代码围栏已修复（仅补一个 ``` 闭合标记，未改写内容行），因此 §10~§18 标题在本文档中为真实标题（而非源文档中的代码块文字）。

### Part II 覆盖证明（来源 RESEARCH_REPORT.md，共 9 个一级章节）

| 合并后章节 | 状态 |
|:---|:---:|
| `### 1. 项目背景与目标` | ✅ 保留 |
| `### 2. Cadence SPB 生态系统速查` | ✅ 保留 |
| `### 3. 现有开源方案调研` | ✅ 保留 |
| `### 4. 核心技术路径深度分析` | ✅ 保留 |
| `### 4.3 网络命名规范（来自 universal-netlist 分析标准）` | ✅ 保留 |
| `### 4.4 BOM 输出格式标准（来自公司实际文件）` | ✅ 保留 |
| `### 4.5 公司 HDL 器件库完整目录（131个器件类，口径：排除备份目录）` | ✅ 保留 |
| `### 6. 风险与难点评估` | ✅ 保留 |
| `### 7. 参考文献与资源` | ✅ 保留 |

> 核对要点：源文档重复编号 §4.3×2 与缺失 `## 5` 标题均已原样保留（§5.1/5.2/5.3 悬空小节在列）。

### Part III 覆盖证明（来源 REFERENCE_READING_NOTES.md，共 18 个文件精读条目）

| 条目 | 状态 |
|:---|:---:|
| 文件 #1 | ✅ 保留 |
| 文件 #2 | ✅ 保留 |
| 文件 #3 | ✅ 保留 |
| 文件 #4 | ✅ 保留 |
| 文件 #5 | ✅ 保留 |
| 文件 #6 | ✅ 保留 |
| 文件 #7 | ✅ 保留 |
| 文件 #8 | ✅ 保留 |
| 文件 #9 | ✅ 保留 |
| 文件 #10 | ✅ 保留 |
| 文件 #11 | ✅ 保留 |
| 文件 #12 | ✅ 保留 |
| 文件 #13 | ✅ 保留 |
| 文件 #14 | ✅ 保留 |
| 文件 #15 | ✅ 保留 |
| 文件 #16 | ✅ 保留 |
| 文件 #17 | ✅ 保留 |
| 文件 #18 | ✅ 保留 |

> 核对要点：**18 个文件笔记条目（文件 #1~#18）全部齐全**，无遗漏。

### Part IV 覆盖证明（来源 FILE_INDEX_AND_MAPPING.md，共 6 个一级章节）

| 合并后章节 | 状态 |
|:---|:---:|
| `### 参考库数据流总览` | ✅ 保留 |
| `### Part A: 完整文件清单表` | ✅ 保留 |
| `### Part B: 功能模块分组` | ✅ 保留 |
| `### Part C: 功能映射表` | ✅ 保留 |
| `### Part D: 阅读计划` | ✅ 保留 |
| `### 附录: 数据流关键数据结构对照` | ✅ 保留 |

> 核对要点：参考库数据流总览、Part A~D、附录（数据流关键数据结构对照）全部保留；内部 `Part A~D` 编号为源文档内部编号，原样保留。

### 全文计数口径核对（现行口径）

- **版本**：v1.1.0（全文以 v1.1.0 为现行版本表述）
- **错误码**：44（全文以 44 为现行错误码）
- **匹配**：v2.0 两阶段管道（Part II §4.2、Part III 文件 #1、Part IV A.2 补充 / B.2 补充 / Part C，均以 v2.0 为现行口径，源文档内"四级管道"描述均标注为历史口径）
- **DSN StructureType 实际枚举**：Page10 / PlacedInstance13 / T0x10=16 / WireScalar20 / WireBus21 / Port23 / LibraryPart24 / Package31 / Device32 / Global37 / OffPageConnector38 / SymbolDisplayProp39 / Alias49 / Junction50 / TitleBlock65（**无 11/26/27**）
- **hdl_lib 器件数**：**131**（排除备份目录；Part II §4.5、Part IV A.1/A.1.2）
- **standard/ 符号目录**：**88**（Part I §0）
- **writer 层**：含 csa / sch / cpm / cdslib / xcon / cpc / scr / mapping_csv / output_manager（Part IV A.2 补充 / B.2 补充）
- **无过时计数作为现行表述**：全文未将 135 / 91 / 124 等旧口径作为现行表述；源文档中出现的旧口径（如"~100""70+/130""17""124"）均已在源文档内加注说明或标注为历史口径。

---

> **合并保全声明结束** — 本文件由 4 份调研文档于 2026-08-07 内容保全式合并生成；源文档未做任何修改。


---

# Phase XI P0 连线格式研究补充（2026-08-10 追加）

> 本节由软件交付团队追加，记录 P0 实施中逆向确认的 Cadence DEHDL 关键格式研究结论。
> 全部结论经真实工程（8367/04p4/switch_practice/CIStoHDL_standard）实测验证。

## 1. CSA 连线命令（推翻 PAINT WIRE 错误认知）

| 命令 | 语法 | 用途 |
|------|------|------|
| WIRE | `WIRE 16 -1 (x1 y1)(x2 y2);` | 导线（16=黄色信号线，-1=线宽占位）；几何重合建立连接 |
| DOT | `DOT 1 (x y);` | 连接点（T 型/十字交叉处） |
| LASTPIN $PN | `FORCEPROP 2 LASTPIN (x y) $PN <n>` | 声明引脚位置+引脚号 |
| LASTPIN SIG_NAME | `FORCEPROP 2 LASTPIN (x y) SIG_NAME <net>` | 引脚网络名（电源网带 `\g`） |
| SIG_NAME（WIRE 上） | `FORCEPROP 2 LAST SIG_NAME <net>` | 网络名标签（每网一个，WIRE 中点） |

**关键机制**：DEHDL 靠**几何重合**判定连接——WIRE 端点必须与 LASTPIN 引脚坐标精确重合，网络名通过 SIG_NAME 附着。没有独立的"网络标号命令"（TEXT/LABEL/ALIAS 在真实 csa 中 grep 为 0）。

## 2. 引脚坐标权威来源 = symbol.css C 指令

`C x y "pinname"` 给出引脚相对体中心偏移。实测验证（8367 page1.csa 对拍）：
- capacitor：pin1 (0,-75)、pin2 (0,+50)
- gnd_power：(0,+50)；vcc_circle：(0,-50)
- dc_dc（多引脚 IC）：各引脚在 ±200 矩形成周边

**规则**：LASTPIN 坐标 = 实例体坐标 + symbol.css C 指令偏移。

## 3. con 格式（Cadence S-Expr）

- cells：`("S1" "cell" "hdl_lib" "sym_N" (terms ("T1" "pin" -1 -1 dir)))`，dir: 1=input/2=output/3=inout
- nets：`("N1" "name" -1 -1 scope)`，scope: 2=全局(\g)/0=局部(pageN_ 前缀)
- instances：`("I1" "pageN_iK" "S1" (pins ("M1" "T3" -1 -1 (conn ("0" -1 -1 "N7" -1 -1)))))`
- lastIds：从 1 连续编号时 = 计数
- 电源符号 gnd_power/vcc_circle **不进** con cells/instances

## 4. pageN.csv（页级连通性）

- 网络编号清单：`0"NC";` + 页内连续编号（与 con 设计级编号不同，靠裸名桥接）
- 实例块：`%"CELL"` + `"sym_N","(x,y)","0","hdl_lib","I<k>";` + `;` + 属性 + `$PN"<pin>"<netId>;`
- 单引脚器件（电源）：直接 `"GND"<netId>;`（无 $PN）
- `END.` 结尾

## 5. EDIF 坐标单位（P0-C 坐标换算）

- EDIF pt = 0.254mm = 10 mil（pageSize 1654×1169pt = A3 420×297mm 完全吻合）
- 但与 CSA 绝对坐标（C 纸 -10750..0 × 0..8275）无固定换算
- **策略"自洽"**：LASTPIN == WIRE 端点（几何重合），不还原 Capture 原坐标

## 6. 数据源判定（P0-D2）

| 数据源 | 结论 |
|--------|------|
| DSN（RTL 变体） | ❌ 负资产：实例=0、wire 16 段垃圾、3717 假网络（误解析） |
| EDIF | ✅ 24 页/3023 实例/862 nets/2516 wires/522 off_pages |
| pstxnet.dat | ✅ 权威网络（590 nets/2821 连接），Stage 5.5b 主注入 |
| CrossRef CSV | ✅ 权威 BOM（889 refdes） |

## 7. 拓扑合成算法（wire_layout）

水平主干 + 垂直支线；端点与 LASTPIN 重合；主干 y 取引脚众数/中值对齐 25 网格；避开器件体；DOT ≥2 段交点（保守策略无害）；每网一个 SIG_NAME 标签。

---

# Phase XVII A* 迷宫布线开源方案深度调研（2026-08-12 追加）

> 软件交付团队追加。目的：深度调查"A* 相关美化布线开源代码方案"，寻找可辅助实现
> 连接点合并、走线化简、电线避让、GND 聚类的现成函数/算法。
> 方法：curl 抓取并核实实际源码（非 README 转述）——SKiDL route.py(3236行)/place.py(2094行)、
> OpenRAM compiler/router/*（BSD-3）、KiCad eeschema sch_line_wire_bus_tool.cpp(1505行)+sch_rtree.h。
> 详细版：`docs/archive/temp files/phase17-research-a-star-routing.md`。

## 1. 调研总览表

| 方案 | 仓库URL | 关键文件 | 关键函数 | 许可 | 代码量 |
|---|---|---|---|---|---|
| SKiDL | github.com/devbisme/skidl | `src/skidl/schematics/route.py`、`place.py` | `Router.route/global_router/cleanup_wires/add_junctions`、`Placer.place/evolve_placement` | MIT | route 3236 行 / place 2094 行 |
| OpenRAM | github.com/VLSIDA/OpenRAM | `compiler/router/{router,graph,graph_node,supply_router,router_tech}.py` | `graph.create_graph/find_shortest_path`、`graph_node.get_edge_cost`、`router.inflate_shape/prepare_path` | BSD-3 | ~1400 行 |
| FGR/FastGR | 学术二进制无源码；替代 tscircuit/capacity-autorouter | `lib/solvers/{CapacityMeshSolver,MultiAstarIntraNodeSolver}.ts` | `AutoroutingPipelineSolver.step` | MIT(tscircuit) | TS 全工程 |
| KiCad Eeschema | gitlab.com/kicad/code/kicad | `eeschema/tools/sch_line_wire_bus_tool.cpp`、`sch_rtree.h` | `simplifyWireList/TrimOverLappingWires/AddJunctionsIfNeeded/SchematicCleanUp`、`EE_RTREE.Overlapping` | GPL-3（抄算法） | 1505 行 |
| Channel Routing | cs.baylor.edu/~maurer/routing.pdf | trunk/branch/left-edge | — | 公开教程 | — |
| shapely/networkx/sklearn | pypi | `LineString.intersects`、`shortest_path`、`KMeans` | BSD/MIT | 零开发 |

## 2. 核心发现（函数级）

### 2.1 SKiDL cleanup_wires —— 本项目"电线化简"的现成解法（MIT 可直接移植）
`Router.route()`(route.py L3109) 流水线：`add_routing_points`(L2015 引脚→bbox 边缘 stub) → `create_routing_tracks`(L2059 非均匀 H/V 轨道=switchbox 网格) → `global_router`(L2190 Dijkstra 迷宫，face.capacity<=0 障碍，rank_net L2314 短网先布) → `switchbox_router`(L2412 Greedy Switchbox 列优先) → **`cleanup_wires`(L2441) 美化后处理** → `add_junctions`(L3054 T/X 交点)。

**cleanup_wires 内部 7 子函数（对标本项目需求）**：
- `split_segments`(L2462)：线段按交点/引脚点切最小区间
- `merge_segments`(L2516)：**共线重叠合并**（同 Y 水平/同 X 垂直段排序后 merge 重叠区间）← 直接削减"电线数量爆炸"
- `break_cycles`(L2568)：邻接图断环
- `trim_stubs`(L2621)：删除连不到引脚的悬空 stub ← 修复"凸出又折回"
- `remove_jogs`(L2816)：3 段阶梯 jog → 2 段直角，`obstructed()`(L2827) 检查撞元件 bbox/平行段

### 2.2 OpenRAM —— A* 代价函数模板（BSD-3 可抄）
- `graph.create_graph`(graph.py L187)：**Hanan 网格**（障碍物角点+引脚安全点笛卡尔坐标，节点量远小于均匀网格）；`inflate_shape`(router.py L217) 障碍物膨胀
- `graph_node.get_edge_cost`(graph_node.py L60)：**代价 = 线长；非首选方向 ×4；拐角加 drc["grid"] 防 dog-leg；via ×2** ← 本项目 A* 代价函数直接模板
- `router.prepare_path`(L254)：去除同向冗余点（路径化简）
- `supply_router.add_side_pin`(L100)：电源环均匀 fake pins 就近接入 ← GND 聚类思路

### 2.3 KiCad —— 画后清理算法（GPL 只能抄思路）
- `simplifyWireList`(L1208) + `TrimOverLappingWires`(L1349) + `AddJunctionsIfNeeded`(L1393) + `SchematicCleanUp`（删冗余 junction/合并重叠线/断 T 点）
- `EE_RTREE`(sch_rtree.h)：R-tree 空间索引 `Overlapping(rect)` ← 重叠检测数据结构思路
- 局限：Eeschema 无稳定 Python API，验证仍需 Cadence 实测

### 2.4 学术 Channel Routing —— 本项目 trunk+stub 的理论原型
channel=矩形布线区，trunk=水平段连最左/右端子，branch=垂直接引脚，垂直约束图+left-edge 算法逐 track 分配。**本项目的 `_find_lane` 车道法本质就是 channel router**；04p4 参考工程"短段分层"风格是 left-edge 分配天然产物。

## 3. 与本项目结合度评估

| 方案 | 贴合度 | 可借鉴 | 实现量 |
|------|:---:|------|:---:|
| **SKiDL cleanup_wires** | **高** | merge_segments/trim_stubs/remove_jogs/break_cycles/add_junctions | 300-500 行（MIT 直接移植） |
| SKiDL global_router | 中 | create_routing_tracks/rank_net/face.capacity | 400-600 行（远期） |
| OpenRAM graph.py | 中 | get_edge_cost/Hanan 网格/is_probe_blocked/prepare_path | A* 骨架 500-800 行 |
| OpenRAM supply_router | 中 | add_side_pin 环+fake pins（GND 就近共用） | 100-150 行 |
| KiCad | 中 | SchematicCleanUp/MergeOverlap/EE_RTREE | 200-300 行（抄思路） |
| shapely/networkx | 高（工具） | LineString.intersects/Polygon | 零开发 |
| sklearn KMeans | 高（工具） | GND 引脚聚类→按簇共用 trunk | 100 行内 |

## 4. 明确推荐（对应 4 个核心问题）

1. **连接点合并/电线化简** → 移植 SKiDL `cleanup_wires` 四件套（merge_segments 共线合并 + trim_stubs 删悬空 + remove_jogs 拐角化简 + break_cycles 断环）。只合并同网段、端点引脚坐标不动（DEHDL 几何重合硬约束）。**最高优先**，比 A* 便宜得多。
2. **多端点网共用 trunk/总线** → `_find_lane` 车道法已是 trunk 思想；增强参考 SKiDL `create_routing_tracks`（bbox 边延伸成轨道）+ left-edge 逐 track；低成本替代=中位 trunk 共线共享。
3. **电线避让元件/自重叠** → 二选一：OpenRAM 网格占用法（inflate_shape+is_node_blocked）或 **shapely 法**（推荐，零新增算法）：`LineString.intersects(Polygon)` + SKiDL `obstructed` 平行段检测。
4. **GND 合并/就近共用** → OpenRAM `add_side_pin`"环+均匀 fake pins" + sklearn KMeans 对 GND 引脚聚类，每簇取 trunk。约 100 行。

**总体建议**：不要全量 A*（对固定布局是过度设计，与 P0 车道法重复）；**最高价值 = 移植 SKiDL cleanup_wires 做"连接点合并+共线化简+stub 修剪"后处理**；避让用 shapely 增强；GND 聚类用 KMeans+OpenRAM 环思路。若未来做自动布局，A* 迷宫按 OpenRAM `get_edge_cost` 公式（线长+拐角+drc["grid"]）实现。

## 5. 参考链接

- SKiDL: github.com/devbisme/skidl（MIT）；API devbisme.github.io/skidl/api/html/rst_output/skidl.schematics.route.html
- OpenRAM: github.com/VLSIDA/OpenRAM（BSD-3）；deepwiki.com/ferdous313/OpenRAM_2017/4.1-a*-maze-router
- tscircuit: github.com/tscircuit/capacity-autorouter（MIT）
- KiCad: gitlab.com/kicad/code/kicad（sch_line_wire_bus_tool.cpp；sch_rtree.h；bus-wire-junction.cpp）；docs.kicad.org/doxygen/classEE__RTREE.html
- Channel Routing: cs.baylor.edu/~maurer/routing.pdf
- FastGR: cse.cuhk.edu.hk/~byu/papers/C138-DATE2022-FastGR.pdf；FGR: IEEE TCAD 2008
- Python: shapely（BSD-3）、networkx、rectpack、scikit-learn KMeans
- Greedy Switchbox Router 论文: doi.org/10.1016/0167-9260(85)90029-X

---

# Phase XVII 追加：SKiDL 完整流水线深度解剖 —— 从"摆放元件"到"绘制走线"（2026-08-12 第二轮）

> 本轮深入 SKiDL `place.py`(2094 行) + `route.py`(3236 行) 实际源码（curl 抓取 raw.githubusercontent.com 核实），
> 完整梳理"元件摆放 → 走线绘制"全链路，探讨对本项目（固定布局 + 生成连线）的可借鉴点。
> 详细版：`docs/archive/temp files/phase17-research-a-star-routing.md` 追加部分。

## 1. place.py 摆放流水线（关键可借鉴点）

| 函数 | 行号 | 核心算法 | 本项目借鉴 |
|------|------|----------|-----------|
| `add_placement_bboxes` | L123 | **符号 bbox + 四侧按引脚数扩展的布线通道**（每引脚 1 通道×GRID）；`expansion_factor` 布线失败整体放大 | ★★★ 重叠检测改用"摆放包围盒"（符号 bbox+通道），margin=GRID；腾挪用 expansion_factor 重放 |
| `add_anchor_pull_pins` | L164 | 引脚沿方向投影到 bbox 边缘作锚点；他件同网引脚作拉点；网质心 pin_ctrs | ★★ 引脚投影点思想供 M6 pin_connect_audit |
| `push_and_pull` | L985 | **alpha 调度表**：`(0.5,α=0 全吸引)→(0.25,0.4)→(0.25,0.8)→(0.25,1.0 全排斥)`；net_normalize 防大件飞走；pt_to_pt_mult 点对点网拉近；rmv_drift 防整组漂移 | ★★★ M3 腾挪：锚定芯片，GND/标签做 α 渐进推开（先吸引后排斥） |
| `place_connected_parts_rowbased` | L1348 | 大组（>20 件）BFS 行式排版 O(n)：种子=连接最多件 → BFS 顺序 → `max_row_width=sqrt(area)*2` → 逐行放 + BLK_INT_PAD | ★★ 局部重排（page8 并联电容 C399 等） |
| `place_net_terminals` | L1139 | **NetTerminal 绕已放置块 bbox 边缘分布 + 只连最近拉点**（trim_pull_pins/orient/move_to_pull_pin） | ★★★ GND/电源符号分布：就近共用（用户问题 4/7/14） |

## 2. route.py 布线流水线（关键可借鉴点）

| 函数 | 行号 | 核心算法 | 本项目借鉴 |
|------|------|----------|-----------|
| `add_routing_points` | L2015 | 引脚沿方向延伸恰好 1 格 GRID 到符号边缘 → stub 起点 | ★★ stub 引出段 = GRID 整数倍（问题 15） |
| `create_routing_tracks` | L2059 | **元件 lbl_bbox 四边坐标去重 → 非均匀 H/V 轨道**；Face 拆分/合并/邻接 | ★★ trunk 车道改"元件 bbox 边坐标"优先（问题 13 对齐） |
| `global_router` | L2190 | Face 级 Dijkstra 迷宫（非严格 A*）；`rank_net` = **短网先布**（bbox 周长+引脚数）；`capacity<=0` 即障碍；多引脚网生成树式生长（随机起点连到已连集合） | ★★ 布线顺序与现相反（短网先布）做 A/B；轨道段容量上限防叠线（问题 2） |
| `switchbox_router` | L2412 | Greedy Switchbox 列优先 + TARGET 引导；**失败 `flip_xy()` 转置重试** | ★ detour 两级降级链（转置→回退 P0） |
| `cleanup_wires` | L2441 | split → **merge_segments**（同 Y/X 共线贪心合并）→ break_cycles → **trim_stubs** → **remove_jogs**（`obstructed` 用 `bbox.resize(Vector(2,2))` 边-边检测） | ★★★ M4 wire_simplifier 移植（最高优先，MIT） |
| `add_junctions` | L3054 | **仅"T 型/十字"真交点放 junction，排除直角端点相接**；前提先 merge_segments | ★★ 问题 12 连接点合并：DOT 只放真 T/X 交点 |

## 3. 关键洞察（与现有实现对比）

1. **`rank_net` 短网先布 vs 本项目长网先布**：SKiDL 短网先布（短网先占车道不易被挤断）；本项目 `route_nets` 长网优先——值得 A/B 对比。
2. **DOT 语义**：本项目 `compute_dots` "每交点一个 DOT"（用户抱怨过多）；SKiDL 仅真 T/X 交点放 junction，直角拐弯不放——需改。
3. **stub 引出**：SKiDL 固定延伸 1 格 GRID；本项目 `stub_lead=100`（4 格）——可对齐 GRID 整数倍。
4. **GND 分布**：SKiDL NetTerminal"绕块边缘+最近拉点"正是"就近共用 GND"的现成模式。

## 4. 落地优先级

1. **P0**：移植 `cleanup_wires`（merge_segments/trim_stubs/remove_jogs/add_junctions）→ `wire_simplifier.py`（MIT 许可，算法已核实）
2. **P1**：`add_placement_bboxes` 思想重构统一碰撞函数 M2（margin=GRID）；GND 改"绕块边缘+就近接入"
3. **P1/P2**：`create_routing_tracks` 非均匀轨道增强 `_find_lane`；`rank_net` 短网先布 A/B
4. **远期**：力导布局（`push_and_pull` α 调度 + rowbased）仅用于 `--aesthetic-placement`；A* 迷宫留自动布局场景

---

# Phase XVII 实现反馈：SKiDL 研究落地验证（2026-08-12 追加）

> 软件交付团队。SKiDL cleanup_wires 移植（M4 wire_simplifier）与配置修复已实现，记录研究结论的实测验证。

## 1. cleanup_wires 移植实测（M4 wire_simplifier）

- `merge_segments`（共线合并）：SKiDL route.py L2516 算法移植——按 Y（水平）/X（垂直）分组、按起点排序、贪心合并重叠/相邻区间。QA 19 项独立检查全 PASS（重叠/相邻/子集/反向规范化）。
- `trim_stubs`（删悬空段）：T 型锚定保留、无锚全删——验证正确。
- `remove_jogs`（拐角化简）：3 段阶梯 H-V-H → 2 段直角，障碍阻挡时保留原路径——正确。
- `add_junctions`（仅 T/X 真交点）：直角端点相接排除（SKiDL add_junctions L3054 语义）——正确。
- **HG5015 实测**：wire_simplify 开启 WIRE 5031→3424（**-32%**）——直接削减"电线爆炸"。

## 2. golden 格式裁决修正（重要）

**04p4 page9.csa 实读**：SIG_NAME LASTPIN 块（FORCEPROP 2/3）**本就带 `PAINT MONO + DISPLAY INVISIBLE`**（L12 GND_POWER / L365 CAPACITOR）；无 PAINT 的是 $PN 块（L63-71）。此前"PAINT 是 SPCOCN-543 根因"的判断系误读（把 $PN 块当 SIG_NAME 块）。**SPCOCN-543 真实根因 = 坐标未命中 symbol.css + 旋转组合**，由方案 B/C/D 处理。SIG_NAME PAINT 恢复为 golden 一致。

## 3. Config.load_from_file 隐藏 bug（附带发现）

此前 `load_from_file` 只处理 page/routing 两节，text_layout/overlap/power_ic/aesthetic/report/placeholder/ioport/mirror/gnd_distribution 等 12 个顶层子节全部静默失效（默认值与 dataclass 默认恰好相同而掩盖）。已修复：合并全部顶层子节进 RoutingConfig。20 项加载断言验证全 PASS。

## 4. 研究结论落地对照

| 研究结论 | 落地 | 实测 |
|---------|:---:|------|
| SKiDL cleanup_wires 四件套（最高优先） | ✅ M4 wire_simplifier | WIRE -32% |
| add_placement_bboxes 思想（margin=GRID） | ✅ M2 detect_collisions(margin=25) | 统一函数 |
| place_net_terminals（GND 就近） | ✅ M3 腾挪（只移 GND/标签） | 芯片不动（D10） |
| rank_net 短网先布 | ⬜ P1/P2 待 A/B | — |
| create_routing_tracks 非均匀轨道 | ⬜ P1/P2 待实现 | — |
| A* 迷宫（get_edge_cost） | ⬜ 远期 | 自动布局场景 |

---

# Phase XVII 二期实现反馈：非均匀轨道 + 短网先布（2026-08-12 追加）

> SKiDL create_routing_tracks（非均匀轨道）与 rank_net（短网先布）研究结论落地。

## 1. create_routing_tracks → _collect_tracks（落地）

- SKiDL（route.py L2059）：元件 lbl_bbox 四边坐标去重 → 非均匀 H/V 轨道
- 本项目（wire_layout.py L444）：outline bbox 边坐标（H=min_y/max_y、V=min_x/max_x）→ 轨道候选
- `_find_lane` 增强：轨道优先（距中位 trunk 距离升序 ±50 试位）→ 回退均匀车道
- 实测：page5 trunk v1(2775/4100) vs v3(2850/4075)——轨道吸到元件边坐标

## 2. rank_net → _net_priority_key（落地）

- SKiDL（route.py L2314）：bbox 周长+引脚数升序（短网先布）
- 本项目（wire_layout.py L55）：long_first 返回 (span,len)+reverse（现状）；short_first 负号键等效升序
- 实测：短网先布首条 key=-525（小网）、长网先布首条 key=13600（GND 大网）
- **关键观察**：排序改变路径不改变总段数（5031 vs 5034）——美观差异需 Cadence 目视确认

## 3. 研究结论落地对照（二期）

| 研究结论 | 落地 | 实测 |
|---------|:---:|------|
| create_routing_tracks 非均匀轨道 | ✅ _collect_tracks + _find_lane 轨道优先 | v3 WIRE=5089（对齐性提升） |
| rank_net 短网先布 | ✅ _net_priority_key 负号键 + --net-order | v2 WIRE=5034（路径变化） |
| 力导布局（push_and_pull） | ⬜ 远期（--aesthetic-placement） | — |
| A* 迷宫（get_edge_cost） | ⬜ 远期（自动布局场景） | — |

---

# Phase XVII 三期实现反馈：GND 聚类落地（2026-08-12 追加）

> OpenRAM supply_router.add_side_pin（GND 就近共用）研究结论落地。

## GND 聚类（用户问题 4"就近七八个元件共用一个 GND"）

- **算法**：芯片 GND 引脚分组 → 贪心最近邻聚类（曼哈顿距离 ≤ cluster_radius=2000 聚簇）→ 每簇 1 个共享 GND
- **实现**：`_plan_and_inject_gnd_symbols`(csa_writer.py L1943)
- **实测**：v8（--gnd-distribute）全工程 GND 19→97、page5 1→6；电气不变（SIG_NAME GND\g 全局连接）
- **对比**：OpenRAM add_side_pin 用"环+均匀 fake pins"，本项目用"贪心最近邻簇"（引脚数少，O(n²) 足够）——同样实现"就近接入"

## 化简收益与布线模式强相关（重要教训）

| 对比 | WIRE | 收益 |
|------|:---:|:---:|
| v1 p0（基线） | 5031 | — |
| v7 p0+simplify | 3424 | **-32%**（同基线） |
| 纯 detour | 12088 | — |
| v5 detour+simplify | 6764 | -44%（相对纯 detour） |

**结论**：对比化简收益必须同布线模式；v5 绝对数高于 v1 是 detour stub 引出段所致，非功能问题。
