# Phase XIX：Cadence 16.6 全量复测问题清单与修复方案（08-13）

> 用户对 v9_default / v9_gnd_distribute / v9_wire_simplify / v9_net_name 四版本
> 全量复测 + test_spn g1-g4 实测，反馈大量问题。本文档逐条分类整理：
> 根因 → 已修复/待实现 → 方案。核心文档追加见 changelog/STATUS。

---

## 一、报错类（🔴 已代码级修复，待用户复测确认）

### E1. SPCOCN-1158 "pin property not preceded by connection"（全部 _PH mock 芯片）🔴 已修复

**现象**：每个 _PH mock cell 的 `symbol.css` 报 `error on line 11: pin property
not preceded by connection` → 芯片图标全部消失（U6C/U6D/U5/U18/U20/S1/S3 等
全部 SPCOCN-515 "library not included"）→ 543 SPN 被删（连锁）。

**根因（grep 全库实锤）**：
1. **C 指令字号非法**：真实库 C 指令 font 合法值域 `{0,1,22,23,24,29,32,34,38,40,41}`
   （最小合法 22，主流 32），mock 用 **16** → 全库 0 条先例 → Cadence 无法解析
   引脚属性。X "PIN_TEXT" 同样 16 非法（真实库 `{0,22,23,24,29,32,34,40}`，主流 24）。
2. **outline 几何悬空**：旧实现 outline 在 x/y **双向内缩 50**（±100 vs 引脚 ±150），
   侧边引脚 L 连接线起点 `(x_edge, py)` 的 py 超出 outline y 范围 → 起点悬空
   → "not preceded by connection"。
3. **BGA 四边分布角部矛盾**：top/bottom 引脚 px 超 outline x，矩形四边同时
   伸出在几何上必然产生角部悬空。

**修复**：
- `_append_pin_line`：C 指令与 X PIN_TEXT 字号钳制 `max(font, 23)`（合法 + 满足
  "缩小"诉求）；L 起点固定为 outline 边界（x0/x1/y1/y0）。
- `mock_outline`：统一公式 **x 内缩 50（引脚伸出）、y 外扩 50（覆盖引脚）**。
- `distribute_mock_pin_offsets`：BGA（n>64）改**两侧多列**（仅 left/right，
  对齐真实库形态；消除 top/bottom 角部悬空）。
- 验证：63/63 mock cell 字号 ≥23；1045 引脚 L 起点 0 悬空；outline 全部覆盖引脚 y。

### E2. SPCOCN-543 SIG_NAME `GND_POWER\g` 被删（g3/g4 均复现）🔴 已修复

**现象**：每页 GND_POWER 报 `SIG_NAME GND_POWER\g deleted`；用户 g3（`GND\g`）
与 g4（`GND_POWER\g`）golden 格式同样被删。

**根因**：LASTPIN offset 用 golden (50,100)，但 fixture hdl_lib 的
`gnd_power/sym_1/symbol.css` 引脚实为 **`C 0 50`（offset (0,50)）** →
LASTPIN 未命中符号引脚 → Cadence 删除 SIG_NAME。golden (50,100) 的"正常页面"
其 GND_POWER 符号是用户生产库（引脚 (50,100)），与输出包 hdl_lib 不同。

**修复**：`routing.yaml` + `config.py` 默认 `gnd_power_lastpin_offset: [0, 50]`
（命中符号实际引脚）。验证：LASTPIN = body+(0,50) ✓。

### E3. SPCOCN-543 SPN 被删（U18/U20/U3/U14/U6H/U6E/U6A/U6B/U5/S1/S3）🔴 已修复

**根因**：与 E1 连锁——mock cell 因 1158 未加载 → 引脚不存在 → SPN 全删。
E1 修复后自动解决（S1/S3 的 `&1` 引脚名是 mock 自动命名，随 cell 加载正常）。

### E4. SPCOCN-515 `ORIGIN.SYM.1.1` 缺失（双击 C481/C368/C423 电容）🔴 已处理

**现象**：双击任意 CAPACITOR 报 `parts missing: ORIGIN.SYM.1.1`。

**根因**：Cadence 打开带 part_table 的符号时隐式解析 `ORIGIN.SYM.1.1`
（参考库 Standard 符号）。输出包无 ORIGIN、用户环境系统库也未提供 →
环境缺失（Phase XVIII 已知悬案）。

**修复**：输出包**自包含**——`OutputManager.write_origin_lib()` 生成最小
origin 库（`origin/sym_1/symbol.css`：outline + PATH 属性）+ cds.lib
`DEFINE origin origin`。任何符号解析 ORIGIN.SYM.1.1 均命中。

---

## 二、V1 default 视觉问题（🟡 待实现/调优）

| # | 用户反馈 | 根因/分析 | 方案 |
|---|---------|----------|------|
| V1-1 | 整页只有一个 GND 且没连上 | gnd_distribution.enabled=false（默认关）；GND 符号引出线缺失 | 默认开 GND 分布；修 GND 引出线（E 系） |
| V1-2 | 大量 IO port 聚集页面右上角 | IOPORT 放置位置统一堆叠（无避让） | ioport 放置加避让/散开（R5 复用） |
| V1-3 | 电阻横向放置未连线、标签纵向；L15 未接 | 元件旋转方向与连线方向不匹配（源 EDF 旋转 R90 未处理或匹配错 symbol） | 旋转感知布局：元件方向随网络主流方向（R11 扩展） |
| V1-4 | J4 图标长条、几乎无连接 | J4 匹配到错误 cell（icon 错误）+ 引脚连接稀疏 | 匹配质量（R10 扩展）|
| V1-5 | S2 芯片图标消失只有标签 | E1（1158）→ 已修复 | 复测 |
| V1-6 | 电容纵向拉长线到总线 | 无总线感知的连线简化 | 总线感知布线（R8 扩展）|

## 三、V2 gnd_distribute 视觉问题（🟡）

| # | 用户反馈 | 分析 | 方案 |
|---|---------|------|------|
| V2-1 | GND 增多但放置乱、J4 与 GND 重叠 | place_gnd_symbol 避让不足（只避 outline，未避元件 body 全矩形） | 增强避让（加所有元件 outline） |
| V2-2 | GND 很多没接入电路（I74/I3002） | GND 符号位置与 WIRE 端点偏离 | 引出线贴合 WIRE 端点（坐标唯一原则） |
| V2-3 | 电线穿元件（R358）、电阻旋转错 | 避让不生效 + 旋转不匹配 | R5 全量接线（默认开）+ R11 方向 |
| V2-4 | "线头"明显 | 三段式 stub 未默认开（three_stage_stub 配置） | 默认开三段式 stub |
| V2-5 | 并联只并 GND 端，另一端没并 | R6 只对 GND 网聚类；用户要求**所有信号**先并联再引出 | R6 扩展到所有网（parallel_short 通用化）|
| V2-6 | 电线很长；并联范围太大 | parallel_short_dist=500 过大；max_wire_len 未生效 | 缩到 ≤200；max_wire_len 默认开 |
| V2-7 | GND 太稀少 | gnd 分布密度低 | 提高聚类密度（减小半径） |

## 四、V3 wire_simplify 问题（🟡）

| # | 用户反馈 | 分析 | 方案 |
|---|---------|------|------|
| V3-1 | 交叉点少了但电线没少（芯片不显示） | E1 连锁——mock 未加载→连线无法化简 | E1 修复后复测 |
| V3-2 | 部分页电线更多更长 | wire_simplify 逻辑对密集页反而拆线 | 分段阈值调优 |
| V3-3 | 电线无长度限制、无网络名 | max_wire_len/break_long 未生效（配置关） | 默认开 + 断口网络名标签 |

## 五、V4 net_name 问题（🟡 严重）

| # | 用户反馈 | 分析 | 方案 |
|---|---------|------|------|
| V4-1 | 无 IO port 也无网络名，电线拉到原位置悬空 | use_net_name 时 SIG_NAME 标签未生成在**悬空端** | net_name_endpoints（Phase XVIII 已实现，需接线到 csa_writer）|
| V4-2 | 悬空电线全部显示 gnd signal | **电线网络归属错误**：无标签孤立线被 Cadence 归默认网 gnd | 补 SIG_NAME（同 V4-1）或归回原网 |
| V4-3 | 悬空线 attribute 含几十条 value | 孤立线继承了多个引脚属性（归属混乱） | 同 V4-2 |
| V4-4 | 跨页网络名手动设置方法 | 用户操作咨询 | README 补操作说明（Edit→Find 等） |
| V4-5 | R53/R54 标签方向混乱 | 文本方向与元件方向不统一 | 标签方向随元件（text_layout 统一） |

## 六、test_spn g1-g4 实测（🟡）

| # | 用户反馈 | 分析 | 方案 |
|---|---------|------|------|
| T1 | page25-28 新建页复制代码无反应、保存清空 | 新建页需登记/或模板缺页面注册信息 | 用 page1-4 已成功；README 注明 |
| T2 | g1/g2 引脚序号竖、标称值横（方向不统一） | 模板中文本方向与 golden 不一致 | 按真实库文本方向修正模板 |
| T3 | g3/g4 报 543（GND\g / GND_POWER\g 被删） | E2（LASTPIN offset）→ 已修复 | 复测 g3/g4 |

---

## 七、代码审查发现（🟡 建议重构）

| # | 位置 | 问题 | 建议 |
|---|------|------|------|
| C1 | mock_icon_lib._append_pin_line | `plen`（_pin_line_len）已不再用于 L 起点（edge 固定 outline 边），但仍在构造/属性中传递 | 删除死参数或保留用于 pin tip 延长 |
| C2 | mock_icon_lib mock_outline | 旧分档逻辑（n≤12/n≤64/BGA）已被统一公式取代 | 确认无残留分档调用 |
| C3 | csa_writer._power_pin_offset | "css" 回退分支实际未被配置默认使用 | 统一改为动态读符号引脚 |
| C4 | 全项目 | 多轮迭代遗留 golden 硬编码（如 (50,100)）——本轮已修一处，需全局扫描 "golden" 字样 | 全局 grep golden/硬编码坐标审查 |
| C5 | xcon_writer | 生成器与 output_manager 存在两套 _build_xcon_content（内容完整版在 xcon_writer，模板版在 output_manager） | 合并单源 |

> 完整代码审查（全模块）与 V1-V4 实施排期：见 ROADMAP Phase XIX。

---

## 八、修复状态汇总

| 项 | 状态 | 验证 |
|----|------|------|
| E1 SPCOCN-1158 mock symbol.css | ✅ 已修复 | 63 cell 字号合法、1045 引脚 0 悬空 |
| E2 SPCOCN-543 GND_POWER | ✅ 已修复 | LASTPIN=body+(0,50) |
| E3 SPCOCN-543 mock SPN | ✅ 已修复（E1 连锁） | — |
| E4 SPCOCN-515 ORIGIN | ✅ 已处理 | origin 库自包含 + cds.lib DEFINE |
| V1-V4 视觉 | 🟡 需求清单待实施 | 见上表 |
| test_spn 模板 | 🟡 待修正方向 | E2 修复后复测 |
| 全量测试 | ✅ 735 passed | 含新增防回归 |

---

## 九、第二轮报错反馈（08-13 14:48，v1 default + gnd_distribute）

### 判定：旧包复测（修复前版本）

用户提供的报错（Windows 路径 `D:\26summer\cis2hdl\output_phaseXVIII_compare\v9_default\...`）
与 Phase XIX 修复**前**的报错逐字一致：
- SPCOCN-1158 `s2_ph/u10_ph/u6h_ph/.../j25_ph` line 11 "pin property not preceded by connection"
- SPCOCN-543 SPN 被删（U20/U18/U3/U14/U6H/U6I/U6E/U6C/U6D/U6G/U6A/U6B/U5/S1/S3/J26/U7 等）
- SPCOCN-515 _PH.SYM.1.1 库缺失（23 个 cell）

**交叉核对（新包 output_phaseXVIII_compare/v9_default/temp_lib）**：
- 报错清单 23 个 cell（S2/U1/U18/U20/U10/U11/U14/U3/U6H/U6I/U6C/U6D/U6E/U6G/U6A/
  U6B/U5/S1/S3/J25/J26/U15/U7_PH）**全部存在**
- 全量 63 个 mock cell **1158 语义 0 违规**（C/X 字号 ≥23、L 起点全在 outline 上）

**结论**：用户拷贝的是修复前包（D:\26summer 为 Windows 旧拷贝）。需重新拷贝
**最新 output_phaseXVIII_compare**（08-13 16:30 重建，含全部 Phase XIX 修复）复测。
修复前包的旧目录本地保留为 output_phaseXVIII_compare_v4_pre19。

> 已加入遗留动作：交付说明须显著提示"必须用最新包复测，勿用旧拷贝"。

---

## 十、第三轮深度调研：1158 隐藏根因 X "MOCK_TEXT"（08-13 15:00）🔴 已修复

### 判定修正
用户确认报错文件为 **12:27 生成（最新包）**——之前"旧包"判定不成立。
重新核对发现：本地 12:27 包 s2_ph 的 outline 已是修复后 `-100,200,100,-200`、
字号 23，但 Cadence **仍报 1158 line 11** → **上一轮 1158 修复不完整**。

### 深度调研实锤
- 真实库 X 指令类型**只有 3 种**：`"PIN_TEXT"`（64980 条）、`"VHDL_PORT"`（3）、
  `"HDL_PORT"`（3）——**无 "MOCK_TEXT"**
- mock 的 `X "MOCK_TEXT" "MOCK/模拟图标"`（line 10）是**未知 X 指令类型** →
  Cadence 解析 symbol.css 报错，错误定位到**后续第一个引脚行**（line 11 的 L）
  → 1158 "pin property not preceded by connection"
- 指令类型 vs 属性名：X 是指令名（必须 Cadence 已知）；P 是属性定义指令
  （容忍自定义属性名，Part Developer 机制）

### 修复
`mock_text_cmd` 默认 **"X" → "P"**（`P "MOCK_TEXT" "MOCK/模拟图标"`）：
- mock_icon_lib.py / config.py / routing.yaml 三处默认值
- 更正两处错误注释（"X 是真实库画文本先例" 实为错误认知）
- 全量 mock symbol.css 指令集现与真实库**同构**：{P, M, L, C, X(PIN_TEXT)}，X 仅 PIN_TEXT
- 验证：4 版本 X_MOCK_TEXT=0、P_MOCK_TEXT=63/63

### 交付
- **新目录名 output_phaseXIX_compare**（用户建议避免与 Windows 旧目录重名混淆）
- 4 版本：origin✓ xcon✓ 1158 语义 0 违规
- 全量 **807 passed / 6 skipped**

---

## 十一、第四轮反馈（08-13 15:54）——报错类清零确认 + 视觉类清点

### 进展确认（重大）
- **SPCOCN-1158 消失**（用户能描述引脚细节 → 芯片图标恢复显示）
- **SPCOCN-543 SPN 被删消失**（mock 芯片正常）
- 剩余报错：542（属性覆盖良性提示）+ p18 GND 543（镜像场景）+ ORIGIN（C34 双击）

### 本轮已修复（08-13 16:00）
| # | 修复 | 验证 |
|---|------|------|
| A3② | **GND_POWER plumbing 忽略 mirror**（p18 LASTPIN=body+(0,-50) 未命中 → 恒 (0,50)） | 全量 GND offset 0 异常 |
| B1 | **mock 标识改 T 指令 + 红色**（P 属性不渲染；63/63 cell "MOCK"） | T-MOCK 63/63 |
| B2-B4 | **芯片尺寸随最长引脚名自适应**（U6H outline -154,200,154,-450，容纳长名） | U6H/U6I/U6G 场景验证 |

### 遗留待办（已入 STATUS §40 总账 + ROADMAP Phase XX 排期）
- A5 ORIGIN：补全库结构 + Project Setup 手动添加指引确认
- A6 542：良性提示判断（属性值生效），待确认
- B5-B15：P0/P1 排期（stub 默认开/避让/网络名接线/J 匹配/并联全信号/IO port 就近/旋转感知/GND 增强/重叠消除/标签布局）
- C1：JEDEC/SN 源数据空（用户库补数据）

---

## 十二、Phase XX：mock_all 全量模拟图标（08-13 16:30 用户决策）

**需求**：J/T/U/S 等所有多引脚芯片与 connector，**无论是否匹配到 hdl_lib
真实符号，后端默认全部用模拟图标输出**；GUI 面板提供"模拟图标/手动选择
元件匹配"切换。

**根因（旧行为缺陷）**：`_is_passive_body` 把 connector/header/j/jumper 归为
passive（因真实库有符号）→ J 系列匹配成功时用真实库 → 用户实测 J4 错误图标
（匹配错 cell）+ 大量引脚悬空。

**实现**：
1. `TempLibCfg.mock_all: bool = True`（config.py + routing.yaml）
2. `_needs_placeholder`：mock_all 分支上移（在 passive 判定前）；passive
   保留名单排除 connector 类（`_is_connector_body` 新增）；2-pin passive
   refdes（L20/C20 变体 L_E）保留真实库
3. 验证：J4/J7/J9/J25 等 connector 全部 `FORCEADD J4_PH..1`；CAPACITOR 等
   passive 仍 `CAPACITOR..1`；mock cell 70→74

**GUI 待办**（P2-5）：面板加 mock_all 复选框 + 手动选择元件匹配。
