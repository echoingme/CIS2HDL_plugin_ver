# CIStoHDL_standard Reference Project Index

> **生成日期:** 2026-08-03
> **参考项目路径:** `D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard`
> **目标项目路径:** `D:\26暑假\cis2hdl`
> **用途:** Phase 2 详细比较分析的权威参考文档

---

## 1. 参考项目概述

CIStoHDL_standard 是一个基于 Cadence Concept HDL (DEHDL) 的原理图自动生成工作流，将 OrCAD Capture CIS 中的原理图器件通过匹配算法映射到 HDL 库，并生成 DEHDL 可识别的 .csa 格式原理图页面。整个流程包含四个阶段:

```
Phase 1: 数据提取     export_page13.py       -> Page13_DeviceList.csv
Phase 2: 器件匹配     match_cis_to_hdl.py    -> CIS_to_HDL_Mapping.csv
Phase 3: 页面生成     generate_hdl_sch.py    -> page1.csa (+ 辅助文件)
Phase 4: 脚本生成     generate_hdl_scr.py    -> place_parts.scr
```

---

## 2. 完整文件清单

### 2.1 根目录文件

| 文件路径 | 类型 | 大小(bytes) | 模块分组 | cis2hdl 映射 | 说明 |
|----------|------|------------|----------|-------------|------|
| generate_hdl_sch.py | Python source | 14,617 | generate | core/writer/csa_writer.py | CSA 原理图页面生成 |
| match_cis_to_hdl.py | Python source | 20,504 | match | core/matcher/ | CIS->HDL 器件匹配 |
| export_page13.py | Python source | 15,664 | parse | core/parser/dsn/dsn_parser.py | OrCAD COM 数据提取 |
| generate_hdl_scr.py | Python source | 4,760 | generate | core/writer/sch_writer.py | DEHDL .scr 脚本生成 |
| export_page.tcl | Tcl script | 13,481 | utility | (无直接映射) | Tcl 导出脚本(替代方案) |
| export_page13.tcl | Tcl script | 12,913 | utility | (无直接映射) | Tcl 页13导出(替代方案) |
| diagnose_com.vbs | VBScript | 3,904 | utility | (无直接映射) | COM 对象探测工具 |
| run_tcl_export.bat | Batch script | 1,487 | utility | scripts/ | Tcl 导出批处理 |
| test_tcl.tcl | Tcl test | 996 | utility | (无直接映射) | Tcl 测试脚本 |
| CIS_to_HDL_Mapping.csv | CSV data | 3,035 | config | 中间数据 | 匹配结果(默认输出) |
| CIS_to_HDL_Mapping.txt | TXT report | 6,134 | config | 中间数据 | 匹配报告(可读) |
| CIS_to_HDL_Mapping_Page13.csv | CSV data | 3,035 | config | 中间数据 | 匹配结果(页13) |
| Page13_DeviceList.csv | CSV data | 833 | config | 中间数据 | CIS 器件导出清单 |
| Page13_DeviceList.txt | TXT report | 4,851 | config | 中间数据 | 器件清单(可读) |
| Page13_AnomalyList.txt | TXT report | 1,058 | config | 中间数据 | 异常器件清单 |
| out_hdl.cpm | CPM config | 832 | config | core/writer/cpm_writer.py | DEHDL 工程文件 |
| cds.lib | Cadence config | 98 | config | core/writer/cdslib_writer.py | Cadence 库定义 |
| page1.scr | SCR output | 33,588 | output | core/writer/csa_writer.py | 手动绘制的 CSA 参考 |
| place_parts.scr | SCR output | 8,889 | output | core/writer/sch_writer.py | 批量放置脚本 |
| place_parts_simple.scr | SCR output | 1,754 | output | core/writer/sch_writer.py | 简化放置脚本 |
| test_place.scr | SCR test | 139 | output | (无直接映射) | 单器件测试放置 |
| c2esch.edif | EDIF data | 31,430 | parse | core/parser/edif_parser.py | EDIF 网表(备用解析源) |
| HG5015-BE36_V10.DSN | OrCAD data | 1,619,456 | parse | core/parser/dsn/ | OrCAD 设计文件 |
| HG5015-BE36_V10.EXP | OrCAD export | 65,779 | parse | core/parser/dsn/ | OrCAD 导出文件 |
| HG5015-BE36_V10.opj | OrCAD project | 4,808 | config | GUI 工程设置 | OrCAD 工程文件 |
| HG5015-BE36_V10_0.DBK | OrCAD backup | 1,619,456 | parse | (无直接映射) | OrCAD 备份文件 |
| tcl脚本导入orcad.docx | Word doc | 16,231 | docs | docs/ | Tcl 导入说明文档 |
| adw/shoppingCart.xml | XML config | 1,501 | config | (无直接映射) | DEHDL 购物车配置 |

### 2.2 HDL 库组件 (hdl_lib/)

HDL 库包含 **70+ 个器件目录**，每个器件遵循标准结构:

```
hdl_lib/<part_name>/
  +-- chips/chips.prt           # 组件基元定义 (primitive)
  +-- entity/verilog.v           # Verilog 实体
  +-- entity/vhdl.vhd            # VHDL 实体
  +-- entity/vlog004u.sir        # 符号引脚报告
  +-- entity/pc.db               # 物理编译器数据库
  +-- metadata/pinlist.txt       # 引脚列表
  +-- metadata/revision.dat      # 版本信息
  +-- metadata/pdv_validation.txt # PDV 验证
  +-- part_table/part.ptf        # 多物理表 (PACKAGE_TYPE/VALUE/...)
  +-- sym_1/symbol.css           # 符号定义 (引脚+属性坐标)
  +-- sym_1/module_order.dat     # 模块排序
  +-- sch_1/<name>.con           # 连通性约束 (可选)
  +-- sch_1/<name>.dcf           # 设计约束文件 (可选)
  +-- sch_1/<name>.xcon          # 交叉引用约束 (可选)
  +-- cfg_package/expand.cfg     # 展开配置 (可选)
  +-- master.tag                 # 版本标记
```

**关键器件目录列表 (代表性):**

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

### 2.3 worklib/ 输出目录

| 文件路径 | 类型 | 模块分组 | cis2hdl 映射 |
|----------|------|----------|-------------|
| worklib/out_hdl/sch_1/page1.csa | CSA output | generate | csa_writer.py 输出 |
| worklib/out_hdl/sch_1/page1.csv | CSV output | generate | 连通性文件 |
| worklib/out_hdl/sch_1/page1.cpc | CPC output | generate | cpc_writer.py 输出 |
| worklib/out_hdl/sch_1/page2.csa | CSA output | generate | 第二页输出 |
| worklib/out_hdl/sch_1/page2.csb | CSB binary | generate | 二进制编译页面 |
| worklib/out_hdl/sch_1/page.map | map file | generate | 页面映射 |
| worklib/out_hdl/sch_1/master.tag | tag file | generate | 版本标记 |
| worklib/out_hdl/sch_1/module_order.dat | config | generate | 模块排序 |
| worklib/out_hdl/sch_1/hdldirect.dat | data | config | HDL 直接连接 |
| worklib/out_hdl/sch_1/pc.db | DB file | config | 物理编译器数据库 |
| worklib/out_hdl/sch_1/viewprps.prp | config | generate | 视图属性 |
| worklib/out_hdl/sch_1/verilog.v | Verilog | generate | Verilog 输出 |
| worklib/out_hdl/sch_1/vlog004u.sir | SIR output | generate | 符号引脚报告 |
| worklib/out_hdl/sch_1/out_hdl.xcon | XML config | generate | xcon_writer.py 输出 |
| worklib/out_hdl/sch_1/out_hdl.dcf | DCF config | generate | 设计约束文件 |
| worklib/out_hdl/sch_1/place_parts.scr | SCR output | generate | 放置脚本副本 |

---

## 3. 功能模块映射

### 3.1 Parse Layer -- 数据提取层

| 参考文件 | cis2hdl 文件 | 覆盖度 | 关键差异 |
|----------|-------------|--------|----------|
| export_page13.py | core/parser/dsn/dsn_parser.py | HIGH (80%) | 参考用 COM; 当前用 .DSN 二进制 |
| c2esch.edif | core/parser/edif_parser.py | MEDIUM (50%) | EDIF 备用源 |
| (无) | core/parser/olb/olb_parser.py | NEW | 当前新增 OLB 库解析 |
| (无) | core/parser/olb/olb_reader.py | NEW | 当前新增 OLB 读取器 |

**详细分析:**

export_page13.py (参考):
- 使用 win32com.client.DispatchEx 创建 OrCAD Capture COM 实例
- 通过 app.OpenProject() / app.Session.ActiveDesign 访问设计
- 遍历 design.Schematics[].Pages[] 找到目标页
- 枚举页面 Objects 并过滤 ObjectType==1 (Instance)
- 通过 obj.Properties 集合提取 CIS 属性: RefDes, Value, Footprint, SNUM, PACKAGE_TYPE, Manufacturer, TYPE_NAME, DESCRIPTION
- 输出 Page13_DeviceList.csv 和可读 TXT
- 依赖 pywin32, 仅 Windows 原生 Python

dsn_parser.py (当前):
- 使用 OLE 结构化存储直接读取 .DSN 二进制格式
- 不需要 OrCAD 安装, 跨平台兼容
- ole_reader -> binary_reader -> page_parser 链式解析
- property_audit 验证属性完整性

**导出字段差异:**

| 字段 | 参考 | 当前 | 状态 |
|------|------|------|------|
| RefDes | YES | YES | 一致 |
| Value | YES | YES | 一致 |
| Footprint | YES | YES | 一致 |
| SNUM | YES | part.ptf补充 | 参考有,当前通过part.ptf |
| PACKAGE_TYPE | YES | YES | 一致 |
| Manufacturer | YES | 缺失 | 参考有,当前缺失 |
| TYPE_NAME | YES | YES | 一致 |
| DESCRIPTION | YES | YES | 一致 |
| RefDes-X/Y | YES | YES | 一致 |


### 3.2 HDL 库解析层

| 参考函数 | cis2hdl 文件 | 覆盖度 | 说明 |
|----------|-------------|--------|------|
| match_cis_to_hdl.py::parse_chips_prt() | core/parser/chips_prt.py | HIGH (90%) | chips.prt 解析 |
| match_cis_to_hdl.py::parse_part_ptf() | core/parser/part_ptf.py | HIGH (95%) | part.ptf 解析 |
| generate_hdl_sch.py::get_prop_offsets() | core/parser/symbol_css.py | HIGH (85%) | symbol.css 解析 |

**比较:**
- chips.prt: 参考正则解析 vs 当前 ChipsPrtParser 类, 支持更多字段 (BODY_NAME, PHYS_DES_PREFIX, CLASS, SLOT_TYPE)
- part.ptf: 参考正则分段 vs 当前 PartPtfParser 状态机, 处理引号转义
- symbol.css: 参考硬编码属性偏移 vs 当前 SymbolCSSParser 更完整的语法解析


### 3.3 Match Layer -- 器件匹配层

| 参考文件 | cis2hdl 文件 | 覆盖度 | 关键差异 |
|----------|-------------|--------|----------|
| match_cis_to_hdl.py | core/matcher/pipeline.py | HIGH (90%) | 单体脚本 vs 多阶段管线 |
| match_component() | exact.py/fuzzy.py/feature.py | HIGH (85%) | 三元匹配 vs 多阶段 |
| extract_pkg_size() | feature.py | HIGH (80%) | 特征提取 |
| body_map/body_fallback | prefix_filter.py | HIGH (95%) | 前缀过滤 |

**匹配策略对比:**

参考 (match_cis_to_hdl.py):
1. 提取 RefDes 前缀 (C460 -> C)
2. 按前缀查 HDL 库索引 (by_prefix)
3. body_map 回退: C->capacitor, R->resistor, U->[amplifier,ldo,...]
4. 三重匹配: exact (Footprint+Value) > size (Footprint) > prefix > none
5. normalize_value(): 规范化比较 (大小写, 单位, 空格)

当前 (matcher/):
1. db.search(): part_name + footprint + pin_count
2. 回退搜索 -> 全部
3. 前缀过滤 (filter_candidates_by_refdes)
4. 四阶段管线: Exact -> Fuzzy -> Feature -> Manual
5. YAML 映射持久化

**差异总结:**

| 特性 | 参考 | 当前 |
|------|------|------|
| 匹配级别 | discrete (exact/size/prefix/none) | continuous (confidence 0-1) |
| 匹配策略 | 单层三元匹配 | 多阶段管线推进 |
| 库索引 | 直接按前缀扫描 | DB search + prefix filter |
| Value 匹配 | normalize_value 精确比较 | 模糊名称匹配 |
| Pin count | 不考虑 | 参与候选搜索 |
| 持久化 | 无 | YAML 文件 |

### 3.4 Generate Layer -- 代码生成层

| 参考文件 | cis2hdl 文件 | 覆盖度 | 关键差异 |
|----------|-------------|--------|----------|
| generate_hdl_sch.py | core/writer/csa_writer.py | VERY HIGH (95%) | CSA 格式生成 |
| generate_csa() | _build_csa_content() | VERY HIGH (95%) | 核心 CSA 内容 |
| map_cis_to_dehdl_coords() | _map_coords_to_dehdl() | VERY HIGH (98%) | 坐标映射 |
| calc_position() | _grid_position() | VERY HIGH (100%) | 网格回退 |
| generate_hdl_scr.py | core/writer/sch_writer.py | MEDIUM (40%) | 当前不生成 .scr |

**CSA 格式生成详细对比:**

| CSA 语句 | 参考 | 当前 | 差异说明 |
|----------|------|------|----------|
| FILE_TYPE/SET COLOR_* | 一致 | 一致 | 无差异 |
| FORCEADD C SIZE PAGE | (-250 0) | (-250 0) | 一致 |
| FORCEADD {BODY}..{S} | ..1 固定 | ..{section} 动态 | 当前多section |
| VALUE | R 1 J 1 DISPLAY | J 0 DISPLAY PAINT | 缺少ROT,加PAINT |
| LOCATION | 始终  | 条件区分 | 按section>1 |
| CDS_LOCATION | 无 | 新增 | 当前独有 |
|  / CDS_SEC | 无 | 新增 | 当前独有 |
| PATH/PART_NAME等 | 直接INVISIBLE | DISPLAY+PAINT+INVISIBLE | 过渡渲染 |
| LASTPIN | 无 | 抑制(方案A) | 显式抑制 |
| QUIT | QUIT | QUIT | 一致 |

**坐标映射算法:** 几乎完全相同 (中心缩放+Y轴反转+0.7比例+边界检查)
**网格回退:** 5列, 2000x1500间距, 起点(-10500,7500) -- 完全一致

**body_name 解析差异:**
- 参考: 直接从 CSV hdl_part 字段 (e.g. capacitor->CAPACITOR)
- 当前: match_map -> library_id -> prefix -> fallback (第2步可能产生 DSN 层级路径)

### 3.5 Config/Data Files

| 参考文件 | 格式 | cis2hdl 映射 | 状态 |
|----------|------|-------------|------|
| out_hdl.cpm | CPM (SPI) | core/writer/cpm_writer.py | COMPATIBLE |
| cds.lib | Cadence lib | core/writer/cdslib_writer.py | COMPATIBLE |
| *.xcon | XML (CSSchema002) | core/writer/xcon_writer.py | COMPATIBLE |
| *.dcf | Lisp/S-expr | (无独立 writer) | PLANNED |
| *.con | Lisp/S-expr | (OutputManager) | PLANNED |
| expand.cfg | 文本配置 | core/writer/cpc_writer.py | COMPATIBLE |
| module_order.dat | 模块排序 | core/writer/output_manager.py | COMPATIBLE |
| master.tag | 版本标记 | core/writer/output_manager.py | COMPATIBLE |


---

## 4. 输出文件格式比较

| 文件类型 | 参考格式 | 当前格式 | 兼容性状态 |
|----------|---------|---------|-----------|
| .csa | MACRO_DRAWING (FORCEADD/FORCEPROP) | MACRO_DRAWING (FORCEADD/FORCEPROP) | COMPATIBLE |
| .cpc | ISCELL text | cpc_writer.py | COMPATIBLE |
| .csv (连通性) | FILE_TYPE=CONNECTIVITY | (未验证) | 待验证 |
| .cpm | SPI 格式 | cpm_writer.py | COMPATIBLE |
| .xcon | CSSchema002 XML | xcon_writer.py | COMPATIBLE |
| .dcf | Allegro ConstraintFile | (无独立生成) | 待实现 |
| .con | conceptHDL | (未实现) | 待实现 |
| page.map | 格式化文本 | output_manager.py | COMPATIBLE |

### CSA 格式详细对比

参考 header 与当前 -- **格式完全一致**



差异: 当前缺少 R 1 (rotation), J1->J0, 增加 PAINT ORANGE

### .dcf 格式 (关键发现)

DCF 文件包含每个器件实例的属性快照 (CDS_LIB, CDS_LMAN_SYM_OUTLINE,
DESCRIPTION, JEDEC_TYPE, PACKAGE_TYPE, PART_NAME, SN_NUM, VALUE, XY, ROT),
是 DEHDL 编译后的产物。当前通过 CSA -> DEHDL 编译 -> 自动生成 DCF。

---

## 5. 关键算法初步比较

### 5.1 CSA 生成方法

**参考 (generate_hdl_sch.py):**
1. 文件头 (FILE_TYPE, SET COLOR_*, PAGE_NUMBER)
2. C SIZE PAGE 边框
3. 遍历: get_prop_offsets -> FORCEADD..1 -> PATH -> PART_NAME -> PACKAGE_TYPE/JEDEC_TYPE/DESCRIPTION/SN_NUM -> VALUE -> 
4. QUIT

**当前 (csa_writer.py):**
1. 文件头 (相同)
2. C SIZE PAGE 边框 (相同)
3. 坐标映射 (map_coords_to_dehdl, 算法相同)
4. 遍历: _resolve_body_name -> FORCEADD..{section} -> VALUE+PAINT -> PATH+DISPLAY+PAINT+INVISIBLE -> CDS_LMAN_SYM_OUTLINE -> CDS_LIB -> PART_NAME -> DESCRIPTION -> PACKAGE_TYPE -> SN_NUM -> JEDEC_TYPE -> LOCATION/ -> CDS_LOCATION -> /CDS_SEC
5. QUIT

**六个关键差异:**
1. Section支持: 当前多section, 参考..1
2. LOCATION vs : 当前按section>1条件区分
3. CDS_LOCATION//CDS_SEC: 当前新增
4. 过渡渲染: 当前INVISIBLE前增加DISPLAY+PAINT
5. 属性偏移: 参考symbol.css动态; 当前硬编码
6. PAINT颜色: 当前显式PAINT ORANGE/MONO

### 5.2 匹配算法

参考: 三层匹配 (exact/size/prefix), 单体函数, by_prefix索引
当前: 四阶段管线 (Exact/Fuzzy/Feature/Manual), 链式调用, DB search+filter

| 特性 | 参考 | 当前 |
|------|------|------|
| 匹配级别 | discrete (4级) | continuous (0-1) |
| 策略 | 单层三元匹配 | 多阶段管线 |
| 库索引 | by_prefix扫描 | DB search+filter |
| Value匹配 | normalize精确 | 模糊名称 |
| Pin count | 不考虑 | 参与搜索 |
| 持久化 | 无 | YAML |

### 5.3 数据提取

| 特性 | 参考 (COM) | 当前 (OLE) |
|------|-----------|-----------|
| 方式 | win32com | OLE Structured |
| 依赖 | OrCAD+pywin32 | 纯Python |
| 平台 | Windows only | 跨平台 |
| 多源 | 仅OrCAD | DSN+EDIF+OLB |

---

## 6. 数据流完整链路

参考:


当前:



---

## 7. 文件扩展名参考

| 扩展名 | 全称 | 作用 | 参考 | 当前 |
|--------|------|------|------|------|
| .csa | Concept Schematic ASCII | DEHDL 页面 (MACRO_DRAWING) | YES | YES |
| .csb | Concept Schematic Binary | 编译后页面 | YES | DEHDL产生 |
| .cpc | Concept Page Config | 页面配置 | YES | YES |
| .cpm | Concept Project Manager | 工程定义 | YES | YES |
| .xcon | Cross-Connection XML | 交叉引用约束 | YES | YES |
| .dcf | Design Constraint File | 设计约束 (Allegro) | YES | PLANNED |
| .con | Connectivity | 连通性约束 | YES | PLANNED |
| .scr | Script | DEHDL 控制台脚本 | YES | NO |
| .csv | Comma-Separated Values | 器件名单/连通性 | YES | YES |
| .ptf | Part Table File | HDL 库料表 | YES | YES |
| .prt | Part/Primitive | HDL 库基元定义 | YES | YES |
| .css | Cadence Symbol Sheet | 符号定义 | YES | YES |
| .sir | Symbol Interconnect Report | 引脚连接报告 | YES | YES |
| .DSN | Design | OrCAD 设计文件 | YES | YES |
| .opj | OrCAD Project | OrCAD 工程 | YES | NO |
| .edif | EDIF | 网表交换格式 | YES | YES |
| .olb | OrCAD Library Binary | OrCAD 库 | NO | YES |
| .v/.vhd | Verilog/VHDL | HDL 实体 | YES | NO |

---

## 8. 编排脚本 (参考项目独有)

| 脚本 | 类型 | 大小(bytes) | 功能 |
|------|------|------------|------|
| run_tcl_export.bat | Batch | 1,487 | Tcl 导出启动 |
| diagnose_com.vbs | VBScript | 3,904 | COM 对象探测 |
| export_page.tcl | Tcl | 13,481 | Tcl 导出脚本 |
| export_page13.tcl | Tcl | 12,913 | Tcl 页13导出 |
| test_tcl.tcl | Tcl | 996 | Tcl 测试 |

---

## 9. 关键待解决问题 (Phase 2 对比发现)

1. **CSA 格式微差异**: 当前 INVISIBLE 前增加 DISPLAY+PAINT 过渡 (PATH, PART_NAME, CDS_LIB 等), 参考直接 INVISIBLE。需验证 DEHDL 解析正确性。

2. **ROTATION 缺失**: 参考  使用 R 1 J 1, 当前使用 J 0 (无 ROT)。需确认对位号显示的影响。

3. **symbol.css 偏移未集成**: SymbolCSSParser 已实现但 CSAWriter 使用硬编码偏移, 可能导致属性位置不理想。

4. **body_name 解析脆弱性**: _resolve_body_name() 第2步直接从 library_id 取最后一段, DSN 层级路径 (如 VRTL8367RB-VB_LQ128EP_0) 不是有效的 HDL 库目录名。

5. **Value 匹配差异**: 参考用精确 value 匹配 + normalize, 当前用模糊名称匹配, 可能导致不同匹配结果。

6. **DCF 生成**: 参考的 DCF 包含属性快照 (PACKAGE_TYPE, SN_NUM, etc.), 当前不生成 .dcf, 由 DEHDL 编译后自动产生。

---

**附录**: 完整文件清单已导出至:
- docs/_ref_file_list.csv (参考项目)
- docs/_cis2hdl_file_list.csv (当前项目)
