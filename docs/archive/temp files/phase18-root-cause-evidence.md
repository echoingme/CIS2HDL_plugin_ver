# Phase XVIII 实测问题根因证据（主理人现场核实，2026-08-12）

> 本文档由主理人齐活林基于用户 Cadence 16.6 实测报告 + 源码/输出文件现场比对产出。
> 所有结论均为**代码级/文件级证据**，供产品经理 PRD、架构师设计、工程师实施直接引用。

---

## 1. SPCOCN-1158 mock symbol.css line 12 parse error（芯片消失根因）🔴

### 现象
`temp_lib/u6c_ph/sym_1/symbol.css: error on line 12: parse error`，U6C/U6D/U6B/U5/U6F/U8/U9 全部无法加载 → 芯片消失，只剩标签+悬空电线。

### 证据
**mock 生成（v1_default/temp_lib/U6C_PH/sym_1/symbol.css line 12）**：
```
L -735 725 -725 725 -1 0
C -725 725 "T12" -725 740 0 0 32 1 U        ← line 12，justify=U
```
**真实库全量统计**：`grep "^C " hdl_lib --include=symbol.css | awk '{print $NF}'`：
```
33987 R
31694 L
```
→ **全库 65689 条 C 指令 justify 只有 R/L，U/D 不存在**。mock 用了 U（top）/D（bottom）→ parse error。

### 真实 C 指令格式（ch347 sym_1）
```
C -300 -250 "RST#" -325 -250 0 1 32 0 R
```
字段：`C <x> <y> "<pinname>" <label_x> <label_y> <orient> <vis?> <fontsize> <??> <justify>`
- capacitor: `C 0 -75 "1" 0 -60 0 0 32 1 R`（orient=0, 第8参=0, 字号=32, 第10参=1）
- ch347: `C -300 -250 "RST#" -325 -250 0 1 32 0 R`（第8参=1, 字号=32, 第10参=0）
- 真实库还有 **X "PIN_TEXT" 指令** 显示可见引脚名：`X "PIN_TEXT" "XTAL2" -380 640 0 0 29 0 0 0 0 0 1 0 0`（1337 个符号含此指令）

### 修复方向
1. mock 引脚 C 指令 justify 只允许 R/L（左右边）——顶部/底部引脚需要重新设计（或按 04p4/golden 实际做法）
2. 补 X "PIN_TEXT" 可见引脚名（与真实库一致）
3. 全量 mock cell 重新生成 + 语法校验（正则校验 C 指令 justify ∈ {R,L}）

---

## 2. SPCOCN-515 库缺失（temp_lib 手动添加后仍找不到）🔴

### 现象
`U6C_PH.SYM.1.1 / J4_PH.SYM.1.1 找不到`；报错路径 `temp_lib\u6c_ph`（小写）vs FORCEADD `U6C_PH`（大写）。

### 证据
**真实库 master.tag 内容**（capacitor cell）：
```
sym_1/master.tag     = "symbol.css"     (xxd: 7379 6d62 6f6c 2e63 7373 0a)
chips/master.tag     = "chips.prt"
entity/master.tag    = "verilog.v"
cell 根目录          = 无 master.tag
```
**mock 生成**：全部 master.tag = `"CDS_SYSTEM"`（write_to_temp_lib L408：`tag.write_text("CDS_SYSTEM\n")`）→ **内容错误**，Cadence 无法识别 cell 视图类型。

**真实库 cell 结构**：`cell/{chips, entity, metadata, part_table, sym_1..N}`；entity 含 `{master.tag, pc.db, verilog.v, vhdl.vhd, vlog004u.sir}`。
**mock 结构**：`cell/{sym_1, chips, entity}`，缺 metadata/part_table/vlog_mode；entity 只有 `{master.tag, pc.db}`。

### 修复方向
1. master.tag 内容对齐真实库：sym_1→`symbol.css`、chips→`chips.prt`、entity→`verilog.v`
2. 目录大小写：FORCEADD 用 `U6C_PH`（大写）→ 目录保持大写即可（Windows 不敏感，macOS/Linux 敏感，但 Cadence 在 Windows 报错是小写显示，非根因）
3. 补 entity/verilog.v + vhdl.vhd + vlog004u.sir（最小 ASCII 声明）

---

## 3. SPCOCN-543 $PN/SPN/SIG_NAME 被删（最大共性问题）🔴

### 现象分层
| 子类 | 报错 | 影响页 |
|------|------|--------|
| 普通 CAPACITOR $PN 1/2 | SPN value 1/2 deleted | p5/6/7/10/11/19/20/22/23 每页 10+ |
| BGA mock 芯片 SPN | AC13/AB18/AD15/L9 等坐标名 deleted | p8/12/13/14/16/17 |
| GND_POWER SIG_NAME | GND\g / GND_POWER\g deleted | p18 + test_spn g4 |
| PQ2016 $PN | 3/4/2/1 deleted | p21 |
| UN$ 自动网名 SIG_NAME | UN$5SCAPACITORSI43$2 deleted | p5/19/20 |

### 证据 3.1 —— CAPACITOR（golden vs 我们）
**golden 04p4 page9**：
```
FORCEADD CAPACITOR..1
(-2875 3325);
FORCEPROP 2 LASTPIN (-2875 3375) $PN 2      ← body+(0,50)，精确命中 symbol.css
R 1
J 0
FORCEPROP 2 LASTPIN (-2875 3250) $PN 1      ← body+(0,-75)，精确命中 symbol.css
```
**我们生成的（v1 page5）**：
```
FORCEADD CAPACITOR..1
R 2                                              ← 旋转 180°
(-8125 4225);
FORCEPROP 2 LASTPIN (-8125 4300) $PN 1          ← 数学正确（旋转后）
FORCEPROP 2 LASTPIN (-8125 4175) $PN 2
```
→ **golden 无 R 行（R 1 默认），我们是 R 2 旋转**。坐标数学正确但 Cadence 仍删 → **旋转 R 行 + LASTPIN 组合是根因嫌疑**（phase17-problem-list.md L78 已记录"仅旋转实例(R 2/R 3)仍删 SPN/SIG_NAME，R 行+LASTPIN 组合无 04p4 先例"）。
04p4 page11 RESISTOR 也是 R 1（无旋转）。04p4 旋转先例仅 VCC_CIRCLE R 4（page12，电源符号）。

### 证据 3.2 —— GND_POWER（golden vs 我们 vs g4 模板）
**golden 04p4 page9 L10-17**：
```
FORCEADD GND_POWER..1
(-3725 3075);
FORCEPROP 3 LASTPIN (-3675 3175) SIG_NAME GND_POWER\g
J 0
(-3665 3185);
DISPLAY 0.659574 (-3665 3185);
PAINT MONO (-3665 3185);
DISPLAY INVISIBLE (-3665 3185);
```
→ LASTPIN 坐标 = FORCEADD + (50,100)，SIG_NAME 值 = `GND_POWER\g`（**带 \g 后缀**）

**我们生成的（v1 page18）**：
```
FORCEADD GND_POWER..1
(-9475 7100);
FORCEPROP 3 LASTPIN (-9475 7050) SIG_NAME GND\g   ← body+(0,-50)，SIG_NAME=GND\g
```
→ 我们 LASTPIN = body+(0,-50)；golden = body+(50,100)。**offset 不一致**（gnd_power symbol.css 引脚在 (0,50)，rotate_point 镜像后变 (0,-50)？）

**test_spn_g4 模板（用户实测报错）**：
```
FORCEADD GND_POWER..1
(-3675 3175);
FORCEPROP 3 LASTPIN (-3675 3175) SIG_NAME GND_POWER\g   ← FORCEADD 与 LASTPIN 同坐标
```
→ g4 模板 LASTPIN offset = (0,0)，**未命中任何 symbol 引脚** → 报错。

### 证据 3.3 —— BGA mock SPN
mock BGA 引脚 C 指令偏移 = 发射坐标必须严格一致；当前 U6B/U5 等 SPN 被删 → 与 1158（cell 未加载）同源，CSS 修复后自愈。

### 修复方向
1. CAPACITOR/被动元件：**旋转实例改用 sym_N 视图**（capacitor..2 横向视图，golden page9 L354 先例 `FORCEADD CAPACITOR..2`）或 R 行+旋转后坐标严格对齐 symbol.css 引脚 offset 并 A/B 验证
2. GND_POWER：LASTPIN offset 与 golden 对齐（(50,100) 或确认 symbol.css 引脚后精确命中）；SIG_NAME 值格式确认
3. 全量 LASTPIN 坐标命中 symbol.css 引脚校验（已有 `_pin_offset_resolves`，需核对旋转分支）

---

## 4. ORIGIN.SYM.1.1 缺失 + attributes "?" 🔴

### 现象
C423 双击报 `<hdl_lib>CAPACITOR.SYM.1.1` 缺 `ORIGIN.SYM.1.1`；attributes 中 description/jedec type/package type/sn num 全是 "?"。

### 证据
- 真实 capacitor symbol.css 声明了 `P "JEDEC_TYPE" / P "PACKAGE_TYPE" / P "DESCRIPTION" / P "SN_NUM"`（默认 "?" 值）
- golden CAPACITOR 块含完整属性：`JEDEC_TYPE 0402R-S / SN_NUM M02.010176 / PACKAGE_TYPE R0402 / DESCRIPTION Ƭʽ����2.49K 1% 1/16W 0402`
- **CrossRef CSV 有对应字段**：DESCRIPTION/JEDEC_TYPE/PACKAGE_TYPE/SN_NUM/Part Number/PKG_TYPE（实测头行确认）
- 我们生成的 CSA 块**未注入** JEDEC_TYPE/SN_NUM/PACKAGE_TYPE/DESCRIPTION → Cadence 显示 "?"
- ORIGIN.SYM.1.1：hdl_lib 无 ORIGIN 目录（`ls | grep -i origin` 空）；我们的 CSA 无 ORIGIN 引用（grep count=0）→ 疑 Cadence 系统库引用或 symbol.css 隐式依赖

### 修复方向
1. CSA 属性块注入 CrossRef 的 JEDEC_TYPE/SN_NUM/PACKAGE_TYPE/DESCRIPTION（golden 格式：FORCEPROP 2 LAST + J 0 + DISPLAY 1.021277）
2. ORIGIN：调研 Cadence ORIGIN 符号机制（可能是每 symbol 必须引用的系统符号），确保 hdl_lib 或 cds.lib 满足

---

## 5. mock 图标视觉问题（标签/引脚/字号/标识）🟡

### 证据
- **引脚在 body 内侧**：U6C outline=±825，BGA 引脚在 ±725（`-735 725 -725 725` L 线在 body 内）→ 真实 ch347 引脚 ±300 vs body ±250（**引脚在外侧**）
- **无 MOCK 标识**：MOCK_TEXT 用 P 指令（symbol.css L10 `P "MOCK_TEXT" "MOCK/模拟图标"`）→ 可能不渲染，真实库无 P 指令画文本先例，应改用 T 或 X
- **引脚名太大**：C 指令字号 32（真实 29-34 区间，但用户要求缩小一半 → ~16）
- **标签方向**：真实库 C 指令 justify 只有 R/L；四边标签需 redesign（用 L/R + 位置区分而非 U/D）
- **J4 无引脚**：J4_PH 只有 3 引脚（1/2/3），L 指令 10 单位太短（`L -140 150 -150 150` vs 真实 50 单位 `L -300 -250 -250 -250`）

### 修复方向
mock_icon_lib 重构：引脚在 body 外侧（outline 外扩）、C 指令 justify 仅 R/L、MOCK_TEXT 改 T 指令、字号减半、引脚 L 段 ≥50 单位、BGA 四边标签 redesign。

---

## 6. 布线/避让/GND/网络名类问题（用户实测逐页）🟡

### 6.1 电线穿元件/线头/贴边缘（R5）
- "线头"= 引脚延伸一点原地掉头（自己和自己重叠）→ 需要**三段式 stub**：延伸 stub_lead → 最远端向外折线避让 → 再拐弯（用户明确要求）
- 电线贴芯片矩形边缘走（S2 out 线）→ 避让区需含 **元件外侧冗余区**（用户明确要求扩大，如 margin 25→50+）
- 引脚附近无避让导致误连接 → 引脚点也要避让
- 避让检测未生效：`_avoid_outlines` 传参问题（Phase XIII R4 已修复过，但 mock/引脚未覆盖）

### 6.2 GND 就近共用 + 引脚延伸（R6）
- 一排并联电容各自单独接地 → 要求：**引脚端信号比较，相近同信号先在引脚附近并联再统一引出**
- GND 放元件上/线路中 → 避让 + 间隙放置
- GND 引脚连线直接拐弯 → 先延伸 stub 再拐弯（同 6.1）

### 6.3 网络名标签（R7）
- v6（use_net_name）电线悬空无标签 → net_name_connect 的标签未落到电线末端

### 6.4 电线长度限制（R8）
- max_wire_len 5000 未生效（v6 超长线仍在）→ wire_simplifier.long_wire_report 有实现但未断线

### 6.5 标签方向与元件统一（R9 部分）
- 水平元件标签竖着 → text_layout 需按元件方向（R 行）旋转标签

### 6.6 匹配质量（R10）
- J4/J8/J11/J12/J47 connector 匹配错误（无 mock 标识/无引脚/互相重叠）
- U16/U17/U18/U20 匹配错误（power_ic.yaml 未回填）
- C270/283/260 并联电容位置偏下连错引脚；I18/I15 重叠

### 6.7 元件对齐（R11，用户问"原始意见"）
- 追溯结果：源自 **用户问题 13 "元件本身互相对齐"**（phase17-research-a-star-routing.md L301）："本项目 wire_layout._find_lane 用中位 trunk ±50 找车道是均匀轨道；SKiDL 用元件 bbox 边坐标生成非均匀轨道——**同列元件自然共线对齐**（这正是用户问题 13 的几何基础）"
- 原始意图：同列电容/电阻在布线后应共线对齐；v3/v4 已实现非均匀轨道（轨道=元件 bbox 边坐标），用户实测"好像元件都是互相排列对齐的"→ 该项基本达成，需向用户解释"对齐"指轨道对齐而非元件自身对齐

### 6.8 对比包（R13）
- v1-v8 已在 HG5015_tests/output_phaseXVII_compare/（766MB）
- 修复后需重新生成 v9（修复版），README 补"temp_lib 手动添加"说明

---

## 7. test_spn 模板问题（R12）
- g1-g3 新页空白（缺页面头 FILE_TYPE/TITLE 等）
- g4 报错（LASTPIN offset 未命中，见 3.2）
- 需补完整页面结构模板

---

## 8. 关键配置现状（routing.yaml）
```yaml
routing: {mode: p0, net_order: long_first, nonuniform_tracks: false, stub_lead: 100}
temp_lib: {enabled: true, lib_name: temp_lib, annotate: true}
wire_simplify: {enabled: false, dot_merge: 50, max_wire_len: 5000}
gnd_distribution: {enabled: false, cluster_radius: 2000}
ioport: {use_net_name: false}
```

## 9. 建议开发顺序
1. **P0 批次**：R1（CSS 语法）→ R2（库结构）→ R3（543）→ R4（属性注入+ORIGIN）→ 重生成对比包 v9
2. **P1 批次**：R5（避让）→ R6（GND）→ R7（网络名）→ R8（长度）→ R9（mock 标签）→ R10（匹配）
3. **P2 批次**：R11（对齐）→ R12（模板）
