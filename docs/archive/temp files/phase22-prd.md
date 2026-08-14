# Phase XXII 增量 PRD — 视觉/布局优化完整实现（Phase XX 排期剩余任务）

> 撰写：许清楚（Xu）· 产品经理
> 输入：主理人现状调查结论（代码级，2026-08-14 实测）+ 本人只读复核（grep 实锤，见 §四）
> 基线：Phase XXI 末 840 passed / 6 skipped（pytest --collect-only 实测 846 collected，一致）
> 性质：**增量 PRD，仅描述本轮变更**（Phase XX 排期中尚未开发任务），不重写历史
> 语言：中文 ｜ 优先级：P0 必须 / P1 应该 / P2 可后置 ｜ 状态图例：✅ 已实现 / 🟡 待开发 / ⚪ 可选项

---

## 一、项目信息

| 项 | 值 |
|----|----|
| 项目名称 | `cis2hdl`（OrCAD Capture CIS .DSN/.EDF → Cadence DEHDL .CSA/.con/.xcon 转换器） |
| 技术栈 | Python 3.13（纯 Python CLI；GUI 为 PySide6，当前环境无 PySide6） |
| 原始需求复述 | 用户要求**完整实现 Phase XX 排期中尚未开发的任务**（视觉/布局优化），走标准 SOP。Phase XVIII-XIX-XX-XXI 已闭环 Cadence 16.6 报错类（A1-A8 + 542/545/310）；本轮聚焦**默认模式下的视觉/布线质量**：三段式 stub、避让、网络名悬空端、并联扩展、IO port 就近、xcon 合并、标签方向、LASTPIN miss 修复。 |
| 成功标准 | 全量测试 ≥ 840 passed；P0-1/P0-2/P0-3/P1-5 默认模式（p0）生效且回归为零；P2-3 xcon 单一实现；P1-7 aes 模式 LASTPIN miss 归零（或证据化豁免）；重新转换输出目录供用户 Cadence 16.6 复测。 |

---

## 二、产品定义

### 2.1 产品目标（3 条正交）

| # | 目标 | 可量化指标 |
|---|------|-----------|
| G1 | **默认模式视觉达标**：p0 模式启用三段式 stub 与避让，消除线头/重合线/穿元件 | p0 模式 WIRE 段数变化可统计；`[WIRE_THROUGH_BODY]` 降为 0 或显著下降；无原地掉头线头 |
| G2 | **电气可读性补齐**：跨页网悬空端补网络名、同信号相近引脚并联短接、IO port 按网络就近 | use_net_name 时悬空端补 SIG_NAME 数量可统计；同信号并联簇 hub 短接段数量可统计；IO port 聚类命中率可统计 |
| G3 | **代码债收敛**：两套 xcon 生成器合并为一；标签方向随元件；aes 模式 LASTPIN miss 修复 | `_build_xcon_content` 全仓仅 1 处定义；text_layout 开启后标签方向与元件方向一致；aes 报告 `[LASTPIN_MISS] total=0` |

### 2.2 用户故事（含验收标准）

| # | 角色 | 故事 | 验收标准（可量化） |
|---|------|------|-------------------|
| US1 | 硬件工程师 | 默认转换（不加 --aesthetic）就能看到无"原地掉头线头"、无重合线的原理图 | p0 模式 WIRE 段数与 detour 同网对比：三段式 stub 引入后单网段数 ≤ 旧段数 + 每引脚 2（延伸+折线），无 self-overlap 段（wire_simplifier self_intersect 检测 0） |
| US2 | 硬件工程师 | 电线不再穿过元件体（默认模式） | `aesthetic_report [WIRE_THROUGH_BODY] total=0`（p0 模式）；stub 直线段命中 outline 数 = 0 |
| US3 | 硬件工程师 | use_net_name 时跨页网电线悬空端能看到网络名标签 | `net_name_endpoints` 接入后：跨页网悬空端 SIG_NAME 数量 = 悬空端总数（≥1/网）；既有 `cross_page_bare_names + net_name_labels` 行为不回归 |
| US4 | 硬件工程师 | 同信号相近引脚（电阻/电容并联）先在引脚附近并联再统一引出 | 非 GND 信号中间距 ≤500 的同信号引脚簇被 hub 短接；每簇 WIRE 段数 = 簇内引脚数（hub 短接）+ 1（引出） |
| US5 | 硬件工程师 | IO port 沿边缘分布且"按网络就近"聚类 | edge_layout 开启时：同网 IOPORT 与页内该网引脚平均距离较等距基线下降（可统计均值）；无 IOPORT 重叠 |
| US6 | 实施工程师 | 不用维护两套 xcon 生成逻辑 | `_build_xcon_content` 全仓 grep 仅 1 处定义（output_manager 或 xcon_writer 二选一）；conversion_engine 走单一入口；既有 .xcon 输出字节级不变（回归测试通过） |
| US7 | 硬件工程师 | 元件标签文字方向随元件方向（水平/旋转） | text_layout 开启后：旋转元件（R 行非 0）的标签 orient 与元件一致；原 0 碰撞回归不劣化 |
| US8 | 硬件工程师 | aes 模式无 LASTPIN 坐标 miss | `aesthetic_report [LASTPIN_MISS] total=0`（aes 模式）；或对 7 处边缘 miss 出证据化豁免说明（resolve 位移 ±25 网格对齐后不 miss） |

---

## 三、需求池（按 Phase XX 排期编号 + 状态）

> 编号沿用 Phase XX 排期；✅ = 已完成（本轮不开发），🟡 = 待开发（本轮范围），⚪ = 可选项/待确认。

### P0 批次

| 编号 | 需求 | 现状（代码证据） | 状态 | 本轮处理 |
|------|------|------------------|:---:|---------|
| P0-1 | 三段式 stub 默认开（消除线头/重合线） | `routing.three_stage_stub: true` 已配置；`_three_stage_stub` 仅在 detour_router（mode=detour）生效；**wire_layout.py（p0 模式）无三段式**（route_horizontal/vertical 直 stub + DetourRouter stub lead-out） | 🟡 | **开发**：p0 模式启用三段式 stub（或复用 detour 的 stub 引出逻辑） |
| P0-2 | 避让默认开（电线不穿元件） | `detour_stubs: true`（mode=detour 生效）；p0 模式 trunk 已避让 outline（`_avoid_outlines`，Phase XIII T4），但 stub 直线段穿元件体（wire_layout.wires_through_bodies 报告） | 🟡 | **开发**：p0 模式 stub 绕障（复用 detour jog/避让能力或引入 stub 级 outline 检测） |
| P0-3 | net_name_endpoints 接线到 csa_writer | `net_name_connect.py:122 net_name_endpoints()` 已实现；**csa_writer.py:2106 只 import cross_page_bare_names/net_name_labels，未调用 net_name_endpoints** | 🟡 | **开发**：csa_writer use_net_name 分支接入 net_name_endpoints，悬空端补 SIG_NAME |
| P0-4 | J/T/S 匹配修复 | mock_all 已接管（Phase XX） | ✅ | 不纳入 |
| P0-5 | resolve_passives 默认开 | `overlap.resolve: true` 已接线（Phase XX P0-7 + Phase XXI bug 修复） | ✅ | 不纳入 |
| P0-6 | mock_all | 已完成（Phase XX） | ✅ | 不纳入 |
| P0-4+ | AMS1117 匹配质量增强 | pstchip 恢复引脚名（GND/OUTPUT/TAP/INPUT）✅；**hdl_lib 真实符号仍缺**（当前 mock 图标，非真实 AMS1117 符号） | ⚪ 部分 | 可选（低价值/高成本：需真实 SOT223 符号资源） |

### P1 批次

| 编号 | 需求 | 现状（代码证据） | 状态 | 本轮处理 |
|------|------|------------------|:---:|---------|
| P1-1 | 引脚标签布局 | C 短号框内 + X 长名框外 + justify 修正（Phase XX 补丁 3/4） | ✅ | 不纳入 |
| P1-2 | IO port 就近放置（按网络聚类） | `ioport.edge_layout` 已有（沿右缘等间距，csa_writer._ioport_position_cfg）；**"按网络聚类就近放置"未实现** | 🟡 | **开发**：edge_layout 之上加"同网 IOPORT 与页内引脚聚类"就近放置（保电气坐标同源） |
| P1-3 | GND 分布增强 | gnd_distribute + cluster_radius 已有（Phase XVII R3 基础版）；密度增强待评估 | ⚪ 增强 | 可选：仅当 P1-2 聚类方案落地后顺带评估（避免并行改动 GND 布局） |
| P1-4 | 电阻/LB 旋转感知 | `_is_passive_view_body` + sym_2 横向视图切换（Phase XVIII R3 Q2）；"方向随连线"未完整 | ⚪ 增强 | 可选：与 P2-4 标签方向联动评估 |
| P1-5 | 并联扩展到所有信号 | `wire_simplifier.parallel_short_wires`（L368）**已有实现但无调用方**（grep 仅定义处）；现仅 GND 簇经 gnd_cluster_planner.route_cluster_parallel 使用；`wire_simplify.enabled=false` 默认关 | 🟡 | **开发**：默认开启/接线 —— 路由前对同信号引脚调用 parallel_short_wires（受 `wire_simplify.parallel_short: true` 配置），并入网后统一引出 |
| P1-6 | wire simplify 阈值调优 | break_long/max_wire_len 已实现（Phase XVIII R8） | ✅ | 不纳入（阈值默认 5000 保持） |
| P1-7 | 剩余 LASTPIN miss（aes 边缘 7 处） | default 模式 0；aes 模式边缘 7 处（C228/C263 等 resolve 位移 ±25）；aesthetic_report 记录 [LASTPIN_MISS] | 🟡 | **开发/核查**：定位 7 处（C228.2/C263.2/C355.1/C356.1/C358.2/T30.1 等），resolve 位移后网格对齐或豁免证据化 |

### P2 批次

| 编号 | 需求 | 现状（代码证据） | 状态 | 本轮处理 |
|------|------|------------------|:---:|---------|
| P2-1 | 542/545 提示抑制 | mock 9P 属性声明（Phase XXI A 根治） | ✅ | 不纳入 |
| P2-2 | origin 库结构补全 | write_origin_lib 自包含库已做（output_manager.py:1013，Phase XIX）；entity/part_table 补全待确认 | ⚪ 待确认 | 转文档指引：若用户复测无 ORIGIN 相关报错则无需开发；否则补 entity/part_table 声明 |
| P2-3 | 两套 xcon 生成器合并 | **output_manager._build_xcon_content（L592）+ xcon_writer._build_xcon_content（L109）两套并存**（C5 代码债）；conversion_engine 走 XconWriter.write_with_manager 但 output_manager 保留自建兜底 | 🟡 | **开发**：合并重构 —— 单一实现（推荐保留 XconWriter 为唯一内容源，output_manager 仅负责写文件），输出字节级不变 |
| P2-4 | 标签文字方向随元件 | text_layout enabled=false 默认关（config.py:358）；方向统一未开发 | 🟡 | **开发**：text_layout 增加"标签方向随元件 R 行旋转"逻辑（默认关可回退，--text-layout 开启） |
| P2-5 | GUI 面板（mock_all 复选框+手动匹配） | **无 PySide6 环境**（历史降级占位）；chip_config_panel 已有雏形（PySide6 延迟导入守卫） | ⚪ 依赖环境 | 本轮不开发：标注环境依赖风险，提供 chip_config.yaml 等价 CLI 路径 |
| P2-6 | MOCK 属性文本标签 | PAINT PINK + DISPLAY 1.5（Phase XXI B） | ✅ | 不纳入 |

---

## 四、本轮开发范围清单（只列待开发项）

> 依据：本人只读复核（grep 实锤）+ 主理人调查。**不修改源码**，仅 PRD。

| # | 任务 | 代码锚点 | 验收口径 |
|---|------|---------|---------|
| D1 | **P0-1 p0 模式三段式 stub 启用** | `wire_layout.py`（route_horizontal/route_vertical）→ 引入延伸→折线→调头；`config.routing.three_stage_stub` | p0 模式同网 WIRE 段数对比 detour 模式 ≤ 旧段数 + 2×引脚数；self-overlap 0 |
| D2 | **P0-2 p0 模式 stub 避障** | `wire_layout._route_*` stub 段 + outline 命中检测（复用 wires_through_bodies）→ 命中则 jog 绕障 | `[WIRE_THROUGH_BODY] total=0`（p0 默认） |
| D3 | **P0-3 net_name_endpoints 接线** | `csa_writer.py:2104` use_net_name 分支追加 `net_name_endpoints(...)`；入 `_extra_sig_names` | 跨页网悬空端均补 SIG_NAME；test_net_name_endpoint.py 扩展 |
| D4 | **P1-5 并联扩展到所有信号** | `csa_writer` 路由前对非 GND 同信号引脚调 `wire_simplifier.parallel_short_wires`（受 wire_simplify.parallel_short=true） | 并联簇 hub 短接段并入网；坐标唯一原则（端点=引脚坐标）保持 |
| D5 | **P1-2 IO port 按网络聚类就近** | `csa_writer._ioport_position_cfg` / `_page_ioports` 增加聚类排序（同网 IOPORT 就近页内引脚） | edge_layout 开启时同网 IOPORT 与引脚距离均值下降；无重叠 |
| D6 | **P2-3 xcon 合并重构** | `output_manager._build_xcon_content` + `xcon_writer._build_xcon_content` 二选一 | 全仓 `_build_xcon_content` 仅 1 处定义；既有 .xcon 字节级不变 |
| D7 | **P2-4 标签方向随元件** | `text_layout.py`（optimize/collect）增加方向属性随 R 行旋转 | --text-layout 开启后标签 orient 与元件一致；原 0 碰撞不劣化 |
| D8 | **P1-7 aes LASTPIN miss 修复/豁免** | `aesthetic_report.lastpin_misses` 7 处（C228.2/C263.2/C355.1/C356.1/C358.2/T30.1 等） | aes 报告 `[LASTPIN_MISS] total=0` 或豁免证据（resolve 位移后 25 网格对齐） |

### 不纳入项及原因

| 项 | 原因 |
|----|------|
| P0-4 / P0-5 / P0-6 / P1-1 / P1-6 / P2-1 / P2-6 | **已完成**（Phase XX/XXI 交付，✅ 见 §三） |
| P2-5 GUI 面板 | **依赖环境**：无 PySide6，历史降级占位；等价能力走 chip_config.yaml CLI |
| P2-2 origin 库补全 | **待确认**：write_origin_lib 已自包含；entity/part_table 仅在用户复测仍报 ORIGIN 时才需开发，本轮转文档指引 |
| P0-4+ AMS1117 真实符号 | **低价值/高成本**：需真实 SOT223 符号资源；现 mock 图标 + pstchip 真实引脚名已可读 |
| P1-3 GND 分布增强 | **低优先级**：基础版已交付；增强与 D5 聚类方案重叠，避免并行改动 |
| P1-4 电阻/LB 旋转感知 | **低优先级**：基础版已交付；与 D7 标签方向联动评估，不单独开发 |

---

## 五、待确认问题（需主理人/实施/QA 拍板）

1. **P0-1 stub 默认开对现有 WIRE 基线的影响**：p0 默认模式引入三段式后，WIRE 段数/坐标变化会改变既有 golden 断言（如 wire_layout 单测）。是否允许更新基线断言（功能性等价、仅几何形态变化）？还是要求段数不变仅消除线头？
2. **P0-2 避让默认开的作用域**：是否**只针对 p0 模式**启用 stub 绕障（detour 已有效果）？还是统一两模式共用同一避让实现（推荐）？
3. **P0-3 net_name_endpoints 与现有 net_name_labels 的关系**：两者都在 use_net_name 分支补 SIG_NAME，是否合并为单一调用点（net_name_endpoints 为主，net_name_labels 仅做非跨页补全）？
4. **P1-5 并联默认开的范围**：`wire_simplify.parallel_short: true` 已配置但 `wire_simplify.enabled=false`。是**仅接线 parallel_short_wires**（不开 wire_simplify 整体化简），还是顺带开启 enabled？—— 建议仅接线并联，wire_simplify 整体保持默认关（回退安全）。
5. **P1-7 的修复策略**：7 处 LASTPIN miss 是 resolve_passives 位移 ±25 导致的网格偏移。是（a）位移后 snap 到 25 网格使 LASTPIN 命中（推荐），还是（b）豁免记录为已知偏差？（用户侧影响：miss 引脚无 $PN 属性 → Cadence 删 SIG_NAME，建议按 (a) 修复）
6. **P2-3 xcon 合并保留哪个实现**：推荐保留 `xcon_writer._build_xcon_content`（带 conn 全量数据）为唯一内容源，`output_manager` 仅负责写文件；若历史兼容风险大，可反向（保留 output_manager，xcon_writer 委托）。需 QA 对 .xcon 字节级回归把关。
7. **P2-4 标签方向默认开还是默认关**：现状 text_layout enabled=false。用户 Phase XXI 曾要求"标签方向随元件"（B6），建议本轮**默认关 + --text-layout 可开**，先出 A/B 对比再决定默认值。
8. **测试基线口径**：全量测试是否保持 ≥840 passed？新增 D1-D8 用例建议 ≥15 条（每任务 1-2 条防回归）。

---

## 六、交付物与流程约束

1. **PRD 文档**：本文件（`docs/archive/temp files/phase22-prd.md`），不修改 docs/ 根目录核心文档。
2. **后续 SOP**：本 PRD → 架构师 system design → 实施 → QA（全量测试 ≥840 + 防回归用例）→ 重新转换输出对比目录 → 用户 Cadence 16.6 复测。
3. **风险提示**：P0-1/P0-2 改动 wire_layout（默认路由路径），回归风险最高 —— 需 wire_layout 单测 + e2e 转换双保险；P2-3 合并属纯重构，字节级回归把关。
