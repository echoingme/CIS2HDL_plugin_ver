# CIS2HDL Phase XIV — 布线美观化 + 文本去冲突 + 人工匹配配线 + 电源芯片匹配增强（架构师交付）

> 架构师：高见远（software-architect）
> 范围：D1 文本/标签去冲突+对齐 / D2 元件重叠检测 / D3 人工匹配→自动配线 / D4 电源芯片匹配改进（复用 practice 工程）/ D5 配置开关体系+模块化（P1 正交绕障 + EDIF 折线复用以路由器形态落地）
> 基线：Phase XIII 交付（433 passed / 1 skipped，P0 车道化布线 + LASTPIN 内联 + IOPORT 模板 + 折线提取）
> 参考：`.workbuddy/artifacts/phaseXIII-routing-scheme-analysis.md`（§6.1 正交绕障、§6.2 EDIF 折线复用、§8 美观化可选项）
> 性质：**只读设计** —— 不改任何源码；全部结论基于源码行号 + practice hdl_lib 实测 + HG5015 netlist/EDIF 实测数据。

---

## 0. 结论速览（TL;DR）

| # | 需求 | 方案一句话 | 默认开关 | 电气风险 | 实现量 |
|---|------|-----------|:-------:|:-------:|:-----:|
| D1 | 标签互相重叠（位号/Value/网络名） | 新模块 `text_layout.py`：收集页面文本 bbox → O(n²) 碰撞检测 → 按优先级微调偏移（SIG_NAME > $LOCATION/VALUE），**只动标签坐标、绝不碰 LASTPIN/WIRE**；网络名 x 对齐 7.5 格点、同侧 Port 对齐、差分对 P 上 N 下 | `text_layout.enabled=false`（默认关，可回退） | **无**（标签不参与电气） | 250-350 行 |
| D2 | 元件相互重叠（fallback 占位尺寸不符） | 复用 `_collect_body_outlines` 做两两相交检测 → 输出 `aesthetic_report.txt`（**只报告不移动**，保守）；`--aesthetic-placement` 开启才自动移动（远期） | `aesthetic.overlap_check=false` | **无** | 60-90 行 |
| D3 | 人工确认匹配 → 软件自动配线（用户重点） | `manual_matches.yaml`（refdes → library_id/section）在 `ConversionEngine._stage_match` 后注入覆盖 → catalog 重建 → pin_coords 用真实符号 css 偏移 → LASTPIN/WIRE 全量重算 → 输出正确连线；配套 `--export-unmatched` 导出待确认清单 | `routing.manual_matches=""`（空=不启用） | **无**（电气由端点重合硬约束保证） | 150-220 行 |
| D4 | 电源芯片匹配改进（复用 practice） | 实测 practice `dc_dc` sym_1..18 / `ldo` / `power_dip4` 引脚清单（见 §D4.2 表）；新增 `cis2hdl/config/power_ic.yaml` 按"引脚数+引脚名+电源网名"匹配候选；`--extra-hdl-lib` 挂载 practice hdl_lib（格式已验证兼容） | `power_ic.enabled=false` | **无** | 120-180 行（实测数据采集另计） |
| D5 | 配置开关 + 模块化（用户强制） | `cis2hdl/config/routing.yaml` 全量开关；`WireRouterBase(ABC) + ROUTER_REGISTRY` 注册 p0_lane / detour / edif_reuse 三种布线器；csa_writer 依赖注入不 import 具体类；异常→`logger.warning`→回退 P0 | 新功能**默认全关** | **无** | 80-120 行 |
| P1a | 正交绕障（stub detour，四开发项之一） | `DetourRouter` 继承 LaneRouter：stub 与 body_outline 相交时走 L/Z 形，绕行点取 outline 外 50 倍数（天然 25 网格） | `routing.mode=detour`（默认 p0） | **无**（端点不变） | 60 行 |
| P1b | EDIF 折线复用（四开发项之一） | `EDIFWireRouter` 消费已解析的 `NetIR.wires`：折线映射→端点重定到实际引脚→中间点吸 25 网格 | `routing.mode=edif_reuse`（默认 p0） | 低（端点重定保证） | 200 行 |
| P2 | A* 迷宫布线 | **仅记录**（远期；布局重排场景才需要） | — | — | — |

**四条铁律（贯穿全部设计）**：
1. **连接判定 = 坐标重合**：WIRE 端点必须精确等于 LASTPIN 坐标——任何"标签/文本"优化不得改变这两个坐标源。
2. **全坐标 25 网格**：所有新产生的坐标（标签偏移、绕行点、折线映射点）一律 `_snap25`/`_snap`。
3. **新功能独立模块 + 配置开关，默认关，可回退**（D5 是工程保障，先做）。
4. **同一目标只保留一个实现**：占位 sym 让位于 EDIF 折线反推；A* 仅记录不排期。

---

# Part A：D1 文本/标签去冲突 + 对齐（核心新需求）

## A.0 现状（证据）

- csa 输出的可见文本有四类，位置全部来自"body 坐标 + symbol.css 属性偏移 + 硬编码模板偏移"：

| 文本 | 生成函数（csa_writer.py） | 坐标来源 | 是否电气相关 |
|------|--------------------------|---------|:-----------:|
| $LOCATION（位号） | `_emit_conn_instance_block` L1356-1362 | `(x-5, y+220)` 硬编码，R 1 / J 1 | 否 |
| VALUE | L1286-1292 | `(x-5, y-50)` 硬编码 | 否 |
| SIG_NAME（网络名@引脚） | `_sig_name_at_pin` L1646-1659 | `coord + (10,10)` | **坐标即连接（LASTPIN）**，标签只是附加文本 |
| SIG_NAME（网络名@线上） | `_sig_name_on_wire` L1662-1673 | `coord`（网首引脚坐标） | 否（独立 FORCEPROP，无 LASTPIN） |
| PIN_TEXT / $PN（引脚名） | `_lastpin_pn` L1634-1643 | `coord + (-10,10)` | **坐标即连接（LASTPIN）** |
| HDL_PORT/VHDL_PORT | `_emit_ioport_block` L1586-1597 | body + css X 偏移 | **坐标即连接（LASTPIN 级别 1）** |

- **无去冲突**：当前每个标签独立放置，不做两两相交检测。用户实测发现：高密度页（page12 等）位号/Value/网络名互相重叠。
- 根因链：① 模板偏移是常数（VALUE 一律 `(x-5, y-50)`，$LOCATION 一律 `(x-5, y+220)`），而 body 之间距离最小只有 ~50-100 → 相邻元件标签 bbox 必然相交；② SIG_NAME 落在引脚 `(x+10,y+10)`，与附近 $PN `(x-10,y+10)` 天然相邻 → 密集区重叠；③ symbol.css 的 P/X 偏移只在 power symbol / IOPORT 生效，普通元件的 VALUE/$LOCATION 用的是硬编码。

## A.1 设计

### A.1.1 数据流

```
PageIR + body_coords + pin_coords + routed_nets
        │
        ▼
TextLayoutOptimizer.collect_text_items(page)      ← 收集全部可见文本（含候选锚点）
        │  (text_kind, text, anchor_xy, font_size, scale, movable, priority, 关联对象)
        ▼
TextLayoutOptimizer.detect_collisions(items)      ← O(n²) 两两相交（页面文本 <500，可接受）
        │  输出 collision 列表 (a, b, overlap_bbox)
        ▼
TextLayoutOptimizer.resolve(items, collisions)    ← 按优先级微调偏移（25 网格）
        │  规则：SIG_NAME 可沿 trunk 移动 → $LOCATION/VALUE 就近最小移动 → PIN_TEXT 禁止移动
        ▼
label_offsets: {text_key: (dx, dy)}              ← 只影响 CSA 输出坐标（DISPLAY 行）
        │
        ▼
csa_writer：VALUE/$LOCATION/SIG_NAME@wire 按 label_offsets 输出；LASTPIN/WIRE 坐标不变
        ▼
aesthetic_report.txt（冲突数/对齐率/差分对正确率）
```

### A.1.2 文本 bbox 估算（关键默认值）

DEHDL 文本由 CSA 的 `FORCEPROP … (x y);` + `DISPLAY scale (x y);` 定位，**锚点是文本左下角**（J 0/1/2 控制对齐）。文本在 Cadence 渲染中的实际 bbox 无法从 CSA 精确得到，只能估算。采用**保守估算**（宁可多留空隙，不可漏判重叠）：

```
width  ≈ char_count × font_size × scale × CHAR_WIDTH_FACTOR + PADDING×2
height ≈ font_size × scale × LINE_HEIGHT_FACTOR + PADDING×2
```

| 参数 | 默认值 | 依据 |
|------|:---:|------|
| `CHAR_WIDTH_FACTOR` | **0.65** | 比例字体平均字宽约 0.55-0.7 倍字高；取 0.65 保守偏宽 |
| `LINE_HEIGHT_FACTOR` | **1.2** | 行高约 1.2 倍字高 |
| `PADDING` | **12**（≈半格） | 文本间至少留半格空隙，防"视觉粘连" |
| `MIN_TEXT_W` | **75**（3 格） | 极短文本（如 $PN "1"）也按 3 格宽算，防密集 $PN 排成一列时互相贴边 |

字体字号来源：symbol.css 的 `P "…" "…" … <height> …`（$LOCATION/VALUE 高 40）与 `X "PIN_TEXT" … <height> …`（PIN_TEXT 高 24），CSA DISPLAY scale 常量已在 csa_writer 顶部定义（`_SCALE_VALUE=0.851064`、`_SCALE_SIG_NAME=0.659574`、`_SCALE_PN=0.808511`、`_SCALE_IOPORT=0.872340`）。**无需读字体文件**——估算只用于"冲突判定与位移量"，不追求像素级精确。

> 实现提示：`symbol_css.py` 已有 `SchematicSymbolDef.bounding_box()`（L90），可复用其解析结果；但文本估算仍需按上表独立实现（bounding_box 是符号轮廓，不是文本 bbox）。

### A.1.3 冲突解算算法（伪代码）

```
PRIORITY = {SIG_NAME_ON_WIRE: 0, SIG_NAME_ON_PIN: 0, VALUE: 1, LOCATION: 1, PORT_LABEL: 2, PIN_TEXT: 3(禁止移动)}

def resolve(items, collisions, grid=25, max_iter=4):
    # 1. 只解"至少一方可移动"的碰撞；双方都不可移动 → 记入 report（无法自动解决）
    # 2. 迭代多轮：一轮内先解低优先级（高优先级先动），再解高优先级
    for _ in range(max_iter):
        changed = False
        for (a, b, ov) in collisions:
            if a.priority > b.priority: a, b = b, a       # 让低优先级(数字小)先动
            mover = a if a.movable else (b if b.movable else None)
            if mover is None:
                report.unresolved.append((a.key, b.key)); continue
            if mover.kind == SIG_NAME_ON_WIRE:
                # SIG_NAME 不参与电气：沿所属 trunk 移动（只动 x 或只动 y，保持"在线"观感）
                candidate = slide_along_trunk(mover, b.bbox)   # 同 trunk 上向远离方向移 1-4 格
            else:
                # $LOCATION / VALUE：就近最小位移，8 方向试最近 25 网格点
                candidate = nearest_free_grid(mover, b.bbox, step=25)
            if candidate:
                mover.offset = candidate - mover.origin      # 记录相对位移
                mover.bbox = translate(mover.bbox, candidate - mover.anchor)
                changed = True
        if not changed: break
    # 3. 对齐（与解冲突同轮后处理）：
    for net_label in SIG_NAME_ON_WIRE:
        net_label.x = align_left_to(trunk_start_x(net_label.net) + 7.5_GRID_UNITS)
    for port in same_side_ports(page):
        port.y = even_spacing(port.rank) ; port.x = port.side_x
    return {it.key: it.offset for it in items if it.offset != (0,0)}
```

**对齐规则落地**（STANDARDS Part III §1.2）：
- **网络名 x 对齐（7.5 格点）**：DEHDL 空间 1 格 = 0.05 inch = 50 单位，7.5 格 = **375 单位**。规则 = 同页同 trunk 列的网络名，其锚点 x 统一为 `trunk 起点 x + 375` 的最近 25 倍数。实现为：`align_x = snap25(min_x_of_wire + 375)`，对 `SIG_NAME_ON_WIRE` 类标签统一设置（`text_layout.align_net_names=true` 时）。
- **同侧 Port 对齐**：IOPORT 块已按 `_ioport_position(index)` 排布（L1510-1520 区域），对齐优化 = 右侧缘/上缘统一 x/y、y 等间距（rank 连续、间距 = 50 的倍数）。
- **差分对标签 P 上 N 下**：检测网络名含 `_P/_N` 或 `_P_/_N_` 后缀的成对网（`net.name` 除后缀外相同），强制同列两个 SIG_NAME 标签 y 满足 `y_P > y_N`（P 上 N 下）；若源数据无 `_P/_N` 后缀则跳过（不猜测）。

**硬约束**：
- `PIN_TEXT` / `SIG_NAME_ON_PIN`（LASTPIN 附加文本）**禁止移动**——它们的锚点即 LASTPIN 坐标；要挪只能挪"独立的 FORCEPROP SIG_NAME"（`_sig_name_on_wire` 产物，无 LASTPIN）。
- 所有新偏移经 `snap25`（复用 `CoordTransform._snap25` 或 wire_layout `_snap`），保证标签坐标仍在 25 网格。
- 移动只影响 csa 输出的 `DISPLAY (x y)` / `FORCEPROP … (x y)` 标签行，**不影响 LASTPIN/WIRE 段**——电气连接不变。

### A.1.4 接口签名（函数级）

```python
# cis2hdl/core/writer/text_layout.py （新模块，独立单一职责）

@dataclass(frozen=True)
class TextItem:
    key: str                    # 唯一键："refdes.VALUE" / "refdes.LOCATION" / "net.SIG_NAME" / "refdes.pin.PIN_TEXT"
    kind: str                   # "LOCATION" | "VALUE" | "SIG_NAME" | "PIN_TEXT" | "PORT"
    text: str
    anchor: tuple[int, int]     # 当前锚点坐标（CSA 输出坐标）
    font_size: int              # css 高度（40/32/24…）
    scale: float                # CSA DISPLAY scale
    movable: bool               # SIG_NAME_ON_WIRE=True；PIN_TEXT=False
    priority: int               # 0=SIG_NAME,1=LOCATION/VALUE,2=PORT,3=PIN_TEXT
    net_key: str = ""           # 所属网（SIG_NAME 对齐/差分对用）
    origin: tuple[int, int] = (0, 0)   # 初始锚点（差分相对位移）

    def bbox(self) -> tuple[int, int, int, int]: ...

@dataclass
class TextLayoutResult:
    offsets: dict[str, tuple[int, int]]        # text key → (dx, dy)
    collisions_before: int
    collisions_after: int
    unresolved: list[tuple[str, str]]          # 无法自动解决的碰撞（记 report）

class TextLayoutOptimizer:
    """标签去冲突 + 对齐（只动标签坐标，绝不碰 LASTPIN/WIRE）。"""
    CHAR_WIDTH_FACTOR = 0.65
    LINE_HEIGHT_FACTOR = 1.2
    PADDING = 12
    MIN_TEXT_W = 75
    ALIGN_NET_LEFT_GRID = 7.5                # 网络名左对齐 7.5 格点
    GRID = 25

    def __init__(self, cfg: "RoutingConfig | None" = None) -> None: ...
    def collect_text_items(self, page_conn, body_coords, pin_coords,
                           routed_nets) -> list[TextItem]: ...
    def detect_collisions(self, items: list[TextItem]) -> list[tuple[TextItem, TextItem, tuple[int,int,int,int]]]: ...
    def resolve(self, items, collisions) -> TextLayoutResult: ...
    def align_net_names(self, items) -> None: ...          # x = snap25(trunk_min_x + 375)
    def align_ports(self, items) -> None: ...              # 同侧 IOPORT 等间距/边缘对齐
    def enforce_diff_pairs(self, items, net_names) -> None: ...  # _P/_N → P 上 N 下
    def optimize(self, page_conn, body_coords, pin_coords, routed_nets) -> TextLayoutResult: ...
    # 输出：offsets 传给 csa_writer 标签行；统计进 aesthetic_report
```

### A.1.5 与现有测试的影响

| 测试 | 断言 | 影响 | 处置 |
|------|------|------|------|
| `test_one_sig_name_per_net` / `test_wire_endpoints_include_pins`（test_phase_xi_p0 L490/L505） | SIG_NAME 引脚 ∈ WIRE 端点 | 若开了 `text_layout.enabled`，SIG_NAME_ON_PIN 不移动 → 不破；SIG_NAME_ON_WIRE 是独立 FORCEPROP，不影响 LASTPIN | 保持（开关默认关，回归零影响） |
| `test_every_connected_pin_has_lastpin`（L476） | LASTPIN 计数 | 标签移动不产生/删除 LASTPIN | 不破 |
| 新增 `tests/unit/test_text_layout.py` | bbox 估算、碰撞检测、SIG_NAME 优先移动、PIN_TEXT 不动、25 网格、差分对 P 上 N 下、网络名 x=375 对齐 | — | 新增 |
| e2e 端点重合断言（tests/e2e） | WIRE 端点 == LASTPIN | 标签与 WIRE 分属不同行 → 不破 | 新增断言：`text_layout.enabled` 下标签坐标均 25 网格 |

---

# Part B：D2 元件相互重叠检测与解算

## B.0 现状

- 转换**保持 CIS 原始布局**（工程师绘制），一般无重叠；但两类场景会引入重叠：
  1. **fallback 占位芯片**：未匹配芯片（U6 等）回退到 CH347/占位轮廓（`_placeholder_outline` L1796-1814 / `_fallback_pin_offsets` L1948-2007），占位矩形尺寸与真实芯片不符，可能压住邻件。
  2. **grid_position 兜底**：无坐标实例按网格排布（`CoordTransform.grid_position`），网格间距 c_page_step_x=2000 一般安全，但 power_symbol_position 角区 150 步进 + 元件密集时可能贴边。
- `csa_writer._collect_body_outlines`（L1816-1861）**已存在**且输出 `(x0,y0,x1,y1)` 绝对矩形——重叠检测可直接复用，无需新数据采集。

## B.1 设计（保守：只检测报告，不自动移动）

```
def detect_overlaps(outlines: list[(x0,y0,x1,y1)], refdes_list) -> list[Overlap]:
    # O(n²) 两两相交（页面元件 <150，可接受；n=100 → 4950 对，毫秒级）
    for i < j:
        if intersects(outlines[i], outlines[j]) and overlap_area >= MIN_OVERLAP_AREA:
            report.overlaps.append(Overlap(
                refdes_a, refdes_b,
                bbox_a, bbox_b,
                overlap_rect, overlap_area,
                kind=classify(a, b),     # "placeholder" | "grid" | "user"
            ))
```

- **默认**：只输出 `aesthetic_report.txt`（与 MappingCSV 同目录输出），**不移动任何布局**（符合 Part III §1.3 "全局布局难自动化" + §1.4 "软件 80% + 工程师 20%"）。
- **`--aesthetic-placement` 开启**才自动移动（远期：force-directed 局部推开，见 phaseXIII §8.3 方案 B；本 Phase 仅留开关占位）。
- `MIN_OVERLAP_AREA` 默认 `25×25=625`（1 格²），过滤"仅仅贴边"的误报。

### B.1.1 overlap 报告格式（aesthetic_report.txt）

```
=== Aesthetic Report: HG5015-BE36_V10 ===
[OVERLAP] page=12  total=3
  U6G  (-8752 5411) outline(-8952 5261,-8552 5561)  vs  U6F (-8337 6180) outline(-8537 6030,-8137 6330)
    overlap=(-8537 5411,-8552 5561) area=15×150=2250  kind=placeholder
    fix_hint: U6G 是未匹配占位（pin=15, fallback CH347），建议 D3 人工匹配后重转
[ALIGN] net_name_x_align=92.3% (48/52)   port_align=100%   diff_pair_ok=2/2
[TEXT]  collisions_before=37  collisions_after=3  unresolved=1 (U12.VALUE vs U13.LOCATION)
[GRID]  off_grid_labels=0  off_grid_wires=0
```

- `kind` 分类：`placeholder`（占位轮廓）、`grid`（兜底网格）、`user`（原始 CIS 布局本身重叠——仅信息，不自动处理）。
- 报告同时承载 D1/D2 全部量化指标（文本冲突数、对齐率、off-grid、差分对方向）——**一个报告文件，多模块写入**（D5 的 `AestheticReport` 收集器）。

### B.1.2 接口签名

```python
# cis2hdl/core/writer/aesthetic_report.py （新模块）
@dataclass
class Overlap:
    page: int
    refdes_a: str; refdes_b: str
    bbox_a: tuple[int,int,int,int]; bbox_b: tuple[int,int,int,int]
    overlap_rect: tuple[int,int,int,int]
    area: int
    kind: str            # "placeholder" | "grid" | "user"

class AestheticReport:
    """多模块共用的量化报告收集器（D1 文本 / D2 重叠 / D5 布线统计）。"""
    def add_overlap(self, ov: Overlap) -> None: ...
    def add_text_stats(self, before: int, after: int, unresolved: list) -> None: ...
    def add_align_stats(self, net_align: float, port_align: float, diff_ok: int, diff_total: int) -> None: ...
    def add_grid_stats(self, off_grid_labels: int, off_grid_wires: int) -> None: ...
    def write(self, output_dir: Path) -> Path: ...   # aesthetic_report.txt

# cis2hdl/core/writer/overlap_detector.py （新模块，~60 行）
class OverlapDetector:
    def __init__(self, min_area: int = 625) -> None: ...
    def detect(self, page, body_coords, outlines_by_refdes: dict[str, tuple]) -> list[Overlap]: ...
```

### B.1.3 测试影响

- 复用现有 `test_phase_xi_p0.py::TestWireLayoutEngine` 的 outline fixture；新增 `tests/unit/test_overlap_detector.py`（构造 3 元件页：1 对重叠 + 1 对贴边不重叠 + 1 对正常，断言 area 过滤与 kind 分类）。
- 回归：开关默认关，转换路径不变 → 433 全绿。

---

# Part C：D3 人工匹配 → 自动配线流程（用户重点）

## C.0 现状与缺口

- 现状：自动匹配（matcher 管线）对未匹配芯片回退占位（U6G→CH347/占位），**引脚错位、连线生硬**（Phase XIII Q3 已缓解中心塌缩，但符号仍是错的）。
- 用户需求：**先人工确认元件匹配**（如 U6 电源芯片该匹配 `dc_dc` 而不是 CH347），**软件再基于确认后的匹配自动配好线路**。这是"先人工确认元件匹配方案，再确认和调整布线方案"的落地点。
- 现有基础：`mapping.csv` 已输出逐器件映射（MappingCSVWriter）；`ConversionEngine` 匹配在 `_stage_match`（L905）；`CSAWriter.set_matches` 把 match 结果灌入 `_match_map`（L107-120）；pin_coords 链路 `_compute_pin_geometry`（L1048）已支持任意符号 css 偏移。

## C.1 设计

### C.1.1 人工匹配输入格式（manual_matches.yaml）

```yaml
# manual_matches.yaml — 用户人工确认的元件匹配表
version: "1.0"
created: "2026-08-11"
matches:
  - refdes: "U6"
    library_id: "dc_dc"        # 优先匹配 practice hdl_lib 的 dc_dc
    section: 1                 # 可选；缺省 1（默认 sym_1）
    value: "MP147X"            # 可选：覆盖 PART_NAME/VALUE 显示
    note: "用户确认 U6 为电源芯片（原自动匹配错误回退 CH347）"
  - refdes: "U12"
    library_id: "ldo"
    section: 2
    note: "3.3V LDO（VIN/GND/EN/ADJ/VOUT 5 引脚）"
  - refdes: "U15"
    library_id: "power_dip4"
    section: 1
```

- **格式要求**：`refdes` 必填；`library_id` 必填（hdl_lib 内的 cell 名，大小写不敏感）；`section` 选填默认 1。
- **校验（转换时）**：
  - 引脚数校验：`irec.pins 数量 vs 符号 css 实际引脚数`（`_get_css_pin_offsets` 结果长度 + chips.prt 引脚数）；**不匹配 → logger.warning + 写入 aesthetic_report/异常清单，仍继续转换**（用占位分布兜底，保证 WIRE 不塌缩）——绝不静默失败。
  - 未知 library_id：`component_db.get_by_library_id` 查不到 → warning + 忽略该条（保留自动结果）。
  - 同一 refdes 重复条目 → 后者覆盖 + warning。

### C.1.2 覆盖点（在 pipeline 哪一层注入）

```
ConversionEngine.convert()
  └─ _stage_parse      → DesignIR
  └─ _stage_scan       → ComponentDB（hdl_lib 扫描）
  └─ _stage_match      → list[MatchResult]（自动匹配）
        │
        │  ★ 注入点：_apply_manual_matches(match_results, manual_cfg)
        │    └ 对每条 manual match：覆盖对应 refdes 的 MatchResult
        │      (target_library_id=library_id, section=section,
        │       confidence=1.0, strategy=MatchStrategy.MANUAL)
        │    └ 校验引脚数/存在性 → warning 收集
        ▼
  └─ _stage_generate   → CSAWriter(set_matches=…, hdl_lib_path=…)
        └ _compute_pin_geometry：body + 真实符号 css 偏移（dc_dc/ldo 的 C 命令）
        └ _lastpins_for_instance / route_nets：LASTPIN/WIRE 全部重算
        → 输出正确连线（U6 引脚按 dc_dc 符号真实分布、WIRE 端点重合）
```

- **为什么注入在 `_stage_match` 之后**：后续所有阶段（catalog 重建、match_map、pin_coords、布线）都只消费 MatchResult，覆盖一次即可全链路生效——无需改 csa_writer/布线器。
- `MatchStrategy` 需新增枚举值 `MANUAL`（在 `ir/match.py` 或 matcher registry 中注册，mapping.csv 的 strategy 列显示 "MANUAL"）。

### C.1.3 交互流程（用户工作流）

```
1. 转换器 --export-unmatched → unmatched_report.yaml（refdes / pin 数 / 引脚名 / 相连网 / Top-3 候选）
2. 用户打开 mapping.csv（现有）或 unmatched_report.yaml → 人工填写 manual_matches.yaml
3. 转换器 --manual-matches manual_matches.yaml → 覆盖匹配 → 自动重算引脚/连线
4. 用户 Cadence 打开验证；不满意 → 改 yaml → 重转（迭代，转换秒级）
```

### C.1.4 --export-unmatched 输出格式

```yaml
# unmatched_report.yaml（--export-unmatched 生成，供人工填写）
version: "1.0"
unmatched:
  - refdes: "U6"
    pin_count: 15            # EDIF/pstxnet 实际连接引脚
    pin_names: [R4, P4, A21, B21, Y22, Y24, Y25, W26, W27, V25, ...]
    nets: [USB2_1, VDD_SYSLDO_0P9, ...]
    auto_match: {library_id: "ch347", confidence: 0.45, strategy: "ACTIVE_WITHIN_TYPE"}
    candidates:               # 按引脚数/引脚名/电源网名排序的 Top-3
      - {library_id: "dc_dc", section: 1, pins: 6, score: 0.82, reason: "6 引脚且含 IN/GND/EN/FB/SW/BST 电源引脚集"}
      - {library_id: "dc_dc", section: 2, pins: 5, score: 0.78, reason: "5 引脚含 VIN/GND/EN/FB/SW"}
      - {library_id: "ldo", section: 1, pins: 4, score: 0.55, reason: "4 引脚 VIN/GND/VOUT"}
    fill: "refdes: U6\nlibrary_id: dc_dc\nsection: 1\n"
low_confidence:
  - refdes: "U19"
    auto_match: {library_id: "...", confidence: 0.62}
    candidates: [...]
```

- candidates 评分逻辑即 D4 的"电源芯片匹配规则"（见 §D4.3）——`--export-unmatched` 与 D4 共用同一评分函数，一个实现两处消费。

### C.1.5 接口签名

```python
# cis2hdl/core/matching/manual_matches.py （新模块，~120 行）
@dataclass
class ManualMatch:
    refdes: str
    library_id: str
    section: int = 1
    value: str = ""
    note: str = ""

@dataclass
class ManualMatchesConfig:
    version: str
    matches: list[ManualMatch]

    @classmethod
    def load(cls, path: Path) -> "ManualMatchesConfig": ...   # yaml.safe_load + pydantic 校验

def apply_manual_matches(match_results: list["MatchResult"],
                         manual: ManualMatchesConfig,
                         component_db: "ComponentDB") -> tuple[list["MatchResult"], list[str]]:
    """覆盖匹配结果；返回 (新 match_results, warnings 列表)。"""
    ...

def export_unmatched(match_results, component_db, page_conns,
                     power_candidates: "PowerCandidateScorer | None" = None) -> dict:
    """生成 --export-unmatched 报告 dict（refdes/pin/候选）。"""
    ...
```

### C.1.6 测试影响

- 新增 `tests/unit/test_manual_matches.py`：①覆盖后 MatchResult.strategy=MANUAL、confidence=1.0；②引脚数不匹配 → warning 且不崩溃；③未知 library_id → 忽略；④`--export-unmatched` 输出的 candidates 排序含电源候选。
- 新增 e2e：用合成 fixture 手工匹配 U 元件到 `dc_dc/sym_1`（6 引脚 FB/IN/GND/EN/SW/BST），断言输出 CSA 的 LASTPIN 坐标 = body + dc_dc css 偏移、WIRE 端点重合、无中心塌缩。
- 回归：默认不传 `--manual-matches` → 行为不变。

---

# Part D：D4 电源芯片匹配改进（复用 practice 工程）

## D.0 已确认事实（实测）

- HG5015 所有 `U*` 类元件 `conf=0.4475`、`strategy=ACTIVE_WITHIN_TYPE`——部分匹配、无具体符号（type_gate.yaml `U: [[IC,0.85],[interface,0.70],[connector,0.40],[voltage_regulator,0.35]]`，voltage_regulator prior 仅 0.35，且 hdl_lib 无该 cell）。
- practice 工程 `docs_for_reference/previous_switch_programme/switch_practice/practice/hdl_lib/` 存在完整电源符号（格式与 tests/fixtures/hdl_lib 一致：`chips/entity/metadata/part_table/sym_N/symbol.css`）。
- HG5015 netlist 实测：`VDD_SYSLDO_0P9`、`VDD_CLDO_0P96`、`VDD_CLDO_0P96_2G` 等电源网名存在（1v1/3v3/0v9 量级），U6 引脚为 BGA 式字母数字（J27/L26/C18…）——U6 是主 SoC 而非电源芯片；电源芯片应为 U 类中**少引脚（4-8）**的实例（待工程师实测确认，见 D.3 采集步骤）。

## D.1 设计：practice 电源符号清单（可复用库存）

### D.1.1 dc_dc 各 section 引脚实测表（sym_1..sym_18）

| section | 引脚数 | 引脚名（左/右列） | 典型器件类型 | 适用场景 |
|:---:|:---:|------|------|------|
| sym_1 | **6** | FB/IN/GND/EN/SW/BST | 6 引脚同步降压（MP147X 类） | **首选**：6 引脚电源芯片 |
| sym_2 | **5** | EN/GND/SW/VIN/FB | 5 引脚降压（TPS56X201 类） | 5 引脚电源芯片 |
| sym_3 | **16** | VIN/NC1/NC2/PGND/PG/MODE/NC…/VOUT/SW1-4/BST | 多路输出电源 | 8+ 引脚电源 |
| sym_4 | **5** | IN/GND/EN/SS/EPAD | 5 引脚带 EPAD | 5 引脚（含散热焊盘） |
| sym_5 | **11** | EN/MODE/PGOOD/VDD/VIN1-6/VREG | 多路输入 LDO/DC-DC | 11 引脚 |
| sym_6 | ~28 | EN/FREQ/SS/AGND/PG/VCC/IN1-2/PGND1-10… | 大电流多相 | 20+ 引脚 |
| sym_7 | ~12 | EN/FREQ/SS/AGND/PG/VCC/IN1-2/PGND1-4 | 多相 | 12 引脚 |
| sym_8 | **5** | EN/FREQ/EPAD/VIN/GND | 5 引脚 | 5 引脚 |
| sym_9 | **5** | EN/VIN/VDD/SS/FSET | 5 引脚 | 5 引脚 |
| sym_10 | **8** | IN/PMID/CELL/VB/ISET/ILIM/VDPM/PMID_S | 充电管理 | 8 引脚电源管理 |
| sym_11 | **8** | BD1/BD2/EN/SVIN/ILIM/FS/COMP… | 升压/充电 | 8 引脚 |
| sym_12 | **4** | SD/VDDQ/AVIN/PVIN | 4 引脚 DDR 电源 | 4 引脚 |
| sym_13 | **5** | EN/GND/FREQ/VIN/EPAD | 5 引脚 | 5 引脚 |
| sym_14 | ~21 | VCC/VCC_IN/VDRV/SCL/SDA/ALT/CTRL/PG/PASS/TAKE/SET/ADDR/ISUM/NC1-8/IREF/VIN1 | I2C 可编程电源 | 20+ 引脚 |
| sym_15 | **6** | IN/PG/EN/IMLT/BYP/VCC | 6 引脚 | 6 引脚 |
| sym_16 | ~32 | ADDR_1-4/ALT/CTRL/PASS/PG/RUN/SCL/SDA/SET_1/ISUM_1-2/VOSNS±/VOUT_1-8… | 大电流多路 | 32 引脚 |
| sym_17 | ~90 | GND_1..GND_89（全地） | 大封装地阵列 | 特殊（地太多，慎用） |
| sym_18 | **6** | IN/GND/EN/LX/BS/FB | 6 引脚异步降压 | 6 引脚（LX 引脚名） |

### D.1.2 ldo / power_dip4 / 电源地符号

| cell | section | 引脚数 | 引脚名 | 适用场景 |
|------|:---:|:---:|------|------|
| ldo | sym_1 | **4** | VIN/GND/4/VOUT | 4 引脚 LDO（3.3V/1.1V 常用） |
| ldo | sym_2 | **5** | VIN/GND/VOUT/EN/ADJ | 5 引脚可调 LDO（带使能） |
| power_dip4 | sym_1 | **4** | NC2/VCC-/VCC+/NC1 | 双电源 dip 4 脚 |
| gnd_power | sym_1 | 1 | GND | 电源地符号（已支持） |
| vcc_circle | sym_1 | 1 | G<SIZE-1..0> | 电源符号（已支持） |

### D.1.3 复用方式（二选一，推荐 A）

- **方案 A（推荐）**：把 `dc_dc` / `ldo` / `power_dip4` 三个 cell 复制进 `tests/fixtures/hdl_lib/`（与现有库同目录，格式已验证 100% 兼容——同为 `chips/entity/metadata/part_table/sym_N/symbol.css` 结构，`SymbolCssPinParser` 可直接解析）。优点：零运行时改动、测试即覆盖；代价：fixtures 增加 ~50 文件（可只拷 sym_1/sym_2/sym_4/sym_8/sym_13/sym_18 + ldo + power_dip4，≈15 文件）。
- **方案 B（可选增强）**：`--extra-hdl-lib <dir>` 挂载额外库目录（CLI 新增），`ComponentDB` 扫描时并入（`_stage_scan` 支持多根目录）。优点：不动 fixtures；代价：需给 scan 加参数。**兼容性评估**：practice 符号格式 = fixtures 格式（已验证），`SymbolCssParser/SymbolCssPinParser` 对 `C/X/P/L/M/T` 命令解析无需改动；`chips.prt` primitive 结构一致。**可行，风险低**。

## D.2 设计：电源芯片匹配规则（power_ic.yaml）

```yaml
# cis2hdl/config/power_ic.yaml（新增，D4 配置）
version: "1.0"
enabled: false                    # 总开关（CLI --power-ic 或 routing.yaml 引用）
# 电源网名模式（HG5015 实测：VDD_SYSLDO_0P9 / VDD_CLDO_0P96 / 1v1 / 3v3 / 0v9 …）
power_net_patterns:
  - "(?i)vdd.*(0p9|0p96|1v1|1p1|3v3|3p3|1v8|1p8)"
  - "(?i)^(0v9|1v1|3v3|1v8)$"
  - "(?i)v(in|out|dd|cc).*(sys|ldo|dc)"
# 电源引脚名集合（用于打分）
power_pin_names: [VIN, IN, GND, PGND, AGND, EN, FB, SW, BST, LX, BS, VOUT, VDD, VCC, PG, PGOOD, MODE, SS, EPAD, ADJ, IREF, ILIM, ISET, COMP, FREQ]
# 候选表：引脚数 → 有序候选（section 按引脚集相似度排序）
candidates_by_pin_count:
  4:  [{library_id: ldo, section: 1}, {library_id: power_dip4, section: 1}, {library_id: dc_dc, section: 12}]
  5:  [{library_id: dc_dc, section: 2}, {library_id: dc_dc, section: 4}, {library_id: dc_dc, section: 8},
       {library_id: dc_dc, section: 9}, {library_id: dc_dc, section: 13}, {library_id: ldo, section: 2}]
  6:  [{library_id: dc_dc, section: 1}, {library_id: dc_dc, section: 15}, {library_id: dc_dc, section: 18}]
  8:  [{library_id: dc_dc, section: 10}, {library_id: dc_dc, section: 11}]
  11: [{library_id: dc_dc, section: 5}]
  12: [{library_id: dc_dc, section: 7}]
  16: [{library_id: dc_dc, section: 3}]
# 评分权重
scoring:
  w_pin_count: 0.40       # 引脚数完全匹配
  w_pin_name_jaccard: 0.40  # 引脚名集合 Jaccard 相似度
  w_net_pattern: 0.20     # 相连网名命中电源网模式
  min_score_auto: 0.80    # ≥0.80 自动采用（替代 ACTIVE_WITHIN_TYPE 的低置信匹配）
  min_score_candidate: 0.50  # 0.50-0.80 进 --export-unmatched 候选列表
```

### D.2.1 匹配流程

```
对每个 U* 实例（引脚数 ≤ 20 且相连网含电源网名）：
  1. 提取特征：pin_count、pin_names（pstxnet/EDIF）、connected_nets
  2. 从 candidates_by_pin_count[pin_count] 取候选符号（含 ldo/dc_dc/power_dip4）
  3. 对每个候选：
       score = w_pin_count * pin_count_hit
             + w_pin_name_jaccard * jaccard(实例引脚名, 符号引脚名)
             + w_net_pattern * any(网名命中 power_net_patterns)
  4. score ≥ min_score_auto → 直接替换 MatchResult（strategy=POWER_IC_AUTO）
  5. min_score_candidate ≤ score < min_score_auto → 进 --export-unmatched candidates
  6. 全部 < min_score_candidate → 维持原自动匹配（不动）
```

- **与 D3 的关系**：D4 提供"自动候选 + 评分"，D3 提供"人工确认落地"。`--export-unmatched` 的 candidates 列 = D4 评分输出，用户照填 manual_matches.yaml → D3 覆盖生效。**两模块正交、可独立开关**。

## D.3 实测步骤（数据待工程师采集，本 Phase 只给方法）

> 以下数据工程师需在实现前跑一遍，把结果回填 `power_ic.yaml` 的 `candidates_by_pin_count`（当前表是依据 practice 符号结构 + HG5015 网名推断的初稿，**引脚名匹配权重依赖真实 U 元件引脚名**）。

1. **列出疑似电源芯片**：解析 `tests/fixtures/HG5015test/pstxnet.dat` 中所有 `U*` 实例，按 `NODE_NAME Ux` 出现次数统计引脚数；筛出 **引脚数 4-20** 的实例（主 SoC U6 数百引脚自动排除）。
2. **提取引脚名**：对每个候选实例，从 `pstxnet.dat` 取 `NODE_NAME Ux <pin>` 列表；与 EDIF 解析结果交叉验证（`edif_parser` 已输出实例引脚）。
3. **提取相连网**：`pstxnet.dat` 按 `NODE_NAME` 行后的网名分组；筛出网名含 `VDD_SYSLDO_0P9/VDD_CLDO_0P96/1V1/3V3/0V9` 等的实例（HG5015 实测 19 处 dc_dc/ldo 相关电源网）。
4. **人工核对**：对 2-3 个高置信实例（如 6 引脚含 IN/GND/EN/FB/SW/BST）用 Cadence/CIS 原图核对，确认后写入 `manual_matches.yaml`（D3 链路）→ 重转验证 WIRE。
5. **回填配置**：把实测 `pin_names` 与 practice 符号引脚集做 Jaccard 对照，确认/修正 `candidates_by_pin_count` 排序。

## D.4 测试影响

- 新增 `tests/unit/test_power_ic_match.py`：①6 引脚实例（IN/GND/EN/FB/SW/BST 网含 3v3）→ 命中 dc_dc sym_1 score≥0.8；②4 引脚（VIN/GND/VOUT + EN）→ 命中 ldo sym_1/sym_2；③主 SoC（引脚数>20）→ 不触发；④低分 → 不覆盖。
- 新增 `tests/unit/test_extra_hdl_lib.py`：`--extra-hdl-lib` 挂载 practice hdl_lib 目录 → ComponentDB 能扫到 dc_dc/ldo/power_dip4 且 `SymbolCssPinParser` 解析成功。
- 回归：`power_ic.enabled=false` 默认 → 433 全绿。

---

# Part E：D5 配置开关体系 + 模块化（用户强制要求）

## E.0 设计原则落地

- wire_layout 保持**单一职责：几何合成**（不引入网络/符号知识）；路由策略抽象到 Router；文本/重叠/报告独立模块。
- 所有新功能独立模块 + 配置开关，**默认关、可回退**；随时增删功能，禁止硬编码（Part I 纪律）。

## E.1 配置结构（cis2hdl/config/routing.yaml，新增）

```yaml
# cis2hdl/config/routing.yaml — Phase XIV 布线/美观化配置
version: "1.0"

routing:
  mode: p0                    # p0 | detour | edif_reuse  （CLI --routing 覆盖）
  lane_pitch: 50              # P0（已有 wire_layout._LANE）
  grid: 25                    # P0（已有）
  detour_stubs: true          # P1a 正交绕障（mode=detour 时生效）
  use_edif_wires: false       # P1b EDIF 折线复用（mode=edif_reuse 时生效；默认关）
  cross_page_opt: false       # 跨页网视觉优化（IOPORT 接入 WIRE 已有；此开关控制"IOPORT 对齐/美化"）
  fallback_to_p0: true        # 新功能异常 → logger.warning → 回退 P0 车道法

text_layout:
  enabled: false              # D1 总开关（CLI --text-layout 置 true）
  align_net_names: true       # 网络名 x 对齐（7.5 格点 = 375 单位）
  align_ports: true           # 同侧 Port 对齐
  diff_pair_pn: true          # 差分对标签 P 上 N 下
  char_width_factor: 0.65
  padding: 12

overlap:
  check: false                # D2 重叠检测（报告）
  min_area: 625
  auto_placement: false       # 远期：--aesthetic-placement 才开

manual_matches: ""            # D3：manual_matches.yaml 路径（CLI --manual-matches）
export_unmatched: ""          # D3：--export-unmatched 输出路径（空=不导出）

power_ic:
  enabled: false              # D4（也可独立 --power-ic）
  config_file: "cis2hdl/config/power_ic.yaml"

aesthetic:
  enabled: false              # 总开关（CLI --aesthetic）：同时打开 text_layout/overlap/power_ic 并输出报告
  report: true                # 输出 aesthetic_report.txt
```

### E.1.1 加载机制（扩展现有 config.py）

```python
# cis2hdl/core/config.py — 新增
@dataclass
class RoutingConfig:
    mode: str = "p0"
    detour_stubs: bool = True
    use_edif_wires: bool = False
    cross_page_opt: bool = False
    fallback_to_p0: bool = True
    text_layout: TextLayoutCfg = field(default_factory=TextLayoutCfg)
    overlap: OverlapCfg = field(default_factory=OverlapCfg)
    manual_matches: str = ""
    export_unmatched: str = ""
    power_ic: PowerIcCfg = field(default_factory=PowerIcCfg)
    aesthetic: AestheticCfg = field(default_factory=AestheticCfg)

class Config:
    def __init__(self):
        ...
        self.routing = RoutingConfig()

    def load_from_file(self, path: Path) -> None:
        """现有 Config.load_from_file 是 NotImplementedError —— Phase XIV 落地为
        yaml.safe_load + dataclasses.replace 覆盖（pyyaml 已在依赖）。"""
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        # 按段覆盖：page / routing / text_layout / overlap / power_ic …
```

- `type_gate.yaml` 已有的加载方式可参照（`cis2hdl/config/` 下 yaml 由 matcher 读取）；RoutingConfig 用 `dataclasses.replace` 逐字段覆盖，保持不可变默认值。

## E.2 基类-注册模式（WireRouterBase + ROUTER_REGISTRY）

```python
# cis2hdl/core/writer/router_base.py （新模块）
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .wire_layout import RoutedNet

ROUTER_REGISTRY: dict[str, type["WireRouterBase"]] = {}

def register_router(name: str):
    def deco(cls: type["WireRouterBase"]) -> type["WireRouterBase"]:
        ROUTER_REGISTRY[name] = cls
        return cls
    return deco

def create_router(mode: str, cfg) -> "WireRouterBase":
    """工厂：按配置选路由器；未知 mode → warning + 回退 p0_lane。"""
    cls = ROUTER_REGISTRY.get(mode)
    if cls is None:
        logger.warning("unknown routing mode %r → fallback p0_lane", mode)
        cls = ROUTER_REGISTRY["p0_lane"]
    return cls(cfg)

class WireRouterBase(ABC):
    """布线器抽象：路由页面网 → WIRE 段。所有实现必须保证端点=引脚坐标（硬约束）。"""
    def __init__(self, cfg: "RoutingConfig | None" = None) -> None:
        self.cfg = cfg

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def route_nets(self, net_pin_map: dict[str, list],
                   body_outlines: list[tuple[int, int, int, int]],
                   **ctx) -> dict[str, "RoutedNet"]:
        """与 WireLayoutEngine.route_nets 同签名（兼容既有调用）。"""
        ...

    def compute_dots(self, wires) -> list[tuple[int, int]]:
        """DOT 计算是纯几何、与策略无关 —— 基类提供（复用 wire_layout 实现）。"""
        ...

    # 统一异常策略：Engine 调用处 catch → logger.warning → 回退 p0_lane
```

```python
# cis2hdl/core/writer/wire_layout.py — 改造：WireLayoutEngine 注册为 p0_lane 路由器
@register_router("p0_lane")
class WireLayoutEngine(WireRouterBase):
    # 现有 route_nets/_find_lane/_avoid_outlines/_route_* 全部保留，仅加 name 属性
    # 类行为零变化 → 现有单测不动
```

```python
# cis2hdl/core/writer/detour_router.py （新模块，P1a 正交绕障）
@register_router("detour")
class DetourRouter(WireLayoutEngine):
    """继承 P0 车道法，追加 stub 正交绕障。"""
    def route_nets(self, net_pin_map, body_outlines, **ctx):
        results = super().route_nets(net_pin_map, body_outlines)
        for routed in results.values():
            routed.wires = [self._stub_with_detour(w, body_outlines) for w in routed.wires]
            routed.dots = self.compute_dots(routed.wires)
        return results

    @staticmethod
    def _stub_with_detour(seg: "WireSegment",
                          outlines: list[tuple[int, int, int, int]]) -> list["WireSegment"]:
        # stub = 一端在引脚、另一端在 trunk 的单段线；若与 outline 相交 →
        # 拆成 L/Z 三/四段（detour 坐标 = outline 外最近 50 倍数，天然 25 网格）
        # 实现见 phaseXIII §6.1 伪代码；直连（绝大多数）原样返回
        ...
```

```python
# cis2hdl/core/writer/edif_wire_reuse.py （新模块，P1b EDIF 折线复用）
@register_router("edif_reuse")
class EDIFWireRouter(WireRouterBase):
    """消费 NetIR.wires（2516 段/6773 点已解析）→ 折线映射 + 端点重定。"""
    def __init__(self, cfg=None, coord_xform: "CoordTransform | None" = None,
                 design: "DesignIR | None" = None) -> None: ...
    def route_nets(self, net_pin_map, body_outlines, **ctx):
        # 1. 按 page_id 聚合设计.wires → 本页折线
        # 2. CoordTransform 变换（复用 map_point / source_bbox）
        # 3. 端点重定：折线首/尾点吸附到该网实际引脚坐标（net_pin_map 查）
        # 4. 中间点 _snap25 → WireSegment 序列
        # 5. 无折线的网 → 降级 super().route_nets（保留 P0 语义）
        ...
```

- **为什么用"继承 + 注册"而非纯组合**：DetourRouter 复用车道/避让逻辑（继承），EDIFWireRouter 复用 DOT 计算（基类）——符合 Part I "基类-注册模式"且实现量最小。
- **回退策略**：`ConversionEngine._stage_generate` 中
  ```python
  try:
      router = create_router(cfg.routing.mode, cfg.routing)
      routed = router.route_nets(net_pin_map, body_outlines, design=design, page=page_conn)
  except Exception as exc:
      logger.warning("router %s failed (%s) → fallback p0_lane", cfg.routing.mode, exc)
      routed = ROUTER_REGISTRY["p0_lane"](cfg.routing).route_nets(net_pin_map, body_outlines)
  ```

## E.3 CLI 参数映射（__main__.py convert 分支扩展）

```
cis2hdl convert <input> [--output <dir>] [--hdl-lib <dir>]
    [--routing p0|detour|edif_reuse]
    [--manual-matches <file.yaml>]
    [--export-unmatched <out.yaml>]
    [--extra-hdl-lib <dir>]          # D4 方案 B 挂载额外库
    [--text-layout]                  # D1 快捷开关
    [--aesthetic]                    # D1+D2+D4+报告 总开关
    [--power-ic]                     # D4 独立开关
    [--benchmark] [--max-workers <n>]
```

- 映射逻辑集中在 `__main__.py`：`--routing` → `cfg.routing.mode`；`--manual-matches` → `cfg.routing.manual_matches`；`--aesthetic` → `text_layout.enabled/overlap.check/power_ic.enabled/aesthetic.enabled = True`；`--export-unmatched` → 阶段后写文件。

## E.4 依赖注入（csa_writer 不 import 具体类）

```python
# csa_writer.py 构造签名扩展（向后兼容：默认 None → 工厂创建）
class CSAWriter(WriterBase):
    def __init__(self, component_db=None, hdl_lib_name="hdl_lib", hdl_lib_path=None,
                 router: "WireRouterBase | None" = None,          # 新增
                 text_optimizer: "TextLayoutOptimizer | None" = None,  # 新增
                 aesthetic_report: "AestheticReport | None" = None) -> None: ...

    def _build_csa_content_conn(self, conn, page_conn):
        # 原 L1012-1017：
        #   from .wire_layout import WireLayoutEngine   ← 删除（防循环依赖）
        #   engine = WireLayoutEngine()
        # 改为：
        #   engine = self._router or create_router(cfg.routing.mode, cfg.routing)
        #   routed_nets = engine.route_nets(net_pin_map, body_outlines,
        #                                   design=conn.design, page=page_conn)
        ...
        # 标签输出（VALUE/$LOCATION/SIG_NAME@wire）：
        #   if cfg.routing.text_layout.enabled:
        #       result = self._text_optimizer.optimize(page_conn, body_coords,
        #                                              pin_coords, routed_nets)
        #       label_offsets = result.offsets   # 仅影响 DISPLAY/标签坐标
```

- **防循环依赖**：csa_writer 只依赖 `router_base.create_router`（抽象层），不 import `detour_router/edif_wire_reuse/wire_layout` 具体类；`text_layout` 与 `wire_layout` 互不依赖（TextLayoutOptimizer 只消费 RoutedNet 数据）。
- **注册时机**：`router_base.py` 顶部 import 三个具体模块完成注册（或沿用 `_bootstrap_writers()` 模式——conversion_engine L247 已有 bootstrapping 先例）。

## E.5 测试影响

- 新增 `tests/unit/test_router_registry.py`：①registry 含 p0_lane/detour/edif_reuse；②未知 mode → 回退 p0_lane；③DetourRouter stub 绕障（stub 穿 outline → 拆段、0 off-grid、端点不变）；④EDIFWireRouter 折线映射（构造 2 页 fixture：端点重定到引脚、0 off-grid、无折线网降级 P0）。
- 新增 `tests/unit/test_routing_config.py`：routing.yaml 加载/覆盖/默认值。
- 回归：mode 默认 p0、全部开关默认关 → 现有 433 测试路径完全不变。
- 跨页网视觉优化（`cross_page_opt`）：开关默认关；开时启用 IOPORT 边缘对齐 + 跨页 trunk 延伸（Phase XIII 已实现 IOPORT 入网，本开关只叠加对齐美化）——新增 `tests/unit/test_cross_page_opt.py`（IOPORT y 等间距、x 边缘统一）。

---

# Part F：实现顺序（T1-T6，按依赖）

```
T1  基础设施：routing.yaml + RoutingConfig.load_from_file + WireRouterBase/ROUTER_REGISTRY/
    create_router + CSAWriter 依赖注入改造 + CLI 参数映射        （D5 骨架，一切的地基）
    └ 产出：router_base.py / routing.yaml / config.py 扩展 / __main__.py 扩展
    └ 验收：registry 单测绿；mode=p0 时 433 全绿（零行为变化）
    ↓
T2  D1 文本/标签去冲突+对齐：text_layout.py + TextLayoutOptimizer + aesthetic_report 收集器
    └ 依赖 T1（配置开关 + 注入点）
    └ 验收：test_text_layout 绿；开启后标签 25 网格、PIN_TEXT 不动、报告输出
    ↓
T3  D2 元件重叠检测：overlap_detector.py + aesthetic_report 写入
    └ 依赖 T1（报告收集器）
    └ 验收：test_overlap_detector 绿；默认关零影响
    ↓
T4  D3 人工匹配→自动配线：manual_matches.py + apply_manual_matches 注入 _stage_match +
    MatchStrategy.MANUAL + --manual-matches/--export-unmatched
    └ 依赖 T1（CLI/配置）；可与 T2/T3 并行
    └ 验收：test_manual_matches 绿；合成 fixture 输出 dc_dc 正确引脚/连线
    ↓
T5  D4 电源芯片匹配：power_ic.yaml + 候选评分器 + --extra-hdl-lib 挂载 + 拷贝 practice 符号到 fixtures
    └ 依赖 T4（candidates 进 export-unmatched；可并行）
    └ 验收：test_power_ic_match/test_extra_hdl_lib 绿；工程师按 §D.3 实测回填配置
    ↓
T6  P1 布线器落地：detour_router.py（正交绕障）+ edif_wire_reuse.py（折线复用）
    └ 依赖 T1（注册/注入）；与 T2-T5 互不阻塞
    └ 验收：test_router_registry 扩展绿；--routing=detour / --routing=edif_reuse 在 HG5015 转换抽查 3 页
```

依赖图：`T1 → T2/T3/T4`（T1 是唯一公共依赖）；`T4 → T5`（候选共用）；`T1 → T6`；T2/T3 相互独立。**尽量并行**：T2、T3、T6 只要 T1 完成即可开工；T4、T5 同理。

---

# Part G：Anything UNCLEAR / 假设

1. **标签 bbox 估算精度**：DEHDL 渲染文本实际宽度依赖 Cadence 字体度量，本地无法精确获得。采用保守估算（CHAR_WIDTH_FACTOR=0.65 + PADDING=12）——宁可多留空隙。若 Cadence 实测仍重叠/过疏，仅需调 `power_ic`/`text_layout` 两个系数，无需改结构。
2. **差分对标签 `_P/_N` 后缀假设**：若 HG5015 网名无 `_P/_N` 后缀（实测部分网名是 VDD_XXX），则 `diff_pair_pn` 静默跳过；需工程师在 §D.3 实测时确认网名模式，必要时扩展差分对识别规则（如 `diff_` 前缀）。
3. **D4 候选表是推断初稿**：`candidates_by_pin_count` 基于 practice 符号引脚结构推断，**真实 U 元件引脚名待工程师实测回填**（§D.3 步骤 1-5）；未回填前 `power_ic.enabled` 保持 false。
4. **EDIF 折线复用（P1b）的布局一致性风险**：折线是针对 CIS 原图布局的；若坐标变换后元件位置差异大，中间段可能穿错区域（端点重定只保端点）。T6 验收需 Cadence 抽查 3 页对比（phaseXIII §4.2 已列此风险）；开关默认关。
5. **cross_page_opt（跨页网视觉优化）**：Phase XIII 已实现"跨页网接入 IOPORT 的 WIRE"；本 Phase 开关只叠加 IOPORT 对齐/美化，不涉及电气改动。
6. **A\* 迷宫布线**：按用户确认"远期仅记录"——本设计只保留 `routing.mode` 预留位（未来 `auto`），不实现。

---

## 附：关键文件清单（新增/修改）

| 文件 | 动作 | 归属 |
|------|------|------|
| `cis2hdl/config/routing.yaml` | 新增 | T1 |
| `cis2hdl/config/power_ic.yaml` | 新增 | T5 |
| `cis2hdl/core/config.py` | 修改（RoutingConfig + load_from_file 落地） | T1 |
| `cis2hdl/core/writer/router_base.py` | 新增（ABC + registry + create_router） | T1 |
| `cis2hdl/core/writer/wire_layout.py` | 修改（注册为 p0_lane，行为零变化） | T1 |
| `cis2hdl/core/writer/detour_router.py` | 新增（P1a 正交绕障） | T6 |
| `cis2hdl/core/writer/edif_wire_reuse.py` | 新增（P1b 折线复用） | T6 |
| `cis2hdl/core/writer/text_layout.py` | 新增（D1） | T2 |
| `cis2hdl/core/writer/overlap_detector.py` | 新增（D2） | T3 |
| `cis2hdl/core/writer/aesthetic_report.py` | 新增（报告收集器） | T2/T3 |
| `cis2hdl/core/writer/csa_writer.py` | 修改（依赖注入 router/optimizer/report；标签行按 offsets） | T1/T2 |
| `cis2hdl/core/matching/manual_matches.py` | 新增（D3） | T4 |
| `cis2hdl/core/matching/power_ic_scorer.py` | 新增（D4 评分器） | T5 |
| `cis2hdl/core/engine/conversion_engine.py` | 修改（注入点 + --extra-hdl-lib + 回退） | T1/T4/T5 |
| `cis2hdl/__main__.py` | 修改（CLI 参数映射） | T1 |
| `tests/fixtures/hdl_lib/{dc_dc,ldo,power_dip4}` | 新增（从 practice 拷贝，方案 A） | T5 |
| `tests/unit/test_{text_layout,overlap_detector,manual_matches,power_ic_match,router_registry,routing_config,cross_page_opt,extra_hdl_lib}.py` | 新增 | 对应任务 |
