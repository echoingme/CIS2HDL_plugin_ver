import os
target = r"D:\26暑假\cis2hdl\docs\_improvement_plan.md"

report = r"""# cis2hdl 改进方案

> 生成日期: 2026-08-03
> 基于: docs/_comparison_report.md
> 排序: P0 > P1 > P2

---

## P0 -- 阻塞性问题 (会导致功能缺失或严重错误)

### P0-1: Value 精确匹配缺失

**现状**: MatcherPipeline 使用 FuzzyNameMatcher 进行模糊名称匹配，缺少参考库的 normalize_value() 精确 Value 比较功能。

**参考代码** (match_cis_to_hdl.py L339-346):
```python
def normalize_value(v):
    v = v.upper().strip()
    v = v.replace("PF","PF").replace("NF","NF").replace("UF","UF")
    v = v.replace("KOHM","K").replace("MOHM","M")
    v = v.rstrip("*").strip()
    v = re.sub(r"\s+","",v)
    return v
```

**影响**: 无法在 part.ptf 料表中精确匹配器件型号(如100nF/10uF/1k等)，导致匹配准确率下降。

**方案**:
1. 在 `cis2hdl/core/matcher/` 下新增 `value_matcher.py`
2. 实现 `normalize_value(value: str) -> str` 函数
3. 在 `ExactMatcher.match()` 中接入: 对 source 和 candidates 的值字段调用 normalize_value 后比较
4. 匹配成功则 confidence=1.0, strategy=EXACT

**预计工作量**: 2-3h
**文件**: 新建 `cis2hdl/core/matcher/value_matcher.py`
**修改**: `cis2hdl/core/matcher/exact.py` (接入 value 比较)
**测试**: `tests/matcher/test_value_matcher.py`

---

## P1 -- 重要缺陷 (影响输出正确性或一致性)

### P1-1: symbol.css 动态偏移未集成

**现状**: CSAWriter 对所有器件使用硬编码偏移 (VALUE: -5,-50; LOCATION: -5,+220)，而参考通过 get_prop_offsets() 从 symbol.css 动态读取。

**影响**: 不同器件的属性位置不理想，尤其是大型芯片(sym_2~sym_13)的属性偏移完全不同。

**参考代码** (generate_hdl_sch.py L27-66):
```python
def get_prop_offsets(body_name):
    css_path = os.path.join(HDL_LIB_DIR, body_name, "sym_1", "symbol.css")
    offsets = {}
    with open(css_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.startswith("P "):
                continue
            parts = line.split('"')
            prop_name = parts[1]
            coords_str = parts[4].strip()
            coords = coords_str.split()
            x, y = int(coords[0]), int(coords[1])
            tokens = line.strip().split()
            rot, just = 0, 1
            if len(tokens) >= 10:
                just = int(tokens[8])
            offsets[prop_name] = (x, y, rot, just)
    return offsets
```

**方案**:
1. CSAWriter 构造函数接受 `hdl_lib_path: Path` 参数
2. 在 `_build_csa_content()` 中，对每个 body_name 调用 `SymbolCSSParser` 获取偏移
3. 将偏移 (x,y,rot,just) 应用于 FORCEPROP 的坐标和 R/J 行
4. 对未找到的 body_name 回退到当前硬编码

**预计工作量**: 4-6h
**文件**: 修改 `cis2hdl/core/writer/csa_writer.py`
**依赖**: `cis2hdl/core/parser/symbol_css.py` (已存在)

### P1-2: ROTATION/JUSTIFICATION 缺失

**现状**: 参考对所有可见属性(VALUE, $LOCATION)使用 "R 1" + "J 1"，当前使用 "J 0" 且无 R 行。

**影响**: 位号和值文字不旋转，在拥挤的布局中可能重叠。Cadence DEHDL 标准使用 R 1 旋转文字90度避免拥挤。

**方案**:
1. 耦合 P1-1 (symbol.css 动态偏移)
2. 从 symbol.css 读取 rot/just 参数
3. 在 CSA 输出中根据 rot 值生成 "R {rot}" 行
4. 根据 just 值生成 "J {just}" 行
5. 回退默认: rot=1, just=1

**预计工作量**: 2-3h (与P1-1耦合)
**文件**: 修改 `cis2hdl/core/writer/csa_writer.py`

### P1-3: .dcf 文件生成缺失

**现状**: 参考项目中 DCF 文件包含详细的属性快照(每个 instance 的 VALUE, PACKAGE_TYPE, SN_NUM, XY, ROT 等)，当前不生成 .dcf。

**影响**: DCF 用于 Allego PCB 设计约束传递。虽然 DEHDL 编译可自动生成，但自动生成的 DCF 可能缺少前端属性。

**参考格式** (out_hdl.dcf 关键结构):
```
( ConstraintFile "out_hdl"
  ( DictionaryExtensions
    ( Attribute (Name "CDS_LMAN_SYM_OUTLINE") ... )
    ( Attribute (Name "DESCRIPTION") ... )
    ( Attribute (Name "PACKAGE_TYPE") ... )
    ( Attribute (Name "SN_NUM") ... )
  )
  ( designConstraints
    ( gate "@out_hdl_lib.out_hdl(sch_1):page1_i1"
      ( attribute "CDS_LIB" "hdl_lib" (Origin gPackager) )
      ( attribute "VALUE" "100nF" (Origin gFrontEnd) )
      ...
    )
  )
)
```

**方案**:
1. 新建 `cis2hdl/core/writer/dcf_writer.py`
2. 从 DesignIR + MatchResult 提取属性快照
3. 生成 Lisp/S-expr 格式的 DCF 内容
4. 由 OutputManager 写入 `worklib/<cell>/sch_1/<cell_name>.dcf`

**预计工作量**: 4-6h
**文件**: 新建 `cis2hdl/core/writer/dcf_writer.py`
**修改**: `cis2hdl/core/writer/output_manager.py` (write_dcf 方法)

---

## P2 -- 可选改进 (增强功能或向后兼容)

### P2-1: .scr 脚本生成

**现状**: 参考有 generate_hdl_scr.py 生成 DEHDL 控制台批处理脚本，当前无此功能。

**方案**: 新建 `cis2hdl/core/writer/scr_writer.py`，生成 DEHDL 控制台 add 脚本(备选放置方式)。

**预计工作量**: 2-3h

### P2-2: .con 连通性文件生成

**现状**: 参考有 b50285.con 定义连通性约束，当前未实现。

**方案**: 在 OutputManager 中添加 write_con() 方法，生成 conceptHDL 格式的连通性约束文件。

**预计工作量**: 1-2h

### P2-3: CSA 额外属性精简决策

**现状**: 当前 CSAWriter 生成了 CDS_LOCATION, $SEC, CDS_SEC 等参考不存在的属性。

**评估**: 这些属性可能是当前项目 IR 结构需要的扩展。需要验证 DEHDL 是否会因为这些额外属性报错。如果过时，应清理；如果必需，应文档化。

**方案**:
1. 在 DEHDL 中打开当前生成的 .csa 文件测试兼容性
2. 删除不必要的额外属性
3. 保留 DEHDL 必需的属性并添加注释说明

**预计工作量**: 1-2h

---

## 实施顺序建议

```
Phase A (P0, 2-3h):
  1. P0-1: Value 精确匹配
  -> 验证: 匹配准确率提升

Phase B (P1, 8-12h):
  2. P1-1 + P1-2: symbol.css偏移 + ROTATION (耦合实施)
  3. P1-3: .dcf 生成
  -> 验证: CSA 输出与参考格式一致

Phase C (P2, 4-7h):
  4. P2-1: .scr 脚本生成
  5. P2-2: .con 生成
  6. P2-3: CSA 额外属性清理
  -> 验证: 完整功能覆盖

总预计工作量: 14-22h
"""

with open(target, 'w', encoding='utf-8') as f:
    f.write(report)
size = os.path.getsize(target)
print(f"Improvement plan written: {size} bytes")