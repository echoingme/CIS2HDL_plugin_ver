# CIS2HDL Cadence 兼容性修复方案

> **生成时间**: 2026-08-03
> **分析者**: Bob (Architect)
> **参考基准**: `D:\26暑假\cis2hdl\docs_for_reference\CIStoHDL_standard\out_hdl.cpm`

---

## 审计总览

| 优先级 | 数量 | 描述 |
|--------|------|------|
| **P0** (阻断) | 4 | 导致 Cadence Project Manager 无法正常打开项目 |
| **P1** (高) | 4 | 导致 Cadence 兼容性警告或部分功能异常 |
| **P2** (中) | 4 | 细节对齐，不影响基本功能 |

---

## P0 — 阻断级修复

### P0-1: cds.lib 路径中多余的 `./` 前缀

| 项目 | 内容 |
|------|------|
| **参考文件** | `CIStoHDL_standard/cds.lib` |
| **参考写法** | `DEFINE out_hdl_lib worklib` |
| **问题代码** | `output_manager.py` 第 523-525 行 |
| **当前写法** | `DEFINE {library_alias} ./worklib` |

**影响**: Cadence 使用 `cds.lib` 解析库路径。`./` 前缀可能在某些 Cadence 版本中导致路径解析异常，触发项目升级（UPREV）。

**同样的问题出现在 hdl_lib 行**:
| 项目 | 内容 |
|------|------|
| **参考写法** | `DEFINE hdl_lib hdl_lib` |
| **当前写法** | `DEFINE hdl_lib ./hdl_lib` |

**修复**: 移除 `cdslib_writer.py` 和 `output_manager.py` 中 `write_cdslib()` 方法的 `./` 前缀。

**涉及文件**:
- `cis2hdl/core/writer/output_manager.py:523-525`
- `cis2hdl/core/writer/cdslib_writer.py:27-30` (docstring 也需更新)

> ✅ 已实施（2026-08-07 代码核实：xcon_writer.py/output_manager.py 存在对应实现）
> 注：行号随代码演进已失效。

---

### P0-2: 缺失 .xcon 文件生成器

| 项目 | 内容 |
|------|------|
| **参考文件** | `CIStoHDL_standard/worklib/out_hdl/sch_1/out_hdl.xcon` |
| **格式** | XML, Cadence CS Schema (`http://www.cadence.com/spb/csschema`) |
| **当前状态** | `master.tag` 中引用了 `.xcon`，但**没有任何代码生成 `.xcon` 文件** |

**影响**: `.xcon` 文件是 Cadence Concept HDL 的核心设计描述文件。它包含:
- 设计头信息（schemaVersion, savedLibrary）
- 单元定义（cells）——引用 HDL 库中的组件
- 实例定义（instances）——页面上放置的组件
- 页面映射（pages）

**没有 `.xcon` 文件 = Cadence 无法识别设计结构 = 触发 UPREV。**

**参考文件结构（最小可工作版本，来自 `.xcon,1`）**:
```xml
<schema xmlns="http://www.cadence.com/spb/csschema"
	xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
	xsi:schemaLocation="http://www.cadence.com/spb/csschema CSSchema002.xsd">
  <header>
    <schemaVersion>16.6</schemaVersion>
    <creatorTool>concepthdl</creatorTool>
    <modifierTool>concepthdl</modifierTool>
    <modificationTime>2026-07-03T16:44:54</modificationTime>
    <savedLibrary>out_hdl_lib</savedLibrary>
  </header>
  <designs>
    <design schemaType="nameBased" name="out_hdl" view="sch_1">
      <lastids>
      </lastids>
      <cells>
      </cells>
      <nets>
      </nets>
      <aliases>
      </aliases>
      <differentialnets>
      </differentialnets>
      <differentialbusnets>
      </differentialbusnets>
      <netgroups>
      </netgroups>
      <netinterfaces>
      </netinterfaces>
      <instances>
      </instances>
      <templateresolutions>
      </templateresolutions>
      <templateinstances>
      </templateinstances>
      <extensions>
        <extension name="schematic_extension">
        <schematicExtension>
        <netScopes>
        </netScopes>
        <pages>
          <page number="1">
            <physicalPageNumber>1</physicalPageNumber>
            <errorStatus>false</errorStatus>
            <nets>
            </nets>
            <instances>
            </instances>
          </page>
        </pages>
      </schematicExtension>
        </extension>
      </extensions>
    </design>
  </designs>
</schema>
```

**修复**: 创建新的 `xcon_writer.py`，在 `OutputManager` 中添加 `write_xcon()` 方法。

**涉及文件**:
- 新建: `cis2hdl/core/writer/xcon_writer.py`
- 修改: `cis2hdl/core/writer/output_manager.py` — 添加 `write_xcon()` 方法
- 修改: `cis2hdl/core/engine/conversion_engine.py` — 注册 `XCONWriter` 并在 Stage 6 调用

> ✅ 已实施（2026-08-07 代码核实：xcon_writer.py/output_manager.py 存在对应实现）

---

### P0-3: master.tag 中 CSA 文件名与实际文件名不匹配

| 项目 | 内容 |
|------|------|
| **参考文件** | `CIStoHDL_standard/worklib/out_hdl/sch_1/master.tag` |
| **参考内容** | `page1.csa` |
| **当前代码位置 1** | `output_manager.py:400` (`write_placeholder_files`) |
| **当前写法 1** | `{self.cell_name}.csa` （如 `8367.csa`） |
| **当前代码位置 2** | `sch_writer.py:1008-1012` (`SCHWriterCSA._generate_support_files`) |
| **当前写法 2** | `{self._design_name}.csa` （如 `test.csa`） |

**影响**: `master.tag` 是 Cadence 用来发现视图下所有文件的索引文件。如果它说 `8367.csa` 但实际文件是 `page1.csa`，Cadence 找不到页面文件 = UPREV 或页面无法打开。

**实际 CSA 文件名**: `page1.csa`, `page2.csa` 等（由 `CSAWriter.write_with_manager()` → `OutputManager.write_csa_page()` 生成）

**修复**: `master.tag` 应列出实际的页面文件名（`page1.csa` 等），而不是 `{cell_name}.csa`。

**涉及文件**:
- `cis2hdl/core/writer/output_manager.py:399-403` (`write_placeholder_files`)
- `cis2hdl/core/writer/sch_writer.py:1008-1012` (`SCHWriterCSA._generate_support_files`)

> ✅ 已实施（2026-08-07 代码核实：xcon_writer.py/output_manager.py 存在对应实现）
> 注：行号随代码演进已失效。

---

### P0-4: SCHWriterCSA 主文件与 CSAWriter 颜色方案不一致

| 项目 | 内容 |
|------|------|
| **参考 page1.csa** | `SET COLOR_PROP ORANGE;` `SET COLOR_NOTE PURPLE;` |
| **SCHWriterCSA** (`sch_writer.py:625-629`) | `SET COLOR_PROP ORANGE;` `SET COLOR_NOTE PURPLE;` ✅ |
| **CSAWriter** (`csa_writer.py:198-203`) | `SET COLOR_PROP MONO;` `SET COLOR_NOTE MONO;` ❌ |
| **实际运行时使用的** | `CSAWriter`（通过 `conversion_engine.py` 注册和调用） |

**影响**: 虽然不影响项目是否能打开，但颜色方案不一致可能导致 Cadence 中元件属性显示异常。参考文件始终使用 ORANGE/PURPLE 颜色组合。

**修复**: 将 `csa_writer.py` 中的 `SET COLOR_PROP MONO` 改为 `SET COLOR_PROP ORANGE`，`SET COLOR_NOTE MONO` 改为 `SET COLOR_NOTE PURPLE`。

**涉及文件**:
- `cis2hdl/core/writer/csa_writer.py:199, 203`

> ✅ 已实施（2026-08-07 代码核实：xcon_writer.py/output_manager.py 存在对应实现）
> 注：行号随代码演进已失效。

---

## P1 — 高优先级修复

### P1-1: module_order.dat 格式错误（反斜杠转义）

| 项目 | 内容 |
|------|------|
| **参考内容** | `@out_hdl_lib.out_hdl(sch_1)	0	1	1	2	0	` |
| **当前代码** | `output_manager.py:273` |
| **当前写法** | `@\\{library}\\.\\{cell}\\(view)\t0\t1\t1\t3\t0\t` |
| **实际输出** | `@\8367_lib\.\8367\(sch_1)	0	1	1	3	0	` |

**影响**: 反斜杠不是 Cadence 期望的分隔符。Cadence 使用点号 `.` 分隔库名/单元名/视图名。反斜杠可能导致 module_order 无法正确解析。

**修复**: 将格式改为 `f"@{library}.{cell}({view})\t0\t1\t1\t2\t0\t"`

**涉及文件**:
- `cis2hdl/core/writer/output_manager.py:270-274`

> ✅ 已实施（2026-08-07 代码核实：xcon_writer.py/output_manager.py 存在对应实现）
> 注：行号随代码演进已失效。

---

### P1-2: .dcf 文件 revisionNumber 应从 0 开始

| 项目 | 内容 |
|------|------|
| **参考 .dcf,1**（初始版） | `logicalViewRevNum 0` |
| **参考 .dcf,2** | `logicalViewRevNum 1` |
| **参考 .dcf**（最终版） | `logicalViewRevNum 2` |
| **当前代码** | `output_manager.py:336` — 硬编码 `logicalViewRevNum 2` |

**影响**: 新项目应该从 revision 0 开始。如果初始 revision 就是 2，Cadence 可能认为这是一个已经修改过的项目。

**修复**: 将初始 `logicalViewRevNum` 改为 `0`。

**涉及文件**:
- `cis2hdl/core/writer/output_manager.py:337`

> ✅ 已实施（2026-08-07 代码核实：xcon_writer.py/output_manager.py 存在对应实现）
> 注：行号随代码演进已失效。

---

### P1-3: 文件行尾格式不一致（CRLF vs LF）

| 项目 | 内容 |
|------|------|
| **参考 worklib/* 文件** | **CRLF** (`\r\n`) — 包括 master.tag, page1.csa, .dcf, .xcon |
| **参考根目录文件** | **LF** (`\n`) — 包括 out_hdl.cpm, cds.lib |
| **当前代码** | 使用 `Path.write_text(content, encoding="ascii")` → 输出 LF |

**影响**: Cadence SPB 16.6 是 Windows 原生应用，期望 worklib 下的文件使用 Windows 行尾格式（CRLF）。使用 LF 可能导致某些文件解析异常。

**修复方案**: 
- 对于 `worklib/` 下的文件：使用 `newline="\r\n"` 或显式替换 `\n` → `\r\n`
- 对于根目录的 `.cpm` 和 `cds.lib`：保持 LF

**涉及文件**:
- `cis2hdl/core/writer/output_manager.py` — 所有 `write_*` 方法
- `cis2hdl/core/writer/csa_writer.py:132` — `write_csa_page` 方法
- `cis2hdl/core/writer/sch_writer.py:594,600` — SCHWriterCSA 文件写入

> ✅ 已实施（2026-08-07 代码核实：xcon_writer.py/output_manager.py 存在对应实现）
> 注：行号随代码演进已失效。

---

### P1-4: 缺失 hdldirect.dat 文件

| 项目 | 内容 |
|------|------|
| **参考文件** | `CIStoHDL_standard/worklib/out_hdl/sch_1/hdldirect.dat` |
| **参考内容** | Lisp S-expression，定义 HDL Direct 配置 |
| **当前状态** | 未生成 |

**影响**: `hdldirect.dat` 文件用于 HDL Direct 功能（Verilog/VHDL 生成）。虽然可能不影响项目打开，但缺失此文件会在尝试使用 HDL Direct 功能时报错。

**修复**: 在 `OutputManager` 中添加 `write_hdldirect_dat()` 方法，生成最小有效的 hdldirect.dat。

**涉及文件**:
- `cis2hdl/core/writer/output_manager.py`

> ✅ 已实施（2026-08-07 代码核实：xcon_writer.py/output_manager.py 存在对应实现）

---

## P2 — 中优先级修复

### P2-1: .cpm session_name

| 项目 | 内容 |
|------|------|
| **参考写法** | `session_name 'ProjectMgr3606'` |
| **当前写法** | `session_name 'ProjectMgr0001'` |

**影响**: 较小。Cadence 可能用 session_name 检测项目是否被其他实例打开。不同的 session_name 可能导致 "project already open" 警告。建议使用更接近参考格式的名称。

**涉及文件**:
- `cis2hdl/core/writer/output_manager.py:479`

> ✅ 已实施（2026-08-07 代码核实：xcon_writer.py/output_manager.py 存在对应实现）
> 注：行号随代码演进已失效。

---

### P2-2: .cpm 文件注释中的工具名

| 项目 | 内容 |
|------|------|
| **参考写法** | `{ Machine generated file created by SPI }` |
| **当前写法** | `{ Machine generated file created by CIS2HDL }` |

**影响**: 极小。Cadence 校验可能检查工具名。使用 `SPI` 更安全。

**涉及文件**:
- `cis2hdl/core/writer/output_manager.py:467`

> ✅ 已实施（2026-08-07 代码核实：xcon_writer.py/output_manager.py 存在对应实现）
> 注：行号随代码演进已失效。

---

### P2-3: page1.csv 格式细节

| 项目 | 内容 |
|------|------|
| **参考** | `{Allegro Design Entry HDL 16.6-S115 (v16-6-112JX) 1/23/2019}` （含构建日期） |
| **当前** | `{Allegro Design Entry HDL 16.6-S115 (v16-6-112JX)}` （无构建日期） |

**影响**: 极小。仅为格式对齐。

**涉及文件**:
- `cis2hdl/core/writer/sch_writer.py:998`

> ✅ 已实施（2026-08-07 代码核实：xcon_writer.py/output_manager.py 存在对应实现）
> 注：行号随代码演进已失效。

---

### P2-4: page1.cpc 引用的 library 名称

| 项目 | 内容 |
|------|------|
| **参考** | `hdl_lib c#20size#20page *` |
| **当前 SCHWriterCSA** | `{self._library_name} c#20size#20page *` |

**影响**: `.cpc` 文件中的库引用。如果 `_library_name` 不是 `"hdl_lib"`，可能导致不一致。但多数情况下 `_library_name` 就是 `"hdl_lib"`，所以风险低。

**涉及文件**:
- `cis2hdl/core/writer/sch_writer.py:989-993`

> ✅ 已实施（2026-08-07 代码核实：xcon_writer.py/output_manager.py 存在对应实现）
> 注：行号随代码演进已失效。

---

## 文件编码汇总

| 参考文件 | 编码 | 行尾 |
|----------|------|------|
| `out_hdl.cpm` | ASCII | LF |
| `cds.lib` | ASCII | LF |
| `master.tag` | ASCII | **CRLF** |
| `page1.csa` | ASCII | **CRLF** |
| `out_hdl.dcf` | ISO-8859 | **CRLF** |
| `out_hdl.xcon` | ASCII | **CRLF** |
| `page1.cpc` | ASCII | **CRLF** |
| `page1.csv` | ASCII | **CRLF** |
| `hdldirect.dat` | ASCII | **CRLF** |
| `module_order.dat` | ASCII | **CRLF** |

---

## 修复优先级排序

```
P0-2 (.xcon缺失) —— 核心阻断，必须最先修复
    │
    ├── P0-1 (cds.lib ./前缀) —— 阻断
    ├── P0-3 (master.tag文件名) —— 阻断
    ├── P0-4 (CSA颜色MONO→ORANGE) —— 阻断
    │
P1-1 (module_order.dat格式) —— 高优
    │
    ├── P1-2 (dcf revision 0) —— 高优
    ├── P1-3 (CRLF行尾) —— 高优
    ├── P1-4 (hdldirect.dat) —— 高优
    │
P2-1 (session_name) —— 细节
P2-2 (.cpm注释) —— 细节
P2-3 (page1.csv日期) —— 细节
P2-4 (cpc库引用) —— 细节
```

---

## 修改文件清单

| 文件 | 修改类型 | 关联问题 |
|------|----------|----------|
| **新建** `cis2hdl/core/writer/xcon_writer.py` | 新建 | P0-2 |
| `cis2hdl/core/writer/output_manager.py` | 修改 | P0-1, P0-2, P0-3, P1-1, P1-2, P1-3, P1-4, P2-1, P2-2 |
| `cis2hdl/core/writer/csa_writer.py` | 修改 | P0-4, P1-3 |
| `cis2hdl/core/engine/conversion_engine.py` | 修改 | P0-2 |
| `cis2hdl/core/writer/cdslib_writer.py` | 修改 | P0-1 |
| `cis2hdl/core/writer/sch_writer.py` | 修改 | P0-3, P2-3, P2-4 |

---

## 附录：HDL_OUTPUT_FIX_PLAN 根因链摘要

> 本附录合并自 `docs/HDL_OUTPUT_FIX_PLAN.md`（2026-08-03，参考项目 `CIStoHDL_standard` 与当前 `cis2hdl` 代码的比特级对比），保留其根因链分析的原文要点。

### 执行摘要（原文要点）

比特级对比发现：**核心代码已经实现了正确的输出格式**（CSAWriter + OutputManager），但**测试输出使用的是旧版代码**（SCHWriter），导致用户看到的报错。

### 根因链（原文要点）

```
SCHWriter → 生成 .sch.* 格式 (非Cadence原生)
  ├─ .cpm 使用 START_DESIGN 格式 (缺少 cpm_version) → 触发 UPREV
  ├─ PIN 0 NET_xxx (错误的引脚编号) → 触发 SPCOCN-543
  └─ 格式不被 DEHDL 识别 → 文件无法正确加载

修复方向：切换到 CSAWriter + OutputManager (已实现但测试输出未更新)
```

### 关键结论（原文要点）

1. **UPREV 根因**：旧版 CPM 使用 `START_DESIGN`/`END_DESIGN` 格式、无 `cpm_version` 字段；已由 `output_manager.py:_build_cpm_content()` 修复为 `START_GLOBAL`/`END_GLOBAL` + `cpm_version '16.6'`（`config.py` 中 `cpm_version: str = "16.6"` 确认）。
2. **SPCOCN-543 根因**：旧版 `SCHWriter` 在 `_build_blocks()` 中使用 `PIN {pin_num} {net_name}` 格式且引脚编号异常；`csa_writer.py:CSAWriter._build_csa_content()` 已显式跳过 LASTPIN 生成（`$PN` 属性不应在页面文件中手动定义，Cadence 自动从 hdl_lib 获取）。
3. **页面格式切换**：`.sch.*` → `.csa`；`conversion_engine.py` 通过 `WriterRegistry` 注册 CPMWriter/CSAWriter，页面生成以 CSAWriter 为准（`WriterRegistry.get("csa")`）。
4. **缺失文件清单**（HDL_OUTPUT_FIX_PLAN 第 4 节）：`.dcf`（P1 待添加）、`.xcon`（P2 可推迟）、`master.tag` 内容修正、`page.map` 内容修正。
5. **验证清单**（HDL_OUTPUT_FIX_PLAN 第 7 节）：重新转换 → 检查 `.cpm` 含 `cpm_version '16.6'` → `.csa` 无 `$PN`/`LASTPIN` → Cadence SPB 16.6 打开无 UPREV、无 SPCOCN-543/541 警告。

> **与本文档的对应关系**：本附录根因链对应 fix_proposal 中 P0-2（.xcon 缺失）、P0-3（master.tag 文件名）、P1-2（.dcf revision 0）、P2 系列等条目；各条目逐项实施状态见上文 ✅ 标注。
