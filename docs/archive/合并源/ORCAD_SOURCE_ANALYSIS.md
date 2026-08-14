# OrCAD SPB 16.6 源文件深度分析报告

> 版本: v1.0 | 日期: 2026-07-30 | 基于对 28,205 个 Cadence 安装文件的深度分析
>
> 修订: v1.0.1 | 日期: 2026-08-07 | 计数修正（standard/ 91→88、cis_for_reference/hdl_lib 124→123）；CTW 模板数量加注（以 6.3 节表格为准）；§10/§11 章节编号跳跃加注（内容不受影响）

---

## 0. 分析概要

| 指标 | 数值 |
|------|:---:|
| 分析文件总数 | 28,205 |
| 关键代码/配置文件 | ~500 |
| 分析耗时 | ~45 分钟（5 个并行 Agent + 直接读取） |

### 关键目录与研究成果

| 目录 | 内容 | 项目价值 |
|------|------|:---:|
| `capDB/` | DSN/OLB XSD Schema + Cadence TCL API | ⭐⭐⭐⭐⭐ |
| `standard/` | HDL 标准符号库 (88 个符号目录) | ⭐⭐⭐⭐⭐ |
| `cdssetup/ctw/devices/` | 器件模板定义 (PIN_ALIAS 映射) | ⭐⭐⭐⭐⭐ |
| `cdssetup/template.bom` | BOM 模板格式 | ⭐⭐⭐⭐ |
| `capture/tclscripts/capDB/` | DSN/OLB 操作 TCL 脚本 | ⭐⭐⭐⭐ |
| `capture/netforms/` | 网表格式化器 DLL 列表 | ⭐⭐⭐ |

---

## 1. DSN/OLB 二进制格式 — 官方 XSD 验证

### 1.1 PartInst 元素（DSN XSD, 行 1865-1965）

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

### 1.2 Package 元素（OLB XSD, 行 2698-2798）

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

### 1.3 TCL API 验证

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

## 2. HDL 文件格式 — 完整定义

### 2.1 symbol.css 格式

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

### 2.2 chips.prt 格式

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

### 2.3 pinlist.txt 格式（Lisp-like）

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

### 2.4 metadata/ 目录结构

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

### 2.5 cds.lib 格式

```
DEFINE standard ../library/standard
SOFTINCLUDE ../library/vlog_cds.lib
SOFTINCLUDE $CHDL_LIB_INST_DIR/share/library/cds.lib
```

---

## 3. 器件模板系统（Component Template Wizard）

### 3.1 器件定义文件（cdssetup/ctw/devices/）

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

### 3.2 PIN_ALIAS 映射规则

```python
# 电阻引脚别名
PIN_ALIAS '1' = '1', 'A', 'A<0>', 'A<SIZE-1..0>'
#           物理 逻辑  标量  总线低位  总线范围
```

### 3.3 BOM 模板（cdssetup/ctw/templates/）

10 个模板文件：
```
bulkcapsleft/right.txt           — 批量电容布置（左/右）
bypassinstcapsleft/right.txt     — 旁路电容（实例级）
bypasspincapsleft/right.txt      — 旁路电容（引脚级）
dpseries.txt                     — 差分对串联
```



## 4. template.bom 格式

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

## 5. CIS 网表格式化器 DLL 列表

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

## 6. 对 cis2hdl 项目的关键启示

### 6.1 Binary DSN Parser 验证 ✅

XSD 官方 Schema 完全验证了我们的 StructureParser 理解：
- PartInst.locX/Y = PlacedInstance.locX/Y
- PartInstDisplayProp = SymbolDisplayProp
- PartInstUserProp = prefixProperties (Value, MPN, PCB Footprint)
- Package.refdesPrefix = 位号前缀

### 6.2 HDL 格式生成得到官方参考 ✅

- symbol.css 格式已完全掌握（C/L/A/T/P 指令）
- chips.prt 格式清晰
- pinlist.txt (Lisp-like) 确认
- metadata/ 目录结构可用

### 6.3 器件模板可用 ✅

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

### 6.4 BOM 生成可用 ✅

template.bom 格式已确认，可作为 HDL 输出的一部分。

---

## 7. 关键文件位置速查

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

## 8. CIS 标准库结构（新增 — Explore-4 Agent 分析）

### 8.1 library/ 主库（30+ .olb）

| 类别 | 文件 | 大小 | 对项目意义 |
|------|------|:--:|-----------|
| 放大器 | Amplifier.olb | 555K | OLB 器件符号参考 |
| 运算放大器 | OPAmp.olb | 1.2M | 多引脚器件参考 |
| 离散器件 | Discrete.olb | 2.8M | 电阻/电容/电感符号 |
| 连接器 | Connector.olb | 5.6M | 接插件符号参考 |
| 微控制器 | MicroController.olb | 3.3M | IC 符号参考（最高复杂度） |

### 8.2 netforms/ — 网表格式化器 DLL（40+ 格式支持）

关键 DLL：
- `orEdif.dll` — EDIF 格式（我们 Phase I-A 所用格式的官方导出器）
- `orTelesis.dll` — Allegro 原生网表
- `orpads2k.dll` — PADS 2000

### 8.3 allegro.cfg — **网表属性传递核心配置**

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

### 8.4 CAP2EDI.CFG + EDI2CAP.CFG — 双向 EDIF 转换配置

文件路径：`capture/CAP2EDI.CFG`, `capture/EDI2CAP.CFG`

### 8.5 macros/ + skill/ — 自动化能力

- VBA 宏：buscnct.bas（总线连接）、custprop.bas（自定义属性）、Titleblock.bas（标题栏）
- SKILL 接口：`capture/skill/orCapSxIf.il` — OrCAD↔Allegro SKILL 桥接

---

## 9. 第二轮深度挖掘

### 9.1 CAP2EDI.CFG — EDIF 导出配置

```ini
[OrCAD Reader]
MultipleLibraries = 1    # 多库模式
ConvertAll = 0
UniquePins = 0
PackagePinNumbersToDesignator = 0
OutputBackAnnotation = 0
```

### 9.2 EDI2CAP.CFG — EDIF 导入配置

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

### 9.3 VBA 宏 — 坐标系统与布局算法

#### buscnct.bas — 总线连接（核心坐标参考）
- 坐标系：十进制英寸 (0.4, 0.1, -0.5)
- 总线间距：`BitYOffset = 0.1 + (Spacing/10)`
- 8 种方向组合
- `PlaceWire(0,0,WendX,WendY)`, `PlaceNetAlias(x,y,name)`, `PlaceBusEntry(x,y,rotate)`, `GoToRelative(dx,dy)`

#### PortIn.bas — 端口放置
- `PlacePort(x,y,"CAPSYM.OLB","PORTRIGHT-R",PortName)`
- 标签偏移：`Offset = 0.95 - (NameLength/20)`

### 9.4 CTW 器件模板 — 21 个完整定义（详见第 5 节更新）

### 9.5 CTW 电路模板 DSL — HDL 生成语言

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

### 9.6 Canvas DRC — 重叠检测

```tcl
proc asda_inst_overlap {designName msgType} {
    # sch::dbGetPageItems → asda_filter asda_isInst → sch::dbGetBBox
    # → asda_checkbbox_intersection 两两比对
}
```

### 9.7 template.bom — 完整 BOM 模板

```
内置属性：BOM_PART, BOM_INST, BOM_QUANTITY, BOM_ITEM_NUM
列：WIDTH, TITLE, JUSTIFICATION, PROPERTY, TOTAL, SUBTOTAL, QUOTE
位号压缩：INST_RANGE=TRUE, RANGE_MIN=3
过滤：PROP="BOM_IGNORE" "TRUE" | PROP="VAR" "1"

---

## 11. XSD 全量解析 + ISCF 导出 + DRC 体系（Explore-2 完整报告）

### 11.1 DSN 全量元素表

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

### 11.2 坐标系统确认

- 所有坐标使用 **xs:long** (整数)
- 字体系统：escapement, height, italic(0/1), name, orientation, weight, width
- 页面参数：ANSIGridRefs, BorderDisplayed, GridRefDisplayed, HorizontalLabelCount/Width, IsMetric, PinToPin, PageSize(A/B/C/D/E/Custom)

### 11.3 ISCF — Cadence 内部交换格式（Explore-2 首曝）

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

### 11.4 DRC 规则体系（7种）

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

## 10. TCL 脚本体系全析（Explore-8 Agent 完整报告）<!-- 注：章节编号待整理，内容不受影响（§10 位于 §11 之后，为原始编号跳跃所致） -->

### 10.1 属性显示系统（Property Display Types）

OrCAD 定义了 **5 种属性显示类型**：

| 类型 | 代码 | 含义 | HDL 生成对应 |
|------|:--:|------|-------------|
| Do Not Display | 0 | 不显示 | 不写入 symbol.css |
| Value Only | 1 | 仅显示值（如 "10K"） | `P "KEY" "VALUE"` 单属性行 |
| Name and Value | 2 | 显示名和值（如 "Value=10K"） | 需要两行或拼接 |
| Name Only | 3 | 仅显示名称 | `P "KEY" ""` |
| Both If Value Exists | 4 | 有值时显示名和值 | 条件式生成 |

### 10.2 坐标系统与几何操作

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

### 10.3 DBO 数据库对象层次

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

### 10.4 通用迭代器 API 模式

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

### 10.5 Canvas 系统（Design Entry HDL）

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

### 10.6 CDS 属性系统（全量属性列表）

**电气属性**：ALLOW_CONNECT, BIDIRECTIONAL, DIR, DELAY, RISE, FALL, INPUT_LOAD, OUTPUT_LOAD, IO_NET, NO_IO_CHECK, NO_LOAD_CHECK

**物理属性**：LOCATION, LOCATION_CLASS, XY, ROT, SEC, has fixed size

**设计属性**：MODEL, PART_NUMBER, PHYS_DES_PREFIX, VALUE, VER, GROUP, ROOM

**仿真属性**：CHIP_DELAY, CLOCK_DELAY, WIRE_DELAY, EVAL, PDELAY, PFALL, PRISE, TIMING_ASSERTION

**配置属性**：AUTO_GEN, LAST_MODIFIED, SCOPE, TERMINAL, NN, NEEDS_NO_SIZE, COMMENT_BODY

**继承规则**：`inherit(body/pin/signal)`, `permit(body/pin/signal)`, `filter`, `case_sensitive`, `parameter`

### 10.7 关键 TCL API 速查表

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

### 10.8 对 cis2hdl 的关键启示

1. **属性显示系统**定义了 5 种模式，HDL symbol.css 生成需支持这些模式
2. **坐标模型** (Point/BBox) 在 TCL 层和 C++ 层之间的转换通过 DboGeom 桥接
3. **Canvas 系统**的 widget 目录表明 HDL 编辑器是完整的 IDE，不仅仅是画布
4. **CDS 属性系统**定义了 HDL 设计中所有可用的属性及其继承规则
5. **迭代器 API 模式**统一了所有对象遍历，Binary DSN Parser 的 component-builder 本质上在复制这套模式
6. **Canvas 错误码**体系可帮助验证 HDL 生成输出的完整性

---

## 12. EDIF 格式深度分析 + 全部配置文件（Explore-12 完整报告）

### 12.1 EDIF 样本分析 — 5个完整 .edf 文件（Actel/Altera/Xilinx + 纯VHDL）

| 文件 | 厂商 | 关键特征 |
|------|------|---------|
| Actel/SampleD/a8bitbcd.edf | Actel | outbuf/inbuf/dfc1原语，member索引MSB=3 |
| Altera/SampleE/a8bitbcd.edf | Altera | S_DFF/SOFT原语，rename重映射 |
| Xilinx/SampleC/a8bitbcd.edf | Xilinx | RLOC/HU_SET/loc约束，FPGA布局坐标 |
| Board/dff_sync_sr.edf | Xilinx 4000 | EQN布尔表达式原语，GND/VCC |
| pure_vhdl/counter_mux_top_level.edf | Xilinx Virtex | LUT INIT属性，MUXCY_L/XORCY进位链 |

### 12.2 EDIF 格式结论

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

### 12.3 全部 10 个配置文件清单

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

### 12.4 cap2edi.log 运行日志（我们的实际转换）

```
工具: OrCAD CAP2EDI SPB 16.60_1.089
日期: 2026-07-30
源文件: RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN
目标: RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.EDF
处理的页面: 05_LED, 04_MDI, 03_RTL8367RB, 02_Power, 01_Block_Diagram
结果: 0 errors, 0 warnings ✅
```

### 12.5 EDIF 对 cis2hdl 的关键启示

1. **EDIF 可用于 Phase I-A 快速逻辑验证**（已验证 0 error 转换）
2. **EDIF 的 `rename` 语法直接对应 HDL 的网络名映射**
3. **EDIF 的 `(array (rename ...))` 语法对应 HDL 的总线定义**
4. **EDIF 不包含坐标 → Binary DSN 是坐标的唯一来源**

---

## 13. GUI 渲染与坐标系统全析（Explore-13 完整报告）

### 13.1 Cadence 多坐标系总表

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

### 13.2 坐标约定：Y轴向上

TCL 和 JavaScript 层均使用**左上角坐标系统**（Y值向下递增），因此：
- `top < bottom` 值
- 左上角为 `(left, top)`，右下角为 `(right, bottom)`

### 13.3 空间索引 — 四叉树（orPrmQTree）

OrCAD 使用四叉树进行空间索引和碰撞检测：

```javascript
// 象限：NE(0), SE(1), SW(2), NW(3)
// 容差：selectionToleranceX=2, selectionToleranceY=2
// 最大深度：maxDepth=10

getShapesAt(point) → 点容差查询
getShapesIn(rect) → 矩形范围查询
orPrmRectIntersects(lhs, rhs) → AABB 交叉检测
```

### 13.4 引脚几何库（30+ 预定义形状）

`orPrmPinLib.js` 定义了所有标准引脚形状：
- **线条类**：busEntryR/L (10px), shortLine (10px), longLine (30px)
- **多边形类**：inPoly (填充三角形), clockPoly, io/out/inDrawnPinPoly
- **椭圆类**：shortEllipse (4x4), longEllipse (4x4), pwrEllipse (10x6)
- **复合引脚模板**：visPas, visIO, visIn, visOut, globalPower, zeroLeak, busEntry 等 30+ 种

**对 cis2hdl 启示**：这些引脚形状定义可直接用于 SCH 生成器中的符号创建。

### 13.5 ConceptHDL 符号模板（template.tsg）

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

### 13.6 Canvas 面板系统（92 个 .panel 文件）

**关键面板示例 — Symbol.panel（484行）**：
- 属性网格列：Name(80), Value(80), Visibility(10), Location(30), Text Height(40), Alignment(40), Rotation(40), Parameter(40), Color(70), X(40), Y(40)
- 文本网格列：Text(120), Location(40), Text Height(40), Alignment(40), Rotation(40), Color(70), X(40), Y(40)
- 符号轮廓：Left, Top, Right, Bottom（距原点距离）
- "Set Origin" 和 "Set Size" 按钮

**SymbolViewer.panel**：图形视口 10,10→5000,5000（支持大偏移）

### 13.7 Canvas 快捷键（48 个）

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

### 13.8 orPrmViewer 渲染配置

```javascript
CacheWidth: 4000, CacheHeight: 2000     // 渲染缓存
SymbolSizeScale: 1                        // 符号缩放
MinScale: 0.2, MaxScale: 4.0              // 缩放范围
InterSymbolGap: 50                        // 符号间距
WorkCanvasWidth: 1000, WorkCanvasHeight: 1000
```

### 13.9 FSP 引脚方向配置

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

### 13.10 完整 GUI Widget 布局图

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

## 14. PSpice/VHDL/Verilog 全析（Explore-14 完整报告）

### 14.1 PSpice 仿真模型（.lib 文件）

**模型层次**：
```
Capture 原理图 → .prp 参数映射 → .lib 器件模型 → PSpice 仿真引擎
```

**关键模型**：
- Butterworth 滤波器：`Fc=1 ord=1` 参数化，使用 `E ... LAPLACE` VCVS 拉普拉斯传递函数
- uA741 运放：5 引脚 (non-inv, inv, V+, V-, out)
- LM339 比较器：BJT 晶体管级建模 (q1-q5)
- D1N914 二极管：多温度模型 (IS, RS, N, TT, CJO, VJ)

### 14.2 FPGA 设计流程

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

### 14.3 TTL 库架构（TTL.VHD/HC.VHD/LS.VHD）

**建模模式**：
- 简单门：数据流 + AFTER 延迟（`AFTER 22 ns`）
- 时序器件：ORCAD_DFFPC 通用原语 + `GENERIC (trise_clk_q=>25 ns, tfall_clk_q=>40 ns)`
- 74HC 系列使用皮秒延迟（`AFTER 1500 ps`）

### 14.4 ORCOMP.VHD — 底层原语库

定义了 `orcad_prims` 包：orcad_nand2, orcad_dffc, orcad_dffp, orcad_dqff, orcad_jkffc, orcad_dlatch, orcad_itsb — 所有支持 GENERIC 延迟建模。

### 14.5 IEEE 1164 标准（ieee/ 目录）

```vhdl
TYPE std_ulogic IS ('U','X','0','1','Z','W','L','H','-');
SUBTYPE std_logic IS resolved std_ulogic;  -- resolution 函数
TYPE std_logic_vector IS ARRAY (NATURAL RANGE <>) OF std_logic;
```

12 个 VHDL 包：std_1164, std_arit, std_sign, std_unsi, std_misc, std_text, num_bit, numeric_, timing_b/p, prmtvs_b/p

### 14.6 VBA 宏系统

| 宏 | 快捷键 | API |
|------|:--:|------|
| BusConnection | Ctrl+B | PlaceWire, PlaceNetAlias, PlaceBusEntry, GoToRelative |
| PropAdd | Shift+P | SetProperty (5对属性) |
| PlaceBusEntryArray | Ctrl+R | For I=LSB to MSB 批量放置 |
| PortIn | Ctrl+F8 | PlacePort("CAPSYM.OLB","PORTRIGHT-R") |
| PortOut | Ctrl+F9 | PlacePort("CAPSYM.OLB","PORTLEFT-L") |
| TitlblockProps | Ctrl+F7 | SetProperty(Title/DocNum/RevCode/CageCode/PageNum/PageCount) |

### 14.7 PLDGATES.VHD — 可编程逻辑门

定义 AND2~AND16, NAND2~NAND16, OR2~OR16, NOR2~NOR16, XOR2~XOR16, XNOR2~XNOR16 — 全部 `AFTER 1 NS` 延迟。

---

## 15. TCL 基础设施全析（Explore-15 完整报告）

### 15.1 capinit.tcl — 主初始化

- `capGetTclTkHome` → 查找外部 Tcl/Tk
- `capLoadTk` → 加载 tk84.dll
- `capTclTkInitialize` → 添加路径到 auto_path

### 15.2 capAutoLoad — 自动加载注册表（18 个初始化文件）

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

### 15.3 属性系统三层架构

| 层 | 文件 | 内容 |
|:--:|------|------|
| 基础层 | **cdsprop.txt** | 60+ 属性定义（inherit/permit/filter/case_sensitive/parameter） |
| HDL 中心层 | **cdsprop.paf** | 属性属性文件（uppercasevalue, preservename 指示符） |
| Concept UI 层 | **property.dat** | 属性<->UI 控件映射（COMP/WIRE/PIN 所有权，locked/hidden 状态） |

附加：**propflow.txt** — 200+ 属性流转定义（CONCEPT→ALLEGRO→WINNING_VALUE），**properrors.txt** — 101-127 错误码

### 15.4 包依赖图

```
capInit → capAutoLoad/* → capUtils/capForms/capDB/capDRC
         → orFlow (Altium→Capture)
         → orPrm* (WebComp/CGI/Designer/Streamer)
         → cdnTclEncrypted (加密 .tle)
         → capStartPage (EMA Web 仪表板)
```

### 15.5 creferhdl — HDL 页面网格定义

`creferhdl/cref.dat` 定义了所有标准页面的网格和标志：
- A 尺寸: 左下(-3750,0) 右上(0,5000), x 标记在 -500,-1500,-2500,-3425
- A~F 标准尺寸 + Cadence 品牌变体 + Valid 变体
- OFFPAGE/端口/自定义标志符号配置

### 15.6 capTCLMenu.tcl — 菜单作用域（2000+ 行）

根据当前视图切换菜单项：项目管理器/零件编辑器/原理图/属性编辑器。涵盖 File, Edit, View, Place, Tools, Analysis, Accessories 菜单。

---

## 16. 学习系统 + 加密组件 + 网表生成器 + FPGA 编译（Explore-18 完整报告）

### 16.1 内建 PSpice 学习系统（caplearningresources）

**架构**：JSON TOC + Dojo UI + Tcl 后端桥接

**核心 API**（openopj.js）：
- `OpenOpjSim(Book, Ch, DesignFolder, Design, Schematic, Page, Profile)` → 打开设计+设置仿真
- `OpenOpjSimnLoadDat(...)` → 打开仿真+加载波形
- `OpenOpjSimnLoadOut(...)` → 打开仿真+加载文本输出
- 通过 `window.external.orPrmConnector` 调用 Tcl 的 `::learningResources::*` 命名空间

### 16.2 加密 TCL 组件（6 个 .tle 包）

| 包名 | 版本 | 推测功能 |
|------|:--:|------|
| orCapTclAppRegistry | 1.0 | Tcl 应用注册表 |
| orDboServerBase | 1.0 | DBO 服务器基础 |
| orPrmDboGeom | **16.6** | 参数化 DBO 几何（与 capDboGeom.tcl 对应） |
| orPrmDboHierStreamer | **16.6** | 参数化 DBO 层次流 |
| orPrmDboStreamer | **16.6** | 参数化 DBO 流 |
| orPrmFieldMap | 1.0 | 参数字段映射（与 orPrmFieldMap.js 对应） |

### 16.3 用户自定义网表生成器（usernetl/）

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

### 16.4 FPGA 编译脚本（20 个 .cmd 文件）

| 厂商 | 脚本数 | FPGA系列 |
|------|:--:|------|
| Actel | 7 | ACT1/ACT2/ACT3/A3200DX/40MX/42MX/54SX |
| Altera | 1 | altera_p.vhd + altera_m.vhd → altlib |
| Xilinx | 9 | XC3000/4000E/EX/5200/9000/CoolRunner + UniSim/SimPrim/LogiBLOX/CoreLib |
| SDF 反标 | 5 | sdf.cmd → COMPILED_SDF_FILE + SCOPE（sdf文件 + 作用域 + 日志） |

### 16.5 creferhdl 页面网格全量（12 种页面尺寸）

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

### 16.6 libManagerReg.env — 库管理器配置

- 支持 20+ 个命名空间：Concept/Concept5x/Edif200/Edif300/Verilog/VerilogA/VHDL/NVerilog/CDBA/...
- 对话框尺寸：newlibrary(305x360), newcell(300x133), newview(300x200)
- 过滤器：library/category/cell/view/viewType/directory/file

---

## 17. 全量文件分析 + HDL 参考库完整结构（Explore-16 完整报告）

### 17.1 .baselined 文件 — 关键发现：可读格式的器件定义基线

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

### 17.2 123 个元件完整目录结构<!-- 注：计数口径为 cis_for_reference/hdl_lib/ 排除"备份"目录后 123（原 124 为旧口径） -->

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

### 17.3 revision.dat — Lisp 风格版本数据

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

### 17.4 part.ptf — 多物理表格式

```
FILE_TYPE = MULTI_PHYS_TABLE;
PART '88E6071'
:PACKAGE_TYPE | VALUE | DESCRIPTION | JEDEC_TYPE | SN_NUM = MANUFACTURER | BOM_SEQ | TYPE_NAME | SPECIFICATION | LIFE_CYCLE ;
 'QFN64' | '88E6071' | '集成电路88E6071-xx-NNC2I000 QFN64' | 'QFN50P900X900X100-65N' | 'M04.100659'(~88E6071) = '' | 'AC00' | '集成电路' | '88E6071-xx-NNC2I000 QFN64' | ''
END_PART
```

**字段**：PACKAGE_TYPE | VALUE | DESCRIPTION | JEDEC_TYPE | SN_NUM=MANUFACTURER | BOM_SEQ | TYPE_NAME | SPECIFICATION | LIFE_CYCLE

### 17.5 Canvas UI XML 定义

**contextmenu.xml（1833 行）**：35+ 上下文菜单，含完整 ToolBarItems 和 ContextMenuItems

**cdnbde.xml（525 行）**：Block Diagram Editor 形状：
- **基本形状 14 种**：Rectangle, RoundRect, Resistor, Speaker, Oval, Pentagon, Hexagon, Octagon, RightTriangle, Cross, Star, Diamond, Triangle
- **连接器/箭头 15 种**：Wire, Bus, Bundle, PCIe 等箭头

**cpSchToolbars.xml**：原理图编辑器工具栏（Explorer, Autoshapes, Add Component, Draw Wire, Draw Bus, Connectors, Ground, Power, Add Note, Properties, Format, Special Bodies, Selection Filter, Constraint Manager）

### 17.6 SDM 设计数据管理

`sdm_policy.xml`：定义完整设计生命周期（preliminary→release），包含 Block/Schematic/Symbol/Variant/Packaged/Layout 的 attachment/monitor/checkin-checkout 规则

### 17.7 .sir 文件 — 二进制符号实例记录

- 1,718 个文件，约 3.3KB 每个
- 魔数：`bb 0c 00 00 00 6f 4d 67`

---

## 18. SPICE 仿真文件全析 + lman/locales 配置（Explore-17 完整报告）

### 18.1 PSpice 文件生态（6 种文件，724 个文件总量）

| 文件 | 数量 | 格式 | 用途 |
|------|:--:|------|------|
| .net | 140 | SPICE 文本 | 扁平化网表（无 .END） |
| .cir | 145 | SPICE 文本 | 仿真入口（含 .lib/.TRAN/.AC/.DC/.INC/.END） |
| .prp | 141 | S-expression | 原理图属性→PSpice 参数映射 |
| .sim | 185 | 键值对+二进制标志 | 仿真设置 |
| .als | 69 | SPICE 文本 | 别名映射（cross-probing） |
| .mrk | 150 | 二进制 | 探针标记数据 |
| .prb | 153 | INI 风格文本 | 探针显示布局配置 |

### 18.2 .prp — 属性映射文件（原理图↔PSpice 桥接）

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

### 18.3 .net — SPICE 扁平化网表

```spice
* source DESIGNNAME
R_R1 N00475 N00484 100 TC=0,0           # 电阻
C_C1 0 N00484 1u IC=0V TC=0,0           # 电容
V_V1 N04788 0 AC 5 +SIN 0 5 50 0 0 0   # 交流正弦源
Q_Q2 NC NB NE Q2N2222                    # BJT
X_AND I0 I1 O $G_DPWR $G_DGND AND2      # 数字子电路
```

### 18.4 .cir — 仿真入口文件

```spice
** Profile: "DESIGN-PROFILE"  [path/profil.sim]
.lib "nom.lib"
.TRAN 0 4m 0 4u                          # 瞬态分析
.AC DEC 100 10 100k                      # AC扫频
.DC LIN V_V1 -1 20 0.01                  # DC扫频
.INC "..\DESIGN.net"                     # 引用网表
.END
```

### 18.5 .als — 交叉探测别名

```spice
.ALIASES
R_R2  R2(1=N04788 2=N04784)
Q_Q2  Q2(c=N13499 b=N07515 e=N09807) @DESIGN.PAGE(sch_1):PG1@LIB.DEVICE(chips)
.ENDALIASES
```

### 18.6 .sim — 仿真配置文件

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

### 18.7 .prb — 探针显示布局

```ini
[DISPLAYS]
BEGIN DISPLAY DISPLAY_NAME
ANALYSIS TRANSIENT_ANALYSIS | AC_SWEEP | DC_SWEEP
BEGIN TRACE TRACE_EXPR
MARKERID ID_NUM           # 波形表达式: V(V1:+), DB(V(OUT)), -I(V2), NTOT(R1)
END TRACE TRACE_EXPR
END DISPLAY DISPLAY_NAME
```

### 18.8 lman/ 目录 — Part Developer 配置（321 文件）

- **.panel** (~300): UI 面板（Lisp/Scheme 风格）
- **.mesg** (7): 消息目录（ERROR/WARNING/FATAL/INFO）
- **.cpm**: setup.cpm（270 行完整配置：引脚类型、网格、符号、CSV导入导出映射）

### 18.9 文件层级关系图

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
