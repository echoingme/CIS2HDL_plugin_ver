# Phase XVII 补充方案：SPN 删除机制详解 + chip_config 合并设计 + BGA 四边图标（2026-08-12）

> 主理人齐活林产出（基于源码核实：csa_writer.py/placeholder_lib.py/manual_matches.py/candidate_selector.py
> + 04p4 golden + 前两轮调研）。用户决策 D1-D11 已记录于 requirement-scheme/problem-list/system_design。

---

## 第一部分：SPN 删除机制详解（用户 D1，需通俗+技术解释）

### 1.1 SPN 到底是什么？（通俗解释）

**一句话**：SPN 不是我们写的属性，而是 Cadence DEHDL 内部给每个引脚自动生成的一个"引脚序号"（Signal Pin Number），它在底层跟踪"这个引脚排第几号"。报错信息里看到的 `SPN with value 8`，其实**就是指我们写在 CSA 里的 `$PN 8`**——Cadence 把我们写的 `$PN` 属性读入后，内部转成它的 SPN 概念。当它说 "has been deleted" 时，意思是：**这个引脚的属性块整体没被采纳，引脚信息被丢弃了**。

打个比方：SPN 是 Cadence 内部的"工牌号"，`$PN` 是我们在原理图文件里贴的"姓名标签"。如果 Cadence 认为这张标签"贴得不对"（比如贴到了错误的位置、格式不对、或者这个元件本来就没有这么多引脚），它就把标签撕掉并报告 "SPN with value X has been deleted"。

### 1.2 三类触发删除的机制（为什么 Cadence 会删）

| 类 | 机制（Cadence 视角） | 证据 |
|---|---------------------|------|
| **① 引脚坐标不在 symbol 引脚上** | Cadence 打开 CSA 时，把 LASTPIN 坐标与符号库（symbol.css）里的 C 指令引脚位置比对。若 LASTPIN 坐标**不在任何 symbol 引脚上**（如实例 8 个引脚但 symbol 只有 6 个，第 7/8 个坐标是 fallback 启发式生成的），Cadence 判定"这不是有效引脚"→ 删除属性 | RF_SW（8脚 vs symbol 6脚）、PQ2016、FILTER 报错 |
| **② LASTPIN 块格式不合规** | 我们输出的 SIG_NAME LASTPIN 块带 `PAINT MONO + DISPLAY INVISIBLE` 两行；04p4 黄金样本同位置**无 PAINT**。Cadence 对 LASTPIN 属性块的解析是严格模板匹配，多余行导致块解析失败 → 整块属性被删 | `_sig_name_at_pin`(csa_writer.py:2609-2622) vs 04p4 page9 L365 |
| **③ 旋转实例的"R 行 + 元件级 SIG_NAME"组合** | 04p4 参考工程中，旋转元件（R 1/2/3）只带 `$PN` 引脚（见 page11 RESISTOR R1），**从未见"旋转 + 元件级 SIG_NAME LASTPIN"的组合**；SIG_NAME 只出现在电源符号（FORCEPROP 3，无 R 行）。Cadence 遇到未验证的组合可能无法绑定属性 | 报错集中在旋转 CAPACITOR（aes6 版 63 次） |

**核心结论**：SPN 报错 = Cadence 的"引脚属性丢弃"通用提示，根因在我们生成的 LASTPIN 块（坐标未命中/格式违规/组合未验证），不是 Cadence 自身 bug。

### 1.3 受控 A/B 实测方案（Cadence 16.6 控制台验证）

用户在有 Cadence 16.6 的电脑上，用最小 csa 文件验证。每组文件内容如下（复制保存为 `test_spn.csa`，放入工程 sch_1 目录后用 DEHDL 打开）：

**组 1：非旋转 + 纯 $PN 块（04p4 格式，基线）→ 期望不删**
```
FORCEADD CAPACITOR..1
(-2875 3325);
FORCEPROP 2 LASTPIN (-2875 3375) $PN 2
R 1
J 0
(-2885 3385);
DISPLAY 0.808511 (-2885 3385);
FORCEPROP 2 LASTPIN (-2875 3250) $PN 1
R 1
J 2
(-2885 3240);
DISPLAY 0.808511 (-2885 3240);
FORCEPROP 1 LAST VALUE 100NF
R 1
J 1
(-2875 3425);
DISPLAY 0.851064 (-2875 3425);
```

**组 2：非旋转 + $PN + SIG_NAME（当前带 PAINT 版本）→ 期望报 SPCOCN-543（验证根因②）**
```
FORCEADD CAPACITOR..1
(-2875 3325);
FORCEPROP 2 LASTPIN (-2875 3375) $PN 2
R 1
J 0
(-2885 3385);
DISPLAY 0.808511 (-2885 3385);
FORCEPROP 2 LASTPIN (-2875 3250) SIG_NAME 12V0\g
J 0
(-2865 3260);
DISPLAY 0.659574 (-2865 3260);
PAINT MONO (-2865 3260);
DISPLAY INVISIBLE (-2865 3260);
```

**组 3：旋转 R 2 + $PN + SIG_NAME → 期望报 SPCOCN-543（验证根因③）**
```
FORCEADD CAPACITOR..1
R 2
(-2875 3325);
FORCEPROP 2 LASTPIN (-2875 3375) $PN 2
R 1
J 0
(-2885 3385);
DISPLAY 0.808511 (-2885 3385);
FORCEPROP 2 LASTPIN (-2875 3250) SIG_NAME 12V0\g
J 0
(-2865 3260);
DISPLAY 0.659574 (-2865 3260);
PAINT MONO (-2865 3260);
DISPLAY INVISIBLE (-2865 3260);
```

**组 4：非旋转 + 无 PAINT SIG_NAME → 期望不删（验证修复有效性）**
```
FORCEADD CAPACITOR..1
(-2875 3325);
FORCEPROP 2 LASTPIN (-2875 3250) SIG_NAME 12V0\g
J 0
(-2865 3260);
DISPLAY 0.659574 (-2865 3260);
```

**判定表**：
| 结果组合 | 结论 |
|---------|------|
| 组1不删 组2删 | 根因②（PAINT）确认 |
| 组1不删 组3删 | 根因③（旋转组合）确认 |
| 组2删 组4不删 | 修复有效（删 PAINT 即可） |
| 组1也删 | 问题在更底层（$PN 格式/坐标），需再查 symbol.css |

### 1.4 代码级修复方案（按优先级）

| 方案 | 内容 | 影响面 | 风险 |
|------|------|--------|------|
| **A（必做）** | 删 `_sig_name_at_pin` 的 `PAINT MONO + DISPLAY INVISIBLE` 两行（csa_writer.py:2620-2621） | 所有 SIG_NAME 引脚标签 | 低（对齐 04p4） |
| **B（必做）** | LASTPIN 前校验坐标是否命中 symbol.css 引脚；未命中不发射（或标 NC） | 引脚数不匹配实例（RF_SW/PQ2016/FILTER） | 低 |
| **C（推荐）** | 旋转实例的 SIG_NAME 改放 WIRE 上（`_sig_name_on_wire`），引脚只留 $PN | 旋转电容/电阻 | 中（需验证） |
| **D（推荐）** | 引脚数不匹配实例改用 temp_lib 模拟图标（M1） | 占位芯片 | 低（新功能） |

---

## 第二部分：chip_config.yaml 与 manual_matches.yaml 合并统一设计（用户 D7）

### 2.1 现状冗余分析

| 文件 | 结构 | 现状问题 |
|------|------|----------|
| `manual_matches.yaml` | `{version, matches:[{refdes, library_id, section, value, note}]}` | 无引脚级映射（pin_mapping 恒空）；加载器 `ManualMatchesConfig.load` + 注入 `apply_manual_matches` |
| `chip_config.yaml`（拟新增） | `{matches:[{refdes, library_id, pin_map, placement, hanging}]}` | 与 manual_matches 大量重叠（refdes/library_id/section） |
| `~/.cis2hdl/mapping_rules.yaml`（candidate_selector 写） | `{mappings:[{source_library_id, target_library_id, confirmed_by, timestamp}]}` | **第三个冗余格式**！字段语义相同但命名不同 |

**冗余点**：三个文件都在做"人工覆盖匹配"这件事，字段高度重叠（refdes↔source_library_id、library_id↔target_library_id），加载/注入逻辑分散。

### 2.2 统一方案：单一 `chip_config.yaml`（推荐名）

**统一文件**：`chip_config.yaml`（替代 manual_matches.yaml + mapping_rules.yaml）

```yaml
# 统一人工配置（替代 manual_matches.yaml / mapping_rules.yaml）
version: "2.0"
matches:
  - refdes: U6H            # 唯一键（refdes，大写规范化）
    library_id: u6h_ph     # 目标库（temp_lib 或 hdl_lib）
    section: 1             # sym 视图号
    value: ""              # 可选值覆盖
    note: ""               # 备注
    pin_map:               # 引脚级映射（可选，空=自动）
      K18: "18"
      G20: "20"
    hanging: ["V25", "W27"]  # 悬空引脚（可选，空=全部自动连接）
    placement:             # 放置覆盖（可选，M3 腾挪结果）
      dx: 0
      dy: 0
```

**向后兼容**：加载器先尝试 v2.0 解析；失败则尝试 v1.0（manual_matches 结构）解析并自动升级——旧文件无需修改即可用。

### 2.3 函数级设计（防冗余：单一加载器 + 单一注入点）

| 组件 | 设计 | 删除的旧代码 |
|------|------|-------------|
| `ManualMatch` dataclass | 扩展字段：`pin_map: dict = field(default_factory=dict)`、`hanging: list = field(default_factory=list)`、`placement: dict = field(default_factory=dict)` | 无（原位扩展） |
| `ManualMatchesConfig.load` | 升级：解析 v2.0 + 兼容 v1.0（`_upgrade_v1` 转换） | 无（增强） |
| `apply_manual_matches` | 升级：消费 pin_map（写入 MatchResult.pin_mapping）+ hanging（标记不生成 WIRE）+ placement（写回实例坐标偏移） | 无（增强） |
| `candidate_selector._save_to_yaml` | **改为写统一 chip_config.yaml**（复用 ManualMatchesConfig 序列化） | 删除 mapping_rules.yaml 独立格式 |
| CLI | `--manual-matches` 保留为别名 → 解析 chip_config.yaml；新增 `--chip-config` 主入口 | 统一到一个参数 |
| routing.yaml | `manual_matches: ""` 字段保留，语义=chip_config 路径 | 无 |

**优先级规则（用户 D7）**：chip_config（v2.0）与旧 manual_matches（v1.0）同时存在时，**v2.0 条目覆盖 v1.0 同 refdes 条目**（加载时合并，v2.0 后写入 wins）。

### 2.4 防冗余清单（删除项）

1. `candidate_selector.py` 的 `_save_to_yaml` 独立 mapping_rules 格式 → 改为调用统一序列化
2. 任何硬编码 `~/.cis2hdl/mapping_rules.yaml` 路径 → 统一为 `chip_config.yaml`（工程目录或用户目录可配）
3. `ManualMatchesConfig` 与未来 chip_config 的重复字段 → 单一定义

---

## 第三部分：temp_lib 模拟图标 —— BGA 四边引脚 + 功能名标签 + 旋转对齐（用户 D3）

### 3.1 引脚分布分档规则（统一 `distribute_mock_pin_offsets`）

| 档位 | 引脚数 | 布局 | 说明 |
|------|:---:|------|------|
| 小型 | n ≤ 12 | 左右两列（现有 `distribute_ic_pin_offsets`） | 保持现有 |
| 中型 | 12 < n ≤ 64 | 四列 -200/-100/+100/+200，pitch≥50 | 保持现有（修 pitch<50 bug） |
| **BGA 大型** | n > 64 | **矩形四边分布**（顶/底/左/右） | 新实现（对齐 CIS 原图） |

### 3.2 BGA 四边分布算法（n > 64）

```
per_side = ceil(n / 4)
top = 4 个引脚数（含角）
body 尺寸自适应：half_w = 200 + (per_side_top-1)*pitch/2（pitch=50 最小）
引脚坐标（相对 body 中心）：
  顶边（i=0..t-1）: x = -half_w + i*pitch, y = +body_h   → 引脚朝上，标签在上方（旋转 0°）
  右边（i=0..r-1）: x = +body_w, y = +half_h - i*pitch   → 引脚朝右，标签在右侧（旋转 90°）
  底边（i=0..b-1）: x = +half_w - i*pitch, y = -body_h   → 引脚朝下，标签在下方（旋转 180°）
  左边（i=0..l-1）: x = -body_w, y = -half_h + i*pitch   → 引脚朝左，标签在左侧（旋转 270°）
```

**DEHDL symbol.css 写法**（C 指令 orientation 参数：0/90/180/270）：
```
# 顶边引脚（功能名 GND 示例，标签在上方水平）
L -10 300 0 300 -1 0
C 0 300 "GND" 0 315 0 0 32 1 U    ← 标签在引脚上方
# 右边引脚（标签右侧，旋转 90°）
L 300 10 300 0 -1 0
C 300 0 "RST#" 315 0 90 0 32 1 L  ← orientation=90
# 底边引脚（标签下方，旋转 180°）
L 10 -300 0 -300 -1 0
C 0 -300 "PWR" 0 -315 180 0 32 1 D  ← orientation=180
# 左边引脚（标签左侧，旋转 270°）
L -300 -10 -300 0 -1 0
C -300 0 "CLK" -315 0 270 0 32 1 R  ← orientation=270
```

**对齐规则**：顶部标签居中（label_x = 引脚 x）、底部居中、左侧右对齐（label_x = pin_x - 15）、右侧左对齐（label_x = pin_x + 15）。

### 3.3 功能名标签（用户 D3：显示功能名）

- 标签文本 = CIS 原引脚功能名（gnd/pwr/rst/CLK 等，来自 EDIF pin_name 或 chips.prt 功能名）
- 引脚号保留在 chips.prt（PIN_NUMBER），**原理图标签显示功能名**
- 重复功能名处理：去重 + 加序号后缀（如 `GND`, `GND_2`, `GND_3`）
- 空功能名回退显示引脚号

### 3.4 与现有 placeholder 的衔接

- `mock_icon_lib.py` 新模块：`distribute_mock_pin_offsets(pin_count, pin_names)` 三档分档 + BGA 四边
- `placeholder_lib.py` 保留（逃生舱）；csa_writer 优先用 mock_icon_lib（`temp_lib.enabled=true` 时）
- LASTPIN/WIRE 同源：mock 图标 C 指令偏移 = csa_writer pin_coords 偏移（硬约束）

---

*补充方案完成（2026-08-12，主理人齐活林）。待工程师实施：P0 修复（A/B/C/D 方案）+ M1 mock_icon_lib + M2 collision + M3 placement + M4 wire_simplifier + M5 net_name_connect + M6 pin_audit + M7 GUI + 文件合并。*

---

# 追加（2026-08-12 二期）：GND 聚类合并实现补充

## GND 聚类算法（对应 supplement 第一部分"place_net_terminals 就近接入"落地）

```
芯片 GND 引脚分组（每芯片 ≥1 个 GND 引脚）→ chip_gnd_pins
  → 贪心最近邻聚类（cluster_radius=2000，用户 D4）：
      对每个芯片 GND 引脚，计算与现有簇质心（曼哈顿距离）；
      距离 ≤ 半径 → 加入该簇；否则新建簇
  → 每簇放置 1 个共享 GND 符号（_outward_point + _gnd_symbol_body 避让）
  → 簇分组键 GND\g@<refdes1>_<refdes2>（trunk 局部化）
  → 共享 SIG_NAME GND\g 保持电气连通（power-net-by-name）
```

**实现位置**：`_plan_and_inject_gnd_symbols`（csa_writer.py L1943，Phase XVII R3）
**配置**：`gnd_distribution.cluster_radius`（默认 2000，0=关闭）
**验证**：v8 全工程 GND 19→97（分布+聚类）；684 passed

*追加完成（2026-08-12 二期）。*
