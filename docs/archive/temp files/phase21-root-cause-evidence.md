# Phase XXI 根因证据（代码级实锤）（2026-08-14）

> 团队：齐活林（编排+根因调查）+ 寇豆码（实施）+ 严过关（QA）。
> 本文件记录每项修复的**代码级证据**（grep/产物实锤），供审计与 QA 复核。

---

## E-1. SPCOCN-542/545：mock symbol.css 缺默认属性声明（A 任务）

### 证据链

| # | 证据 | 内容 |
|---|------|------|
| 1 | 用户报错 100% 集中在 _PH（mock）cell | P5-P24 全部 542 报错元件：U20_PH/U18_PH/U1_PH/S2_PH/J4_PH/T*/U6*/J*/Z*/S* —— **无一是真实库元件**（CAPACITOR/RESISTOR 0 报错） |
| 2 | 真实库 symbol.css | `tests/fixtures/hdl_lib/temp/hdl_lib/capacitor/sym_1/symbol.css`：**9 个 P 属性**（CDS_LMAN_SYM_OUTLINE/$LOCATION/VALUE/PART_NAME/**JEDEC_TYPE**/PATH/**PACKAGE_TYPE**/**DESCRIPTION**/**SN_NUM**） |
| 3 | mock symbol.css（当前） | `mock_icon_lib._symbol_css`（L637-641）只声明 **5 个**（$LOCATION/VALUE/PART_NAME/PATH）——缺 JEDEC_TYPE/PACKAGE_TYPE/DESCRIPTION/SN_NUM |
| 4 | golden 04p4 | at88sc0104c symbol.css 同样 9 个 P 属性，`FORCEPROP 1 LAST PACKAGE_TYPE SOP8` 注入**无 542** |

### 机制

Cadence 对 `FORCEPROP 1 LAST <KEY> <value>` 注入的属性：
- symbol.css **已声明**该属性（P 指令）→ 实例覆盖 symbol 默认值 → 正常（golden 行为）；
- symbol.css **未声明**该属性 → Cadence 视为"未声明的默认属性"→ 删除 + SPCOCN-542 + 545 STICKY 提示。

### 修复

`_symbol_css` P 块补 4 行（顺序对齐真实库：PART_NAME/JEDEC_TYPE/PATH/PACKAGE_TYPE/DESCRIPTION/SN_NUM）：
```
P "JEDEC_TYPE" "?" 0 0 0 0 48 0 0 0 0 0 0 0 32
P "PACKAGE_TYPE" "?" 0 0 0 0 48 0 0 0 0 0 0 0 32
P "DESCRIPTION" "?" 0 0 0 0 48 0 0 0 0 0 0 0 32
P "SN_NUM" "?" 0 0 0 0 48 0 0 0 0 0 0 0 32
```

---

## E-2. MOCK 绿色 + 字号（B 任务）

### 证据

- symbol 内 T 指令颜色字段（token 10=color）实测 c11=4 仍渲染绿系 —— Cadence symbol 内文本颜色受限（交接文档 14.8 已知）；
- golden 04p4 `PAINT PINK` 40 次（CSA 层属性颜色先例），`PAINT RED` 0 次（Cadence CSA 无 RED，PINK 最接近红）；
- golden DISPLAY 缩放可达 4.723404（属性文本大字号先例）。

### 修复

1. T 指令字号 59 → 89（1.5x）；
2. CSA 实例属性标签：mock FORCEADD 块注入 `FORCEPROP 1 LAST MOCK_TEXT "MOCK/模拟图标"` + J 0 + 坐标 + DISPLAY 缩放 ≥1.5 + PAINT PINK。

---

## E-3. J4/S2 引脚名偏右（C 任务）

### 证据（当前 J4_PH symbol.css）

```
L -200 150 -300 150 -1 0
C -300 150 "1" -275 150 0 0 29 1 L
X "PIN_TEXT" "A1" -350 150 0 1 29 ...
```
left 列 X 锚点 px-50（= -350），C 短号 px+25（= -275）—— X 与 C 号距离仅 75，视觉粘连偏右。

### 修复

left X 锚点 px-50 → **px-80**；right px+50 → **px+80**；`_label_w` 相应 +30 余量；保持 50 栅格。

---

## E-4. IC3 引脚名 1-8（D 任务）

### 证据

- EDF L217023-217120：IC3（INS531340, AMS1117）**portInstance 有真实引脚名**：INPUT(3)/OUTPUT(2)/GND(1)/TAP(4)；
- pstchip.dat L1329-1349 AMS1117 primitive 同构（双源交叉验证）；
- edif_parser L939-942 只从 comp_def.pins 初始化 pin_connections，**未解析实例级 portInstance name** → IC3 占位 1-8。

### 修复

实例解析处补 portInstance (name X) + designator (stringDisplay "N") → (pin_number, pin_name) 对；只增强 pins 缺失/网名空实例。

---

## E-5. U6H/U6I/U6A/U12 尺寸（E 任务）

### 证据（当前 outline）

| cell | outline | 宽 | 用户要求 |
|------|---------|----|---------|
| U6H | `-500,400,500,-900` | 1000 | ≥3000（3 倍） |
| U6I | `-400,400,400,-800` | 800 | ≥2400（3 倍） |
| U6A | `-400,400,400,-800` | 800 | ≥2400（3 倍） |
| U12 | `-300,400,300,-200` | 600 | ≥1200（2 倍） |

### 修复

字符宽 18→28、边距 150→250；`_label_w=max_len*28+250`；尺寸钳制到目标值（50 栅格）。C 号改贴 outline 边（防 px 外移后 C 号出框）。

---

## E-6. U6B/U6 文本重叠（F 任务）

### 证据

- char_w=18 检测 0 碰撞，但 Cadence 渲染（字号 29）字符宽 ~24+ → 实测重叠（DDR_ADDR 类 14 字符名与相邻列文本）；
- U6B 84 pin（BGA 双侧多列）、U5_PH 80 pin —— 长名列间距不足。

### 修复

char_w 18→24（与字号 29 匹配）；列间距/`_lab2` 按新口径重算；**文本自检避让函数**（用户 P13 授权"都必要就写避让函数"）：C 号与 X 名同 y 30 内重叠 → 微调（C 号换侧/列间距加大）。

---

## E-7. J/T/电容重叠（G 任务）

### 证据（overlap_resolver.py L288-296 代码 bug 实锤）

```python
nb = _shift_rect(rb, -real_dx, -real_dy, self.grid)
rects[kb] = nb
moved = True
nb = (...)[0] if False else _shift_rect(rb, -dx, -dy, self.grid)  # ← 覆盖
rects[kb] = nb      # ← 用完整分离向量（含 margin）覆盖 real 位移
moved = True
```
位移量错误（-dx/-dy 而非 -real_dx/-real_dy）→ 迭代失真 → 密集区散不开。

### 修复

1. 删重复赋值（只留 `_shift_rect(rb, -real_dx, -real_dy)`）；
2. `placement.max_passive_move: 100 → 200`；
3. 同坐标组（page16/17 J）按 refdes 序号确定性偏移兜底。

---

## E-8. T 元件 4pin 过长（H 任务）

### 证据（T1_PH）

n≤12 行距 pitch=100、y 起点 150 → 4pin outline `-200,250,200,-150`（高 400）。

### 修复

行距 100→50、y 起点 150→100 → 4pin 高 400→250。

---

## E-9. 电线穿芯片（I 任务）

### 证据

`_route_nets`（csa_writer L1911）已传 body_outlines；用户 P19 实测仍穿 → 需调查 `_avoid_outlines` 生效性（Phase XIII L1086 曾修）。

### 状态

调查中（P2 优先级，不阻塞 A-G）。
