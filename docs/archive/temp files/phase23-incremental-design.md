# Phase XXIII 增量开发设计 — 三项未开发任务（P1-3 / P1-4 / R-2）

> 文档：2026-08-14 ｜ 撰写：齐活林（主理人/架构师）｜ 状态：**待工程师实施**
> 基线：git `6468ebb`（Phase XXII 末 877 passed + Phase XXIII 文档 v2）
> 开发环境：**现有 cis2hdl 仓库**（plugin_ver 版不参与本轮，S0 后另行）

---

## 〇、任务总览

| # | 任务 | 来源清点 | 目标 |
|---|------|---------|------|
| T1 | GND 分布增强（P1-3） | §1.5 未开发清点 🟡 | 密度+避让+接入电路增强 |
| T2 | 电阻旋转感知（P1-4） | §1.5 未开发清点 🟡 | 电阻符号方向随连线 |
| T3 | violations=506 trunk 避让（R-2） | §1.5 未开发清点 🟡 | trunk 穿体收敛 |

**验收总纲**：全量测试 ≥877 不回归；默认（p0）转换行为等价（除目标改善项）；542/310/1158/off-grid/LASTPIN 语义不回归；交付对比包**新目录** output_phaseXXV_compare（递增约定）。

---

## T1 · GND 分布增强（P1-3）

### 现状（代码实锤）

- `gnd_cluster_planner.py`：`_cluster_hubs`（贪心最近邻聚簇，max_dist=500）+ `route_cluster_parallel` + `hub_short_wires` + `place_gnd_symbol`（csa_writer L2690 引用）
- Phase XXII 已并入 parallel_short（csa_writer L1957/1975/1986），GND 端并联已生效
- **缺失**（P1-3 原始诉求 B9、V2-1/2/7）：①GND 符号**密度**（页面上 GND 符号数量/位置是否够密，远处引脚是否绕远路）②GND trunk **避让**（GND 网 trunk 是否仍穿元件体）③GND **接入电路**（簇 hub 到 GND 符号路径是否清晰）

### 设计

**T1.1 GND 符号密度补点（新函数 `ensure_gnd_symbols`）**
- 位置：`gnd_cluster_planner.py`，csa_writer 布线前调用
- 逻辑：对每页 GND 网引脚做**区域划分**（按页面 1/4 分块），每块若存在 ≥3 个 GND 引脚且距最近 GND 符号 >1500，在该块中心（snap25）补一个 GND 符号（`GND_SYM_{block}`），走 `place_gnd_symbol` 既有路径
- 验收：GND 网每页 hub→最近符号曼哈顿距离均值**下降 ≥20%**（对比 output_phaseXXIV_compare）
- 开关：`gnd.distribute_density: bool = False`（默认关——**默认行为等价铁律**；用户 --gnd-distribute 或新 profile max-beauty 时开）

**T1.2 GND trunk 避让增强**
- 现状：GND 网 trunk 走 `_route_horizontal/_route_vertical` 普通逻辑，`_avoid_outlines` 只避让 trunk 线本身的 outline 交叉点
- 增强：GND 网（net_display 含 `\g` 后缀）route 时**提高 lane 避让权重**——`route_nets` 中 GND 网 trunk 选择时，对 body_outlines 的 edge_clearance 用 `_edge_clearance() + 50`（额外余量）
- 验收：`[WIRE_THROUGH_BODY] violations` 中 GND 网 trunk 穿体数**下降 ≥30%**
- 开关：并入 T1.1 的 `gnd.distribute_density`（同时控制）

**T1.3 GND 接入电路（hub→符号路径避让）**
- 现状：`route_cluster_parallel` 的 outlet 到 GND 符号的引出段可能穿元件
- 增强：outlet→符号 段生成后，调用 `WireLayoutEngine._stub_direct_blocked` 检查；受阻时绕行（沿 grid 折 90°，最多 2 次）
- 验收：GND hub outlet 引出段穿体 = 0（新报告口径可数）
- 开关：同 T1.1

**测试**：
- `tests/unit/test_gnd_distribute.py`（新）：密度补点触发/不触发、hub 距离均值下降、outlet 避让
- `tests/unit/test_gnd_parallel_short.py` 扩展：distribute 开时 GND 网行为

---

## T2 · 电阻旋转感知（P1-4）

### 现状（代码实锤）

- `ComponentInstanceIR.rotation: int = 0` / `mirror: int = 0`（ir/component.py L99/103）——EDIF 方向已捕获
- `coord_transform.py` L279-287：P2-1 已实现"per-instance rotation/mirror 旋转 symbol.css 引脚偏移"
- **缺失**：电阻/电容等二端元件的**符号绘制方向**未随连线方向旋转——`placeholder_lib.py` 生成 mock 符号时固定方向；`mock_icon_lib` 的 R 类图标固定

### 设计

**T2.1 电阻符号方向随连线（新函数 `apply_passive_orientation`）**
- 位置：`placeholder_lib.py` 或新增 `orientation_planner.py`；csa_writer 生成 mock 符号后、布线前调用
- 逻辑：对 prefix ∈ {R, L, FB, FERRI, BEAD} 的实例，取其两个引脚坐标（pin_coords 单源），若 Δx > Δy（水平连线）→ 符号按水平方向（rotation=0 或 180）；若 Δy > Δx（垂直）→ 旋转 90/270；符号 outline 尺寸随之 swap（宽↔高）
- 联动：`coord_transform` 的引脚偏移旋转链复用（rotation 字段已支持 R90/R180/R270）
- 验收：R 类符号宽高方向与两引脚连线主轴一致率 **≥80%**；310 引脚重叠仍 0
- 开关：`placement.rotate_passives: bool = False`（默认关——默认行为等价；用户显式开或 max-beauty profile）

**T2.2 符号尺寸自适应**
- 现状：mock R 符号尺寸固定（如 200×100）
- 增强：按旋转后方向输出对应尺寸的 outline（水平 200×100 / 垂直 100×200），C 短号/引脚名锚点随旋转
- 验收：旋转后 symbol.css outline 尺寸正确；文本不重叠（沿用 char_w28 避让）

**测试**：
- `tests/unit/test_passive_orientation.py`（新）：水平/垂直/45° 判定、尺寸 swap、310 仍 0
- `tests/unit/test_placeholder_lib.py` 扩展

---

## T3 · violations=506 trunk 避让（R-2）

### 现状（代码实锤）

- `[WIRE_THROUGH_BODY] detected=1022 exempt=516 violations=506`（v9_default）
- 506 构成：**trunk 穿体 >500 长段 283 条**（核心大头）+ 中短段；页面集中 P21=179/P22=78/P9=44
- `route_nets`：net 按"最长优先"排序，trunk 选 median 后 `_avoid_outlines` 推离 outline；但**只推离 trunk 线上与 outline 的交叉点**，跨多个元件体时仍穿中间元件
- `_avoid_outlines(trunk, body_outlines, vertical, edge_clearance)`：返回避开所有 outline 的 trunk 坐标

### 设计

**T3.1 trunk 避让增强（`_avoid_outlines` 提升）**
- 现状 `_avoid_outlines` 逻辑：对 trunk 坐标，检查是否与任一 outline 的 x/y 区间重叠且 y/x 区间含 trunk 坐标；重叠则向上/下（或左/右）移动到 outline 边缘 + clearance
- 增强：**分段避让**——trunk 保持单一 y/x 坐标不变（Cadence 语义），但避让算法从"推离首个重叠 outline"改为"推离所有重叠 outline 的最大扩展"（即选择使 trunk 不与任何 outline 重叠的坐标；若无可选坐标，选穿透最少的坐标并记录）
- 增强点：`route_nets` 中 net 排序后，对 trunk 避让增加 **outline 冲突计数优先**——多条候选 trunk 坐标中选冲突最少者（当前只选 median 后单向推离）
- 验收：violations **506 → ≤300**（trunk 穿体 283 → ≤150），且 WIRE 段数不增（trunk 坐标变化不产生新段）
- 开关：默认开（这是避让增强，不是新行为开关；但需验证 877 测试不回归——若既有测试断言 trunk 坐标，按 Q1 授权更新）

**T3.2 密集页降级豁免标记**
- 现状：密集页（P21/P22）无法找到完全避让 trunk 时回退直穿
- 增强：回退时在 report 记录 `reason=trunk_blocked`（沿用 Phase XXII reason 体系），violations 分项统计 trunk_blocked 数量，README 已知限制明确
- 验收：报告可区分"trunk_blocked（密集页不可避免）"与"可避让未避让"；可避让未避让 = 0

**测试**：
- `tests/unit/test_trunk_avoidance.py`（新）：单 outline 推离、多 outline 冲突计数、无解回退标记
- `tests/e2e/test_v9_compare_package.py` 扩展：violations 断言（≤300 或 trunk_blocked 分项）
- `tests/unit/test_wire_through_body_exempt.py` 扩展：reason=trunk_blocked

---

## 实施要求

1. **默认行为等价铁律**：T1/T2 新开关默认 false；T3 避让增强默认开但必须 877 测试全绿（若 trunk 坐标断言变化按 Q1 授权更新并说明）
2. 每项附防回归测试；全量 `python3 -m pytest tests/ -q` ≥877
3. 交付对比包**新目录 output_phaseXXV_compare**（make_compare_v9.py OUT 递增 + test_v9_compare_package.py 指向 + README/metrics_summary）
4. 提交 git（英文 message，注明三项）
5. 回传报告（≤400 字）：每项完成文件+关键变更+验收指标（hub 距离下降/violations 收敛/旋转一致率）+ 遗留

## 运行命令

```bash
export PY=/Users/echo/.workbuddy/binaries/python/envs/default/bin/python3
$PY -m pytest tests/ -q -p no:cacheprovider   # 全量
$PY -m pytest tests/unit/test_gnd_distribute.py tests/unit/test_passive_orientation.py tests/unit/test_trunk_avoidance.py -q -p no:cacheprovider
# 转换验证（对比包重建）
$PY scripts/make_compare_v9.py
```
