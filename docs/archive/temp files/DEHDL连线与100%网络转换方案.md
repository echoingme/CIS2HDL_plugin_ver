# DEHDL 原理图连线显示 + 100% 网络转换实现方案（研究稿）

> 研究人：齐活林（交付总监，独立实测）+ 高见远（架构师，已合并）+ 寇豆码（工程师，待合并）
> 日期：2026-08-10
> 聚焦：Design Entry HDL (SPB 16.6) 原理图内显示电路连接线与跨页连接符（**非 PCB Editor**）；
> 要求：网络和连接 **100% 转换成功**；正确导出网表 + export physical；暂不考虑 PCB 封装覆盖率。

---

## 〇、需求与判定标准

| 目标 | 成功标准 |
|------|----------|
| 原理图正确显示所有符号 | Cadence DEHDL 打开后所有元件符号可见、属性正确（无 SPCOCN-542 删除） |
| 原理图显示电路连接线 | CSA 中生成 WIRE 线段 + LASTPIN SIG_NAME 网络标注 |
| 跨页连接符 | 生成 GND_POWER/VCC_CIRCLE（\g 全局信号）与/或 offpage 符号 |
| 页面命名正确 | page.map 格式正确 + CSA EDIT PAGE NAME 与 hierarchy 一致 |
| 100% 网络转换 | con 网络数/连接数与源 pstxnet 完全一致（590/2821） |
| 正确导出网表 | Packager-XL Export Packager Files 成功，无 Error |
| export physical | 生成 pstx 三件套可被 Allegro/后续工具读取 |

---

## 一、Cadence 实测报错根因（已确认，待工程师合并细节）

### 1.1 页面命名错乱（P0）
- 现象：hierarchy viewer 标题全错，第1页显示 16-WIFI2G，第2页 17-WIFI5G...
- 实测证据：
  - 我们输出 `page.map` = `1 1 16-WIFI2G`、`2 2 17-WIFI5G`...（三列，第9行才是 01-Cover_Page）
  - 我们输出 `page1.csa` 的 EDIT PAGE NAME = `01-Cover_Page`（正确）
  - **真实 8367/04p4 工程 page.map 是两列**：`34 1`、`33 3`（源页码 + 索引），**无名称列**
- 根因链（总监已查实，conversion_engine.py）：
  1. `write_page_map()` 遍历 `design.pages` 枚举顺序（L668-670），而 `design.pages` 的构建
     顺序来自 CrossRef 循环 `for entry in catalog.all_entries()`（L1306）——**按 CrossRef CSV 行序**，
     第一个 entry 落在 16-WIFI2G 页 → page.map 第1行 = 16-WIFI2G
  2. CSA 文件名用 `_extract_page_number(page_id)`（csa_writer.py L549）——page1.csa 对应
     page_id 数字 1（01-Cover_Page），与 page.map 枚举顺序错位
  3. page.map 格式本身错误（三列 vs 真实两列）
- 修复方向：page.map 改两列格式（源页码 + 索引，索引与 CSA 文件编号一致）；design.pages
  按 page_id 数字排序后再枚举；或 CSA 文件编号与 page.map 索引统一使用同一排序键

### 1.1b 工程师根因细化（寇豆码实测，已合并）
- DSN 解析顺序 ≠ 页码顺序：`dsn/dsn_parser.py _read_all_pages()`（L146-235）按 DSN OLE 原始
  顺序 append，实测 = 16-WIFI2G, 17-WIFI5G, 09-SOC_GND, ... 01-Cover_Page，**无任何排序**
- page_id 只是发现序号 `1.{idx+1}`（与页码无关）
- **错误精确在 `output_manager.write_page_map()` L666-671**：用 `enumerate(pages)` 的 idx 当页码
  写第一列 → 产出 `1 1 16-WIFI2G`（应为 `16 16 16-WIFI2G`）、`9 9 01-Cover_Page`（应为 `1 1`）
- master.tag/.xcon/.cpc 编号均正确，**唯一错位就是 page.map 第一列**
- 修复：write_page_map 复用 `_extract_page_number`（从 page_name 前缀取数字），按页码排序后输出
  `页码 tab序号 名称`，预期：`1 1 01-Cover_Page / 2 2 02-Block_Diagram / ... / 16 16 16-WIFI2G`

### 1.2 SPCOCN-542 默认属性被删除（P1）
- 现象：`INFO(SPCOCN-542): The default property PART_NAME with value CH347 has been deleted`
  涉及 CH347/RF_SW/RJ45_2X2_LED 等，SPCOCN-545 提示 SET STICKY_ON
- 根因：CSA 用 `FORCEPROP 1 LAST VALUE/PATH/PART_NAME/LOCATION` 写属性，但这些属性在
  symbol.css 中是**默认属性**（`P "PART_NAME" "?"`），FORCEPROP 覆盖默认属性 → Cadence 删除
- 修复方向：a) symbol.css 不声明这些为默认属性；b) 用 STICKY 机制；c) 属性写入方式调整

### 1.2b 工程师根因细化（寇豆码实测，已合并）
- **规律自洽**：SPCOCN-542 只删 symbol.css **未声明**为默认属性的 FORCEPROP 属性
  - capacitor/resistor 的 symbol.css 声明全套（PART_NAME/PATH/VALUE/$LOCATION "?"）→ 不报错
  - ch347 只声明 $LOCATION/VALUE，未声明 PART_NAME/PATH → 报 PART_NAME/PATH 被删
  - rf_sw 几乎未声明 → 四项全删；rj45_2x2_led 未声明 → 四项全删
- 附带发现：参考工程单 section 元件写 `FORCEPROP 1 LAST $LOCATION Cxxx`（带 $，75 次），
  我们 csa_writer L433-456 对 section==1 写 `LOCATION`（无 $）→ 不合惯例，是 LOCATION 被删额外诱因
- 影响评估：SPCOCN-542 为 INFO 级，元件仍放置；PART_NAME 回退符号名（无影响）、PATH 回退
  自动路径（无影响）、LOCATION 回退可能影响位号、VALUE 回退默认（RF_SW 丢 PSW6M2 显示）
- 修复（按优先级）：
  1. 库侧主修复：为 ch347/rf_sw/rj45_2x2_led 的 symbol.css 补充默认属性声明
     （P "PART_NAME" "?" / P "PATH" "?" / P "LOCATION" "?" / P "VALUE" "?"）
  2. 代码修复：csa_writer L433-456 单 section 也写 `$LOCATION`
  3. 备选（不优先）：宏内 SET STICKY —— 参考工程无此用法，支持性存疑

### 1.3 跨页连接符缺失（P1）
- 现象：15-IOMUX J47 等无跨页连接符
- 根因（已确认）：**hdl_lib 无 offpage/inport/outport 符号** + 代码无生成逻辑
- 真实机制（参考 04p4 工程）：
  - 电源/地：`FORCEADD GND_POWER..1` + `FORCEPROP 3 LASTPIN (x y) SIG_NAME GND_POWER\g` + `HDL_POWER` 属性
  - `\g` 后缀 = global 信号 → 跨页同名网络自动相连（con 中 1083 个 pageNN_ 信号）
  - 普通信号跨页：offpage 符号（standard 库，symbol.css 含 P "OFFPAGE" "TRUE"）

### 1.3b 工程师根因细化（寇豆码实测，已合并）
- **J47/PWC3_A（厚膜电路）= 库缺失**：output_v2c 与 tests/fixtures 的 hdl_lib 均无 J47*/PWC*
  目录；page5 的 J4 PWC3_A 被错误匹配为 ORTHOGONAL_CONNECTOR..1 / 4X8_MALE（匹配回退而非 542）。
  用户已说明"没有就不用处理" → 可不处理
- **跨页连接符 = 代码缺失 + 库缺符号**：
  - 解析层有数据：`dsn/page_parser.py` L118 解析 ports（label port/global/offpage），PageIR
    有 ports 字段（ir/design.py L83），但 **csa_writer 从未使用 ports**（grep 无命中）
  - hdl_lib 无 port/offpage 专用符号（仅 connector/orthogonal_connector 物理连接器）
  - .con 的 nets 只由实例 pin_connections 聚合，无 port 网络表达
  - 修复方向（后续 feature）：① hdl_lib 增加 PORT/offpage 符号；② csa_writer 按
    page.ports / design.global_nets 生成 FORCEADD PORT + SIG_NAME；③ .con 补充 port 网络
  - 若目标只是"工程能打开不报错"，跨页连接符缺失不影响打开

---

## 二、CSA 连线格式（黄金参考已确认）

### 2.1 WIRE 导线
```
WIRE 16 -1 (-3675 3175)(-3675 3200);
```
- 格式：`WIRE <width?> <style?> (x1 y1)(x2 y2);`（实测 04p4 工程 361 条）
- 16 = 线宽/类，-1 = 样式标志

### 2.2 LASTPIN 引脚网络标注
```
FORCEPROP 3 LASTPIN (-3675 3175) SIG_NAME GND_POWER\g     ← 全局电源/地（\g）
FORCEPROP 2 LASTPIN (4950 5200) $PN 2                      ← 普通引脚编号（$PN）
```
- SIG_NAME = 网络名（\g 后缀 = global 跨页信号）
- $PN = 引脚号
- 位置 = 引脚连接点坐标

### 2.3 电源/地符号（跨页核心）
```
FORCEADD GND_POWER..1
(-3725 3075);
FORCEPROP 3 LASTPIN (-3675 3175) SIG_NAME GND_POWER\g
...
FORCEPROP 1 LAST HDL_POWER VDD_DDR
FORCEPROP 2 LAST CDS_LIB standard        ← 符号来自 standard 库
```

---

## 三、con 文件格式（重大发现：我们输出的 con 不兼容）

### 3.1 真实格式（8367.con / 04p4.con 一致）
```
(cells
  ("S2" "dc_dc" "hdl_lib" "sym_1"
    (terms ("T3" "bst" -1 -1 3) ("T4" "en" -1 -1 3) ...)
  )
)
(nets
  ("N2" "page1_gnd_power" -1 -1 0)
  ("N3" "unnamed_1_capacitor_i12_1" -1 -1 0)
  ...
)
(instances
  ("I1" "page1_i1" "S1"
    (pins
      ("M1" "T1" -1 -1 (conn ("0" -1 -1 "N388" -1 -1)))
      ...
    )
  )
)
```

### 3.2 我们输出的格式（不兼容）
```
(cells (cell "capacitor"))
(nets (net "netname" (instTerm (refdes "C59") (pin "2"))))
(instances (instance (refdes "C122") (cell "capacitor") (loc "29000 20500") (rotation "R0")))
```

### 3.3 差异总结
| 段 | 真实 | 我们 | 影响 |
|----|------|------|------|
| cells | (terms 带引脚定义) | 仅 cell 名 | 引脚信息缺失 |
| nets | 内部ID N2 + 显示名 | 直接网络名 | Packager-XL 读取依赖内部ID |
| instances | 实例ID I1 + pins/conn | refdes + loc/rotation | 连接关系无法表达 |

**结论：con 是自创简化格式，Packager-XL 可能无法正确读取 → 网表导出失败。这是"100% 网络转换"的核心技术障碍。**

### 3.4 补充证据：真实 page.map 格式（8367/04p4）
```
# 真实（两列：源页码 + 索引）
34 1
33 3
9 4
...
# 我们输出（三列：索引 序号 名称）—— 格式错误！
1 1 16-WIFI2G
2 2 17-WIFI5G
```
- 真实 page.map 无名称列，显示名由 CSA 的 EDIT PAGE NAME 提供
- 我们的 page.map 三列格式 + 顺序错位（16-WIFI2G 在第1行）→ hierarchy viewer 标题全错

### 3.5 补充证据：真实 xcon 格式（8367）
```
<design schemaType="nameBased" name="8367" view="sch_1">
  <lastids><instanceid>149</instanceid><netid>135</netid><insttermid>519</insttermid></lastids>
  <cells>
    <cell><id>S2</id><library>hdl_lib</library><name>dc_dc</name><view>sym_1</view>
      <terms><term><id>T3</id><name>bst</name><direction>inout</direction></term>...</terms>
    </cell>
  </cells>
  <nets>...</nets>
  <instances>...</instances>
</design>
```
- 真实 xcon：完整 cells/terms/nets/instances（XML 等价于 con）
- 我们的 xcon：仅 179 行空骨架，`<nets></nets><instances></instances>` 全空
- **结论：con/xcon/page.map 三个文件格式均需重构为真实 Cadence 格式**

---

## 四、100% 网络转换路径（P0 修复后现状）

- P0 修复后：pstxnet 解析 2821 连接（100%）、U6A-I 展开、EDIF 0 空名
- con instTerm 1466 → 2771（工程师实测）
- 但要达到"100% 转换成功 + 导出网表"，还需：
  1. con 格式重构为真实 Cadence 格式（上面 3.1）
  2. CSA 生成 WIRE + LASTPIN SIG_NAME（连线显示）
  3. 页面命名修复（page.map 两列格式 + 排序一致）

---

## 五、实现方案路线（总监综合，待成员细化合并）

### 5.1 页面命名修复（P0，先做）
- `write_page_map()` 改为两列格式：`<源页码> <索引>`，索引与 CSA 文件编号（page_id）一致
- design.pages 按 page_id 数字排序后再枚举（而非 CrossRef 顺序）
- 验证：page.map 第 N 行索引 N 对应 pageN.csa，Cadence hierarchy 显示名正确

### 5.2 con/xcon 格式重构（P0，核心）
- con writer 按真实格式重写：
  - cells：`("S1" "resistor" "hdl_lib" "sym_N" (terms ("T1" "1" -1 -1 3)...))` —— 从 hdl_lib symbol.css/pinlist 提取引脚
  - nets：`("N2" "netname" -1 -1 0)` —— 分配内部网络 ID
  - instances：`("I1" "pageN_i1" "S1" (pins ("M1" "T1" -1 -1 (conn ("0" -1 -1 "N388" -1 -1)))))` —— 实例引脚连接
- xcon writer 按真实 XML 格式同步（cells/terms/nets/instances 与 con 一致）
- 数据来源：pstchip（引脚定义）+ pstxnet（网络连接）+ CrossRef（坐标/refdes）

### 5.3 CSA 连线生成（P1）
- 元件后追加：
  - 电源/地：FORCEADD GND_POWER..1 / VCC_CIRCLE..1 + LASTPIN SIG_NAME xxx\g + HDL_POWER
  - 普通网络：WIRE 16 -1 (x1 y1)(x2 y2); 线段 + LASTPIN $PN + SIG_NAME（网络名）
- 跨页连接：\g 全局信号（网络名相同自动跨页相连）+ 可选 offpage 符号
- 需要：从 CIS 侧提取元件引脚坐标（DSN/EDIF 有坐标）→ 连线走线规划（正交布线）

### 5.4 SPCOCN-542 属性删除修复（P1）
- 方案 a：symbol.css 中将 PART_NAME/PATH/LOCATION 从默认属性改为普通属性（或 "?" 占位）
- 方案 b：CSA 中 FORCEPROP 属性值前置 SET STICKY 机制
- 方案 c：属性写入改为非默认（USER）属性
- 需在 Cadence 实测验证哪种生效

### 5.5 100% 网络验证方法
- 断言：con nets 数 == pstxnet 网络数（590）、conn 连接数 == pstxnet 连接数（2821）
- 回归测试：新增 con/xcon 格式解析测试（对照 8367 参考）

### 5.6 跨页连接两种实现方式（实测 04p4 工程）
| 方式 | 符号 | 语法 | 适用 |
|------|------|------|------|
| A. 全局电源/地 | GND_POWER / VCC_CIRCLE（standard 库） | `FORCEADD GND_POWER..1` + `FORCEPROP 3 LASTPIN (x y) SIG_NAME GND_POWER\g` + `HDL_POWER` 属性 | 电源/地网络跨页 |
| B. offpage 符号 | offpage / inport / outport（standard 库，symbol.css 含 `P "OFFPAGE" "TRUE"`） | FORCEADD offpage + 网络名属性 | 普通信号跨页 |

- 04p4 工程实测：con 中 1083 个 pageNN_ 前缀网络名（跨页信号），CSA 中 18 GND_POWER + 22 VCC_CIRCLE
- \g 后缀 = global 信号：同名网络在任意页出现即自动连接（DEHDL 全局信号机制）
- 普通信号跨页：放置 offpage 符号（含 OFFPAGE 属性），网络名通过符号关联

---

## 六、架构师（高见远）研究报告（已合并）

### 6.1 核心结论：DEHDL 连线完全可行，SPCOCN-1891 是错误诊断
- 历史 v0.9.0 用 `PAINT WIRE;` 命令（CSA 中不存在）→ 报 SPCOCN-1891 → 错误地推断"16.6 不支持连线"
- 真实 DEHDL 用 `WIRE 16 -1 (x1 y1)(x2 y2);`（4 个真实 Cadence 工程逆向证实，16.6 完全支持）
- **结论：应推翻 v0.9.0 移除连线的决策，重做连线生成**

### 6.2 三条核心命令（真实示例）
```
WIRE 16 -1 (x1 y1)(x2 y2);              ← 画导线（16=黄色信号线）
DOT 1 (x y);                             ← 连接点（T 形/十字交叉）
FORCEPROP N LASTPIN (x y) $PN <n>        ← 引脚位置+引脚号
FORCEPROP N LASTPIN (x y) SIG_NAME <net> ← 引脚附网络名
```
- 连接机制 = **几何重合**：WIRE 端点与 LASTPIN 坐标精确重合，DEHDL 自动建立连接
- 无独立"网络标号命令"（TEXT/LABEL/ALIAS 在真实 csa 中 grep 均为 0）
- 颜色：原理图页信号线统一 16

### 6.3 配套文件（当前完全缺失，DEHDL 加载必需）
- **pageN.csv**：`FILE_TYPE = CONNECTIVITY;` + 网络清单 `0"NC"; 1"GND_POWER\g";` + 每实例引脚→网络编号映射 —— **当前完全不生成**
- **pageN.cpc**：`#ISCELL standard gnd_power * page1_i10`（ISCELL=虚拟元件：电源/端口）+ `#CELL hdl_lib capacitor * page1_i12`

### 6.4 跨页连接（standard 库端口符号）
- 符号：`standard/{ioport,inport,outport}`（`X "HDL_PORT" "INOUT"` + `P "OFFPAGE" "TRUE"`）
- CSA：`FORCEADD IOPORT..1` + PATH + OFFPAGE TRUE + LASTPIN HDL_PORT/VHDL_PORT + CDS_LIB standard + WIRE 接引脚
- 跨页机制：同名网络自动合并；电源地带 `\g` 后缀（con scope=2、xcon netScopes global）
- **当前 hdl_lib 缺 ioport/inport/outport 和 standard 库** → 需拷入 + cds.lib DEFINE

### 6.5 ★ 最严重：con 不是 Cadence 格式（与总监独立发现一致）
```
# 真实：("S2" "dc_dc" "hdl_lib" "sym_1" (terms ...)) + ("N2" "net" -1 -1 0) + ("I1" ... (pins (conn ...)))
# 我们：(cell "capacitor") + (net "x" (instTerm ...)) + (instance ...) —— 格式全错
```
Packager-XL 无法读取 → **必须先重写 con 生成器**

### 6.6 全部缺口清单（按文件）
| 文件 | 现状 | 缺口 |
|---|---|---|
| pageN.csa | 仅 FORCEADD/属性 | 无 LASTPIN $PN/SIG_NAME、WIRE、DOT、IOPORT |
| pageN.csv | 不生成 | 页面网络/引脚连接文件，必补 |
| pageN.cpc | 仅 C SIZE PAGE | 缺实例条目 |
| 5015.con | 自创格式 | 重写 Cadence S-expr |
| 5015.xcon | 全空 | 填 lastids/cells/nets/instances/netScopes |
| cds.lib | 缺 standard | 端口符号库 |
| hdl_lib | 有 gnd/vcc | 缺 ioport/inport/outport |

### 6.7 代码层根因（精确到行）
1. `output_manager._build_con_content()` 自创格式（L316-368）
2. `output_manager._build_xcon_content()` 空 XML（L594-631）
3. `csa_writer._build_csa_content()` 不写 LASTPIN/WIRE/DOT（L278-487）
4. `edif_parser.extract_pin_net_map()`（2771）未 merge 进 PageIR pin_connections（con 只拿 1466）
5. `dsn_parser._build_page_ir()` 丢弃 off_pages（L730+）
6. 网络名未清洗（$47N776、&1V8_BUCK 非法名需转换；电源网加 \g）

### 6.8 网表导出充分条件清单
1. ❌ con 完整且格式合法（cells/terms/nets/instances/pins/conns + lastIds）
2. ❌ CSA 可解析（WIRE/LASTPIN/DOT 用真实语法）
3. ✅ cds.lib 存在（缺 standard）
4. ✅ 符号库 88 cell 够元件（缺 port 符号）
5. ❌ 页面端口与全局网络登记（con scope=2 / xcon netScopes）
6. ✅ dcf/cpm/hdldirect/master.tag/module_order 已有
7. ❌ pageN.csv 连接文件

### 6.9 优先级（架构师建议 + 工程师修复单合并）
**工程师 P1/P2/P3 修复单（本轮 Cadence 报错修复）**
| 优先级 | 任务 | 位置 |
|:---:|------|------|
| P1 高 | write_page_map 页码取错（enumerate idx → 应取 page_name 前缀页码并排序） | output_manager.py L666-671 |
| P2 中 | 库侧补 ch347/rf_sw/rj45_2x2_led symbol.css 默认属性声明（PART_NAME/PATH/LOCATION/VALUE "?"） | hdl_lib/{ch347,rf_sw,rj45_2x2_led}/sym_1/symbol.css |
| P2 中 | csa_writer 单 section 改用 $LOCATION | csa_writer.py L433-456 |
| P3 低 | J47 库缺失（不处理）；跨页连接符代码未实现（单独立项） | — |

**架构师 P0-P2 清单（连线 + 100% 网络）**
| 优先级 | 任务 |
|:---:|------|
| P0 | EDIF 注入 PageIR（1466→2771）+ con 重写 + xcon 填充 + pageN.csv 生成 + csa LASTPIN |
| P0 | csa 输出 `WIRE 16 -1`（DSN 线段优先 + **拓扑合成兜底**——HG5015 DSN 线段仅 16 段不可靠） |
| P1 | DOT + 网络名清洗 + 电源网 \g + con scope=2 |
| P1 | standard 库 port 符号 + IOPORT 生成 + cds.lib DEFINE standard + cpc 实例 |
| P2 | xcon netScopes、总线支持、多 section 引脚偏移 |

### 6.10 互联网调研结论
- SPCOCN-1891 = CSA 宏语法错误（非"不支持连线"）；SPCOCN-542 无公开文档
- 无现成 CSA 生成器可抄（OpenOrCadParser 只解析 DSN；schematic-file-converter 不支持 Cadence 输出）→ **必须自研，格式来自真实工程逆向**
- 有用资料：DEHDL Wire 菜单（Draw/Route/Signal Name/Bus Name）、端口放置（Component-Add INPORT/OUTPORT）、\G 全局信号机制

---

## 七、待合并（工程师寇豆码：页面命名根因 + SPCOCN-542 细节 + 跨页连接符库检查）

## 附录：P0-B 实施精确格式模板（2026-08-10 总监逆向验证版）

> 本附录由交付总监从 8367/04p4 真实工程逆向，供 P0-B 实现直接照抄。

### A. con 文件完整模板
```
(
  (version 16.6)
  (tool
    (creator "conceptHDL")
    (last "conceptHDL")
  )
  (library "5015_lib")
  (design "5015"
    (lastIds
      (lastInstanceId 890)
      (lastNetId 590)
      (lastInstTermId 2771)
    )
    (cells
      ("S2" "capacitor" "hdl_lib" "sym_1"
        (terms
          ("T3" "1" -1 -1 3)
          ("T4" "2" -1 -1 3)
        )
      )
      ...
    )
    (nets
      ("N1" "gnd_power" -1 -1 2 )      ← scope=2 全局（N1 保留给地）
      ("N2" "page1_3V3" -1 -1 0 )      ← scope=0 局部
      ...
    )
    (alias
    )
    (instances
      ("I1" "page1_i1" "S2"
        (pins
          ("M1" "T3" -1 -1
            (conn
              ("0" -1 -1 "N7" -1 -1)
            )
          )
          ...
        )
      )
      ...
    )
  )
)
```

### B. xcon 完整模板（8367.xcon 结构）
```xml
<schema xmlns="http://www.cadence.com/spb/csschema"
	xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
	xsi:schemaLocation="http://www.cadence.com/spb/csschema CSSchema002.xsd">
  <header>
    <schemaVersion>16.6</schemaVersion>
    <creatorTool>conceptHDL</creatorTool>
    <modifierTool>conceptHDL</modifierTool>
    <modificationTime>2026-08-10T00:00:00</modificationTime>
    <savedLibrary>5015_lib</savedLibrary>
  </header>
  <designs>
    <design schemaType="nameBased" name="5015" view="sch_1">
      <lastids>
        <instanceid>890</instanceid>
        <netid>590</netid>
        <insttermid>2771</insttermid>
      </lastids>
      <cells>
        <cell>
          <id>S2</id>
          <library>hdl_lib</library>
          <name>capacitor</name>
          <view>sym_1</view>
          <parameters></parameters>
          <terms>
            <term><id>T3</id><name>1</name><direction>inout</direction></term>
          </terms>
        </cell>
      </cells>
      <nets>
        <net><id>N1</id><name>gnd_power</name></net>
        <net><id>N2</id><name>page1_3V3</name></net>
      </nets>
      <instances>
        <instance>
          <id>I1</id>
          <cellid>S2</cellid>
          <name>page1_i1</name>
          <parameters></parameters>
          <masks></masks>
          <powers></powers>
          <pins>
            <pin>
              <id>M1</id>
              <termid>T3</termid>
              <connections><connection net="N7" /></connections>
            </pin>
          </pins>
        </instance>
      </instances>
      <netScopes>
        <netScope ref="gnd_power">
          <pageScope number="1"><scope>global</scope></pageScope>
        </netScope>
      </netScopes>
      <pages>
        <page number="1">
          <physicalPageNumber>1</physicalPageNumber>
          <errorStatus>false</errorStatus>
          <nets><net ref="gnd_power"></net></nets>
          <instances><instance ref="i1"></instance></instances>
        </page>
      </pages>
    </design>
  </designs>
</schema>
```

### C. ID 分配规律（实测 8367）
| 段 | 起始 | 规律 | lastIds |
|----|------|------|---------|
| cells | S2 | 每个唯一 cell 一个 ID，按出现序 | — |
| terms | T3 | 每 cell 引脚递增 | — |
| nets | N1=全局地, N2 起局部 | scope=2 全局（\g 网络）在前 | lastNetId |
| instances | I1 | 实例名 pageN_iX | lastInstanceId |
| pins | M1 | 每实例引脚 | — |
| conn | — | 引用网络 ID Nxxx | lastInstTermId = pins 总数 |

### D. 全局网络判定
- con scope=2 + xcon netScope global 的 = 电源/地网络（\g 后缀：GND_POWER\g、DC3.3V\g）
- scope=0 = 页面局部网络
- netScope ref 用短名（去 \g）：gnd_power/vcc_12/vdd_33

### E. pageN.csv 模板（04p4 page9 实测）
```
FILE_TYPE = CONNECTIVITY;
{Allegro Design Entry HDL 16.6-S003 (v16-6-112R) 1/28/2013}
"PAGE_NUMBER" = 14;
0"NC";
1"REG_LED";
2"GND_POWER\g";
3"DC12V\g";
...
%"GND_POWER"
"1","(-3725,3075)","0","standard","I1";
;
CDS_LIB"standard"
JEDEC_TYPE"0402R-S"
...
"GND"3;
%"CAPACITOR"
"1","(-2875,3325)","0","hdl_lib","I10";
;
VALUE"100NF"
$LOCATION"C133"
...
"1"2;
```
- 网络编号清单：0=NC，后续每个唯一网络名一个编号（\g 保留）
- 实例段：`%"<cell名>"` + `"<引脚>","(<x>,<y>)","0","<库>","I<n>";` + `;` + 属性行 + `"<引脚>"<网络编号>;`

### F. pageN.cpc 模板（04p4 page9 实测）
```
#ISCELL
  hdl_lib c#20size#20page *
  *
#ISCELL
  standard gnd_power *
  page14_i1
#CELL
  hdl_lib capacitor *
  page14_i10
```
- #ISCELL = 虚拟元件（电源/端口/页框），#CELL = 真实元件
- 格式：`#ISCELL\n  <库> <符号名> *\n  <pageN_iX>`
