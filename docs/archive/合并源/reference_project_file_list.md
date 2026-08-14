# 参考项目文件清单

**扫描路径**: `D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\`
**扫描日期**: 2026-08-03
**排除目录**: `备份`、`temp`

---

## 总体统计

| 项目 | 数量 |
|------|------|
| 文件总数 (不含备份) | 3,211 |
| hdl_lib 器件目录 | 130 |
| worklib 子目录 | 4 |

---

## 顶层源文件（Python脚本）

| 文件 | 大小 | 功能 |
|------|------|------|
| `generate_hdl_sch.py` | 14,617 B | **CSA 原理图生成** (核心：FORCEADD/FORCEPROP宏) |
| `match_cis_to_hdl.py` | 20,504 B | **CIS→HDL 器件匹配** |
| `export_page13.py` | 15,664 B | DSN 数据导出 |
| `generate_hdl_scr.py` | 4,760 B | .scr 脚本生成 (手动放置器件) |

## 顶层关键文件

| 文件 | 大小 | 重要性 |
|------|------|--------|
| `out_hdl.cpm` | 832 B | ⭐ **CPM 工程文件** — `cpm_version '16.6'` |
| `cds.lib` | 98 B | 库定义文件 |
| `CIS_to_HDL_Mapping.csv` | 3,035 B | 器件映射表 |
| `page1.scr` | 33,588 B | DEHDL 宏脚本参考 |

## worklib/out_hdl/sch_1/ 输出文件（参考格式）

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

## hdl_lib/ 目录结构（每个器件）

```
hdl_lib/<device>/
├── chips/
│   ├── chips.prt          ← Primitive 定义 (BODY_NAME, PHYS_DES_PREFIX, CLASS)
│   ├── chips.prt.baselined ← 基线版本
│   └── master.tag
├── entity/
│   ├── verilog.v          ← Verilog 模块
│   ├── vhdl.vhd           ← VHDL 实体
│   ├── pc.db              ← 引脚约束数据库
│   ├── vlog004u.sir       ← 符号实例报告
│   └── master.tag
├── metadata/
│   ├── pinlist.txt        ← 引脚列表
│   ├── pdv_validation.txt
│   ├── revision.dat/log
│   ├── revHistory.log
│   └── master.tag
├── part_table/
│   ├── part.ptf           ← ⭐ Physical Part Table
│   └── master.tag
├── sym_1/ (sym_2/...)
│   ├── symbol.css         ← ⭐ 符号图形定义 (P指令, L/C/M/...)
│   ├── symbol.css.baselined
│   ├── module_order.dat
│   └── master.tag
└── [可选] cfg_package/, sch_1/
```

## 文件类型统计

| 扩展名 | 数量 | 用途 |
|--------|------|------|
| `.tag` | 965 | 元数据标签 |
| `.css` | 445 | 符号图形定义 |
| `.baselined` | 293 | 基线信息 |
| `.txt` | 257 | 文本/日志 |
| `.log` | 254 | 日志 |
| `.dat` | 147 | 数据文件 |
| `.sir` | 128 | 符号实例报告 |
| `.v` | 126 | Verilog |
| `.db` | 125 | 数据库 |
| `.vhd` | 124 | VHDL |
| `.prt` | 124 | Primitive 定义 |
| `.ptf` | 123 | Part Table |
| `.csa` | ~4 | CSA 页面 |
| `.csb` | ~4 | 二进制页面 |
| `.dcf` | ~4 | 设计约束 |
| `.xcon` | ~4 | 跨连接 |
| `.cpm` | 1 | 工程文件 |
| `.lib` | 1 | 库定义 |
