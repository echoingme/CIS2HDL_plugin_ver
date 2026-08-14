# 参考库逐文件精读笔记

> 版本: v1.0 | 日期: 2026-07-31 | 作者: 寇豆码（代码阅读分析师）
>
> 本文件包含对 `CIStoHDL_standard/` 参考库中全部文件的逐文件精读笔记。
>
> 修订: 2026-08-07 | 「与当前项目的映射」补充 v2.0 新 writer（csa/scr/xcon/cpc/output_manager）与 matcher v2.0 文件；其余精读笔记内容保留不动。

---

━━━ 文件 #1: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\match_cis_to_hdl.py ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\match_cis_to_hdl.py
  • 语言/格式: Python 3 (纯标准库，零外部依赖)
  • 行数估算: 481 行
  • 大小: 20,504 B (约20KB)

🎯 职责定位
  • 功能域: 器件匹配
  • 解决什么问题: 将从 OrCAD CIS 原理图导出的器件清单（DeviceList.csv）与 HDL 标准器件库（hdl_lib/）进行自动匹配，输出 CIS→HDL 的器件映射表。这是整个 CIStoHDL 转换流程的"心脏"——没有匹配结果，后续的 CSA/SCR 代码生成就无从进行。

🧠 核心算法

  **三重匹配策略（由高到低保真度）：**

  1. **Level 1: 精确匹配 (exact)** — 同时在 Footprint 封装尺寸和 Value 值两个维度上匹配成功时触发。
     - 从 CIS Footprint 字符串中提取尺寸代码（如 HSC0201-HDTB→0201，使用 `extract_pkg_size()`）
     - 在 HDL 库器件的 primitive 名称中搜索该尺寸代码（如 CAPACITOR_0201 中包含 0201）
     - 在 part.ptf 料表中搜索与 CIS Value 规范化的值匹配的库存行
     - 两个条件同时满足 → `exact` 等级

  2. **Level 2: 尺寸匹配 (size)** — Footprint 尺寸在 primitive 名称中找到，但 Value 值在 part.ptf 料表中找不到匹配项。
     - 此时仍选择该 primitive 作为匹配，但使用 part.ptf 的第一行作为参考行（ref_row）
     - SNUM 字段为空（因为没有精确的库存行对应）

  3. **Level 3: 前缀匹配 (prefix)** — 仅通过 RefDes 前缀（如 C→capacitor, R→resistor）找到对应的 HDL 库器件类别。
     - 使用 `body_fallback` 映射表进行回退匹配
     - 排序策略：优先选择 `body_fallback` 中指定的通用器件（如 capacitor/resistor），而非目录中碰到的第一个器件

  4. **Level 0: 未匹配 (none)** — 连前缀都无法匹配时。

  **关键数据结构：**
  - `catalog`: 两级索引 — `by_prefix[prefix]`（前缀→候选器件列表）+ `by_part_name[part_name]`（器件名→详细信息）
  - `primitives`: 从 chips.prt 解析的列表，每项含 `part_name/body_name/prefix/class`
  - `ptf_data`: 从 part.ptf 解析的 dict，`{PART_NAME: [row_dict, ...]}`
  - `body_fallback`: 硬编码的前缀→通用器件名映射表（两次出现：lines 224-234 和 293-303）

  **复杂度:** O(N×M×K)，其中 N=CIS器件数，M=候选HDL器件数，K=每个器件的primitive数。实际可接受因为 M、K 通常很小。

  **封装尺寸提取算法 (`extract_pkg_size()`):**
  - 优先级链：BGA→4位数字代码→SOT/QFN/MLF/TO封装名称→前10字符截断
  - 值得注意的是：BGA 只取"BGA+数字"（如 BGA96），不匹配完整的 BGA96-32-1609W

  **Value 规范化算法 (`normalize_value()`):**
  - 大写化 + 去空格
  - 将 "KOHM"/"MOHM" 标准化为 "K"/"M"（注意：不处理 "OHM"→"" 的规范化！）
  - 去除尾部 `*` 标记
  - 注意：PF→PF, NF→NF, UF→UF 实际无变化（本来就是大写），可能最初有其他意图

📡 对外接口
  • 暴露的函数/类:
    - `read_cis_data(csv_path)` → `list[dict]`: 读取 CIS 器件清单 CSV
    - `_read_file_auto_encoding(filepath)` → `str`: 自动编码检测文件读取器
    - `parse_chips_prt(filepath)` → `list[dict]`: 解析 chips.prt
    - `parse_part_ptf(filepath)` → `dict[str, list[dict]]`: 解析 part.ptf
    - `extract_pkg_size(footprint_str)` → `str`: 封装尺寸提取
    - `scan_hdl_library(lib_dir)` → `dict`: 扫描 HDL 库构建索引
    - `match_component(comp, catalog)` → `dict`: 核心匹配函数
    - `normalize_value(v)` → `str`: Value 规范化
    - `write_mapping_report(results, output_dir)`: 输出 CSV+TXT 报告
    - `format_string(fmt, values)`: 中文字符串安全格式化
    - `main()`: 主流程（4 步管线）
  • 输入契约: CIS CSV 必须包含 RefDes, Value, Footprint, RefDes-X, RefDes-Y 列；HDL 库每个目录下必须有 chips/chips.prt 和 part_table/part.ptf
  • 输出契约: 生成两个文件 — CIS_to_HDL_Mapping.csv（14列）和 CIS_to_HDL_Mapping.txt（格式化报告）

🔗 内部依赖
  • 依赖哪些模块: 纯标准库 — os, csv, re, sys, collections.defaultdict, locale
  • 被谁调用: 作为独立脚本运行，或被 run_tcl_export.bat 编排调用。输出被 generate_hdl_sch.py 和 generate_hdl_scr.py 消费

✨ 设计亮点

  1. **零外部依赖**: 仅使用 Python 标准库，这在 Windows/OrCAD 环境中极为重要，避免了依赖管理地狱。

  2. **编码自动回退**: `_read_file_auto_encoding()` 先尝试 UTF-8，失败后使用 `locale.getpreferredencoding()`（中文 Windows 为 GBK）。这是处理 Cadence 工具链生成文件（常混用编码）的实用方案。

  3. **全局配置集中化**: 顶部三个全局变量（PAGE_NUM, CIS_CSV, HDL_LIB_DIR, OUTPUT_DIR）统一管理所有路径。虽然看似"硬编码"，但在这种单页转换脚本中反而最实用。

  4. **前缀回退机制**: `body_fallback` 映射表提供了从 RefDes 前缀到语义级 HDL 器件类别的映射。如 C→[capacitor], R→[resistor], U→[amplifier, ldo, dc_dc, interface, logic_gate]。这比单纯按字母匹配要智能得多。

  5. **匹配等级符号化**: 用 ●/○/△/✕ 四个符号直观表示匹配质量，在 TXT 报告中一目了然。

  6. **异常处理器件命名规范**: 当 prefix 不在标准映射中时（如 FB→[fb], Y→[crystal,osc], J→[connector,rj45,...]），通过 `body_map` 字典优雅处理边缘情况。

⚠️ 潜在问题

  1. **body_fallback 代码重复（DRY 违规）**: 相同的 `body_fallback` 字典在 `match_component()` 中出现了两次（lines 224-234 用于无候选时的查找，lines 293-303 用于有候选但未匹配时的回退排序）。合并为一个模块级常量可减少维护负担。

  2. **extract_pkg_size 对非标准封装的处理**: 当 Footprint 不包含 BGA 也不包含 4 位数字时，回退到 `footprint_str[:10]` 截断或 SOT/QFN 等正则匹配。这可能在某些极端封装名称（如 "HSC0201-HDTB" 中的 "HSC-" 或 "HDTB" 部分）上产生意外结果。

  3. **normalize_value 不完整**: "KOHM"→"K", "MOHM"→"M" 但缺少 "OHM"→"" 的规则，可能导致 "10OHM" 和 "10" 的比较失败。

  4. **硬编码路径**: 全局变量中的 Windows 绝对路径（`C:\Users\zhong\Desktop\test\...`）使脚本不可移植。

  5. **候选器件匹配的"第一个匹配即返回"策略**: `match_component()` 在找到尺寸匹配后立即 `break`，不考虑多个候选 primitive 都有相同尺寸代码的情况。如果在 capacitor 下同时有 CAPACITOR_0201 和 CAPACITOR_0201_HV，只有第一个被选中。

  6. **part.ptf 解析对 SN_NUM 提取的正则脆弱性**: `sn_match = re.match(r"([^(~]+)", sn_field)` 假设 SN 字段格式为 "SN(~alias)"，但这个假设在其他器件库格式中可能不成立。

  7. **无进度条或 ETA**: 对于大批量器件匹配（如全板 >500 个器件），用户看不到进度。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/matcher/pipeline.py`（匹配管道）+ `cis2hdl/core/matcher/exact.py` + `cis2hdl/core/matcher/fuzzy.py` + `cis2hdl/core/matcher/feature.py`
    <!-- 已修改：补充 matcher v2.0 文件 —— 候选生成：type_hypothesis.py/candidate_pool.py/prefix_filter.py；匹配：passive_matcher.py/active_matcher.py/value_matcher.py/fallback.py；配置打分：match_config.py/scoring.py；基础：base.py/registry.py（v2.0 已重构为两阶段，原"四级管道"描述为历史口径） -->
  • 实现状态: 已实现但差异大
  • 关键差异:
    - 参考库：三重匹配（exact/size/prefix）在一个函数中
    - 当前项目：两阶段匹配管道（v2.0：TypeHypothesis→CandidatePool→PassiveMatcher/ActiveMatcher），各模块独立实现
    - 参考库的 `size` 匹配是当前项目 `exact` 匹配的一个子策略
    - 参考库的 `prefix` 回退映射表在当前项目中可能由 `fuzzy` 匹配覆盖
    - 参考库直接操作 CSV 文件；当前项目通过 IR 层（ComponentDef/MatchResult）解耦

---

━━━ 文件 #2: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\CIS_to_HDL_Mapping.txt ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\CIS_to_HDL_Mapping.txt
  • 语言/格式: 纯文本（格式化报告，由 match_cis_to_hdl.py 的 write_mapping_report() 生成）
  • 行数估算: 56 行
  • 大小: 6,134 B

🎯 职责定位
  • 功能域: 配置与映射（匹配结果样本）
  • 解决什么问题: 提供 human-readable 的 CIS→HDL 器件匹配结果，包含统计摘要和异常清单。这是理解匹配输出格式和匹配等级的"参考标准"。

🧠 核心算法
  • N/A（纯数据文件，非代码）
  • 但格式结构至关重要——它定义了 DEHDL 转换管道的"数据契约"

📡 对外接口
  • 暴露的函数/类: N/A
  • 输入契约: 由 match_cis_to_hdl.py 生成
  • 输出契约: 被人工阅读，或被 generate_hdl_sch.py/generate_hdl_scr.py 消费（通过同名的 .csv 版本）

🔗 内部依赖
  • 依赖哪些模块: 无（输出产物）
  • 被谁调用: 被 generate_hdl_sch.py 通过 CSV_MAPPING 路径间接引用

✨ 设计亮点

  1. **四等级符号系统**: ●/○/△/✕ 直观表达匹配质量，这在命令行输出中非常有效。
  2. **统计摘要前置**: 报告顶部直接给出 4 级统计数字，用户一眼看到全局匹配率。
  3. **固定列宽表格**: 140 字符定宽表格适合终端和纯文本阅读器。
  4. **异常器件专区**: 底部集中列出未匹配和前缀匹配的器件，用于人工审核。

⚠️ 潜在问题

  1. **中英文混合对齐问题**: 报告中使用 `format_string()` 的 `%` 格式化来处理中文对齐，但固定列宽假设每个中文字符占 2 个英文字符宽度——这在某些终端/字体下可能不准。
  2. **CSV 和 TXT 内容重复**: 两者包含完全相同的数据和统计，增加了维护成本。
  3. **数据样本局限性**: 仅 27 个器件、24 个 exact、2 个 size、1 个 prefix、0 个 none——覆盖率很高但没有复杂边缘案例（如大量未匹配器件）。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/ir/match.py` 中的 MatchResult + `cis2hdl/core/diagnostics/report_gen.py`
  • 实现状态: 已实现但差异大
  • 关键差异:
    - 参考库：静态 TXT 报告由 match_cis_to_hdl.py 内嵌生成
    - 当前项目：结构化 MatchResult IR + 独立的 report_gen.py 诊断管道
    - 当前项目多了 JSON/HTML 等多格式报告输出支持

---

━━━ 文件 #3: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\generate_hdl_sch.py ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\generate_hdl_sch.py
  • 语言/格式: Python 3 (纯标准库)
  • 行数估算: 368 行
  • 大小: 14,617 B (约15KB)

🎯 职责定位
  • 功能域: 代码生成（CSA 原理图宏）
  • 解决什么问题: 读取匹配结果（CIS_to_HDL_Mapping.csv），为每个器件生成 DEHDL 的 CSA 宏文件（FORCEADD/FORCEPROP 命令序列），同时生成配套的连通性文件（.csv）、配置（.cpc）、页面映射（page.map）等 DEHDL 项目文件。

🧠 核心算法

  **CSA 生成管线（5步）：**

  1. **读取映射表**: 从 CSV 读取 14 列数据（refdes, cis_value, cis_footprint, cis_x, cis_y, hdl_part, hdl_primitive 等）

  2. **坐标映射 (`map_cis_to_dehdl_coords()`)**: 
     - 收集所有器件的 CIS 坐标，计算包围盒（min/max）
     - 计算中心点 `cis_cx, cis_cy`
     - 计算缩放比例：`scale = min(page_w/cis_w, page_h/cis_h) * 0.7`（取宽高比中较小者 ×0.7 保证不超出页面）
     - C 纸可用区域：x∈[-10200, -550], y∈[400, 7200]
     - Y 轴取反（CIS 和 DEHDL 的 Y 方向相反）
     - 网格回退：没有 CIS 坐标的器件使用 `calc_position()` 按 COLS=5 的网格排列

  3. **symbol.css 属性偏移读取 (`get_prop_offsets()`)**: 
     - 解析 symbol.css 中的 `P "NAME" ...` 行
     - 提取每个属性的 (x, y, rot, just) 偏移量
     - 用于 FORCEPROP 时精确定位属性文本相对于器件原点的位置

  4. **CSA 宏生成 (`generate_csa()`)**: 
     - FILE_TYPE = MACRO_DRAWING 声明
     - 颜色设置（WIRE=YELLOW, PROP=ORANGE, BODY=GREEN 等）
     - 页面边框添加：C SIZE PAGE 符号 + CDS_LMAN_SYM_OUTLINE 属性
     - 每个器件循环：
       a. FORCEADD {cell_name}..1 — 添加器件实例
       b. FORCEPROP PATH — 设置实例标识
       c. FORCEPROP PART_NAME — 设置器件型号（primitive 名）
       d. FORCEPROP PACKAGE_TYPE / JEDEC_TYPE / DESCRIPTION / SN_NUM — 库存属性（INVISIBLE）
       e. FORCEPROP VALUE — 设置值属性（**可见**，DISPLAY 带缩放因子 0.851064）
       f. FORCEPROP $LOCATION — 设置位号（**可见**，GREEN 涂色）

  5. **辅助文件生成**:
     - `page1.csv`: 最小连通性文件（FILE_TYPE=CONNECTIVITY, NC 网络）
     - `page1.cpc`: 单元配置（`#ISCELL hdl_lib c#20size#20page * *`）
     - `page.map`: 页面映射（`1 1 DDR3\n`）
     - `master.tag`: 设计标签文件
     - `module_order.dat`: 模块顺序文件（Version 15.0 格式）

  **FORCEADD/FORCEPROP 指令格式解析：**
  ```
  FORCEADD CAPACITOR..1        ← 添加器件实例
  (-10500 7500);                ← 放置坐标
  FORCEPROP 1 LAST PATH I1     ← 设置属性（1=选择第一个属性实例）
  J 0                           ← 对齐方式 0
  (-10500 7500);                ← 属性位置
  DISPLAY INVISIBLE (x y);      ← 可见性控制
  ```

  **网格布局参数：**
  - COLS=5, SPACING_X=2000, SPACING_Y=1500
  - START_X=-10500, START_Y=7500

📡 对外接口
  • 暴露的函数/类:
    - `get_prop_offsets(body_name)` → `dict[str, tuple]`: symbol.css 解析器
    - `calc_position(index, total)` → `(int, int)`: 网格位置计算
    - `map_cis_to_dehdl_coords(components)`: 原地修改 components，添加 dehdl_x/dehdl_y
    - `generate_csa(components)` → `str`: CSA 宏内容生成
    - `generate_csv()` / `generate_cpc()` / `generate_page_map()` / `generate_master_tag()` / `generate_module_order()`: 辅助文件生成
    - `main()`: 主入口，支持 --page 和 --mapping 参数
  • 输入契约: 映射 CSV 必须包含 refdes, cis_value, cis_x, cis_y, hdl_part, hdl_primitive, hdl_package_type, hdl_jedec_type, hdl_description, hdl_sn_num, match_level 列
  • 输出契约: 在 `worklib/{DESIGN_NAME}/sch_{page}/` 下生成 page{N}.csa, page{N}.csv, page{N}.cpc, page.map, master.tag, module_order.dat

🔗 内部依赖
  • 依赖哪些模块: csv, os, locale, argparse（纯标准库）
  • 被谁调用: 独立运行，消费 match_cis_to_hdl.py 的 CSV 输出
  • 外部依赖: 需要访问 hdl_lib/ 下的 symbol.css 文件读取属性偏移

✨ 设计亮点

  1. **symbol.css 驱动的属性定位**: 不从代码硬编码属性偏移，而是从 symbol.css 动态读取。这是其"数据驱动"设计的关键——当 HDL 库器件符号更新时，生成器自动适应。

  2. **双坐标系策略**: 
     - 优先使用 CIS 原始坐标（通过缩放居中对齐到 C 纸）
     - 回退到规则网格布局（5 列）
     - 这种"保形布局"策略最大程度保留了原始设计的视觉结构

  3. **属性可见性分层**: VALUE 和 $LOCATION 设为可见（带缩放因子），其他属性（PATH, PART_NAME, PACKAGE_TYPE, SN_NUM 等）设为 INVISIBLE。这保持了 DEHDL 页面整洁。

  4. **模块化辅助文件**: 每个辅助文件由独立函数生成，返回字符串。这使得测试和替换（如为不同项目生成不同的 page.map）变得容易。

  5. **命令行参数化**: 虽然全局配置区有硬编码路径，但 main() 也支持 --page 和 --mapping 参数，提供了一定的灵活性。

  6. **编码兼容**: CSA 文件使用 `locale.getpreferredencoding()` 写入（与 match_cis_to_hdl.py 保持一致），辅助文件使用 UTF-8。

⚠️ 潜在问题

  1. **symbol.css 解析脆弱性**: `get_prop_offsets()` 依赖于 `.split('"')` 然后索引 parts[4] 获取坐标。如果 symbol.css 格式有微小变化（如引号内含空格），解析结果就会错误。缺少错误恢复机制。

  2. **硬编码的 DISPLAY 缩放因子**: `DISPLAY 0.851064` 和 `DISPLAY 0.468085` 是魔法数字，没有注释说明其来源或含义。这些可能是 DEHDL 内部渲染参数。

  3. **硬编码的 C 纸边框坐标**: 
     - 边框符号 "C SIZE PAGE..1" 放置于 (-250, 0)
     - 器件区域 (-10500~-2500, 100~7500)
     - 这些坐标针对特定 DSN 文件的全局坐标系统，不具备通用性

  4. **无未匹配器件处理逻辑**: 即使 match_level 为 "none"，器件仍会被添加到 CSA 文件中，使用默认的 "capacitor" 作为 cell_name。这可能导致 DEHDL 编译错误（cell 不存在）。

  5. **module_order.dat 保护不完整**: `if fname == "module_order.dat" and os.path.exists(fpath): continue` — 只保护 module_order.dat，不保护其他可能被用户修改的文件。

  6. **坐标映射的 Y 轴符号**: `dy = page_cy - dy * scale` 中 Y 取反是正确的，但逻辑隐藏在表达式内部，没有显式的坐标变换注释说明。

  7. **字符串转义问题**: CSA 内容如果包含特殊字符（如引号、分号），可能导致 DEHDL 宏解析错误。当前没有转义处理。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/writer/sch_writer.py`（SCH 原理图生成）+ `cis2hdl/core/parser/symbol_css.py`（symbol.css 解析）+ `cis2hdl/core/parser/layout_mapper.py`（坐标映射）
    <!-- 已修改：补充 v2.0 新 writer —— csa_writer.py（CSA 主输出）/ cpc_writer.py（.cpc 页面配置）/ output_manager.py（page.map、master.tag、module_order.dat）/ xcon_writer.py（.xcon 交叉连接） -->
  • 实现状态: 已实现但差异大
  • 关键差异:
    - 参考库：直接生成 CSA 宏文本（命令式）
    - 当前项目：CTW 模板 DSL（声明式），由 DEHDL 编译模板
    - symbol.css 解析在参考库中是 generate_hdl_sch.py 的子功能，当前项目独立为 symbol_css.py
    - 坐标映射在参考库中是 generate_hdl_sch.py 的子功能，当前项目独立为 layout_mapper.py
    - 当前项目的 sch_writer.py 覆盖了参考库中 generate_hdl_sch.py + generate_hdl_scr.py + page1.scr + place_parts.scr 的功能

---

━━━ 文件 #4: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\generate_hdl_scr.py ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\generate_hdl_scr.py
  • 语言/格式: Python 3 (纯标准库 + datetime)
  • 行数估算: 140 行
  • 大小: 4,760 B

🎯 职责定位
  • 功能域: 代码生成（SCR 交互式脚本）
  • 解决什么问题: 生成 Concept HDL 控制台可执行的 .scr 脚本，实现交互式逐器件放置。与 generate_hdl_sch.py 的"全自动宏模式"不同，.scr 脚本模式需要用户在 DEHDL 图形界面中手动点击每个器件的放置位置。

🧠 核心算法

  **SCR 生成流程：**

  1. **读取映射表**: 从 CIS_to_HDL_Mapping.csv 读取 8 个关键列
  2. **生成 SCR 头部注释**: 花括号 `{}` 包裹的注释块，含器件总数和时间戳
  3. **逐器件生成指令块**:
     - 注释块：`{ [idx/total] RefDes Value ... 匹配等级 }`
     - add 命令：`add <hdl_lib>{cell_name}` — 从 HDL 库添加器件
     - 属性设置：`: %Value:PROPERTY=value` 格式（DEHDL 控制台命令）
     - 用户提示：`{ >>> 请点击放置 {refdes} <<< }`
  4. **尾部**: 完成注释 + 结束符 `;`

  **SCR 命令格式解析：**
  ```
  {                        ← 注释块开始（DEHDL SCR 语法）
    [1/27] C460  100nF
    HDL器件: capacitor  Primitive: CAPACITOR_0201
    料号: M01.010024
    匹配等级: exact
  }
  add <hdl_lib>capacitor    ← 从 hdl_lib 库添加 capacitor 器件
  :%Value:PART_NAME=CAPACITOR_0201   ← 属性设置
  :%Value:VALUE=100nF
  :%Value:JEDEC_TYPE=0201
  :%Value:PACKAGE_TYPE=C0402
  :%Value:SN_NUM=M01.010024
  { >>> 请点击放置 C460 (100nF) <<< }
  ```

  **与 generate_hdl_sch.py 的关键区别：**
  | 维度 | generate_hdl_sch.py | generate_hdl_scr.py |
  |------|---------------------|---------------------|
  | 输出格式 | CSA 宏（FILE_TYPE=MACRO_DRAWING） | SCR 脚本（DEHDL 控制台命令） |
  | 放置方式 | 全自动（坐标由 map/calc 计算） | 交互式（用户手动点击） |
  | 属性设置 | FORCEPROP 指令 | :%Value: 格式 |
  | 坐标处理 | CIS→C纸映射+网格 | 无坐标（用户决定） |
  | symbol.css | 需要读取 | 不需要 |
  | 适用场景 | 批量自动转换 | 交互式逐个确认 |

📡 对外接口
  • 暴露的函数/类:
    - `generate_scr(components)` → `str`: 生成 SCR 脚本内容
    - `main()`: 主入口
  • 输入契约: 映射 CSV 必须包含 refdes, cis_value, hdl_part, hdl_primitive, hdl_package_type, hdl_sn_num, cis_fp_size, match_level
  • 输出契约: `place_parts.scr` 文件

🔗 内部依赖
  • 依赖哪些模块: csv, os, datetime（`__import__('datetime')` 用法不常见但有效）
  • 被谁调用: 独立运行。生成的 .scr 文件在 DEHDL 控制台通过 `script place_parts.scr` 执行

✨ 设计亮点

  1. **简洁明了**: 仅 140 行完成所有功能，代码量小意味着出 bug 概率低。

  2. **交互式确认模式**: 每个器件放置后提示用户手动点击，适合需要人工审核对齐的场景（如复杂 BGA 器件、模拟电路）。

  3. **进度注释清晰**: 每个器件都有 `[idx/total]` 标记和匹配等级标注，用户在执行 .scr 脚本时可以实时看到进度。

  4. **属性设置顺序合理**: PART_NAME → VALUE → JEDEC_TYPE → PACKAGE_TYPE → SN_NUM，从关键到辅助。

⚠️ 潜在问题

  1. **全局变量反模式**: `global total` 在 main() 中设置，generate_scr() 中使用——这是模块级共享状态的反模式。且 total 在 `if __name__ == "__main__"` 块中初始化为 0 但没有在 main() 执行前被正确初始化（generate_scr 中的 total 依赖于 main 先执行）。

  2. **硬编码路径**: `BASE_DIR = r"C:\Users\zhong\Desktop\CIS"` 硬编码，且与 generate_hdl_sch.py 中的路径不同（一个用 "test" 一个用 "CIS"）。

  3. **无未匹配器件处理**: 与 generate_hdl_sch.py 一样，match_level="none" 的器件也会生成 add 命令，可能导致 DEHDL 错误。

  4. **无坐标信息**: 没有从映射表中读取 cis_x/cis_y 坐标。映射 CSV 中实际有这些列，但在 generate_scr.py 中被忽略了。这意味着即使是已知坐标的器件也必须手动放置。

  5. **JEDEC_TYPE 误用**: `f":%Value:JEDEC_TYPE={cis_fp_size}"` — 将 CIS 的 fp_size 写入 JEDEC_TYPE 属性，但这可能是语义错误。fp_size 是封装尺寸（如 0201），JEDEC_TYPE 通常存储 JEDEC 标准封装名称。

  6. **`: %Value:` 格式可能错误**: 代码中是 `:%Value:`，但注释中是 `: %Value:`（有空格）。DEHDL 控制台语法对空格极敏感，需确认正确格式。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/writer/sch_writer.py`
    <!-- 已修改：补充 v2.0 新 writer —— scr_writer.py（DEHDL .scr 交互式放置脚本生成） -->
  • 实现状态: 部分实现
  • 关键差异:
    - 参考库：交互式 SCR 脚本，依赖用户手动点击
    - 当前项目：CTW 声明式模板 + 自动布局
    - 当前项目未实现交互式放置场景（SCH_WRITER 尚未包含 SCR 输出模式）
    - SCR 模式对于需要人工审核的复杂电路仍然有价值，当前项目可能需要补充此模式

---

━━━ 文件 #5: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\export_page13.py ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\export_page13.py
  • 语言/格式: Python 3 + pywin32 (Windows COM)
  • 行数估算: 462 行
  • 大小: 15,664 B

🎯 职责定位
  • 功能域: 数据导出（OrCAD Capture COM 自动化）
  • 解决什么问题: 通过 Windows COM 接口自动化操作 OrCAD Capture，打开工程文件 → 定位指定页面 → 提取所有器件的 CIS 属性 → 输出 CSV/TXT 器件清单和异常报告。这是整个 CIStoHDL 管线的数据入口。

🧠 核心算法

  **COM 自动化管线（6步）：**

  1. **COM 初始化 (`CoInitialize` + `DispatchEx`)**: 
     - 多 ProgID 候选（OrCAD.CaptureApp → Capture.Application）
     - 使用 `DispatchEx`（而非 `Dispatch`），创建独立 COM 进程

  2. **工程打开 (OpenProject/Open)**: 
     - 双方法回退：先尝试 `OpenProject`，失败则 `Open`

  3. **Design 对象获取 (6 种方法链式回退)**: 
     - `app.Session.ActiveDesign` → `app.Session.Designs.Item(1)` → `app.ActiveDesign` → `app.ActiveDocument` → `app.Design` → `app.Designs.Item(1)`
     - 这种"贪心回退"策略是 COM 自动化的经典模式——不同版本的 OrCAD Capture 有不同的对象层级结构

  4. **目标页面定位 (`find_target_page()`)**: 
     - 双层匹配：优先按 PageNumber，备选按 PageName
     - 遍历 design.Schematics → schematic.Pages → 比较 page.PageNumber/page.Name

  5. **器件属性提取 (三层策略)**:
     - **第一层: 页面对象枚举** — 尝试多种集合名（Objects/PageObjects/Instances/Items）
     - **第二层: 器件识别 (`is_component_object()`)** — 三种方法：ObjectType==1 / 有 Instance 子对象 / 有非空 Reference
     - **第三层: 属性读取 (`safe_get_prop()`)** — 先直接属性访问，失败则遍历 Properties 集合（CIS 扩展属性的常用访问方式）

  6. **异常检测**: 检查每个器件是否有 Footprint/SNUM/Value（或 TYPE_NAME），缺失则记入异常清单

  **关键数据结构：**
  - `components`: `list[dict]` — 每项 8 字段（RefDes/Value/Footprint/SNUM/PACKAGE_TYPE/Manufacturer/TYPE_NAME/DESCRIPTION）
  - `anomalies`: `list[(refdes, reason)]` — 异常器件列表

📡 对外接口
  • 暴露的函数/类:
    - `probe_com_object(obj, name, depth, max_depth)`: COM 对象探查（调试用）
    - `create_capture_app()` → `(app, progid)`: 创建 Capture 实例
    - `safe_get_prop(obj, prop_name, fallback="")` → `str`: 安全属性读取
    - `get_all_properties(instance)` → `dict`: 提取全部 8 个 CIS 字段
    - `is_component_object(obj)` → `(bool, instance_or_none)`: 器件判断
    - `get_available_pages(design)` → `list[(sname, pnum, pname)]`: 页面列表
    - `find_target_page(design, page_num, page_name)` → `(schematic, page)`: 页面定位
    - `enumerate_page_objects(page)` → `list`: 对象枚举
    - `main()`: 主流程 6 步管线
  • 输入契约: 需要 OrCAD Capture 已安装，工程文件 .opj 存在，目标页面存在
  • 输出契约: Page13_DeviceList.csv, Page13_DeviceList.txt, Page13_AnomalyList.txt

🔗 内部依赖
  • 依赖哪些模块: win32com.client, pythoncom（pywin32 包）, os, csv, sys, datetime
  • 被谁调用: 独立运行（必须在 Windows 原生 Python 中执行，WSL 不可用）。输出被 match_cis_to_hdl.py 消费
  • 外部依赖: OrCAD Capture 必须已安装且支持 COM Automation

✨ 设计亮点

  1. **多层回退策略**: 无论是 ProgID（2种）、工程打开（2种）、Design 获取（6种）还是对象枚举（4种集合名），都采用了链式回退。这种"兼容性优先于优雅"的设计在 COM 自动化中极为重要。

  2. **丰富调试输出**: 每个关键步骤都有 `[1/6]` 进度标记和 `[OK]/[FAIL]/[WARN]` 状态。COM 探测函数 (`probe_com_object`) 可以打印完整的 COM 对象成员树，极大降低了调试难度。

  3. **资源清理保证**: `finally` 块中总是调用 `app.Quit()` 和 `pythoncom.CoUninitialize()`，防止 COM 进程泄漏。

  4. **异常器件自动检测**: 不只导出数据，还自动检测缺少 Footprint/SNUM/Value 的器件并生成异常清单。这是"导出+质检"一体化的设计。

  5. **双格式输出**: CSV（机器可读）+ TXT（人类可读），与 match_cis_to_hdl.py 的输出风格完全一致。

⚠️ 潜在问题

  1. **pywin32 依赖**: 需要 `pip install pywin32`，在 OrCAD 环境中可能无法直接安装（如果 Python 是 OrCAD 自带的）。

  2. **COM 单线程公寓限制**: `pythoncom.CoInitialize()` 使用默认的 STA 模式。如果 OrCAD Capture 需要 MTA，可能导致问题。脚本中没有显式指定线程模型。

  3. **属性读取顺序依赖**: `safe_get_prop()` 先尝试直接属性访问，再遍历 Properties 集合。如果直接属性返回了错误值（如空字符串），而 Properties 集合中有正确值，就会丢失数据。

  4. **无器件坐标提取**: 没有提取器件的 X/Y 坐标（与 match_cis_to_hdl.py 中期望的 cis_x/cis_y 列不对应）。Page_DeviceList.csv 输出只有 8 列，缺少 RefDes-X 和 RefDes-Y。这会导致后续的坐标映射功能失效。

  5. **页面名称硬编码**: `TARGET_PAGE_NAME = "13-DDR3"` 硬编码。如果页面命名约定变化（如 "13-DDR4" 或 "14-DDR3"），脚本就无法定位。

  6. **ObjectType==1 判断不可靠**: `if ot == 1` 依赖于 OrCAD Capture 的内部约定，但 ObjectType 的值在不同版本的 Capture 中可能不同。

  7. **异常报告只检测缺失**: 不会检测格式错误（如 SNUM 格式不正确、Value 包含非法字符等）。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/parser/dsn/dsn_parser.py` + `cis2hdl/core/parser/dsn/ole_reader.py` + `cis2hdl/core/parser/dsn/page_parser.py`
  • 实现状态: 已实现但方式完全不同
  • 关键差异:
    - 参考库：通过 COM 接口使用 OrCAD 进程读取数据（依赖 OrCAD 运行时）
    - 当前项目：直接解析 DSN 二进制文件（OLE 复合文档 → 页面流），不依赖 OrCAD
    - 这是当前项目相对于参考库的**最大架构优势**：无需安装 OrCAD Capture，可在任何平台运行
    - 但当前项目也因此失去了 OrCAD COM 提供的语义层便利（如自动分辨器件/导线/网络标签）

---

━━━ 文件 #6: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\export_page13.tcl ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\export_page13.tcl
  • 语言/格式: TCL (Cadence DboTclHelper API)
  • 行数估算: 363 行
  • 大小: 12,913 B

🎯 职责定位
  • 功能域: 数据导出（TCL 自动化，特定页面 13-DDR3）
  • 解决什么问题: 通过 OrCAD Capture 内置 TCL 解释器和 DboTclHelper API，以无外部依赖的方式导出特定页面的器件属性。这是 COM 方式的替代方案——不依赖 Python/pywin32，直接在 Capture 内部运行。

🧠 核心算法

  **TCL 导出管线：**

  1. **C 字符串管理**: TCL 使用 DboTclHelper 的 C 字符串 API：
     - `DboTclHelper_sMakeCString` / `sGetConstCharPtr` / `sDeleteCString`
     - 每次属性读取都要 create→read→delete 三段式操作
     - 这是与 Python COM 方式最大的实现差异——TCL 必须手动管理 C 内存

  2. **Session 与 Design**: 
     - `DboTclHelper_sCreateSession` → `GetActivePMDesign`（GUI 模式）/ `GetDesignAndSchematics`（批处理模式）
     - 对比 Python COM 的 6 种 Design 获取方法，TCL 只有 2 种但更可靠

  3. **页面遍历**: 使用迭代器模式 — `NewViewsIter` → `NextView` → `DboViewToDboSchematic` → `NewPagesIter` → `NextPage`

  4. **器件属性提取（双策略）**:
     - RefDes: `GetReference`（直接）→ `GetReferenceDesignator`（通过 PlacedInst）
     - Value: `GetPartValue` → `GetEffectivePropStringValue "Value"`
     - Footprint: `GetPCBFootprint` → `GetEffectivePropStringValue "PCB Footprint"` → `GetEffectivePropStringValue "Footprint"`
     - CIS 扩展属性: `GetEffectivePropStringValue` → `PropertyValue`（双回退）

  5. **CSV 转义**: 手动实现引号和逗号转义——`[string map {\" \"\"} $field]`

  **关键 API 调用链：**
  ```
  DboTclHelper_sCreateSession
    → GetDesignAndSchematics(project_path)
    → NewViewsIter → NextView → DboViewToDboSchematic
      → NewPagesIter → NextPage → GetName
    → NewPartInstsIter → NextPartInst
      → GetReference / GetReferenceDesignator
      → GetPartValue / GetEffectivePropStringValue
      → GetPCBFootprint
  ```

📡 对外接口
  • 暴露的函数/类:
    - `make_cstr([str])` → C 字符串: 创建 C 字符串
    - `get_cstr(cstr)` → TCL 字符串: 读取 C 字符串
    - `cleanup_cstr(cstr)`: 释放 C 字符串内存
    - `get_eff_prop(handle, prop_name)` → str: 读取有效属性值
    - `get_prop_value(handle, prop_name)` → str: 通过 PropertyValue 读取
    - `get_str_prop(handle, method)` → str: 通过 getter 方法读取
    - `main()`: 主流程
  • 输入契约: 需要 OrCAD Capture 运行环境，.opj 工程文件存在
  • 输出契约: Page13_DeviceList.csv, Page13_DeviceList.txt, Page13_AnomalyList.txt（8 列，无坐标）

🔗 内部依赖
  • 依赖哪些模块: DboTclHelper, DboState, DboPartInstToDboPlacedInst, 等 Cadence TCL API
  • 被谁调用: Capture.exe -tcl export_page13.tcl 或 Capture GUI Tools→Tcl/Tk Scripts

✨ 设计亮点

  1. **零外部依赖**: 纯 Cadence TCL API，不需要 Python/pywin32，与 OrCAD 环境天然集成。

  2. **双运行模式**: 自动检测 GUI/批处理模式 — `GetActivePMDesign` 成功即 GUI 模式，失败则批处理模式。这比 Python COM 方式更优雅。

  3. **完整页面列表**: 在找不到目标页面时，自动打印所有可用页面。这是良好的调试体验设计。

  4. **迭代器模式**: 使用 DboPagePartInstsIter 迭代器而非一次性加载所有对象，内存友好。

⚠️ 潜在问题

  1. **C 字符串内存泄漏风险**: 如果脚本在某个 `make_cstr` 之后异常退出，对应的 C 字符串不会释放。虽然有 try-catch，但 TCL 的错误处理不如 Python 的 try-finally 可靠。

  2. **无坐标提取**: 与 export_page13.py 一样，不提取器件 X/Y 坐标。这使得该脚本只能用于匹配流程，不能用于布局转换。

  3. **页面名称硬编码**: `target_name = "13-DDR3"`，不可参数化。

  4. **CSV 转义简单**: 只处理逗号和引号，不处理换行符。如果属性值包含换行（如在 DESCRIPTION 字段中），CSV 格式会损坏。

  5. **`get_str_prop` 未使用**: 虽然定义了，但主流程中没有调用。可能是预留的扩展接口。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/parser/dsn/dsn_parser.py` + `cis2hdl/core/parser/dsn/page_parser.py`
  • 实现状态: 已实现但方式完全不同
  • 关键差异: 与文件 #5 相同——TCL 方式和 COM 方式都依赖 OrCAD 运行时，当前项目的二进制 DSN 解析器完全独立于 OrCAD。

---

━━━ 文件 #7: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\export_page.tcl ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\export_page.tcl
  • 语言/格式: TCL (Cadence DboTclHelper API)
  • 行数估算: 377 行
  • 大小: 13,481 B

🎯 职责定位
  • 功能域: 数据导出（TCL 自动化，通用参数化版本）
  • 解决什么问题: 与 export_page13.tcl 的功能相同，但增加了两个关键改进：(1) 提取器件 X/Y 坐标（RefDes-X, RefDes-Y），(2) GUI 模式下安全清理逻辑。这是 TCL 导出脚本的"最终改进版"。

🧠 核心算法

  与 export_page13.tcl **完全相同**的核心流程。以下仅列出差异点：

  **与 export_page13.tcl 的关键差异：**

  | 维度 | export_page13.tcl | export_page.tcl |
  |------|-------------------|-----------------|
  | 目标页面 | 13-DDR3 | 21-4GE |
  | CSV 列数 | 8 列（无坐标） | 10 列（含 RefDes-X, RefDes-Y） |
  | 坐标提取 | ❌ 无 | ✅ `GetLocation` → `sGetCPointX/sGetCPointY` |
  | GUI 模式标志 | ❌ 无 | ✅ `gui_mode` 变量追踪 |
  | GUI 清理 | 总是清理 Session | 跳过 Session 清理（防闪退） |
  | 输出文件名 | Page13_DeviceList.* | Page_DeviceList.* |
  | 输出目录 | Desktop/CIS | Desktop/test/OUT |

  **坐标提取实现（新增逻辑）：**
  ```tcl
  if {[catch {set lPoint [$lPartInst GetLocation $lStatus]}] == 0} {
      if {$lPoint != "NULL" && $lPoint != ""} {
          set x_pos [DboTclHelper_sGetCPointX $lPoint]
          set y_pos [DboTclHelper_sGetCPointY $lPoint]
      }
  }
  ```
  这是 TCL 版本中独有的能力——Python COM 版本的 export_page13.py **也没有**提取坐标。

📡 对外接口
  • 暴露的函数/类: 与 export_page13.tcl 完全相同
  • 输入契约: 与 export_page13.tcl 相同，此外需要器件有 Location 属性
  • 输出契约: Page_DeviceList.csv (10列), Page_DeviceList.txt (10列), Page_AnomalyList.txt

🔗 内部依赖
  • 依赖哪些模块: 与 export_page13.tcl 相同 + DboTclHelper_sGetCPointX/sGetCPointY
  • 被谁调用: 与 export_page13.tcl 相同

✨ 设计亮点

  1. **坐标提取是关键改进**: 有了 X/Y 坐标，match_cis_to_hdl.py 和 generate_hdl_sch.py 才能进行 CIS→DEHDL 坐标映射。这是整个自动化布局管线的关键数据。

  2. **GUI 模式安全退出**: `if {!$gui_mode} { ... cleanup ... }` — 在 GUI 模式下不清理 Session，防止 Capture 窗口意外关闭。这是从实践中总结的经验。

  3. **通用化命名**: 输出文件名为 `Page_DeviceList` 而非 `Page13_DeviceList`，使其可复用于任意页面。

  4. **输出目录分离**: 使用 `OUT` 子目录，与源文件隔离。

⚠️ 潜在问题

  1. **代码重复严重**: export_page.tcl 和 export_page13.tcl 有约 80% 的代码相同（helper 函数完全一样）。应该合并为一个参数化脚本。

  2. **坐标可能为空**: `GetLocation` 可能返回空（某些器件类型没有位置信息），但 CSV 中会用空字符串填充，可能在下游匹配时产生问题（如 match_cis_to_hdl.py 中 `if c.get("cis_x") and c.get("cis_y")` 判断）。

  3. **硬编码目标页面名**: 虽然命名通用化了，但 `target_name = "21-4GE"` 仍然是硬编码的。

  4. **输出文件名与 Python 版本的冲突**: Python 版本输出 `Page13_DeviceList.csv`，TCL 版本输出 `Page_DeviceList.csv`。如果两个脚本都在同一目录运行，文件名冲突或混淆。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/parser/dsn/dsn_parser.py` + `cis2hdl/core/parser/dsn/page_parser.py`
  • 实现状态: 已实现
  • 关键差异: 
    - TCL 脚本依赖 OrCAD 运行时；当前项目直接解析 DSN 二进制
    - TCL 通过 `GetLocation` 获取坐标；当前项目通过 DSN 二进制流解析坐标
    - 当前项目提取的坐标精度可能更高（从原始二进制解析，不受 TCL API 浮点精度限制）

---

━━━ 文件 #8: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\page1.scr ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\page1.scr
  • 语言/格式: DEHDL 宏脚本（MACRO_DRAWING 格式）
  • 行数估算: 1,448 行（27 个器件 × ~50 行/器件 + 头部 30 行）
  • 大小: 33,588 B (约34KB)

🎯 职责定位
  • 功能域: 代码生成（DEHDL 原理图页面宏）
  • 解决什么问题: 这是一个由 generate_hdl_sch.py 生成的**完整 DEHDL 原理图页面宏**。它包含了对 page1（DDR3 页面）上 27 个器件的完整 FORCEADD/FORCEPROP 指令序列。这是 CSA 代码生成器的**黄金标准输出**——理解这个文件就理解了 DEHDL 页面自动化的一切。

🧠 核心算法

  **文件结构解析（三段式）：**

  **第一段：宏头部 (lines 1-31)**
  ```
  FILE_TYPE = MACRO_DRAWING;        ← 声明为宏绘制文件
  SET COLOR_WIRE YELLOW;            ← 颜色配置
  SET COLOR_PROP ORANGE;
  SET COLOR_DOT WHITE;
  SET COLOR_ARC YELLOW;
  SET COLOR_BODY GREEN;
  SET COLOR_NOTE PURPLE;
  SET PROP_DISPLAY VALUE;           ← 默认显示 Value 属性
  SET PAGE_NUMBER P1;               ← 页面编号
  FORCEADD C SIZE PAGE..1           ← 添加 C 纸边框符号
  (2900 200);
  FORCEPROP 1 LAST COMMENT_BODY TRUE
  ...
  FORCEPROP 0 LAST EDIT PAGE NAME DDR3  ← 页面名称
  ```

  **第二段：器件实例循环 (lines 32-1447) — 27 个器件 × 5 行 × 5 列网格**

  每个器件的**标准指令模板**（共 19 条指令）：
  ```
  FORCEADD {PRIMITIVE_NAME}..1      ← 线 1: 添加器件实例（如 CAPACITOR_0201..1）
  (X Y);                             ← 线 2: 放置坐标

  // ---- 不可见属性 ----
  FORCEPROP 1 LAST PATH I{N}        ← 实例标识（I1, I1, I1... 注意全为 I1!）
  J 0                                ← Justification 0
  (X Y);
  DISPLAY 1.021277 (X Y);          ← 先以 1.02x 显示
  DISPLAY INVISIBLE (X Y);         ← 再隐藏（两步操作，可能是 DEHDL 内部协议）

  FORCEPROP 1 LAST PART_NAME {PN}   ← 型号名称
  ... (同上 J0 + DISPLAY 1.02x + INVISIBLE)

  FORCEPROP 1 LAST JEDEC_TYPE {SZ}  ← JEDEC 封装类型
  ...
  FORCEPROP 1 LAST PACKAGE_TYPE {PT} ← 封装类型
  ...
  FORCEPROP 1 LAST SN_NUM {SN}      ← 物料号
  ...
  FORCEPROP 1 LAST DESCRIPTION {D}  ← 描述
  ...

  // ---- 可见属性 ----
  FORCEPROP 1 LAST VALUE {V}        ← 值（可见）
  R 1                                ← Rotation 1
  J 1                                ← Justification 1（右上对齐）
  (X+offset Y+100);                 ← Y+100（向上偏移 100 单位）
  DISPLAY 0.851064 (X+offset Y+100); ← 以 0.85x 缩放显示

  FORCEPROP 1 LAST $LOCATION {Ref}  ← 位号（可见，绿色）
  R 1
  J 1
  (X+offset Y-100);                 ← Y-100（向下偏移 100 单位）
  DISPLAY 0.851064 (X+offset Y-100);
  PAINT GREEN (X+offset Y-100);     ← 绿色涂色

  // ---- 器件边框 ----
  FORCEPROP 1 LAST CDS_LMAN_SYM_OUTLINE {outline}
  J 0
  (X Y);
  DISPLAY 0.468085 (X Y);
  PAINT GREEN (X Y);
  DISPLAY INVISIBLE (X Y);

  // ---- 库引用 ----
  FORCEPROP 2 LAST CDS_LIB hdl_lib   ← 第二个属性实例
  J 0
  (X Y);
  DISPLAY INVISIBLE (X Y);
  ```

  **网格布局分析：**
  | 行(Y) | 列1(X=-11000) | 列2(X=-9000) | 列3(X=-7000) | 列4(X=-5000) | 列5(X=-3000) |
  |-------|---------------|-------------|-------------|-------------|-------------|
  | 7000  | C460 (0201)   | C54 (0201)  | C57 (0201)  | C52 (0402)  | C458 (0201) |
  | 5500  | C466 (0201)   | R281 (0201) | R270 (0201) | R278 (0201) | U5 (88E6320)|
  | 4000  | C55 (0201)    | R41 (0402)  | C455 (0402) | C456 (0201) | R282 (0201) |
  | 2500  | C465 (0201)   | C457 (0201) | C454 (0201) | R269 (0201) | C53 (0402)  |
  | 1000  | C469 (0201)   | C462 (0201) | C56 (0201)  | C468 (0201) | C467 (0201) |
  | -500  | R40 (0201)    | C459 (0201) | —           | —           | —           |

  **关键数值常量：**
  - DISPLAY 缩放因子: 0.851064（VALUE/$LOCATION）、0.468085（边框/库引用）、1.021277（隐藏前过渡）
  - 网格步长: X=2000, Y=1500（同 generate_hdl_sch.py 中 COMPONENT_SPACING_X/Y）
  - VALUE 偏移: (-5, +100) 或 (-50, +5)
  - $LOCATION 偏移: (-5, -100) 或 (-220, +5)
  - 电容 CDS_LMAN_SYM_OUTLINE: -50,0,50,-25
  - 电阻 CDS_LMAN_SYM_OUTLINE: -50,25,50,-25
  - 88E6320 CDS_LMAN_SYM_OUTLINE: -600,2250,600,-2250

  **第三段：结束 (line 1448)**
  ```
  QUIT
  ```

📡 对外接口
  • 暴露的函数/类: N/A（数据文件）
  • 输入契约: 由 generate_hdl_sch.py 生成，在 DEHDL 中通过打开项目时自动编译
  • 输出契约: 编译为 page1.csb（二进制页面文件）

🔗 内部依赖
  • 依赖哪些模块: 依赖 hdl_lib/ 下的所有器件（CAPACITOR_0201, RESISTOR_0201, CAPACITOR_0402, 88E6320 等）
  • 被谁调用: DEHDL (nconcepthdl) 在打开设计时自动读取并编译

✨ 设计亮点

  1. **DISPLAY INVISIBLE 两步操作**: 每个不可见属性先以放大比例显示（DISPLAY 1.021277），再设为 INVISIBLE。这可能是 DEHDL 内部协议：属性必须先在某个位置"存在"才能被隐藏。generate_hdl_sch.py 中跳过了这个中间 DISPLAY 步骤，直接 INVISIBLE — 可能是简化假设。

  2. **器件放置的规则网格**: 5 列 × 6 行网格，间距精确为 X=2000, Y=1500。这种规律性使 DEHDL 页面整洁且可预测。

  3. **CDS_LMAN_SYM_OUTLINE 区分器件类型**: 电容 (-50,0,50,-25)、电阻 (-50,25,50,-25)、BGA 芯片 (-600,2250,600,-2250)。outline 值似乎反映了器件的物理尺寸（相对放置点的边界框）。

  4. **$LOCATION 可见且着色**: 位号设为绿色可见，这是 DEHDL 原理图的标准约定——便于人工阅读和调试。

  5. **PATH 固定为 I1**: 所有器件的 PATH 都设为 I1，这表示它们都是"第一个实例"。在 CSA 宏的上下文中，每个 FORCEADD 创建独立的实例，所以 PATH=I1 是合理的。

⚠️ 潜在问题

  1. **与 generate_hdl_sch.py 输出不完全一致**: page1.scr 的 DISPLAY 顺序是 DISPLAY(1.02x) → DISPLAY INVISIBLE，而 generate_hdl_sch.py 的 generate_csa() 直接输出 DISPLAY INVISIBLE。需要确认 DEHDL 是否接受简化格式。

  2. **所有 PATH 都是 I1**: 当多个器件在同一页面时，PATH 应该递增（I1, I2, I3...）还是保持 I1？如果 PATH 必须唯一，这可能是 bug。generate_hdl_sch.py 中 PATH 是 `I{idx+1}`，正确处理了递增。

  3. **缺少 SN_NUM 为空时的处理**: page1.scr 中 R278 和 R41（size 匹配等级）没有 SN_NUM 行，generate_hdl_sch.py 中的处理逻辑是 `if hdl_sn: ...`，一致。

  4. **88E6320（U5）的 VALUE 和 $LOCATION 位置异常**: VALUE 在 (-3600, 3200)，$LOCATION 在 (-3600, 7770)，偏移量远大于其他器件（因为 BGA 的 CDS_LMAN_SYM_OUTLINE 很大）。

  5. **硬编码的页面名称 "DDR3"**: 第 29 行 `FORCEPROP 0 LAST EDIT PAGE NAME DDR3`。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/writer/sch_writer.py` (CTW 输出)
    <!-- 已修改：补充 v2.0 新 writer —— csa_writer.py（CSA 页面宏）/ cpc_writer.py（page1.cpc 页面配置）/ output_manager.py（page.map、master.tag、module_order.dat） -->
  • 实现状态: 已实现但差异大
  • 关键差异:
    - 参考库：直接生成 DEHDL 宏脚本（FORCEADD/FORCEPROP）
    - 当前项目：生成 CTW 模板 DSL，由 DEHDL 编译为等效的二进制页面
    - CTW 模板是声明式的，DEHDL 负责将其转化为 FORCEADD/FORCEPROP 指令
    - 当前项目需要确认 CTW 编译器是否能正确处理 DISPLAY 缩放因子、PAINT 颜色等细节

---

━━━ 文件 #9: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\place_parts.scr ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\place_parts.scr
  • 语言/格式: DEHDL 控制台 SCR 脚本（由 generate_hdl_scr.py 生成）
  • 行数估算: 384 行（27 个器件 × ~13 行/器件 + 尾部 3 行）
  • 大小: 8,889 B

🎯 职责定位
  • 功能域: 代码生成（DEHDL 交互式器件放置脚本）
  • 解决什么问题: 与 page1.scr 的"全自动宏模式"不同，这个 SCR 脚本需要用户在 DEHDL 图形界面中**手动点击**每个器件的放置位置。它提供属性设置（:`%Value:` 格式），但不包含坐标信息。

🧠 核心算法

  **SCR 脚本结构（已完全被 generate_hdl_scr.py 文档覆盖）：**
  
  每个器件块格式：
  ```
  {                                 ← 注释开始
    [N/27] RefDes  Value
    HDL器件: hdl_part  Primitive: hdl_primitive
    料号: hdl_sn_num               ← 仅 exact 匹配有此项
    匹配等级: match_level
  }
  add <hdl_lib>{cell_name}         ← 从库添加器件
  :%Value:PART_NAME=...            ← 属性设置（DEHDL 控制台命令）
  :%Value:VALUE=...
  :%Value:JEDEC_TYPE=...
  :%Value:PACKAGE_TYPE=...
  :%Value:SN_NUM=...               ← 仅 exact/size 匹配有此项
  { >>> 请点击放置 RefDes (Value) <<< }
  ```

  **匹配等级与 SN_NUM 的关系：**
  - `exact` 匹配：显示料号（共 24 个）
  - `size` 匹配（R278, R41）：显示"匹配等级: size"，无 SN_NUM 行
  - `prefix` 匹配（U5）：显示"匹配等级: prefix"，无 SN_NUM 行和无"料号"行

  **与 generate_hdl_scr.py 的输出对比：**
  - ✅ 完全一致：格式、顺序、属性映射
  - 验证了 generate_hdl_scr.py 的正确性

📡 对外接口
  • 暴露的函数/类: N/A（数据文件）
  • 输入契约: 在 DEHDL 控制台通过 `script place_parts.scr` 执行
  • 输出契约: 用户在 DEHDL 画布上手动点击放置 27 个器件

🔗 内部依赖
  • 依赖哪些模块: 依赖 hdl_lib/ 库在 DEHDL 中已配置；依赖 DEHDL 控制台环境
  • 被谁调用: DEHDL 控制台的 `script` 命令

✨ 设计亮点

  1. **交互式确认**: 每个器件放置后都有 `{ >>> 请点击放置 ... <<< }` 提示，用户可以看到具体要放哪个器件及其属性。

  2. **匹配等级透明**: 每个器件的注释中都标注了匹配等级，用户可以在放置时做出判断（如 prefix 匹配的 U5 可能需要人工检查）。

  3. **:`%Value:` 命令格式**: 这是 DEHDL 控制台的原生命令格式，比 CSA 宏的 FORCEPROP 更简洁。

⚠️ 潜在问题

  1. **`: %Value:` 空格问题**: 文件中使用 `:%Value:PART_NAME=...`（注意冒号后无空格），与 generate_hdl_scr.py 源码中的 `f":%Value:PART_NAME={hdl_primitive}"` 一致。需确认 DEHDL 接受此格式。

  2. **无错误处理**: 如果某个 `add` 命令失败（如库中无此器件），脚本会继续执行下一个，不会回滚。这可能使得部分页面处于不一致状态。

  3. **SN_NUM 字段不一致**: 在注释中用"料号"，在 `:%Value:` 命令中用 SN_NUM。两者语义相同但在文件中的命名不统一。

  4. **手动放置效率**: 对于 27 个器件的页面，手动点击 27 次。对于更大的页面（100+ 器件），这种方式不可行。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/writer/sch_writer.py`
    <!-- 已修改：补充 v2.0 新 writer —— scr_writer.py（DEHDL .scr 交互式放置脚本生成） -->
  • 实现状态: 部分实现
  • 关键差异:
    - 与 generate_hdl_scr.py 相同——当前项目的 CTW 模板模式覆盖了全自动放置，但缺少交互式 SCR 模式
    - SCR 模式对于需要人工审核的复杂电路（如模拟电路、BGA 布线）仍有价值

---

━━━ 文件 #10: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\place_parts_simple.scr ━━━

📋 文件身份
  • 路径: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\place_parts_simple.scr
  • 语言/格式: DEHDL 控制台 SCR 脚本（精简版）
  • 行数估算: 142 行（27 个器件 × ~5 行）
  • 大小: 1,754 B

🎯 职责定位
  • 功能域: 代码生成（极简交互式放置脚本）
  • 解决什么问题: place_parts.scr 的"精简版"——每个器件只有 `add` 命令，没有属性设置。适用于只需要快速放置器件符号、不需要设置属性的场景。或者是在属性已经通过 CSA 宏设置后，只需要调整位置时使用。

🧠 核心算法

  **极度精简的格式：**
  ```
  {
    N/27 RefDes - Value (cell_name)   ← 单行精简注释
  }
  add <hdl_lib>{cell_name}            ← 仅 add 命令，无属性
  ;                                    ← 分号分隔（原来的完整版用空行）
  ```

  **精简了什么：**
  | 维度 | place_parts.scr (完整版) | place_parts_simple.scr (精简版) |
  |------|--------------------------|-------------------------------|
  | 属性设置 | ✅ :`%Value:PART_NAME=...` 等 5-6 条 | ❌ 无 |
  | 料号信息 | ✅ 显示 | ❌ 不显示 |
  | 匹配等级 | ✅ 显示 | ❌ 不显示 |
  | 器件注释 | 5 行 | 1 行 |
  | 每器件行数 | ~13 行 | ~5 行 |

  **文件名推测的用法：**
  - `place_parts.scr` — 初始转换：添加器件 + 设置属性，手动放置
  - `place_parts_simple.scr` — 后续调整：只添加器件符号（属性可能由 CSA 宏或其他方式设置）

📡 对外接口
  • 暴露的函数/类: N/A
  • 输入契约: 在 DEHDL 控制台通过 `script place_parts_simple.scr` 执行
  • 输出契约: 27 个裸器件符号放置在画布上

🔗 内部依赖
  • 依赖哪些模块: 与 place_parts.scr 相同

✨ 设计亮点

  1. **极致精简**: 每个器件仅 5 行，文件大小只有完整版的 20%。加载和执行速度更快。

  2. **分号终止**: 每个 add 命令后紧跟 `;`，作为 DEHDL 控制台的命令分隔符。这是正确的 SCR 语法实践——完整版用空行分隔可能不够可靠。

  3. **适用场景清晰**: 适用于"属性已经正确，只需重新放置器件"的场景。这在迭代式设计调整中很常见。

⚠️ 潜在问题

  1. **无属性设置**: 放置后的器件没有 VALUE、PART_NAME、SN_NUM 等属性，需要后续手动设置或通过 CSA 宏批量设置。

  2. **缺少 `:{...}:` 注释块**: 精简版中的 `{}` 块是注释但格式不规范——缺少闭合的花括号层级。

  3. **无法追溯来源**: 没有匹配等级信息，用户不知道哪些器件是精确匹配、哪些是前缀匹配。

🔀 与当前项目的映射
  • 对应文件: `cis2hdl/core/writer/sch_writer.py`
    <!-- 已修改：补充 v2.0 新 writer —— scr_writer.py（DEHDL .scr 交互式放置脚本生成） -->
  • 实现状态: 部分实现
  • 关键差异: 精简版 SCR 是当前项目未覆盖的模式。如果要支持"仅重新放置"场景，需要在 sch_writer 中添加一个 `--placement-only` 或类似模式。

---

━━━ 文件 #11: D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\diagnose_com.vbs ━━━

📋 文件身份
  • 路径: diagnose_com.vbs
  • 语言/格式: VBScript (Windows Script Host)
  • 行数估算: 134 行 | 大小: 3,904 B

🎯 职责定位
  • 功能域: 诊断（COM ProgID 注册表扫描）
  • 解决什么问题: 当 export_page13.py 无法创建 OrCAD Capture COM 实例时，扫描 Windows 注册表找 OrCAD 相关 ProgID 并逐个测试创建。8 个候选 ProgID 比 Python 版的 2 个更全面。

🧠 核心算法
  • 三步管线：(1) 注册表搜索 OrCAD/Capture 关键词 (2) 逐个 CreateObject 测试 8 个 ProgID (3) CLSID 搜索
  • ⚠️ 注册表枚举方式 `RegRead(key & "Enum\N" & i)` 在标准 Windows API 中不存在，步骤 1 和 3 实际上不会产生输出

📡 对外接口
  • 通过 `cscript diagnose_com.vbs` 运行，输出到标准输出

🔀 与当前项目的映射
  • 对应: `cis2hdl/core/diagnostics/config_validator.py`（已实现，但功能不同——当前项目校验配置而非诊断 OrCAD COM）

---

━━━ 文件 #12: Page13_AnomalyList.txt ━━━

📋 文件身份
  • 语言/格式: 纯文本 | 行数: 33 | 大小: 1,058 B
  • 功能域: 诊断（异常报告）

🎯 职责定位
  • 列出 Page 13 上所有 27 个器件都缺少 SNUM（物料号）。100% 异常率。

🔀 与当前项目的映射
  • 对应: `cis2hdl/core/diagnostics/quality.py`（已实现，多维度评分更全面）

---

━━━ 文件 #13: Page13_DeviceList.txt ━━━

📋 文件身份
  • 语言/格式: 纯文本定宽表格 | 行数: 36 | 大小: 4,851 B
  • 功能域: 器件属性清单

🎯 职责定位
  • 提供 Page 13 上 27 个器件的 RefDes/Value/Footprint（SNUM/PACKAGE_TYPE/Manufacturer/TYPE_NAME/DESCRIPTION 全为空）。由 TCL 脚本通过 `GetPartValue`/`GetPCBFootprint` 等 API 提取。

🔀 与当前项目的映射
  • 对应: `cis2hdl/core/ir/design.py` (DesignIR)（已实现，结构化 IR 替代中间文件）

---

━━━ 文件 #14: out_hdl.cpm ━━━

📋 文件身份
  • 路径: out_hdl.cpm | 语言/格式: DEHDL CPM 项目配置文件 | 行数: 39 | 大小: 832 B

🎯 职责定位
  • 功能域: 代码生成（DEHDL 项目配置）
  • DEHDL 项目文件格式：START_GLOBAL/START_CONCEPTHDL/START_PKGRXL/START_DESIGNSYNC/START_CONSTRAINT_MGR 五个段
  • 关键配置：`design_name 'out_hdl'`, `library 'hdl_lib' 'out_hdl_lib'`, `cpm_version '16.6'`
  • 由 SPI 机器生成，不可手动修改

🔀 与当前项目的映射
  • 对应: `cis2hdl/core/writer/cpm_writer.py`（已实现，模板化生成，支持配置参数）

---

━━━ 文件 #15: cds.lib ━━━

📋 文件身份
  • 路径: cds.lib | 语言/格式: Cadence 库配置文件 | 行数: 3 | 大小: 98 B

🎯 职责定位
  • 功能域: 库配置
  • 三行内容：`DEFINE out_hdl_lib worklib` / `INCLUDE $CONCEPT_INST_DIR/share/cdssetup/cds.lib` / `DEFINE hdl_lib hdl_lib`
  • 极简但关键：告诉 DEHDL 去哪里找库文件

🔀 与当前项目的映射
  • 对应: `cis2hdl/core/writer/cdslib_writer.py`（已实现，DEFINE 语句生成）

---

━━━ 文件 #16: c2esch.edif ━━━

📋 文件身份
  • 路径: c2esch.edif | 语言/格式: EDIF 3.0.0 (Lisp-like S 表达式) | 行数: 1,010 | 大小: 31,430 B

🎯 职责定位
  • 功能域: 数据导出（EDIF 中间格式）
  • 由 `c2esch` 工具从 OrCAD Capture 导出的 EDIF 中间文件
  • 包含两个库：`hdl_lib`（页面边框模板 C SIZE PAGE）+ `out_hdl_lib`（目标设计 out_hdl 的 sch_1 页）
  • 只有结构框架（totalPages 1, page SH_1），无实际器件/网络内容
  • 页面边框定义证实：C 纸区域为 x∈[-10750,0], y∈[0,8275]（与 generate_hdl_sch.py 中的坐标一致！）

🔀 与当前项目的映射
  • 对应: `cis2hdl/core/parser/edif_parser.py`（已实现，当前项目支持 EDIF 输入解析）

---

━━━ 文件 #17: run_tcl_export.bat ━━━

📋 文件身份
  • 路径: run_tcl_export.bat | 语言/格式: Windows Batch | 行数: 60 | 大小: 1,487 B

🎯 职责定位
  • 功能域: 流程编排（批处理启动器）
  • 三种执行模式：
    1. Tcl 批处理模式：`Capture.exe -tcl export_page13.tcl`（后台执行）
    2. Tcl 手动模式：提示用户在 GUI 中手动执行 Tcl 脚本
    3. COM 诊断模式：`cscript diagnose_com.vbs`
  • 关键路径：`C:\Cadence\SPB_16.6\tools\capture\Capture.exe`

🔀 与当前项目的映射
  • 对应: `cis2hdl/core/engine/conversion_engine.py`（已实现，Python 引擎管道替代批处理编排）

---

━━━ 文件 #18: CIS_to_HDL_Mapping.csv ━━━

📋 文件身份
  • 路径: CIS_to_HDL_Mapping.csv | 语言/格式: CSV (UTF-8-BOM) | 行数: 28 (+header) | 大小: 3,035 B

🎯 职责定位
  • 功能域: 匹配结果（机器可读）
  • 10 列：refdes/cis_value/cis_footprint/cis_fp_size/hdl_part/hdl_primitive/hdl_package_type/hdl_sn_num/match_level/note
  • 这是整个管线的"数据合约"——上游(match)的输出 = 下游(generate)的输入
  • 统计：24 exact + 2 size + 1 prefix = 27 器件全匹配（0 none）
  • 关键观察：
    - `100nF*` 和 `1uF*`（带 `*` 后缀）被 normalize_value 正确处理
    - `HSC0201-HDTB` → fp_size=0201（extract_pkg_size 正确提取）
    - `BGA96-32-1609W` → fp_size=BGA96（BGA 优先匹配）
    - `SC0201A` → fp_size=0201（4 位数字匹配）
  • U5(88e6320) 只有 prefix 匹配——芯片级器件的匹配是已知难点

🔀 与当前项目的映射
  • 对应: `cis2hdl/core/ir/match.py` (MatchResult)（已实现，结构化 IR 替代 CSV）

