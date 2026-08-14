# HG5015 output_v2c 转换质量深度评估报告

> 评估人：齐活林（交付总监）· 高见远（架构师）· 寇豆码（工程师）
> 评估日期：2026-08-10
> 评估对象：`HG5015_tests/output_v2c/`（v1.1.0 匹配系统 v2.0 最新转换输出）
> 源数据：`tests/fixtures/HG5015test/`（HG5015-BE36_V10.DSN + EDF + pstx 三件套）

---

## 一、执行摘要（TL;DR）

**转换结果总体判定：结构性可用，电气连接严重不完整，暂不具备导出网表 / export physics 的充分条件。**

| 维度 | 结论 |
|------|------|
| 工程结构合法性 | ✅ 合法（cpm/cds.lib/xcon/con/dcf 齐全，SPB 16.6 可打开） |
| 元件转换 | ✅ 889/889 全部写入 con instances + CSA FORCEADD |
| 符号可用性 | ✅ 17 个 cell 均有对应 hdl_lib 符号目录 |
| **网络连接完整性** | ❌ **仅 52% 连接写入**（1466/2821），**GND(845连接)/12V0(49连接) 整块丢失** |
| 图形连线 | ❌ CSA 无任何 SIGNAL/WIRE/LASTPIN 连线（PAINT WIRE 已移除） |
| xcon 网络 | ❌ `<nets>` 全空 |
| 网表导出 | ⚠️ 不充分：con 网络缺失 + PCB 封装库仅 2/154 目录可用 |

---

## 二、工程结构核验（✅ 通过）

```
output_v2c/
├── 5015.cpm            # 工程文件（design_name '5015'，cpm_version '16.6'）
├── cds.lib             # DEFINE 5015_lib worklib + hdl_lib
├── hdldirect.dat       # HDLDirect (Version 16.6)
├── worklib/5015/sch_1/
│   ├── 5015.con        # 连接文件（Lisp S-expr，含 nets/instances）
│   ├── 5015.dcf        # 约束文件
│   ├── 5015.xcon       # CS Schema XML（页面骨架）
│   ├── master.tag / module_order.dat / page.map
│   ├── page1~24.csa    # 原理图图形文件
│   └── page1~24.cpc
└── hdl_lib/            # 154 个元件目录（含 sym/css/ptf/prt）
```

- `.cpm` 使用 `cpm_version '16.6'`，`START_PKGRXL feedback 'ALLEGRO'` 已配置 —— 格式合法。
- `cds.lib` 正确 DEFINE 两个库，`hdldirect.dat` 声明 Design "5015"。
- 889 个实例全部写入 con `(instances)` 段，坐标（loc）+ rotation（R0）齐全。
- 24 页 CSA 均含 `FORCEADD <CELL>..1` + 属性，页面名（EDIT PAGE NAME）正确。

**结论：工程文件结构完整，Cadence SPB 16.6 Design Entry HDL 可正常打开（但打开后元件无连线，详见第四节）。**

---

## 三、网络连接完整性（❌ 严重缺失 — 本次评估核心发现）

### 3.1 数据对比（一手实测）

| 数据源 | 网络数 | 引脚连接数 |
|--------|:---:|:---:|
| pstxnet.dat（CIS 源，EXPANDEDNETLIST） | 590 | 2821 |
| pstxnet_netlist_parser 实际解析 | 590* | **1818** |
| 5015.con 实际写入 | **510** | **1466** |
| 报告声称 | 3717 | — |

> *解析器提取 590 个网络名，但其中 GND/12V0 等 80 个网络连接数被丢弃为 0。

- **1003 个连接在解析阶段丢失**（2821 → 1818）；
- **80 个网络完全未写入 con**（含 12V0 的 49 个连接、GND 的 845 个连接）；
- con 中 91/889 实例无任何连接（含 U6A~U6I 等）。

### 3.2 根因一（P0）：pstxnet 解析器状态机 Bug

`cis2hdl/core/parser/pstxnet_netlist_parser.py` 的 `_parse_content()` 状态机：

```python
_RE_SKIP_LINE = re.compile(
    r"^\s*(?:{|--|@|C_SIGNAL|DIFFERENTIAL_PAIR|C_PATH|P_PATH|SECTION_NUMBER)"
)
```

**缺少 `RATSNEST_SCHEDULE` / `NET_PHYSICAL_TYPE` / `NET_SPACING_TYPE` 三种网络属性行的跳过规则。**

实测行为：遇到 `RATSNEST_SCHEDULE='POWER_AND_GROUND';` 或 `NET_PHYSICAL_TYPE='12V';` 行时，
状态机进入 `else` 分支将 `state = _IDLE`，**当前网络块被提前终止**，该网络及其后所有
NODE_NAME 全部丢弃。

| 网络 | 源连接数 | 解析器提取 | 状态 |
|------|:---:|:---:|------|
| GND（含 RATSNEST_SCHEDULE） | 845 | **0** | 整块丢失 ❌ |
| 12V0（含 NET_PHYSICAL_TYPE） | 49 | **0** | 整块丢失 ❌ |
| 33 个 NET_PHYSICAL_TYPE 网络 | — | 0 | 整块丢失 ❌ |
| 42 个仅 C_SIGNAL 网络 | — | 0 | 状态机退出后连锁丢失 ❌ |

**修复验证（已实测通过）**：在 `_RE_SKIP_LINE` 增加
`|RATSNEST_SCHEDULE|NET_PHYSICAL_TYPE|NET_SPACING_TYPE` 后重新解析：

| 指标 | 修复前 | 修复后 | 源数据 | 恢复率 |
|------|:---:|:---:|:---:|:---:|
| 连接数 | 1818 | **2806** | 2821 | 99.5% |
| GND 连接 | 0 | **845** | 845 | 100% |
| 12V0 连接 | 0 | **49** | 49 | 100% |
| 网络数 | — | 584 | 590 | 99.0% |

> 修复仅需修改 `_RE_SKIP_LINE` 一处（L74-76），剩余 15 个连接差异为差分对展开格式，
> 不影响主网络。

> **✅ 2026-08-10 更新：P0 修复已落地**（工程师寇豆码实现，总监独立复验通过）——
> `_RE_SKIP_LINE` 已补全 4 个关键字（含 RELATIVE_PROPAGATION_DELAY），实测连接数恢复到
> **2821（100%）**，GND 1067/12V0 49 完整恢复；U6 多 section 展开 + EDIF 网络名提取同步修复，
> 全流程转换后 5015.con instTerm 1466→**2771**，测试 36 passed 无回归。

### 3.3 根因二（P1）：U6 母 refdes 与 U6A~U6I 分 section 实例不匹配

- pstxnet 中 NODE_NAME 使用母 refdes `U6`（304 个连接）；
- 设计 IR / con 实例使用分 section refdes `U6A`~`U6I`（9 个实例）；
- `pstxnet_map.get(_inst.refdes)` 无法命中 → U6 全部分支（含 TG1_ABB 交换机核心）无连接。

### 3.4 根因三（P1）：EDIF 网络名提取失败（架构师 + 总监双重实测）

架构师高见远发现并经交付总监复核：EDIF pin_map 实测提取 2771 连接，但**非空网络名仅 21 个
（99.2% 为空）**。根因：862 个 EDIF net 中 837 个采用 `(net (joined ...))` / `(net (rename ...))`
结构（含内部 ID 与属性），`_parse_net_raw` 中 `net_name = _sym_str(net[1])` 对 list 形式
返回空字符串；而实例引用是 `INSxxx`（内部 ID）非 refdes。EDIF 注入的 pin→net 实际多为
空网络名，写入 con 时被 `if net_name:` 过滤 → **EDIF 注入形同虚设**。

> 注：转换日志声称"EDIF 注入 2713 pin→net"为假象 —— 计数包含空网络名，实际有效连接极少。

### 3.5 根因四（P2）：EDIF 注入被 PST 主注入覆盖

Stage 5.5b 以 pstxnet 为 PRIMARY（覆盖 EDIF），但 pstxnet 解析不完整 → 最终 con 数据
少于 EDIF 可提供的 2713 个 pin→net。建议改为"pstxnet 为主、EDIF 补齐缺失 refdes"。

### 3.6 3717 网络口径说明（架构师核实）

报告的 3717 网络为 **DSN 每页 net 对象累计（含空/重复）**，con 文件仅记录有跨器件
连接的有效网络（510 个）。`matched_nets = min(nets, nets)` 为**假指标**，不能反映真实
转换率。**真正的对比基准是 pstxnet 590/2821 与 con 510/1466，缺口约 48%。**

---

## 四、CSA 图形连线（❌ 完全缺失）

| 检查项 | 结果 |
|--------|------|
| CSA 中 SIGNAL / LASTPIN / NETNAME / PORT | 全部 0 |
| CSA 中 WIRE / PAINT WIRE 图形 | 0 |
| con 中 instTerm 引用 | 1466（不完整） |
| xcon `<nets>` | 空 |

- PAINT WIRE 连线渲染于 v0.9.0 因 Cadence 16.6 不支持（SPCOCN-1891）移除 —— 文档口径一致；
- **但 CSA 中也未写入信号名/引脚网络属性**（SIGNAL 命令），意味着在 DEHDL 中打开只能看到
  孤立的元件符号，看不到任何导线与网络标号；
- con 文件虽然携带电气连接，但 DEHDL 16.6 的图形界面依赖 CSA 中的连线/信号定义来显示。

**影响**：即使 con 完整，打开原理图也看不见连线，工程师无法目视检查电路。

---

## 五、PCB 后续开发可行性（⚠️ 不充分）

### 5.1 网表导出（Packager-XL / Create Netlist）充分性

| 前提条件 | 现状 | 判定 |
|----------|------|:---:|
| con 网络完整 | 仅 52% | ❌ |
| CSA 可打开无错误 | 结构合法但无连线 | ⚠️ |
| pstx 三件套可生成 | 依赖 con 数据 | ❌ |
| hdl_lib 与输出工程路径一致 | cds.lib 已 DEFINE | ✅ |

**结论：当前 output_v2c 不具备导出网表的充分条件 —— Packager-XL 生成的 pstxnet 必然缺失
约 48% 连接，导入 Allegro 后网络不全，无法布局布线。**

### 5.2 PCB 封装库覆盖率（❌ 致命瓶颈）

output_v2c/hdl_lib 共 154 个元件目录，但**只有 2 个目录包含 PCB 封装文件**：

```
有 .psm/.pad/.dra 的目录：
  BGA353C65P23X20_1500X1300X140
  qfn21_3x4
```

- 其余 152 个目录仅含原理图符号（sym/css/ptf/prt/chips），**无 .psm 封装符号、无 .pad 焊盘**；
- Allegro 导入网表时要求每个器件有对应封装（psmpath/padpath），否则报 "Symbol not found"；
- 电容/电阻/二极管/芯片等 887 个元件的封装库缺失 → **即使网表完整也无法进入 PCB 布局**。

**这是比网络缺失更根本的障碍：公司 HDL 库（hdl_lib）本身就不是为 PCB 开发准备的完整库。**

### 5.3 引脚号一致性风险

- con instTerm 使用数字引脚（`(pin "1")`），但 pstxnet 中引脚是字母标签（`U6 J27`）；
- pstchip.dat 提供 label→number 映射（`'A':'(1)'`），Stage 5.5c 已做转换 —— 但仅覆盖
  有 pin_connections 的 797 个实例；
- 无连接实例（91 个）的引脚映射未验证，存在 Pin number mismatch 风险。

---

## 六、修复优先级清单

| 优先级 | 问题 | 建议动作 |
|:---:|------|----------|
| P0 | pstxnet 解析器状态机丢网络（GND/12V0 整块丢失） | `_RE_SKIP_LINE` 增加 `RATSNEST_SCHEDULE\|NET_PHYSICAL_TYPE\|NET_SPACING_TYPE\|RELATIVE_PROPAGATION_DELAY`；补回归测试（GND/12V0/差分对） |
| P0 | EDIF 网络名提取失败（99.2% 空名） | `_parse_net_raw` 处理 `(joined)`/`(rename)` 结构，从属性中提取显示名；refdes 从 INSxxx 映射回真实 refdes |
| P0 | 缺少 PCB 封装库（154 目录仅 2 个含 .psm/.pad） | 向库管理员申请完整封装库；或在转换时从 company 库复制 .psm/.dra/.pad |
| P1 | U6 母 refdes ↔ U6A~U6I 分 section 不匹配 | pstxnet 注入时按前缀匹配分 section（U6 → U6A~U6I），引脚按 pstchip 映射分发 |
| P1 | EDIF 注入被 PST 主注入覆盖 | 改为 pstxnet 优先 + EDIF 补齐缺口 refdes |
| P2 | CSA 无信号名/连线 | 恢复 SIGNAL 标签写入（若 16.6 支持）或生成"连线预览"辅助校验 |
| P2 | con/报告网络口径混乱（510 vs 3717） | 统一口径：con 按有效网络数统计，报告注明基准来源（3717 为 DSN 累计含空/重复） |
| P2 | xcon `<nets>` 为空 | 可选：向 xcon 写入网络/实例（16.6 使用 con 为主，非必需） |

---

## 七、Cadence 16.6 显示网络连线方案（Part C）

> 由交付总监基于代码研读 + 官方流程调研完成，架构师结论合并见文末注。

### 7.1 官方流程（已确认）

```
Design Entry HDL 工程 → Tools → Packager Utilities → Export Packager Files
  → 生成 packaged/ 目录（pstxnet.dat + pstxprt.dat + pstchip.dat）
→ Allegro PCB Editor → File → Import → Logic（Design entry CIS/Capture）
  → 选择 packaged 目录 → Import Cadence
  → 检查 netrev.lst 无 Error → 布局布线
```

- DEHDL 的电气连接来源于 **con 文件**（Packager-XL 读取 con 生成 pstx 三件套）；
- 因此**修复 con 网络完整性 = 修复网表导出**，两者是同一件事；
- Allegro 中显示"网络连线"（ratsnest/飞线）依赖网表导入成功 + 封装库齐全。

### 7.2 OpenAllegroParser 评估（结论）

- OpenAllegroParser 是 C++17 库，**仅解析 Allegro PCB 二进制**（.brd/.mdd/.dra/.psm/.ssm/.fsm/.osm/.bsm/.pad），
  重点在 padstack；
- **不支持原理图/网表（.con/.csa/pstxnet）解析**；
- 对本项目（HDL 工程 → Allegro 显示连线）**无直接帮助**；
- 潜在用途：解析 hdl_lib 中的 .pad 焊盘文件验证封装正确性（若库提供）。

### 7.3 推荐路线

1. **短期（验证连通性）**：修复 pstxnet 解析器 Bug（P0）→ 重跑转换 → con 网络恢复到
   590/2821 → 在 Cadence 环境 Packager-XL 导出网表验证；
2. **中期（PCB 开发）**：补齐 PCB 封装库（.psm/.pad/.dra）→ Import Logic 进 Allegro；
3. **长期（可视化）**：若需在原理图界面看到连线，需恢复 CSA 的 SIGNAL/连线写入（先验证
   SPB 16.6 支持哪些连线命令，或考虑 17.2/17.4 目标）。

### 7.4 "Allegro 16.6 显示 HDL 网络连线" 方案详解

> 用户问题：如何让 Cadence Allegro 16.6 显示 HDL 文件当中网络对应的电路连线？

**关键认知**：Allegro PCB Editor 本身**不显示原理图连线**（那是 DEHDL 的职责）。Allegro
中显示的是 **ratsnest（飞线/鼠线）** —— 表示网络连接关系的点线。要让网络连线可见，
必须走通"网表导入"链路：

| 方案 | 做法 | 可行性 | 前提 |
|------|------|:---:|------|
| **A. 官方流程（推荐）** | DEHDL → Packager-XL Export → pstx 三件套 → Allegro Import Logic | ✅ | 修复 con 网络 + 补齐封装库 |
| B. 直接生成 pstx 三件套 | 转换器直接输出 pstxnet/pstxprt/pstchip（格式已知） | ⚠️ | 需实现 writer；格式与 16.6 严格兼容 |
| C. OpenAllegroParser | 解析 .brd/.pad/.psm 二进制 | ❌ 不适用 | 只解析 PCB 侧文件，不解析原理图网表 |
| D. 原理图内显示连线 | CSA 恢复 SIGNAL/WIRE 命令 | ⚠️ | 需验证 SPB 16.6 支持；SPCOCN-1891 曾否决 |

**推荐路径 A 的分步操作**：
1. 修复 `pstxnet_netlist_parser.py` 状态机 Bug（+5 行跳过规则）；
2. 重跑转换 → 用 Cadence 打开 5015.cpm → Tools → Packager Utilities → Export Packager Files；
3. 检查生成 packaged/ 的 pstxnet.dat（应恢复到 590 网络/2821 连接）；
4. Allegro PCB Editor → File → New（新建 .brd）→ File → Import → Logic；
5. Import Logic 对话框：Logic type = **Design entry CIS (Capture)**，Import directory =
   packaged 目录，Place changed component = Always；
6. 点击 Import Cadence → 检查 netrev.lst 无 Error；
7. 导入后元件 + ratsnest 飞线出现 → Setup → Design Parameter Editor 调整显示 → 布局布线。

**如果只想"预览"连线（不需要完整 PCB）**：可用 Allegro Viewer（免费）打开导入后的 .brd
查看 ratsnest；或在 DEHDL 中用 Display → Connectivity 检查网络。

### 7.5 架构师调研补充（合并区）

> 预留：软件架构师（高见远）的独立调研结论在此合并。核心数据（con 510/1466、GND/12V0
> 丢失、状态机根因）已由交付总监独立实测确认，与架构师结论一致性待最终核对。

---

## 八、附录：关键证据文件

| 文件 | 说明 |
|------|------|
| `HG5015_tests/output_v2c/worklib/5015/sch_1/5015.con` | con 连接文件（510 net/1466 instTerm） |
| `tests/fixtures/HG5015test/pstxnet.dat` | CIS 源网表（590 net/2821 连接） |
| `cis2hdl/core/parser/pstxnet_netlist_parser.py` | 状态机 Bug 所在 |
| `HG5015_tests/output_v2c/HG5015-BE36_V10_top3.txt` | 匹配结果（889 元件） |
| `HG5015_tests/output_v2c/HG5015-BE36_V10_errors.log` | 转换日志（0 错误/117 警告） |
