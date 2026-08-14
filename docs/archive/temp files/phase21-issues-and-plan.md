# Phase XXI：Cadence 16.6 最新实测问题清单 + 根因 + 修复方案（2026-08-14）

> **来源**：用户对最新交付包（output_phaseXXII_compare 态，Phase XX 补丁 4 后）的 Cadence 16.6 全量实测反馈（逐页）。
> **基线**：818 passed / 6 skipped（Phase XX 末）。
> **团队**：齐活林（编排）+ 寇豆码（实施）+ 严过关（QA）。
> **文档**：本文件（问题清单+根因）→ phase21-root-cause-evidence.md（证据）→ 核心文档追加（README/STATUS/changelog_master/ROADMAP）。

---

## 1. 报错类：SPCOCN-542/545 仍未消除（P5-P24 全部页面）

### 用户报错原文（节选）

```
INFO(SPCOCN-542): The default property PACKAGE_TYPE with value SOT666-6
  has been deleted from the component U20_PH.
INFO(SPCOCN-545): To turn the deleted default properties into non-default
  properties, type SET STICKY_ON; GET; SET STICKY_OFF in the console window.
```

- P5：U20_PH(SOT666-6) / U18_PH(SOT666-6) / U1_PH(SOT23-6L) / S2_PH(PSW6-RA) / J4_PH(PWC0103-M-N)
- P6：U3_PH / U14_PH / U11_PH / U10_PH（均 SOT23-6L）
- P7/P8/P9/P10/P11/P12/P14：U6H/U61/U6I/U6E/U6D/U6C/U6G/U6A/U6B/U6F（均 BGA531-26-2727B）
- P13：U5_PH(BGA96-32-1609W)
- P15/P16/P17：J8/J47/J38/J12/J11 等 COPPER0201；U19_PH(MLF8B)；U8_PH(MLF68AB)
- P18：Z2/Z1_PH(HD-SFLT6-0201D)
- P19/P20：U12/U13_PH(MLF16BW-050-0303L)
- P21：T9/T7/T5/T31/T3 等(SL4-0302A / HD-SL4-0101A/F)
- P22：U7_PH(MLF48X-040-0606L) / U15_PH(SOT23-6L)
- P24：S3/S1_PH(RTSW4-RG-C)

### 共性

**报错元件 100% 是 mock（_PH）cell，真实库元件（CAPACITOR/RESISTOR 等）0 报错。**

### 根因（代码级实锤）

| 证据 | 内容 |
|------|------|
| 真实库 symbol.css | `tests/fixtures/hdl_lib/temp/hdl_lib/capacitor/sym_1/symbol.css` 声明 **9 个** P 属性：CDS_LMAN_SYM_OUTLINE / $LOCATION / VALUE / PART_NAME / **JEDEC_TYPE** / PATH / **PACKAGE_TYPE** / **DESCRIPTION** / **SN_NUM** |
| mock symbol.css | `mock_icon_lib._symbol_css`（L637-641）只声明 **5 个**：$LOCATION / VALUE / PART_NAME / PATH（缺 JEDEC_TYPE/PACKAGE_TYPE/DESCRIPTION/SN_NUM） |
| golden 04p4 | at88sc0104c symbol.css 同样 9 个 P 属性（含 PACKAGE_TYPE），`FORCEPROP 1 LAST PACKAGE_TYPE SOP8` 注入正常无 542 |

**机制**：Cadence 对 `FORCEPROP 1 LAST <KEY> <value>` 注入的属性，若 symbol.css **未声明**该默认属性（P 指令），视为"未声明的默认属性"→ 删除并报 SPCOCN-542 + 545 提示 STICKY。mock cell 缺 4 个 P 声明 → 注入 PACKAGE_TYPE 等真值时全部触发 542。

### 修复方案

`mock_icon_lib._symbol_css` 的 P 属性块补 4 行（对齐真实库格式）：
```
P "JEDEC_TYPE" "?" 0 0 0 0 48 0 0 0 0 0 0 0 32
P "PACKAGE_TYPE" "?" 0 0 0 0 48 0 0 0 0 0 0 0 32
P "DESCRIPTION" "?" 0 0 0 0 48 0 0 0 0 0 0 0 32
P "SN_NUM" "?" 0 0 0 0 48 0 0 0 0 0 0 0 32
```
（顺序对齐真实库：PART_NAME/JEDEC_TYPE/PATH/PACKAGE_TYPE/DESCRIPTION/SN_NUM）

### 验证标准

- 重新转换后：temp_lib 全部 symbol.css 含 9 个 P 属性；mock cell 不再触发 542/545 的代码级判定通过
- Cadence 复测：无 SPCOCN-542/545（待用户实测确认）

---

## 2. 视觉/布局类问题（逐页）

### B-1（P5）MOCK 标识仍是绿色，字号放大 1.5x

- **用户**："mock仍然是绿色的，是不是说软件本来就不支持红色，或者说像现在这样写在图标里就只能绿色，应该做成标签的方式就可以比较大个的显示出来，也可以改变颜色。字号要比现在放大1.5x"
- **现状**：T 指令 `T 0 {y1-90} 0 0 59 0 0 0 0 4 0` + "MOCK"，c11=4 实测仍绿系（交接文档已知：symbol 内 T 指令颜色受 Cadence 限制，纯红需属性标签方案 P2-6）
- **修复**：①T 字号 59→89（1.5x）；②**CSA 实例属性标签**（用户建议的"标签方式"）：mock FORCEADD 块注入可见属性 `FORCEPROP 1 LAST MOCK_TEXT "MOCK/模拟图标"` + DISPLAY 大字号 + PAINT PINK（golden 04p4 有 PAINT PINK 40 次先例，最接近红色）

### B-2（P5）J4/S2 引脚名 A1/A2 位置偏右

- **用户**："J4，S2来看，引脚名称A1，A2这些，位置有点偏右边"
- **现状**（J4_PH）：left 列 X PIN_TEXT 在 px-50、C 短号在 px+25
- **修复**：X 锚点 px-50→px-80（left）/ px+50→px+80（right），C 短号贴框内，保持 50 栅格

### B-3（P6）IC3 引脚全悬空 + 引脚名 1-8

- **用户**："IC3转换成mock版本了，但不知道为什么还是所有引脚都悬空的，而且现在的引脚名称是：1，2，3，4，5，6，7，8，原本就是这样的吗还是有gnd之类的这种信号名称。其他IC元件呢？"
- **现状**：IC3=AMS1117，源 EDF pin_connections 网名全空 → mock 占位 8 引脚（无信号名）
- **关键证据**：`tests/fixtures/HG5015test/pstchip.dat` L1329-1349 有 AMS1117 primitive：INPUT(3)/OUTPUT(2)/GND(1)/TAP(4) 真实引脚名
- **修复**：从 pstchip.dat 恢复 IC3 真实引脚名（INPUT/OUTPUT/GND/TAP 对应 1-4），替代占位 8 引脚；其他 IC（U18=EN/BST/FB/SW/VIN/GND）已正常，勿回归

### B-4（P7/P8/P11）U6H/U6I/U6A 横向拉宽 3 倍

- **用户**："U6H还是横向太小了，至少横向再拉宽3倍。可以通过引脚的名称的字符数量和长度进行一定的推断。"
- **现状**：U6H outline 宽 1000、U6I/U6A 宽 800
- **修复**：字符宽 18→28、边距 150→250，`_label_w = max_len*28+250`；U6H≥3000 / U6I≥2400 / U6A≥2400（钳 50 栅格）

### B-5（P12）U6B 引脚字符重叠（DDR_DDR 与 A1_DM1）

- **用户**："U6B芯片引脚发生字符重叠……比如说：'DDR_DDR'和'A1_DM1'部分重叠了。左侧和右侧的引脚都是这样。"
- **现状**：char_w=18 检测 0 碰撞，但 Cadence 渲染（字号 29）实际字符宽 >18 → 实测重叠
- **修复**：char_w 18→24/28 口径统一；列间距按真实文本宽重算；新增文本自检避让函数（用户 P13 授权）

### B-6（P13）U6 芯片引脚名重叠（A3/C_A_S_ 与 VDDQ）

- **用户**："U6芯片也是有引脚名称重叠，比如说又显示了A3，C_A_S_这些，又显示了VDDQ之类的……这个不知道两个信息都是必要的吗？还是说只有一个必要？如果只有一个必要的话删除一个，都必要的话单独写一个重叠检测避让函数。还是说这其实是不同的引脚，不过没有排列好，没有排列够所以重叠到一起了？"
- **判定**：C 短号（引脚号，LASTPIN $PN 识别必需）+ X 长名（功能名，用户可读必需）**两者都必要** → 实现**重叠检测避让函数**（用户授权）
- **修复**：mock 生成后自检——C 号与相邻 X 名（同 y 30 内）x 重叠则微调（C 号换侧/列间距加大）

### B-7（P16/P17）J 元件 + 电容互相重叠，无避让

- **用户**："这里不同的J元件虽然是模拟图标，但是互相重叠在一起，旁边的电容也全部重叠在一起。没有避让措施。"
- **根因**：overlap_resolver.py `resolve_passives` L288-296 **双重赋值 bug**（第二次用 -dx/-dy 覆盖 real 位移）+ max_move 100 不足
- **修复**：删重复赋值；max_passive_move 100→200；同坐标组确定性偏移兜底

### B-8（P19）U12 拉宽 2 倍 + 电线穿芯片

- **用户**："U12芯片也至少要拉宽两倍。而且电线错综复杂大量穿过芯片，元件等等。"
- **修复**：U12（n≤64 四列）走同一公式，宽 600→1200+；电线穿元件调查 _route_nets 避让生效性

### B-9（P21）T 元件 4pin 过长（左列右上/右列右下）+ 重叠

- **用户**："这里也是大量的T元件，电容重叠在一起了。而且现在我不明白T元件在引脚比较少的情况下（比如四个引脚），左侧的引脚在右上角，右侧的引脚到了右下角，导致整个器件过长，很容易挤压或者重叠到其他元件上去。"
- **现状**：n≤12 已对称（top→bottom），但行距 100 → 4pin outline 高 400 仍过长
- **修复**：n≤12 行距 100→50、y 起点 150→100 → 4pin 高 400→250；重叠走 B-7

---

## 3. 任务分解（对应工程师任务）

| # | 任务 | 优先级 |
|---|------|:---:|
| A | mock symbol.css 补 4 个 P 属性声明（542/545 修复） | P0 |
| B | MOCK 标签方式：T 字号 89 + CSA 属性标签（PAINT PINK） | P0 |
| C | J4/S2 引脚名 X 锚点外移（px±80） | P1 |
| D | IC3 引脚名从 pstchip 恢复（AMS1117 INPUT/OUTPUT/GND/TAP） | P1 |
| E | 尺寸拉宽：字符宽 28、U6H≥3000/U6I≥2400/U6A≥2400/U12≥1200 | P0 |
| F | 文本零碰撞：char_w=24+ 口径、列间距重算、重叠避让函数 | P0 |
| G | overlap_resolver 双重赋值 bug + max_move 200 + 同坐标兜底 | P0 |
| H | T 元件 n≤12 行距 50 压缩高度 | P1 |
| I | 电线穿芯片调查（_route_nets 避让） | P2 |

## 4. 验收口径

1. 全量测试 ≥ 818 passed，净增防回归用例
2. 重新转换（QA 命令）：temp_lib symbol.css 9 P 属性、MOCK 字号 89、U6H outline 宽 ≥3000、文本碰撞（char_w=24）0、U6B 无 310
3. 交付新目录 output_phaseXXIII_compare（用户要求新目录名）
4. 核心文档末尾追加本阶段记录（README/STATUS/changelog_master/ROADMAP）
