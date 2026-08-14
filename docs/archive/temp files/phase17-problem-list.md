# Phase XVII 问题清单（2026-08-12）— 两版测试报错全量分析

> 数据来源：
> 1. `HG5015_tests/errors_aes_08111200.txt`（output_phaseXIV_aes，8.11 12:00）
> 2. `HG5015_tests/errors_aes6_08111718.txt`（output_phaseXVI_aes6，8.11 17:18）
> 3. 架构师高见远根因分析（16 条问题清单，代码级）+ 工程师寇豆码代码级核对（14 条问题表）+ 主理人独立复核
> 本文件为临时文档，正式内容追加至 docs/STATUS.md。

## 一、报错统计对比（两版）

| 错误码 | 含义 | 12:00 版(XIV aes) | 17:18 版(XVI aes6) | 变化 |
|--------|------|:---:|:---:|:---:|
| SPCOCN-543 | pin property SPN/$PN/SIG_NAME 被删 | **182** | **116** | 减少但仍在 |
| SPCOCN-542 | default property PLACEHOLDER 被删 | 0 | **15** | 新增 |
| SPCOCN-541 | 附加默认属性也被删 | 18 | 11 | 减少 |
| SPCOCN-515 | 库缺失（如 U6H_PH.SYM.1.1） | **13** | 0 | ✅ 消除 |
| SPCOCN-545 | 提示 SET STICKY_ON 保留默认属性 | 0 | 13 | 新增 |

**关键发现**：
- CAPACITOR 的 SPCOCN-543 占最大比重（aes6 版 63 次，SPN 1/2 各 27/23 次）——**普通被动元件引脚属性被删是最大共性问题**，不只是占位芯片
- 17:18 版解决了 SPCOCN-515（库缺失）但新增 SPCOCN-542/545（PLACEHOLDER 属性问题）——说明占位符号写入了库，但 PLACEHOLDER 属性写法仍不被 Cadence 接受
- 量化对比：aes6 WIRE=12786 vs final 4911（**+160%**）、GND=541 vs 19（**+28 倍**）——用户"连接点过多/GND 过多"抱怨的量化证据

## 二、SPCOCN 报错根因（代码级）

### P0-1 SPCOCN-543：CAPACITOR 等普通元件引脚属性被删（182→116 次）
- 根因链：`_lastpin_pn` 的 $PN 块已对齐 04p4 golden（`FORCEPROP 2 LASTPIN (x y) $PN <n>` + R 1 + J 0，无 PAINT），但 **`_sig_name_at_pin`(csa_writer.py L2609-2622) 的 SIG_NAME LASTPIN 块含 `PAINT MONO + DISPLAY INVISIBLE` 两行，违反 04p4 page9 L365 golden（该块仅 J 0 + DISPLAY，无 PAINT）**
- SPN 是 Cadence 对 $PN 的内部名（全代码库无 SPN 字符串输出），报错"SPN with value 8"即我们写的 `$PN 8`
- 更深层：占位库缺失（已修复）时 Cadence 丢弃未知引脚属性 → SPCOCN-543/542 同页共现
- **修复方向**：删 `_sig_name_at_pin` 的 PAINT MONO + DISPLAY INVISIBLE 两行（对齐 golden）

### P0-2 SPCOCN-542/545：PLACEHOLDER 默认属性被删（15 次）
- 位置：csa_writer.py L2141-2146
- 现状：`FORCEPROP 1 LAST PLACEHOLDER 1` + J 0 + `(x y);` + DISPLAY + **PAINT ORANGE + DISPLAY INVISIBLE**
- 根因：PLACEHOLDER 是非标准属性，Cadence 16.6 打开时当"默认属性"删除（SPCOCN-542），并提示 SPCOCN-545（SET STICKY_ON 可保留）
- **修复方向**：①库存在后按 golden 无 PAINT 块重写；②必要时 SET STICKY；③或改用标准可见标注（见新需求"模拟图标标注"）

### P0-3 SPCOCN-515：占位库缺失（12:00 版 13 处，17:18 版已消除）
- 根因（工程师核对）：①`placeholder_lib.py:292` cell 目录用小写 `j4_ph`，Cadence 按大写 `J4_PH.SYM.1.1` 查找 → 大小写不匹配视为库缺失；②sym_1/chips 下只有 master.tag，缺 cell 根 tag/symbol.tag 等 Cadence 要求的文件；③**占位符号缺 `entity/` 目录**（真实库 ch347 有 entity/pc.db、verilog.v、vhdl.vhd——主理人独立验证）
- 17:18 版消除说明部分已修，但 entity 目录缺失问题仍待确认
- **修复方向**：目录大写化 + 补 entity 目录 + 补 cell 根 tag

## 三、用户 17 条共性问题 → 根因 → 修复方向

| # | 用户问题 | 根因（代码级） | 修复方向 |
|---|----------|--------------|----------|
| 1 | 大量冗余连线，整体复杂 | aes 模式 stub 引出段 + 每网 trunk，段数 +160%（12786 vs 4911） | SKiDL `merge_segments` 共线合并 + `trim_stubs`（见 A* 调研） |
| 2 | 连接点过多，每线单画而非共用总线 | 每引脚独立 stub→trunk；多网车道独立 | 多端点网共用 trunk（left-edge / 轨道共享） |
| 3 | 需要连线化简算法 | 无后处理化简阶段 | **wire_simplify 模块**（SKiDL cleanup_wires 移植） |
| 4 | GND 过多需合并 | `_plan_and_inject_gnd_symbols`(L1822) 每芯片 1 个（max_per_chip=1 恒 1），无近区合并；GND 541 vs 19 | GND 距离聚类（KMeans/最近邻）共享 |
| 5 | 电线凸出又折回 | detour `_route_horizontal`(L136-177)/`_route_vertical`(L179-215) **把原始引脚 x 加入 trunk_xs** → trunk 画 `[x,lx]` 死段 | trunk_xs 只含 lx 与跨度端点（工程师 #6） |
| 6 | 电线/自身/元件重叠 | wire_layout 仅同向共线检测（`_lane_free` L376-392），无异向交叉检测、无自重叠检测、stub 不避元件体 | shapely `LineString.intersects` + 异向相交检测 |
| 7 | GND 无重叠检测放芯片上 | `_gnd_symbol_body`(L2000-2016) 只对 used_body（其他 GND）+25 挪位，**不查元件体/引脚/电线** | GND 位置复用统一重叠检测 |
| 8 | 重叠检测应扩大一圈避让引脚 | `_avoid_outlines` 只推 trunk 坐标，不扩圈 | outline 膨胀（OpenRAM `inflate_shape`） |
| 9 | 连接点不能在元件范围内 | `compute_dots`(L514-547) 无 dot 避体 | DOT 避让检测 |
| 10 | 重叠检测应是统一函数反复调用 | `overlap_detector.py` 仅元件矩形vs元件；text_layout 还有独立一份 bbox 相交 | **重构为通用几何检测函数**（元件/线/DOT/GND 统一） |
| 11 | C354 等偏右引脚没接上 | `_unique_pin_coord`(L1568-1690) 挪引脚后无"引脚在体内/端点重合"QA | 路由后 QA：LASTPIN 坐标==WIRE 端点 |
| 12 | 就近连接点应合并 | DOT 无邻近合并 | `merge_segments` + `add_junctions` 邻近合并 |
| 13 | 标签乱、需对齐分置两侧 | text_layout VALUE 锚 (x-5,y-50)/$LOCATION (x-5,y+220) **固定偏移不随 R 1/2/3 旋转** | 标签偏移应用 rotate_point + R 行同步；两侧分置 |
| 14 | GND 长线飞线不规范 | `_fill_gnd_symbols` threshold=2000 允许长线 | GND 就近聚类 + 电线长度限制 |
| 15 | 电线引出先延伸再拐弯、不穿 GND | stub 直出无引出段（final 版）；detour 有但无避让 | stub_lead 引出段 + 避让检测 |
| 16 | IO port 用网络名而非 IOPORT、放芯片附近 | `_ioport_position_cfg` 右缘单列（edge_layout）或右上角 8 个一行；用户要求网络名跨页 | 页内网网络名优先（Phase XV 已做部分）；跨页口位置优化 |
| 17 | 电线最长长度限制 | 无长度限制逻辑 | 超长断线→网络名远程连接 |

## 四、芯片渲染问题（page7/8/9/10/11/13/14/16/17/22）

- 现象：芯片只显示标签无图形，周围密集连接点"织网"
- 根因：占位符号库缺失（SPCOCN-515）→ Cadence 找不到 U6H_PH.SYM.1.1 → 不渲染图形只显示文本；引脚坐标仍在 → WIRE 全打上去形成"织网"
- 17:18 版 SPCOCN-515 消除，但用户仍报"芯片只有标签"（aes6 版）→ 说明占位符号渲染仍不完整（可能缺 entity 目录/symbol.tag）
- **修复方向**：占位库结构补全（entity/master.tag）+ 模拟图标新方案（见需求清单）

## 五、架构师权威问题清单（16 条，代码级根因核实）

| # | 问题 | 根因（代码级） | 严重度 | 页面 | 修复方向 |
|---|------|----------------|:--:|------|----------|
| 1 | SPCOCN-542 PLACEHOLDER 被删 | csa_writer.py:2141 发射 `FORCEPROP 1 LAST PLACEHOLDER 1`，但 placeholder_lib.py:326-376 `_symbol_css` **未声明 PLACEHOLDER**（只有 OUTLINE/$LOCATION/VALUE/PART_NAME/PATH）→ 未声明默认属性被删（SPCOCN-545 提示 STICKY）；04p4 惯例：凡 CSA 发射的属性均在 symbol.css 有 `P` 声明 | P1 | 全部占位页 | ①补 `P "PLACEHOLDER"` 声明并 STICKY ②或改用已声明属性（VALUE/PART_NAME）+ `_PH` 后缀标识 |
| 2 | SPCOCN-543 RF_SW SPN 7/8 被删 | RF_SW symbol.css 仅 6 引脚（IN/OUT/GND1-4），实例 8 引脚；`_resolve_pin_offset`(csa_writer.py:1719-1774) 对 7/8 走 `_fallback_pin_offsets`(2952) 启发式 → LASTPIN 坐标不在 symbol 引脚上 → 删属性 | P1 | p5 | LASTPIN 前校验坐标是否命中 css 引脚，未命中不发射（或标 NC）；引脚数不匹配改用占位/temp_lib |
| 3 | SPCOCN-543 CAPACITOR 等（aes6 残留） | $PN 格式已对齐 04p4（`_lastpin_pn`:2576 与 04p4 page9 L63-71 一致）；**仅旋转实例(R 2/R 3)仍删 SPN/SIG_NAME**。候选：①"R 行+元件级 SIG_NAME LASTPIN"组合无 04p4 先例（04p4 旋转元件仅 $PN 见 page11 RESISTOR R1；SIG_NAME 只在电源 FORCEPROP 3 无 R 行）②`_unique_pin_coord`(2370) nudge 偏离 symbol 引脚 ③旋转变换与 Cadence R 行不一致 | P1 | p5-7,10-13,16-17,22-23 | 受控 A/B 实测三组（旋转+$PN / 旋转+$PN+SIG / 非旋转+SIG）定案；未命中坐标不发射 |
| 4 | SPCOCN-515 library missing | 12:00 版 `write_to_hdl_lib` 未写入（0 cell）；17:18 已修复（15 cell）。接线：csa_writer.py:1237-1248 + output_manager.py:938 cds.lib `DEFINE hdl_lib ./hdl_lib` | P0(12:00)/已修 | p5,7-14,16-17,22-23 | 保持统一写出 + 单测断言 `_PH` cell 存在 |
| 5 | 芯片不渲染（12:00 p7-11） | 同 #4：符号缺失 → Cadence 只渲染属性标签 | P0(12:00)/已修 | p7-11 | 同 #4 |
| 6 | 模拟图标引脚向内/标签重叠/竖直 | ①placeholder_lib.py:75-83 大芯片 4 列分布 x=±100 **在 body 内** → "引脚向内"（违反规范"IC 管脚只左右分布"）；②per_col>12 时 pitch=25 < 规范最小 2 格点(50) → 标签重叠；③`_lastpin_pn`(2602) `R 1` 竖直 $PN 与 css 水平标签叠加 | P1 | 全部占位芯片 | 引脚仅左右边缘分布、短线外引 50、pitch≥50；占位不发射 $PN；css 标签字号 32 样式 0 水平、左靠左右靠右 |
| 7 | U18/U20 匹配错 | mapping.csv:1052-1053 U18/U20→ch347(fuzzy 0.4475)，CH347 20 脚 vs sot95p285x112-6n 6 脚；power_ic.yaml(D4) 规则未实写 | P1 | p5 | 回填 power_ic.yaml 6 脚稳压规则；或默认走 temp_lib 模拟图标 |
| 8 | C534/C354 偏右引脚未接 | 12:00 坐标映射偏差；final3 已为正常 CAPACITOR 块（page5/page16），待复测。候选：CoordTransform.map_page + 旋转 offset 组合 | P2(待复测) | p5,p16 | 复测确认；吸网格源头已修(_snap25) |
| 9 | ①冗余连线 ②③连接点过多需化简 | wire_layout.py:109-568 每网独立 trunk、无跨网共用总线、无端点合并；compute_dots(514) 每交点一个 DOT | P1 | 全部 | 新增 wire_simplifier：共线合并、就近端点/DOT 合并、同网同侧引脚先短接 trunk 再引出（page8 并联电容 C399 等） |
| 10 | ④⑦ GND 过多/重叠/放芯片上 | csa_writer.py:1822-1975 `_plan_and_inject_gnd_symbols` 每芯片 1 个、无区域合并、无重叠检测、无下方放置约束 | P1 | 全部 | GND 区域聚类共用 + 固定元件下方 + 避让芯片 outline + 距离阈值（gnd_distribution 配置扩展） |
| 11 | ⑤⑥⑮ 电线凸出折回/自重叠 | detour_router.py:136-285 `_route_horizontal/_vertical + _lead_point` stub 引出后 U 形返回、无"先延伸再拐弯"保证、无自身/元件重叠检查 | P1 | 全部 | lead-out 增强：掉头前外引≥stub_lead；禁止与本体/他线/元件 outline 相交 |
| 12 | ⑧⑨⑩ 重叠检测需统一 | overlap_detector.py:27-178 仅元件-元件矩形报告；电线/连接点/GND/标签无统一检测 | P1 | 全部 | 新建 core/geometry/collision.py 统一函数（rect/point/segment/label×膨胀边距+引脚避让），全类型复用 |
| 13 | ⑬ 标签对齐/旋转 | text_layout.py:135-260 VALUE/$LOCATION 仅 8 方向微调，未按规范两侧分置+跨元件对齐+随旋转同步 | P1 | 全部 | 增强：VALUE 右上/左上、$LOCATION 左/右下（随 R 行旋转）；同排对齐线；网络名 7.5 格点(375) |
| 14 | ⑯ IO port 改网络名 | ioport 目前独立 IOPORT 符号（csa_writer.py:2470 `_emit_ioport_block`）；用户要求跨页网用网络名（规范 §3.2"同层不加 port"） | P1 | 全部 | 新增 net_name_connect：跨页网以 SIG_NAME 标签表达，IOPORT 符号默认不生成（con/xcon 输出策略待确认） |
| 15 | ⑭⑰ 电线/GND 最长限制 | 路由无长度上限；超长 GND 飞线（左上 GND→右上 port） | P1 | 全部 | 路由后长度检查：超阈值断开改用网络名；GND 就近放置 |
| 16 | p21 PQ2016 / p18-20 FILTER/INTERFACE/CONNECTOR SPN 删 | 同 #2 模式：实例引脚数 > symbol 引脚数 → fallback 坐标未命中 | P1 | p18-21 | 同 #2 修复方向 |

## 六、代码级问题总表（工程师 14 条 + 主理人补充）

| # | 位置 | 问题 | 修复建议一句话 |
|---|------|------|----------------|
| 1 | placeholder_lib.py:292 | cell 目录小写 vs Cadence 大写查找 → SPCOCN-515 库缺失 | 目录改大写/同时生成大小写别名 |
| 2 | csa_writer.py:2141-2146 | PLACEHOLDER 属性带 PAINT/DISPLAY INVISIBLE → 当默认属性被删(SPCOCN-542) | 按 golden 无 PAINT 块重写；必要时 SET STICKY |
| 3 | csa_writer.py:2620-2621 | SIG_NAME LASTPIN 块含 PAINT MONO+INVISIBLE，违 04p4 | 删除 PAINT/INVISIBLE 两行 |
| 4 | csa_writer.py:2000-2016 | GND 只避其他 GND，不避元件/引脚/线 → 放芯片上 | 复用统一重叠检测（元件轮廓+引脚坐标） |
| 5 | csa_writer.py:1822-1915 | GND 每芯片 1 个、无近区合并 → 过多重复 | 距离聚类合并共享 GND |
| 6 | detour_router.py:160-176/199-214 | 引脚 x 加入 trunk_xs → 主干画死段"凸出又折回" | trunk_xs 只含 lx 与跨度端点 |
| 7 | wire_layout.py:376-392 | 仅同向共线检测，异向 stub×trunk 交叉漏检→短路 | 增异向相交检测 |
| 8 | wire_layout/detour | 无电线自重叠、stub 不避元件体 | 全部段过 outline 避让+自交检查 |
| 9 | wire_layout.py:514-547 | DOT 不合并、可落在元件内 | 邻近合并+dot 避体 |
| 10 | csa_writer.py:2157/2233 + text_layout.py:167-178 | 标签不随旋转 | 标签偏移应用 rotate_point+R 行同步 |
| 11 | csa_writer.py:1568-1690 | `_unique_pin_coord` 挪引脚后无 QA → C354 偏右未接 | 路由后 QA：LASTPIN==WIRE 端点且引脚在 outline 内 |
| 12 | overlap_detector.py | 仅元件vs元件，非统一函数(用户10) | 重构为通用 intersect 复用给线/DOT/GND |
| 13 | main_window.py:492-496 | GUI 转换不透出 routing 开关 | SettingsDialog+worker 参数扩展 |
| 14 | manual_matches.py:177 | pin_mapping 恒空，无引脚级映射 | 扩 yaml schema+apply 引脚映射 |
| 15 | placeholder_lib write_to_hdl_lib | 缺 entity/ 目录（真实库有 pc.db/verilog.v） | 补 entity 结构（主理人独立验证） |
| 16 | csa_writer _ioport_position_cfg | IOPORT 全右缘单列，用户要求网络名跨页 | 页内网网络名优先；跨页口就近芯片 |

## 七、严重度分级

| 优先级 | 项 | 说明 |
|:---:|------|------|
| **P0** | SPCOCN-543 SIG_NAME PAINT（#3）、SPCOCN-542 PLACEHOLDER（#2）、占位库结构（#1/#15） | 报错刷屏 + 芯片不渲染，阻塞后续实测 |
| **P0** | GND 放芯片上（#4）、标签不随旋转（#10）、引脚未接 QA（#11） | 电气/视觉硬伤 |
| **P1** | 冗余连线/连接点合并（wire_simplify 模块）、GND 聚类（#5）、凸出折回（#6）、异向交叉（#7）、统一重叠函数（#12） | 美观化核心，用户 17 条主体 |
| **P2** | GUI 开关透出（#13）、pin_mapping 扩展（#14）、IOPORT 位置策略（#16） | 新需求配套 |

## 八、用户决策与落地优先级（2026-08-12 追加）

### 8.1 用户决策记录

| # | 决策项 | 决策 |
|---|--------|------|
| D1 | SPN 删除精确机制 | 需详细解释 + 受控 A/B 实测定案（架构师方案研究进行中） |
| D2 | IOPORT→网络名 | **同步去除，con 层也可以去除**（CSA + con 都改网络名表达） |
| D3 | temp_lib 引脚标签 | **显示功能名**（gnd/pwr/rst 等，对应 CIS 原引脚标签）；BGA 用大矩形四边引脚分布（同 CIS 原图）；引脚标签要旋转和对齐 |
| D4 | GND 合并半径 | 2000 单位可配，先试，不行用户反馈 |
| D5 | 电线最长长度阈值 | 5000 单位可配 |
| D6 | GUI 框架 | 沿用 PySide6，内嵌新面板或弹窗 |
| D7 | chip_config vs manual_matches | 用 chip_config 覆盖 manual_matches；不允许冗余，可合并统一 |
| D8 | 模拟图标 cell 名 | 保留 `_PH` 后缀 + MOCK 标注（同意） |
| D9 | temp_lib git | 不提交（生成物） |
| D10 | 腾挪范围 | **不移动芯片本体，只能移动 GND、标签、跨页信号网络名** |
| D11 | 标注语言 | 中英双标（`MOCK/模拟图标`），字号 24（批准） |

### 8.2 开发优先级（用户确认）

| 优先级 | 项 | 说明 |
|:---:|------|------|
| **P0** | SPCOCN-543 SIG_NAME PAINT（#3）、SPCOCN-542 PLACEHOLDER（#2）、占位库结构（#1/#15） | 报错刷屏 + 芯片不渲染，阻塞后续实测 |
| **P0** | GND 放芯片上（#4）、标签不随旋转（#10）、引脚未接 QA（#11） | 电气/视觉硬伤 |
| **P1** | 冗余连线/连接点合并（wire_simplify 模块）、GND 聚类（#5）、凸出折回（#6）、异向交叉（#7）、统一重叠函数（#12） | 美观化核心，用户 17 条主体 |
| **P2** | GUI 开关透出（#13）、pin_mapping 扩展（#14）、IOPORT 位置策略（#16） | 新需求配套 |

### 8.3 SKiDL 研究落地顺序（结合 phase17-research-a-star-routing.md）

1. **P0**：移植 cleanup_wires（merge_segments/trim_stubs/remove_jogs/add_junctions）→ wire_simplifier.py（MIT）
2. **P1**：add_placement_bboxes 思想（符号 bbox + 引脚侧通道）重构统一碰撞函数 M2，margin=GRID(25)；GND 改 place_net_terminals 式"绕块边缘+就近接入"
3. **P1/P2**：create_routing_tracks 非均匀轨道增强 _find_lane；rank_net 短网先布 A/B
4. **远期**：力导布局（push_and_pull α 调度）仅用于 --aesthetic-placement；A* 迷宫留自动布局场景

## 九、二期实现状态更新（2026-08-12）

### 9.1 用户问题答复后新增实现

| 项 | 状态 | 说明 |
|----|:---:|------|
| 电线化简（问题 9/12） | ✅ 已实现（一期 M4） | v7 p0+simplify WIRE=5031→3424（**-32%**，同基线公平对比） |
| 连接点合并（问题 12） | ✅ 已实现（M4 add_junctions） | 仅 T/X 真交点 + dot_merge=50；wire_simplify.enabled=true 时生效 |
| **GND 聚类合并（问题 4"就近共用"）** | ✅ **二期新增** | `gnd_distribution.cluster_radius=2000`（用户 D4）：距离≤半径的芯片 GND 聚簇共享 1 个符号；v8 实测 GND 19→97 |
| 非均匀轨道（问题 13 后半） | ✅ 二期实现 | `--nonuniform-tracks`：_collect_tracks + _find_lane 轨道优先 |
| 短网先布 A/B | ✅ 二期实现 | `--net-order short_first`（v2）+ 长网先布（v1）双版本 |

### 9.2 二期关键验证

- **v5 电线多的解释**：detour 模式（stub 引出段美化）基线与 p0 不同；化简确实生效（纯 detour 12088→6764，-44%）。**与 v1 同基线的公平对比是 v7（p0+simplify）=3424，-32%**
- **GND 分布调试结论**：合成 GND 符号复用 GND_POWER body（refdes 通过属性区分），page5 GND_POWER 1→6、全工程 19→97 为分布+聚类生效证据
