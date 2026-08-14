# Phase XI 规划稿（草稿，待架构师报告合并）

## Part V Phase XI：DEHDL 原理图连线显示 + 100% 网络转换 + 网表导出（2026-08-10 规划）

> 本节由软件交付团队（齐活林/高见远/寇豆码）基于：
> - 用户第二轮需求（DEHDL 原理图内显示连线与跨页连接符，非 PCB Editor；网络 100% 转换；正确导出网表 + export physical）
> - `docs/archive/temp files/HG5015_output_v2c_质量评估报告.md`
> - `docs/archive/temp files/DEHDL连线与100%网络转换方案.md`
> - Cadence 实测报错 `output_v2c/errors.txt`（用户提供）

### 需求背景与目标

| 目标 | 成功标准 |
|------|----------|
| 原理图正确显示所有符号 | DEHDL 打开后元件符号可见、属性正确（无 SPCOCN-542） |
| 原理图显示电路连接线 | CSA 生成 WIRE 16 -1 + LASTPIN $PN/SIG_NAME + DOT |
| 跨页连接符 | 生成 GND_POWER/VCC_CIRCLE（\g 全局）+ IOPORT/INPORT/OUTPORT |
| 页面命名正确 | page.map 格式正确 + 与 CSA 编号一致 |
| 100% 网络转换 | con 网络数/连接数与源完全一致 |
| 正确导出网表 | Packager-XL Export 成功，无 Error |
| export physical | 生成 pstx 三件套可被读取 |

### 关键技术结论（已确认）

1. **SPCOCN-1891 是错误诊断**：`PAINT WIRE;` 命令不存在；真实命令 `WIRE 16 -1 (x1 y1)(x2 y2);`（4 个真实工程逆向，16.6 支持）→ 推翻 v0.9.0 移除连线决策
2. **CSA 连线四条命令**：WIRE/DOT/LASTPIN $PN/LASTPIN SIG_NAME（几何重合建立连接）
3. **con 不是 Cadence 格式**：需重写为 `("S2" "dc_dc" "hdl_lib" "sym_1" (terms...))` + `(pins (conn...))`
4. **xcon 空骨架**：需填充 cells/terms/nets/instances/netScopes
5. **pageN.csv 完全缺失**：DEHDL 页面网络/引脚连接文件，必补
6. **EDIF 是连线理想数据源**（待架构师确认细节）：2516 WIRE + 坐标 + 网络名
7. **页面命名错位**：write_page_map 用 enumerate idx 当页码（L666-671）
8. **SPCOCN-542**：symbol.css 未声明默认属性 + $LOCATION 惯例

### 任务分解（P0-P3）

（详见 ROADMAP.md Part V Phase XI §XI.2 完整任务分解，此处为摘要）

| 阶段 | 子任务 | 状态 |
|------|--------|:---:|
| P0-A1 | EDIF figure WIRE 解析（2516 折线） | ✅ 已完成 |
| P0-A2 | EDIF page 块识别（24 页不塌缩） | ⬜ 待实施 |
| P0-A3 | OFF_PAGE_CONNECTOR 解析（522/765） | ✅ 部分 |
| P0-A4 | EDIF docstring 更正 | ✅ 已完成 |
| P0-A5 | 网络名转义还原 | ✅ 已完成 |
| P0-B1~B4 | con/xcon/pageN.csv 重构 | ⬜ 待实施 |
| P0-C1~C5 | CSA LASTPIN/WIRE/DOT 生成 | ⬜ 待实施 |
| P0-D1~D2 | EDIF 注入 + DSN 去留 | ⬜ 待实施 |

---

## 附：CIS 文件信息完整清单（架构师调研，2026-08-10）

> 来源：dsn-format.md（1064 行 VERIFIED）+ HG5015 三件套实测 + EDIF 实测

### DSN 侧信息（18 类）

| # | 信息类别 | 章节 | 关键字段 | 对 HDL 的用途 | 解析器状态 |
|---|----------|------|----------|--------------|:---:|
| A1 | CFBF/OLE 容器 | §1-2 | Library/Cache/Views/{v}/Pages/{p} 流 | 页面发现 | ✅ |
| A2 | 全局字符串表 strLst | §6 | name_idx/val_idx 解析 | 属性/网络名/库路径 | ✅ |
| A3 | 页面顶层布局 | §7 | page_name/size/各结构数组 | 页面组织 | ⚠️ |
| A4 | **Net Name Table** | §7.5 | net_name↔net_id（=Wire.id） | **网络名权威映射** | ❌ 未解析 |
| A5 | **Wire 线段** | §7.6 | segment_id/id/start/end/width/style/color | **连线几何** | ⚠️ 16 段（RTL 差） |
| A6 | Alias 网络标号 | §7.6.1 | loc/rot/name | 网络名标签 | ⚠️ 名空 |
| A7 | PlacedInstance | §7.7 | refdes/坐标/值/属性 | 元件实例 | ❌ RTL=0 |
| A8 | **T0x10 引脚** | §7.7.1 | point_x/y/net_id/sth(NC) | **引脚坐标/网络** | ✅（NC 未存） |
| A9 | **GraphicInst** | §7.8 | Global/Port/OffPage name_str_idx | **跨页连接** | ⚠️ IR 丢弃 |
| A10 | SymbolDisplayProp | §7.9 | name_idx/x/y/rot | 标签显示 | ✅ |
| A11 | Hierarchy 流 | §8 | 扁平网络名清单 | 跨页消歧 | ❌ 未解析 |
| A12 | Package/Device | §9.1-9.2 | pin_map 引脚号 | 引脚映射 | ✅ |
| A13 | LibraryPart/SymbolPin | §9.3-9.4 | 引脚名/电气类型 | 功能引脚 | ⚠️ 电气类型未存 |
| A14 | Cache 流 | §10 | 器件定义 | 引脚 fallback | ✅ |
| A15 | TitleBlock | §7.1 | 标题栏 | 信息页 | ⚠️ 假阳性 |
| A16 | PageSettings | §6/§7.2 | 156B opaque | 页面尺寸 | ❌ 硬编码 |
| A17 | EDIF 侧 | Part C | net/wire/offpage | 替代源 | ⚠️ 见下 |
| A18 | OLB 侧 | — | Packages/Devices/Symbols | 器件库 | ✅ |

### EDIF 侧信息（实测 HG5015）

| 结构 | 数量 | 状态 |
|------|:---:|:---:|
| (net) 网络定义 | 862 | ✅ |
| (joined)/(portRef) 连接 | 3583 | ✅ |
| **OFF_PAGE_CONNECTOR** | 765 | ⚠️ 522 已解析 |
| **figure WIRE 折线** | **2516** | ✅ 已解析（P0-A1） |
| (pt) 坐标点 | 4257 | ✅ |
| 含 WIRE 的网络 | 836/862 (97%) | ✅ |
| (page) 页面块 | 24 | ❌ 未解析（塌缩） |
| designator 位号坐标 | 3733 | ⚠️ 待用 |
| 网络名标签 origin | 4625 | ⚠️ 待用（P0-C2） |

### 结论：连线数据源优先级
1. **EDIF figure WIRE**（2516 图元/4257 点/97% 网络覆盖）—— ⭐ 首选
2. DSN Wire（标准变体）—— RTL 变体不可用
3. 拓扑合成兜底（EDIF 缺失网络）—— L 型/星型
4. 跨页连接：EDIF OFF_PAGE_CONNECTOR（765）+ DSN GraphicInst name_str_idx
