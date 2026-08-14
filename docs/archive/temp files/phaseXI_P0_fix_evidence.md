# Phase XI P0 修复 — 真实工程格式证据（8367 / 04p4 / HG5015 实测）

> 配套 docs/phaseXI_P0_fix_design.md。所有片段均来自真实文件：
> - 8367: `docs_for_reference/OrCAD_files_references/cis_for_reference/worklib/8367/sch_1/`
> - 04p4: `docs_for_reference/previous_switch_programme/交换机练习/OSJZX-6100F-RTK/.../worklib/04p4/sch_1/`
> - HG5015: `tests/fixtures/HG5015test/`

---

## 1. 电源符号 — CSV 块（8367 page1.csv L360-376）

### GND_POWER（L360-367）
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
### VCC_CIRCLE（L368-376）
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
要点：无 VALUE / PART_NAME / LOCATION；必含 HDL_POWER（=电源网名，无 \g）+ BODY_TYPE"PLUMBING"；VCC_CIRCLE 另有 SIZE"1B"；单引脚行 `"<引脚名>"<网ID>;`；实例行 `"1","(x,y)","0","hdl_lib","I<k>";`（1=引脚数）。GND_POWER 网名 `2"GND_POWER\g"`、VCC_12 网名 `1"VCC_12\g"`（网列表 L4-21）。

### 8367 page1.csv 网列表（L4-21，UN$ 证据）
```
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
10"UN$1$CAPACITOR$I8$2";
11"UN$1$CAPACITOR$I23$2";
12"UN$1$CAPACITOR$I8$1";
13"UN$1$DCDC$I1$EN";
14"UN$1$CAPACITOR$I23$1";
15"UN$1$DCDC$I24$EN";
16"VCC_12";
17"UN$1$DIODE$I31$1";
```
UN$ 规则：`UN$<page>$<CELL>$I<k>$<pin_name>`（pin 段=符号引脚名：EN/1/2）。

### 8367 page1.csv 实例引脚与 UN$ 网对应（L85-102，CAPACITOR I12）
```
%"CAPACITOR"
"1","(-4150,6475)","0","hdl_lib","I12";
;
VALUE"22PF"
...
LOCATION"C12"
...
"2"
$PN"2"6;
"1"
$PN"1"7;
```
网 7 = `UN$1$CAPACITOR$I12$1` → I12 引脚 1（$PN"1"7）→ **UN$ I<k> 与 csv 页内编号一致**。

---

## 2. 电源符号 — CSA 块（8367 page1.csa / 04p4 page9.csa）

### 8367 page1.csa GND_POWER（L1592 起）
```
FORCEADD GND_POWER..1
(-5600 4275);
FORCEPROP 3 LASTPIN (-5600 4325) SIG_NAME GND_POWER\g
J 0
(-5590 4335);
DISPLAY 0.659574 (-5590 4335);
PAINT MONO (-5590 4335);
DISPLAY INVISIBLE (-5590 4335);
FORCEPROP 1 LAST CDS_LMAN_SYM_OUTLINE -50,0,50,-50
J 0
(-5600 4275);
DISPLAY 0.468085 (-5600 4275);
PAINT GREEN (-5600 4275);
DISPLAY INVISIBLE (-5600 4275);
FORCEPROP 2 LAST CDS_LIB hdl_lib
J 0
(-5600 4275);
PAINT ORANGE (-5600 4275);
DISPLAY INVISIBLE (-5600 4275);
FORCEPROP 1 LAST PATH I27
J 0
(-5600 4275);
DISPLAY 1.021277 (-5600 4275);
PAINT ORANGE (-5600 4275);
DISPLAY INVISIBLE (-5600 4275);
FORCEPROP 1 LAST HDL_POWER GND_POWER
J 0
(-5500 4325);
DISPLAY 0.978723 (-5500 4325);
PAINT ORANGE (-5500 4325);
DISPLAY INVISIBLE (-5500 4325);
FORCEPROP 1 LAST BODY_TYPE PLUMBING
J 0
(-5500 4425);
DISPLAY 0.978723 (-5500 4425);
PAINT ORANGE (-5500 4425);
DISPLAY INVISIBLE (-5500 4425);
```
坐标关系：LASTPIN(-5600,4325) = FORCEADD(-5600,4275) + (0,+50)（GND 引脚偏移）。

### 8367 page1.csa VCC_CIRCLE（L1629 起）
```
FORCEADD VCC_CIRCLE..1
(-6450 5375);
FORCEPROP 3 LASTPIN (-6450 5325) SIG_NAME VCC_12\g
J 0
(-6440 5335);
DISPLAY 0.659574 (-6440 5335);
PAINT MONO (-6440 5335);
DISPLAY INVISIBLE (-6440 5335);
FORCEPROP 1 LAST HDL_POWER VCC_12
J 1
(-6448 5429);
DISPLAY 0.851064 (-6448 5429);
PAINT GREEN (-6448 5429);
FORCEPROP 2 LAST CDS_LIB hdl_lib
...
```
坐标关系：LASTPIN(-6450,5325) = FORCEADD(-6450,5375) + (0,-50)（VCC 引脚偏移）。

### 04p4 page9.csa VCC_CIRCLE（L219 起，HDL_POWER=DC12V 变体）
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
J 1
(-2272 9750);
DISPLAY 0.851064 (-2272 9750);
PAINT GREEN (-2272 9750);
DISPLAY INVISIBLE (-2272 9750);
FORCEPROP 1 LAST CDS_LMAN_SYM_OUTLINE -75,75,75,-75
...
FORCEPROP 2 LAST CDS_LIB hdl_lib
...
FORCEPROP 1 LAST BODY_TYPE PLUMBING
...
FORCEPROP 1 LAST PATH I101
...
```

---

## 3. 电源符号 — CPC 块

### 8367 page1.cpc（L58-63、L100-105）
```
#ISCELL
  hdl_lib gnd_power *
  page1_i27
#ISCELL
  hdl_lib vcc_circle *
  page1_i28
...
#ISCELL
  hdl_lib vcc_circle *
  page1_i5
#ISCELL
  hdl_lib gnd_power *
  page1_i6
```
### 04p4 page9.cpc（L4-15）
```
#ISCELL
  standard gnd_power *
  page14_i1
#CELL
  hdl_lib capacitor *
  page14_i10
#ISCELL
  hdl_lib vcc_circle *
  page14_i101
```
要点：电源符号用 `#ISCELL`（普通元件 `#CELL`）；实例名 `pageN_i<k>` 与 csv `I<k>` 一致；库名跟随源（8367=hdl_lib / 04p4 GND=standard，输出统一用 conn.hdl_lib_name）。

---

## 4. UN$ 自动网名 — CON 内部名（8367.con）

### L282-292（page1 网表）
```
("N2" "page1_gnd_power" -1 -1 0 )
("N3" "unnamed_1_capacitor_i12_1" -1 -1 0 )
("N4" "unnamed_1_capacitor_i18_1" -1 -1 0 )
("N5" "unnamed_1_capacitor_i23_1" -1 -1 0 )
("N6" "unnamed_1_capacitor_i23_2" -1 -1 0 )
("N7" "unnamed_1_capacitor_i8_1" -1 -1 0 )
("N8" "unnamed_1_capacitor_i8_2" -1 -1 0 )
("N9" "unnamed_1_dcdc_i1_en" -1 -1 0 )
("N10" "unnamed_1_dcdc_i24_en" -1 -1 0 )
("N11" "unnamed_1_diode_i31_1" -1 -1 0 )
```
### L409-410（全局电源网，scope=2）
```
("N1" "gnd_power" -1 -1 2 )
("N12" "vcc_12" -1 -1 2 )
```
要点：UN$ 网 con 内部名 = `unnamed_<page>_<cell>_i<k>_<pin>`（scope=0）；电源网全局名 = 裸名小写（scope=2）+ 每页 `pageN_<name>`（scope=0）+ alias。

---

## 5. HG5015 实测数据（根因/现状证据）

### 5.1 EDIF 电源符号实例（HG5015-BE36_V10.EDF L54471）
```
(portImplementation GND
  (instance GND
    (viewRef GND
      (cellRef GND
        (libraryRef LIBRARY1)))
    (property VOLTAGE (string ""))
    (property CURRENT (string ""))
    (property POWER_TYPE (string "GND"))
    (property PINORDER (string "GND"))
    (property NETNAME (string "GND"))
    (property SINGAL (string "GND"))
    (property DEVICE (string "x"))
    (transform (origin (pt 1020 -610))))
  (connectLocation (figure PARTBODY (dot (pt 1030 -610)))))
```
EDIF cell 定义：`(cell GND ... (property CELLTYPE (string "pagePort")) ...)`（L1092）；`(cell VCC_CIRCLE ...)`（L1212）。

### 5.2 EDIF 自动网名（L54138）
```
(net
  (rename
    (name &_47N777
      (display (figureGroupOverride ALIAS ...) (origin (pt 940 -420)))) "$47N777")
  (joined
    (portRef A (instanceRef INS265))
    (portRef UPS_N_TX_N (instanceRef INS337)))
  (property DIFFERENTIAL_PAIR (string "2P5GE_TX_"))
  (figure WIRE (path (pointList (pt 1040 -420) (pt 920 -420)))))
```
EDIF 内部名 `&_47N777`、显示名 `$47N777`、连接为 page 级 INS### 占位符（P0-D2 后映射真实 refdes）。

### 5.3 pstxnet ROUTE 跳线连接（pstxnet.dat）
```
NET_NAME
'2P5GE_RSTN'
 ...
NODE_NAME	J11 2
 '@HG5015-BE36_V10.TG1C0D8_VB(SCH_1):INS6185@LIBRARY1.ROUTE.NORMAL(CHIPS)':
 'NET2':;
NODE_NAME	U7 1
 ...
NET_NAME
'HGPIO_17'
 ...
NODE_NAME	U6 B11
 ...
NODE_NAME	J11 1
 '@HG5015-BE36_V10.TG1C0D8_VB(SCH_1):INS6185@LIBRARY1.ROUTE.NORMAL(CHIPS)':
 'NET1':;
```
J11 = 2 引脚，引脚键 1/2，分别连 HGPIO_17 / 2P5GE_RSTN。

### 5.4 当前输出问题现状
- `output/worklib/5015/sch_1/5015.con`：`("N148" "21n109399" -1 -1 0)`（数字开头自动网名）；电源网 `("N55" "gnd" -1 -1 2)` + `pageN_gnd` 局部 + alias 完整。
- `output/worklib/5015/sch_1/page14.csv`：网列表 `1"$21N109399";`、`122"GND\g";`；**无 %"GND"/%"VCC_CIRCLE" 符号块**。
- `output/worklib/5015/sch_1/page14.csa` / `.cpc`：无 GND/VCC_CIRCLE 符号。
- pstxnet 统计：915 refdes、590 唯一网、166 个 $ 自动网、25 个 ROUTE 跳线（50 次 ROUTE.NORMAL）。
- CrossRef CSV：914 条（含 25 ROUTE）；catalog 跳过后 889 = 当前 con instances。

---

## 6. hdl_lib 电源/电阻符号定义（output/hdl_lib/）

### gnd_power/sym_1/symbol.css（节选）
```
P "CDS_LMAN_SYM_OUTLINE" "-50,0,50,-50" 0 0 ...
P "HDL_POWER" "GND_POWER" 100 50 ...
P "BODY_TYPE" "PLUMBING" 100 150 ...
P "PATH" "?" 0 0 ...
L 0 50 0 0 -1 0
C 0 50 "GND" ...        ← 引脚 (0,+50)，名 GND
```
### vcc_circle/sym_1/symbol.css（节选）
```
P "CDS_LMAN_SYM_OUTLINE" "-75,75,75,-75" 0 0 ...
P "HDL_POWER" "VCC_circle" 2 54 ...
P "BODY_TYPE" "PLUMBING" 125 -1 ...
P "PATH" "?" -148 100 ...
P "SIZE" "1B" -147 0 ...
L 0 -50 0 0 -1 0
C 0 -50 "G<SIZE-1..0>" ...   ← 引脚 (0,-50)，名 G<SIZE-1..0>
```
### resistor/sym_1/symbol.css（节选）
```
P "CDS_LMAN_SYM_OUTLINE" "-50,25,50,-25" 0 0 ...
C 100 0 "2" ...          ← 引脚 2 (100,0)
C -100 0 "1" ...         ← 引脚 1 (-100,0)
```
hdl_lib 无 jumper / route_jumper 符号 → ROUTE 跳线映射 resistor。
