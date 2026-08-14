# CIS2HDL Phase XVI — 镜像归一化（mirror normalization）+ IOPORT 一致性核对（架构师交付）

> 架构师：高见远（software-architect）
> 范围：T1 镜像归一化（方案 A：引脚坐标镜像变换 + 等效 R 行近似 + 报告标注）/ T2 IOPORT 一致性核对（三节审计 + 报告 + 修复建议 + 配置开关）
> 基线：Phase XV 交付（519 passed / 5 skipped）
> 主测试：HG5015-BE36_V10（24 页 / 3023 实例 / 522 页级 off_page / 243 唯一跨页网名）
> 参考：`docs/archive/temp files/system_design0811-phase14.md`（风格）、`tests/fixtures/HG5015test/HG5015-BE36_V10.EDF`（实测数据）
> 性质：**只读设计** —— 不改任何源码；全部结论基于源码行号 + EDIF 标准语义 + HG5015/04p4/8367 实测。

---

## 0. 结论速览（TL;DR）

| # | 需求 | 方案一句话 | 默认开关 | 电气风险 | 实现量 |
|---|------|-----------|:-------:|:-------:|:-----:|
| T1a | EDIF mirror 语义确认 | EDIF 2.0.0 八方向常量由**镜像在前、旋转在后**复合（MYR90=MY 后 R90）；MY=左右翻转（x→-x）、MX=上下翻转（y→-y）；现有 `rotate_point` 注释的复合顺序**与标准相反**（但从未在 writer 路径被使用，无存量影响） | — | — | 纯确认 |
| T1b | 镜像归一化（用户 Cadence 实测 L20 等"翻转 180°"） | **方案 A**：引脚坐标做**精确 EDIF 镜像变换**（电气硬约束：LASTPIN/WIRE 端点重合），渲染方向用**数据驱动的最接近等效旋转**近似（`closest_rotation_for_mirror`），镜像清单进 `aesthetic_report` 并标注"方向近似需人工复核"；**不输出 M 行**（04p4/8367 无 mirror 语法可对照） | `mirror.normalize=true`（正确性修复，默认开） | **无**（端点重合硬约束不变；仅 217 实例坐标变化） | 120-180 行 |
| T1c | 镜像后引脚名左右列互换 | **坐标变换自动完成**：`$PN`/`SIG_NAME` 标签锚点 = 引脚坐标，引脚坐标镜像后标签随引脚移动，左列→右列天然互换；无需额外代码 | 随 T1b | 无 | 0 行（仅文档说明） |
| T2a | IOPORT 接线核对 | 新模块 `ioport_audit.py`：每页每 IOPORT 验证其引脚坐标 ∈ 所属网 WIRE 端点；**网仅含 IOPORT 引脚（本页无元件引脚）时按"网名连接"豁免**（跨页网本页常只有连接器，无 WIRE 是正常） | `ioport.audit=false`（默认关） | 无 | 200-260 行 |
| T2b | 网名跨页一致性 | 全工程 SIG_NAME/off_page 网名做 canonical 归一化（去下划线+小写）分组；输出"疑似同一网不同名"清单；**只报告不合并**（跨页改名有电气风险） | 同上 | 无 | 随 T2a |
| T2c | 孤立 connector | IOPORT 网名在全工程任何页元件引脚 SIG_NAME 均不出现 → 标记孤立；**审计必须基于 DesignConnectivity 模型**（raw PageIR 的 pin_connections 未注入时会误报全部 243 个孤立——已实测验证该坑） | 同上 | 无 | 随 T2a |
| T2d | 修复建议 | 接线缺失→布线层修复；孤立→`ioport.skip_orphan=true` 时不生成该 IOPORT（默认只报告）；网名不一→`ioport.manual_names` 人工映射覆盖（默认空=不合并） | `skip_orphan=false`、`manual_names={}` | 无（默认只报告） | 60-100 行 |

**四条铁律（延续 Phase XIV）**：
1. **连接判定 = 坐标重合**：WIRE 端点必须精确等于 LASTPIN 坐标——镜像归一化只改"引脚坐标源头"，LASTPIN/WIRE 同源重算，重合不变。
2. **全坐标 25 网格**：镜像变换后坐标仍须 `_snap25`（`_unique_pin_coord` 已兜底）。
3. **新功能独立模块 + 配置开关，可回退**：`mirror.normalize` / `ioport.audit` 均独立开关；`--no-mirror-normalize` 逃生舱回退 Phase XIII 行为。
4. **只报告不自动合并**：网名一致性/孤立 connector 默认仅报告，修复需显式开关或人工映射（电气风险）。

**决策记录（方案选择）**：
- **方案 A（推荐，本轮落地）**：引脚坐标精确镜像 + 等效旋转近似渲染。理由：①电气硬约束（连接）100% 保证；②对竖直双引脚无源件（L20 类主体）镜像与旋转**精确等价**（MX≡R180、MY≡R0、MYR90≡R90、MXR90≡R270），渲染零误差；③不赌 M 行语法。
- **方案 B（不落地，记录）**：尝试输出 M 行。04p4/8367 参考工程 16+ 页 CSA **无任何 mirror 行**（已 grep 验证），无语法可对照，需用户 Cadence 逐条验证——风险高，留作远期。
- **方案 C（不落地，记录）**：镜像元件不修正方向仅报告——不满足用户"翻转 180°"修复诉求。

---

# Part A：任务 1 — 镜像归一化（mirror normalization）

## A.0 现状与根因（证据）

- **EDIF 解析**（`edif_parser.py` L905-923）：`(orientation R90/R180/R270)` → `rotation`；`MY*` → `mirror=2`（x→-x）、`MX*` → `mirror=1`（y→-y）；`MYR90/MXR90` 解析为 `rotation=90` + 对应 mirror。
- **writer 保守策略**（`csa_writer.py` L1545-1548 注释 + L1956-1959 注释，Phase XIII T2）：mirror≠0 实例 **只按 rotation 旋转、不输出 M 行、引脚不镜像** → Cadence 按未镜像渲染 → 与原图方向相反 → 用户实测"翻转 180°"（L20）。
- **实测分布**（HG5015-BE36_V10.EDF，本设计实测）：`MX×89、MY×77、MYR90×37、MXR90×14` = **217 镜像实例**，分布在 **17 页**（07-SOC_PWR1×44、20-WIFI5G_FEM_C1×35、21-4GE×34、19-WIFI5G_FEM_C0×33…）；含普通元件（DDR_DQS0_N 等差分 stub、INSxxxx 无源件）与电源符号（GND）。旋转-only 另计 R90×267 / R180×356 / R270×109。
- **参考工程**：04p4（16 页 csa）/ 8367 全部 csa **均无 `^M n`/MY/MX 行**（已 grep 验证）→ M 行语法无对照，方案 A 的"不依赖 M 行"前提成立。
- **现有 rotate_point 复合顺序注释错误**（`coord_transform.py` L313-318 注释"mirror applied after rotation (EDIF orientation order)"）：EDIF 标准实际为**镜像在前、旋转在后**。由于 writer 从 Phase XIII 起从不传 mirror（`csa_writer.py` L1594 只传 `rot_dehdl`），该错误从未被触发；`test_phase_xi_p1.py::test_rotate_point_mirror` 只测 rotation=0，不受影响。本设计一并修正。

## A.1 EDIF 2.0.0 orientation 语义确认（标准 + 实证）

EDIF 2.0.0 定义 8 个 orientation 常量：**绕原点逆时针旋转**或**对两轴之一镜像**，八个常量对应坐标映射如下（引自 EDIF 2.0.0 标准条文，中文论文引述 + 赛题文档交叉验证：`MXR90 等同于 MX+R90`、`MYR90 等同于 MY+R90`）：

| orientation | 映射 (x,y) → | 说明 | det |
|---|---|---|---|
| R0 | (x, y) | 无变换 | +1 |
| R90 | (-y, x) | 逆时针 90° | +1 |
| R180 | (-x, -y) | 180° | +1 |
| R270 | (y, -x) | 逆时针 270° | +1 |
| MX | (x, -y) | 关于 X 轴镜像（上下翻转，y→-y） | **-1** |
| MY | (-x, y) | 关于 Y 轴镜像（左右翻转，x→-x） | **-1** |
| MYR90 | (-y, -x) | **先 MY（x→-x），再 R90（CCW）** | **-1** |
| MXR90 | (y, x) | **先 MX（y→-y），再 R90（CCW）** | **-1** |

要点：
1. **复合顺序 = 镜像在前、旋转在后**（MYR90 = MY∘R90 的几何 = 关于直线 y=-x 反射；MXR90 = 关于直线 y=x 反射）。OrCAD Capture 导出遵循该标准。
2. **镜像反转 chirality（det=-1）**，严格无法用纯旋转表达 → 方案 A 的"方向近似"取舍依据。
3. OrCAD 惯例核对：Capture "Mirror Horizontally" = 左右翻转 = EDIF MY（x→-x）；"Mirror Vertically" = 上下翻转 = EDIF MX（y→-y）。与 `edif_parser.py` 现有映射（MY→2→x→-x、MX→1→y→-y）一致 ✓。

## A.2 镜像几何变换矩阵（各 orientation，绕元件中心 = css 引脚偏移空间）

以列向量 [x; y]，变换矩阵：

| orientation | 矩阵 M | 说明 |
|---|---|---|
| MX | `[[1,0],[0,-1]]` | 上下翻转 |
| MY | `[[-1,0],[0,1]]` | 左右翻转 |
| MYR90 | `[[0,-1],[-1,0]]` | y=-x 反射 |
| MXR90 | `[[0,1],[1,0]]` | y=x 反射 |

**实现**（`coord_transform.py`，修正 `rotate_point` 复合顺序为镜像在前 + 新增表驱动入口）：

```python
def rotate_point(x: float, y: float, rotation: int = 0, mirror: int = 0) -> tuple[int, int]:
    """旋转(CCW, EDIF 角度) + 镜像（EDIF 2.0.0：镜像在前、旋转在后）。
    mirror: 1=MX(flip Y), 2=MY(flip X)。
    例: MYR90(rotation=90,mirror=2): (x,y)->(-x,y)->(-y,-x)  ==  EDIF MYR90 ✓
    """
    rx, ry = float(x), float(y)
    if mirror == 1:      # MX：先镜像（flip Y）
        ry = -ry
    elif mirror == 2:    # MY：先镜像（flip X）
        rx = -rx
    rot = int(rotation or 0) % 360
    if rot == 90:
        rx, ry = -ry, rx
    elif rot == 180:
        rx, ry = -rx, -ry
    elif rot == 270:
        rx, ry = ry, -rx
    return int(round(rx)), int(round(ry))

def apply_edif_orientation(x, y, rotation=0, mirror=0):
    """表驱动别名：== rotate_point（镜像在前、旋转在后）。writer 唯一入口。"""
    return rotate_point(x, y, rotation, mirror)
```

兼容性：现有 `rotate_point(10,20,0,1)==(10,-20)`、`(10,20,0,2)==(-10,20)`、`(0,-75,90)==(75,0)` 等测试全部仍成立（rotation=0 时顺序无关；纯旋转不变）。

## A.3 等效 R 行映射（方案 A：数据驱动"最接近旋转"）

DEHDL R 行只能旋转（0/90/180/270），不能镜像。选择使**渲染符号引脚位置**与**镜像真值引脚位置**总平方位移最小的旋转 θ*：

```python
def closest_rotation_for_mirror(pin_offsets: list[tuple[int, int]],
                                rotation: int, mirror: int) -> int:
    """返回 EDIF 角度 θ*∈{0,90,180,270}，使 Σ|M(p) − Rθ(p)|² 最小。
    M(p) = rotate_point(p, rotation, mirror)  # 镜像真值（电气硬约束）
    Rθ(p) = rotate_point(p, theta)            # 纯旋转候选
    """
    if not pin_offsets or len(pin_offsets) < 2:
        return int(rotation or 0)             # 退化（单引脚/无引脚）→ 仅旋转部分
    best_t, best_err = 0, None
    for theta in (0, 90, 180, 270):
        err = sum(
            (mx - rx) ** 2 + (my - ry) ** 2
            for (px, py) in pin_offsets
            for (mx, my) in [rotate_point(px, py, rotation, mirror)]
            for (rx, ry) in [rotate_point(px, py, theta)]
        )
        if best_err is None or err < best_err:
            best_t, best_err = theta, err
    return best_t
```

**关键性质（为什么对 L20 类元件完美）**——竖直双引脚无源件（css 偏移 (0,-75)/(0,50) 类）：

| 镜像 orientation | M(引脚) | 等价旋转 θ* | DEHDL R 行 | 误差 |
|---|---|---|---|---|
| MX | (0,75),(0,-50) | 180 | `R 2` | **0（精确）** |
| MY | (0,-75),(0,50) | 0 | 无 | **0（精确）** |
| MYR90 | (75,0),(-50,0) | 90 | `R 3`（经 _dehdl_rotation） | **0（精确）** |
| MXR90 | (-75,0),(50,0) | 270 | `R 1` | **0（精确）** |

对左右列 IC（引脚 (±dx, y) 对称分布），θ* 由数据决定（Σx² 与 Σy² 竞争），同一 cell+orientation 结果确定（css 偏移一致 → 输出一致），非精确但误差有界；报告中标注"方向近似"。

> 为什么 θ* 在 **EDIF 角度空间**求、R 行用 `_dehdl_rotation(θ*)` 转 DEHDL 角：Phase XV 已实测 DEHDL R 行与 EDIF 旋转角符号相反（90↔270 互换），渲染"呈现为" EDIF 旋转 θ*；求最小位移须在同一角度空间比较，故求 θ* 用 EDIF 空间、输出 R 行转 DEHDL 空间。

## A.4 引脚左右列互换规则

**无需额外代码**：DEHDL 的 `FORCEPROP 2 LASTPIN (x y) $PN n` 与 `_sig_name_at_pin`（标签锚点 = 引脚坐标 + 固定偏移）都以 `pin_coords` 为源；镜像变换改 `pin_coords` 后，`$PN`/`SIG_NAME` 标签随引脚移动 → IC 左列引脚镜像后自然显示在右侧（左右列互换）。`pin_name_map`（引脚名→网名映射）与电气连接不涉及方向，无需改动。

## A.5 算法伪代码 + 注入点

```python
# ── csa_writer._compute_pin_geometry（Pass 1，现 L1541-1595）──
mirror = int(getattr(irec, "mirror", 0) or 0)
rot    = int(getattr(irec, "rotation", 0) or 0)
if not self._routing_cfg.mirror.normalize:
    # Phase XIII 行为原样（镜像忽略，仅旋转部分）
    rot_dehdl = _dehdl_rotation(rot)
    if rot: off = rotate_point(off[0], off[1], rot_dehdl)
elif mirror:
    # Phase XVI：精确 EDIF 镜像变换（镜像在前、旋转在后）
    off = rotate_point(off[0], off[1], rot, mirror)      # 电气硬约束
    self._mirror_rline[irec.refdes] = _dehdl_rotation(
        closest_rotation_for_mirror(offsets_list, rot, mirror))
    self._mirror_entries.append(MirrorEntry(
        page=page_conn.page_name, refdes=irec.refdes,
        orient=f"{'MX' if mirror==1 else 'MY'}{rot or ''}",
        rline=self._mirror_rline[irec.refdes], approx=is_approx))
else:
    rot_dehdl = _dehdl_rotation(rot)                      # 纯旋转不变
    if rot: off = rotate_point(off[0], off[1], rot_dehdl)
# 其余（_unique_pin_coord 25 网格兜底）不动

# ── csa_writer._emit_conn_instance_block（现 L1960-1969）──
_rot = int(getattr(irec, "rotation", 0) or 0)
if self._routing_cfg.mirror.normalize and int(getattr(irec, "mirror", 0) or 0):
    _rot_dehdl = self._mirror_rline.get(irec.refdes, _dehdl_rotation(_rot))  # 镜像用近似 R
else:
    _rot_dehdl = _dehdl_rotation(_rot)                    # 纯旋转不变
# 90→"R 1"、180→"R 2"、270→"R 3"；0→不输出（不变）
```

- **镜像变换发生在 pin_coords 源头**（`_compute_pin_geometry` 的 offset 解析后）→ `pin_coords`、`net_pin_map`、LASTPIN、WIRE、SIG_NAME 全部同源自动一致（连接重合硬约束不变）。
- **R 行状态传递**：Pass 1 计算 `self._mirror_rline[refdes]`，Pass 2 发射时读取（同 `self._page_gnd_symbols` 既有模式）。
- **电源符号**（`_compute_pin_geometry` 电源分支 L1511-1517 + `_emit_power_symbol_block`）：mirror≠0 时对引脚偏移做**仅镜像**（不旋转，保持电源符号现有"不旋转"行为；单引脚、SIG_NAME 连接，电气中性）；不计入 `_mirror_rline`（电源块不发射 R 行）。

## A.6 报告（aesthetic_report.txt 新增 [MIRROR] 节）

`AestheticReport.add_mirror(entry)` 收集、`write()` 输出：

```
[MIRROR] total=217  normalized=217  exact=131  approx=86   (数字为示例，实测为准)
  page=13-DDR3  refdes=DDR_DQS0_N  orient=MX  → R 0    pins_mirrored=1  exact
  page=21-4GE   refdes=INS12345    orient=MY  → R 2    pins_mirrored=1  approx
    note: 方向近似（镜像无法用纯旋转表达），需人工复核
  page=16-WIFI2G refdes=GND        orient=MXR90 → (no R line) pins_mirrored=1 (power symbol)
```

- `exact` = θ* 与镜像映射完全一致（竖直双引脚无源件）；`approx` = 其余（含左右列 IC）。
- 受 `aesthetic.enabled` 门控（与 D2 OVERLAP 同机制）；`mirror.report=false` 可单独关。

## A.7 对现有输出的影响评估

| 范围 | 影响 | 结论 |
|---|---|---|
| 217 镜像实例（17 页） | 引脚坐标按 EDIF 真值镜像 → 该实例 LASTPIN/WIRE/SIG_NAME 坐标变化（**这正是修复目标**） | 预期变化 |
| 旋转-only 732 实例（R90×267/R180×356/R270×109） | **零变化**（mirror=0 分支原样走 `_dehdl_rotation`） | 不破 |
| 04p4 / 8367 参考输出 | 无 mirror 实例（grep 验证无 M 行）→ 不受影响 | 不破 |
| e2e 断言（`test_phase_xi_p0.py` L198-295 `test_a5_wire_endpoints_cover_pins` 等） | 只断言 **LASTPIN ∈ WIRE 端点重合**（不锁绝对坐标）→ 镜像后仍重合 | 不破 |
| 单测 `test_phase_xi_p1.py` `rotate_point`/`rotate_bbox` | rotation=0 镜像测试仍成立；无复合（rotation≠0 且 mirror≠0）断言 | 不破（补新用例） |
| 单测合成 fixture（`test_phase_xv` / `test_cross_page_opt` / `test_phase_xi_p0` 合成页） | 均无 mirror 实例 | 不破 |
| `test_phase_xi_p1.py::test_edif_orientation_captured`（L183-190） | 断言 `len(mirs) > 100`（217>100） | 不破 |
| 需要人工复核 | `--no-mirror-normalize` 关闭后与 Phase XIII 输出一致（逃生舱对照） | QA 抽查 2-3 页 |

---

# Part B：任务 2 — IOPORT 一致性核对

## B.0 现状与缺口

- 现状（已确认）：24 页 IOPORT 总数 **522** = EDIF off_page 页级条目；去重后 **243 唯一跨页网名**（DDR_DQS1_P/25GE_TRXN3_0/wps 等）。522>243 正常：每跨页网在出现的每一页都有 connector（电气正确）。
- Phase XV P1-C 已实现"页内网不生成 IOPORT、跨页网右缘等间距分布"。
- 遗留核对项：①IOPORT 与页内元件引脚接线是否成立（WIRE 接入）②网名跨页一致性（大小写/别名，如 wps vs WPS）③孤立 connector（243 网中是否有网在页内无元件引脚引用）。

## B.1 核对算法（三节检测）

**数据源铁律**：审计必须基于 **DesignConnectivity 模型**（stage 后、pin_connections 已注入）与 **CSAWriter 生成的页级坐标**（pin_coords/net_pin_map/routed_nets）。⚠️ 实测教训：直接对 raw `EDIFParser().parse()` 的 PageIR 实例做孤立检测时，`pin_connections` 未注入 → **243 个 IOPORT 网名全部"查无引脚"**（误报 100%）；必须在连通性模型上核对（该模型由 `_extract_pin_net_map` 注入后构建，`connectivity_model.py` L470 消费 `inst.pin_connections`）。

### B.1.1 接线核对（每页）

```
对每页每个 IOPORT（off_page idx）：
  net_display = _power_net_display(page_conn, net_name)   # 与 Pass1 同源解析
  pins = net_pin_map.get(net_display, [])
  comp_pins = [p for p in pins if not p.refdes.startswith("IOPORT_")]
  if not comp_pins:
      → 本页该网仅有 IOPORT（跨页网本页常只有连接器）→ 豁免（按 SIG_NAME 网名连接）
        （不生成 WIRE 是正常：Phase XIII 起 IOPORT 引脚入网，单引脚网不布线）
  else:
      → 该网有 ≥2 引脚（元件引脚 + IOPORT）→ 必须已布线
      → 断言 ioport_coord ∈ { routed_nets[net_display].wires 全部端点 }
        不满足 → 记 unwired（真实问题：元件引脚已接、IOPORT 未接入）
```

- 豁免规则是**关键**：若机械地要求"每个 IOPORT 都有 WIRE 端点"，跨页网本页仅连接器的场景会全部误报（522 全报）。
- 输入：`audit_page(page_conn, net_pin_map, routed_nets)`——在 `_build_csa_content_conn` 的 `_route_nets` 之后调用（现 L1288-1290 之后）。
- 依赖：`emit_csa_wires=true`（wire 关闭时本节跳过并注明）。

### B.1.2 网名跨页一致性（全局）

```
canonical(name) = re.sub(r"[_\s]+", "", name).replace("\\g", "").lower()
  # 例: "WPS"/"wps"/"W_P_S" → "wps"

收集全工程两个名字集：
  A = {所有 off_page net_name（IOPORT 名）}
  B = {所有页元件引脚 SIG_NAME 网名}（来自 conn 的 NetRecord.display_name / page nets）

检测：
  1) A 内按 canonical 分组 → 组内 distinct raw > 1 → "疑似同一网不同名"（页间拼写差异）
  2) A 的 canonical 与 B 的 canonical 对齐 → 某 IOPORT 的 raw 与同页元件引脚 raw 不同拼写
     （即 _power_net_display 解析出的 net_display 与元件侧不同 key → 该 IOPORT 未入网）
     → 记 "IOPORT 名 vs 页内引脚名不一致"（页级）
  3) 输出清单 + 统计；**不自动合并**（跨页改名有电气风险），供人工裁决
```

### B.1.3 孤立 connector（全局）

```
对每个唯一 IOPORT net_name：
  canonical(n) ∈ canonical(B)（全工程任何页元件引脚 SIG_NAME）？
  否 → 孤立（该网全工程无任何元件引脚引用）
```

- 合法例外：off_page 指向**页内网**（本不应生成 IOPORT，Phase XV P1-C 已修）或 auto-net（UN$/数字开头）的残留 → 标记并建议"不生成该 IOPORT"。
- 实测预估：**大概率 0 或极少**（243 网均为真实跨页网），但审计的价值在防回归（改网名/漏网时立刻暴露）。

## B.2 伪代码 + 报告格式

```python
# cis2hdl/core/writer/ioport_audit.py（新模块）
@dataclass
class UnwiredIoport:    page: str; idx: int; net: str; coord: tuple; pins_on_page: int
@dataclass
class NameConflict:     page: str; ioport_name: str; pin_net_names: list[str]; canonical: str
@dataclass
class OrphanIoport:     page: str; net: str; canonical: str; reason: str

class IOPortAuditor:
    def __init__(self, enabled=True, skip_orphan=False,
                 manual_names: dict[str, str] | None = None): ...
    def audit_page(self, page_conn, net_pin_map, routed_nets) -> None:   # 接线核对 + 收集 A/B
    def finalize(self, conn) -> None:                                     # 网名一致性 + 孤立
    def write(self, output_dir: Path) -> Path | None:                     # ioport_audit_report.txt
```

```
=== IOPORT Audit Report: HG5015-BE36_V10 ===
[SUMMARY] pages=24  ioport_total=522  unique_nets=243
          unwired=0  name_conflicts=0  orphan=0  exempt_name_only=NN
[UNWIRED] total=0
  (none)                          # 格式: page / net / coord / 页内引脚数
[NAME_CONFLICT] total=0           # 疑似同一网不同名 —— 人工裁决，不自动合并
  page=13  ioport="WPS"  page-pins=["wps"]  canonical="wps"
[ORPHAN] total=0                  # IOPORT 网名全工程无元件引脚引用
  page=15  net="UN$2$CAPACITOR$I7$1"  reason=auto-net 建议=不生成该 IOPORT
[FIX_SUGGESTION]
  unwired: 布线层修复（网名一致则 WIRE 必达；若否检查 net_pin_map 归属）
  orphan:  config ioport.skip_orphan=true → 不生成该 IOPORT
  name_conflict: config ioport.manual_names={"WPS":"wps"} → 解析时覆盖
```

## B.3 修复建议（分层）

| 问题 | 修复层 | 默认动作 | 风险 |
|---|---|---|---|
| 接线缺失（元件引脚已接、IOPORT 未达） | 布线层：检查该网 net_pin_map 归属/网名解析（多为网名不一致导致） | 报告 | — |
| 孤立 connector | 生成层：`ioport.skip_orphan=true` 时 `_emit_ioport_block` 与 Pass1 入网均跳过 | 报告 | 低（网无引脚引用，跳过不影响连接） |
| 网名跨页不一致（wps vs WPS） | 解析层：`ioport.manual_names={"raw":"canonical"}` 在 `_power_net_display`/net 解析处覆盖 | **只报告** | 自动合并有电气风险，默认禁止 |

## B.4 配置开关 + 依赖注入（见 Part C 汇总）

---

# Part C：配置开关 + 依赖注入汇总

## C.1 routing.yaml 新增段（cis2hdl/config/routing.yaml）

```yaml
# Phase XVI
mirror:
  normalize: true        # T1 总开关（正确性修复，默认开）；CLI --no-mirror-normalize 关闭
  report: true           # 镜像清单进 aesthetic_report（受 aesthetic.enabled 门控）
ioport:
  audit: false           # T2 核对开关（默认关）；CLI --ioport-audit / --aesthetic 开启
  skip_orphan: false     # 孤立 connector 是否不生成（默认只报告）
  manual_names: {}       # 人工网名覆盖 {raw_name: canonical_target}（默认空=不合并）
```

## C.2 dataclass（cis2hdl/core/config.py）

```python
@dataclass
class MirrorCfg:
    normalize: bool = True
    report: bool = True

# IoportCfg 追加字段（现有类扩展，默认值向后兼容）
@dataclass
class IoportCfg:
    edge_layout: bool = False
    edge_x: int = -600; edge_step: int = 100; edge_margin: int = 300
    audit: bool = False
    skip_orphan: bool = False
    manual_names: dict[str, str] = field(default_factory=dict)

# RoutingConfig 追加
mirror: MirrorCfg = field(default_factory=MirrorCfg)
# from_dict 增加 mirror / ioport.manual_names 分支（ioport 分支已存在）
```

## C.3 CLI（cis2hdl/__main__.py convert 分支）

```
--ioport-audit      → cfg.routing.ioport.audit = True
--no-mirror-normalize → cfg.routing.mirror.normalize = False
--aesthetic 扩展     → 追加 cfg.routing.ioport.audit = True（用户决策：aesthetic 含审计）
```

## C.4 依赖注入（csa_writer，向后兼容默认 None）

```python
class CSAWriter(WriterBase):
    def __init__(self, component_db=None, hdl_lib_name="hdl_lib", hdl_lib_path=None,
                 router=None, text_optimizer=None, aesthetic_report=None,
                 ioport_auditor: "IOPortAuditor | None" = None,   # 新增
                 routing_cfg=None): ...
    # 内部：
    #   self._ioport_auditor = ioport_auditor or (
    #       IOPortAuditor(enabled=..., skip_orphan=..., manual_names=...)
    #       if routing_cfg.ioport.audit else None)
    # _compute_pin_geometry / _build_csa_content_conn / write_all_with_conn
    #   注入点见 A.5 / B.1.1；write 时 ioport_auditor.write(output_root)
```

- 审计只依赖 `page_conn / net_pin_map / routed_nets / conn`（数据对象），与布线器解耦；`IOPortAuditor` 不 import 具体 writer 类（防循环依赖，沿用 Phase XIV D5 模式）。

---

# Part D：测试影响评估 + 新单测清单

## D.1 现有测试影响（镜像归一化）

| 测试 | 断言 | 影响 | 处置 |
|---|---|---|---|
| `test_phase_xi_p1.py::TestP2Rotation`（L162-181） | rotate_point/rotate_bbox 纯旋转 + rotation=0 镜像 | 修正顺序后全部仍成立 | 不破 |
| `test_phase_xi_p1.py::test_edif_orientation_captured`（L183-190） | `len(mirs)>100`（217） | 不变 | 不破 |
| `test_phase_xi_p0.py`（unit）L148/L302 等合成坐标断言 | 合成 fixture 无 mirror | 不变 | 不破 |
| e2e `test_a5_wire_endpoints_cover_pins` / `test_one_sig_name_per_net` | LASTPIN ∈ WIRE 端点（重合） | 镜像后同源重算仍重合 | 不破 |
| e2e `test_rtl8367rb_full` / `test_v2c_regression`（8367） | 8367 无 mirror 实例 | 不变 | 不破 |
| `test_phase_xv.py::TestP0ERotation`（L106-140） | `_dehdl_rotation` 90↔270 映射 | 纯旋转分支不变 | 不破 |
| `test_routing_config.py` | RoutingConfig 默认字段 | 新增字段有默认值，旧断言不涉及 | 不破（补用例） |

## D.2 现有测试影响（IOPORT 核对）

- `ioport.audit=false` 默认 → 全部现有 IOPORT 行为零变化；`IOPortAuditor` 默认不实例化。
- `test_phase_xv.py::TestIoportEdge` / `test_cross_page_opt.py`：开关默认关 → 不破。
- `test_phase_xv.py::test_page_internal_net_no_ioport`（L343-353）：页内网无 IOPORT 的既有逻辑不变。

## D.3 新单测清单

| 测试文件 | 用例 |
|---|---|
| `tests/unit/test_orientation_geometry.py`（新） | ①8 方向映射表逐项断言（R0/R90/R180/R270/MX/MY/MYR90/MXR90 对 (10,20)）；②MYR90=(−20,−10)、MXR90=(20,10)（修正复合顺序后的关键断言）；③rotate_bbox 镜像一致性；④`closest_rotation_for_mirror`：竖直双引脚 MX→180/MY→0/MYR90→90/MXR90→270（exact）；左右列 IC 数据集 → 确定性 θ*；单引脚 → 返回 rotation 部分 |
| `tests/unit/test_mirror_normalize.py`（新） | ①合成页含 MX 双引脚无源件 → CSA 引脚坐标 = css 偏移镜像、R 行 = `R 2`、WIRE 端点重合；②MYR90 合成 IC → 坐标 = (−y,−x) 真值 + R 行近似、`aesthetic_report` [MIRROR] 记录 approx 标注；③`mirror.normalize=false` → 输出与 Phase XIII 完全一致（回归开关）；④电源符号镜像：GND 引脚偏移仅镜像、无 R 行 |
| `tests/unit/test_ioport_audit.py`（新） | ①三页合成：网 A 跨页（本页仅 IOPORT → 豁免不报）；网 B 跨页（本页 1 元件引脚 + 1 IOPORT 且 WIRE 接入 → 通过）；网 C 元件引脚已接但 IOPORT 坐标非端点 → unwired；②网名一致性：`WPS` vs `wps` 同 canonical → name_conflicts=1 且不自动合并；③孤立：IOPORT 网名全工程无引脚 → orphan=1；`skip_orphan=true` 后该 IOPORT 不生成；④`manual_names={"WPS":"wps"}` 覆盖后接线通过；⑤报告文件格式三节+统计 |
| `tests/e2e/test_phase_xvi.py`（新） | ①真实 HG5015 转换（`--aesthetic`）：断言 217 镜像实例全部入 [MIRROR] 清单、exact/approx 计数、LASTPIN∈WIRE 端点重合（含 07-SOC_PWR1/13-DDR3/21-4GE 抽查）；②`--ioport-audit` 输出 ioport_audit_report.txt 且三节可解析；③`--no-mirror-normalize` 输出与旧版逐字节一致（回归锚点） |
| `tests/unit/test_phase_xi_p1.py`（扩展） | rotate_point 复合用例（rotation≠0 且 mirror≠0）补充到 TestP2Rotation |
| `tests/unit/test_routing_config.py`（扩展） | mirror/ioport.audit/skip_orphan/manual_names 加载与默认值 |

---

# Part E：实现顺序（T1-T5，按依赖）

```
T1  基础设施：routing.yaml 增 mirror/ioport 段 + MirrorCfg/IoportCfg 扩展 + CLI
    （--ioport-audit / --no-mirror-normalize / --aesthetic 联动）
    + coord_transform.py：修正 rotate_point 复合顺序 + apply_edif_orientation
    + closest_rotation_for_mirror 工具 + test_orientation_geometry.py
    └ 产出：routing.yaml / config.py / __main__.py / coord_transform.py / test_orientation_geometry.py
    └ 验收：8 方向映射单测绿；rotate_point 旧用例不破；默认配置 519 全绿
    ↓
T2  镜像归一化落地：csa_writer 引脚镜像 + R 行映射 + 电源符号仅镜像 + _mirror_rline 状态
    + aesthetic_report [MIRROR] 节 + test_mirror_normalize.py + test_phase_xi_p1.py 扩展
    └ 依赖 T1（几何工具 + 开关）
    └ 验收：合成镜像页单测绿；HG5015 217 实例坐标镜像且端点重合；--no-mirror-normalize 等价旧版
    ↓
T3  IOPORT 核对模块：ioport_audit.py（三节检测 + 报告）+ CSAWriter 注入（audit_page/finalize/write）
    + IoportCfg 字段 + test_ioport_audit.py
    └ 依赖 T1（开关/注入）；与 T2 并行
    └ 验收：三节单测绿；真实 HG5015 --ioport-audit 报告可解析且无崩溃
    ↓
T4  修复建议落地：ioport.skip_orphan 跳过生成 + manual_names 覆盖 + --aesthetic 联动审计
    └ 依赖 T3
    └ 验收：skip_orphan/manual_names 单测绿；默认（只报告）行为零变化
    ↓
T5  集成 + e2e 回归：test_phase_xvi.py（真实工程 3 项 e2e）+ 全量回归
    （04p4/8367 无镜像确认已 grep；QA 在 Cadence 抽查 13-DDR3/21-4GE/07-SOC_PWR1）
    └ 依赖 T2/T3/T4
    └ 验收：e2e 绿；519 全量回归绿（新增测试另计）；aesthetic_report 含 [MIRROR] 217 条
```

依赖图：`T1 → T2/T3`（T1 唯一公共依赖）；`T3 → T4`；`T2+T4 → T5`。**T2 与 T3 并行**（互不阻塞）。

---

# Part F：Anything UNCLEAR / 假设

1. **R 行近似的主观性**：镜像无法用纯旋转表达，"最接近旋转"用引脚总平方位移最小定义——这是几何上最客观的标准，且对竖直双引脚无源件**精确**。左右列 IC 的近似方向若用户视觉不满意，可调 `closest_rotation_for_mirror` 的距离度量（如改为最大单引脚误差），不影响电气。
2. **电源符号镜像语义**：仅做镜像不做旋转（保持电源符号现"不旋转"行为）。单引脚 + SIG_NAME 连接，电气中性；若用户要求电源符号也精确旋转，需另行评估（会影响 rotation-only 电源符号的现有输出）。
3. **镜像实例的 outline**：`_collect_body_outlines_map` 的避障轮廓当前不随方向变换（旋转-only 也不变换），镜像后引脚偏移与轮廓可能有 ≤100 单位的视觉错位，不影响连接；如需美观化属远期。
4. **IOPORT 审计的"豁免"规则**：本页仅 IOPORT、无元件引脚的跨页网，按"网名连接"豁免（无 WIRE 属正常）。若用户期望这类连接器也画引出短线，属布线美观化需求（Phase XIII 起设计如此）。
5. **孤立 connector 实测数量**：基于 DesignConnectivity 的精确计数待 T3 实现后实测（raw IR 直测会误报 243 全孤立，本设计已规避）。预判接近 0。
6. **manual_names 的 canonical 语义**：覆盖发生在 `_power_net_display`/网名解析层，仅影响 IOPORT 网名 → 页网解析；**不**改动 con/xcon/csv 的全局网名（避免连锁）。
7. **`rotate_point` 顺序修正是行为变更点**：虽无存量调用（writer 从未传 mirror），但语义修正属"潜在 bug 修复"，QA 回归时重点观察 `test_phase_xi_p1.py::TestP2Rotation` 是否全绿。
8. **M 行语法（方案 B）**：留档不排期；若用户后续提供 Cadence 16.6 有效 M 行样例，可升为精确方案（引脚不再需要近似）。

---

## 附：关键文件清单（新增/修改）

| 文件 | 动作 | 归属 |
|------|------|------|
| `cis2hdl/config/routing.yaml` | 修改（mirror / ioport.audit 段） | T1 |
| `cis2hdl/core/config.py` | 修改（MirrorCfg、IoportCfg 扩展、RoutingConfig.mirror） | T1 |
| `cis2hdl/__main__.py` | 修改（--ioport-audit / --no-mirror-normalize / --aesthetic 联动） | T1/T4 |
| `cis2hdl/core/writer/coord_transform.py` | 修改（rotate_point 顺序修正 + apply_edif_orientation + closest_rotation_for_mirror） | T1 |
| `cis2hdl/core/writer/csa_writer.py` | 修改（引脚镜像 + R 行映射 + 电源符号仅镜像 + auditor 注入 + skip_orphan/manual_names） | T2/T3/T4 |
| `cis2hdl/core/writer/aesthetic_report.py` | 修改（add_mirror + [MIRROR] 节） | T2 |
| `cis2hdl/core/writer/ioport_audit.py` | 新增（三节检测 + 报告） | T3 |
| `tests/unit/test_orientation_geometry.py` | 新增 | T1 |
| `tests/unit/test_mirror_normalize.py` | 新增 | T2 |
| `tests/unit/test_ioport_audit.py` | 新增 | T3/T4 |
| `tests/e2e/test_phase_xvi.py` | 新增 | T5 |
| `tests/unit/test_phase_xi_p1.py` | 修改（复合 rotate_point 用例） | T2 |
| `tests/unit/test_routing_config.py` | 修改（新字段用例） | T1 |
| `docs/archive/temp files/class-diagram-phase16.mermaid` | 新增 | T1 |
| `docs/archive/temp files/sequence-diagram-phase16.mermaid` | 新增 | T1 |
