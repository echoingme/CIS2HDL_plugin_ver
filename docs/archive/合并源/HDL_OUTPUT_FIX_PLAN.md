# HDL 输出格式差异与修复方案

**基于**: 参考项目 `CIStoHDL_standard` 与当前 `cis2hdl` 代码的比特级对比
**日期**: 2026-08-03

---

## 执行摘要

经过比特级对比分析，发现当前项目的**核心代码已经实现了正确的输出格式**（CSAWriter + OutputManager），但**测试输出使用的是旧版代码**（SCHWriter），导致用户看到的报错。

### 根因链

```
SCHWriter → 生成 .sch.* 格式 (非Cadence原生)
  ├─ .cpm 使用 START_DESIGN 格式 (缺少 cpm_version) → 触发 UPREV
  ├─ PIN 0 NET_xxx (错误的引脚编号) → 触发 SPCOCN-543
  └─ 格式不被 DEHDL 识别 → 文件无法正确加载

修复方向：切换到 CSAWriter + OutputManager (已实现但测试输出未更新)
```

---

## 1. 文件版本号问题（导致 UPREV）✅ 已修复

### 1.1 问题描述
Cadence 打开 `.cpm` 文件时检测到版本不匹配，触发 UPREV 流程，但 `write.exe` 不在 PATH 中导致失败。

### 1.2 根因分析
- 旧版 CPM 使用 `START_DESIGN`/`END_DESIGN` 格式，**没有 `cpm_version` 字段**
- Cadence 无法判断版本，触发升级流程

### 1.3 修复状态
**代码层面已修复**。`output_manager.py:_build_cpm_content()` (第327-389行) 已经实现了正确的格式：

```python
# output_manager.py 已正确实现：
nl("START_GLOBAL")
nl(f"design_name '{self.cell_name}'")
nl(f"design_library '{self.library_alias}'")
nl(f"library 'hdl_lib' '{self.library_alias}'")
nl(f"temp_dir '{cfg.output.temp_dir}'")
nl(f"cpm_version '{cfg.output.cpm_version}'")  # ← 16.6
nl("END_GLOBAL")
nl("START_CONCEPTHDL")
nl("PAGE_NAME_PROP 'EDIT PAGE NAME'")
nl("END_CONCEPTHDL")
```

配置确认：`config.py` 中 `cpm_version: str = "16.6"` ✅

### 1.4 验证方法
1. 重新运行转换，生成新的 `.cpm` 文件
2. 确认文件包含 `cpm_version '16.6'`
3. 确认格式为 `START_GLOBAL`/`END_GLOBAL`
4. 在 CadenceProject Manager 中打开，不应触发 UPREV

---

## 2. 引脚属性 $PN 格式问题（导致 SPCOCN-543）✅ 已修复

### 2.1 问题描述
Cadence 加载时批量删除 `$PN` 引脚属性：
```
INFO(SPCOCN-543) The pin property $PN with value 89 has been deleted
INFO(SPCOCN-543) The pin property $PN with value 90 has been deleted
```

### 2.2 根因分析
- 旧版 `SCHWriter` 在 `_build_blocks()` (第192-206行) 中使用 `PIN {pin_num} {net_name}` 格式
- 引脚编号来自 `pin_connections` 字典，但值异常（如 "0"）
- Cadence 期望引脚编号与 `symbol.css` + `chips.prt` 中的定义完全一致
- **`$PN` 属性不应在页面文件中手动定义** — Cadence 自动从 hdl_lib 获取

### 2.3 修复状态
**代码层面已修复**。`csa_writer.py:CSAWriter._build_csa_content()` (第339-344行) 显式跳过了 LASTPIN 生成：

```python
# csa_writer.py 第339-344行 — 已有注释说明
# ── Pin connections (LASTPIN) — SUPPRESSED (方案 A) ─────
# LASTPIN entries are NOT emitted.  DEHDL auto-generates
# pin numbers and net names from the HDL component library
# definitions during compilation.  Emitting incorrect $PN
# values (without matching SIG_NAME entries) causes
# SPCOCN-543 errors in Cadence Concept HDL.
```

### 2.4 CSA vs SCH 格式对比

| 维度 | CSA 格式 (正确) | SCH 格式 (错误) |
|------|----------------|----------------|
| 格式类型 | Cadence MACRO_DRAWING 原生格式 | 自定义文本格式 |
| 引脚定义 | 不定义（Cadence 自动获取） | `PIN {num} {net}` 硬编码 |
| 器件引用 | `FORCEADD CAPACITOR..1` → 引用 hdl_lib | `BEGIN BLOCK refdes worklib cell symbol` |
| 格式标识 | `FILE_TYPE = MACRO_DRAWING;` | `VERSION 6` |
| Cadence 识别 | ✅ 直接编译为 .csb | ❌ 无法识别 |

### 2.5 验证方法
1. 重新运行转换，确认生成 `.csa` 文件（非 `.sch.*`）
2. 确认 `.csa` 文件中无 `LASTPIN` 或 `$PN` 相关内容
3. 在 Cadence 中打开，不应出现 SPCOCN-543/SPCOCN-541 警告

---

## 3. 页面格式切换：`.sch.*` → `.csa`

### 3.1 当前架构
`conversion_engine.py` 注册了三个 writer：

```python
WriterRegistry.register(CPMWriter())    # ✅ 正确
WriterRegistry.register(SCHWriter())    # ❌ 应禁用（旧格式）
WriterRegistry.register(CSAWriter())    # ✅ 正确（新格式）
```

在第533-545行，engine 使用 CSAWriter（通过 `WriterRegistry.get("csa")`）生成页面 — **这是正确的**。

### 3.2 确认事项
需要确认 `conversion_engine.py` 的主流程：
1. ✅ 使用 `CSAWriter.write_with_manager()` 生成 CSA 页面
2. ✅ 使用 `OutputManager` 生成项目文件
3. ❓ 确认没有同时调用 `SCHWriter` 生成 `.sch.*` 文件

### 3.3 测试输出更新
`tests/fixtures/RTL8367RB_CADENCE_TEST/` 中的旧格式文件需要**重新生成**：
- 删除旧的 `.sch.*` 文件
- 运行新代码生成 `.csa` 文件

---

## 4. 缺失文件问题

### 4.1 参考项目输出 vs 当前代码实现

| 文件 | 参考项目 | 当前代码 (output_manager.py) | 状态 |
|------|---------|-----------------------------|------|
| `.cpm` | ✅ | ✅ `write_cpm()` | ✅ 正确 |
| `cds.lib` | ✅ | ✅ `write_cdslib()` | ✅ 正确 |
| `.con` | ❌ (使用 .dcf) | ✅ `write_con_file()` | 🟡 格式待验证 |
| `.dcf` | ✅ `out_hdl.dcf` | ❌ 未实现 | 🔴 P1 待添加 |
| `.xcon` | ✅ `out_hdl.xcon` | ❌ 未实现 | 🟡 P2 可推迟 |
| `module_order.dat` | ✅ | ✅ `write_module_order()` | ✅ 正确 |
| `master.tag` | ✅ (文件列表) | ✅ (但内容为 `"CDS_SYSTEM"`) | 🟡 内容需修正 |
| `page.map` | ✅ `"1 1 DDR3\n"` | ✅ (空文件) | 🟡 内容需修正 |

### 4.2 `.dcf` 文件 — P1 优先级
**作用**: 设计约束文件，Cadence 的 Packager 和 Constraint Manager 需要此文件来管理器件属性和规则。

**参考格式**（S-expression）:
```lisp
( ConstraintFile "out_hdl"
  ( constraintHeader
    ( objectKey ( logical ) )
    ( version ( 16.6 ) )
    ( revisionNumber ( logicalViewRevNum 2 ) ( physicalViewRevNum 0 ) )
    ...
  )
  ( DictionaryExtensions
    ( Attribute ( Name "CDS_LMAN_SYM_OUTLINE" ) ... )
    ( Attribute ( Name "DESCRIPTION" ) ... )
    ( Attribute ( Name "PACKAGE_TYPE" ) ... )
    ( Attribute ( Name "SN_NUM" ) ... )
  )
  ( designConstraints
    ( ruleChanges
      ( gate "@out_hdl_lib.out_hdl(sch_1):page1_i1"
        ( attribute "VALUE" "0.9PF" ( Origin gFrontEnd ) )
        ( attribute "PART_NAME" "CAPACITOR_0201" ( Origin gFrontEnd ) )
        ...
        ( pin "\1\" )     ← 引脚引用（反斜杠转义）
        ( pin "\2\" )
      )
    )
  )
)
```

**修复方案**: 在 `OutputManager` 中添加 `write_dcf()` 方法，生成最小有效的 `.dcf` 文件。

### 4.3 `master.tag` 内容修正
**当前**: `"CDS_SYSTEM"`
**参考**: `"out_hdl.csa\nout_hdl.xcon\nout_hdl.dcf\n"`

**修复**: 修改 `write_placeholder_files()` 中的 `master.tag` 内容为文件清单。

### 4.4 `page.map` 内容修正
**当前**: 空字符串
**参考**: `"1 1 DDR3\n"`（格式: `页码 数量 页面名称`）

**修复**: 修改 `write_placeholder_files()` 中 `page.map` 为正确的格式字符串。

---

## 5. Phase III 功能缺失影响评估

### 5.1 当前未实现的功能
根据 DEHDL 标准，以下功能当前未实现，但**不直接影响基本兼容性**：

| 功能 | 影响 | 优先级 |
|------|------|--------|
| OLB 库解析 | 解析 OrCAD Capture 库获取器件符号 | P2 — 非阻塞 |
| 完整 PTF 生成 | part.ptf 中的多行数据支持 | P1 — 影响器件属性完整性 |
| Symbol 图形生成 | 生成 symbol.css 图形数据（L/C/M/B指令） | P2 — Cadence 可用默认图形 |
| hdldirect.dat | HDL Direct 接口文件 | P2 |
| pc.db | 引脚约束数据库 | P2 |

### 5.2 对当前报错的影响评估
**结论**: 当前报错（UPREV + SPCOCN-543）**与 Phase III 功能缺失无关**。
- UPREV → 由 `.cpm` 格式版本号引起 → 代码已修复
- SPCOCN-543 → 由 `.sch.*` 中的错误 PIN 格式引起 → CSAWriter 已绕过

---

## 6. 代码修改清单

### 6.1 必须修改（P0）

| 序号 | 文件 | 修改内容 | 工作量 |
|:----:|------|---------|:------:|
| 1 | `output_manager.py` | `master.tag` 改为文件列表格式 | 小 |
| 2 | `output_manager.py` | `page.map` 改为 `"1 1 <name>\n"` 格式 | 小 |
| 3 | `output_manager.py` | 添加 `write_dcf()` 方法 | 中 |
| 4 | `conversion_engine.py` | 确认 CSAWriter 为主 writer | 检查/小 |

### 6.2 建议修改（P1）

| 序号 | 文件 | 修改内容 | 工作量 |
|:----:|------|---------|:------:|
| 5 | `output_manager.py` | 添加 `write_xcon()` 方法 | 中 |
| 6 | `output_manager.py` | 添加补充文件（`hdldirect.dat`, `pc.db` 等） | 小 |
| 7 | 测试 | 重新生成所有测试 fixture | 小 |

### 6.3 可选修改（P2）

| 序号 | 文件 | 修改内容 |
|:----:|------|---------|
| 8 | `config.py` | 添加 SCHWriter 启用/禁用开关 |
| 9 | `symbol_css.py` | 增强 symbol.css 生成能力 |

---

## 7. 验证清单

- [ ] 重新运行转换：`python -m cis2hdl convert tests/fixtures/...DSN --output .../`
- [ ] 确认输出目录格式：
  ```
  output/
  ├── <project>.cpm          ← START_GLOBAL, cpm_version '16.6'
  ├── cds.lib                ← DEFINE ... ./worklib, INCLUDE ... DEFINE hdl_lib
  ├── temp/
  └── worklib/<cell>/
      ├── sch_1/
      │   ├── page1.csa      ← FILE_TYPE = MACRO_DRAWING;
      │   ├── page1.cpc
      │   ├── page1.csv
      │   ├── <cell>.con     ← version 16.6
      │   ├── <cell>.dcf     ← S-expression 格式
      │   ├── module_order.dat
      │   ├── master.tag     ← 文件列表
      │   └── page.map       ← "1 1 <name>\n"
      ├── cfg_package/
      ├── cfg_pic/
      ├── physical/
      └── variant/
  ```
- [ ] `.cpm` 文件包含 `cpm_version '16.6'`
- [ ] `.csa` 文件无 `$PN` / `LASTPIN` 相关内容
- [ ] 在 Cadence SPB 16.6 中打开 `.cpm`，无 UPREV 提示
- [ ] 无 SPCOCN-543 / SPCOCN-541 警告
