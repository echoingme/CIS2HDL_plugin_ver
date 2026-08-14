# 文件索引与功能映射表

> 版本: v1.0 | 日期: 2026-07-31 | 作者: 高见远（首席架构师）
>
> 本文档基于对参考库 `CIStoHDL_standard/` 全部 30 个文件/目录的逐一分析，
> 以及对当前项目 `cis2hdl/` 源码树的扫描，建立完整的文件索引与功能映射。

---

## 参考库数据流总览

```
┌──────────────────────────────────────────────────────────────────┐
│  阶段 1: 数据导出 (Export)                                        │
│                                                                   │
│  HG5015-BE36_V10.DSN  ──→  export_page13.py  (COM)              │
│                      ──→  export_page13.tcl (TCL)               │
│                      ──→  export_page.tcl    (TCL)              │
│                          │                                        │
│                          ▼                                        │
│                   Page13_DeviceList.csv / .txt                    │
│                   Page13_AnomalyList.txt                          │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│  阶段 2: 器件匹配 (Match)                                         │
│                                                                   │
│  Page13_DeviceList.csv  ──→  match_cis_to_hdl.py                │
│  hdl_lib/ (100+ 目录)    ──→  (扫描 chips.prt + part.ptf)       │
│                          │                                        │
│                          ▼                                        │
│                   CIS_to_HDL_Mapping.csv / .txt                   │
│                   (三重匹配: Prefix + Footprint + Value)          │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│  阶段 3: 代码生成 (Generate)                                      │
│                                                                   │
│  CIS_to_HDL_Mapping.csv ──→  generate_hdl_sch.py                │
│                          ──→  generate_hdl_scr.py                │
│                          │                                        │
│                          ▼                                        │
│                   worklib/out_hdl/sch_1/page1.csa                 │
│                   worklib/out_hdl/sch_1/place_parts.scr           │
└──────────────────────────────────────────────────────────────────┘
```

---

## Part A: 完整文件清单表

### A.1 参考库文件清单（CIStoHDL_standard/）

| # | 路径 | 大小 | 类型 | 功能域 | 优先级 |
|---|------|------|------|--------|:------:|
| 1 | `export_page13.py` | 15,664 B | Python | 数据导出（COM） | **高** |
| 2 | `generate_hdl_sch.py` | 14,617 B | Python | 代码生成（CSA） | **高** |
| 3 | `generate_hdl_scr.py` | 4,760 B | Python | 代码生成（SCR） | **高** |
| 4 | `match_cis_to_hdl.py` | 20,504 B | Python | 器件匹配 | **高** |
| 5 | `export_page.tcl` | 13,481 B | TCL | Cadence自动化 | **高** |
| 6 | `export_page13.tcl` | 12,913 B | TCL | Cadence自动化 | **高** |
| 7 | `test_tcl.tcl` | 996 B | TCL | 测试/调试 | 低 |
| 8 | `page1.scr` | 33,588 B | SCR | Cadence自动化 | **高** |
| 9 | `place_parts.scr` | 8,889 B | SCR | Cadence自动化 | 中 |
| 10 | `place_parts_simple.scr` | 1,754 B | SCR | Cadence自动化 | 低 |
| 11 | `test_place.scr` | 139 B | SCR | 测试/调试 | 低 |
| 12 | `diagnose_com.vbs` | 3,904 B | VBS | 诊断 | 中 |
| 13 | `run_tcl_export.bat` | 1,487 B | Batch | 流程编排 | 中 |
| 14 | `CIS_to_HDL_Mapping.txt` | 6,134 B | Data | 配置与映射 | **高** |
| 15 | `CIS_to_HDL_Mapping.csv` | 3,035 B | Data | 配置与映射 | **高** |
| 16 | `CIS_to_HDL_Mapping_Page13.csv` | 3,035 B | Data | 配置与映射 | 中 |
| 17 | `Page13_DeviceList.txt` | 4,851 B | Data | 配置与映射 | **高** |
| 18 | `Page13_DeviceList.csv` | 833 B | Data | 配置与映射 | **高** |
| 19 | `Page13_AnomalyList.txt` | 1,058 B | Data | 诊断 | 中 |
| 20 | `out_hdl.cpm` | 832 B | Output | 代码生成 | 中 |
| 21 | `cds.lib` | 98 B | Output | 配置与映射 | 低 |
| 22 | `c2esch.edif` | 31,430 B | Output | 数据导出 | 低 |
| 23 | `HG5015-BE36_V10.DSN` | 1.6 MB | Project | 项目文件 | **高** |
| 24 | `HG5015-BE36_V10_0.DBK` | 1.6 MB | Project | 项目文件 | 低 |
| 25 | `HG5015-BE36_V10.opj` | 4.8 KB | Project | 项目文件 | 中 |
| 26 | `HG5015-BE36_V10.EXP` | 65 KB | Project | 项目文件 | 低 |
| 27 | `tcl脚本导入orcad.docx` | 16 KB | Project | 文档 | 低 |
| 28 | `hdl_lib/` | 131 目录 | Library | 配置与映射 | **高** |
> 注（2026-08-07 代码核对）：`CIStoHDL_standard/hdl_lib/` 实际器件目录数为 **131**（排除"备份"目录，原"~100"为早期估计）；完整器件目录表见 A.1.2。
| 29 | `worklib/` | — | Output | 代码生成 | 中 |
| 30 | `adw/` | — | Output | 代码生成 | 低 |

### A.1.2 参考库 HDL 器件目录表（吸收自 `_reference_index.md`，2026-08-03）

> 实际目录数核对（2026-08-07）：`CIStoHDL_standard/hdl_lib/` 排除"备份"后为 **131** 个器件目录（原文档写"70+ / 130"为旧口径）。每个器件遵循标准结构：`chips/chips.prt`、`entity/{verilog.v,vhdl.vhd,vlog004u.sir,pc.db}`、`metadata/{pinlist.txt,revision.dat,pdv_validation.txt}`、`part_table/part.ptf`、`sym_1/symbol.css`、`master.tag`，可选 `cfg_package/expand.cfg`、`sch_1/{.con,.dcf,.xcon}`。

| 目录名 | 类别 | 估计pins | 说明 |
|--------|------|---------|------|
| capacitor | 无源/电容 | 2 | 多 primitive (0201/0402/0603/0805) |
| resistor | 无源/电阻 | 2 | 多 primitive (0201~2512) |
| inductor | 无源/电感 | 2 | 基础电感 |
| diode | 半导体/二极管 | 2 | 二极管 |
| led | 半导体/LED | 2 | 发光二极管 |
| n_mos, p_mos | 半导体/MOSFET | 3 | MOS 管 |
| npn, pnp | 半导体/BJT | 3 | 三极管 |
| amplifier | 模拟/运放 | 5-8 | 运算放大器 |
| ldo | 电源/LDO | 3-6 | 低压差稳压器 |
| dc_dc | 电源/DC-DC | 5-12 | DC-DC 转换器 |
| connector | 连接器 | 2-100+ | 通用连接器(多 sym_) |
| crystal | 时钟/晶振 | 2-4 | 石英晶体振荡器 |
| interface | 通信/接口 | 4-28 | 接口芯片(RS485, CAN) |
| logic_gate | 逻辑/门 | 5-14 | 逻辑门电路 |
| flash, eeprom | 存储 | 8 | 存储器芯片 |
| fb | 无源/磁珠 | 2 | 铁氧体磁珠 |
| hole, mark | 辅助 | 1 | 安装孔/标记点 |
| 88e6071, 88e6320 | 芯片/交换机 | 100+ | 网络交换芯片 |
| bcm53125~bcm88470 | 芯片/博通 | 200-600+ | 博通系列(多 sym_) |
| b50210sb0, b50285 | 芯片/博通 | 300+ | 博通控制器 |
| bcm56150k | 芯片/博通 | 400+ | 博通交换(8 sym_) |
| bcm56760 | 芯片/博通 | 600+ | 博通大芯片(13 sym_) |
| an7552ct, att7022e | 芯片/通信 | 50+ | 通信处理芯片 |
| lpc176x, hc32 | 芯片/MCU | 50-100 | 微控制器 |
| ddr | 芯片/内存 | 78-200 | DDR 内存 |

### A.1.3 参考库 worklib/out_hdl/sch_1 输出文件表（吸收自 `reference_project_file_list.md`，2026-08-03）

| 文件 | 大小 | 格式 | 说明 |
|------|------|------|------|
| `page1.csa` | 33,288 B | MACRO_DRAWING | ⭐ **CSA 页面主文件** |
| `page1.cpc` | 43 B | 页面配置 | `#ISCELL hdl_lib c#20size#20page *` |
| `page1.csv` | 123 B | 连通性 | `FILE_TYPE = CONNECTIVITY;` |
| `page2.csa` | 210 B | MACRO_DRAWING | 第二页（空页） |
| `page2.csb` | 512 B | 二进制 | Cadence 编译后的二进制页面 |
| `page2.cpc` | 0 B | 空文件 | |
| `page2.csv` | 118 B | 连通性 | |
| `out_hdl.dcf` | 2,937 B | S-expr | ⭐ **设计约束文件** (Cadence内部格式) |
| `out_hdl.dcf,1` | 572 B | S-expr | 约束备份 v1 |
| `out_hdl.dcf,2` | 537 B | S-expr | 约束备份 v2 |
| `out_hdl.xcon` | 3,313 B | S-expr | ⭐ **跨连接文件** |
| `out_hdl.xcon,1-3` | ~6 KB | S-expr | 跨连接备份 |
| `master.tag` | 38 B | text | 包含 `out_hdl.csa\nout_hdl.xcon\nout_hdl.dcf` |
| `module_order.dat` | 86 B | text | 模块顺序 |
| `page.map` | 10 B | text | 页面映射 `1 1 DDR3` |
| `hdldirect.dat` | 209 B | binary | HDL Direct 数据 |
| `pc.db` | 163 B | binary | 引脚约束数据库 |
| `verilog.v` | 216 B | Verilog | 生成的 Verilog 代码 |
| `viewprps.prp` | 157 B | text | 视图属性 |
| `vlog004u.sir` | 359 B | text | 符号实例报告 |
| `place_parts.scr` | 8,889 B | script | 器件放置脚本 |

---

### A.2 当前项目核心文件清单（cis2hdl/）

| # | 路径 | 功能域 | 说明 |
|---|------|--------|------|
| 31 | `cis2hdl/core/engine/conversion_engine.py` | 流程编排 | 六阶段转换管道控制器 |
| 32 | `cis2hdl/core/parser/base.py` | 解析器 | 解析器注册表与基类 |
| 33 | `cis2hdl/core/parser/dsn/dsn_parser.py` | 解析器 | 二进制DSN顶层调度器 |
| 34 | `cis2hdl/core/parser/dsn/ole_reader.py` | 解析器 | OLE复合文档读取 |
| 35 | `cis2hdl/core/parser/dsn/page_parser.py` | 解析器 | DSN页面流解析 |
| 36 | `cis2hdl/core/parser/dsn/structures.py` | 解析器 | DSN数据结构定义 |
| 37 | `cis2hdl/core/parser/dsn/binary_reader.py` | 解析器 | 二进制流读取工具 |
| 38 | `cis2hdl/core/parser/edif_parser.py` | 解析器 | EDIF格式解析器 |
| 39 | `cis2hdl/core/parser/hdl_scanner.py` | 解析器 | HDL库扫描器（对应参考库match_cis_to_hdl.py的库扫描部分） |
| 40 | `cis2hdl/core/parser/chips_prt.py` | 解析器 | chips.prt文件解析 |
| 41 | `cis2hdl/core/parser/part_ptf.py` | 解析器 | part.ptf文件解析 |
| 42 | `cis2hdl/core/parser/symbol_css.py` | 解析器 | symbol.css文件解析 |
| 43 | `cis2hdl/core/parser/layout_mapper.py` | 解析器 | 坐标布局映射 |
| 44 | `cis2hdl/core/parser/cross_validator.py` | 解析器 | 跨格式校验 |
| 45 | `cis2hdl/core/matcher/__init__.py` | 匹配器 | 匹配器模块入口 |
| 46 | `cis2hdl/core/matcher/base.py` | 匹配器 | 匹配器基类 |
| 47 | `cis2hdl/core/matcher/pipeline.py` | 匹配器 | 匹配管道（v2.0 已重构为两阶段，原"四级链式"为历史口径；详见 A.2 补充） |
| 48 | `cis2hdl/core/matcher/exact.py` | 匹配器 | 精确指纹匹配 |
| 49 | `cis2hdl/core/matcher/feature.py` | 匹配器 | 特征提取匹配 |
| 50 | `cis2hdl/core/matcher/fuzzy.py` | 匹配器 | 模糊名称匹配 |
| 51 | `cis2hdl/core/matcher/registry.py` | 匹配器 | 匹配器注册表 |
| 52 | `cis2hdl/core/writer/base.py` | 代码生成 | Writer基类与注册表 |
| 53 | `cis2hdl/core/writer/cpm_writer.py` | 代码生成 | CPM项目文件生成 |
| 54 | `cis2hdl/core/writer/cdslib_writer.py` | 代码生成 | cds.lib库配置生成 |
| 55 | `cis2hdl/core/writer/sch_writer.py` | 代码生成 | SCH原理图生成（CTW模板） |
| 56 | `cis2hdl/core/db/component_db.py` | 数据库 | 统一元件数据库 |
| 57 | `cis2hdl/core/ir/component.py` | IR | 元件定义IR |
| 58 | `cis2hdl/core/ir/design.py` | IR | 设计IR（页面/网络） |
| 59 | `cis2hdl/core/ir/match.py` | IR | 匹配结果IR |
| 60 | `cis2hdl/core/diagnostics/pipeline.py` | 诊断 | 诊断管道 |
| 61 | `cis2hdl/core/diagnostics/report_gen.py` | 诊断 | 报告生成 |
| 62 | `cis2hdl/core/diagnostics/error_diagnosis.py` | 诊断 | 错误诊断引擎 |
| 63 | `cis2hdl/core/diagnostics/file_validator.py` | 诊断 | 文件校验 |
| 64 | `cis2hdl/core/diagnostics/config_validator.py` | 诊断 | 配置校验 |
| 65 | `cis2hdl/core/diagnostics/quality.py` | 诊断 | 质量评估 |
| 66 | `cis2hdl/core/diagnostics/recovery.py` | 诊断 | 错误恢复 |
| 67 | `cis2hdl/core/diagnostics/tracker.py` | 诊断 | 进度跟踪 |
| 68 | `cis2hdl/core/validator/base.py` | 校验 | 校验器基类 |
| 69 | `cis2hdl/core/validator/pin_validator.py` | 校验 | 引脚校验 |
| 70 | `cis2hdl/core/validator/power_validator.py` | 校验 | 电源校验 |
| 71 | `cis2hdl/core/validator/net_validator.py` | 校验 | 网络校验 |
| 72 | `cis2hdl/core/net_utils.py` | 工具 | 网络分类工具 |
| 73 | `cis2hdl/core/config.py` | 配置 | 全局配置 |
| 74 | `cis2hdl/utils/naming.py` | 工具 | 命名工具 |

### A.2 补充（2026-08-07 代码树核对新增）

> 以下文件为按 08-07 实际代码树核对后新增的当前项目核心文件（原 #31~#74 表保持不变）。核对范围：`cis2hdl/core/{matcher,writer,parser,diagnostics}/`。

| # | 路径 | 功能域 | 说明 |
|---|------|--------|------|
| 75 | `cis2hdl/core/matcher/type_hypothesis.py` | 匹配器 v2.0 | 类型假设生成（Stage 1） |
| 76 | `cis2hdl/core/matcher/candidate_pool.py` | 匹配器 v2.0 | 候选池构建（Stage 1） |
| 77 | `cis2hdl/core/matcher/prefix_filter.py` | 匹配器 v2.0 | 前缀过滤（对应参考库 body_map/body_fallback） |
| 78 | `cis2hdl/core/matcher/passive_matcher.py` | 匹配器 v2.0 | 被动匹配 5 级（Stage 2） |
| 79 | `cis2hdl/core/matcher/active_matcher.py` | 匹配器 v2.0 | 主动匹配 5 维（Stage 2） |
| 80 | `cis2hdl/core/matcher/value_matcher.py` | 匹配器 v2.0 | Value 值匹配 |
| 81 | `cis2hdl/core/matcher/fallback.py` | 匹配器 v2.0 | 回退匹配 |
| 82 | `cis2hdl/core/matcher/match_config.py` | 匹配器 v2.0 | 匹配配置（STOP_SEARCH=0.75 / NEEDS_REVIEW=0.40） |
| 83 | `cis2hdl/core/matcher/scoring.py` | 匹配器 v2.0 | 打分（final_conf=prior×within） |
| 84 | `cis2hdl/core/writer/csa_writer.py` | 代码生成 | CSA 原理图页面生成（对应参考库 generate_hdl_sch.py / page1.scr） |
| 85 | `cis2hdl/core/writer/scr_writer.py` | 代码生成 | DEHDL .scr 交互式放置脚本（对应参考库 generate_hdl_scr.py） |
| 86 | `cis2hdl/core/writer/xcon_writer.py` | 代码生成 | .xcon 交叉连接文件生成 |
| 87 | `cis2hdl/core/writer/cpc_writer.py` | 代码生成 | .cpc 页面配置生成（expand.cfg） |
| 88 | `cis2hdl/core/writer/output_manager.py` | 代码生成 | 输出管理（page.map / master.tag / module_order.dat / .con） |
| 89 | `cis2hdl/core/writer/mapping_csv_writer.py` | 代码生成 | 映射结果 CSV 输出 |
| 90 | `cis2hdl/core/writer/error_logger.py` | 代码生成 | 写入错误日志 |
| 91 | `cis2hdl/core/parser/component_catalog.py` | 解析器 | 元件目录索引 |
| 92 | `cis2hdl/core/parser/cross_ref_parser.py` | 解析器 | 交叉引用解析 |
| 93 | `cis2hdl/core/parser/pstchip_parser.py` | 解析器 | pstchip.dat 解析 |
| 94 | `cis2hdl/core/parser/pstxnet_parser.py` | 解析器 | pstxnet.dat 解析 |
| 95 | `cis2hdl/core/parser/pstxnet_netlist_parser.py` | 解析器 | pstxnet 网表解析 |
| 96 | `cis2hdl/core/diagnostics/diagnostic_report.py` | 诊断 | 诊断报告输出 |
| 97 | `cis2hdl/core/diagnostics/file_inventory.py` | 诊断 | 文件清单盘点 |
| 98 | `cis2hdl/core/diagnostics/history.py` | 诊断 | 历史记录 |
| 99 | `cis2hdl/core/diagnostics/multi_source.py` | 诊断 | 多数据源诊断 |
| 100 | `cis2hdl/core/diagnostics/olb_integrity.py` | 诊断 | OLB 完整性检查 |

> 补充说明：`cis2hdl/core/parser/` 下另有 `dsn/`（二进制 DSN 解析，含 dsn_parser/ole_reader/page_parser/structures/binary_reader 等）与 `olb/`（OLB 库解析）两个子目录；匹配器 v2.0 已重构为**两阶段**（TypeHypothesis→CandidatePool→PassiveMatcher/ActiveMatcher），原"四级管道（Exact→Fuzzy→Feature→Manual）"描述为历史口径。

---

## Part B: 功能模块分组

### B.1 参考库功能模块分组

```
┌─────────────────────────────────────────────────────────────────┐
│  1. 解析器 (Parser)                                              │
│     • export_page13.py   — COM方式从OrCAD Capture导出器件属性    │
│     • export_page.tcl    — TCL通用页面导出脚本                   │
│     • export_page13.tcl  — TCL特定页面(13-DDR3)导出脚本          │
│     • test_tcl.tcl       — TCL API可用性测试                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  2. 匹配器 (Matcher)                                             │
│     • match_cis_to_hdl.py — 核心匹配引擎                        │
│       ├── read_cis_data()      读取Page_DeviceList.csv           │
│       ├── parse_chips_prt()    解析HDL库chips.prt                │
│       ├── parse_part_ptf()     解析HDL库part.ptf                 │
│       ├── match_by_prefix()    前缀匹配 (RefDes→HDL器件类别)     │
│       └── match_by_footprint() 封装匹配 + Value值匹配            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  3. 代码生成器 (Code Generator)                                  │
│     • generate_hdl_sch.py — 生成DEHDL原理图CSA宏文件             │
│       ├── get_prop_offsets()    读取symbol.css属性偏移           │
│       ├── calc_position()       网格布局计算                     │
│       ├── map_cis_to_dehdl_coords() CIS→DEHDL坐标映射            │
│       └── generate_csa()        生成CSA文件(FORCEADD/FORCEPROP)  │
│     • generate_hdl_scr.py — 生成交互式放置SCR脚本                │
│     • out_hdl.cpm         — DEHDL项目配置文件                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  4. Cadence 自动化 (Cadence Automation)                          │
│     • page1.scr              — DEHDL页面宏绘制脚本               │
│     • place_parts.scr        — 批量器件放置脚本                  │
│     • place_parts_simple.scr — 简化版放置脚本                    │
│     • test_place.scr         — 放置测试                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  5. 诊断 (Diagnostics)                                           │
│     • diagnose_com.vbs        — COM ProgID注册表诊断             │
│     • Page13_AnomalyList.txt  — 器件异常报告(缺失SNUM)           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  6. 配置与映射 (Configuration & Mapping)                         │
│     • CIS_to_HDL_Mapping.txt      — 匹配结果(人类可读)           │
│     • CIS_to_HDL_Mapping.csv      — 匹配结果(机器可读)           │
│     • CIS_to_HDL_Mapping_Page13.csv — 同上的Page13副本           │
│     • Page13_DeviceList.txt       — 器件属性清单                 │
│     • Page13_DeviceList.csv       — 器件属性清单                 │
│     • cds.lib                     — Cadence库配置文件            │
│     • hdl_lib/                    — HDL标准器件库(100+目录)      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  7. 项目文件 (Project Files)                                     │
│     • HG5015-BE36_V10.DSN  — OrCAD Capture原始设计               │
│     • HG5015-BE36_V10.opj  — OrCAD项目文件                       │
│     • HG5015-BE36_V10.EXP  — 导出配置                            │
│     • run_tcl_export.bat   — 批处理启动器(流程编排)              │
│     • tcl脚本导入orcad.docx — 操作文档                           │
└─────────────────────────────────────────────────────────────────┘
```

### B.2 当前项目功能模块分组

```
┌─────────────────────────────────────────────────────────────────┐
│  1. 解析器 (Parser)                  cis2hdl/core/parser/        │
│     • dsn/        — 二进制DSN解析 (OLE→页面流→IR)               │
│     • edif_parser.py  — EDIF格式解析                             │
│     • hdl_scanner.py  — HDL库扫描                                │
│     • chips_prt.py    — chips.prt解析                           │
│     • part_ptf.py     — part.ptf解析                            │
│     • symbol_css.py   — symbol.css解析                          │
│     • layout_mapper.py — 坐标映射                               │
│     • cross_validator.py — 跨格式校验                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  2. 匹配器 (Matcher)                  cis2hdl/core/matcher/     │
│     • pipeline.py   — 匹配管道（v2.0 两阶段，原"四级"为历史口径） │
│     • exact.py      — 指纹精确匹配 (P1)                         │
│     • fuzzy.py      — 模糊名称匹配 (P2)                         │
│     • feature.py    — 特征提取匹配 (P3)                         │
│     • registry.py   — 匹配器注册                                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  3. 代码生成器 (Writer)               cis2hdl/core/writer/      │
│     • cpm_writer.py   — CPM项目文件生成                         │
│     • cdslib_writer.py — cds.lib生成                           │
│     • sch_writer.py   — SCH原理图生成(CTW模板DSL)               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  4. 引擎 (Engine)                     cis2hdl/core/engine/       │
│     • conversion_engine.py — 六阶段转换管道                     │
│       (诊断→解析→扫描→匹配→校验→生成)                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  5. 诊断 (Diagnostics)                cis2hdl/core/diagnostics/  │
│     • pipeline.py    — 诊断管道                                 │
│     • report_gen.py  — 报告生成                                 │
│     • error_diagnosis.py — 错误诊断                             │
│     • quality.py     — 质量评估(对应参考库AnomalyList)          │
│     • recovery.py    — 错误恢复                                 │
│     • tracker.py     — 进度跟踪                                 │
│     • file_validator.py — 文件校验                             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  6. IR层 (Intermediate Representation)  cis2hdl/core/ir/        │
│     • component.py — 元件定义                                   │
│     • design.py    — 设计结构(页面/网络)                        │
│     • match.py     — 匹配结果                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  7. GUI (图形界面)                     cis2hdl/gui/              │
│     • app.py / main_window.py — 应用主窗口                      │
│     • panels/ — 面板组件(项目/诊断/日志/预览/匹配审查)          │
│     • dialogs/ — 对话框(设置/恢复/匹配确认)                     │
│     • widgets/ — 组件(转换Worker)                               │
└─────────────────────────────────────────────────────────────────┘
```

### B.2 补充（2026-08-07 代码树核对，v2.0）

> 以下为按 08-07 实际代码树核对后新增/修正的模块文件，上方原 ASCII 分组图保持不动（其中"四级链式管道"已过时，v2.0 为两阶段）。

**匹配器 `core/matcher/`（v2.0 两阶段重构）**：
- Stage 1 候选生成：`type_hypothesis.py`、`candidate_pool.py`、`prefix_filter.py`
- Stage 2 匹配：`passive_matcher.py`（5 级）、`active_matcher.py`（5 维）、`value_matcher.py`、`fallback.py`
- 配置/打分：`match_config.py`（STOP_SEARCH=0.75 / NEEDS_REVIEW=0.40）、`scoring.py`（final_conf=prior×within）
- 原有：`exact.py`、`fuzzy.py`、`feature.py`、`base.py`、`registry.py`、`pipeline.py`

**代码生成器 `core/writer/`（新增 5 个核心 writer）**：`csa_writer.py`、`scr_writer.py`、`xcon_writer.py`、`cpc_writer.py`、`output_manager.py`（另有 `mapping_csv_writer.py`、`error_logger.py`）

**解析器 `core/parser/`（新增）**：`component_catalog.py`、`cross_ref_parser.py`、`pstchip_parser.py`、`pstxnet_parser.py`、`pstxnet_netlist_parser.py`（另有 `dsn/`、`olb/` 两个子目录）

**诊断 `core/diagnostics/`（新增）**：`diagnostic_report.py`、`file_inventory.py`、`history.py`、`multi_source.py`、`olb_integrity.py`

---

## Part C: 功能映射表

### 参考库 → 当前项目 cis2hdl 对应关系

| 参考库文件 | 功能 | 当前项目对应文件 | 实现状态 | 备注 |
|-----------|------|-----------------|:------:|------|
| **数据导出层** |
| `export_page13.py` | OrCAD COM 属性导出 | `cis2hdl/core/parser/dsn/dsn_parser.py` | ✅ 已实现 | 参考库用COM读取；当前项目直接解析DSN二进制，无需OrCAD运行时 |
| `export_page.tcl` | TCL通用页面导出 | `cis2hdl/core/parser/dsn/page_parser.py` | ✅ 已实现 | TCL方式已由二进制DSN解析器替代 |
| `export_page13.tcl` | TCL特定页面导出 | 同上 + `dsn/ole_reader.py` | ✅ 已实现 | OLE复合文档→页面流→DesignIR |
| `run_tcl_export.bat` | 流程启动器 | `cis2hdl/core/engine/conversion_engine.py` | ✅ 已实现 | 批处理编排→Python引擎管道 |
| **器件匹配层** |
| `match_cis_to_hdl.py` | 核心匹配引擎 | `cis2hdl/core/matcher/pipeline.py` | ✅ 已实现 | 参考库:三重匹配; 当前:v2.0 两阶段管道（TypeHypothesis→CandidatePool→Passive/ActiveMatcher；原"四级管道"为历史口径） |
| `match_cis_to_hdl.py::read_cis_data()` | CSV读取 | `cis2hdl/core/parser/dsn/dsn_parser.py` | ✅ 已实现 | 不再依赖CSV中间文件 |
| `match_cis_to_hdl.py::parse_chips_prt()` | chips.prt解析 | `cis2hdl/core/parser/chips_prt.py` | ✅ 已实现 | 独立解析器，支持更多PINUSE类型 |
| `match_cis_to_hdl.py::parse_part_ptf()` | part.ptf解析 | `cis2hdl/core/parser/part_ptf.py` | ✅ 已实现 | 结构化解析，返回PartProperty |
| `match_cis_to_hdl.py::_read_file_auto_encoding()` | 自动编码检测 | `cis2hdl/core/parser/chips_prt.py` (内置) | ✅ 已实现 | UTF-8/GBK自动回退 |
| **代码生成层** |
| `generate_hdl_sch.py` | CSA原理图宏生成 | `cis2hdl/core/writer/sch_writer.py` | ✅ 已实现 | 参考库:CSA(FORCEADD); 当前:CTW模板DSL |
| `generate_hdl_sch.py::get_prop_offsets()` | symbol.css解析 | `cis2hdl/core/parser/symbol_css.py` | ✅ 已实现 | 独立解析器，返回SchematicSymbolDef |
| `generate_hdl_sch.py::map_cis_to_dehdl_coords()` | 坐标映射 | `cis2hdl/core/parser/layout_mapper.py` | ✅ 已实现 | 居中+缩放策略 |
| `generate_hdl_scr.py` | SCR交互脚本生成 | `cis2hdl/core/writer/sch_writer.py` | ⚠️ 部分实现 | SCR功能已被CTW模板替代，但交互式放置场景未覆盖 |
| `page1.scr` | DEHDL页面宏 | `cis2hdl/core/writer/sch_writer.py` (CTW输出) | ✅ 已实现 | SCR宏指令→CTW声明式模板 |
| `place_parts.scr` | 批量放置脚本 | `cis2hdl/core/writer/sch_writer.py` | ✅ 已实现 | 位置由CTW模板中的x/y坐标指定 |
| `out_hdl.cpm` | CPM项目配置 | `cis2hdl/core/writer/cpm_writer.py` | ✅ 已实现 | 模板化生成，支持配置参数 |
| `cds.lib` | 库配置 | `cis2hdl/core/writer/cdslib_writer.py` | ✅ 已实现 | DEFINE语句生成 |
| **诊断层** |
| `diagnose_com.vbs` | COM诊断 | `cis2hdl/core/diagnostics/config_validator.py` | ✅ 已实现 | COM ProgID扫描→配置校验 |
| `Page13_AnomalyList.txt` | 异常报告 | `cis2hdl/core/diagnostics/quality.py` | ✅ 已实现 | No_SNUM→质量评估报告 |
| `Page13_AnomalyList.txt` | 异常报告 | `cis2hdl/core/diagnostics/report_gen.py` | ✅ 已实现 | 统一报告生成 |
| **配置与映射** |
| `CIS_to_HDL_Mapping.txt/csv` | 映射结果 | `cis2hdl/core/ir/match.py` (MatchResult) | ✅ 已实现 | 结构化MatchResult替代CSV |
| `Page13_DeviceList.txt/csv` | 器件清单 | `cis2hdl/core/ir/design.py` (DesignIR) | ✅ 已实现 | IR替代中间文件 |
| `hdl_lib/` | HDL标准器件库 | `cis2hdl/core/parser/hdl_scanner.py` + `component_db.py` | ✅ 已实现 | 扫描→ComponentDB统一索引 |
| **项目文件** |
| `HG5015-BE36_V10.DSN` | 测试DSN | `cis2hdl/tests/fixtures/` | 🔶 待确认 | 需确认测试夹具路径 |
| `HG5015-BE36_V10.opj` | OrCAD项目 | 不需要 | N/A | opj仅OrCAD使用 |
| `test_tcl.tcl` | TCL测试 | 不需要 | N/A | TCL方式已废弃 |
| `tcl脚本导入orcad.docx` | 操作文档 | 不需要 | N/A | 已归档为参考 |

### 新增能力（参考库未覆盖）

| 能力 | 当前项目实现 | 说明 |
|------|-------------|------|
| GUI 界面 | `cis2hdl/gui/` | 完整Tkinter GUI：项目面板、诊断面板、日志面板、匹配审查面板、报告面板 |
| 校验层 | `cis2hdl/core/validator/` | 引脚校验、电源校验、网络校验（参考库无此层） |
| 错误恢复 | `cis2hdl/core/diagnostics/recovery.py` | 转换失败后的自动恢复策略 |
| 进度跟踪 | `cis2hdl/core/diagnostics/tracker.py` | 六阶段进度实时跟踪 |
| EDIF 支持 | `cis2hdl/core/parser/edif_parser.py` | 参考库只有EDIF输出示例，当前项目支持EDIF输入解析 |

---

## Part D: 阅读计划

> ✅ **阅读计划已完成**（截至 2026-08-07）。精读产出已归档：逐文件精读见 `REFERENCE_READING_NOTES.md`；7 路并行精读报告见 doc-researcher-1~7；本部分保留为历史参考，不再作为待办。

### D.1 按优先级排序的阅读顺序

#### 🔴 Phase 1 — 必须精读（15 个文件）：理解核心数据流

| 阅读顺序 | 文件 | 理由 | 预计时间 |
|:------:|------|------|:------:|
| 1 | `match_cis_to_hdl.py` | **核心匹配引擎** — 整个流程的"心脏"。理解三重匹配算法、chips.prt/part.ptf解析方式、编码处理策略 | 45 min |
| 2 | `CIS_to_HDL_Mapping.txt` | **匹配结果样本** — 了解输入输出数据格式、匹配等级(●/○/△/✕)的含义 | 10 min |
| 3 | `generate_hdl_sch.py` | **CSA代码生成** — 了解FORCEADD/FORCEPROP命令格式、坐标映射、C纸布局 | 30 min |
| 4 | `generate_hdl_scr.py` | **SCR脚本生成** — 了解交互式放置流程、DEHDL控制台命令格式 | 15 min |
| 5 | `export_page13.py` | **COM导出** — 了解OrCAD COM接口使用方式、pywin32依赖、属性提取逻辑 | 25 min |
| 6 | `export_page13.tcl` | **TCL导出** — 了解DboTclHelper API用法、GetEffectivePropStringValue等关键函数 | 25 min |
| 7 | `export_page.tcl` | **TCL通用导出** — 与export_page13.tcl对比，理解参数化差异 | 20 min |
| 8 | `page1.scr` | **DEHDL宏脚本** — 完整FORCEADD/FORCEPROP/DISPLAY命令序列，理解DEHDL页面格式 | 20 min |
| 9 | `run_tcl_export.bat` | **流程启动器** — 理解原始工作流编排（三种执行模式） | 5 min |
| 10 | `Page13_DeviceList.txt` | **器件清单样本** — 理解CIS导出数据结构（RefDes/Value/Footprint/SNUM等8字段） | 5 min |
| 11 | `CIS_to_HDL_Mapping.csv` | **映射CSV** — 理解CSV列结构：cis_*/hdl_*/match_level | 5 min |
| 12 | `diagnose_com.vbs` | **COM诊断** — 理解注册表扫描逻辑、OrCAD ProgID候选列表 | 10 min |
| 13 | `Page13_AnomalyList.txt` | **异常报告** — 理解"缺失SNUM"等常见异常类型 | 5 min |
| 14 | `place_parts.scr` | **放置脚本样本** — 与generate_hdl_scr.py输出对比 | 10 min |
| 15 | `out_hdl.cpm` | **CPM输出样本** — 理解DEHDL项目文件格式 | 5 min |

#### 🟡 Phase 2 — 建议阅读（8 个文件）：理解周边逻辑

| 阅读顺序 | 文件 | 理由 |
|:------:|------|------|
| 16 | `hdl_lib/` 目录结构 | 理解HDL库组织方式：每个器件一个目录，含chips.prt/symbol.css/part.ptf |
| 17 | `HG5015-BE36_V10.opj` | OrCAD项目结构（XML格式） |
| 18 | `place_parts_simple.scr` | 简化SCR与完整版对比 |
| 19 | `CIS_to_HDL_Mapping_Page13.csv` | 确认与通用版的一致性 |
| 20 | `worklib/` 目录结构 | 理解DEHDL输出目录布局 |
| 21 | `cds.lib` | Cadence库引用格式 |

#### 🟢 Phase 3 — 可选阅读（5 个文件）：补充背景

| 阅读顺序 | 文件 | 理由 |
|:------:|------|------|
| 22 | `test_tcl.tcl` | TCL API测试，理解Capture TCL环境 |
| 23 | `test_place.scr` | 最小SCR测试 |
| 24 | `c2esch.edif` | EDIF输出格式参考 |
| 25 | `HG5015-BE36_V10.EXP` | 导出配置 |
| 26 | `tcl脚本导入orcad.docx` | 操作文档，历史参考 |

### D.2 推荐阅读路径图

```
                        ┌──────────────────────┐
                        │  入口: run_tcl_export │
                        │       .bat           │
                        └──────┬───────────────┘
                               │
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
        ┌────────────┐  ┌────────────┐  ┌────────────┐
        │ COM 方式    │  │ TCL 方式    │  │ 诊断        │
        │ export_     │  │ export_     │  │ diagnose_   │
        │ page13.py   │  │ page13.tcl  │  │ com.vbs     │
        └──────┬─────┘  └──────┬─────┘  └────────────┘
               │               │
               └───────┬───────┘
                       ▼
              ┌─────────────────┐
              │ Page13_DeviceList│
              │ .csv / .txt      │
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │ ★ match_cis_to_  │  ← 核心！
              │    hdl.py        │
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │ CIS_to_HDL_      │
              │ Mapping.csv/.txt │
              └────────┬────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
   ┌───────────┐ ┌───────────┐ ┌─────────┐
   │ generate_ │ │ generate_ │ │ page1.  │
   │ hdl_sch.py│ │ hdl_scr.py│ │ scr     │
   └─────┬─────┘ └─────┬─────┘ └────┬────┘
         │             │            │
         ▼             ▼            ▼
   ┌───────────┐ ┌───────────┐ ┌─────────┐
   │ page1.csa │ │ place_    │ │ DEHDL   │
   │           │ │ parts.scr │ │ 直接执行 │
   └───────────┘ └───────────┘ └─────────┘
```

### D.3 关键对比阅读点

| 对比维度 | 参考库实现 | 当前项目实现 | 重点关注 |
|---------|-----------|-------------|---------|
| 匹配策略 | 三重匹配(Prefix+Footprint+Value) | v2.0 两阶段管道（TypeHypothesis→CandidatePool→Passive/ActiveMatcher；原"四级管道(Exact→Fuzzy→Feature→Manual)"为历史口径） | 当前项目更精细，但参考库的Footprint尺寸提取逻辑值得借鉴 |
| 输出格式 | CSA宏(FORCEADD/FORCEPROP) | CTW模板DSL | 当前项目更声明式，需确认DEHDL对CTW的兼容性 |
| 坐标映射 | CIS坐标→C纸居中缩放 | layout_mapper.py | 算法逻辑一致，需确认缩放比例差异 |
| 库扫描 | walk目录+解析chips.prt+part.ptf | HDLLibScanner(扫描→ComponentDB) | 功能完整覆盖，当前项目多了symbol.css解析 |
| 编码处理 | _read_file_auto_encoding() | 内置于各解析器 | 需确认当前项目是否也支持GBK回退 |

---

## 附录: 数据流关键数据结构对照

### A.1 匹配结果数据格式

**参考库 (CIS_to_HDL_Mapping.csv)**:
```
refdes,cis_value,cis_footprint,cis_fp_size,hdl_part,hdl_primitive,hdl_package_type,hdl_sn_num,match_level
C460,100nF,HSC0201-HDTB,0201,capacitor,CAPACITOR_0201,C0402,M01.010024,exact
```

**当前项目 (MatchResult)**:
```python
MatchResult(
    confidence=1.0,
    strategy=MatchStrategy.EXACT,
    source_library_id="CIS::C460",
    target_library_id="HDL::capacitor::CAPACITOR_0201",
    pin_mapping={},
    warnings=[],
)
```

### A.2 器件数据格式

**参考库 (Page13_DeviceList.csv)**:
```
RefDes,Value,Footprint,SNUM,PACKAGE_TYPE,Manufacturer,TYPE_NAME,DESCRIPTION
C460,100nF,HSC0201-HDTB,,,,,,
```

**当前项目 (ComponentDef / ComponentInstanceIR)**:
```python
ComponentDef(
    library_id="capacitor::CAPACITOR_0201",
    part_name="CAPACITOR_0201",
    prefix="C",
    footprint="0201",
    ...
)
```

---

> **文档结束** — 此文件为 Phase 0 交付物；Phase 1 精读已完成（2026-08-07），本文件已于 2026-08-07 按实际代码树刷新并吸收 `_reference_index.md` / `reference_project_file_list.md`。
