# CIS2HDL Phase XI P0-B/P0-C 系统设计：Cadence DEHDL 真实格式重构

> 架构师：高见远（Bob）｜ 实现：寇豆码（Engineer）
> 日期：2026-08
> 目标：把 CIS2HDL 的 con/xcon/pageN.csv/pageN.cpc/csa 输出重构为与 Cadence SPB 16.6 DEHDL 完全兼容的真实格式，使 HG5015 工程可在 Concept HDL 中完成 page 编译并成功导出 pstxnet 网表（禁用 DSN 元件源，主链 = EDIF + pstxnet）。
>
> **全部格式均逆向自真实 Cadence 工程（8367 / 04p4 / switch_practice / CIStoHDL_standard），每条规则都有实测文件证据，禁止臆测。**

---

## 0. 实测文件证据索引（设计依据）

| 证据文件 | 路径 | 用途 |
|---|---|---|
| 8367.con | `docs_for_reference/OrCAD_files_references/cis_for_reference/worklib/8367/sch_1/8367.con` | con 全量模板（cells/nets/instances/lastIds/terms 方向数字） |
| 8367.xcon | 同上目录 `8367.xcon` | xcon 全量模板（lastids/cells/nets/aliases/instances/netScopes/pages） |
| 8367 page1.csv | 同上目录 `page1.csv` | CSV 模板（网络编号、实例块、$PN 引脚映射、电源块） |
| 8367 page1.cpc | 同上目录 `page1.cpc` | CPC 模板（#ISCELL/#CELL 顺序） |
| 8367 page1.csa | 同上目录 `page1.csa` | CSA 模板（FORCEADD/LASTPIN $PN/SIG_NAME/WIRE/DOT/QUIT） |
| 04p4 page4.csa | `previous_switch_programme/交换机练习/OSJZX-6100F-RTK/.../worklib/04p4/sch_1/page4.csa` | WIRE 16 主干拓扑、LASTPIN SIG_NAME `\g` 全局电源 |
| 04p4 page10.csv | 同上目录 `page10.csv` | 真实填充 CSV（PAGE_NUMBER=15、$PN 完整结构） |
| 04p4 page10.cpc | 同上目录 `page10.cpc` | 真实填充 CPC（116 个 #CELL/#ISCELL） |
| switch_practice page1.csa | `previous_switch_programme/switch_practice/practice/worklib/switch_practice/sch_1/page1.csa` | 395 WIRE + 332 LASTPIN + 110 DOT 完整结构、无页框的 CSA |
| HG5015 全套 | `tests/fixtures/HG5015test/`（EDF/DSN/CSV/pstxnet/pstchip/pstxprt） | 被测工程与验收基准（590 nets / 2821 nodes / 906 refdes） |
| hdl_lib symbol.css | `HG5015_tests/output_v2c/hdl_lib/<cell>/sym_1/symbol.css` | 引脚偏移权威来源（`C x y "pinname"` 指令） |

---

# Part A：逐文件精确格式模板（逆向结论）

## A.1 `.con` 文件（Cadence S-Expr 连通性文件）

### A.1.1 完整结构（8367.con 实测）

```lisp
(
  (version 16.6)
  (tool
    (creator "conceptHDL")
    (last "conceptHDL")
  )
  (library "8367_lib")
  (design "8367"
    (lastIds
      (lastInstanceId 149)      ;; = 设计内实例总数（含所有页、不含电源符号）
      (lastNetId 135)           ;; = 设计内网络最大 ID（N1..N135 连续）
      (lastInstTermId 519)      ;; = 设计内引脚总数（M1..M519 连续）
    )
    (cells
      ("S2" "dc_dc" "hdl_lib" "sym_1"
        (terms
          ("T3" "bst" -1 -1 3)     ;; 第5个数字: 1=input, 2=output, 3=inout（与xcon direction 对照验证）
          ("T4" "en" -1 -1 3)
          ("T5" "fb" -1 -1 3)
          ("T6" "gnd" -1 -1 1)
          ("T7" "in" -1 -1 3)
          ("T8" "sw" -1 -1 3)
        )
      )
      ("S3" "capacitor" "hdl_lib" "sym_1"
        (terms
          ("T9" "1" -1 -1 3)
          ("T10" "2" -1 -1 3)
        )
      )
      ;; ... 每个唯一 (cell, sym_N) 一个 S 条目；电源符号 (gnd_power/vcc_circle) 不在此列
    )
    (nets
      ("N1" "gnd_power" -1 -1 2 )        ;; scope: 2=全局（名称为裸名、小写、无 \g）
      ("N2" "page1_gnd_power" -1 -1 0 )  ;; scope: 0=局部（名称带 pageN_ 前缀）
      ("N3" "unnamed_1_capacitor_i12_1" -1 -1 0 )  ;; 自动命名网（UN$ → unnamed_）
      ;; ...
    )
    (instances
      ("I1" "page1_i1" "S2"
        (pins
          ("M1" "T3" -1 -1
            (conn
              ("0" -1 -1 "N7" -1 -1)     ;; 第1字段恒为 "0"（gate 索引占位）；"N7" = 设计级网络ID
            )
          )
          ("M2" "T4" -1 -1
            (conn
              ("0" -1 -1 "N9" -1 -1)
            )
          )
          ;; ... 每个已连接引脚一个 M 条目
        )
      )
      ;; ...
    )
  )
)
```

### A.1.2 字段语义（实测推导，证据见 8367.con）

| 字段 | 格式 | 语义/规则 |
|---|---|---|
| `(cells)` | `("S<n>" "<cell>" "hdl_lib" "sym_<n>")` | 每个唯一 (cell, sym_N) 组合一个条目；S-id 从 1 连续（8367 从 S2 开始是因 S1 被页框占用；CIS2HDL 从 S1 起即可）。**电源符号 gnd_power/vcc_circle 不列入**（8367 实测：cells 中无 gnd_power/vcc_circle，但有 mark） |
| `(terms)` | `("T<n>" "<pinName>" -1 -1 <dir>)` | 引脚按**名称字母序**排列（8367 dc_dc: bst,en,fb,gnd,in,sw）；T-id 全设计连续。方向数字：**1=input、2=output、3=inout**（对照 8367.xcon `<direction>` 验证：T6 gnd→input=1，T44→output=2，T59→inout=3） |
| `(nets)` | `("N<n>" "<name>" -1 -1 <scope> )` | 名称 = **DEHDL 内部名**（小写、`$`→`_`、去 `\g`）。局部网 scope=0 且名称带 `pageN_` 前缀（避免跨页同名合并）；全局网 scope=2 且裸名。`-1 -1` 恒为占位（猜测为 bus 上下界/标志，实测恒 -1）。行尾 `scope` 后有一个空格再 `)` |
| `(instances)` | `("I<n>" "pageN_i<k>" "S<cellId>")` | I-id 设计级连续；内部名 = `page<N>_i<page-local-k>`（与 cpc 一致）；cell 引用 S-id。**电源符号实例不列入**（实测 page1_i27 GND_POWER 不在 instances） |
| `(pins)` | `("M<n>" "T<termId>" -1 -1 (conn ("0" -1 -1 "N<netId>" -1 -1)))` | 每个已连接引脚一个；M-id 全设计连续；conn 第 1 字段恒 `"0"`；`"N<netId>"` 引用设计级网络 ID |
| `(lastIds)` | `(lastInstanceId N) (lastNetId N) (lastInstTermId N)` | **从 1 连续编号时 = 计数**（8367 实测：149 个 I 条目 & lastInstanceId=149；519 个 M 条目 & lastInstTermId=519；nets 135 个 ID & lastNetId=135） |

### A.1.3 CIS2HDL 映射规则（PageIR/ComponentInstanceIR/NetIR → con）

1. **cells 收集**：遍历 `design.pages[*].instances`，按 `(cell_name, section)` 去重。cell_name = match_map 的 target cell（`hdl_lib/capacitor` → `capacitor`），无 match 时用 library_id 末段。`sym_<section>` 用 `inst.section`（默认 1）。terms 来自 matched `ComponentDef.pins`（name + type→方向），按名称字母序排序，方向映射：`ElectricalType.INPUT→1, OUTPUT→2, 其余(包括POWER/GROUND/PASSIVE/BIDIR/NC)→3`。
2. **nets 收集**：全局唯一网 = 按**规范化名**去重（规范化 = 去 `\g`、小写、`$`→`_`）。每条网的连接集合 = 跨页 `NetIR.connections` 并集（refdes+pin_number）。scope 判定：网名在 `design.global_nets` 或分类为 POWER/GROUND 且跨页出现 → scope=2 裸名；否则 scope=0 且名称 = `pageN_<规范化名>`（若多页出现同名局部网，天然唯一）。自动名网（`UN$...`）→ `unnamed_<page>_<cell>_<inst>_<pin>`（与 csv 中的 `UN$n$CELL$I$PIN` 对应）。
3. **instances 收集**：所有非电源符号实例（排除 cell ∈ {gnd_power, vcc_circle}）。I-id 设计级从 1 连续；page-local k 按页内从 1 连续（**每页独立计数**，与 cpc/csv 共用）。pin→net：`inst.pin_connections[pin_number] = net_name` → 查设计级 netId。termId 查 cells 中该实例 cell 的 terms 表。
4. **lastIds**：`lastInstanceId=实例条数`，`lastNetId=网络条数`，`lastInstTermId=引脚条数`（M 条数 = conn 数）。

## A.2 `.xcon` 文件（CS Schema XML，8367.xcon 实测）

### A.2.1 完整结构

```xml
<schema xmlns="http://www.cadence.com/spb/csschema"
	xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
	xsi:schemaLocation="http://www.cadence.com/spb/csschema CSSchema002.xsd">
  <header>
    <schemaVersion>16.6</schemaVersion>
    <creatorTool>conceptHDL</creatorTool>
    <modifierTool>conceptHDL</modifierTool>
    <modificationTime>2024-09-04T19:17:49</modificationTime>
    <savedLibrary>8367_lib</savedLibrary>
  </header>
  <designs>
    <design schemaType="nameBased" name="8367" view="sch_1">
      <lastids>
        <instanceid>149</instanceid>
        <netid>135</netid>
        <insttermid>519</insttermid>
      </lastids>
      <cells>
        <cell>
          <id>S2</id>
          <library>hdl_lib</library>
          <name>dc_dc</name>
          <view>sym_1</view>
          <parameters>
          </parameters>
          <terms>
            <term>
              <id>T3</id>
              <name>bst</name>
              <direction>inout</direction>
            </term>
            <!-- 每个 term：id/name/direction（inout|input|output） -->
          </terms>
        </cell>
        <!-- ... -->
      </cells>
      <nets>
        <net>
          <id>N2</id>
          <name>page1_gnd_power</name>
        </net>
        <!-- 与 con (nets) 完全一致（ID+内部名） -->
      </nets>
      <aliases>
        <alias net1="N2" lsb1="-1" msb1="-1" net2="N1" lsb2="-1" msb2="-1" />
        <!-- 局部网→全局网别名：net1=局部网ID, net2=全局网ID；lsb/msb 恒 -1 -->
      </aliases>
      <differentialnets>
      </differentialnets>
      <differentialbusnets>
      </differentialbusnets>
      <netgroups>
      </netgroups>
      <netinterfaces>
      </netinterfaces>
      <instances>
        <instance>
          <id>I1</id>
          <cellid>S2</cellid>
          <name>page1_i1</name>
          <parameters>
          </parameters>
          <masks>
          </masks>
          <powers>
          </powers>
          <pins>
            <pin>
              <id>M1</id>
              <termid>T3</termid>
              <connections>
                <connection net="N7" />
              </connections>
            </pin>
            <!-- 每个已连接引脚 -->
          </pins>
          <differentialpins>
          </differentialpins>
          <differentialbuspins>
          </differentialbuspins>
          <portgroups>
          </portgroups>
          <portinterfaces>
          </portinterfaces>
        </instance>
        <!-- ... -->
      </instances>
      <templateresolutions>
      </templateresolutions>
      <templateinstances>
      </templateinstances>
      <extensions>
        <extension name="schematic_extension">
        <schematicExtension>
        <netScopes>
          <netScope ref="gnd_power">
            <pageScope number="1">
              <scope>global</scope>
            </pageScope>
            <pageScope number="2">
              <scope>global</scope>
            </pageScope>
          </netScope>
          <!-- 每个全局网一个 netScope；ref=裸名；每个出现的页一个 pageScope -->
        </netScopes>
        <pages>
          <page number="1">
            <physicalPageNumber>1</physicalPageNumber>
            <errorStatus>false</errorStatus>
            <nets>
              <net ref="gnd_power"></net>
              <net ref="unnamed_1_capacitor_i12_1"></net>
              <!-- 该页出现的网（按内部名，去重） -->
            </nets>
            <instances>
              <instance ref="i1"></instance>
              <!-- 该页实例（page-local 短名，不带 pageN_ 前缀） -->
            </instances>
          </page>
          <!-- 每页一个 -->
        </pages>
      </schematicExtension>
        </extension>
      </extensions>
    </design>
  </designs>
</schema>
```

### A.2.2 字段语义与 CIS2HDL 映射

| 区块 | 规则 |
|---|---|
| lastids | 与 con lastIds 相同数值 |
| cells | 与 con cells 相同；term direction 用英文全称 `inout/input/output`（con 数字 3/1/2 的展开） |
| nets | 与 con nets 相同（id + 内部名） |
| aliases | **局部电源网 → 全局网** 的别名（8367 实测 7 条：page1_gnd_power→gnd_power、page1_vcc_12→vcc_12、page2_gnd_power→gnd_power、page2 的 dc_105/vdd_105/vdd_33 局部网→全局 vdd_105/vdd_33 等）。CIS2HDL：凡 scope=0 的局部网与 scope=2 的全局网**规范化名相同**时生成一条 alias |
| differentialnets/differentialbusnets/netgroups/netinterfaces/templateresolutions/templateinstances | 恒为空（保留标签） |
| instances | 与 con instances 相同（pins→connections 用 `<connection net="N.." />`） |
| netScopes | 每个全局网一个 `<netScope ref="裸名">`，每出现页一个 `<pageScope number="N"><scope>global</scope></pageScope>` |
| pages | 每页一个；`<page number>` = 物理页码；nets 用该页出现的网（内部名，去重）；instances 用 page-local 短名（`i1`，不带前缀） |

## A.3 `pageN.csv`（DEHDL 页面连通性文件）

### A.3.1 完整结构（8367 page1.csv + 04p4 page10.csv 实测）

```
FILE_TYPE = CONNECTIVITY;
{Allegro Design Entry HDL 16.6-p007 (v16-6-112F) 10/10/2012}
"PAGE_NUMBER" = 1;
0"NC";
1"VCC_12\g";
2"GND_POWER\g";
3"GND_POWER\g";
4"VCC_12\g";
5"GND_POWER\g";
6"VDD_105";
7"UN$1$CAPACITOR$I12$1";
8"VDD_33";
9"UN$1$CAPACITOR$I18$1";
...
%"DC_DC"
"1","(-5350,6675)","0","hdl_lib","I1";
;
VALUE"SY8113BADC"
CDS_LMAN_SYM_OUTLINE"-150,200,150,-200"
CDS_LIB"hdl_lib"
PART_NAME"SY8113"
DESCRIPTION"集成电路SY8113BADC TSOT23-6"
PACKAGE_TYPE"TSOT23-6"
SN_NUM"M04.100620"
JEDEC_TYPE"SOT95P285X112-6N"
$LOCATION"IC1"
CDS_LOCATION"IC1"
$SEC"1"
CDS_SEC"1";
"BST"
$PN"1"12;
"SW"
$PN"6"10;
"EN"
$PN"4"13;
"GND"
$PN"2"5;
"IN"
$PN"5"4;
"FB"
$PN"3"7;
%"RESISTOR"
"2","(-4250,6475)","0","hdl_lib","I10";
;
VALUE"10K"
JEDEC_TYPE"0402R-S"
SN_NUM"M02.010144"
PACKAGE_TYPE"R0402"
DESCRIPTION"片式电阻10K 1% 1/16W 0402"
PART_NAME"RESISTOR_0402"
CDS_LIB"hdl_lib"
CDS_LMAN_SYM_OUTLINE"-25,50,25,-50"
LOCATION"R1"
$SEC"1"
CDS_SEC"1";
"1"
$PN"1"7;
"2"
$PN"2"6;
%"GND_POWER"
"1","(-5600,4275)","0","hdl_lib","I27";
;
CDS_LMAN_SYM_OUTLINE"-50,0,50,-50"
CDS_LIB"hdl_lib"
HDL_POWER"GND_POWER"
BODY_TYPE"PLUMBING";
"GND"2;
%"VCC_CIRCLE"
"1","(-6450,5375)","0","hdl_lib","I28";
;
HDL_POWER"VCC_12"
CDS_LIB"hdl_lib"
SIZE"1B"
BODY_TYPE"PLUMBING"
CDS_LMAN_SYM_OUTLINE"-75,75,75,-75";
"G<SIZE-1..0> \B"1;
...
END.
```

### A.3.2 字段语义（实测推导）

| 字段 | 规则 |
|---|---|
| 第1行 | `FILE_TYPE = CONNECTIVITY;` |
| 第2行 | `{Allegro Design Entry HDL 16.6-S115 (v16-6-112JX) <date>}`（版本字符串可任意，CIS2HDL 沿用现有） |
| 第3行 | `"PAGE_NUMBER" = <物理页码>;`（04p4 page10.csv 实测 = 15，即设计内页码） |
| 网络清单 | `<pageLocalNetId>"<显示名>";`，**0 恒为 `0"NC";`**；页码内从 1 递增。显示名规则：全局电源网带 `\g` 后缀（`GND_POWER\g`、`VCC_12\g`）；自动名网用 `UN$<page>$<CELL>$<I<k>>$<pin>`；普通命名网原样 |
| 实例头 | `%"<CELLNAME>"` 下一行 `"<symView>","(<x>,<y>)","0","hdl_lib","I<page-local>";` 再下一行 `;`。**`<symView>` = 符号视图号 sym_N（已验证：capacitor sym_1→"1"、sym_2→"2"、interface sym_4→"4"；即 con cells 第4字段）**；`(<x>,<y>)` = DEHDL 页坐标（与 csa FORCEADD 坐标一致）；`"0"` = 旋转/放置标志占位（实测恒 0）；`I<page-local>` 与 cpc 的 `pageN_i<k>` 的 k 一致 |
| 属性块 | 若干 `ATTR"value"` 行（VALUE/CDS_LMAN_SYM_OUTLINE/CDS_LIB/PART_NAME/DESCRIPTION/PACKAGE_TYPE/SN_NUM/JEDEC_TYPE/$LOCATION 或 LOCATION/CDS_LOCATION/$SEC/CDS_SEC），**最后一行以 `;` 结尾**；顺序与 csa FORCEPROP 顺序不必一致 |
| 多引脚器件引脚 | `"<pinName>"` 换行 `$PN"<pinNum>"<pageLocalNetId>;`。**pinNum 是符号引脚号**（非 terms 顺序：dc_dc terms 按字母序 bst,en,fb,gnd,in,sw，但 $PN 为 BST=1、GND=2、FB=3、EN=4、IN=5、SW=6）；pinName 是引脚名 |
| 单引脚器件 | 无 `$PN`，直接 `"<pinName>"<netId>;`：GND_POWER → `"GND"2;`；VCC_CIRCLE → `"G<SIZE-1..0> \B"1;`；MARK → `"1"0;` |
| 结尾 | `END.` |

### A.3.3 CIS2HDL 映射规则

1. 网络清单 = 该页所有网（`page.nets`），0="NC" 占位，其余按页内顺序编号（建议：电源/地网在前，其余按 NetIR 顺序）。**页内 netId 与 con 的设计级 netId 不同**——CSV 用页内编号，con 用设计级编号，二者通过网名桥接（8367 实测：csv `1"VCC_12\g"` vs con `N12 "vcc_12"` scope 2 不同号）。
2. 每个实例块：`%` + CELL 大写名；头行 symView=section；坐标 = csa FORCEADD 的 (x,y)（**必须与 csa/LASTPIN 坐标一致**）；实例引用 `I<page-local>`（页内 1..K 连续，跳过电源与否均可，但必须与 cpc 的 `pageN_i<k>` 的 k 一致）。
3. 属性：从 `inst.properties` + matched ComponentDef 取（VALUE/PART_NAME/JEDEC_TYPE/PACKAGE_TYPE/DESCRIPTION/SN_NUM），`$LOCATION`（section>1）或 `LOCATION`（section==1）用 refdes，`$SEC/CDS_SEC` 用 section，`CDS_LIB` 用 hdl_lib 名，`CDS_LMAN_SYM_OUTLINE` 从 symbol.css 的 P 指令取默认值。
4. 引脚：`inst.pin_connections` 中每个 (pinNumber→netName)；pinName 从 matched ComponentDef.pins 按 number 反查；netId = 页内编号。电源/地符号（gnd_power/vcc_circle）按单引脚格式，pinName = 引脚名（GND / `G<SIZE-1..0> \B`），属性块含 HDL_POWER/BODY_TYPE/SIZE。

## A.4 `pageN.cpc`（页面实例清单）

### A.4.1 完整结构（8367 page1.cpc + 04p4 page10.cpc 实测）

```
#ISCELL
  hdl_lib c#20size#20page *
  *
#ISCELL
  standard gnd_power *
  page15_i1
#CELL
  hdl_lib capacitor *
  page15_i10
#CELL
  hdl_lib capacitor *
  page15_i101
#ISCELL
  hdl_lib vcc_circle *
  page15_i102
#CELL
  hdl_lib resistor *
  page15_i103
...
```

### A.4.2 字段语义与映射

| 字段 | 规则 |
|---|---|
| `#ISCELL` | 页框 `c#20size#20page`（`#20`=空格转义，实例名 `*`）+ **电源符号**（gnd_power/vcc_circle，8367 用 hdl_lib 库、04p4 用 standard 库——CIS2HDL 统一用 hdl_lib） |
| `#CELL` | 普通元件（capacitor/resistor/.../mark） |
| 库名 | `hdl_lib`（或 match 的库） |
| 实例名 | `page<N>_i<page-local-k>`（与 con 实例内部名、csv 的 `I<k>` 严格一致） |
| 顺序 | 与页内实例顺序一致（8367 实测按 page-local 编号升序） |

---

# Part B：CSA 连线生成方案（P0-C）

## B.1 真实 CSA 完整结构（8367 page1.csa / 04p4 page4.csa / switch_practice page1.csa 实测）

```
FILE_TYPE = MACRO_DRAWING;
SET COLOR_WIRE YELLOW;
SET COLOR_PROP ORANGE;          ← 8367 用 MONO，04p4/switch_practice 用 ORANGE（均可）
SET COLOR_DOT WHITE;
SET COLOR_ARC YELLOW;
SET COLOR_BODY GREEN;
SET COLOR_NOTE PURPLE;
SET PROP_DISPLAY VALUE;
SET PAGE_NUMBER P1;
[FORCEADD C SIZE PAGE..1  ... （页框，可选，可放开头也可放组件段末尾，见 switch_practice:8096）]
FORCEADD CAPACITOR..1
(-4150 6475);
FORCEPROP 1 LAST VALUE 22PF
J 0
(-4200 6400);
DISPLAY 0.851064 (-4200 6400);
PAINT ORANGE (-4200 6400);
FORCEPROP 1 LAST PATH I12
J 0
(-4150 6475);
DISPLAY 1.021277 (-4150 6475);
PAINT ORANGE (-4150 6475);
DISPLAY INVISIBLE (-4150 6475);
... CDS_LMAN_SYM_OUTLINE / CDS_LIB / PART_NAME / DESCRIPTION / PACKAGE_TYPE / SN_NUM / JEDEC_TYPE / LOCATION($LOCATION) / CDS_LOCATION / $SEC / CDS_SEC ...
FORCEPROP 2 LASTPIN (-4150 6400) $PN 1
J 2
(-4160 6410);
DISPLAY 0.808511 (-4160 6410);
PAINT ORANGE (-4160 6410);
FORCEPROP 2 LASTPIN (-4150 6525) $PN 2
J 0
(-4140 6535);
DISPLAY 0.808511 (-4140 6535);
PAINT ORANGE (-4140 6535);
[电源符号：]
FORCEADD GND_POWER..1
(-5600 4275);
FORCEPROP 3 LASTPIN (-5600 4325) SIG_NAME GND_POWER\g
J 0
(-5590 4335);
DISPLAY 0.659574 (-5590 4335);
PAINT MONO (-5590 4335);
DISPLAY INVISIBLE (-5590 4335);
FORCEPROP 1 LAST HDL_POWER GND_POWER
J 0
(-5500 4325);
DISPLAY 0.978723 (-5500 4325);
DISPLAY INVISIBLE (-5500 4325);
FORCEPROP 1 LAST BODY_TYPE PLUMBING
...
FORCEPROP 2 LAST CDS_LIB hdl_lib
...
[组件段结束 → WIRE 段：]
WIRE 16 -1 (-4250 6325)(-4250 6275);
WIRE 16 -1 (-4250 6325)(-4250 6375);
WIRE 16 -1 (-4250 6325)(-4150 6325);
WIRE 16 -1 (-4850 6325)(-4250 6325);
...
[网络名标签（每网一个，放 WIRE 段中或段后）：]
FORCEPROP 2 LAST SIG_NAME VDD_105
J 0
(-3410 6685);
DISPLAY 1.021277 (-3410 6685);
PAINT ORANGE (-3410 6685);
[DOT 段（T 型/十字交叉点）：]
DOT 1 (-4250 6325);
DOT 1 (-3450 6675);
...
QUIT
```

### B.1.1 结构顺序规则（实测）

1. **组件段**：每个实例一个 FORCEADD 块，块内先属性 FORCEPROP，再所有引脚的 LASTPIN（`$PN` 或 `SIG_NAME`）。8367 实测：**每个已连接引脚都有 LASTPIN**（59 个 $PN）；每个网**恰好一个 SIG_NAME 标签**——信号网在源引脚处 `FORCEPROP 2 LASTPIN (pin) SIG_NAME UN$...`，电源网在电源符号引脚处 `FORCEPROP 3 LASTPIN (pin) SIG_NAME GND_POWER\g`，显式命名网在 WIRE 上 `FORCEPROP 2 LAST SIG_NAME VDD_105`。
2. **WIRE 段**：所有 `WIRE 16 -1 (x1 y1)(x2 y2);` 集中在组件段之后（8367/switch_practice 实测）。**16 = 黄色信号线**；`-1` = 线宽/样式占位恒 -1。
3. **DOT 段**：`DOT 1 (x y);` 在 WIRE 之后、QUIT 之前。
4. **QUIT** 收尾。

### B.1.2 LASTPIN 规则（实测）

| 类型 | 格式 | 显示行 | 颜色 | 证据 |
|---|---|---|---|---|
| 普通引脚 | `FORCEPROP 2 LASTPIN (x y) $PN <n>` + `J 2` + `(x-10 y+10);` + `DISPLAY 0.808511` + `PAINT ORANGE` | 8367:75-79 | 橙色 | 8367/04p4 |
| 信号网名（引脚处） | `FORCEPROP 2 LASTPIN (x y) SIG_NAME <net>` + `J 0` + `(x+10 y+10);` + `DISPLAY 0.659574` + `PAINT MONO` + `DISPLAY INVISIBLE` | 8367:64-69 | MONO | 8367/04p4 |
| 电源网名（电源符号引脚处） | `FORCEPROP 3 LASTPIN (x y) SIG_NAME <net>\g` + `J 0` + `(x+10 y+10);` + `DISPLAY 0.659574` + `PAINT MONO` + `DISPLAY INVISIBLE` | 8367:1594 | MONO | 8367/04p4/switch_practice |
| 显式网名（WIRE 上） | `FORCEPROP 2 LAST SIG_NAME <net>` + `J 0` + `(midX midY);` + `DISPLAY 1.021277` + `PAINT ORANGE` | 8367:2913-2917 | 橙色 | 8367 |

> 注意：SIG_NAME 放**引脚处**时坐标 = 引脚坐标 = WIRE 端点；放 **WIRE 上**时坐标 = 线段中点。每个网只打一个标签。

### B.1.3 WIRE 拓扑规则（04p4 page4.csa:4913-4974 实测）

真实布线 = **水平主干 + 垂直支线（bus/trunk 拓扑）**，端点落在引脚坐标上：

```
WIRE 16 -1 (2650 4875)(2650 4850);   ← 引脚 A（GND_POWER 符号，pin 在 (2650,4850)）竖直连到主干 y=4875
WIRE 16 -1 (2775 4875)(2650 4875);   ← 主干水平延伸
WIRE 16 -1 (2650 4975)(2650 4875);   ← 主干竖直延伸到引脚 B (2650,4975)
WIRE 16 -1 (2900 4875)(2775 4875);   ← 主干继续延伸
WIRE 16 -1 (2775 4975)(2775 4875);   ← 引脚 C 竖直连到主干
WIRE 16 -1 (3025 4875)(2900 4875);
WIRE 16 -1 (2900 4975)(2900 4875);
WIRE 16 -1 (3025 4975)(3025 4875);
```

- 同网多引脚通过一条**公共主干**互联（主干 y 或 x 取各引脚的中值/众数，避开器件体）。
- 端点必须与 LASTPIN 坐标完全重合（Cadence 靠几何重合判定连接）。
- DOT 放在 ≥3 段交汇/主干 T 型点（8367 DOT 坐标全部是 WIRE 交汇点，如 (-4250 6325)）。

## B.2 引脚坐标来源（关键设计决策）

**结论（实测验证）：引脚偏移的唯一权威来源 = hdl_lib 符号的 `symbol.css` 的 `C` 指令。**

```
;; hdl_lib/capacitor/sym_1/symbol.css
C 0 -75 "1" 0 -60 0 0 32 1 R    → pin "1" 相对体中心 (0, -75)
C 0 50 "2" 0 35 0 0 32 1 L      → pin "2" 相对体中心 (0, +50)
;; hdl_lib/dc_dc/sym_1/symbol.css
C 200 -150 "FB" ...  C -200 150 "IN" ...  C -200 -150 "GND" ...  C -200 0 "EN" ...  C 200 0 "SW" ...  C 200 150 "BST" ...
;; hdl_lib/gnd_power/sym_1/symbol.css
C 0 50 "GND" ...                 → GND_POWER 引脚 (0, +50)
;; hdl_lib/vcc_circle/sym_1/symbol.css
C 0 -50 "G<SIZE-1..0>" ...       → VCC_CIRCLE 引脚 (0, -50)
```

**与真实 CSA 坐标对拍（8367 page1.csa）：**
- CAPACITOR I12 体 (-4150,6475)：pin1 (-4150,6400) = (0,-75) ✓，pin2 (-4150,6525) = (0,+50) ✓
- DC_DC I1 体 (-5350,6675)：EN (-5550,6675) = (-200,0) ✓，BST (-5150,6825) = (200,150) ✓
- GND_POWER I27 体 (-5600,4275)：pin (-5600,4325) = (0,+50) ✓
- VCC_CIRCLE I28 体 (-6450,5375)：pin (-6450,5325) = (0,-50) ✓

**规则：`LASTPIN 坐标 = 实例体坐标 + 符号引脚偏移(symbol.css C 指令)`。** 实例体坐标 = csa FORCEADD 的 (x,y)（即现有 `_map_coords_to_dehdl` 或页内布局的输出，全页统一）。若 symbol.css 缺失/无 C 指令，兜底启发式：

| 器件类别 | 兜底引脚偏移 |
|---|---|
| 2 引脚无源件（cap/res/ind/diode/led） | `(0,±75)`（sym_1 竖直）或 `(±75,0)`（sym_2 水平，按 section 判断） |
| 电源符号 gnd_power | `(0,+50)` |
| 电源符号 vcc_circle | `(0,-50)` |
| 多引脚 IC | 按引脚数在矩形周界均布：每边引脚间距 100，从体中心外扩 150；`CDS_LMAN_SYM_OUTLINE` 可作参考 |
| mark | `(0,0)`（单引脚，接 NC） |

## B.3 坐标换算（Part B 关键问题，实测结论）

**问题：EDIF `(pt x y)` 与 CSA `(x y)` 是否同单位同原点？**

**实测数据对比（HG5015 vs 8367/04p4）：**

| 来源 | 坐标样例 | 量级 |
|---|---|---|
| HG5015 EDIF 实例 transform origin | C106 = `(pt 1040 -560)`；页框 `(pt 0 -1169)(pt 1654 0)` | 百~千级，页 ~1654×1169 |
| HG5015 CrossRef CSV（Capture 交叉参考） | C106 = `X 255.00 Y 140.00` | 与 EDIF 约 4 倍关系（Y 反号），页坐标 mil 级 |
| 8367 CSA（C 纸） | 组件 -6450..-3050 x，3625..6975 y | 千级，C 纸 -10750..0 × 0..8275 |
| 04p4 CSA（B/A 纸） | 组件 2000..5950 x，3350..7275 y | 千级 |
| switch_practice CSA（无页框） | 组件 -2375..4825 x，0..3125 y | 千级，坐标原点任意 |

**结论：三者互不同原点、不同单位。EDIF pt ≈ CrossRef × 4（Y 反号）**，但均与 DEHDL C 纸（-10750..0 × 0..8275）无固定换算——DEHDL 页面大小取决于页框符号。

**因此 CSA 几何的正确策略不是"还原 Capture 坐标"，而是"自洽"：**
1. 实例体坐标沿用现有 `_map_coords_to_dehdl`（把 CrossRef 坐标按页 bbox 适配进 C 纸可用区）——**全页统一一个仿射变换**，避免每实例独立缩放破坏相对位置。
2. 引脚坐标 = 体坐标 + symbol.css 偏移（B.2）——**保证 LASTPIN 与 FORCEADD 相对关系正确**。
3. WIRE 端点 = 引脚坐标（拓扑合成），**保证 WIRE 与 LASTPIN 严格重合**——这是 Cadence 判定连接的唯一几何依据。
4. EDIF figure WIRE polyline（`WireSegment.points`）作为**可选几何参考**：若未来要复现原图走线，用与实例相同的仿射变换映射 polyline 后**吸附到最近的引脚坐标**；默认不依赖它（拓扑合成已自洽）。

## B.4 拓扑合成算法（wire_layout 模块）

对每个网（按页内网序）：

1. **收集引脚点集** P = {p_i}（该页上该网所有已连接引脚坐标），去重。
2. 若 |P| < 2：不画线（单引脚网仅在引脚处打 SIG_NAME；NC 不打）。
3. **主干选择**：统计引脚坐标的众数 y（若各引脚 y 分散）取中值，向下取整到 25 的倍数（DEHDL 网格对齐），作为水平主干 y_trunk；若 |P| 中 x 更分散则用垂直主干。**避开器件体**：若主干 y 落入某器件 CDS_LMAN_SYM_OUTLINE 的 y 范围内，则偏移到 outline 外侧 +50。
4. **生成 WIRE 段**（以水平主干为例）：
   - 对每个引脚 p_i=(x_i,y_i)：若 y_i != y_trunk，输出 `WIRE 16 -1 (x_i y_i)(x_i y_trunk);`（垂直支线）
   - 主干段：`(minX y_trunk)(maxX y_trunk);` 分段输出（每 1000 一段或按途经引脚分段均可；实测为分段小段）
   - 输出顺序：8367 实测为"从一端向另一端"，任意稳定顺序均可。
5. **DOT 生成**：所有满足"≥3 段端点/内部相交"或"两段端点重合且非同一段"的交点 → `DOT 1 (x y);`。简化规则：主干上每个有支线接入的点 + 主干端点若有 2 条支线 → DOT；另有 8367 实测 DOT 也在**两段端点相连的拐点**（如 (-3450 6675)）。**保守规则：凡 ≥2 段相交即打 DOT**（多余 DOT 无害，缺失会断连）。
6. **SIG_NAME 标签**：每网一个。优先放"源引脚"（电源符号引脚 / 自动名网取第一个引脚）；若引脚处已由该网的其他引脚打标签则放 WIRE 中点 `FORCEPROP 2 LAST SIG_NAME`。

**IOPORT/跨页端口（P0-C5）**：`page.off_pages`（EDIF `OFF_PAGE_CONNECTOR` portRef）→ 若页上该网无电源符号引脚，在网的中点为该跨页网生成 `FORCEPROP 2 LAST SIG_NAME <net>` 标签即可（跨页连接由 con/xcon 的 netScopes/aliases 保证）；不强制放置 IOPORT 符号（DEHDL 可用 SIG_NAME 表达跨页网名）。电源/地网 `\g` 后缀在 SIG_NAME 中保留（`GND_POWER\g`），并在 csv 网络清单同步。

## B.5 csa_writer 改造点

现有 `CSAWriter._build_csa_content`（cis2hdl/core/writer/csa_writer.py）保留 FORCEADD/FORCEPROP 属性生成，**新增**：
1. `_build_lastpin_section(page, coord_map)`：对每个实例每个已连接引脚生成 LASTPIN `$PN`；对每个网生成一个 SIG_NAME 标签（引脚处或 WIRE 上）。
2. `_build_wire_section(page, pin_coords)`：调用 `WireLayoutEngine.route(net_pin_map)` 输出 WIRE 段。
3. `_build_dot_section(page)`：输出 DOT 段。
4. 引脚偏移解析：新增 `SymbolCssPinParser`（复用/扩展 `cis2hdl/core/parser/symbol_css.py` 解析 `C x y "name"`）。
5. FORCEADD 坐标统一走 `CoordTransform`（体坐标），LASTPIN/WIRE 同源。

---

# Part C：实现顺序、文件清单与验收断言

## C.1 实现顺序（依赖链）

```
P0-A2（EDIF page 块解析，已有基础）
  → T01 基础设施（net_utils 网络名清洗 + coord_transform + wire_layout + symbol_css 引脚解析）
  → T02 con/xcon 重构（设计级）
  → T03 csv/cpc 生成（页级）
  → T04 csa 连线生成（LASTPIN/WIRE/DOT）
  → T05 主链集成 + DSN 源禁用 + 验收
```

## C.2 文件清单（改动/新增）

| 文件 | 动作 | 职责 | 归属任务 |
|---|---|---|---|
| `cis2hdl/core/net_utils.py` | 扩展 | 网络名清洗：`con_name()`（小写/$→_/去\g/pageN_前缀）、`csv_display_name()`（\g/UN$ 还原）、`auto_net_name()`（unnamed_/UN$ 双向）、网分类 | T01 |
| `cis2hdl/core/writer/coord_transform.py` | 新增 | `CoordTransform`：CrossRef/EDIF 坐标 → DEHDL C 纸坐标（统一仿射，替换/包装现有 `_map_coords_to_dehdl` 逻辑，供 csa/csv 共用） | T01 |
| `cis2hdl/core/writer/wire_layout.py` | 新增 | `WireLayoutEngine`：路由（B.4 拓扑合成）+ DOT 计算 + SIG_NAME 标签定位 | T01 |
| `cis2hdl/core/parser/symbol_css.py` | 扩展 | `SymbolCssPinParser`：解析 `C x y "pinname"` 引脚偏移 + outline | T01 |
| `cis2hdl/core/writer/con_writer.py` | 新增 | `ConWriter`：按 A.1 生成 `<cell>.con`（cells/nets/instances/lastIds） | T02 |
| `cis2hdl/core/writer/xcon_writer.py` | 重写 | `XconWriter`：按 A.2 生成 `<cell>.xcon`（含 aliases/netScopes/pages） | T02 |
| `cis2hdl/core/writer/output_manager.py` | 修改 | `write_con_file`/`write_xcon` 委托 ConWriter/XconWriter；新增 `write_csv_page()`；`write_cpc_file` 扩展为全量组件 | T02/T03 |
| `cis2hdl/core/writer/csv_writer.py` | 新增 | `PageCsvWriter`：按 A.3 生成 `pageN.csv` | T03 |
| `cis2hdl/core/writer/cpc_writer.py` | 重写 | `CpcWriter`：按 A.4 生成 `pageN.cpc`（#CELL/#ISCELL 全量） | T03 |
| `cis2hdl/core/writer/csa_writer.py` | 改造 | 按 B.5 增加 LASTPIN/WIRE/DOT/SIG_NAME；FORCEADD 坐标走 CoordTransform | T04 |
| `cis2hdl/core/engine/conversion_engine.py` | 修改 | 编排：EDIF→IR→(T01-T04 writers)；新增 DSN 元件源禁用开关 | T05 |
| `cis2hdl/core/config.py` | 修改 | 新增 `use_dsn_components=False`、`emit_csa_wires=True` 等开关 | T05 |
| `tests/e2e/test_phase_xi_p0.py` | 新增 | 全链验收断言（C.4） | T05 |

## C.3 任务分解（≤5，按依赖）

### T01：P0-A2 基础设施 — net_utils/coord_transform/wire_layout/symbol_css
- **Source Files**：`net_utils.py`、`coord_transform.py`（新）、`wire_layout.py`（新）、`symbol_css.py`
- **Dependencies**：无
- **Priority**：P0
- **验收**：单测通过——`con_name("GND_POWER\\g", page=1, local=True) == "page1_gnd_power"`；`auto_net_name("UN$1$CAPACITOR$I12$1") == "unnamed_1_capacitor_i12_1"`；wire_layout 对 3 引脚网输出"2 支线 + 1 主干 ≥3 段"且端点==引脚；symbol_css 解析 capacitor 得 {1:(0,-75), 2:(0,50)}。

### T02：P0-B1 con/xcon 重构（设计级连通性）
- **Source Files**：`con_writer.py`（新）、`xcon_writer.py`（重写）、`output_manager.py`
- **Dependencies**：T01
- **Priority**：P0
- **验收**：con 可被 S-Expr 解析；`cells 数 == 唯一(cell,section) 数`；`nets 数 == 设计级唯一网数（HG5015 应 == 590）`；`conn 数 == 引脚连接总数（HG5015 应 == 2821）`；lastIds 与计数一致；电源符号不在 cells/instances；xcon aliases/netScopes/pages 与 con 交叉一致（每页 nets/instances ref 均在 con 中存在）。

### T03：P0-B2 csv/cpc 生成（页级）
- **Source Files**：`csv_writer.py`（新）、`cpc_writer.py`（重写）、`output_manager.py`
- **Dependencies**：T01（命名规则）；T02（实例 I-id/page-local k 约定）
- **Priority**：P0
- **验收**：每页生成 `pageN.csv` 以 `FILE_TYPE = CONNECTIVITY;` 开头、`END.` 结尾；`0"NC";` 存在；每个实例块有 `$PN` 或单引脚格式且 netId 在页内网络清单范围内；`pageN.cpc` 的 `pageN_i<k>` 与 csv 的 `I<k>`、con 实例内部名三方一致；页内网络清单与 csa SIG_NAME 命名一致。

### T04：P0-C csa 连线生成
- **Source Files**：`csa_writer.py`、`symbol_css.py`、`wire_layout.py`、`coord_transform.py`
- **Dependencies**：T01、T03（网络命名一致）
- **Priority**：P0
- **验收**：CSA 含 `WIRE 16 -1`（数量 ≥ 拓扑段数）；每已连接引脚有 LASTPIN；**每个 WIRE 端点坐标与某 LASTPIN 坐标重合**（自动校验：端点集合 ⊆ 引脚坐标集合）；每网恰一个 SIG_NAME 标签（电源网带 `\g`）；DOT 在 ≥2 段交点；`QUIT` 结尾。

### T05：P0-D2 主链集成 + DSN 禁用 + 全链验收
- **Source Files**：`conversion_engine.py`、`config.py`、`tests/e2e/test_phase_xi_p0.py`（新）
- **Dependencies**：T02、T03、T04
- **Priority**：P0
- **验收**：`use_dsn_components=False` 时主链 = EDIF + CrossRef CSV + pstxnet（pstxnet 仍作 pin→net 主注入，DSN 仅用于辅助坐标，不提供元件）；输出目录文件齐全（con/xcon/csv/cpc/csa）；**全链断言见 C.4**。

## C.4 验收断言（端到端，HG5015）

```
A1. con (nets) 条目数 == 590（== pstxnet NET_NAME 数）
A2. con (pins) conn 总数 == 2821（== pstxnet NODE_NAME 数）
A3. con (instances) 数 == 906（== pstxnet 唯一 refdes 数；电源符号除外后≈实际）
A4. 每个 pageN.csv：0"NC"; 存在；每实例块有 $PN 映射；最后一个 netId < 页内网数；END. 结尾
A5. 每个 pageN.csa：含 WIRE 16 -1；所有 WIRE 端点 ∈ 该页 LASTPIN 坐标集；QUIT 结尾
A6. xcon 与 con 的 nets/instances/cells 双向一致（ID 与内部名可互相解析）
A7. cpc 实例名 pageN_i<k> 与 con 实例内部名、csv I<k> 一致
A8. 关键文件可被 Cadence S-Expr/XML 解析器解析（tests 用 Python s-expression/xml 解析断言）
A9. 转换报告无 fatal error；输出文件清单包含全部 4 类文件
```

## C.4b 配套小文件格式（实测修正）

| 文件 | 真实格式（8367/04p4 实测） | 当前实现问题 | 修正 |
|---|---|---|---|
| master.tag | 每行一个文件名：`pageN.csa` 按页 + `<cell>.xcon` + `<cell>.dcf`（**不列 .cpc**；04p4 实测新页追加在末尾） | 当前多列了 `pageN.cpc` | 去掉 cpc 行，csa 按页序 + xcon + dcf |
| page.map | 8367 实测 0 字节 | 当前写 `1 1 name` | 可保留现状（无危害）；如需完全对齐可写空 |
| module_order.dat | `@\\<lib>\\.\\<cell>\\(sch_1)\t0\t1\t1\t3\t0\t`（反斜杠转义 + 末字段 3） | 当前 `@lib.cell(sch_1)\t...\t2\t`（无反斜杠、末字段 2） | 改为 `@\\<lib>\\.\\<cell>\\(sch_1)\t0\t1\t1\t3\t0\t` |
| hdldirect.dat | `(HDLDirect (Version 16.6) (Design "cell"))` | 基本一致 | 保持 |

## C.5 共享约定（Shared Knowledge）

- **网络命名三态**：CSV 显示名（`GND_POWER\g` / `UN$1$...` / 原样）、con 内部名（小写 `$→_` 去 `\g`，局部加 `pageN_`）、SIG_NAME（与 CSV 显示名一致）。三者由 `net_utils` 统一生成，任何 writer 不得自行拼名。
- **ID 三套**：设计级（con/xcon：I/N/M/S/T）、页级网络（csv：0..K，0=NC）、页级实例（csv `I<k>` + cpc `pageN_i<k>` + con 内部名）。页级实例编号**每页从 1 连续**，设计级 I-id 跨页连续。
- **坐标唯一原则**：一个实例只有一个"体坐标"，由 `CoordTransform` 输出；LASTPIN/WIRE/csv 头行坐标全部由"体坐标 + symbol.css 偏移"派生，禁止独立计算。
- **电源符号特例**：gnd_power/vcc_circle 不进入 con cells/instances，但进入 csv/cpc（#ISCELL）/csa（FORCEADD + LASTPIN SIG_NAME）；其网在 con 中 scope=2 全局（带 `\g` 时）或局部 pageN_ 网（8367 两种都存在，以是否跨页为准）。
- **换行**：worklib 下所有文件 CRLF（`OutputManager._write_worklib_file` 已处理）。
- **编码**：CSA/CSV/CPC/CON/XCON 均 ASCII/UTF-8（属性值中文需转义处理，参考 8367 中文 DESCRIPTION 直接 UTF-8）。

## C.6 风险与未决项

1. **引脚号 vs 引脚名**：con terms 用 pinName；csv `$PN` 用 pinNumber；symbol.css C 指令用 pinName 匹配。若 matched ComponentDef 的 pin number↔name 映射缺失（如 pstxnet 用 label 'A'），需 pstchip 的 label→number 映射补齐（现有 Stage 5.5c 已做）。**未决：少数符号 css 引脚名与 ComponentDef 引脚名不一致时，以 css 为准并记录 warning。**
2. **符号视图号 sym_N**：csv 头行第 1 字段与 con cell 的 sym_N 必须一致。CIS2HDL 的 section 字段默认 1，多 section 器件需确认 ComponentDef.section_pin_maps 与 css 目录 `sym_<section>` 存在。
3. **DOT 保守策略**：在 ≥2 段交点打 DOT 可能比真实 Cadence 多（8367 实测 27 个 DOT / 94 WIRE，比例约 0.29；保守策略比例可能更高），多余 DOT 无害。
4. **EDIF WIRE polyline 复用**：本期默认拓扑合成；若后续要还原原图走线，通过 `CoordTransform` + 端点吸附实现（已在 wire_layout 预留接口）。
5. **aliases 生成**：8367 实测 alias 只覆盖"局部电源网→全局网"。CIS2HDL 若全局网判定过宽（所有 POWER 网都跨页），可能生成多余 alias；规则收敛为"该网在 ≥2 页出现且分类为 POWER/GROUND 才建全局网 + alias"。
