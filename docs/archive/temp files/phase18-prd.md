# Phase XVIII 增量 PRD — Cadence 16.6 全量实测问题闭环（2026-08-12）

> 撰写：许清楚（Xu）· 产品经理
> 输入：用户 Cadence 16.6 全量实测报告（8 版本 v1-v8 逐页实测）+ 主理人现场根因证据（已核实）
> 基线：Phase XVII 交付 684 passed / 5 skipped；对比包 8 版本（766MB）
> 性质：**增量 PRD，仅描述 Phase XVIII 变更部分**（相对 Phase XVII 方案/交付）
> 语言：中文 ｜ 优先级：P0 必须 / P1 应该 / P2 可后置

---

## 一、项目信息

| 项 | 值 |
|----|----|
| 项目名称 | `cis2hdl`（OrCAD Capture CIS .DSN → Cadence DEHDL .CSA 转换器） |
| 技术栈 | Python 3.13（Vite/React/MUI/Tailwind 不适用——纯 Python CLI 工具，GUI 为 PySide6） |
| 原始需求复述 | 用户用 Cadence 16.6 实测 8 个对比版本后反馈两大类问题：**A. 系统级报错**（SPCOCN-1158/515/543/541 刷屏、ORIGIN 库引用、attributes 全 "?"、setup 未引用 temp_lib、test_spn 新页空白）；**B. 视觉与布线**（mock 图标标签/引脚/字号、电线穿元件与线头、GND 就近共用与引脚延伸、网络名标签缺失、电线超长、匹配错误、元件重叠）。Phase XVIII 目标：**报错清零 + 视觉规范 + 电气可读**，重新生成对比包 v9 供用户复测。 |
| 成功标准 | 用户在 Cadence 16.6 打开 v9 各版本：SPCOCN-1158/515/543/541 归零；芯片/元件全部正常显示；电线不穿元件、无线头、长度受限；GND 就近共用；网络名标签可见；mock 图标标签规范。 |

---

## 二、产品定义

### 2.1 产品目标（3 条正交）

| # | 目标 | 可量化指标 |
|---|------|-----------|
| G1 | **报错清零**：系统级错误在 Cadence 16.6 打开修复版对比包时归零 | SPCOCN-1158 / 515 / 543 / 541 各版本 0 条 |
| G2 | **电气可读**：元件引用库统一（无 ORIGIN）、引脚连接无误连/悬空、GND 就近共用、网络名可见 | C423 等双击无 515；attributes 无 "?"；GND 簇内 1 条引出；跨页信号末端有标签 |
| G3 | **视觉规范**：电线不穿元件/不重叠/长度受限、mock 图标标签方向对齐字号规范、元件不重叠 | 目视零线头、零穿元件；标签零重叠；字号缩小一半 |

### 2.2 用户故事

| # | 角色 | 故事 | 受益 |
|---|------|------|------|
| US1 | 硬件工程师 | 打开 Cadence 16.6 原理图时无报错刷屏 | 专注审查电路而非处理系统错误 |
| US2 | 硬件工程师 | 每个元件（含 mock 芯片 U6 系列/J4 等）正常显示图形与引脚 | 看到完整电路拓扑，不靠猜测 |
| US3 | 硬件工程师 | 电线不穿过元件、不自我重叠、贴边避让、长度受限 | 原理图可读、后续可布线 |
| US4 | 硬件工程师 | 就近同信号（尤其 GND）先在引脚附近并联再统一引出 | 图面简洁且符合电气规范 |
| US5 | 硬件工程师 | 跨页网络在电线末端看到网络名标签 | 追踪信号走向，不悬空猜测 |

---

## 三、问题来源分析（现象 → 根因 → 影响）

> 根因基于主理人现场证据（grep 实锤 / golden 逐行比对 / 目录与文件实测），非猜测。

### 3.1 A 类：系统级报错

| # | 现象（用户实测） | 根因（证据） | 影响 | 对应需求 |
|---|------------------|--------------|------|---------|
| A1 | 打开 v1，Project Setup 无 temp_lib，需手动添加 | cds.lib 已 `DEFINE temp_lib`（output_manager.py 修复），但 Cadence Project Setup 未自动引用，或用户未手动 add | 每次打开需手动操作，易漏；漏则后续全部 515 | R2/R13 |
| A2 | SPCOCN-543 大量刷屏：普通 CAPACITOR 的 $PN 1/2 全被删（page5/6/7/10/11/19/20/22/23 每页 10+ 条） | golden 04p4 CAPACITOR 无 R 行（R 1 默认），$PN 坐标 = FORCEADD 坐标 + symbol.css 引脚 offset 精确命中；我们生成 CAPACITOR 有 `R 2` 旋转行，坐标数学正确但 Cadence 仍删——**疑旋转 R 行与 LASTPIN 组合问题** | 每页 10+ 报错刷屏，引脚属性丢失（电气信息缺失） | R3 |
| A3 | SPCOCN-543：BGA mock 芯片 SPN（AC13/AB18 等坐标名）被删 | BGA 引脚 C 指令偏移与 LASTPIN 发射坐标不一致（或 master.tag 错误导致 symbol 未加载 → 引脚属性无从挂载） | mock 芯片引脚属性丢失；叠加 1158 后芯片消失 | R1/R2/R3 |
| A4 | SPCOCN-543：GND_POWER 的 SIG_NAME `GND\g` / `GND_POWER\g` 被删（p18 + test_spn g4 实测确认） | golden LASTPIN 坐标 (-3675 3175) = FORCEADD (-3725 3075) + (50,100)，SIG_NAME 值 `GND_POWER\g`；我们生成 LASTPIN = FORCEADD + (0,-50)（rotate_point 后），坐标 offset 与 symbol.css 引脚 (0,50) 不符，SIG_NAME 值 `GND\g` 与 golden 不一致 | 电源符号属性丢失；g4 模板加入任意页稳定报错 | R3/R12 |
| A5 | SPCOCN-541 伴随 543 出现 | 543 的次生：引脚属性块整体未采纳时，附加默认属性一并删除 | 报错叠加刷屏 | R3 |
| A6 | SPCOCN-515 库缺失：U6C_PH/U6D_PH/U6B_PH/U5_PH/U6F_PH/U8_PH/U9_PH/J4_PH.SYM.1.1 找不到（手动添加 temp_lib 后仍报；报错路径 temp_lib\u6c_ph 小写 vs FORCEADD U6C_PH 大写） | ① master.tag 内容错误：真实库 sym_1/master.tag=`symbol.css`、chips/master.tag=`chips.prt`、entity/master.tag=`verilog.v`；**mock 三处全写 `CDS_SYSTEM`**（已实测确认）② 目录名与 FORCEADD 大小写一致性待核（报错路径显示小写）③ entity/pc.db 为最小 ASCII 声明 | 芯片 cell 无法解析 → 图形不渲染、引脚属性挂不上 | R2 |
| A7 | SPCOCN-1158 parse error：`temp_lib\u6c_ph\sym_1\symbol.css: error on line 12` —— U6C/U6D/U6B/U5/U6F/U8/U9 芯片全部消失根因 | **mock symbol.css 的 C 指令 justify 参数用了 U/D，但全库 65689 条真实 C 指令只有 R/L（grep 实锤）**。真实格式：`C x y "pinname" lx ly orient ... justify`，如 ch347 `C -300 -250 "RST#" -325 -250 0 1 32 0 R`；capacitor `C 0 -75 "1" 0 -60 0 0 32 1 R`。已实测：U6C_PH line 12 = `C -725 725 "T12" -725 740 0 0 32 1 U`（justify U）。真实库另有 `X "PIN_TEXT"` 指令显示引脚名，mock 缺失 | **芯片消失根因**：整 cell 无法加载，只剩标签+悬空电线"织网" | R1 |
| A8 | C423 双击报 `<hdl_lib>CAPACITOR.SYM.1.1` 缺 ORIGIN.SYM.1.1；attributes 中 description/jedec type/package type/sn num 全是 "?" | ① CAPACITOR symbol.css 存在引用 ORIGIN 系统库的继承/子符号（违反用户"全部用 hdl_lib"诉求）② CrossRef CSV 有 DESCRIPTION/JEDEC_TYPE/PACKAGE_TYPE/SN_NUM 字段（golden CAPACITOR 块含 JEDEC_TYPE 0402R-S/SN_NUM/PACKAGE_TYPE/DESCRIPTION 属性），但 CSA 属性块未注入 | 双击报错；属性全 "?"，元件信息不可读 | R4 |
| A9 | test_spn g4（GND_POWER 块）加入任何页面都报 `GND_POWER\g deleted`；g1-g3 加入新页面（page25-29）全空白 | ① g4 触发 A4 同因 ② test_spn 模板缺页面头（FILE_TYPE/TITLE/SIZE 等）或 FORCEADD 语法不完整 → 新页不认 | 用户无法用模板做 SPN 复测；新页全空白 | R3/R12 |

### 3.2 B 类：视觉与布线

| # | 现象（用户实测） | 根因（证据） | 影响 | 对应需求 |
|---|------------------|--------------|------|---------|
| B1 | U6H/U6G/U6E/U6C/U6D 等 mock 芯片标签竖着排列且互相重叠；引脚在矩形框内侧；无 MOCK 标识；引脚名称字体太大（至少缩小一半） | ① BGA 四边标签 orientation/坐标偏移错误 ② 引脚 C 指令在 body 内侧 ③ MOCK_TEXT 用 P 指令（可能不渲染）④ 引脚标签字号 scale 过大（当前 32，用户要求缩小一半） | 图面混乱、芯片信息不可读 | R9 |
| B2 | 右侧引脚名称左对齐（应右对齐靠边）；上侧应竖直靠上；下侧应竖直靠下；引脚名称排布不均匀 | 标签对齐规则未按边区分（左=left / 右=right / 上=top / 下=bottom）；BGA 四边标签未按 90°/270° 竖直放置 | 引脚名与引脚对应关系混乱 | R9 |
| B3 | 电线大量穿过元件（电容/电阻/芯片）；"线头"严重（引脚延伸一点原地掉头，自己和自己折线重叠）；电线贴芯片矩形边缘走 | ① 避让检测 margin 过小（25），未覆盖元件外侧冗余区 ② 无 self-intersection 检测（线头=自身重叠）③ 无"先延伸→折线避让→再调头"三段式 stub（当前原地掉头）④ 边缘冗余区未避让（用户明确"担心边缘上不被检测"） | 原理图不可读、可能误连接 | R5 |
| B4 | GND 一页就 1 个；并联电容（C52/455/53/459/462）各自单独引线接地而非就近共用；GND 放置在元件正上方且连线穿元件；GND 引脚连线不先延伸就拐弯 | ① GND 聚类已实现（v8 19→97）但"簇内引脚先并联再统一引出"未实现 ② GND 符号避让不完整（仍落元件上/线中）③ GND 连线无引出段直接拐弯横穿 | 图面不简洁、违反电气规范观感 | R6 |
| B5 | v6（use_net_name）无 IOPORT 但电线延伸到原 IOPORT 位置悬空，无网络名标签 | net_name_connect 的 SIG_NAME 标签未落到电线末端（悬空端） | 信号去向不可知 | R7 |
| B6 | 电线长度无限制（拉超长线）；元件标签（名称/标称值/引脚序号）全部竖着放置互相重叠，未与元件方向统一 | ① max_wire_len（5000 可配）未生效或超长未断开改网络名 ② 标签方向未随元件方向统一（R237/239 水平放置但标签竖直） | 超长飞线、标签不可读 | R8/R11 |
| B7 | J4/J8/J11/J12/J47 等 connector 匹配错误（无 mock 标识/无引脚/互相重叠）；U16/U17/U18/U20 匹配错误；C270/283/260 并联电容位置偏下连错引脚；I18/I15 电阻重叠 | ① J* 匹配到错误 cell（无 mock 接管）② U18/U20→CH347 fuzzy 0.4475 误匹配（power_ic.yaml 规则未实写）③ 并联电容坐标偏下导致连错引脚 ④ 腾挪/对齐未覆盖被动元件 | 元件显示错误/重叠/功能错位 | R10/R11 |
| B8 | 用户核心诉求汇总：全部元件用 hdl_lib（不能有 ORIGIN）；避让区扩到外侧留冗余；引脚附近避让；电线不能自己/互相重合；调头先延伸再折线避让再调头；GND 先延伸再拐弯；就近共用 GND；网络名标签必须显示；电线长度设限；标签方向与元件方向统一；引脚名缩小一半；mock 图标必须显示且有 MOCK 标识、引脚在框外侧；并联电容先短网连接再连出去；元件间不重叠 | 分散于 R4-R11 | 全部视觉诉求 | R4-R11 |

---

## 四、需求池（R1-R13，含 Cadence 可验证验收标准）

> 编号延续 handoff §9（R1-R13）。P0=必须（报错/芯片消失/阻塞实测）；P1=应该（视觉硬伤/核心诉求）；P2=可后置（增强/模板）。

### P0 需求（报错清零，阻塞实测）

#### R1 🔴 mock symbol.css 语法修复（SPCOCN-1158）——芯片消失根因

| 项 | 内容 |
|----|------|
| 现象 | temp_lib/u6c_ph/sym_1/symbol.css line 12 parse error；U6C/U6D/U6B/U5/U6F/U8/U9 芯片全部消失 |
| 根因 | C 指令 justify 参数用了 U/D；全库 65689 条真实 C 指令只有 R/L（grep 实锤）；真实库另有 `X "PIN_TEXT"` 指令显示引脚名，mock 缺失 |
| 动作 | ① mock_icon_lib.py 生成逻辑修复：C 指令 justify 仅允许 R/L（BGA 上/下边标签改用文本方向而非 U/D justify 表达）② 对照真实库补 `X "PIN_TEXT"` 引脚名显示 ③ 全量 mock cell 重新生成 + 自研语法检查（遍历 symbol.css 逐行校验 justify ∈ {R,L}、坐标数值合法、括号闭合、无非法字符） |
| **验收标准（Cadence 可验证）** | ① 代码级：全量 temp_lib symbol.css 语法检查 0 错误（justify 仅 R/L）② Cadence 16.6 打开 v9：SPCOCN-1158 报错 **0 条** ③ U6C/U6D/U6B/U5/U6F/U8/U9 芯片**图形正常显示**（不再只有标签+悬空电线）④ 引脚名在 Cadence 中可见（X PIN_TEXT 生效） |

#### R2 🔴 temp_lib 库结构修复（SPCOCN-515 / master.tag / 大小写）

| 项 | 内容 |
|----|------|
| 现象 | 手动添加 temp_lib 后仍报 U6C_PH.SYM.1.1 等找不到；报错路径小写 temp_lib\u6c_ph vs FORCEADD 大写 |
| 根因 | master.tag 内容错误（真实库 sym_1=`symbol.css`、chips=`chips.prt`、entity=`verilog.v`；mock 三处全写 `CDS_SYSTEM`，已实测）；entity/pc.db 为最小 ASCII 声明；目录名大小写一致性待核 |
| 动作 | ① master.tag 按 golden 分目录改写（sym_1/chips/entity 各不同）② 全量校验目录结构 = golden：sym_1/{symbol.css, master.tag}、chips/{chips.prt, master.tag}、entity/{master.tag, pc.db}、cell 根无 master.tag ③ FORCEADD 引用名与 cell 目录名大小写统一（建议全大写），全量 grep 校验 ④ 复核 pc.db 是否需要更完整声明 |
| **验收标准（Cadence 可验证）** | ① 代码级：结构/大小写/ master.tag 内容断言全过 ② 用户在 Cadence Project Setup 手动添加 temp_lib 后：SPCOCN-515 报错 **0 条** ③ 所有 _PH cell 在 Cadence 中可解析（可放置/可显示）④ README 写入"temp_lib 手动添加"说明（R13 配套） |

#### R3 🔴 SPCOCN-543 全面修复（CAPACITOR $PN / BGA SPN / GND SIG_NAME / PQ2016 / UN$ 网名）

| 项 | 内容 |
|----|------|
| 现象 | ① 普通 CAPACITOR $PN 1/2 全被删（页页刷屏）② BGA mock SPN（AC13/AB18 等）被删 ③ GND_POWER SIG_NAME `GND\g`/`GND_POWER\g` 被删 ④ PQ2016 $PN 3/4/2/1 被删 ⑤ UN$ 自动网名 SIG_NAME 被删 ⑥ SPCOCN-541 伴随 |
| 根因 | ① golden CAPACITOR 无 R 行，$PN 坐标=FORCEADD+offset 精确命中；我们生成有 R 2 旋转行 → 疑 R 行与 LASTPIN 组合问题 ② mock 芯片 SPN 坐标未命中（叠加 R1/R2 未修复时 symbol 未加载）③ GND_POWER LASTPIN offset 与 symbol.css 引脚 (0,50) 不符、SIG_NAME 值 `GND\g` 与 golden `GND_POWER\g` 不一致 ④ PQ2016 引脚数不匹配 → fallback 坐标未命中 ⑤ UN$ 自动网名可能不被 Cadence 接受 |
| 动作 | ① CAPACITOR：LASTPIN 发射前坐标命中校验（命中 symbol.css 引脚 offset 才发射）；**R 行旋转组合做受控 A/B**（旋转+$PN / 旋转+$PN+SIG / 非旋转+SIG）定案 ② BGA mock：引脚 C 指令偏移与 LASTPIN 发射坐标严格同源 ③ 电源符号：LASTPIN offset 对齐 symbol.css 引脚 (0,50)，SIG_NAME 值对齐 golden（`GND_POWER\g`）④ PQ2016：引脚数不匹配 → 跳 LASTPIN 或 mock 接管 ⑤ UN$ 网名：确认 Cadence 接受性，不接受则生成稳定可读网名或省略 SIG_NAME |
| **验收标准（Cadence 可验证）** | ① Cadence 16.6 打开 v9：SPCOCN-543 报错 **0 条**（全版本）② SPCOCN-541 **0 条** ③ test_spn g4 加入任意页（含 page24）**不再报 GND_POWER\g deleted** ④ CAPACITOR/BGA/PQ2016 引脚属性（$PN/SPN/SIG_NAME）在 attributes 中可查 ⑤ 代码级：坐标命中校验断言全过 |

#### R4 🔴 元件库统一 hdl_lib（ORIGIN.SYM.1.1 / attributes "?"）

| 项 | 内容 |
|----|------|
| 现象 | C423 双击报 `<hdl_lib>CAPACITOR.SYM.1.1` 缺 ORIGIN.SYM.1.1；attributes description/jedec type/package type/sn num 全 "?" |
| 根因 | ① CAPACITOR symbol.css 引用 ORIGIN 系统库继承/子符号（违反"全部用 hdl_lib"）② CSA 属性块未注入 CrossRef CSV 的 DESCRIPTION/JEDEC_TYPE/PACKAGE_TYPE/SN_NUM（golden CAPACITOR 块含这些属性） |
| 动作 | ① 全量扫描输出 CSA 与 hdl_lib symbol.css 的 CDS_LIB/cell 引用，确认无 ORIGIN 引用链 ② CAPACITOR 的 ORIGIN 依赖处理（复制依赖符号进 hdl_lib 自包含 或 改引用 hdl_lib 已有符号——**待用户决策 Q1**）③ 属性注入：CSA 属性块补充 DESCRIPTION/JEDEC_TYPE/PACKAGE_TYPE/SN_NUM（数据源 CrossRef CSV，golden 字段对齐） |
| **验收标准（Cadence 可验证）** | ① 全部元件 CDS_LIB ∈ {hdl_lib, temp_lib}（grep 断言无 ORIGIN）② C423 等任意元件双击：SPCOCN-515 **0 条**（不再缺 ORIGIN.SYM.1.1）③ attributes 显示真实值（description/jedec type/package type/sn num 非 "?"）④ golden 字段级比对通过（JEDEC_TYPE 0402R-S 等） |

### P1 需求（视觉硬伤/核心诉求）

#### R5 🟡 避让检测增强（线头/穿元件/边缘冗余区/引脚避让/三段式 stub）

| 项 | 内容 |
|----|------|
| 现象 | 电线大量穿过元件；"线头"严重（原地掉头、自己重叠）；电线贴芯片边缘走；引脚附近误连接 |
| 根因 | 避让 margin 过小；无 self-intersection 检测；无三段式 stub（延伸→折线避让→调头）；边缘冗余区未避让 |
| 动作 | ① 统一碰撞 detect_collisions margin 扩大（25→50+，可配；芯片外侧留冗余区——**待用户决策 Q3**）② 检测集含：元件 outline + 膨胀区 + 引脚点 + 已路由线段（self-intersection 检测）③ 三段式 stub：引脚延伸 stub_lead → 最远端向外折线避让 → 再拐弯（消除原地掉头）④ 禁止电线贴元件边缘走（边缘冗余区避让）⑤ 引脚附近避让（防误连接） |
| **验收标准（Cadence 可验证）** | ① 目视：无电线穿元件、无贴边缘线、无线头（无自己和自己重叠）② 代码级：shapely 断言所有 WIRE 段与元件 outline（含冗余区）零相交、所有线段对零重合 ③ 引脚附近无电线从引脚正上方/旁边穿过导致误连接 ④ 调头处可见"先延伸→折线→调头"三段式路径 |

#### R6 🟡 GND 就近共用 + 引脚延伸

| 项 | 内容 |
|----|------|
| 现象 | 一页就 1 个 GND；并联电容（C52/455/53/459/462）各自单独引线接地；GND 放元件正上方且连线穿元件；GND 连线不延伸就拐弯 |
| 根因 | 聚类已实现但"簇内引脚先并联再统一引出"未实现；GND 符号避让不完整；GND 连线无引出段 |
| 动作 | ① GND 簇内引脚**先在引脚附近并联（短接）再统一引出**到 GND 符号（同信号近距先连，用户 v7 诉求）② GND 符号位置避让元件（放空隙/下方，不落元件上/线中）③ GND 引脚连线先延伸 stub 再拐弯（同 R5 三段式）④ 聚类半径保持可配（默认 2000，**待用户反馈 Q4**） |
| **验收标准（Cadence 可验证）** | ① 一排并联电容（C52/455/53/459/462）**1 条 GND 引出线**（簇内先并联）② GND 符号不落在任何元件 outline 上/内（v8 问题消除）③ GND 连线先延伸再拐弯，不直接横穿元件 ④ 每页 GND 数量合理（聚类生效，非一页 1 个） |

#### R7 🟡 网络名标签显示（v6 悬空问题）

| 项 | 内容 |
|----|------|
| 现象 | v6（use_net_name）无 IOPORT 但电线延伸到原 IOPORT 位置悬空，无网络名标签 |
| 根因 | net_name_connect 的 SIG_NAME 标签未落到电线末端（悬空端） |
| 动作 | ① 网络名标签（SIG_NAME）落到**电线末端/悬空端**，用户可知信号去向 ② 标签避让元件/电线、方向对齐（样式**待用户决策 Q5**）③ use_net_name 版本（v6 对应）回归验证 |
| **验收标准（Cadence 可验证）** | ① v9 的 use_net_name 版本：所有跨页信号电线末端**有网络名标签** ② 无"电线悬空无标签" ③ 标签不与元件/电线重叠、可读 |

#### R8 🟡 电线长度限制 + 并联先短接

| 项 | 内容 |
|----|------|
| 现象 | v6 拉超长线；C270/283/260 并联电容位置偏下连错引脚；一排并联电容应先就近互联再连出 |
| 根因 | max_wire_len（5000 可配）未生效/超长未断开改网络名；并联组未做"先短接再统一引出" |
| 动作 | ① 电线长度检查：超 max_wire_len 断开改用网络名标签表达（上限**待用户决策 Q6**）② 同类信号相近元件（并联组）先短网连接再连出去（cluster 级布线）③ 并联电容位置/引脚连接修正（R11 配合） |
| **验收标准（Cadence 可验证）** | ① 脚本统计：无 >max_wire_len 的 WIRE 段（或超长清单全转为网络名标签表达）② 并联电容组内引脚先短接、再统一引出 ③ C270/283/260 引脚连接正确（上端不再悬空/下端不再漏接） |

#### R9 🟡 mock 图标标签全面修正（方向/对齐/字号/标识/引脚朝外）

| 项 | 内容 |
|----|------|
| 现象 | 标签竖排重叠；右侧左对齐（应右对齐）；上/下侧应竖直靠边（当前水平重叠）；字体太大（缩小一半）；无 mock 标识；引脚在框内侧 |
| 根因 | 标签布局未按边区分方向/对齐；字号过大；MOCK_TEXT 用 P 指令可能不渲染；引脚 C 指令在 body 内侧；L 指令仅 10 单位（真实 50） |
| 动作 | ① 四边标签：左=水平 0° 左对齐 / 右=水平 180° 右对齐靠边 / 上=竖直 90° 靠上 / 下=竖直 270° 靠下（用户 B2 明确）② 字号缩小一半（32→16 等效）③ MOCK_TEXT 改 X/T 指令验证渲染（P 指令不渲染则替换）④ 引脚 C 指令在 body 边缘**外侧**、L 指令长度 50 单位向外 ⑤ 标签排布均匀（对照 CIS 原引脚排布）⑥ 标签不重叠 |
| **验收标准（Cadence 可验证）** | ① 目视：标签方向正确（右=右对齐、上=竖直靠上、下=竖直靠下）、零重叠 ② 字号缩小一半（用户目视确认）③ 所有 _PH 芯片可见 MOCK/模拟图标 标识 ④ 引脚在矩形框外侧（可点选/可接线）⑤ 引脚名排布均匀 |

#### R10 🟡 匹配质量修复（J* / U16-20 / PQ2016）

| 项 | 内容 |
|----|------|
| 现象 | J4/J8/J11/J12/J47/J40-44 匹配错误（无 mock 标识/无引脚/互相重叠）；U16/U17/U18/U20 匹配错误；PQ2016 $PN 被删 |
| 根因 | J* 匹配到错误 cell 且无 mock 接管；U18/U20→CH347 fuzzy 0.4475 误匹配（power_ic.yaml 规则未实写）；PQ2016 引脚数不匹配 |
| 动作 | ① J* connector：引脚数校验 + 候选过滤 + 低置信 fallback 到 mock 图标（mock 接管后显示完整）② U16-20：power_ic.yaml 回填 6 脚稳压规则 + chip_config.yaml 预置正确映射 ③ PQ2016：引脚数不匹配跳 LASTPIN 或 mock 接管（同 R3④）④ 匹配错误元件不再产生错误符号/过长符号 |
| **验收标准（Cadence 可验证）** | ① J* 全部正常显示（正确符号或 mock 图标，含引脚/延伸/mock 标识）② U16/U17/U18/U20 显示正确符号、无"失去功能" ③ PQ2016 无 $PN 被删 ④ 无匹配错误导致的元件重叠/过长符号 |

### P2 需求（增强/模板）

#### R11 🟢 元件对齐/腾挪增强

| 项 | 内容 |
|----|------|
| 现象 | C270/283/260 并联电容位置偏下连错引脚；I18/I15 重叠；J8/R118/R107 重叠；R237/239 标签竖直（元件水平） |
| 根因 | 腾挪/对齐未覆盖被动元件；标签方向未随元件方向统一 |
| 动作 | ① M3 腾挪器增强：元件级微调对齐（**是否允许小范围移动被动元件待用户决策 Q12**；芯片本体不动 D10）② 摆放网格对齐 ③ 标签方向与元件方向统一（水平元件标签水平） |
| **验收标准（Cadence 可验证）** | ① I18/I15、J8/R118/R107 重叠消除 ② C270/283/260 位置正确、引脚连接正确 ③ 同列/同排元件对齐无重叠 ④ 标签方向与元件方向统一（R237/239 标签水平） |

#### R12 🟢 test_spn 模板修正（新页面可显示）

| 项 | 内容 |
|----|------|
| 现象 | 新建 page25-29 复制 test_spn 全空白；加头尾后只有 SIZE PAGE 显示 |
| 根因 | 模板缺页面头（FILE_TYPE/TITLE/PAGE/SIZE 等）或 FORCEADD 实例级必备属性不完整 |
| 动作 | ① 对照真实 csa 页面头补齐模板（FILE_TYPE=MACRO_DRAWING + SIZE PAGE..1 + 实例必备属性块）② 提供可直接复制到新页显示的 g1-g4 模板（g4 依赖 R3 修复后不再报 deleted） |
| **验收标准（Cadence 可验证）** | ① 用户在 Cadence 新建页复制修正后模板：g1-g3 元件正常显示 ② g4 加入任意页不再报 GND_POWER\g deleted |

#### R13 🔴 对比包 v9 重新生成（P0：交付物）

| 项 | 内容 |
|----|------|
| 动作 | ① R1-R12 修复后重新生成对比包（8-9 版本，范围**待用户决策 Q7**）② 更新 metrics_summary.md（报错计数/WIRE/GND/IOPORT 修复前后对比）③ 更新 README：temp_lib 手动添加说明 + 各版本修复说明 ④ 保留/更新 test_spn 模板 |
| **验收标准（Cadence 可验证）** | ① v9 各版本在 Cadence 16.6 打开：SPCOCN-1158/515/543/541 **0 条** ② README 含 temp_lib 添加指引 ③ metrics_summary 含修复前后对比表 ④ 用户按 README 可完整复测 |

### 需求池总览

| # | 需求 | 优先级 | 关联问题 | 验收核心（Cadence 可验证） |
|---|------|:---:|----------|---------------------------|
| R1 | mock symbol.css 语法修复（1158） | 🔴 P0 | A7/B1 | 0 条 1158；U6 系列芯片图形显示 |
| R2 | temp_lib 库结构修复（515/master.tag/大小写） | 🔴 P0 | A1/A6 | 0 条 515；_PH cell 可解析 |
| R3 | SPCOCN-543 全面修复 | 🔴 P0 | A2/A3/A4/A5/A9 | 0 条 543/541；g4 不再报 deleted |
| R4 | 元件库统一 hdl_lib（ORIGIN/attributes） | 🔴 P0 | A8 | 无 ORIGIN；双击无 515；attributes 无 "?" |
| R5 | 避让检测增强（线头/穿元件/冗余区/三段式） | 🟡 P1 | B3 | 无穿元件/无线头/无贴边 |
| R6 | GND 就近共用 + 引脚延伸 | 🟡 P1 | B4 | 并联簇 1 条引出；GND 不落元件上 |
| R7 | 网络名标签显示 | 🟡 P1 | B5 | 悬空电线末端有标签 |
| R8 | 电线长度限制 + 并联先短接 | 🟡 P1 | B6 | 无超长线；并联组内短接 |
| R9 | mock 标签全面修正 | 🟡 P1 | B1/B2 | 标签方向/对齐/字号/标识/引脚朝外 |
| R10 | 匹配质量修复（J*/U16-20/PQ2016） | 🟡 P1 | B7 | J* 正常显示；U16-20 正确；PQ2016 无删 |
| R11 | 元件对齐/腾挪增强 | 🟢 P2 | B6/B7 | 重叠消除；标签方向统一 |
| R12 | test_spn 模板修正 | 🟢 P2 | A9 | 新页复制可显示 |
| R13 | 对比包 v9 重新生成 | 🔴 P0 | 全部 | v9 无 1158/515/543/541；README 完整 |

---

## 五、待确认问题清单（需用户决策）

| # | 问题 | 建议默认 | 影响需求 |
|---|------|----------|---------|
| Q1 | **ORIGIN.SYM.1.1 处理方式**：hdl_lib 内 CAPACITOR 引用 ORIGIN 系统库依赖符号——复制依赖符号进 hdl_lib（自包含）？改引用 hdl_lib 已有符号？还是允许保留 ORIGIN 引用？ | **✅ 已决策（用户）：改引用 hdl_lib 已有符号，且确保所有匹配函数只能在 hdl_lib 中匹配符号，不能使用系统库符号** | R4 |
| Q2 | **CAPACITOR 旋转与 $PN 组合**：若 A/B 实测确认旋转 R 行触发 543，采用哪种方案？a) 旋转实例改 sym_2 视图（不写 R 行）b) 去掉旋转保持非旋转放置 c) 其他 Cadence 兼容写法 | **✅ 已决策（用户）：方案 A —— sym_2 视图为主**。只对 capacitor/resistor/inductor 这类「有横向 sym_2 视图」的被动元件用 ..2 选视图（golden page9 L354 先例）；dc_dc 等 sym_N 是器件变体的保留 R 行或 mock 接管，避免歧义 | R3 |
| Q3 | **避让冗余区大小**：统一碰撞 margin 默认 25→50？芯片外侧冗余区取值（50/100/150）？引脚附近避让半径？ | **✅ 已决策（用户）：margin=50，冗余区=100，引脚避让半径=50（可配）** | R5 |
| Q4 | **GND 就近合并半径**：cluster_radius 默认 2000 是否合适（用户实测后反馈）？"相近同信号先在引脚附近并联"的判定距离阈值？ | 保持 2000，并联判定距离 ≤500 | R6 |
| Q5 | **网络名标签样式**：字号/位置（电线末端上方/下方）/对齐？显示网络全名还是短名？ | 字号 32、末端上方、显示可读网名（UN$ 换稳定名） | R7/R8 |
| Q6 | **电线长度上限**：max_wire_len 默认 5000 是否合适？超长线处理（断开改网络名 vs 保留+报告）？ | 保持 5000；断开改网络名 + 报告 | R8 |
| Q7 | **对比包范围**：v9 重新生成哪些版本？全部 8 版本 or 仅修复版（默认/v7/v8/use_net_name）？是否新增"修复版默认"？ | **✅ 已决策（用户）：4 个核心版本**（默认修复版 + GND 分布版 + 电线化简版 + 网络名版 use_net_name） | R13 |
| Q8 | **mock 引脚名**：BGA 大量坐标名（AC13/AB18 等）是否保留原名？还是映射功能名？（D3 已定"显示功能名"，但坐标名是 CIS 原名） | 保留 CIS 原名（用户可后续 chip_config 改） | R9 |
| Q9 | **attributes 注入字段**：DESCRIPTION/JEDEC_TYPE/PACKAGE_TYPE/SN_NUM 从 CrossRef CSV 注入 CSA 属性块的字段名/格式确认（对齐 golden）？ | 按 golden CAPACITOR 块字段注入 | R4 |
| Q10 | **temp_lib 自动添加**：是否要求工具自动把 temp_lib 加入 Cadence Project Setup（cds.lib 已 DEFINE 但 setup 未引用）？还是维持 README 手动说明？ | 维持 README 手动说明（工具侧无法控制 Cadence UI） | R2/R13 |
| Q11 | **MOCK_TEXT 渲染**：P 指令实测不渲染时改用 X/T 指令是否可接受？ | 改 X/T 指令 + Cadence 复测确认 | R9 |
| Q12 | **元件级腾挪**：R11 对齐是否允许小范围移动被动元件（电容/电阻）？（D10 已定芯片本体不动） | 允许微调被动元件（≤50 单位），芯片本体不动 | R11 |
| Q13 | **SPN A/B 复测**：R3 修复后是否需用户再次用 test_spn g1-g4 复测确认？（需 R12 模板先修好） | 需要，v9 内附带修正后模板 | R3/R12/R13 |

---

## 六、非目标（Out of Scope）

- **GUI 交互实测**（Phase XVII M7 chip_config_panel 的 PySide6 实测）：Phase XVIII 不阻塞，属并行/后续
- **全量 A\* 迷宫布线**：留远期自动布局场景，不在本阶段
- **hdl_lib 符号重建**（如 CAPACITOR 尺寸/外观）：仅在 ORIGIN 依赖需自包含时复制符号，不做大规模重建
- **匹配算法重写**：R10 只做规则回填与 mock 接管，不动匹配管线核心

---

## 七、交付物与验收流程（建议）

1. 开发完成后：全量 pytest（基线 684 passed/5 skipped 不得回退）+ 新增 R1-R13 回归用例
2. 代码级自动验收：mock symbol.css 语法检查 / master.tag 断言 / 坐标命中断言 / 无 ORIGIN grep / 无超长 WIRE 统计 / 线段零相交断言
3. 生成对比包 v9（含 README + metrics_summary + test_spn 修正模板）
4. 用户 Cadence 16.6 复测：按 R1-R13 验收标准逐项核对（重点 1158/515/543 归零、芯片显示、避让、GND、网络名）
5. 复测通过后提交 git（Phase XII-XVII 工作区 90 项 + XVIII 改动）

---

*Phase XVIII 增量 PRD v1.0（2026-08-12，产品经理许清楚）。输入 = 用户 Cadence 16.6 全量实测报告 + 主理人根因证据；待确认问题 Q1-Q13 建议开发前 grill-me 与用户对齐。*
