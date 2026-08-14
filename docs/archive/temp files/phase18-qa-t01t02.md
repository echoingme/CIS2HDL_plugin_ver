# Phase XVIII QA 验证报告 — T01+T02（P0 报错清零批次）

> QA 工程师：严过关（Yan）｜主理人齐活林代执行（QA agent 会话中断后由主理人接管验证）
> 验证日期：2026-08-13
> 验证对象：工程师完成的 T01（R1+R2）+ T02（R3+R4）
> 方法：全量 pytest + 真实 E2E 转换（HG5015 工程）+ 产物断言 + 代码审查

---

## 1. 验证结果总表

| # | 验证项 | 方法 | 结果 | 说明 |
|---|--------|------|:---:|------|
| 1 | 全量单元测试 | `pytest tests/unit/` | ✅ 671 passed | 工程师完成时实测 |
| 2 | 全量测试（含 e2e） | `pytest tests/` | ✅ **736 passed / 5 skipped** | 基线 684→736（+52 新测试） |
| 3 | E2E 真实转换 | CLI convert HG5015.EDF | ✅ 成功 | 24 页/1219 实例/917 匹配/84% |
| 4 | temp_lib symbol.css 语法 | validate_symbol_css 全量 | ✅ **0 错误** | SPCOCN-1158 根因消除（U/D→R/L） |
| 5 | temp_lib 库结构 | validate_temp_lib_structure | ✅ **[]** | master.tag 分目录 golden（SPCOCN-515 根因消除） |
| 6 | X "PIN_TEXT" 覆盖 | grep 15/15 cell | ✅ 100% | 真实库先例（ch347） |
| 7 | sym_2 视图切换 | CSA 含 CAPACITOR..2 | ✅ 生效 | page10/11/13/16/17 等（R3 Q2） |
| 8 | GND_POWER golden 对齐 | LASTPIN offset + SIG_NAME | ✅ 完全一致 | body+(50,100)、`GND_POWER\g`、PAINT MONO |
| 9 | ORIGIN 引用 | grep CSA | ✅ **0 条** | R4/Q1 达成 |
| 10 | CrossRef 属性注入 | CSA FORCEPROP 1 LAST | ✅ **897 条 PACKAGE_TYPE 真值** | 0 条 "?" 注入 |
| 11 | UN$ 网名稳定化 | stabilize_un_name | ✅ 实现 | `UN$5SCAPACITORSI43$2`→`UN_5SCAPACITORSI43_2` |
| 12 | LASTPIN 命中强校验 | _lastpin_coord_hit | ✅ 生效 | 少量 miss 记录进报告（C228/C355 等） |

---

## 2. 详细验证记录

### 2.1 全量测试（#1/#2）

```
工程师完成时：736 passed, 5 skipped in 70.49s
新增测试文件：
  tests/unit/test_symbol_css_validator.py   (12 tests)
  tests/unit/test_temp_lib_structure.py     (9 tests)
  tests/unit/test_spcn543_fix.py            (15 tests)
  tests/unit/test_crossref_attrs.py         (20 tests, 含主理人补 5 个 entire 格式)
```

### 2.2 E2E 真实转换（#3）

命令：`python -m cis2hdl convert HG5015-BE36_V10.EDF --output /tmp/qa_v18_e2e --hdl-lib tests/fixtures/hdl_lib`

```
Conversion complete: SUCCESS pages=24 instances=1219 nets=862
outputs=247 matched=917/917 quality=84%
```

### 2.3 temp_lib 语法与结构（#4/#5/#6）

```
symbol.css errors: 0
structure errors: []
master.tag: sym_1→"symbol.css" / chips→"chips.prt" / entity→"verilog.v" ✅
entity: master.tag + pc.db + verilog.v + vhdl.vhd + vlog004u.sir ✅
cells with X "PIN_TEXT": 15/15 ✅
BGA 四边 C 指令: justify=R（orient 90/270 表达方向）✅
```

### 2.4 sym_2 视图切换（#7）

```
CSA 中 FORCEADD CAPACITOR..2 出现于 page10(2)/page11(14)/page13(1)/page16(22)/page17(28)
—— 旋转电容改用 sym_2 横向视图（不写 R 行），对齐 golden page9 L354 先例
```

### 2.5 GND_POWER golden 对齐（#8）

```
FORCEADD GND_POWER..1
(-1500 6300);
FORCEPROP 3 LASTPIN (-1450 6400) SIG_NAME GND_POWER\g   ← body+(50,100) + golden 值
J 0
(-1440 6410);
DISPLAY 0.659574 ... PAINT MONO ... DISPLAY INVISIBLE    ← golden 格式
```

### 2.6 CrossRef 属性注入（#10）

```
全工程统计（真实 entire.csv 数据源）：
  PACKAGE_TYPE: 897 条真值（HSC0201-HDTA / HSC0402-HDTD / SR0201-TA 等）
  JEDEC_TYPE / SN_NUM / DESCRIPTION: 0 条（源 CSV 本为空，正确跳过）
  "?" 注入: 0 条 ✅
```

> ⚠️ 主理人发现并修复：CrossRefParser 原只支持简化版（逗号分隔 `Item,Part,...`），
> 真实 OrCAD "Entire" 导出（tab 分隔 `"HEADER"` + `"PARTINST:..."`）无法解析 →
> R4 属性注入在真实数据下失效。已修复 `_detect_delimiter`/`_build_col_map`/`_parse_row`
> 支持 tab 分隔 + 新增 `_parse_entire`（跳过 PININST 行、过滤 `<null>`/`?` 占位符），
> 并补 5 个单元测试（20/20 通过）。

### 2.7 LASTPIN 命中强校验（#12）

```
LASTPIN miss 记录（校验器正确拦截的实例）：
  J37.1 / J24.2 / C228.2 / T30.1 / C355.1 / C356.1 / C358.2 等
—— 设计意图：坐标未命中 symbol.css 引脚 → 不发射 LASTPIN（避免 SPCOCN-543），
  记录进 aesthetic_report [LASTPIN_MISS] 供人工复核
```

---

## 3. 主理人修复清单（QA 中发现并修复）

| # | 问题 | 位置 | 修复 |
|---|------|------|------|
| QA-1 | **Mapping CSV generation failed: name 'self' is not defined** | mapping_csv_writer.py L426 | `_xref_attrs` 被错误缩进为 `_write_device_mapping` 嵌套函数并误用 `self.` 调用 → 移到模块级直接调用（outputs 247 恢复正常） |
| QA-2 | **CrossRefParser 不支持 OrCAD Entire 格式**（tab 分隔，真实数据） | cross_ref_parser.py | 新增 `_detect_delimiter`/`_parse_entire`/`_RE_ENTIRE_HEADER`；`_build_col_map`/`_parse_row` 支持 tab；过滤 `<null>`/`?` 占位符 |

---

## 4. 诚实声明（静态 vs 实测）

| 项 | 验证程度 | 说明 |
|----|:---:|------|
| symbol.css 语法 / master.tag / X PIN_TEXT | ✅ 代码级实测 | 生成产物直接校验 |
| CAPACITOR..2 / GND_POWER\g / 属性注入 | ✅ 转换产物级实测 | 真实转换输出 grep/断言 |
| **SPCOCN-1158/515/543/541 在 Cadence 16.6 归零** | ⚠️ **待 Cadence 实测** | 代码级根因已消除，但最终确认需用户 Cadence 16.6 打开 v9 复测 |
| X "PIN_TEXT" / MOCK_TEXT X 指令渲染 | ⚠️ 待 Cadence 实测 | P→X 指令切换后需 16.6 目视确认 |
| sym_2 视图（180° 旋转无对应横向视图） | ⚠️ 部分待实测 | capacitor/resistor/inductor 的 90°/270° 已处理；180° 保留 R 行需 A/B 实测 |

---

## 5. 结论

**T01+T02 验收通过（代码级）**。四个 P0 报错根因（1158 CSS 语法 / 515 master.tag / 543 LASTPIN / attributes "?"）均已在真实转换产物中验证消除；工程师引入的 2 个新 bug（mapping_csv self、entire.csv 解析）由主理人 QA 发现并修复。**最终 Cadence 16.6 确认待用户复测 v9**。

*QA 报告 v1.0（2026-08-13）*
