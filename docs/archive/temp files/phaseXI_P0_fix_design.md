# Phase XI P0 遗留三问题 — 精确修复方案（架构师交付）

> 高见远（software-architect）· 2026-08-10
> 只读设计：全部结论基于 HG5015 实测数据（entire.csv / pstxnet.dat / HG5015-BE36_V10.EDF / CrossRef CSV）
> 与真实 Cadence 工程逆向格式（8367、04p4 的 csa/csv/cpc/con）。
> 配套：docs/phaseXI_P0_fix_evidence.md（格式证据全文）。

---

## 问题 1：25 个 ROUTE 跳线被错误跳过（889 vs 906 实例偏差根因）

### 1.1 根因精确定位

| 位置 | 内容 |
|---|---|
| `cis2hdl/core/parser/component_catalog.py` L73 | `_SKIP_REFDES_VALUES: set[str] = {"ROUTE"}` |
| L228-233 | `from_cross_ref()`：`if xref_entry.value and xref_entry.value.upper().strip("*") in _SKIP_REFDES_VALUES: continue` → **Value="ROUTE" 的 25 个 J 跳线被跳过** |
| L69 | `"ROUTE": ""` 前缀提示（实际不生效——跳线 refdes 前缀是 `J` 非 `ROUTE`） |
| `cis2hdl/core/engine/conversion_engine.py` L1403-1417 | P0-D2：`_page.instances = []` 清空 EDIF 占位符后**只用 ComponentCatalog 重建实例** → catalog 缺失 ⇒ 跳线整体丢失 |

**跳过判定 bug 细节**：L228 `if refdes.upper() in _SKIP_REFDES_VALUES` 对 `J8` 等 refdes 永远不命中；实际命中的是 L231 的 **value 判定**（Part 列 = `ROUTE`）。即代码把"Value=ROUTE 的 0Ω 跳线"误判为"非元件布线标记"。

### 1.2 数据证据（实测）

- CrossRef CSV `HG5015-BE36_V10.CSV`：`869,ROUTE,J8,TG1C0D8_VB/15-IOMUX,0,...` —— 25 行，Part=ROUTE、Reference=J8/J11/.../J47，坐标齐全。
- entire.csv：25 个 `PARTINST` 行统一特征：Value=`ROUTE`、Source Package=`ROUTE`、Source Part=`ROUTE.Normal`、PKG_TYPE=`COPPER0201`、PCB Footprint=`COPPER0201`、Type=`ROUTE.Normal`、Library=`LIBRARY1.OLB`。
- pstxnet.dat：`ROUTE.NORMAL(CHIPS)` 出现 **50 次 = 25 跳线 × 2 引脚**；J11 两端连接**不同网络**：`NET_NAME '2P5GE_RSTN'` → `NODE_NAME J11 2`（引脚名 `'NET2'`）、`NET_NAME 'HGPIO_17'` → `NODE_NAME J11 1`（引脚名 `'NET1'`）。**pstxnet 引脚键是数字 1/2**（不是符号引脚名 NET1/NET2）。
- 数量：CrossRef=914、pstxnet=915。914 − 25(ROUTE) = 889 = 当前 con instances（`output/worklib/5015/sch_1/5015.con` 实测 `"I<k>" "pageN_i<k>"` 共 889 条级联行之外的 cell 引用不含跳线）→ 保留后 catalog = 914。

**结论：entire.csv/pstxnet 中不存在"纯布线标记 ROUTE"——25 个 ROUTE 全部是 2 引脚 0Ω 跳线（COPPER0201），必须保留。** 用户列出的 25 个 refdes（J8 J11 J12 J14-J24 J29-J38 J47）与实测完全吻合。

### 1.3 修复方案

**修改 A：component_catalog.py 不再按 Value 跳过 ROUTE**

```python
# L73 原：_SKIP_REFDES_VALUES: set[str] = {"ROUTE"}
# 改：
# 实测 HG5015 无"纯布线标记"：Value="ROUTE" 全部是 2 引脚 COPPER0201 0Ω 跳线（真实元件）。
# 保留跳线；若未来出现 0 引脚/单引脚 ROUTE 标记，由 pstxnet 连接数兜底过滤。
_SKIP_REFDES_VALUES: set[str] = set()
```

```python
# L69 原： "ROUTE": "",   # 跳过：布线标记
# 改：  "ROUTE": "resistor",   # OrCAD 0Ω 跳线（COPPER0201）→ 2 引脚 resistor
```

`from_cross_ref()` L228-233 逻辑保留（集合为空即不跳过）；建议额外加防御性断言：

```python
if not xref_entry.value or not xref_entry.value.strip():
    _skipped += 1; continue   # 空 Value 仍跳过（非元件）
```

**修改 B：匹配强制规则——ROUTE 跳线 → hdl_lib/resistor**

hdl_lib 已确认**无 jumper/route_jumper 符号**（`output/hdl_lib/` 仅 connector/orthogonal_connector/resistor），因此映射到 `resistor`（0Ω 跳线本质是 2 引脚电阻，hdl_lib/resistor/sym_1/symbol.css 引脚为 `C -100 0 "1"` / `C 100 0 "2"`，与 pstxnet 引脚键 1/2 天然对齐）。

实现（二选一，推荐前者）：
1. `cis2hdl/core/parser/component_catalog.py` `to_component_defs()`：当 `entry.value.upper() == "ROUTE"` 时强制 `footprint="resistor"`、`part_name="ROUTE_JMPR"`（避免匹配器按 J 前缀走到 connector 多引脚符号）；
2. `cis2hdl/core/matcher/candidate_pool.py` 类型假设：`"J"` 分支前插入 value 特判——`value.upper() == "ROUTE"` → `[["resistor", 1.0]]`。

**修改 C：引脚/符号输出**

- 跳线按普通 2 引脚元件走既有路径（csv `$PN"1"/"2"`、con term `1/2`、csa LASTPIN `$PN`），不需要新格式。
- pin_name 从 hdl_lib/resistor 取（`"1"`/`"2"`），**不要用源符号引脚名 NET1/NET2**（OrCAD 内部名，DEHDL 无此符号）。

### 1.4 验证断言

- con instances = 914（含 25 跳线；与 pstxnet 915 − U6 section 差异按既有 U6A-I 处理）；
- 25 个 J 跳线在 con/csv/csa/cpc 中可见，每跳线 2 引脚连**两个不同网络**（如 J11: 2P5GE_RSTN ↔ HGPIO_17）；
- csv 中跳线 `%"RESISTOR"` + `LOCATION"J11"` + `$PN"1"<netA>; $PN"2"<netB>;`；
- cpc 中 `#CELL hdl_lib resistor * pageN_i<k>`（普通 #CELL，非 #ISCELL）。

---

## 问题 2：电源符号未进 csa/csv/cpc（设计 C.5 与实现不一致）

### 2.1 根因精确定位（两层）

| 层 | 位置 | 内容 |
|---|---|---|
| 第一层（实例丢失） | `cis2hdl/core/engine/conversion_engine.py` L1403-1417 | P0-D2：`for _page in design.pages: _page.instances = []` **无条件清空所有 EDIF 实例**（含电源符号 GND/VCC_CIRCLE），随后仅用 ComponentCatalog 重建（CrossRef CSV 无电源符号）⇒ 电源符号彻底丢失 |
| 第二层（识别缺失） | `cis2hdl/core/writer/connectivity_model.py` L46-48 | `POWER_SYMBOL_CELLS = {"gnd_power","vcc_circle","gnd_earth","gnd_signal","vcc_bar"}` **缺 `"gnd"`/`"dgnd"`** —— HG5015 符号名是 `GND`/`DGND`（非 gnd_power），即使实例保留也识别不出 |
| 第三层（EDIF 解析） | `cis2hdl/core/parser/edif_parser.py` `_parse_instance` | 电源符号出现在 `(portImplementation ...)` 中（EDIF L54471），refdes=`GND`、library_id=`GND`、**pin_connections 为空**（电源符号不参与 net 的 joined portRef）→ 无引脚数据 |

### 2.2 数据证据（实测）

- EDIF L54471：`(portImplementation GND (instance GND (viewRef GND (cellRef GND (libraryRef LIBRARY1))) (property POWER_TYPE (string "GND")) ... (property NETNAME (string "GND")) ... (transform (origin (pt 1020 -610))))` —— **电源符号带坐标 (1020,-610)、POWER_TYPE/NETNAME 属性**。
- EDIF 统计：`lib='GND'` 电源符号实例覆盖 21 页（page2-24 除 1/7/11/17/19），`lib='VCC_CIRCLE'` 2 个、`'&3V3_SOC'` 1 个。
- 当前输出（问题现状）：`output/worklib/5015/sch_1/page14.csv` 网列表有 `122"GND\g";` 但 **无 `%"GND"` 符号块**；`page14.csa`/`page14.cpc` 无 GND/VCC_CIRCLE；con 有 `("N55" "gnd" -1 -1 2)` + `pageN_gnd` 局部网 + alias（**网数据完整，符号缺失**）。
- 8367 page1.csv L360-376：GND_POWER/VCC_CIRCLE 符号块完整模板（见 2.3）。
- 8367 page1.cpc L58-63：`#ISCELL hdl_lib gnd_power * page1_i27` / `#ISCELL hdl_lib vcc_circle * page1_i28`。
- 04p4 page9.csa L10-60、L219-250：FORCEADD + LASTPIN SIG_NAME + HDL_POWER + BODY_TYPE 完整模板。
- hdl_lib 电源符号定义：
  - `output/hdl_lib/gnd_power/sym_1/symbol.css`：引脚 `C 0 50 "GND"`、`HDL_POWER "GND_POWER"`、`BODY_TYPE "PLUMBING"`、outline `-50,0,50,-50`；
  - `output/hdl_lib/vcc_circle/sym_1/symbol.css`：引脚 `C 0 -50 "G<SIZE-1..0>"`、`SIZE "1B"`、`HDL_POWER "VCC_circle"`、outline `-75,75,75,-75`。

### 2.3 真实工程格式模板（可照抄）

**8367 page1.csv — GND_POWER 块（L360-367）：**
```
%"GND_POWER"
"1","(-5600,4275)","0","hdl_lib","I27";
;
CDS_LMAN_SYM_OUTLINE"-50,0,50,-50"
CDS_LIB"hdl_lib"
HDL_POWER"GND_POWER"
BODY_TYPE"PLUMBING";
"GND"2;
```
**8367 page1.csv — VCC_CIRCLE 块（L368-376）：**
```
%"VCC_CIRCLE"
"1","(-6450,5375)","0","hdl_lib","I28";
;
HDL_POWER"VCC_12"
CDS_LIB"hdl_lib"
SIZE"1B"
BODY_TYPE"PLUMBING"
CDS_LMAN_SYM_OUTLINE"-75,75,75,-75";
"G<SIZE-1..0> \B"1;
```
要点：电源符号**无 VALUE/PART_NAME/LOCATION**；属性顺序不限但必须含 **HDL_POWER（=电源网名，无 \g）** 与 **BODY_TYPE"PLUMBING"**；VCC_CIRCLE 另含 **SIZE"1B"**；单引脚行 `"<pinName>"<netId>;`（GND_POWER→`"GND"`，VCC_CIRCLE→`"G<SIZE-1..0> \B"`）；实例行 `"<pinCount>","(<x>,<y>)","0","<lib>","I<k>";`（pinCount=1）。

**04p4 page9.csa — VCC_CIRCLE 块（L219-250，核心行）：**
```
FORCEADD VCC_CIRCLE..1
(-2125 9750);
FORCEPROP 3 LASTPIN (-2125 9700) SIG_NAME DC12V\g
J 0
(-2115 9710);
DISPLAY 0.659574 (-2115 9710);
PAINT MONO (-2115 9710);
DISPLAY INVISIBLE (-2115 9710);
FORCEPROP 1 LAST HDL_POWER DC12V
J 1
(-2123 9804);
DISPLAY 0.851064 (-2123 9804);
PAINT GREEN (-2123 9804);
FORCEPROP 1 LAST SIZE 1B
...
FORCEPROP 1 LAST CDS_LMAN_SYM_OUTLINE -75,75,75,-75
...
FORCEPROP 2 LAST CDS_LIB hdl_lib
...
FORCEPROP 1 LAST BODY_TYPE PLUMBING
...
FORCEPROP 1 LAST PATH I101
```
**GND_POWER 同构**：`FORCEADD GND_POWER..1 (x y);` + `FORCEPROP 3 LASTPIN (px py) SIG_NAME GND_POWER\g` + `FORCEPROP 1 LAST HDL_POWER GND_POWER` + `BODY_TYPE PLUMBING` + `PATH I<k>`（8367 page1.csa L1592-1650）。
坐标关系（实测）：`LASTPIN 坐标 = FORCEADD 坐标 + 引脚偏移`；GND_POWER 偏移 `(0,+50)`、VCC_CIRCLE 偏移 `(0,-50)`（与 symbol.css 引脚一致）。FORCEADD 坐标 = csv 实例坐标（8367: (-5600,4275) 两文件一致）。

**8367 page1.cpc：#ISCELL 结构（L58-63）：**
```
#ISCELL
  hdl_lib gnd_power *
  page1_i27
#ISCELL
  hdl_lib vcc_circle *
  page1_i28
```
电源符号用 **#ISCELL**（区别于普通元件 #CELL），实例名 `pageN_i<k>` 与 csv `I<k>` 严格一致（8367: csv I27 ↔ cpc page1_i27）。

### 2.4 修复方案

**修改 A：conversion_engine.py P0-D2 保留电源符号实例**

```python
# 原（L1413-1417）：
#   for _page in design.pages:
#       _page.instances = []
# 改：清空前先收集电源符号实例（cellRef ∈ 电源符号集），清空后回填
_POWER_CELLS = {"gnd", "dgnd", "vcc_circle", "gnd_power", "gnd_earth",
                "gnd_signal", "vcc_bar", "vcc_arrow", "gnd_chassis"}
for _page in design.pages:
    power_insts = [
        inst for inst in _page.instances
        if (getattr(inst, "library_id", "") or "").lower() in _POWER_CELLS
    ]
    _page.instances = []
    for _pi in power_insts:
        _page.instances.append(_pi)
```
补充：电源符号实例可能 refdes 为空（EDIF 实测 `''`）——在 `_parse_instance` 或回填时统一赋值唯一 refdes：`refdes or f"{lib_id}_{page_index}_{k}"`（如 `GND_2_1`），保证 `_map_coords_to_dehdl` / CoordTransform 不碰撞。

**修改 B：connectivity_model.py 电源符号识别扩展**

```python
# L46-48 原：
# POWER_SYMBOL_CELLS = frozenset({"gnd_power","vcc_circle","gnd_earth","gnd_signal","vcc_bar"})
# 改：补 HG5015 实际符号名 gnd/dgnd
POWER_SYMBOL_CELLS: frozenset[str] = frozenset(
    {"gnd", "dgnd", "gnd_power", "vcc_circle", "gnd_earth",
     "gnd_signal", "vcc_bar", "vcc_arrow"}
)
```
同时 `_SCHEMATIC_ELEMENT_LIBS`（L51-57）确认**不含** gnd/dgnd/vcc_circle（当前已不含，勿加入）。

**修改 C：电源网关联（power_nets）**

电源符号实例 0 引脚、不参与 net joined portRef，`power_nets` 需从实例属性推导：
- GND/DGND 符号 → 固定网名 `"GND"`（EDIF `POWER_TYPE`/`NETNAME` 属性均为 "GND"，实测）；
- VCC_CIRCLE → 取 EDIF 实例 refdes（OrCAD 用网名作 refdes，实测 `&3V3_SOC` → `3V3_SOC`）或 `NETNAME` 属性；两者均无则跳过该符号（不生成）。

在 connectivity_model `build()` 第 5 步循环中，`is_power=True` 分支（L452-453）已收集 `irec.power_nets.append(net_name)` —— 但那是从 pin_connections 来的；对 0 引脚电源符号改为：

```python
if is_power and not irec.pins:
    net = _power_net_for_symbol(irec)   # GND→"GND"；VCC_CIRCLE→refdes/NETNAME
    if net:
        irec.power_nets.append(net)
```

**修改 D：csv_writer.py 电源符号块格式修正**

`_build_instance_block` L154-173 现状：电源符号走了普通属性块（VALUE/PART_NAME/LOCATION）+ 单引脚行，**缺 HDL_POWER/BODY_TYPE，且多出 VALUE/PART_NAME/LOCATION**。改为专用分支：

```python
if irec.is_power_symbol:
    lines = [f'%"{cell_label.upper()}"',
             f'"1","({x},{y})","0","{conn.hdl_lib_name}","I{irec.page_local_k}";',
             ";"]
    if cell_label.lower() == "vcc_circle":
        lines += [f'HDL_POWER"{net_display}"',      # net_display 无 \g
                  f'CDS_LIB"{conn.hdl_lib_name}"',
                  'SIZE"1B"',
                  'BODY_TYPE"PLUMBING"',
                  f'CDS_LMAN_SYM_OUTLINE"{outline}";']
        pin_name = "G<SIZE-1..0> \\B"
    else:  # gnd/dgnd/gnd_power
        lines += [f'CDS_LMAN_SYM_OUTLINE"{outline}"',
                  f'CDS_LIB"{conn.hdl_lib_name}"',
                  f'HDL_POWER"{net_display}"',
                  'BODY_TYPE"PLUMBING";']
        pin_name = "GND"
    lines.append(f'"{pin_name}"{net_id};')
    return lines
```
其中 `net_display` 取 `irec.power_nets[0]`（strip `\g`），`net_id` 用 `_pin_net_id(page_conn, irec, first_only=True)`（已有 L238-244）。outline 复用 `_outline_for`（L231-234 已有 gnd_power/vcc_circle 分支）。

**修改 E：cpc_writer.py**

`_build_cpc_content` L105-111 已有 `is_iscell = irec.is_power_symbol or ...` → 自动 #ISCELL ✓；但 cell_label 需为 `gnd`/`vcc_circle`（连接模型 cell_name 来源）。**确保库名用 conn.hdl_lib_name**（L110 已是）。无需大改，仅验证。

**修改 F：csa_writer.py 电源符号专用块**

`_emit_conn_instance_block`（L1080-1186）对电源符号走普通块（VALUE/LOCATION 等）不符合 8367/04p4。加专用分支（按 04p4 模板）：

```python
if irec.is_power_symbol:
    lines = _emit_power_symbol_block(conn, irec, body_name, x, y)
    return lines

def _emit_power_symbol_block(self, conn, irec, body_name, x, y):
    net = (irec.power_nets[0] if irec.power_nets else "GND").rstrip("\\g")
    is_vcc = body_name.lower() == "vcc_circle"
    px, py = (x, y + 50) if not is_vcc else (x, y - 50)   # symbol.css 引脚偏移
    lines = [f"FORCEADD {body_name.upper()}..1", f"({x} {y});",
             f"FORCEPROP 3 LASTPIN ({px} {py}) SIG_NAME {net}\\g",
             "J 0", f"({px - 10} {py + 10});",
             f"DISPLAY {_SCALE_SIG_NAME} ({px - 10} {py + 10});",
             f"PAINT {_PAINT_MONO} ({px - 10} {py + 10});",
             f"DISPLAY INVISIBLE ({px - 10} {py + 10});",
             f"FORCEPROP 1 LAST HDL_POWER {net}",
             "J 1", f"({x} {y + 54});",
             f"DISPLAY {_SCALE_VALUE} ({x} {y + 54});",
             f"PAINT {_PAINT_GREEN} ({x} {y + 54});"]
    if is_vcc:
        lines += ["FORCEPROP 1 LAST SIZE 1B", "J 1", f"({x - 147} {y});",
                  f"DISPLAY {_SCALE_VALUE} ({x - 147} {y});",
                  f"PAINT {_PAINT_GREEN} ({x - 147} {y});",
                  f"DISPLAY INVISIBLE ({x - 147} {y});"]
    lines += [f"FORCEPROP 1 LAST CDS_LMAN_SYM_OUTLINE {outline}",
              "J 0", f"({x} {y});", f"DISPLAY {_SCALE_OUTLINE} ({x} {y});",
              f"PAINT {_PAINT_GREEN} ({x} {y});",
              f"DISPLAY INVISIBLE ({x} {y});",
              f"FORCEPROP 2 LAST CDS_LIB {self._hdl_lib_name}",
              "J 0", f"({x} {y});", f"DISPLAY INVISIBLE ({x} {y});",
              "FORCEPROP 1 LAST BODY_TYPE PLUMBING",
              "J 0", f"({x} {y - 100});",
              f"DISPLAY {_SCALE_VALUE} ({x} {y - 100});",
              f"PAINT {_PAINT_GREEN} ({x} {y - 100});",
              f"DISPLAY INVISIBLE ({x} {y - 100});",
              f"FORCEPROP 1 LAST PATH I{irec.page_local_k}",
              "J 0", f"({x} {y});",
              f"DISPLAY {_SCALE_TRANSITION} ({x} {y});",
              f"PAINT {_PAINT_ORANGE} ({x} {y});",
              f"DISPLAY INVISIBLE ({x} {y});"]
    return lines
```

**修改 G：放置策略（每页每电源网 1 个 + 坐标）**

- 数量：8367 实测 = **每页每个电源网 1 个符号**（page1：3 个 GND_POWER 对 3 个 GND 网、2 个 VCC_CIRCLE 对 2 个 VCC 网）。HG5015 每页 1 个 GND 符号（每页 1 个 GND 网）。
- 坐标：优先用 EDIF `portImplementation` 的 `transform origin`（真实放置，L54471 有 (1020,-610)）经 CoordTransform 映射；无坐标回退到**页面右下角边缘区域**（`(-600, 7200)` 附近递减，避开元件区）——勿用该网第一个元件引脚（会导致符号压线）。
- 多个 VCC 符号同页：按 k 递增错开（8367 已证实例 k 与普通元件共享连续编号）。

### 2.5 验证断言

- 每页 csa 有 `FORCEADD GND_POWER..1`/`VCC_CIRCLE..1` + `LASTPIN ... SIG_NAME <net>\g` + `HDL_POWER <net>` + `BODY_TYPE PLUMBING`；
- csv 有 `%"GND"/%"VCC_CIRCLE"` 块 + `HDL_POWER` + 单引脚行 `"GND"<id>;` / `"G<SIZE-1..0> \B"<id>;`；
- cpc 有 `#ISCELL hdl_lib gnd_power/vcc_circle * pageN_i<k>`；
- con **无**电源符号 cells/instances（保持 C.5 约定）；
- GND 网在 csv 显示名：当前为 `GND\g`，与 8367 的 `GND_POWER\g` 差异源于源符号名（HG5015=GND）——**保留 `GND\g`**（符号块 cell 名用 `GND`，HDL_POWER=`GND`）。

---

## 问题 3：自动网名未转 UN$ 形式

### 3.1 根因精确定位

| 位置 | 内容 |
|---|---|
| `cis2hdl/core/net_utils.py` L106-109 | `con_name()`：`'$'→'_'` + `n.lstrip("_")` → `"$21N109399"` → `"21n109399"`（**数字开头**，Cadence 校验风险） |
| `cis2hdl/core/writer/connectivity_model.py` L365 | `bare = con_name(raw_name)` 对**所有**网名直接清洗，无 UN$ 转换触发点 |
| con/csv writer | 只消费 `NetRecord.internal_name/display_name`，UN$ 转换必须在 `build()` 第 4 步完成 |

### 3.2 数据证据（实测）

- EDIF L54138：`(net (rename (name &_47N777 ...) "$47N777") (joined (portRef A (instanceRef INS265)) (portRef UPS_N_TX_N (instanceRef INS337))) (property DIFFERENTIAL_PAIR (string "2P5GE_TX_")))` —— **$ 自动网名 + 连接（page 级 INS### 占位符）**。
- pstxnet：**166 个 `$` 开头自动网名**（$17N82598、$21N109399、$21N109400...）；`$47N777` 连接 `NODE_NAME C96 1`。
- 当前输出：`5015.con` `("N148" "21n109399" -1 -1 0)`（数字开头）；`page14.csv` 网列表 `1"$21N109399";` 等 530 处 `$`。
- 8367 csv L7：`7"UN$1$CAPACITOR$I12$1";`；L13：`13"UN$1$DCDC$I1$EN";`；L17：`17"UN$1$DIODE$I31$1";` —— **pin 段是符号引脚名**（EN 非数字）。
- 8367 con L283：`("N3" "unnamed_1_capacitor_i12_1" -1 -1 0)` —— con 内部名 `unnamed_<page>_<cell>_i<k>_<pin>`，**scope=0（局部网）**。
- 8367 csv L86/L96：CAPACITOR I12 的 `$PN"1"7`（引脚 1 → 网 7 = UN$1$CAPACITOR$I12$1）→ **UN$ 的 I<k> 与 csv/cpc 页内实例编号一致**（net_utils L164 `auto_net_con_name` 已按 page_local_k 设计）。

### 3.3 UN$ 命名规则（8367 逆向）

```
CSV 显示名 : UN$<page>$<CELL>$I<k>$<pin_name>
con 内部名 : unnamed_<page>_<cell>_i<k>_<pin_name>   （$→_、小写）
样例       : UN$1$CAPACITOR$I12$1  ↔  unnamed_1_capacitor_i12_1
             UN$1$DCDC$I1$EN       ↔  unnamed_1_dcdc_i1_en
             UN$1$DIODE$I31$1      ↔  unnamed_1_diode_i31_1
```
- `page` = 网所在物理页（第一个连接的页）；
- `CELL` = 第一个连接元件的 cell 名（大写）；
- `I<k>` = 该元件页内实例编号（csv `I<k>` / cpc `pageN_i<k>` 一致）；
- `pin_name` = 连接该网的**符号引脚名**（EN、1、2…，非引脚号）；
- scope=0（8367 证据：`-1 -1 0`）。

### 3.4 修复方案

**修改 A：net_utils.py 新增/完善**

```python
# 已有（L142-161）auto_net_csv_name: unnamed_1_capacitor_i12_1 → UN$1$CAPACITOR$I12$1
# 已有（L164-178）auto_net_con_name: (1,"capacitor",12,"1") → unnamed_1_capacitor_i12_1
# 新增判定 + 从连接推导入口：

def is_auto_net(name: str) -> bool:
    """OrCAD EDIF 自动网名：$ 开头（$47N777 / $21N109399）。"""
    return bool(name) and name.startswith("$")

def auto_net_name(
    conn,
    raw_name: str,
    connections: list[tuple[str, str]],
    inst_page: dict[str, int],
    cell_by_refdes: dict[str, str],
) -> tuple[str, str]:
    """由自动网第一个连接 (refdes, pin) 推导 (con_internal, csv_display)。

    Args:
        conn: DesignConnectivity（用于 page_local_k / cell 查询）。
        raw_name: $ 开头自动网名（仅显示用途，不参与命名）。
        connections: 该网 (refdes, pin_number) 连接列表（有序）。
        inst_page: refdes → 物理页号。
        cell_by_refdes: refdes → cell_name（小写）。

    Returns:
        (con_internal_name, csv_display_name)，如
        ("unnamed_12_capacitor_i34_1", "UN$12$CAPACITOR$I34$1")。
        无连接/推导失败时回退 (con_name(raw_name), raw_name)。
    """
    for refdes, pin_number in connections:
        if not refdes:
            continue
        page = inst_page.get(refdes)
        irec = conn.inst_by_refdes.get(refdes)
        if irec is None or page is None:
            continue
        cell = cell_by_refdes.get(refdes) or irec.cell_name  # lowercase
        k = irec.page_local_k
        pin_name = irec.pin_name_for(pin_number) or pin_number
        internal = auto_net_con_name(page, cell, k, pin_name)
        return internal, auto_net_csv_name(internal)
    return con_name(raw_name), raw_name
```

**修改 B：connectivity_model.py build() 第 4 步接线（唯一触发点）**

L363-414 构造 NetRecord 时，对 `is_auto_net(raw_name)` 的网：

```python
if is_auto_net(raw_name):
    bare, display = auto_net_name(
        conn, raw_name, raw_conns[raw_name], inst_page, cell_by_refdes,
    )
else:
    bare = con_name(raw_name)
    display = (csv_display_name(raw_name, is_global=True)
               if is_power_or_ground(raw_name) else raw_name)
# scope：自动网 = 0（8367 证据），即使跨页也按局部处理（不做 alias）
```
其中 `cell_by_refdes` 在 build() 第 5 步之前预构建（`inst_page` 已有 L358-361；补充 `cell_by_refdes: refdes → cell_name_i`，可在第 2 步 cells 建立后回填）。`InstanceRecord.pin_name_for` 需新增（或直接查 `irec.pins` 匹配 pin_number 的 pin_name；无匹配回退 pin_number）。

**修改 C：con_writer / csv_writer / csa_writer 零改动**

- con 输出 `net.internal_name` → `unnamed_12_capacitor_i34_1`（非数字开头）✓；
- csv 网列表输出 `pnr.display_name` → `UN$12$CAPACITOR$I34$1` ✓；
- csa `_sig_name_at_pin` 的 `net_display` 来自 `PageNetRecord.display_name` → UN$ 显示名 ✓；
- `csv_display_name` L115-139 保持（非全局网原样返回）→ UN$ 名不经变换直接显示 ✓。

**修改 D：推导失败兜底**

若自动网无任何连接（孤立网）：回退 `con_name(raw_name)`（维持现状，不崩）；CSV 显示名仍用 `$21N109399` 原文（与 8367 中非 UN$ 网如 `VCC_12` 不带 \g 同理，保留原名的可见性）。

### 3.5 验证断言

- con 中**无数字开头网名**（除 12v0/1v2/3v3 等合法电源网名——它们不是 $ 自动网，不转换）；
- 166 个 $ 网全部变为 `unnamed_<page>_<cell>_i<k>_<pin>`（con）/ `UN$<page>$<CELL>$I<k>$<pin>`（csv/csa SIG_NAME）；
- csv 网列表中无 `$21N109399` 样式残留（仅兜底孤立网例外）；
- UN$ 名与 cpc `pageN_i<k>`、csv `I<k>`、con `pageN_i<k>` 三处编号一致。

---

## 共享知识（跨问题注意事项）

- **三问题共用一条主链**：EDIF 解析 → conversion_engine P0-D2 实例重建（问题 1/2 的丢失点）→ connectivity_model（问题 3 的命名点 + 问题 2 的识别点）→ con/csv/cpc/csa writers（问题 2 的格式点）。**建议按"解析保留 → 模型识别/命名 → 输出格式"三层依次修复并回归**。
- 电源符号**不进入 con cells/instances**（C.5 约定，8367 实证），但**进入 csv/cpc(#ISCELL)/csa**；实例 k 与普通元件共享连续编号。
- ROUTE 跳线是**真实元件**（进 con），与电源符号相反——两者都来自 EDIF 但处理路径不同。
- 所有网名统一在 `connectivity_model.build()` 第 4 步定稿（internal/display/scope 三态），writers 不得二次改名。
- 电源网判定沿用 `net_utils.classify_net`（ground_names/power_prefixes 已覆盖 GND/VCC/VDD/12V0/3V3 等），`GND` 已是 ground_name ✓。
- 转换目标 hdl_lib 已具备 `gnd_power`/`vcc_circle`/`resistor` 符号；HG5015 源符号名 `GND`/`DGND`/`VCC_CIRCLE` 与 hdl_lib 的 `gnd_power`/`vcc_circle` 之间的 cell 名映射：**输出统一用 hdl_lib 符号名**（GND→gnd_power、DGND→gnd_power、VCC_CIRCLE→vcc_circle），网名/HDL_POWER 保留源网名（GND）。
