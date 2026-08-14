# CIS2HDL 匹配系统深度分析报告

**日期**: 2026-08-06  
**分析对象**: v1.0.0 MultiScorer 全库打分 vs v0.8.2 前缀过滤+置信度  
**测试数据**: HG5015-BE36_V10 (889 元件)

---

## 零、新旧系统对比总览（一票否决）

| 案例 | v0.8.2 (旧) | v1.0.0 (新) | 结论 |
|------|------------|------------|------|
| **C11** (1mF电容) | capacitor ✅ | **resistor** ❌ conf=1.0 | 致命错误 |
| **C21** (22UF电容) | capacitor ✅ | **inductor** ❌ conf=0.7 | 致命错误 |
| **C282** (22UF电容) | capacitor ✅ | **inductor** ❌ conf=0.7 | 致命错误 |
| **C394/395** (22UF电容) | capacitor ✅ | **inductor** ❌ | 致命错误 |
| **D21** (0值二极管) | diode ✅ | **resistor** ❌ conf=1.0 | 致命错误 |
| **R2** (100K电阻) | resistor ✅ | **capacitor** ❌ conf=0.6 | 致命错误 |
| **R92** (100K电阻) | resistor ✅ | **capacitor** ❌ conf=0.6 | 致命错误 |
| **R117** (100K电阻) | resistor ✅ | **capacitor** ❌ conf=0.6 | 致命错误 |
| **R42** (100电阻) | resistor ✅ | **capacitor** ❌ conf=0.7 | 致命错误 |
| **R228** (9.1NH电感) | resistor ✅ | **capacitor** ❌ conf=0.7 | 致命错误 |
| **M1** (MARK) | mark ✅ | **rtxm169** ❌ conf=0.5 | 类型错误 |
| **LB4** (磁珠LB) | fb ✅ | **ch347** ❌ conf=0.5 | 完全错误 |
| **C284** (22UF电容) | capacitor ✅ | **uc2843** ❌ conf=0.8 | 完全错误 |
| **C1** (10UF电容) | capacitor exact | capacitor fuzzy 0.55 | 劣化 |

**结论: v1.0 MultiScorer 系统使匹配质量严重倒退。虽然官方宣称匹配率从 95.1% 提升到 100%，但实际上大量匹配是类型错误的（电容→电阻、电容→电感、二极管→电阻），只是被虚高的置信度掩盖了。**

---

## 一、根因分析

### 1.1 架构层面：类型约束从 HARD GATE 退化为 SOFT WEIGHT

```
旧系统 (v0.8.2):
  PREFIX_TO_CATEGORY 硬编码 → 候选池过滤（仅同类型元件）
  → ValueMatcher 在有限的同类型候选池内做精确匹配 → conf=1.0

新系统 (v1.0):
  移除 PREFIX_TO_CATEGORY → 144 个候选全部参与评分
  → MultiScorer 6维加权排序 → top-20
  → ValueMatcher 在 20 个跨类型候选内搜索 → 如果唯一匹配则 conf=1.0
  → 问题：唯一匹配可能是错误类型！
```

**核心问题**: 在元件匹配中，前缀（类型）是**硬约束**而非软权重。一个电容永远不能匹配为电阻，无论 value/footprint/pin_count 多么匹配。

### 1.2 MultiScorer 六维权重的结构性缺陷

```
维度        权重    问题
─────────────────────────────────────────────
footprint   0.25    电容和电阻可能有相同的封装（如0402）
prefix      0.20    冷启动底分0.1 → 电容对电阻候选也能拿分
pin_count   0.20    所有无源器件都是2脚 → 该维度完全无区分力
value       0.15    值可能跨类型匹配（如22UF同时存在电容和电感ptf中）
jedec       0.10    关联信息不足
part_name   0.10    名称重叠少
```

**关键计算模拟（C11: 1mF电容 → 电阻）**：

```
电容候选:  prefix=1.0×0.20 + footprint=0.5×0.25 + pin=1.0×0.20 
          + value=0.0×0.15 + jedec=0.5×0.10 + part=0.5×0.10 
          = 0.525
          
电阻候选:  prefix=0.1×0.20 + footprint=0.5×0.25 + pin=1.0×0.20
          + value=0.9×0.15 + jedec=0.5×0.10 + part=0.5×0.10
          = 0.535  ← 高于电容！
```

电阻候选因 ptf_rows 中某个 value 在 normalize 后碰巧与 "1mF" 归一化结果匹配，value 维度得 0.9，总分超过电容。MultiScorer 将电阻排到第一，ValueMatcher 找到唯一匹配 → conf=1.0。

### 1.3 ValueMatcher 无类型检查的致命缺陷

```python
# ValueMatcher.match() — 当前逻辑
for candidate in candidates:       # ← 包含所有类型的候选
    for row in ptf_rows:
        if normalize(row.value) == src_value:
            matched_candidates.append(candidate)  # ← 不检查类型！
```

**ValueMatcher 完全不检查候选类型与源元件类型是否一致。** 它只比较归一化后的值字符串。这在旧系统中不是问题，因为候选池已被前缀过滤器限定为同类型。但在新系统中，候选池包含 144 个跨类型元件，值匹配的"唯一性"保证不再有意义。

### 1.4 FallbackMatcher 的分数通胀

当 ValueMatcher 因候选太多而失败（跨类型歧义），FallbackMatcher 接管：

```
FallbackMatcher._score_candidate():
  - exact (值+封装同时匹配): conf=1.0
  - size  (仅封装匹配):     conf=0.8
  - prefix (仅前缀匹配):    conf=0.5

然后 result.confidence = max(Fallback.confidence, MultiScorer.score)
```

由于 MultiScorer 对错误的跨类型候选也能打出 0.5-0.7，FallbackMatcher 的 0.5 前缀分被 MultiScorer 的 0.6-0.7 覆盖，最终 conf 看起来"还可以"但实际类型完全错误。

### 1.5 PST Value 列和 JEDEC_TYPE 列的来源

- **pst_value**: 来自 CIS 端 PST 数据（pstchip/pstxprt），是 CIS 原始元件的标称值，**不是匹配到的 HDL 元件的值**
- **jedec_type**: 来自 HDL 库中匹配到的元件的 JEDEC_TYPE 字段（part.ptf 中），**不是 CIS 端的 JEDEC_TYPE**
- **cis_value**: 来自 CrossRef CSV，是 CIS 端解析出的标称值

**当前 CSV 的问题**：只显示了 CIS value + HDL jedec_type，缺少：
- CIS 端 JEDEC_TYPE（来自 pstchip）
- CIS 端 footprint
- HDL 端 value
- HDL 端 footprint
- HDL 端类型/类别

用户无法在 CSV 中对比双边数据来验证匹配正确性。

### 1.6 "Best match via MultiScorer: X" 的含义

当 error_note 显示 "Best match via MultiScorer: CAPACITOR_0402"，意思是：
- MultiScorer 六维打分后排名第一的候选是 CAPACITOR_0402
- 但匹配器链（Exact→Fuzzy→Feature→Value→Fallback）最终选择的是另一个候选
- 最终 conf = max(匹配器链.confidence, MultiScorer.top_score)

这说明两套评分系统存在分歧，而且永远取较高值——这使得低质量匹配也被赋予虚高的 conf。

---

## 二、具体案例深度分析

### 2.1 C11: 1mF电容 → resistor（conf=1.0, VALUE策略）

```
旧系统: capacitor → conf=0.65 (feature, unity boost)
新系统: resistor  → conf=1.0 (VALUE策略)
```

**问题**: ValueMatcher 在 top-20 候选中找到唯一一个 ptf_row value 归一化后等于 "1mF" 的候选。该候选恰好是 resistor 类型。由于 ValueMatcher 不检查前缀一致性，直接返回 conf=1.0。

**为什么电阻会有"1mF"值**：虽然搜索结果未在 resistor/part.ptf 中找到 "1mF" 字面量，但 normalize_value() 的归一化逻辑可能将 "1mF" 转换后与电阻的某个 ptf value（如 "1000uF" 或特殊编码值）匹配。或是从 capacitor 库中通过某种路径（如 chips.prt 交叉引用）进入了电阻的 ComponentDef 构建过程。

### 2.2 C21/C282/C394等: 22UF电容 → inductor（conf=0.7）

```
旧系统: capacitor → 正确
新系统: inductor  → conf=0.7 (FeatureMatcher)
```

**问题**: 电容值 "22UF" 经 normalize_value 后，FeatureMatcher 在 inductor 候选中找到了匹配特征。或者 ValueMatcher 因多个候选都有 "22UF" 值而返回 no_match（歧义），FallbackMatcher 接手后首选了 inductor。

**根因**: pin_count 对所有无源器件都是 2，价值部分权重（footprint 0.25 + pin 0.20 = 0.45）是无区分力的，使得错误的类型匹配能通过 value+footprint 得分超过正确的类型。

### 2.3 D21: 二极管 → resistor（conf=1.0, VALUE策略）

```
旧系统: diode → conf=0.55 (FALLBACK, prefix 'D' + zero-value)
新系统: resistor → conf=1.0 (VALUE策略)
```

**问题**: D21 的值是 "0"。ValueMatcher 在 resistor 的 ptf_rows 中找到了值为 "0" 的行（0Ω电阻），且恰好只有一个候选匹配 → conf=1.0。

**preventable**: 如果先确定 refdes 前缀 "D" → diode 类型，然后只在 diode 候选中搜索 value="0"，就不会错误匹配到 resistor。

### 2.4 M1/M2/M3-M6: MARK → rtxm169/ch347（conf=0.5）

```
旧系统: mark → 正确
新系统: rtxm169/ch347 → conf=0.5
```

**问题**: MARK 点的 refdes 前缀是 "M"。MultiScorer 冷启动下 prefix affinity 为 0.1，而 footprint="FMARKS" 与 rtxm169/ch347 的 footprint 可能有部分匹配，导致这些芯片元件得分更高。FallbackMatcher 选取得分最高的候选。

**M1 和 M2 类型不同**: 因为 MultiScorer 对不同候选的打分略有差异，rtxm169 和 ch347 的分数微差导致 M1 匹配到 rtxm169，M2 匹配到 ch347。这在功能上毫无意义——MARK 点只需要匹配到 mark 或 test_point。

### 2.5 R117/R92/R2/R42: 电阻 → capacitor

```
旧系统: 全部正确匹配为 resistor
新系统: 全部错误匹配为 capacitor
```

**问题**: 电阻值 "100K", "100", "51K" 等经 normalize 后，在 capacitor 的 ptf_rows 中没有对应值（因为电容不使用这些值），但 pin_count 一致（都是 2 脚）、footprint 可能相似 → MultiScorer 给 capacitor 打了更高分。

这说明 **footprint+pin_count 两个高权重维度（合计 0.45）在无源器件之间完全没有区分力**。

### 2.6 C284: 22UF电容 → uc2843（conf=0.8, 看起来像芯片名）

uc2843 是一个真实的 PWM 控制器芯片型号。它的 library_id 或 part_name 中包含 "2843"，而 C284 的 library_id 恰好包含 "284" → MultiScorer 的 part_name 维度给予高分。这是一个意外但真实的"命名碰撞"问题。

### 2.7 D9: 空值二极管 → conf=0.5 FALLBACK

这是可以接受的——D9 的 value 为空，只能通过前缀 "D" 匹配到 diode。旧系统也是 conf=0.5。但新系统额外显示 "Best match via MultiScorer: DIODE"，说明 MultiScorer 和 FallbackMatcher 对 DIODE 的意见一致，这是正确的。

### 2.8 IC3: AMS1117-1.5 稳压器 → 匹配问题

```
旧系统: interface (通用接口类) → conf=0.65
新系统: 未在用户提到的新 CSV 中...
```

从旧数据看，AMS1117-1.5 是一个真实的 1.5V 输出 LDO 稳压器（SOT223 封装）。旧系统匹配到 "interface" 并不理想（应该是 voltage_regulator 或 IC）。这是 HDL 库缺乏对应 cell 的问题，而非匹配算法问题。

---

## 三、根本原因总结

### MultiScorer 不可行的五个根本原因

| # | 原因 | 严重度 |
|---|------|:---:|
| 1 | **前缀是硬约束，不是软权重** — C 前缀的元件必须是电容，权重 0.20 无法保证 | 🔴 |
| 2 | **pin_count 权重无区分力** — 所有无源器件 2 脚，合计权重浪费 0.45 | 🔴 |
| 3 | **value 维度可跨类型匹配** — normalize_value 后不同元件的值可能碰撞 | 🔴 |
| 4 | **conf=max() 造成虚高** — 取两个独立评分系统的最大值，无法反映真实可信度 | 🟡 |
| 5 | **ValueMatcher 无类型一致性检查** — conf=1.0 不保证类型正确 | 🔴 |

### 为什么旧系统更好

旧系统虽然只有 95.1% 匹配率（44/889 失败），但：
- **0 个类型错误** — 前缀过滤确保类型正确
- 失败的 44 个主要是 T* 变压器（20）、LB* 磁珠（15）、D* 空值二极管（5）等少见类型
- 这些问题可以通过扩展 VALUE_CATEGORY_HINTS 和改进 FallbackMatcher 逐步解决
- 匹配质量远高于新系统的"100% 但充满类型错误"

---

## 四、新方案设计（修正版）

### 4.1 核心原则

> **类型先行，值/封装在后** — 先确定元件类型（硬约束），再在类型内精确匹配（软评分）。

> **Phase 1 不做"单一门控"，做"类型假设排序"** — 避免锁死类型而导致搜索不到正确匹配。对歧义前缀（U/J/T/M...）维护有序的类型假设列表，Phase 2 在多个类型池中并行搜索，由候选质量决定最终归属。

> **被动元件（R/C/L/D）使用确定性规则匹配，而非加权评分** — 标称值和封装尺寸必须精确匹配，不允许通过权重妥协。

### 4.2 两阶段匹配架构（修正版）

```
Phase 1: TYPE HYPOTHESES (有序假设列表 — 不锁死)
──────────────────────────────────────────────────
输入: CIS 元件 (refdes, value, footprint, pst_data)
输出: [(type_1, prior_conf_1), (type_2, prior_conf_2), ...]  ← 有序列表

策略:
  A. refdes 前缀 → 类型假设列表（带先验置信度）
     精确前缀: 
       C → [(capacitor, 1.0)]
       R → [(resistor, 1.0)]
       L → [(inductor, 1.0)]
       D → [(diode, 0.95), (zener, 0.80), (tvs, 0.60)]
       LED → [(led, 1.0)]
       TP → [(test_point, 0.90), (mark, 0.70), (hole, 0.50)]
       
     歧义前缀 (多类型排序):
       U → [(IC, 0.85), (interface, 0.70), (connector, 0.40), (voltage_regulator, 0.35)]
       J → [(connector, 0.80), (rj45, 0.60), (header, 0.50)]
       T → [(transformer, 0.70), (inductor, 0.60)]
       M → [(mark, 0.80), (test_point, 0.60)]
       X/Y → [(crystal, 0.85), (oscillator, 0.75)]
       S → [(switch, 0.70), (button, 0.60)]
       LB → [(ferrite_bead, 0.75), (inductor, 0.50)]
       P → [(connector, 0.60), (power, 0.50)]
       K → [(relay, 0.80)]
       Z → [(zener, 0.80), (diode, 0.60)]
       VR → [(voltage_regulator, 0.90)]
       RN → [(resistor_network, 0.90)]
       F → [(fuse, 0.90)]

  B. 动态学习矩阵增强先验概率
     PrefixAffinityCalculator 在每次成功匹配后更新先验:
       首次运行: U → [(IC, 0.85), ...]  ← 冷启动先验
       匹配 U7→lcmxo2 成功后: U→IC 权重 +0.05
       下次运行: U → [(IC, 0.90), ...]  ← 学习了！
     用于调整类型假设列表中的 pre_conf

  C. PST 数据辅助细化
     pstchip JEDEC_TYPE / PART_NAME 可为先验类型加权:
       U + JEDEC_TYPE="FPGA" → IC 先验 conf 从 0.85 提升到 0.95
       D + value="DZ_" → zener 先验 conf 提升到 0.95

  D. VALUE 特征推断
     "UH"/"NH"/"uH"/"nH" → inductor 类型排在前面
     "MHz"/"kHz" → crystal/oscillator
     "MARK" → mark
     "TESTPOINT" → test_point

Phase 1.5: CANDIDATE POOL CONSTRUCTION (按类型假设构建搜索池)
───────────────────────────────────────────────────────────
对于 Phase 1 输出的每个类型假设，构建对应的 HDL 候选子池:
  type=IC → [lcmxo2, ch347, rtxm169, ...]  (89 个 IC 候选)
  type=interface → [interface, ...]         (1 个)
  合并: 按类型假设顺序排列的候选巢状列表（去重）

Phase 2: MATCH (分类型分层搜索)
────────────────────────────────
按类型假设顺序依次搜索，一旦找到满足阈值的匹配即停止。

A. 被动元件匹配器 (PassiveMatcher) — 确定性规则
   ─────────────────────────────────────────
   适用于: C(capacitor), R(resistor), L(inductor), D(diode/zener)
   
   层级 1: 值 + 尺寸 双精确匹配 (conf=1.0)
     在 ptf_rows 中搜索 normalize(row.value) == src_value 
     AND extract_pkg_size(row.package_type) == src_size
     唯一匹配 → conf=1.0, strategy="PASSIVE_EXACT"
     多个匹配 → JEDEC_TYPE 做 tiebreaker → conf=0.95, strategy="PASSIVE_EXACT_MULTI"
   
   层级 2: 值精确 + 尺寸未知 (conf=0.80)
     src_value 精确匹配但 CIS footprint 为空
     按尺寸降序选择默认 primitive → conf=0.80, strategy="PASSIVE_VALUE_ONLY"
   
   层级 3: 值精确 + 尺寸近似 (conf=0.70)
     src_value 精确匹配，src_size 不完美匹配
     选择最接近尺寸的 primitive → conf=0.70, strategy="PASSIVE_VALUE_NEAR"
   
   层级 4: 尺寸精确 + 值近似 (conf=0.60)
     src_value 无精确匹配但 src_size 精确
     → conf=0.60, strategy="PASSIVE_SIZE_ONLY"
   
   层级 5: 前缀兜底 (conf=0.40)
     无值/尺寸匹配 → 选择同类型最通用的 primitive
     → conf=0.40, strategy="PASSIVE_PREFIX_ONLY"

B. 主动/特殊元件匹配器 (ActiveMatcher) — 类型内评分
   ────────────────────────────────────────
   适用于: IC, connector, crystal, switch, transformer, mark...
   
   在类型内使用 5 维加权评分（已移除 prefix）:
     footprint:  0.30  ← 在类型内才有区分力
     value:      0.15
     jedec:      0.20
     pin_count:  0.20
     part_name:  0.15
   
   匹配器链: Exact → Fuzzy → Feature → Value → Fallback
   最终 conf = type_prior_conf × within_type_conf

搜索停止条件:
  对于被动元件: 找到层级 1 (PASSIVE_EXACT) → 立即停止，不搜索层级 2-5
  对于主动元件: 找到 within_type_conf ≥ 0.75 → 停止，不搜索下一个类型假设
  如果所有类型假设都未达到阈值 → 回到 type_prior_conf 较低的类型再搜一轮
```

### 4.2a 关键设计：避免 Phase 1 锁死类型

```
错误设计 (已否决):
  U → Phase 1 → "interface"（锁死）
       → Phase 2 → 只在 interface 候选池搜索 → 永远找不到 lcmxo2

正确设计 (修正版):
  U → Phase 1 → [(IC, 0.85), (interface, 0.70), (connector, 0.40)]
       → Phase 1.5 → 构建 IC_pool + interface_pool + connector_pool
       → Phase 2 → 
           ① 先在 IC_pool 中搜索 → 找到 lcmxo2, within_conf=0.92
              final_conf = 0.85×0.92 = 0.782 → ≥ 阈值 0.75 → 停止！
           ② 无需搜索 interface_pool / connector_pool
       
特殊情况 (IC 池找不到好匹配):
  U18 → PWR（实际是电源模块）
       → Phase 2 ①: IC_pool → best conf=0.35（太低）
       → Phase 2 ②: interface_pool → best conf=0.45（还不够）
       → Phase 2 ③: connector_pool → 无匹配
       → 底线处理: 返回所有池中 top-3，标记 "needs_manual_review"
```

> **注记（内部不一致说明）**：本节"正确设计"中 U 的类型假设列表为 **3 项** `[(IC, 0.85), (interface, 0.70), (connector, 0.40)]`，与 §4.2 策略 A 及 §4.3 type_gate.yaml 中的 **4 项**（含 `voltage_regulator`：`[(IC, 0.85), (interface, 0.70), (connector, 0.40), (voltage_regulator, 0.35)]`）不一致。**实现版取 4 项处理**（见 `cis2hdl/config/type_gate.yaml`）。
>
> <!-- 已修改：§4.2a 加注 —— U 类型假设 3 vs 4 内部不一致，实现取 4 类型。 -->

### 4.2b Top-3 候选生成逻辑

```python
def generate_top3(source, type_hypotheses, all_candidates):
    """
    生成 Top-3 候选列表。
    
    跨类型规则:
      - 可以跨类型（只要 Phase 1 产生了多个类型假设）
      - 每个类型假设的候选严格在各自类型池内产生
      - 按 final_conf = type_prior_conf × within_type_conf 全局排序
      - 被动元件 C/R/L/D 通常只有一个类型假设 → Top-3 都在同一类型内
    
    详细示例见 4.7 节。
    """
```

### 4.2c 被动元件为什么不能用加权评分

```
MultiScorer 对 C1 (10UF):
  值维度权重 0.15 → 即使值不匹配也只丢 0.15 分
  其他维度 (footprint+prefix+pin+jdec+name) 可补回 0.85 分
  → 一个值不匹配的电容候选可能得分 0.6+
  → 永远无法保证"100% 标称值匹配"的语义

确定性规则:
  先检查值是否完全匹配（normalize 后全等比较）
  → 值不匹配 → 直接跳过该层级，降级到层级 4/5
  → 值匹配 → 再检查尺寸
  → 没有任何"部分匹配可以补回"的路径
  → 严格保证"100% 必须匹配"的语义
```

### 4.3 类型映射表（动态可学习）

```yaml
# type_gate.yaml — Phase 1 类型假设配置
# 格式: prefix → [(type, prior_conf), ...]
# 列表按 prior_conf 降序排列（Phase 2 搜索顺序）

type_hypotheses:
  # ── 精确前缀（单一类型，无歧义）──
  C:    [[capacitor, 1.0]]
  R:    [[resistor, 1.0]]
  L:    [[inductor, 1.0]]
  LED:  [[led, 1.0]]
  FB:   [[ferrite_bead, 1.0]]
  IC:   [[IC, 0.95], [voltage_regulator, 0.70]]

  # ── 歧义前缀（多类型排序）──
  D:    [[diode, 0.95], [zener, 0.80], [tvs, 0.60]]
  U:    [[IC, 0.85], [interface, 0.70], [connector, 0.40], [voltage_regulator, 0.35]]
  J:    [[connector, 0.80], [rj45, 0.60], [header, 0.50]]
  T:    [[transformer, 0.70], [inductor, 0.60]]
  TP:   [[test_point, 0.90], [mark, 0.70], [hole, 0.50]]
  M:    [[mark, 0.80], [test_point, 0.60]]
  X:    [[crystal, 0.85], [oscillator, 0.75]]
  Y:    [[crystal, 0.85], [oscillator, 0.75]]
  S:    [[switch, 0.70], [button, 0.60]]
  LB:   [[ferrite_bead, 0.75], [inductor, 0.50]]
  P:    [[connector, 0.60], [power, 0.50]]
  K:    [[relay, 0.80]]
  Z:    [[zener, 0.80], [diode, 0.60]]
  VR:   [[voltage_regulator, 0.90]]
  RN:   [[resistor_network, 0.90]]
  F:    [[fuse, 0.90]]
  Q:    [[transistor, 0.85], [mosfet, 0.75]]

# 值特征辅助（提升特定类型的 prior_conf）
value_type_boost:
  NH: [inductor, 0.15]
  UH: [inductor, 0.15]
  mH: [inductor, 0.10]
  nH: [inductor, 0.10]
  MHz: [crystal, 0.20]
  kHz: [crystal, 0.15]
  MARK: [mark, 0.30]
  TESTPOINT: [test_point, 0.30]

# PST 数据辅助（基于 pstchip JEDEC_TYPE 提升 prior_conf）
pst_type_boost:
  CAPACITOR: [capacitor, 0.10]
  RESISTOR: [resistor, 0.10]
  INDUCTOR: [inductor, 0.10]
  DIODE: [diode, 0.10]
  ZENER: [zener, 0.15]
  CONNECTOR: [connector, 0.15]
  IC: [IC, 0.10]
  FPGA: [IC, 0.20]
  CRYSTAL: [crystal, 0.20]
  OSCILLATOR: [oscillator, 0.15]
  TRANSFORMER: [transformer, 0.15]
  SWITCH: [switch, 0.15]

# 被动元件类型标识（用于触发确定性规则匹配）
passive_types: [capacitor, resistor, inductor, diode, zener, ferrite_bead]
```

> **实现版注记（代码核对，供整合参考）**：本节 type_gate.yaml 为分析稿草案，与实际实现（`cis2hdl/config/type_gate.yaml`）存在 3 处差异，**以实现版为准**：
> 1. `passive_types` 实现版**含 `led`**：`[capacitor, resistor, inductor, diode, zener, ferrite_bead, led]`；
> 2. `type_hypotheses` 实现版额外含 **`RD: [[resistor, 0.90]]`**（RD 前缀 → 电阻，如 RD25 = 4.7K）；
> 3. 实现版新增 **`fixed_prefixes` 段**：`LB→ferrite_bead`、`LED→led`、`FB→ferrite_bead`、`TP→test_point`（强绑定，命中首类型假设即停止，不降级第二优先级）。
>
> <!-- 已修改：§4.3 加注 —— passive_types 缺 led、缺 RD/fixed_prefixes；实现版见 cis2hdl/config/type_gate.yaml。 -->

### 4.4 PrefixAffinityCalculator 的新角色

学习矩阵的核心价值从"跨类型候选评分"转为"类型假设排序优化"：

- **冷启动**: 使用 type_gate.yaml 中的硬编码先验概率
- **学习后**: U→IC 权重从 0.85 → 0.90 → 0.95 → 1.0
  - U 前缀的搜索顺序: IC 越来越靠前
  - 已学到的关联可以跳过 type_gate.yaml 的其他假设
- **记录方式**: `~/.cis2hdl/type_affinities.yaml`
  - 格式: `{U: {IC: {count: 15, conf: 0.92}, interface: {count: 2, conf: 0.45}}}`
  - 多次匹配后，低质量关联被淘汰，高质量关联权重不断累积
- **关键安全边界**: 即使学习矩阵显示 U→IC 的 conf=0.99，仍然保留 interface/connector 作为 fallback 类型假设（prior_conf 不低于 0.05），确保极端 outlier 仍有机会正确匹配

### 4.5 conf 值的重新定义

```python
# 新 conf 定义 — 分阶段、可追溯

Phase 1 — Type Prior Conf:
  表示: 元件类型的先验置信度
  来源:
    - exact_prefix_match:     1.00  (C→capacitor)
    - prefix_yaml_rule:       0.85  (U→IC, 来自 type_gate.yaml)
    - pst_data_boost:        +0.10  (JEDEC_TYPE 确认)
    - value_hint_boost:      +0.10  (值特征辅助)
    - learned_affinity:      +0.05  (历史学习增量)
    - cap_at:                 0.95  (先验上限，保留不确定性)

Phase 2 — Within-Type Conf (被动元件):
  表示: 类型内匹配的确定性
  层级:
    - PASSIVE_EXACT:          1.00  (值+尺寸双精确，唯一)
    - PASSIVE_EXACT_MULTI:    0.95  (值+尺寸双精确，多 candidate，JEDEC tiebreak)
    - PASSIVE_VALUE_ONLY:     0.80  (值精确，尺寸未知)
    - PASSIVE_VALUE_NEAR:     0.70  (值精确，尺寸近似)
    - PASSIVE_SIZE_ONLY:      0.60  (尺寸精确，值缺失/不匹配)
    - PASSIVE_PREFIX_ONLY:    0.40  (仅类型正确，无值/尺寸信息)

Phase 2 — Within-Type Conf (主动元件):
  表示: 类型内评分
  来源: 5 维加权评分 (0.5-1.0)
  最低阈值: 0.50 (低于此值认为不匹配)

Final Conf = Phase 1 conf × Phase 2 conf

示例:
  C1 (10UF):   1.0 × 0.80 = 0.80  (值精确，尺寸未知)
  C11 (1mF):   1.0 × 1.0  = 1.0   (值+尺寸双精确)
  U7 (FPGA):   0.85 × 0.92= 0.782  (IC类型+精确匹配)
  M1 (MARK):   0.80 × 0.90= 0.72   (mark类型+值精确)
```

### 4.6 CSV 和 HTML 报告增强

CSV 应包含以下完整列（双边对比 + Top-3）：

```
主报告列 (单行/元件):
  cis_refdes | cis_value | cis_footprint | cis_jedec | cis_library_id | cis_page
  hdl_cell | hdl_primitive | hdl_value | hdl_footprint | hdl_jedec | hdl_category | hdl_pin_count
  phase1_types | phase1_prior_conf | phase2_strategy | phase2_within_conf | final_conf
  match_status | error_note

Top-3 候选列 (每元件 3 组，嵌入或独立文件):
  [rank1_type] [rank1_cell] [rank1_primitive] [rank1_final_conf] [rank1_match_dims]
  [rank2_type] [rank2_cell] [rank2_primitive] [rank2_final_conf] [rank2_match_dims]
  [rank3_type] [rank3_cell] [rank3_primitive] [rank3_final_conf] [rank3_match_dims]

match_dims 格式 (可读的匹配维度说明):
  "value✅ footprint✅ jedec✅ pin_count✅"  ← 全部匹配
  "value✅ footprint⚠️(default_0603)"       ← 部分匹配
  "type_only❌"                             ← 仅类型级别
```

### 4.7 Top-3 生成示例

**例 1: C1 (10UF 电容) — 被动元件，单一类型**

```
Phase 1: [(capacitor, 1.0)]
Phase 1.5: capacitor_pool = [CAPACITOR_0201, CAPACITOR_0402, CAPACITOR_0603, CAPACITOR_0805, ...]

Phase 2 (确定性规则):
  层级 1: 值"10uf"匹配 + 尺寸精确 → 未命中(CIS footprint为空)
  层级 2: 值"10uf"匹配 + 尺寸默认 → 
    应用默认尺寸"0603" → CAPACITOR_0603 (conf=0.80)
  层级 1 unfulfilled → 层级 2 命中 → 停止

Top-3 (同类型内, 值精确匹配的变体):
  #1 capacitor / CAPACITOR_0603 / conf=0.80 / value✅ footprint⚠️(default)
  #2 capacitor / CAPACITOR_0805 / conf=0.70 / value✅ footprint🔽(not exact)
  #3 capacitor / CAPACITOR_0402 / conf=0.65 / value✅ footprint🔽(not exact)
```

**例 2: U7 (FPGA 芯片) — 主动元件，歧义前缀**

```
Phase 1: [(IC, 0.85), (interface, 0.70), (connector, 0.40)]

Phase 2:
  ① 搜索 IC_pool → lcmxo2, within_conf=0.92
     final = 0.85×0.92 = 0.782 ≥ 阈值 0.75 → 停止！

Top-3 (跨类型, 类型假设范围内):
  #1 IC/lcmxo2      / 0.782 / value✅ footprint✅ jedec✅ pin_count✅
  #2 interface       / 0.39  / value❌ footprint⚠️ pin_count✅
  #3 connector       / 0.16  / value❌ footprint❌ pin_count⚠️
```

**例 3: M1 (MARK 点) — 歧义前缀**

```
Phase 1: [(mark, 0.80), (test_point, 0.60)]

Phase 2:
  ① 搜索 mark_pool → mark, within_conf=0.90
     final = 0.80×0.90 = 0.72 ≥ 阈值 0.65 → 停止！

Top-3 (跨类型):
  #1 mark    / 0.72 / value✅ footprint✅
  #2 test_point / 0.42 / value⚠️ footprint⚠️
  #3 (如果 mark_pool 还有其他变体) 或 test_point 的其他变体
```

**对比: 现在的 MultiScorer 对 M1 的处理**

```
现在的流程:
  → 144 候选全量打分, M→rtxm169 因 footprint 和 pin_count 得分高
  → M1 → rtxm169 (芯片!) ❌
  → M2 → ch347 (另一个芯片!) ❌
  → 两个 MARK 点匹配为不同的芯片类型，完全错误

修正后:
  → Phase 1: M → [(mark, 0.80), (test_point, 0.60)]
  → mark_pool 内搜索 → mark, conf=0.72
  → M1, M2, M3... → 全部匹配为 mark ✅
```

---

## 五、实施建议（修正版）

### 优先级排序

| 优先级 | 任务 | 说明 |
|:---:|------|------|
| **P0** | Phase 1: 类型假设列表生成器 | 基于 refdes+PST+value_hints+YAML 的有序类型列表 |
| **P0** | Phase 2A: PassiveMatcher (确定性规则) | C/R/L/D 被动元件 5 级确定性匹配，替代 ValueMatcher |
| **P0** | Phase 2B: ActiveMatcher (类型内评分) | IC/连接器等主动元件在类型内评分，恢复 prefix_filter 的门控作用 |
| **P0** | 移除 MultiScorer 跨类型评分 | 从 pipeline.run_batch 恢复 prefix 过滤（通过 Phase 1.5 候选池构建） |
| **P0** | conf 计算重构 | 从 max(Fallback,MultiScorer) 改为 Phase1×Phase2 |
| **P1** | Top-3 候选生成 | 跨类型排序 + 匹配维度标注 |
| **P1** | CSV/HTML 双边对比增强 | 完整 CIS↔HDL 属性对比 + Top-3 列 |
| **P2** | PrefixAffinityCalculator 重新定位 | 改为 Phase 1 类型假设学习器 |
| **P2** | YAML type_gate.yaml 可编辑 | 类型映射 + 值特征 + PST boost 配置 |
| **P3** | 冷启动验证 | 在 HG5015 数据集上运行，对比 v0.8.2 和 v1.0 的正确性 |

### 关键设计原则

1. **类型假设排序 > 类型锁死** — 多类型并行搜索，最终由候选质量决定归属
2. **被动元件 = 确定性规则** — 值+尺寸必须精确匹配，不接受权重妥协
3. **主动元件 = 类型内评分** — 只有同类型内评分才有区分力
4. **conf = Phase1 × Phase2** — 两阶段独立可信度乘算，不取 max 虚高
5. **宁可漏匹配，不虚假匹配** — 类型假设耗尽仍未找到 → 标记需要人工确认

---

## 六、附录：新旧系统关键数据对比

### 旧系统 (v0.8.2 output_final) — 类型正确性: 100%

```
正确匹配: 845/889 (95.1%)
失败(类型正确但不可用): 44/889 (4.9%)
  - T*变压器: 20
  - LB*磁珠:  15
  - D*空值:    5
  - 其他:      4
类型错误匹配: 0/889 (0%)
```

### 新系统 (v1.0 output_phaseX_test) — 类型正确性: 严重下降

```
官方声称: 889/889 (100%) 匹配
实际分析:
  明显类型错误: 估算 > 50 个
    - C→R (电容→电阻): ~5 个
    - C→L (电容→电感): ~10 个
    - R→C (电阻→电容): ~15 个
    - D→R (二极管→电阻): ~5 个
    - M→IC (MARK→芯片): ~6 个
    - LB→IC (磁珠→芯片): ~12 个
    - X→IC (晶振→芯片): ~1 个
    - 其他: ~10 个
  类型正确但低conf: 大量 (C1=0.55, C106=0.5, C133=0.5...)
  类型正确且高conf: 大部分
```

### 结论

v1.0 的"100% 匹配率"是以牺牲**类型正确性**为代价换来的统计美化。实际匹配质量显著低于 v0.8.2。
