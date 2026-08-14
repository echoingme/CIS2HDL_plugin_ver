# Phase XVII 调研：A* 迷宫布线开源方案深度调查（2026-08-12 追加）

> 调研人：研究员（researcher）+ 主理人齐活林汇总
> 目的：用户要求深度调查"A* 相关美化布线开源代码方案"，寻找可辅助实现
> 连接点合并、走线化简、电线避让、GND 聚类的现成函数/算法。
> 方法：curl 抓取并核实实际源码（非 README/DeepWiki 转述）——SKiDL route.py(3236行)/place.py(2094行)、
> OpenRAM compiler/router/*（BSD-3）、KiCad eeschema/tools/sch_line_wire_bus_tool.cpp(1505行)+sch_rtree.h。
> 所有函数名/行号均已对源码核实。本文件为临时调研文档，正式内容追加至 docs/RESEARCH.md。

---

## 一、调研总览表

| 方案 | 仓库URL | 关键文件 | 关键函数 | 许可 | 代码量 |
|---|---|---|---|---|---|
| **SKiDL** | github.com/devbisme/skidl | `src/skidl/schematics/route.py`、`place.py` | `Router.route/global_router/cleanup_wires/add_junctions`、`Placer.place/evolve_placement` | **MIT**（可直接参考/移植） | route.py 3236 行，place.py 2094 行 |
| **OpenRAM** | github.com/VLSIDA/OpenRAM | `compiler/router/{router,graph,graph_node,supply_router,router_tech}.py` | `graph.create_graph/find_shortest_path`、`graph_node.get_edge_cost`、`router.find_blockages/inflate_shape/prepare_path` | **BSD-3-Clause** | router 全套约 1400 行 |
| **FGR/FastGR** | FGR 1.1 学术二进制无公开源码；开源替代 **tscircuit/capacity-autorouter** | `lib/solvers/{CapacityMeshSolver,MultiAstarIntraNodeSolver,NetToPointPairsSolver}.ts`、`lib/autorouter-pipelines/*` | `AutoroutingPipelineSolver.step/solve` | MIT（tscircuit） | TS 全工程，solvers 约 30+ 类 |
| **KiCad Eeschema** | gitlab.com/kicad/code/kicad | `eeschema/tools/sch_line_wire_bus_tool.cpp`、`eeschema/bus-wire-junction.cpp`、`eeschema/sch_rtree.h`、`eeschema/junction_helpers.cpp` | `simplifyWireList/TrimOverLappingWires/AddJunctionsIfNeeded/BreakSegmentsOnJunctions`、`SCH_EDIT_FRAME::SchematicCleanUp`、`EE_RTREE::Overlapping` | **GPL-3.0**（只能抄算法不能抄代码） | 1505 行/工具文件 |
| **gEDA/gschem** | github.com/geda-project/geda-gaf | 无自动布线（仅有手动 wire 工具） | — | GPL-2 | — |
| **Channel Routing（学术）** | cs.baylor.edu/~maurer/routing.pdf | trunk/branch 概念、垂直约束图、left-edge 算法 | — | 公开教程 | — |
| **Python 几何/图库** | pypi.org | shapely / networkx / rectpack / scikit-learn | `LineString.intersects`、`networkx.shortest_path`、`KMeans` | BSD-3 / BSD-3 / MIT / BSD-3 | — |

---

## 二、各方案深度细节（函数级，已核实）

### 2.1 SKiDL（最贴合"原理图自动布线"，MIT，可直接借鉴甚至移植思路）

`Router.route()`(route.py L3109) 完整流水线：
1. `add_routing_points`(L2015)：引脚沿方向延伸到元件 bbox 边缘形成 stub
2. `create_routing_tracks`(L2059)：把每个 part 的 lbl_bbox 边坐标去重后生成非均匀 H/V GlobalTrack（= switchbox 网格）
3. `create_terminals`(L2138)
4. `global_router`(L2190)：Dijkstra 式迷宫，代价=`dist_from_start + adj.dist`，`face.capacity<=0` 即障碍；`rank_net`(L2314) 按"bbox 周长+引脚数"排序先布短网
5. `create_switchboxes`(L2362)
6. `switchbox_router`(L2412)：Greedy Switchbox Router，列优先+TARGET 引导（1985 论文）
7. **`cleanup_wires`(L2441) 走线美化后处理**（★本项目最高价值参考）
8. `add_junctions`(L3054)：T/X 交点生成 junction 点（DOT）

**`cleanup_wires` 是对本项目"连接点过多/每线单画/电线爆炸"的现成解法**，内部 7 个子函数：

| 子函数 | 行号 | 功能 | 对标本项目需求 |
|--------|------|------|--------------|
| `split_segments` | L2462 | 线段按"与其他段交点+引脚点"切成最小区间 | 连接点切分 |
| `merge_segments` | L2516 | **共线重叠合并**：同一 Y 水平段/同一 X 垂直段按起点排序后 merge 重叠区间 | ★ 电线数量爆炸的直接削减手段 |
| `break_cycles` | L2568 | 邻接图遍历断环（移除形成环的段） | 走线化简 |
| `trim_stubs` | L2621 | 从引脚段做图搜索，删除连不到任何引脚的悬空 stub | ★ stub removal（用户"凸出又折回"修复） |
| `remove_jogs` | L2816 | 检测 3 段"阶梯/礼帽 jog"替换为 2 段直角，`obstructed()`(L2827) 检查新段是否撞元件 bbox 或撞其他网平行段（`segment_bbox.resize(Vector(2,2))` 保证边-边检测） | ★ 拐角化简 + 避让检测 |

place.py 力导向布局：`net_force_dist`(L659 网吸引) + `overlap_force`(L741 bbox 重叠排斥) + `evolve_placement`(L1118) 的 **alpha 调度表**(L1033：`(0.5,α=0)全吸引 → (0.25,0.4) → (0.25,0.8) → (0.25,1.0)全排斥`渐进避免振荡) + `snap_to_grid`(L102 snap 到 GRID)。

### 2.2 OpenRAM（A* 代价函数与 Hanan 网格模板，BSD-3）

- `graph.create_graph`(graph.py L187)：**Hanan 网格**——不在均匀网格上找路，而是在"源/目标 bbox + 障碍物角点 + 引脚安全点 + via 中心"的笛卡尔坐标处生成节点（`generate_cartesian_values` L277），相邻正交节点用 `is_probe_blocked`(L74) 探测连接；障碍物先 `inflate_shape`(router.py L217) 按 spacing 膨胀，`is_node_blocked`(graph.py L100) 标记阻塞节点。节点量远小于均匀网格。
- `graph.find_shortest_path`(L392)：标准 A*（heapq 优先队列 + close_set + came_from 回溯），`h(node)=min(到各 target 的欧氏距离+层差)`；多源多目标支持。
- **`graph_node.get_edge_cost`(graph_node.py L60)：代价公式 = 线长；非首选方向层移动 ×4；拐角（方向改变）加 `drc["grid"]` 防 dog-leg；换层 via ×2。** ← 本项目若做 A* 可直接抄的代价函数模板
- `router.prepare_path`(L254)：**去除同向冗余点**（路径化简 = OpenRAM 版"共线合并"）
- `supply_router.py add_side_pin`(L100)：电源环四周均匀生成 fake pins 就近接入——**GND 聚类的现成思路**（"环 + 均匀取点"）

### 2.3 FGR / FastGlobalRouter 及开源替代

FGR 1.1（Markov, ISPD'07 冠军）**无公开源码**（学术二进制，可从论文/讲义获得算法）；其思想：A* + 历史拥塞迭代（negotiated congestion，NCR 式）、多引脚网 Steiner/MST 分解、ε-sharing（共享边给极小正成本避免 A* 下界退化）。FastGR（DATE2022 论文）CPU-GPU 加速版，仍无源码。
**开源可运行的替代是 tscircuit/capacity-autorouter（MIT, TypeScript）**：`AutoroutingPipelineSolver` 全流水线，solvers 含 `CapacityMeshSolver`（容量网格=拥塞代价）、`MultiAstarIntraNodeSolver`（A*）、`NetToPointPairsSolver`（多引脚网→点对分解）、`CrossingViaReductionSolver`（交叉减少）。TS 代码质量高可读，但面向 PCB（多层/过孔/差分对），对原理图场景仅算法参考，不建议直接移植。

### 2.4 KiCad Eeschema（GPL，抄算法不抄代码）

KiCad 原理图**无自动布线**（wire 工具仅正交手动绘制），但有成熟的**画后清理/连接管理**算法，与本项目"化简"需求直接相关：
- `simplifyWireList`(L1208)：用 `SCH_LINE::MergeOverlap` 合并同向重叠线（画线回溯时去重）
- `TrimOverLappingWires`(L1349)（L 形修剪重叠段）
- `AddJunctionsIfNeeded`(L1393)、`BreakSegmentsOnJunctions`(L1455)、`SCH_EDIT_FRAME::SchematicCleanUp`（bus-wire-junction.cpp：删冗余 junction、合并重叠线、断 T 点）
- `EE_RTREE`(sch_rtree.h)：**R-tree 空间索引**，`Overlapping(rect)` 毫秒级找重叠/邻近项——重叠检测的现成数据结构思路
- 局限性：GPL-3.0 只能抄思路；Eeschema 无稳定 Python API（pcbnew 才支持脚本），**KiCad python scripting 不能直接用于验证 CSA 输出**，验证仍需 Cadence 实测。

### 2.5 学术：Channel Routing（本项目 trunk+stub 的理论原型）

Maurer 教程定义标准 channel routing：矩形布线区上/下端子，**trunk=一个水平段连最左/最右端子，branch=垂直接引脚**，垂直约束图（同列两个网→约束边）+ **left-edge 算法**逐 track 分配（取无前驱且最左的网）。
结论：**本项目的 `_find_lane` 车道法 + trunk/stub 本质就是一个 channel router**；参考工程 04p4 的"短段分层"风格就是 left-edge 分配天然产物。学术上的 NP 完全性说明：追求"最少轨道数"不现实，启发式足够。

---

## 三、与本项目结合度评估表

| 方案 | 贴合度 | 可借鉴的具体函数/算法 | 实现量估计 |
|---|---|---|---|
| **SKiDL cleanup_wires** | **高** | `merge_segments`(共线合并)、`trim_stubs`(stub删除)、`remove_jogs`(拐角化简)、`break_cycles`(断环)、`add_junctions`(T/X点) | 300-500 行（直接移植思路，MIT） |
| SKiDL global_router | 中 | `create_routing_tracks`(bbox边→轨道=非均匀网格)、`rank_net`(短网先布)、`face.capacity`(拥塞) | 400-600 行（远期，A* 时用） |
| OpenRAM graph.py | 中 | `get_edge_cost`(线长+拐角×grid+方向×4)、Hanan 网格、`is_probe_blocked`(避让探测)、`prepare_path`(路径化简) | A* 骨架 500-800 行（BSD 可抄） |
| OpenRAM supply_router | 中 | `add_side_pin`(环+fake pins 均匀分布，GND 就近共用) | 100-150 行 |
| KiCad Eeschema | 中 | `SchematicCleanUp`、`MergeOverlap`、`EE_RTREE.Overlapping`(重叠检测) | 200-300 行（GPL 只抄思路） |
| tscircuit | 低-中 | `MultiAstarIntraNodeSolver`、`NetToPointPairsSolver`(多引脚分解) | 参考为主 |
| **shapely/networkx** | 高（工具） | `LineString.intersects/crosses`(避让/重叠检测)、`Polygon`(元件体)、`networkx`(图论) | 零开发（直接 pip 依赖） |
| **sklearn KMeans / 手写最近邻** | 高（工具） | GND 引脚聚类→按簇共用 trunk | 100 行内 |

---

## 四、明确推荐（对应 4 个核心问题）

### 推荐 1：连接点合并 + 电线化简 → 移植 SKiDL `cleanup_wires` 四件套（最高优先）
对本项目"连接点过多、每线单画、电线数量爆炸"的**现成解法**，MIT 许可可直接照抄算法：
- `merge_segments`：同 Y 水平段 / 同 X 垂直段排序后合并重叠区间 → **直接削减段数**
- `trim_stubs`：从引脚段做连通图搜索，删除连不到引脚的悬空段
- `remove_jogs`：3 段阶梯/礼帽 jog 替换为 2 段直角（拐角化简）
- `break_cycles`：邻接图断环

实现为 wire_layout.py 后处理阶段（P0 之后），**只合并同网段、端点引脚坐标不动**（满足 DEHDL 几何重合硬约束）。建议做成独立模块 + 配置开关（如 `routing.simplify=true`），与现有 P0 输出可回退并存。

### 推荐 2：多端点网共用 trunk/总线合并
- 本项目 `_find_lane` 车道法已是 trunk 思想，理论原型即 Channel Router 的 trunk/branch
- 增强参考：SKiDL `create_routing_tracks`（元件 bbox 边延伸成轨道，多网可共享轨道） + left-edge 逐 track 分配
- **低成本替代**：对每网按引脚坐标排序取中位 trunk，让"段合并"升级为"多网共享同轨道不重叠区间"——可并入 P0 车道法，不必上 switchbox

### 推荐 3：电线避让元件 / 自重叠
现成实现二选一：
- **(a) OpenRAM 网格占用法**（BSD 可抄）：`inflate_shape`(障碍物膨胀) + `is_node_blocked`(格点阻塞) + `is_probe_blocked`(正交探测避让)
- **(b) shapely 法**（推荐，零新增算法）：`LineString.intersects(Polygon)` 检测 stub/trunk 穿元件体 + SKiDL `obstructed`(L2827) 的平行段重叠检测（`bbox.resize(Vector(2,2))` 处理边-边）

本项目已有 `_avoid_outlines`/`_pin_on_trunk`，用 shapely 增强即可，不必引入完整 A*。

### 推荐 4：GND 合并 / 就近共用
- OpenRAM `supply_router.add_side_pin` 思路：在页面/区域四周生成"电源环"+均匀 fake pins，GND 引脚就近接入最近环点
- sklearn `KMeans`（或手写最近邻，引脚数少时 O(n²) 足够）对 GND 引脚聚类，每簇取一个 trunk/共用段
- 实现量约 100 行，与现有 `\g` 全局信号机制兼容

### 总体建议（防止过度设计）
不要全量 A*（对固定布局是过度设计，与 P0 车道法重复）；**最高价值 = 移植 SKiDL cleanup_wires 做"连接点合并+共线化简+stub 修剪"后处理**（量小、MIT、直接解决电线爆炸）；避让用 shapely 增强；GND 聚类用 KMeans+OpenRAM 环思路。若未来做自动布局（--aesthetic 力导重排后原折线失效），A* 迷宫再按 OpenRAM `get_edge_cost` 公式（线长+拐角+drc["grid"]）实现。

---

## 五、参考链接清单

1. SKiDL：github.com/devbisme/skidl（route.py / place.py，MIT）；API 文档 devbisme.github.io/skidl/api/html/rst_output/skidl.schematics.route.html
2. OpenRAM：github.com/VLSIDA/OpenRAM（compiler/router/*，BSD-3-Clause）；DeepWiki deepwiki.com/ferdous313/OpenRAM_2017/4.1-a*-maze-router
3. tscircuit capacity-autorouter：github.com/tscircuit/capacity-autorouter（MIT）
4. KiCad：gitlab.com/kicad/code/kicad（eeschema/tools/sch_line_wire_bus_tool.cpp；eeschema/sch_rtree.h；eeschema/bus-wire-junction.cpp）；doxygen docs.kicad.org/doxygen/classEE__RTREE.html
5. Channel Routing 学术教程（trunk/branch/left-edge）：cs.baylor.edu/~maurer/routing.pdf
6. FastGR 论文：cse.cuhk.edu.hk/~byu/papers/C138-DATE2022-FastGR.pdf；FGR 1.1 描述：IEEE TCAD 2008 "High-Performance Routing at the Nanometer Scale"
7. Python 库：pypi.org/project/shapely（BSD-3，几何求交）、networkx（BSD-3，图/路径）、rectpack（MIT，矩形装箱）、scikit-learn（KMeans 聚类）
8. 多聚类网模型 MCN（引脚 k-means 分解，多引脚网拆子网）：academia.edu/56133640/Multi_Clustering_Net_Model_for_Placement_Algorithms
9. Greedy Switchbox Router 论文（SKiDL switchbox_router 依据）：doi.org/10.1016/0167-9260(85)90029-X

---

*调研完成（2026-08-12，软件团队）。所有源码经 curl 抓取核实，函数名/行号可信。*

---

# 追加（2026-08-12 第二轮）：SKiDL 完整流水线深度解剖 —— 从"摆放元件"到"绘制走线"

> 本轮深入 SKiDL `place.py`(2094 行) + `route.py`(3236 行) 实际源码（curl 抓取 raw.githubusercontent.com 核实），
> 完整梳理"元件摆放 → 走线绘制"全链路，逐函数标注算法细节，并探讨对本项目（CIS2HDL 固定布局 + 生成连线）的可借鉴点。
> 结论先行：**SKiDL 的"摆位 bbox 预留布线通道"与"cleanup_wires 后处理"两大思想最值得借鉴**；力导布局仅适用于重排场景。

## A. place.py 完整流水线（元件摆放阶段）

### A.1 `Placer.place(node, tool, **options)` 主入口（place.py L1293）

```
place() 主流程（递归式，先子后父）：
  1. 递归 place 子节点（child.place）
  2. group_parts()：按内部网把元件分组
       → connected_parts（有网连接的组列表）
       → internal_nets（组内连接网）
       → floating_parts（悬浮件：无任何连接）
  3. _auto_stub_cross_group()：跨组的长链网自动打 stub 断链
  4. _auto_stub_large_groups()：超大组按链式网拆分（防力导 O(n²) 爆炸）
  5. 对每个 connected 组 → place_connected_parts(组)   ← 核心摆放
  6. place_floating_parts(悬浮件)                     ← 浮件摆放
  7. place_blocks(所有块 + 子节点)                    ← 块级排列（similarity force）
  8. snap_to_grid + calc_bbox
```

**对本项目的借鉴**：
- 我们**不做全局重排**（CIS 原布局是工程师手绘，保持坐标），但 `floating_parts` 思想可借鉴——**未匹配芯片/connector 放模拟图标时，把它们当作"可移动块"**，周围元件是"固定件"。
- `_auto_stub_large_groups`（链式网拆分防 O(n²)）与本项目 GND 大网拆分思想一致（`\g@refdes` 分组）。

### A.2 `add_placement_bboxes`（place.py L123）—— ★★ 最值得借鉴的"预留布线通道"思想

```python
def add_placement_bboxes(parts, **options):
    for part in parts:
        part.place_bbox = BBox(); part.place_bbox.add(part.lbl_bbox)
        padding = {"U": 1, "D": 1, "L": 1, "R": 1}   # 每侧最小 1 个通道
        for pin in part:
            if pin.stub is False and pin.is_connected():
                padding[pin.orientation] += 1          # 每侧引脚数 → 通道数
        expansion_factor = options.get("expansion_factor", 1.0)  # 布线失败可放大
        # 右侧/上侧 + 通道*GRID，左侧/下侧 - 通道*GRID
        part.place_bbox.add(part.place_bbox.max + (Point(padding["L"], padding["D"]) * GRID * expansion_factor))
        part.place_bbox.add(part.place_bbox.min - (Point(padding["R"], padding["U"]) * GRID * expansion_factor))
```

**核心思想**：每个元件的"摆放包围盒"= 符号 bbox + 四侧按引脚数扩展的布线通道（每引脚 1 通道 × GRID）。元件之间靠通道间距自然隔开，后续布线不穿越。

**对本项目的借鉴（★ 高价值）**：
- 本项目 `overlap_detector` 只做**符号矩形 vs 符号矩形**检测；若引入"**摆放 bbox**"（符号 bbox + 引脚侧通道），可自动解决用户问题 8（"重叠检测扩大化、避让引脚"）——检测用 place_bbox，实际渲染用符号 bbox。
- `expansion_factor`（布线失败后整体放大）正是"挤压→腾挪"（M3 placement_fitter）的现成模式：检测到挤压 → 对区域 expansion_factor 放大重放。
- GND 放置（用户问题 7 "GND 放芯片上"）可直接用 place_bbox 判空位：GND 的 place_bbox 与芯片 place_bbox 不交即不压引脚。

### A.3 `add_anchor_pull_pins`（place.py L164）—— 力导的"引脚级吸引力"来源

```python
def add_place_pt(part, pin):
    pin.route_pt = pin.pt; pin.place_pt = Point(pin.pt.x, pin.pt.y)
    # 引脚沿方向投影到摆放包围盒边缘（U→min.y / D→max.y / L→max.x / R→min.x）
    if pin.orientation == "U": pin.place_pt.y = part.place_bbox.min.y
    elif pin.orientation == "D": pin.place_pt.y = part.place_bbox.max.y
    elif pin.orientation == "L": pin.place_pt.x = part.place_bbox.max.x
    elif pin.orientation == "R": pin.place_pt.x = part.place_bbox.min.x

for net in nets:
    for pin in pins:
        pin.part.anchor_pins[net].append(pin)          # 本件：anchor（锚）
        for part in net.parts - {pin.part}:
            part.pull_pins[net].append(pin)            # 他件：pull（拉点）
    # 每网每件：pin_ctrs[net] = 本件该网所有 anchor 的质心
```

**核心思想**：吸引力不是"元件中心连元件中心"，而是**引脚沿方向投影到 bbox 边缘的点（place_pt）→ 对端元件的拉点**。这保证同网元件引脚面对面靠近，走线短。

**对本项目的借鉴（中价值）**：本项目不做力导，但"引脚投影点"思想可用于**摆位后验证**——检查某网引脚投影方向是否被元件挡住（M6 pin_connect_audit 可复用）。

### A.4 力导核心 `push_and_pull` + `evolve_placement`（place.py L985/L1118）—— alpha 调度表

```python
force_schedule = [          # (速度, alpha, 稳定系数, 是否对齐, 力掩码)
    (0.50, 0.0, 0.1, False, (1,1)),   # 全吸引（网力主导）
    (0.25, 0.0, 0.01, False, (1,1)),
    (0.25, 0.4, 0.1, False, (1,1)),   # 加入排斥（重叠力渐强）
    (0.25, 0.8, 0.1, False, (1,1)),
    (0.25, 1.0, 0.01, False, (1,1)),  # 全排斥（消除重叠收尾）
]
# 每个阶段迭代直到总位移 < stability 阈值；force = α*排斥 + (1-α)*吸引
```

**关键细节**（对"腾挪"极有价值）：
- 吸引力 `net_force_dist`(L659)：`total_force += Σ(anchor_pt - pull_pt)`；`net_normalize`（按网数归一）防止多网大件飞走；`pt_to_pt_mult` 点对点网放大 2 倍——**"点对点网优先拉近"**。
- 排斥力 `overlap_force`(L741)：两个 place_bbox 重叠 → 最小分离向量推开，力度随 alpha 渐强。
- `rmv_drift`：无锚定件时计算整体漂移力并减掉（防整组飘走）。
- `snap_to_grid`(L102)：迭代结束后 snap 到 GRID（本项目 = `_snap25`）。

**对本项目的借鉴（★ 高价值，用于 M3 placement_fitter）**：用户问题 8 "挤压周围元件就腾挪"——**alpha 调度表是"先吸引后排斥"的标准范式**：先让挤压区元件被网力拉拢，再逐步推开消除重叠，比一次贪心移动稳定。我们做局部腾挪时：锚定芯片/connector（不可动），GND/标签/低优先元件做 α 渐进推开。

### A.5 `place_connected_parts_rowbased`（place.py L1348）—— 大组 BFS 行式摆放（O(n)）

```python
# 阈值：real_count > _ROW_PLACE_THRESHOLD(20) 时走行式（避免力导 O(n²)）
# 1. 建邻接图：同网元件互为邻居
# 2. 种子 = 连接最多的元件；BFS 遍历得顺序
# 3. total_area → max_row_width = sqrt(area) * 2
# 4. 逐行放：col_x + w > max_row_width → 换行 row_y += row_max_h + BLK_INT_PAD
# 5. snap_to_grid；NetTerminal 由 place_net_terminals 绕周边布置
```

**对本项目的借鉴（中价值）**：本项目布局固定，但**BFS 行式排列适合"腾挪后的局部重排"**（如 page8 并联电容 C399 等 9 个电容被挤在一起时，可对它们做局部行式重排+共用 trunk）。`max_row_width = sqrt(area)*2` 与 `BLK_INT_PAD` 是现成的排版参数。

### A.6 `place_net_terminals`（place.py L1139）—— 网络端子绕块布置

```python
def place_net_terminals(net_terminals, placed_parts, nets, force_func, **options):
    # 把 NetTerminal（如电源/地/网络名标记）沿已放置块的 bbox 边缘分布
    # trim_pull_pins：终端只保留最近的拉点 → orient：沿边缘方向 → move_to_pull_pin
```

**对本项目的借鉴（★ 高价值，对应 GND/电源符号分布）**：本项目 GND 分布（`_plan_and_inject_gnd_symbols`）目前按"每芯片 1 个"——**SKiDL 的"终端绕块边缘分布 + 只连最近拉点"正是用户问题 4/7/14 想要的"就近共用 GND"**：GND 符号 = NetTerminal，沿元件块边缘找空位，只连最近 GND 引脚。

## B. route.py 完整流水线（走线绘制阶段）

### B.1 `Router.route(node, tool, **options)` 主入口（route.py L3109）—— 8 步全链路

```
route() 主流程：
  1. 递归 route 子节点（先子后父）
  2. add_routing_points(internal_nets)：引脚沿方向延伸到符号 bbox 边缘 → 形成 stub 起点
  3. routing_bbox = internal_bbox.resize(channel_sz)   # channel_sz = (nets+1)*GRID
  4. create_routing_tracks(routing_bbox)：元件 lbl_bbox 四边坐标去重 → 非均匀 H/V 轨道
  5. create_terminals：引脚 → 轨道上的 terminal（Face）
  6. global_router(internal_nets)：Face 级 Dijkstra 迷宫（全局）
  7. create_switchboxes + switchbox_router：每 switchbox 内 Greedy 列优先（详细）
  8. cleanup_wires() + add_junctions()：美化后处理 + T/X 交点
```

### B.2 `add_routing_points`（route.py L2015）—— stub 引出段的源头

```python
def add_routing_point(pin):
    # 引脚从 pin.pt 沿方向延伸 GRID 单位到 bbox 边缘
    pin.route_pt = pin.pt + pin.direction * GRID    # ← 每个引脚先向外延伸一格
```

**对本项目的借鉴（★ 对应用户问题 15 "电线引出先延伸再拐弯"）**：SKiDL 每个引脚**沿方向延伸恰好 1 格（GRID）到符号边缘**再进入轨道——本项目 detour `stub_lead=100` 已实现类似，但可对齐"延伸量 = GRID 整数倍"（本项目 25 网格 = 1 格），消除"凸出又折回"。

### B.3 `create_routing_tracks`（route.py L2059）—— 非均匀轨道网格

```python
# 每个元件的 lbl_bbox 四边坐标 → v_track_coord/h_track_coord 列表
# 去重 + 排序 → GlobalTrack(HORZ/VERT) 列表
# bbox_to_faces：每元件四边 → Face(part, track, ...)
# track.extend_faces + split_faces + remove_duplicate_faces + add_adjacencies
```

**对本项目的借鉴（中价值）**：本项目 `wire_layout._find_lane` 用"中位 trunk ±50 找车道"是**均匀轨道**；SKiDL 用"元件 bbox 边坐标"生成**非均匀轨道**——同列元件自然共线对齐（这正是用户问题 13 "元件本身互相对齐"的几何基础）。可将 trunk 车道改为"元件 bbox 边坐标"优先，未命中再回退中位。

### B.4 `global_router`（route.py L2190）—— Face 级 Dijkstra 迷宫（非严格 A*）

```python
def rt_srch(start_face, stop_faces):
    visited_faces = [start_face]; start_face.dist_from_start = 0
    unconstrained_faces = stop_faces | net_pin_faces   # 有本网引脚的 face 可穿越
    while True:
        visited_faces.sort(key=lambda f: f.dist_from_start)
        for visited_face in visited_faces:
            for adj in visited_face.adjacent:
                if adj.face in visited_faces: continue
                if adj.face not in unconstrained_faces and adj.face.capacity <= 0:
                    continue                            # 容量耗尽即障碍
                dist = visited_face.dist_from_start + adj.dist
                ... # 更新最近 face（Dijkstra 式，非 A* 无启发式）
    # 多引脚网：随机起点 → 依次连到已连集合（生成树式生长）
def rank_net(net):
    # 排序键 = (bbox 周长, 引脚数) → 短网先布（长网后布，避免被挤）
```

**对本项目的借鉴**：
- **`rank_net` = 短网先布**：本项目 `route_nets` 已按 (span, 引脚数) 排序（长网优先）——**与 SKiDL 相反**！SKiDL 是短网先布（短网先占车道不易被挤断），值得对比验证哪种更美观。
- **`capacity` 拥塞**：Face 容量 = 可容纳网数，耗尽即障碍——本项目 `_find_lane` 的"车道占用"是其简化版；可加"同一轨道段最多 N 网"上限防多网叠线（对应用户问题 2 共用总线但不过度）。
- **生成树式多引脚网生长**：随机起点 → 每次连到已连集合最近 face——比本项目"中位 trunk 一网到底"更接近人工布线（逐引脚就近接入）。

### B.5 `create_switchboxes` + `switchbox_router`（route.py L2362/L2412）—— 详细布线

```python
def switchbox_router(node, switchboxes, **options):
    for swbx in switchboxes:
        try:
            swbx.route(**options)              # Greedy Switchbox：列优先 + TARGET 引导
        except RoutingFailure:
            swbx.flip_xy()                     # 失败 → 转置（行列互换）重试
            swbx.route(**options); swbx.flip_xy()
```

**对本项目的借鉴**：`flip_xy()` 失败重试（水平失败转垂直）是优雅降级的现成模式——本项目 detour 失败回退 P0 车道法（`fallback_to_p0`）同理，可扩展为"detour 失败 → 转置重试 → 再回退"两级降级。

### B.6 `cleanup_wires`（route.py L2441）—— ★★★ 最值得移植的美化后处理（详见上轮 §2.1）

```python
def cleanup_wires(node):
    # 1. order_seg_points：段端点排序（p1 ≤ p2，规范方向）
    # 2. split_segments：按交点/引脚点切最小区间
    # 3. merge_segments：同 Y/X 共线重叠合并 ← 段数削减主力
    # 4. break_cycles：邻接图断环
    # 5. trim_stubs：删连不到引脚的悬空段
    # 6. remove_jogs：3 段阶梯 → 2 段直角（obstructed 检查避让）
```

**移植要点（MIT 许可）**：`merge_segments` 算法完整代码已核实（按 Y 分组 → 按 p1.x 排序 → 贪心合并重叠区间）——可直接照抄为 `wire_simplifier.py` 核心；`obstructed()`（`segment_bbox.resize(Vector(2,2))` 处理边-边碰撞）是本项目 `_avoid_outlines` 的精确化版本。

### B.7 `add_junctions`（route.py L3054）—— T/X 交点（对应本项目 DOT）

```python
def find_junctions(route):
    horz_segs / vert_segs 分离
    for hseg in horz_segs:
        for vseg in vert_segs:
            if hseg 内部与 vseg 内部相交（排除直角端点相接）→ junction 点
    # 前提：必须已 merge_segments（否则端点顺序错乱）
```

**对本项目的借鉴（★ 对应用户问题 12 "就近连接点合并"）**：SKiDL 的 junction 检测**只产生"T 型/十字"交点，且排除直角端点相接**——本项目 `compute_dots` 对"每交点一个 DOT"（用户抱怨过多）应改为**仅在真 T/X 交叉处放 DOT，直角拐弯不放**。且加"先 merge 后找 junction"的顺序约束。

## C. 对本项目可借鉴点汇总表（摆放 → 走线全链路）

| 阶段 | SKiDL 函数 | 可借鉴内容 | 对本项目价值 | 对应问题/模块 |
|------|-----------|-----------|:---:|------|
| 摆放 | `add_placement_bboxes` | 符号 bbox + 引脚侧通道 = 摆放包围盒 | ★★★ | 问题 8 重叠扩大化 → M2 collision margin |
| 摆放 | `expansion_factor` | 布线失败整体放大重放 | ★★★ | M3 placement_fitter 腾挪 |
| 摆放 | `push_and_pull` α 调度 | 先吸引后排斥渐进消除重叠 | ★★★ | M3 腾挪（锚定芯片，推 GND/标签） |
| 摆放 | `place_net_terminals` | 终端绕块边缘分布 + 连最近拉点 | ★★★ | 问题 4/7/14 GND 就近共用 |
| 摆放 | `place_connected_parts_rowbased` | BFS 行式排版（O(n)） | ★★ | 局部重排（page8 并联电容） |
| 摆放 | `net_force_dist` 引脚投影点 | 引脚投影到 bbox 边缘作锚 | ★★ | M6 pin_connect_audit |
| 布线 | `add_routing_points` | 引脚沿方向延伸 1 格 GRID | ★★ | 问题 15 stub 引出段 |
| 布线 | `create_routing_tracks` | 元件 bbox 边坐标 → 非均匀轨道 | ★★ | 问题 13 元件/线对齐 |
| 布线 | `rank_net` 短网先布 | 布线顺序策略（与现相反） | ★★ | wire_layout 排序对比 |
| 布线 | `global_router` capacity | 轨道段容量上限防叠线 | ★★ | 问题 2 共用总线防过度 |
| 布线 | `switchbox_router` flip_xy | 失败转置重试两级降级 | ★ | detour 降级链 |
| 布线 | `cleanup_wires` 全套 | merge/trim/remove_jogs/break_cycles | ★★★ | M4 wire_simplifier（最高优先） |
| 布线 | `add_junctions` | 仅 T/X 真交点放 DOT | ★★ | 问题 12 连接点合并 |

## D. 结论与落地建议

1. **第一优先级（P0，已排期）**：移植 `cleanup_wires` 的 `merge_segments` + `trim_stubs` + `remove_jogs` + `add_junctions`（MIT 许可，算法完整核实）→ `wire_simplifier.py`，作为 wire_layout 后处理，配置开关 `wire_simplify.enabled`。
2. **第二优先级（P1）**：引入 `add_placement_bboxes` 思想（符号 bbox + 引脚侧通道）重构 `overlap_detector` 为统一碰撞函数（M2），margin 默认 = GRID（25）；GND 放置改为 `place_net_terminals` 式"绕块边缘 + 就近接入"（M4 GND 聚类）。
3. **第三优先级（P1/P2）**：`create_routing_tracks` 非均匀轨道（元件 bbox 边坐标）替代/增强 `_find_lane` 均匀车道；`rank_net` 短网先布做 A/B 对比。
4. **远期**：力导布局（`push_and_pull` α 调度 + rowbased）仅用于 `--aesthetic-placement`（用户已同意可选项定位）；A* 迷宫（OpenRAM `get_edge_cost`）留自动布局场景。

*追加完成（2026-08-12 第二轮，软件团队）。源码行号基于 curl 抓取的 SKiDL master 分支 route.py(3236 行)/place.py(2094 行) 实时核实。*


---

# 追加（2026-08-12 第三轮）：落地优先级确认（用户排期）

> 用户确认 SKiDL 研究结论的落地优先级，追加至研究文档归档。

## 落地优先级（用户确认 2026-08-12）

1. **第一优先级（P0，已排期）**：移植 `cleanup_wires` 的 `merge_segments` + `trim_stubs` + `remove_jogs` + `add_junctions`（MIT 许可，算法完整核实）→ `wire_simplifier.py`，作为 wire_layout 后处理，配置开关 `wire_simplify.enabled`。
2. **第二优先级（P1）**：引入 `add_placement_bboxes` 思想（符号 bbox + 引脚侧通道）重构 `overlap_detector` 为统一碰撞函数（M2），margin 默认 = GRID（25）；GND 放置改为 `place_net_terminals` 式"绕块边缘 + 就近接入"（M4 GND 聚类）。
3. **第三优先级（P1/P2）**：`create_routing_tracks` 非均匀轨道（元件 bbox 边坐标）替代/增强 `_find_lane` 均匀车道；`rank_net` 短网先布做 A/B 对比。
4. **远期**：力导布局（`push_and_pull` α 调度 + rowbased）仅用于 `--aesthetic-placement`（用户已同意可选项定位）；A* 迷宫（OpenRAM `get_edge_cost`）留自动布局场景。

## 完整 P0-P2 任务分级（用户确认）

| 优先级 | 项 | 说明 |
|:---:|------|------|
| P0 | SPCOCN-543 SIG_NAME PAINT（#3）、SPCOCN-542 PLACEHOLDER（#2）、占位库结构（#1/#15） | 报错刷屏 + 芯片不渲染，阻塞后续实测 |
| P0 | GND 放芯片上（#4）、标签不随旋转（#10）、引脚未接 QA（#11） | 电气/视觉硬伤 |
| P1 | 冗余连线/连接点合并（wire_simplify 模块）、GND 聚类（#5）、凸出折回（#6）、异向交叉（#7）、统一重叠函数（#12） | 美观化核心，用户 17 条主体 |
| P2 | GUI 开关透出（#13）、pin_mapping 扩展（#14）、IOPORT 位置策略（#16） | 新需求配套 |

*追加完成（2026-08-12 第三轮）。*

---

# 追加（2026-08-12 第四轮）：二期实现验证（非均匀轨道/短网先布/GND 聚类）

## SKiDL 研究结论 → 二期落地实测

| 研究结论 | 落地 | 实测 |
|---------|:---:|------|
| create_routing_tracks 非均匀轨道 | ✅ `_collect_tracks` + `_find_lane` 轨道优先 | v3 WIRE=5089；page5 trunk 吸到元件边 |
| rank_net 短网先布 | ✅ `_net_priority_key` 负号键 + `--net-order` | v2 WIRE=5034（排序改路径不改段数） |
| supply_router.add_side_pin（GND 就近） | ✅ GND 聚类（cluster_radius=2000） | v8 GND 19→97 |
| cleanup_wires 化简（同基线验证） | ✅ v7 p0+simplify | **WIRE 5031→3424（-32%）** |

## 关键洞察

1. **排序改变路径不改变段数**（5031 vs 5034）——短网/长网先布的美观差异需 Cadence 目视确认
2. **化简收益与模式强相关**：p0+化简 -32%（v7）、detour+化简 -44%（v5 相对纯 detour）——对比须同基线
3. **GND 聚类**：贪心最近邻（曼哈顿距离）实现"就近共用"，cluster_radius 可配

*追加完成（2026-08-12 第四轮）。*
