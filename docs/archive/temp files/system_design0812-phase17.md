# CIS2HDL Phase XVII — 两版实测报错根因 + 新需求实现方案（架构师交付）

> 架构师：高见远（software-architect）｜主理人：齐活林（汇总）  
> 范围：①两版 Cadence 实测报错（12:00 aes / 17:18 aes6）16 条问题清单与根因  
> ②新需求实现方案（temp_lib 模拟图标 / GUI 手动配置 / 默认模拟原理图 / 统一重叠检测与腾挪）  
> 基线：Phase XVI 交付（583 passed / 5 skipped）  
> 性质：**只读设计** —— 不改任何源码；全部结论基于源码行号 + EDIF/DEHDL 语义 + HG5015/04p4/8367 实测。  
> 关联：`phase17-problem-list.md`（问题清单明细）、`phase17-research-a-star-routing.md`（A* 调研）、  
> `phase17-requirement-scheme.md`（需求方案 v0.9）

---

## 0. 结论速览（TL;DR）

| #    | 需求                          | 方案一句话                                                                                                                                  |                        默认开关                        |        电气风险        |    实现量    |
| ---- | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------: | :----------------: | :-------: |
| P1-1 | SPCOCN-542 PLACEHOLDER 被删   | symbol.css 补 `P "PLACEHOLDER"` 声明 + STICKY；或改用已声明属性（VALUE/PART_NAME）+ `_PH` 后缀标识                                                       |                         随修复                        |          无         |   ~10 行   |
| P1-2 | SPCOCN-543 引脚属性被删           | 三类根因：①SIG_NAME LASTPIN 块 PAINT 违 golden ②旋转实例 R 行+SIG_NAME 组合无先例 ③引脚数不匹配 fallback 坐标未命中 → LASTPIN 前校验命中 css 引脚，未命中不发射；旋转实例做受控 A/B 实测定案 |                         随修复                        |          无         |  30-60 行  |
| P1-3 | 芯片不渲染                       | 12:00 占位符号未写入 hdl_lib（0 cell）→ 17:18 已修（15 cell）；补 entity 目录结构                                                                         |                        已修+补                        |          无         |    20 行   |
| P1-4 | 模拟图标引脚向内/重叠                 | 4 列分布 x=±100 在 body 内 + pitch=25 违规范 → 引脚仅左右边缘、短线外引、pitch≥50                                                                           |                        随 M1                        |          无         |    随 M1   |
| R1   | 匹配照常（csv/html）              | 匹配管线不动                                                                                                                                 |                          —                         |          —         |    0 行    |
| R2   | temp_lib 模拟图标               | 新模块 `mock_icon_lib.py`：按硬件规范绘制 DEHDL cell 到 `output/temp_lib/`                                                                         |               `temp_lib.enabled=true`              |      无（引脚几何同源）     | 250-350 行 |
| R3   | GUI 手动配置                    | 新面板 `chip_config_panel.py`（复用 match_review 三栏 + 可编辑引脚映射表）→ chip_config.yaml → D3 注入点覆盖                                                 |                       GUI 内开关                      |      无（用户确认才写）     | 400-600 行 |
| R4   | 默认模拟图标原理图 + 标注              | 未匹配/低置信芯片 → temp_lib 图标；原理图放 NOTE"模拟图标，无标准电气特性"                                                                                        |                         默认开                        |          无         |    随 R2   |
| R5   | 统一重叠检测 + 腾挪                 | `core/geometry/collision.py` 统一碰撞（rect/point/segment/label）+ `placement_fitter.py` 腾挪                                                  | `overlap.unified=true`、`placement.auto_move=false` |      无（只移动可动件）     | 300-400 行 |
| R6   | 电线化简 + GND 合并 + 标签对齐 + 长度限制 | `wire_simplifier.py`（SKiDL cleanup_wires 移植）+ GND 聚类 + text_layout 增强                                                                  |            `wire_simplify.enabled=false`           |   无（同网段合并、引脚坐标不动）  | 400-600 行 |
| R7   | 跨页网用网络名                     | `net_name_connect.py`：SIG_NAME 表达跨页网，IOPORT 默认不生成                                                                                      |             `ioport.use_net_name=true`             | 待确认（con/xcon 输出策略） | 150-250 行 |

**五条铁律（延续 Phase XIV-XVI）**：

1. **连接判定 = 坐标重合**：WIRE 端点必须精确等于 LASTPIN 坐标——任何化简/腾挪不得移动端点引脚坐标。
2. **全坐标 25 网格**：所有新坐标仍 `_snap25`。
3. **新功能独立模块 + 配置开关，可回退**：temp_lib/overlap/placement/wire_simplify/net_name_connect 均独立开关。
4. **匹配管线不动**：csv/html/top3 照常生成（R1 是硬约束）。
5. **悬空引脚直接悬空**：不强制连接；报告标注 `[HANGING]` 待 Allegro 布线。

**决策记录（方案选择）**：

- **模拟图标 vs 占位符号**：placeholder（占位方块）升级为 mock_icon_lib（模拟图标，按规范绘制、标注清晰）；placeholder 保留为逃生舱（`temp_lib.enabled=false`）。
- **PLACEHOLDER 属性 vs 可见文本**：属性会被 Cadence 删（SPCOCN-542），改用**图形内可见文本**"MOCK/模拟图标"标注（symbol.css P 指令）——规避删除问题且用户可见。
- **IOPORT vs 网络名**：用户明确要求网络名跨页（规范 §3.2"同层不加 port"）→ `net_name_connect` 优先；con/xcon 输出策略待用户确认。
- **A* 迷宫 vs 化简后处理**：A* 对固定布局是过度设计（方案文档 §4.1 结论）；**移植 SKiDL cleanup_wires 做后处理化简**（MIT、量小、直接解决"电线爆炸"），A* 留远期（自动布局时才启动）。

---

## 一、两版报错根因（完整清单见 phase17-problem-list.md）

### 1.1 12:00 版（output_phaseXIV_aes）核心问题

- **芯片不渲染** = 占位符号未写入输出 hdl_lib（`output_phaseXIV_aes/hdl_lib` 中 0 个 `_PH` cell）→ FORCEADD U6H_PH 引用不存在 cell → SPCOCN-515 ×13 + 只显示标签无图形 + 周围"织网"（引脚坐标在但符号不在）。
- SPCOCN-543 ×182（CAPACITOR/J4_PH/RF_SW/PQ2016 等）。
- 用户 17 条共性问题完整记录（冗余连线/连接点过多/GND 过多/电线重叠/标签乱/IO port 位置等）。

### 1.2 17:18 版（output_phaseXVI_aes6）残留

- SPCOCN-515 消除（占位写入 15 cell）。
- SPCOCN-542 ×15（PLACEHOLDER 属性被删）+ SPCOCN-545 ×13（STICKY 提示）。
- SPCOCN-543 ×116，集中在：①**旋转实例**（R 2/R 3）②**引脚数不匹配**（RF_SW 8 脚 vs symbol 6 脚、PQ2016、FILTER 等）③CAPACITOR 普通实例。

### 1.3 关键代码证据

| 证据                                         | 位置                                                           |
| ------------------------------------------ | ------------------------------------------------------------ |
| PLACEHOLDER 属性发射（未声明）                      | csa_writer.py:2141-2146                                      |
| placeholder symbol.css 属性声明（无 PLACEHOLDER） | placeholder_lib.py:326-376                                   |
| SIG_NAME LASTPIN 块（含 PAINT MONO+INVISIBLE） | csa_writer.py:2609-2622                                      |
| 04p4 golden SIG_NAME 块（无 PAINT）            | 04p4 page9.csa L365                                          |
| 占位库写入路径                                    | csa_writer.py:1237-1248；cds.lib DEFINE output_manager.py:938 |
| 大芯片 4 列分布 x=±100（body 内）                   | placeholder_lib.py:75-83                                     |
| fallback 引脚偏移（未命中时）                        | csa_writer.py:2952 `_fallback_pin_offsets`                   |
| GND 分布（每芯片 1、无重叠检测）                        | csa_writer.py:1822-1975                                      |
| detour stub 引出 U 形返回                       | detour_router.py:136-285                                     |
| overlap 仅元件-元件                             | overlap_detector.py:27-178                                   |
| text_layout 标签不随旋转                         | text_layout.py:135-260                                       |

---

## 二、新需求实现方案（8 模块）

### 需求清单

| #  | 需求                                                | 优先级 | 依赖        |
| -- | ------------------------------------------------- | :-: | --------- |
| R1 | 芯片/connector 仍按原算法匹配，csv/html 匹配结果不变              |  P0 | 无（匹配管线不动） |
| R2 | temp_lib 模拟芯片图标（独立库，不污染 hdl_lib）                  |  P0 | R1        |
| R3 | GUI 手动配置面板（逐芯片/connector：引脚映射、连接状态、尺寸/挤压检查、腾挪）    |  P1 | R2        |
| R4 | 默认原理图用模拟图标 + "模拟图标，无标准电气特性"标注                     |  P0 | R2        |
| R5 | 统一重叠检测 + 电线化简 + GND 合并 + 标签对齐 + 长度限制（吸收 17 条共性问题） |  P1 | R4        |

### 实现清单

| #  | 模块（文件路径）                           | 职责                                                                                                                                                     | 复用点                                                                              | 配置开关                                                                 |
| -- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| M1 | `core/writer/mock_icon_lib.py`     | temp_lib 生成：矩形 body + 左右边缘短引脚 + 水平引脚标签 + 芯片名/序号标注，按硬件规范（宽 6/10/24 格、pitch≥50）输出 DEHDL cell（symbol.css/chips.prt/master.tag/entity）到 `output/temp_lib/` | placeholder_lib.distribute_ic_pin_offsets（改边缘分布）、write_to_hdl_lib 模板             | `temp_lib: {enabled: true, dir: "temp_lib"}`                         |
| M2 | `core/geometry/collision.py`       | 统一几何碰撞：rect/point/segment/label 相交、膨胀边距、引脚避让、最大偏移求解                                                                                                    | overlap_detector.py:130 `_intersection` 抽取；wire_layout body_outlines             | `overlap: {unified: true}`                                           |
| M3 | `core/writer/placement_fitter.py`  | 尺寸适配检查 + 挤压检测 + 腾挪（用 M2 找空位）                                                                                                                           | overlap_detector.detect、wire_layout.\_find_lane 车道思想                             | `placement: {check: true, auto_move: false}`                         |
| M4 | `core/writer/wire_simplifier.py`   | 共线合并、就近连接点/DOT 合并、同网同侧短接 trunk、GND 区域合并、超长断开改网络名                                                                                                       | wire_layout.compute_dots、detour_router.\_dedupe_wires、SKiDL cleanup_wires        | `wire_simplify: {enabled: false, dot_merge: 50, max_wire_len: 5000}` |
| M5 | `core/writer/net_name_connect.py`  | 跨页网用网络名标签（SIG_NAME）表达，IOPORT 符号默认不生成                                                                                                                   | `_sig_name_on_wire`(csa_writer:2625)、ioport_audit 网名一致性                          | `ioport: {use_net_name: true, emit_ioport: false}`                   |
| M6 | `core/writer/pin_connect_audit.py` | 逐引脚连接状态（已接/悬空/网名不匹配/引脚名不匹配），供 GUI+报告                                                                                                                   | \_compute_pin_geometry net_pin_map、ioport_audit 数据源铁律                            | `pin_audit: {enabled: true}`                                         |
| M7 | `gui/panels/chip_config_panel.py`  | 逐芯片/connector 配置面板：图标预览、可编辑引脚映射表、状态列、尺寸/挤压结果、自动腾挪按钮、保存                                                                                                 | match_review.py（三栏+引脚表改可编辑）、candidate_selector.py、manual_matches.py（扩 pin_map 节） | GUI 内开关；输出 `chip_config.yaml` 由 `--chip-config` 注入                   |
| M8 | 标注模块（并入 M1）                        | 原理图放置 NOTE 文本"模拟图标，无标准电气特性" + 报告节                                                                                                                      | csa_writer NOTE/PAINT 已有模式                                                       | `temp_lib.annotate: true`                                            |

### 关键数据流（引脚映射 + GUI → 转换）

```
CIS 实例(refdes, 尺寸, 引脚名/号, 网名)
  └→ 原匹配管线(不动) → csv/html 照常
  └→ M6 pin_connect_audit: 每引脚 {net, 目标symbol引脚, 状态✓/✗/悬空}
       └→ M7 GUI 面板: 手动改目标引脚/标记悬空 → chip_config.yaml
            └→ 注入点同 manual_matches(Phase XIV D3, _stage_match 后覆盖) + 新增 pin_map/section
  └→ M1 mock_icon_lib: 未匹配/低置信芯片 → temp_lib cell(Uxx_PH)
       └→ M3 placement_fitter: 尺寸/挤压检查 → 必要时腾挪
       └→ M4 wire_simplifier + M5 net_name_connect + M2 统一碰撞
            → CSA(CDS_LIB temp_lib) + cds.lib(DEFINE temp_lib ./temp_lib)
```

### GUI 面板布局（复用 match_review 三栏 + 增强）

```
┌──────────────────────────────────────────────────────┐
│ 左=芯片/connector 列表（按页分组、低置信红标）          │
│ 中=图标预览（M1 几何渲染）+ 尺寸/挤压报告               │
│ 下=引脚映射表（CIS引脚|CIS网名|目标引脚|目标名|状态，    │
│    目标引脚列可下拉编辑）                               │
│ 按钮: [保存配置][自动腾挪][标记悬空]                     │
└──────────────────────────────────────────────────────┘
信号 `config_saved(refdes, mapping, placement)` → 写 YAML → 重跑转换
```

---

## 三、待明确问题（需用户决策）

| # | 问题                                                                      | 建议                               |
| - | ----------------------------------------------------------------------- | -------------------------------- |
| 1 | SPN 删除精确机制：需 Cadence 控制台受控 A/B（旋转+$PN / 旋转+$PN+SIG_NAME / 非旋转+SIG_NAME） | 先按"未命中不发射"修复，A/B 实测定案            |
| 2 | IOPORT→网络名：con/xcon/cpm 是否同步去 IOPORT，还是仅 CSA 视觉层替换？                     | 建议 CSA 视觉层优先，con 层待用户确认          |
| 3 | temp_lib 图标内容：引脚标签显示功能名还是引脚号？BGA 200+ 引脚超高 body 是否接受？                   | 功能名优先；超高 body 分页排布待定             |
| 4 | GND 合并半径默认值                                                             | 建议 2000 单位可配（用户说"近距离七八个元件共用一个"）  |
| 5 | 电线最长长度阈值                                                                | 建议 5000 单位可配                     |
| 6 | GUI 框架：PySide6（推荐）vs tkinter candidate_selector                         | PySide6 main_window 内嵌新面板        |
| 7 | chip_config.yaml 与 manual_matches.yaml 并存优先级                            | 建议 chip_config 覆盖 manual_matches |

---

*架构师交付（2026-08-12）。已核实证据：placeholder cell 写入路径 csa_writer.py:1237-1248；cds.lib DEFINE output_manager.py:938；04p4 旋转 RESISTOR 参考 page11；RF_SW css 6 脚 vs 实例 8 脚；12:00 aes 0 个 \_PH cell vs 17:18 15 个。*

---

# 追加：用户决策落地 + 开发排期（2026-08-12 第二轮）

## 一、用户决策全量记录（待明确问题已全部答复）

| # | 问题 | 用户答复 |
|---|------|----------|
| 1 | SPN 删除精确机制 | 需详细解释 + 受控 A/B 实测方案（架构师专项研究，见本文档后续补充章节） |
| 2 | IOPORT→网络名：con/xcon/cpm 是否同步去 | **同步去除，con 层也可以去除**（CSA + con 都改网络名表达，M5 net_name_connect 全链路） |
| 3 | temp_lib 引脚标签：功能名 vs 引脚号 | **显示功能名**（gnd/pwr/rst 等，对应 CIS 原引脚标签）；**BGA 用大矩形四边引脚分布**（同 CIS 原图）；引脚标签要旋转和对齐 |
| 4 | GND 合并半径 | 2000 单位可配，先试，不行用户反馈 |
| 5 | 电线最长长度阈值 | 5000 单位可配 |
| 6 | GUI 框架 | 沿用 PySide6，内嵌新面板或弹窗 |
| 7 | chip_config vs manual_matches 优先级 | **chip_config 覆盖 manual_matches 对应内容**；深度分析两文件及函数，**不允许代码/文件/配置冗余，可合并统一**（架构师专项研究） |
| 8 | 模拟图标 cell 名 | 保留 `_PH` 后缀 + MOCK 标注（同意） |
| 9 | temp_lib 是否提交 git | 不提交（生成物） |
| 10 | 腾挪是否移动芯片本体 | **不移动芯片本体，只能移动 GND、标签、跨页信号网络名** |
| 11 | 标注语言 | 中英双标（`MOCK/模拟图标`），字号 24（批准） |

## 二、开发排期（按用户确认的优先级）

```
[P0 先行]  SPCOCN-542/543 修复（PLACEHOLDER 声明/SIG_NAME 去 PAINT/未命中不发射/占位库补 entity）
           GND 放置重叠检测 + 标签随旋转 + 引脚未接 QA
[P1]       wire_simplifier（cleanup_wires 移植）+ GND 聚类 + 统一碰撞 M2 + 腾挪 M3
           temp_lib 模拟图标 M1（BGA 四边 + 功能名标签 + 旋转对齐）+ net_name_connect M5（con 同步）
           pin_connect_audit M6 + GUI 面板 M7（PySide6）
[P2]       GUI 开关透出 + pin_mapping 扩展 + IOPORT 位置策略
[远期]     力导布局（--aesthetic-placement）/ A* 迷宫（自动布局场景）
```

## 三、关键决策更新

| 决策 | 更新 |
|------|------|
| M5 net_name_connect 范围 | **CSA + con 都改网络名**（用户 D2）；xcon/cpm 是否同步待实现时确认 |
| M1 temp_lib 图标 | 引脚标签 = CIS 原功能名；BGA 四边引脚分布（顶/底/左/右）+ 标签旋转对齐（D3） |
| M3 腾挪范围 | 只移 GND/标签/跨页网络名；**芯片本体不动**（D10） |
| M7 GUI | PySide6 内嵌面板或弹窗（D6），复用 MatchReviewPanel 骨架 |
| 配置文件 | chip_config 覆盖 manual_matches；合并统一防冗余（D7，架构师设计） |
| M4 wire_simplifier | 移植 SKiDL cleanup_wires（MIT），`wire_simplify.enabled` 开关 |

*追加完成（2026-08-12 第二轮，软件团队）。*

---

# 追加：二期实现（非均匀轨道/短网先布/GND 聚类/对比包 v7-v8）（2026-08-12）

## R2 实现

| 项 | 实现 | 验证 |
|----|------|------|
| 非均匀轨道 | `_collect_tracks`(wire_layout.py L444) outline bbox 边坐标 + `_find_lane` 轨道优先 | v3 WIRE=5089（对齐性提升） |
| 短网先布 | `_net_priority_key`(L55) 负号键 + `--net-order` | v2 WIRE=5034（路径变化） |
| **GND 聚类合并** | `_plan_and_inject_gnd_symbols`(csa_writer.py L1943) 贪心最近邻聚类 + `cluster_radius=2000` | v8 GND 19→97 |
| 版本对比 | 8 版本（v1-v8）输出到 output_phaseXVII_compare/ | 全部 SUCCESS 84% |

## 关键验证

- **v7（p0+simplify）=3424 vs v1=5031（-32%）**：与基线同模式的化简收益
- **v5 澄清**：detour 模式基线与 p0 不同；纯 detour 12088→6764（-44%）
- **GND 分布调试结论**：合成 GND 复用 GND_POWER body，page5 1→6 为分布证据

*二期追加完成（2026-08-12）。*
