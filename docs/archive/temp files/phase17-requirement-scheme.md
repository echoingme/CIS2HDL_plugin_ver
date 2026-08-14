# Phase XVII 新需求实现方案（2026-08-12）— temp_lib 模拟图标 / GUI 手动配置 / 默认模拟原理图

> 方案人：主理人齐活林（基于架构师/工程师核对 + 独立研究；架构师详细设计补充中）
> 用户需求原文要点：
> 1. 芯片和 connector 按原算法匹配，照常生成 csv、html 匹配结果
> 2. 根据尺寸/引脚名/芯片名/序号绘制**模拟芯片图标**，放 **temp_lib**（不污染 hdl_lib）
> 3. GUI 手动配置每个芯片/connector；配置后分析引脚连接/尺寸/挤压；重叠检测+腾挪；引脚级手动匹配；悬空引脚直接悬空（Cadence Allegro 自行布线）
> 4. 默认（及 GUI 不手动匹配时）用模拟图标生成原理图，美观准确；标注"模拟图标，无标准电气特性"

---

## 一、需求清单

| # | 需求 | 优先级 | 依赖 |
|---|------|:---:|------|
| R1 | 匹配管线照常运行，生成 csv/html/top3 等匹配结果 | P0 | 现有匹配管线（零改动） |
| R2 | **temp_lib 模拟芯片图标生成器**：根据芯片/connector 的尺寸、引脚名称、芯片名称、芯片序号绘制模拟图标，写入独立 temp_lib 目录 | P0 | 引脚数据（已有）、轮廓规则（硬件规范 §2.2.2） |
| R3 | 默认转换使用模拟图标替代未匹配芯片/connector（替代现有 placeholder 占位符号） | P0 | R2 |
| R4 | 模拟图标上明确标注"模拟图标，无标准电气特性"（PLACEHOLDER/MOCK 标注，且 Cadence 不删除——用可见文本而非被删属性） | P0 | R2 + SPCOCN-542 修复 |
| R5 | GUI 手动配置面板：每个芯片/connector 可分别选择匹配（复用 MatchReviewPanel + candidate_selector） | P1 | GUI 现有骨架 |
| R6 | 配置后自动分析：引脚是否都有匹配连接 / 尺寸是否合适 / 是否挤压周围元件 | P1 | R5 + 重叠检测 |
| R7 | 挤压时重叠检测 + 腾挪（自动避让移动） | P1 | 统一重叠函数（问题 #12） |
| R8 | 引脚不对应/未连接/名称不匹配时 GUI 手动选择 CIS 引脚 ↔ 目标芯片/connector 引脚 | P1 | manual_matches 扩 pin_mapping |
| R9 | 悬空引脚直接悬空，标注待布线（Cadence Allegro 工程师后续布线） | P1 | R8 |
| R10 | GUI 不手动匹配时自动用模拟图标（默认行为） | P0 | R3 |

## 二、实现清单（模块 + 文件路径 + 配置开关）

| # | 模块 | 文件路径（建议） | 职责 | 复用点 | 配置开关 |
|---|------|----------------|------|--------|---------|
| M1 | temp_lib 模拟图标生成器 | `cis2hdl/core/writer/mock_lib.py` | 按尺寸/引脚名/芯片名/序号生成 symbol.css+chips.prt+entity，写入 `output/temp_lib/` | placeholder_lib.py 几何分布、chips.prt 格式 | `temp_lib.enabled=true`（默认） |
| M2 | 统一重叠检测函数 | `cis2hdl/core/writer/overlap_detector.py`（重构） | 通用 bbox/线段/点 相交检测，供元件/线/DOT/GND/标签统一调用 | 现有 `_intersection` + shapely | `overlap.check` |
| M3 | 重叠腾挪器 | `cis2hdl/core/writer/overlap_resolver.py` | 检测到挤压 → 沿最小分离向量移动元件（力导一步） | SKiDL `overlap_force` + alpha 调度 | `overlap.auto_placement=true` |
| M4 | 引脚连接/尺寸分析器 | `cis2hdl/core/diagnostics/pin_analysis.py` | 配置后分析：引脚匹配/未连接/悬空清单 + 尺寸适配 + 挤压检测 | ioport_audit 模型 | `pin_analysis.enabled` |
| M5 | GUI 芯片/connector 配置面板 | `cis2hdl/gui/panels/component_config.py` | 每元件配置：候选选择 + 引脚映射表 + 分析结果展示 | MatchReviewPanel 三栏 + 引脚表 | GUI 内嵌（无开关） |
| M6 | GUI→YAML 写入 | 复用 `manual_matches.py` + candidate_selector `_save_to_yaml` | 配置结果持久化 → 重跑转换 | 现有 D3 | `gui_match.write_manual_yaml` |
| M7 | 引脚级映射 schema | `manual_matches.py` 扩展 | `matches[].pin_map: {cis_pin: hdl_pin}` | 现有 ManualMatch | — |
| M8 | 悬空引脚处理 | `csa_writer.py` 微调 | 未连接引脚：保留 LASTPIN 但不生成 WIRE/SIG_NAME，报告标注"待布线" | P2-2 NC 处理模式 | `pin_analysis.report_hanging` |
| M9 | 模拟图标标注 | `mock_lib.py` symbol.css | 图形内画"MOCK/模拟符号"文本（可见、非属性） | symbol.css P 指令 | 随 M1 |

## 三、实现方案（分模块设计）

### 3.1 M1 temp_lib 模拟图标生成器（核心）

**目标**：为未匹配芯片（U6/U6A-I/U5/U7/U8/U9 等）和未匹配 connector（J4/J26 等）生成"像模像样"的模拟图标，替代现有占位方块。

**目录结构**（与 hdl_lib 解耦，写入 `<output>/temp_lib/`）：
```
<output>/temp_lib/<CELL>/sym_1/symbol.css + master.tag + symbol.tag
<output>/temp_lib/<CELL>/chips/chips.prt + master.tag
<output>/temp_lib/<CELL>/entity/master.tag + pc.db   ← 补真实库结构（问题 #15）
```

**图标绘制规则**（对齐硬件规范 §2.2.2）：
- **body 尺寸**：按引脚数自适应（n≤12 两列 ±150/pitch 100；n>12 四列 -200..200/pitch 50/25——沿用 `distribute_ic_pin_offsets`），矩形 body 用 M 指令 4 条边
- **引脚**：左右两列分布（IC 管脚只左右分布——规范 §2.2.2），短引脚（L 指令 10 单位），引脚名用 C 指令标注（字号 32 小号，外侧对齐）
- **芯片名/序号**：`$LOCATION`/`VALUE` 属性 = refdes + cell 名（如 `U6H_PH`），PART_NAME 同源
- **模拟标注**：body 内部居中画文本 `"MOCK SYMBOL - NO ELECTRICAL PROPERTIES"` 或中文"模拟图标·无电气特性"（P 指令、字号 24、颜色区分）——**用可见图形文本而非 PLACEHOLDER 属性**（规避 SPCOCN-542）
- **cell 名大小写**：目录用大写（与 FORCEADD 一致，修问题 #1）

**数据链路**：
```
匹配结果（未匹配/低置信度 refdes）
  → 取引脚数据（pin_number/pin_name 来自 EDIF）
  → MockLibrary.symbol_for(refdes, section, pins)
  → 生成 symbol.css + chips.prt + entity → temp_lib
  → csa_writer FORCEADD <CELL>..1 + CDS_LIB temp_lib + R 行（旋转/镜像）
  → pin_coords/net_pin_map/WIRE 与现有占位逻辑同源（LASTPIN==WIRE 硬约束）
```

**与 placeholder_lib.py 的关系**：placeholder 是"占位方块"（临时），mock_lib 是"模拟图标"（美观准确、标注清晰）。策略：**默认启用 mock_lib 替代 placeholder**（用户需求 4），placeholder 保留为逃生舱（`temp_lib.enabled=false` 回退）。

### 3.2 M2/M3 统一重叠检测 + 腾挪

**统一检测函数**（用户问题 10 要求单一函数反复调用）：
```python
def detect_collisions(
    geometry_a: list[Rect | Segment | Point],
    geometry_b: list[Rect | Segment | Point],
    margin: int = 25,          # 膨胀一圈（用户问题 8）
) -> list[Collision]:          # 返回所有碰撞对 + 最小分离向量
```
- 内部用 shapely（`LineString.intersects` / `Polygon.intersection`）或手写 AABB+线段相交
- 所有调用方统一：元件vs元件（现有 OverlapDetector）、线vs元件、线vs线、DOTvs元件、GNDvs元件、标签vs标签（text_layout 复用）

**腾挪器**（M3）：检测到碰撞 → 沿最小分离向量移动元件（一次迭代），移动后重新检测（最多 N 轮）。参考 SKiDL `overlap_force` 最小分离向量 + alpha 渐进。只移动可动件（GND 符号、标签优先），不移动固定件（芯片/连接器本体，除非用户确认）。

### 3.3 M5/M6/M7 GUI 手动配置

**面板设计**（复用 MatchReviewPanel 三栏骨架）：
```
┌───────────────────────────────────────────────┐
│ 元件列表（CIS）│ 候选/匹配库 │ 引脚映射表        │
│ - U6H (占位)  │ [temp_lib/U6H_PH] │ CIS引脚 ↔ HDL引脚│
│ - J4  (占位)  │ [hdl_lib/CH347]   │ K18   ↔  18    │
│ - C354(错位)  │ [hdl_lib/C0603]   │ G20   ↔  20    │
│ 配置按钮: [接受匹配] [引脚映射] [分析] [导出YAML]  │
└───────────────────────────────────────────────┘
```

**流程**：
1. 转换后 GUI 展示匹配结果（现有 MatchReviewPanel）
2. 用户选中元件 → 选候选库（temp_lib 优先列出模拟图标）→ 接受
3. 引脚级：CIS 引脚列表 vs 目标符号引脚列表 → 拖拽/选择映射（写入 `pin_map`）
4. 点击"分析"→ 运行 M4 分析器：输出引脚匹配状态/未连接/悬空清单 + 尺寸适配 + 挤压检测
5. 点击"导出 YAML"→ 写 manual_matches.yaml（含 pin_map）→ 重跑转换

**悬空引脚**：分析后未连接引脚 → 保留 LASTPIN（引脚存在）不生成 WIRE，报告中标注 `[HANGING] <refdes>.<pin> 待 Allegro 布线`。

### 3.4 M4 引脚连接/尺寸分析器

配置后对每芯片/connector：
- **引脚匹配**：CIS 引脚数 vs 目标符号引脚数；每个引脚是否有 net 连接
- **尺寸适配**：符号 outline 尺寸 vs 周围元件间距（min_gap=100 单位）；挤压 → 腾挪
- **悬空清单**：`[HANGING]` 输出（供工程师 Allegro 布线参考）

### 3.5 配置开关（routing.yaml 追加，按工程师四步模式）

```yaml
temp_lib:
  enabled: true               # M1 模拟图标（默认开，替代 placeholder）
  lib_name: temp_lib          # 输出库目录名
  mock_text: true             # 图标内画"模拟图标"标注
overlap:
  check: true                 # M2 统一检测（默认转换开）
  margin: 25
  auto_placement: true        # M3 腾挪（可回退）
pin_analysis:
  enabled: true               # M4 引脚/尺寸分析
  report_hanging: true        # 悬空引脚报告
gui_match:
  enabled: false              # M5-M7 GUI 配置（CLI 启动 GUI 时生效）
  write_manual_yaml: "manual_matches_gui.yaml"
```

## 四、待明确问题（用户答复 2026-08-12 ✅）

| # | 问题 | 建议 | 用户答复 |
|---|------|------|----------|
| 1 | 模拟图标 cell 名是否用 `<REFDES>_PH` 还是统一 `MOCK_<TYPE>` | 保留 `_PH` 后缀 + MOCK 标注（避免与真实库冲突） | ✅ 同意 |
| 2 | temp_lib 是否提交 git | 与 hdl_lib 一致不提交（生成物） | ✅ 不提交 |
| 3 | GUI 框架（PySide6 vs tkinter candidate_selector） | PySide6 主窗口内嵌面板（复用 MatchReviewPanel） | ✅ 沿用 PySide6 |
| 4 | 腾挪是否移动芯片本体 | 默认只移 GND/标签，芯片需用户确认（电气安全） | ✅ **不移动芯片本体，只能移动 GND、标签、跨页信号网络名** |
| 5 | "无标准电气特性"标注语言 | 中英双标（`MOCK/模拟图标`），字号 24 | ✅ 批准 |

## 五、落地优先级（用户确认排期 2026-08-12）

| 优先级 | 项 | 说明 |
|:---:|------|------|
| **P0** | SPCOCN-543 SIG_NAME PAINT（#3）、SPCOCN-542 PLACEHOLDER（#2）、占位库结构（#1/#15） | 报错刷屏 + 芯片不渲染，阻塞后续实测 |
| **P0** | GND 放芯片上（#4）、标签不随旋转（#10）、引脚未接 QA（#11） | 电气/视觉硬伤 |
| **P1** | 冗余连线/连接点合并（wire_simplify 模块）、GND 聚类（#5）、凸出折回（#6）、异向交叉（#7）、统一重叠函数（#12） | 美观化核心，用户 17 条主体 |
| **P2** | GUI 开关透出（#13）、pin_mapping 扩展（#14）、IOPORT 位置策略（#16） | 新需求配套 |

### 开发顺序（SKiDL 流水线研究落地）

1. **第一优先级（P0，已排期）**：移植 `cleanup_wires` 的 `merge_segments` + `trim_stubs` + `remove_jogs` + `add_junctions`（MIT 许可，算法完整核实）→ `wire_simplifier.py`，作为 wire_layout 后处理，配置开关 `wire_simplify.enabled`。
2. **第二优先级（P1）**：引入 `add_placement_bboxes` 思想（符号 bbox + 引脚侧通道）重构 `overlap_detector` 为统一碰撞函数（M2），margin 默认 = GRID（25）；GND 放置改为 `place_net_terminals` 式"绕块边缘 + 就近接入"（M4 GND 聚类）。
3. **第三优先级（P1/P2）**：`create_routing_tracks` 非均匀轨道（元件 bbox 边坐标）替代/增强 `_find_lane` 均匀车道；`rank_net` 短网先布做 A/B 对比。
4. **远期**：力导布局（`push_and_pull` α 调度 + rowbased）仅用于 `--aesthetic-placement`（用户已同意可选项定位）；A* 迷宫（OpenRAM `get_edge_cost`）留自动布局场景。

## 六、用户决策记录（2026-08-12 全量）

| # | 决策项 | 决策 |
|---|--------|------|
| D1 | SPN 删除精确机制 | 需详细解释 + 受控 A/B 实测定案（架构师方案研究进行中，见 system_design 补充） |
| D2 | IOPORT→网络名 | **同步去除，con 层也可以去除**（CSA + con 都改网络名表达） |
| D3 | temp_lib 引脚标签 | **显示功能名**（gnd/pwr/rst 等，对应 CIS 原引脚标签）；BGA 用大矩形四边引脚分布（同 CIS 原图）；引脚标签要旋转和对齐 |
| D4 | GND 合并半径 | 2000 单位可配，先试，不行用户反馈 |
| D5 | 电线最长长度阈值 | 5000 单位可配 |
| D6 | GUI 框架 | 沿用 PySide6，内嵌新面板或弹窗 |
| D7 | chip_config vs manual_matches | **用 chip_config 覆盖 manual_matches 对应内容**；深度分析两文件及函数代码，**不允许代码/文件/配置冗余，可合并统一**（架构师设计进行中） |

---

*方案 v1.0（2026-08-12，软件团队）。用户决策已全部记录；SPN A/B 方案与文件合并设计见 system_design0812-phase17.md 补充章节。*

---

# 追加（2026-08-12 二期）：GND 聚类 + 版本对比落地

## 一、GND 聚类合并（用户问题 4"就近七八个元件共用一个 GND"）—— 已实现

- **配置**：`gnd_distribution.cluster_radius: 2000`（用户 D4 默认 2000 可配；0=关闭聚类回退每芯片 1 个）
- **实现**：`_plan_and_inject_gnd_symbols`(csa_writer.py L1943) 芯片 GND 分组后做贪心最近邻聚类——距离 ≤ 半径的芯片聚簇，簇内共享 1 个 GND 符号（簇命名 `GND_<refdes1>_<refdes2>`）
- **验证**：v8（--gnd-distribute）全工程 GND 19→97、page5 1→6；684 passed / 5 skipped

## 二、版本对比补充（v7/v8）

| 版本 | 标志 | WIRE | GND | 说明 |
|------|------|:---:|:---:|------|
| v7_p0_simplify | --wire-simplify | **3424** | 19 | ★ p0+化简（与 v1 同基线，-32%） |
| v8_gnd_distribute | --gnd-distribute | 5102 | **97** | ★ GND 分布+聚类 |

## 三、v5 电线多的问题澄清

v5（detour+simplify）WIRE=6764 高于 v1（p0）=5031 是因为 **detour 模式 stub 引出段基数大**（纯 detour=12088），化简 -44% 后仍高于 p0。**与 v1 同基线的公平对比是 v7（p0+simplify）=3424（-32%）**。对比包已含 v7 供用户 Cadence 实测。

---

*二期追加完成（2026-08-12）。对比包现含 8 版本（v1-v8）。*
