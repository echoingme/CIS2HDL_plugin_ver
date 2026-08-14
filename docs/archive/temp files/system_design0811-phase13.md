# CIS2HDL Phase XIII — Cadence 16.6 实测四问题根因分析与布线优化设计（架构师交付）

> 架构师：高见远（software-architect）
> 范围：Q1 IOPORT 引脚属性被删（SPCOCN-543/541）/ Q2 WIRE 端点与引脚不重合 / Q3 芯片中心电线锚点 / Q4 布线方案分级改进
> 基线：output_phaseXII_final3（Cadence 16.6 用户逐页实测，errors.txt 441 行）
> 性质：**只读分析设计** —— 全部结论基于源码行号 + 生成 CSA + 04p4/8367 参考工程 + EDIF 实测数据交叉验证，不修改任何源码。

---

## 0. 结论速览（TL;DR）

| # | 问题 | 根因（文件/行号/数据） | 修复方向 |
|---|------|------------------------|----------|
| 页面错位（已确认，引用） | 信息页出现芯片 / page11/17/19 空白 | `connectivity_model.py:427/541 page_num = page_idx + 1` 按 EDIF 解析顺序编号；page.map 按页名排序（实测 page2.csa EDIT PAGE NAME=10-SOC_SerDes、page11=02-Block_Diagram、page17=03-Clock_Tree、page19=04-Power_Tree） | page_num 改为 page.map 的页名数字序号（由工程师实现，本报告不再展开） |
| Q1 SPCOCN-543/541 | 大量 `pin property SPN/$PN/SIG_NAME … deleted from the component IOPORT` | **① CSA 结构错误**：所有组件 FORCEADD（L961-966）→ 所有 IOPORT FORCEADD（L974-981）→ **所有 LASTPIN 引脚属性集中到文件尾（L1058-1075）**；Cadence 16.6 把 LASTPIN 绑定到最近 FORCEADD 的元件（最后一个是 IOPORT）→ 属性无处挂靠被删。**② IOPORT LASTPIN 属性级别 3（L1407/1413）≠ 04p4/eeworm 的级别 1**。**③ IOPORT 引脚坐标错**：LASTPIN 用 body+(0,0)，symbol.css 实为 C -50 0；HDL_PORT 标签 (25,-100) 实为 (325,-125) | LASTPIN 移入各自 FORCEADD 块（04p4 结构）；IOPORT LASTPIN 改级别 1；引脚/标签坐标取自 symbol.css；删多余 CDS_LMAN_SYM_OUTLINE |
| Q2 引脚与电线"差一点" | WIRE 端点与渲染引脚不重合 | **① 旋转未写入 CSA**：EDIF 实测 3023 实例中 **783 个 rotation≠0、217 个 mirror≠0**；`csa_writer.py:1018-1043` 用 rotate_point 计算引脚偏移，但 `_emit_conn_instance_block`（L1129-1240）**不输出任何 R/M 行** → Cadence 按未旋转默认视图渲染，引脚实际在未旋转位置 → 差一个旋转位移（如电容 (0,-75) 旋 90°→(75,0)，差 ~106）。**② body 坐标 off-grid**：`coord_transform.py:112-114 int()` 不吸 25 网格 → 实测 page2 WIRE 端点 64% off-grid（49/76）、page12 60%（680/1132）；参考工程 0%。**③ 与 Q3 中心塌缩叠加** | 组件块补 `R 1/2/3` 旋转行（04p4 INPORT `R 2` 实证：LASTPIN 在旋转后位置）；CoordTransform body 吸 25 网格；引脚坐标 = 吸网格 body + css 偏移 |
| Q3 芯片正中央电线锚点 | U6G/U6A/U6B/U5/U19/U6F 等所有引脚塌缩到中心 | **① 未匹配芯片（U6G 等）回退到错误符号 CH347**：EDIF 引脚号 R4/P4/A21… 与 CH347 chips.prt（1..20）不匹配 → `csa_writer.py:1030-1036` 映射失败 → L1038-1040 fallback `.get(pre.pin_name,(0,0))` 全 (0,0)。**② fallback 键错**：`_fallback_pin_offsets`（L1640-1681）字典键是 `str(i)` 数字，调用处按 **pin_name** 查（L1040）→ 对功能名引脚永远 (0,0)，周边分布代码形同虚设 | ① fallback 按 pin_number 查；② 未匹配芯片生成占位 sym / 引脚按序分布四周；③ 长线方案：EDIF 原始 WIRE 折线（P0-A4 已有 NetIR.wires）映射后反推引脚真实落点 |
| Q4 电线杂乱/重合 | 多网共享同一 trunk、未避让元件体、off-grid | **① trunk 汇聚**：`wire_layout.py:141` 每网取中位 y 吸网格 → 实测 page12 **44 条 WIRE 共用 y=4400**；page2 三个网共享 (-8752 5400)→(-2076 5400)（几何短路风险）。**② `csa_writer.py:1086` 未传 body_outlines** → `_avoid_outlines` 形同虚设。**③ 引脚 off-grid → WIRE off-grid → SPCOCN-1329**。**④ 跨页网未连 IOPORT**：page2 无一条 WIRE 到 IOPORT 引脚（04p4 有 `(-4425 -1400)(-3950 -1400)`） | P0：全坐标吸网格 + 传 body_outlines + trunk 车道差异化 + 保留端点重合硬约束；P1：正交绕障、奇偶页横/竖 trunk 交替、IOPORT 接入 WIRE；P2：A* 迷宫布线 |

---

# Part A：Q1-Q4 根因确认（证据链）

## A.0 共享前提：CSA 的 LASTPIN 语义（实证）

- 04p4 `page15.csa` L10-103：`FORCEADD AT88SC0104C..1` 之后 **紧接** 该元件的 8 条 `FORCEPROP 2 LASTPIN $PN`（L17-45），再放 VALUE/PART_NAME/CDS_LIB 等，**之后才** `FORCEADD GND_POWER..1`（L104）→ **每个元件的引脚属性都在自己的 FORCEADD 块内**。
- 04p4 `page15.csa` L11643 起才是 WIRE 段、L12475 起是 DOT 段 → **WIRE/DOT 在文件尾是正确结构**（我们已是）。
- Cadence 官方培训材料（eeworm page1.csa）：`FORCEADD INPORT..1` 块内 `FORCEPROP 1 LASTPIN (-2900 3200) HDL_PORT IN`、`VHDL_PORT IN` —— **IOPORT 系 LASTPIN 用级别 1**。
- 结论：**LASTPIN 与"最近 FORCEADD 的元件"绑定**；引脚属性必须紧跟所属 FORCEADD，不能集中到文件尾（尤其不能在 IOPORT 之后）。

## A.1 Q1 — IOPORT 引脚属性被删（SPCOCN-543/541）

### A.1.1 生成文件结构证据（output_phaseXII_final3/worklib/5015/sch_1/page2.csa）

```
L10   FORCEADD C SIZE PAGE..1
L32   FORCEADD CAPACITOR..1      (C106)
L87   FORCEADD CAPACITOR..1
L197  FORCEADD RESISTOR..1
L307  FORCEADD CH347..1          (U6G 回退符号)
L397..L716  10 × FORCEADD IOPORT..1   ← 最后 FORCEADD = IOPORT
L717..L884  全部 LASTPIN（$PN / SIG_NAME），中间再无 FORCEADD
L886..L904  WIRE 段
```

- errors.txt page2 报告的删除值（R4、P4、A21、B21、Y22、Y24、Y25、W26、W27、V25）**正好是 L830-880 U6G 引脚 $PN 值的子集**，且报错组件名是 **IOPORT** —— 与"LASTPIN 绑定到最后 FORCEADD 的 IOPORT、引脚不存在 → SPCOCN-543/541 删除"完全吻合。
- 04p4 对照：组件块内含自己的 $PN（L17-45），IOPORT 块（L228-254）内含自己的 LASTPIN（L240/L245）→ **必须内联**。

### A.1.2 IOPORT 块逐字段差异（04p4 page15 L228-254 vs 我们的 page2 L397-428）

| 字段 | 04p4（Cadence 实测可开） | 我们（SPCOCN-543） | 判定 |
|------|--------------------------|--------------------|------|
| LASTPIN 级别 | `FORCEPROP 1 LASTPIN`（L240/245） | `FORCEPROP 3 LASTPIN`（csa_writer L1407/1413） | **改 1** |
| 引脚坐标 | body(-3900 -1400)+(-50,0)=(-3950 -1400)（IOPORT css `C -50 0`） | body+（0,0）（`_pos("A",0,0)` L1389-1390 查不到 C 命令回退） | **改 -50,0** |
| HDL_PORT 标签 | body+(325,-125)（css `X "HDL_PORT" 325 -125`）=(-3575 -1525) | body+(25,-100)（L1391 fallback） | **改 325,-125** |
| VHDL_PORT 标签 | body+(-35,-70)=(-3935 -1470) ✓ | body+(-35,-70) ✓ | 保持 |
| OFFPAGE 标签 | body+(25,100) ✓ | body+(25,100) ✓ | 保持 |
| PATH 标签 | body+(0,50) ✓ | body+(0,50) ✓ | 保持 |
| DISPLAY 比例 | 0.872340 | 1.021277 / 0.851064 | 对齐 0.872340 |
| CDS_LMAN_SYM_OUTLINE | 无 | 多一条 `FORCEPROP 2 LAST CDS_LMAN_SYM_OUTLINE IOPORT`（L1423-1426） | **删除** |
| PAINT | PATH PINK / VHDL_PORT PINK，HDL_PORT 无 | PATH ORANGE / HDL_PORT PINK / VHDL_PORT PINK | 对齐 04p4 |

### A.1.3 修复方案（Q1）

1. **结构重构**（csa_writer.py `_build_csa_content_conn` L924-1114）：
   - 第 1 遍：现有 L983-1056 只算数据（pin_coords / pin_name_map / net_pin_map / source_pins），**不输出**。
   - 第 2 遍：遍历实例，每实例先 `_emit_conn_instance_block`（含新加的旋转行），**随后立即输出该实例全部 LASTPIN**（把 L1058-1075 的逻辑按实例内联）；IOPORT 块改为在实例循环内按序输出（或在所有实例之后，因其自带 LASTPIN，不再影响任何后续 LASTPIN——两者皆可，推荐并入实例循环）。
   - WIRE/DOT/SIG_NAME-on-wire 段保持在文件尾（对齐 04p4 L11643+）。
   - 新增辅助函数：`_lastpin_pn`（L1459-1468）与 `_sig_name_at_pin`（L1471-1485）保持，仅调用位置变化；级别不变：**$PN=2、SIG_NAME=3**（04p4 实证 $PN level 2（L17）、SIG_NAME level 3（L106））。
2. **IOPORT 块模板对齐**（`_emit_ioport_block` L1339-1427）：
   - `FORCEPROP 1 LASTPIN`（级别 1）；
   - 引脚坐标：`body + symbol.css C 命令偏移`（IOPORT = (-50,0)）；实现上复用 `_get_css_pin_offsets(body, 1)` 的 "A" 键，回退 (-50,0)；
   - HDL_PORT 标签坐标：css `X "HDL_PORT"` 偏移 (325,-125)，回退 (325,-125)；VHDL_PORT 保持 (-35,-70)；
   - DISPLAY 比例统一 0.872340；PAINT：PATH/VHDL_PORT PINK，HDL_PORT 不 PAINT；
   - 删除 `CDS_LMAN_SYM_OUTLINE`；CDS_LIB 值：04p4 是 `standard`，我们用 `hdl_lib`（symbol 已拷入 hdl_lib，保持 hdl_lib 亦可，二选一需与 IOPORT 符号所在库一致——当前 hdl_lib/IOPORT 存在，保持 hdl_lib）。
3. **跨页网接入 IOPORT 的 WIRE**（配合 Q4 P1）：把 IOPORT 引脚坐标加入对应跨页网的 `net_pin_map`，使 trunk+stub 布线覆盖 IOPORT（对齐 04p4 `(-4425 -1400)(-3950 -1400)`）。

## A.2 Q2 — WIRE 端点与引脚不重合（"引脚和悬空的电线端口很近，但差一点"）

### A.2.1 证据链

1. **旋转数据（EDIF 实测）**：3023 实例中 `rotation: {90:318, 180:356, 270:109}`（共 783，26%）、`mirror: {2:114, 1:103}`（共 217）。EDIF 解析 `edif_parser.py:906-918` → IR → `connectivity_model.py:577-578`。
2. **生成端**：`csa_writer.py:1018-1043` 对 `rot/mirror` 用 `rotate_point`（coord_transform.py L273-300）旋转 css 偏移后写 LASTPIN/WIRE；但 `_emit_conn_instance_block`（L1129-1240）**通篇无旋转输出行**（无 `R 1/2/3`、无 `MY/MX`）→ Cadence 按默认视图渲染 → 引脚在未旋转位置。
3. **参考实证**：04p4 `page15.csa` L255-283 `FORCEADD INPORT..1` + **`R 2`**（180°）+ body(-3900 -1300) + `LASTPIN (-3950 -1300)`。INPORT css 实测 `C 50 0 "A"`（偏移 +50,0）→ 旋转 180° 后 = (-50,0) → (-3950 -1300) **恰为旋转后位置**。⇒ **Cadence 确实旋转引脚；LASTPIN 必须写在旋转后位置；同时 CSA 必须输出旋转行**。我们目前"算旋转、不输出旋转行"是自相矛盾。
4. **off-grid 叠加**：`coord_transform.py:112-114` `int(page_cx + dx*scale)` 无网格吸整 → body 如 C106 (-2611 2188)（2611%25=11, 2188%25=13）→ 引脚/WIRE 全部 off-grid（实测 page2 64%、page12 60% 端点 off-grid；04p4/8367 全部 0%）。Cadence 移动元件时报 `SPCOCN-1329: 1 wire was not rerouted because it was off-grid`。

### A.2.2 修复方案（Q2）

1. **组件旋转行输出**（`_emit_conn_instance_block` L1146-1147 之间插入）：
   - `rotation=90 → "R 1"`、`180 → "R 2"`、`270 → "R 3"`（04p4 `R 2` 实证；R 取值 1/2/3 对应 90/180/270 为 DEHDL 约定，实现时以 R 2=180° 为锚校验）；
   - `mirror`：04p4/8367 参考工程无镜像实例可抄语法；**P0 保守策略**：mirror≠0 的 217 个实例**不应用 rotate_point 镜像**（即 pin_coords 只按 rotation 旋转；不输出 mirror 行），保证"渲染=坐标"一致（方向近似错但**连接成立**）；**P1 验证** `MY/MX`（或 `M Y`）在 Cadence 16.6 的真实语法后再启用镜像。
2. **body 坐标吸 25 网格**（`coord_transform.py` map_page / map_point 输出前 `round(v/25)*25`）：引脚 = 吸网格 body + css 偏移（css 偏移本身为 25 倍数）→ LASTPIN 与 WIRE 全部 on-grid，消除 SPCOCN-1329 与 Cadence 隐性吸附错位。**注意**：吸网格必须发生在 LASTPIN 与 WIRE **共用**的 pin_coords 源头（csa_writer L984-1056），保证两者仍精确重合（硬约束）。
3. 回归确认：修复后逐页扫描 `WIRE 端点 == LASTPIN 坐标`（现 tests 已断言）继续成立。

## A.3 Q3 — 芯片几何正中央电线锚点（fallback 链）

### A.3.1 fallback 链与失效点

链路：`_get_css_pin_offsets(body,section)`（L1556-1584，读 hdl_lib/body/sym_N/symbol.css 的 C 命令）→ 未命中时 `_get_pin_name_map`（L1586-1638，读 chips.prt PIN_NUMBER→功能名）→ 仍未命中 → `_fallback_pin_offsets`（L1640-1681）→ L1040 `.get(pre.pin_name, (0,0))`。

- **失效点 1（键错）**：`_fallback_pin_offsets` 字典键为 `str(i)`（数字 1..n，L1676-1680），L1040 却按 `pre.pin_name`（功能名）查 → 对任何功能名引脚永远 (0,0)；**周边分布代码从未生效**。
- **失效点 2（符号错配）**：U6G（原 SOC 数百引脚）匹配不到符号 → 回退 CH347（20 引脚 USB 芯片）。CH347 css 有 `C -300 -250 "RST#"` 等（chips.prt 1→RST#…20），但 U6G 的 EDIF 引脚是 R4/P4/A21…（**数字≠1..20**）→ `_get_pin_name_map("CH347")` 映射 `{'1':'RST#',...}` 对 `pin_number='R4'` 查不到 → fallback (0,0)。实测 page2 L780-880：U6G 全部 15 个 $PN + 6 个 SIG_NAME 均在 **同一坐标 (-8752 5411)**（=body 中心）。
- 用户看到：芯片中心一个锚点、电线从中心拉出、页面出现"错误芯片"（CH347 20 脚 vs 原 SOC）。

### A.3.2 修复方案（Q3，可落地、对 8367/04p4 无回归）

1. **P0：fallback 按 pin_number 查**（csa_writer L1038-1040）：
   ```python
   fallback = self._fallback_pin_offsets(body_name, section, len(irec.pins))
   off = (fallback.get(pre.pin_name) or fallback.get(str(pre.pin_number))
          or fallback.get(pre.pin_number) or (0, 0))
   ```
   使多引脚 IC 至少分布到两侧（-150/+150 列），消除"全部 (0,0) 中心塌缩"；对 2 脚无源件 fallback 键本就是 '1'/'2'，行为不变。
2. **P0：未匹配芯片引脚顺序分布 + 占位轮廓**：
   - 对 `pin_count > 1` 且 css 完全缺失的芯片，按 `_fallback_pin_offsets` 的周边分布（左列 i≤half、右列 i>half），**保证每个引脚坐标唯一且与 LASTPIN/WIRE 一致**；
   - 生成端为该类实例输出合理的 `CDS_LMAN_SYM_OUTLINE`（如按引脚数推导矩形），使 Cadence 渲染一个矩形占位体，避免"20 脚符号 + 300 引脚数据"错配渲染；
   - 不试图把 U6G 数据塞进 CH347 符号（治标）：**未匹配芯片可考虑不再 fallback 到具体符号而是占位 sym**（见 P1）。
3. **P1：占位 sym 生成**：对无 hdl_lib 符号的 cell，在 hdl_lib 生成 `<cell>/sym_1/symbol.css`（按引脚数生成 C 命令 + 矩形轮廓 + chips.prt），Cadence 渲染为真实占位芯片；引脚偏移与生成端 `_fallback_pin_offsets` 完全一致 → 连接成立、外观正常。生成逻辑放 `csa_writer` 或独立 `placeholder_lib.py`，仅对 unmatched 实例触发，**不影响**已匹配的 8367/04p4 输出。
4. **P2：复用 EDIF 原始引脚坐标**：P0-A4 已把 EDIF WIRE 折线解析到 `NetIR.wires/PageIR.wires`；将折线端点经同一 CoordTransform 映射后，与"网→引脚"关联即可反推每个引脚的真实落点（Capture 图纸中 WIRE 端点必压在引脚上）。此方案对**任何**符号都给出正确引脚几何，是终极解；需处理多页/跨页网与端点去重，列为远期。

## A.4 Q4 — 布线方案改进（用户重点：杂乱/重合/遮挡）

### A.4.1 参考工程真实布线风格（实测 04p4/8367，5 页统计）

| 指标 | 04p4 page15 | 04p4 page3 | 8367 page1/2/3 | 我们 page2 | 我们 page12 |
|------|-------------|-----------|----------------|-----------|-------------|
| WIRE 总数 | 424 | 487 | 94/352/272 | 19 | 283 |
| off-grid 端点 | **0/1696 (0%)** | **0/1948** | **0%** | **49/76 (64%)** | **680/1132 (60%)** |
| 非正交段 | **0** | **0** | **0** | 0 | 0 |
| 最热 trunk-y 聚集 | 2475×12 | 5500×17 | 6650×23 | 5400×3 | **4400×44** |
| LASTPIN/FORCEADD off-grid | **0** | — | **0** | 大量 | 大量 |

结论：参考工程 = **全正交、全 25 网格、trunk 分散在多个 y/x 层**；多网之间 trunk 几乎不共线；WIRE 端点精确压在引脚上（其余端点是转弯/接点）。我们当前 trunk 取每网中位 y 吸网格 → 高密度页大量网中位同值 → **44 条线共线**。

### A.4.2 关键连线本质（硬约束）

Cadence DEHDL 以"坐标重合"判定连接：**WIRE 端点必须精确等于引脚坐标**（04p4 L17-45 的 $PN 坐标 = WIRE 端点坐标；我们的 e2e 测试同样断言）。任何布线优化（避让、绕障、分层）**不得破坏端点重合**；吸网格必须发生在引脚坐标源头，不能只吸 WIRE。

### A.4.3 分级改进设计

#### P0（必修，本轮）
1. **全坐标吸 25 网格**（见 A.2.2-2）：body → 引脚 → LASTPIN → WIRE 端点统一 on-grid，消灭 SPCOCN-1329。
2. **传 body_outlines**：`csa_writer.py:1086` 改为
   `engine.route_nets(net_pin_map, body_outlines)`；
   body_outlines 由 body_coords + `CDS_LMAN_SYM_OUTLINE`（或 css 轮廓）展开为 (x0,y0,x1,y1) 列表；`_avoid_outlines`（wire_layout L195-222）恢复有效。
3. **trunk 车道差异化（去重）**：
   - 新方法 `WireLayoutEngine.route_nets(net_pin_map, body_outlines) -> dict[str, RoutedNet]`：
     - 先按 (span, 引脚数) 排序（长网先布，视觉更清晰）；
     - 维护 `used_lanes: dict[区间, int]`；对每个网的候选 trunk（中位 y 或 x），若与已用 trunk 在同一区间（±25）共线，则 `trunk += lane*50`（lane 从 1 起，直到不与任何已用 trunk 及元件体重叠）；
     - 单网路径与 `route_net` 相同（保留 `route_net` 供单测，内部抽 `_route_horizontal/_route_vertical`）。
   - 效果：page12 的 44 条 y=4400 → 分布在 4400/4450/4500… 多车道；同页不同网不再几何共线（消除"重合/疑似短路"）。
4. **端点重合硬约束回归**：所有生成坐标只由 pin_coords 派生；新增 e2e 断言"每条 WIRE 端点都在 25 网格上、且任一网不与其它网共享 trunk 线段"。

#### P1（建议，本轮或下轮）
5. **正交绕障**：`_route_stub_with_detour(pin, trunk, outlines)`——若直 stub 穿过元件体，在网格上走 L/Z 形（pin→(pin.x, 绕行y)→(trunk.x, 绕行y)→trunk），绕行 y 取 outline 外 50 的倍数。
6. **横/竖 trunk 交替**：按网序奇偶或页面象限选择 trunk 方向，或"同方向 trunk 车道满则换方向"，进一步分散。
7. **IOPORT 接入 WIRE**（见 A.1.3-3）：跨页网 trunk 延伸/分叉到 IOPORT 引脚，消除"右上角一排排孤立 IO 口"。

#### P2（远期）
8. **A\* / 迷宫布线**：以 25 网格为状态空间、元件体为障碍、线长+拐角+交叉为代价；支持先布关键网（高扇出/跨页）再布其余；可选用 EDIF 原始 WIRE 折线（NetIR.wires）映射结果作为布线提示（保证与 CIS 原图观感一致）。
9. **网序优化**：按引脚数/跨度降序布线，稠密网优先占车道。

---

# Part B：修复函数级改动清单（汇总）

| 文件 | 改动 | 影响函数/行 |
|------|------|-------------|
| `cis2hdl/core/writer/csa_writer.py` | ① LASTPIN 内联进各 FORCEADD 块（2 遍重构）；② IOPORT 模板对齐 04p4（级别 1、引脚/标签坐标、DISPLAY、删 outline）；③ 组件旋转行 `R 1/2/3` 输出；④ fallback 按 pin_number 查；⑤ 传 body_outlines + IOPORT 入网；⑥ 未匹配芯片占位轮廓 | `_build_csa_content_conn` L924-1114；`_emit_ioport_block` L1339-1427；`_emit_conn_instance_block` L1129-1240；L1038-1040；L1082-1090 |
| `cis2hdl/core/writer/coord_transform.py` | body 输出吸 25 网格（map_page/map_point/power_symbol_position） | `map_page` L108-115、`map_point` L144-147、`power_symbol_position` L192-208 |
| `cis2hdl/core/writer/wire_layout.py` | 新增 `route_nets`（车道差异化、传 outlines、绕障 L/Z）；保留 `route_net`；`_avoid_outlines` 强化为区间冲突链 | L80-222 |
| `cis2hdl/core/writer/connectivity_model.py` | page_num 按 page.map 页名数字（页面错位修复，工程师执行） | L427/L541 |
| `cis2hdl/core/writer/coord_transform.py`（P1） | 镜像语法验证后启用 mirror 行 | `rotate_point` L273-300 |
| 新增 `placeholder_lib.py`（P1） | 未匹配芯片占位 sym 生成（css + chips.prt） | — |

# Part C：tests/ 影响评估

| 测试 | 断言 | 影响 | 处置 |
|------|------|------|------|
| `tests/unit/test_phase_xi_p0.py::TestCsaWriterConn::test_every_connected_pin_has_lastpin`（L345-357） | `count("FORCEPROP 2 LASTPIN") + count("FORCEPROP 3 LASTPIN") == pin_count` | 合成设计无 off_pages → 无级别 1 LASTPIN，**不破**；但若将来加 IOPORT fixture 会漏数 | 建议改为正则 `FORCEPROP [0-3] LASTPIN` 计数，防御性更新 |
| `test_csa_has_wire_lastpin_sig_name_dot_quit`（L331-343） | 存在性断言 | 保持 | 无需改 |
| `test_one_sig_name_per_net`（L359-372）、`test_wire_endpoints_include_pins`（L374-402） | SIG_NAME 引脚 ∈ WIRE 端点 | 吸网格后 LASTPIN/WIRE 同步移动 → 仍一致 | 无需改（保持源头一致即可） |
| `tests/unit/test_phase_xi_p0.py::TestWireLayoutEngine`（L123-167） | 单网 route_net 拓扑/端点/outline | 保留 `route_net` 单网语义 → 不破；`test_avoid_body_outline` 继续有效 | 新增 `route_nets` 车道/去重单测 |
| `tests/unit/test_phase_xi_p1.py::TestP0C5Ioport`（L263-281） | 源码含 FORCEADD IOPORT / OFFPAGE TRUE / HDL_PORT INOUT；hdl_lib 有 IOPORT | 模板改动后字符串仍在 | 建议新增断言：`FORCEPROP 1 LASTPIN`、引脚坐标=body-50、无 CDS_LMAN_SYM_OUTLINE |
| `tests/e2e/test_phase_xi_p0.py`（L192-196, L240-290, L415-432） | WIRE 端点 == LASTPIN 坐标；电源块 `FORCEPROP 3 LASTPIN … SIG_NAME` | 电源块级别 3 不变；端点一致性保持 → 不破 | 新增：全端点 on-grid、无网共 trunk、U6G 类引脚不再全 (0,0) |
| `tests/unit/test_phase_xi_p1.py`（L86-99 $LOCATION） | 与本次改动无关 | 无 | — |
| 8367 DSN/EDF 回归（Phase XI 基线 404 passed） | 布局/引脚/网络 | 吸网格与旋转行只改变几何坐标与渲染视图，不改网络拓扑；8367 参考工程无镜像实例 | 需全量回归 |

# Part D：实现顺序（按依赖）

```
T1 基础设施：coord_transform 吸网格 + 组件旋转行输出（Q2 地基，先于一切几何改动）
T2 Q1：LASTPIN 内联重构 + IOPORT 模板对齐（消除 SPCOCN-543/541）
T3 Q3：fallback 按 pin_number + 未匹配芯片分布/占位（消除中心锚点）
T4 Q4 P0：route_nets 车道差异化 + 传 body_outlines + IOPORT 入网（布线整洁）
T5 P1：正交绕障 / 横竖交替 / 镜像语法验证 / 占位 sym（可选，下一轮）
T6 P2：A* 迷宫布线 + EDIF 折线复用（远期）
```
依赖：T1 → T2/T3/T4 均依赖 T1（坐标与引脚一致）；T4 依赖 T2（IOPORT 引脚坐标正确后才能接入 WIRE）；T3 独立于 T2 但共享 T1。

---

## 附：关键实测数据速查

- EDIF HG5015-BE36_V10：3023 实例；rotation 90×318 / 180×356 / 270×109；mirror 2×114 / 1×103；24 页；off_page 243 声明 / 522 页面引用。
- output_phaseXII_final3 page2：FORCEADD 顺序（组件→IOPORT→批 LASTPIN）；U6G 15×$PN + 6×SIG_NAME 全在 (-8752 5411)；WIRE 19 条、端点 off-grid 64%；3 网共享 trunk (-8752 5400)→(-2076 5400)。
- output_phaseXII_final3 page12：44 条 WIRE 共 trunk y=4400；FET 类 4 引脚（G1/G2/G3/S）全塌缩中心 (-8337 6180)、(-2919 5217)；端点 off-grid 60%。
- 参考工程：04p4/8367 全部 WIRE/LASTPIN/FORCEADD 0% off-grid、0 非正交；WIRE 段在文件尾；IOPORT/INPORT 用 `FORCEPROP 1 LASTPIN`（eeworm 培训材料同）；INPORT `R 2` 实证"LASTPIN=旋转后位置"。
