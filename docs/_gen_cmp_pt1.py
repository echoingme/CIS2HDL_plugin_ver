import os
target = r"D:\26暑假\cis2hdl\docs\_comparison_report.md"

# Build complete report
report = r"""# CIStoHDL_standard vs cis2hdl 详细比对报告

> 生成日期: 2026-08-03
> 基于: docs/_reference_index.md
> 用途: Phase 2.1 逐项深度比对

---

## 1. 功能完备性

### 1.1 功能矩阵

| 功能 | 参考实现 | 当前实现 | 状态 | 优先级 |
|------|---------|---------|------|--------|
| CIS数据提取 | export_page13.py (COM) | dsn_parser.py (OLE) | COMPLETE (80%) | - |
| EDIF解析 | c2esch.edif | edif_parser.py | COMPLETE | - |
| OLB库解析 | (无) | olb_parser.py | NEW | - |
| chips.prt解析 | parse_chips_prt() | chips_prt.py | COMPLETE (90%) | - |
| part.ptf解析 | parse_part_ptf() | part_ptf.py | COMPLETE (95%) | - |
| symbol.css解析 | get_prop_offsets() | symbol_css.py | COMPLETE (85%) | - |
| Value精确匹配 | normalize_value() | (无) | MISSING | P0 |
| 手动映射持久化 | (无) | YAML import/export | NEW | - |
| CSA页面生成 | generate_hdl_sch.py | csa_writer.py | COMPLETE (95%) | - |
| symbol.css动态偏移 | get_prop_offsets() | 硬编码 | GAP | P1 |
| ROTATION支持 | R 1 J 1 | J 0 only | GAP | P1 |
| .scr脚本生成 | generate_hdl_scr.py | (无) | MISSING | P2 |
| .dcf生成 | DEHDL编译产出 | (无独立writer) | GAP | P1 |
| .con生成 | b50285.con | (无) | MISSING | P2 |

### 1.2 优先级汇总

| 优先级 | 数量 | 条目 |
|--------|------|------|
| P0 | 1 | Value精确匹配缺失 |
| P1 | 3 | symbol.css偏移硬编码, ROTATION缺失, .dcf生成 |
| P2 | 3 | .scr生成, .con生成, COM诊断/Tcl导出 |

---

## 2. CSA输出格式逐行对比

### 2.1 文件头对比 -- 判定: 完全一致

参考 (generate_hdl_sch.py, L131-140):
```
FILE_TYPE = MACRO_DRAWING;
SET COLOR_WIRE YELLOW;
SET COLOR_PROP ORANGE;
SET COLOR_DOT WHITE;
SET COLOR_ARC YELLOW;
SET COLOR_BODY GREEN;
SET COLOR_NOTE PURPLE;
SET PROP_DISPLAY VALUE;
SET PAGE_NUMBER P1;
```

当前 (csa_writer.py, L197-205) 生成相同输出。

### 2.2 CSIZEPAGE边框对比 -- 判定: 完全一致

参考 (L142-167) 与当前 (L208-229) 逐行相同。两者都将 EDIT PAGE NAME 硬编码为 "DDR3"。

### 2.3 FORCEADD指令对比

参考 page1.csa L32-37:
```
FORCEADD CAPACITOR..1
(-10500 7500);
FORCEPROP 1 LAST CDS_LMAN_SYM_OUTLINE -50,0,50,-25
J 0
(-10500 7500);
DISPLAY 0.468085 (-10500 7500);
PAINT GREEN (-10500 7500);
DISPLAY INVISIBLE (-10500 7500);
```

当前 csa_writer.py L294-295, L319-325: FORCEADD..{section} 语义等价。

### 2.4 VALUE属性 -- 关键差异

**参考 (L233-238):**
```python
vo = prop_offsets.get("VALUE", (50, 5, 0, 1))
nl(f"FORCEPROP 1 LAST VALUE {cis_value}")
nl("R 1")       # ROTATION
nl("J 1")       # JUSTIFICATION
nl(f"({x + vo[0]} {y + vo[1]});")
nl(f"DISPLAY 0.851064 ({x + vo[0]} {y + vo[1]});")
```

**当前 (L297-308):**
```python
vx, vy = x - 5, y - 50    # 硬编码偏移
lines.append(f"FORCEPROP 1 LAST VALUE {value}")
# 无 R 行 (缺失 ROTATION!)
lines.append("J 0")       # J0而非J1
lines.append(f"({vx} {vy});")
lines.append(f"DISPLAY {_SCALE_VALUE} ({vx} {vy});")
lines.append(f"PAINT {_PAINT_ORANGE} ({vx} {vy});")
```

差异:
| 参数 | 参考 | 当前 |
|------|------|------|
| ROTATION | R 1 | none |
| JUSTIFICATION | J 1 | J 0 |
| 偏移来源 | symbol.css | 硬编码(-5,-50) |
| PAINT | 无 | ORANGE |
| SCALE | 0.851064 | 0.851064 (一致) |

### 2.5 PATH属性 -- 过渡渲染差异

参考: DISPLAY INVISIBLE 直接
当前: DISPLAY 1.021277 + PAINT ORANGE + DISPLAY INVISIBLE (过渡渲染)

### 2.6 LOCATION属性 -- 关键差异

参考: 始终 FORCEPROP 1 LAST $LOCATION, R 1, J 1
当前: section>1用$LOCATION否则LOCATION, J 0 (无ROT)

### 2.7 透明属性 -- 过渡渲染差异

所有透明属性(PART_NAME, CDS_LIB, DESCRIPTION, PACKAGE_TYPE, SN_NUM, JEDEC_TYPE):
- 参考: 直接 DISPLAY INVISIBLE
- 当前: DISPLAY + PAINT + INVISIBLE (过渡渲染)

### 2.8 当前独有属性

CDS_LOCATION, $SEC, CDS_SEC -- 参考无

### 2.9 CDS_LMAN_SYM_OUTLINE -- BUG

参考: 电容器 -50,0,50,-25; 电阻器 -50,25,50,-25 (因器件而异)
当前: 硬编码 -50,0,50,-25 (统一用电容器值)

---

## 3. 坐标映射算法对比

### 3.1 算法核心 -- 判定: 完全一致

参考 map_cis_to_dehdl_coords() (L96-121) vs 当前 _map_coords_to_dehdl() (L569-616):
- 两者使用相同的 C PAGE 区域: x0=-10200, x1=-550, y0=400, y1=7200
- 相同的缩放因子: scale = min(pw/cw, ph/ch) * 0.7
- 相同的中心缩放 + Y轴反转公式

### 3.2 边缘情况差异

参考: 无坐标 -> dehdl_x/dehdl_y = None
当前: (0,0)滤除 + C PAGE 边界检查 [-10750,0]x[0,8275]

### 3.3 网格回退 -- 判定: 完全一致

5列, 2000x1500, 起点(-10500,7500)

---

## 4. 匹配算法对比

### 4.1 匹配策略差异

参考 (match_cis_to_hdl.py):
- 三重离散匹配: exact > size > prefix > none
- 直接按前缀索引 (by_prefix目录)
- normalize_value() 精确Value比较
- 单体函数 match_component()

当前 (pipeline.py):
- 四阶段管线: Exact > Fuzzy > Feature > Manual
- DB search + prefix_filter
- 模糊名称匹配 (无精确Value匹配)
- 多阶段链式调用

### 4.2 Value匹配 -- P0关键缺失

参考 normalize_value():
```python
def normalize_value(v):
    v = v.upper().strip()
    v = v.replace("PF","PF").replace("NF","NF").replace("UF","UF")
    v = v.replace("KOHM","K").replace("MOHM","M")
    v = v.rstrip("*").strip()
    v = re.sub(r"\s+","",v)
    return v
```

当前: 无此功能。使用 FuzzyNameMatcher 的模糊名称匹配，不执行单位规范化和精确值比较。

### 4.3 前缀过滤 -- 判定: 高度一致

参考 body_map / body_fallback 与当前 prefix_filter.py PREFIX_TO_CATEGORY 映射表一致，当前版本还有扩展。

---

## 5. body_name解析对比

### 5.1 参考方法

generate_hdl_sch.py L178-180:
```python
body_name = hdl_part if hdl_part else "capacitor"
cell_name = body_name.upper()
```
直接从 CSV 的 hdl_part 字段读取，简洁可靠。

### 5.2 当前方法

csa_writer.py _resolve_body_name() L457-509:
```python
# step1: match_map -> ComponentDef.library_id -> rsplit("/")[-1]
# step2: inst.library_id -> rsplit("/")[-1]  (可能产生DSN层级路径!)
# step3: refdes prefix -> mapping table
# step4: refdes.upper() fallback
# step5: "UNKNOWN"
```

**问题**: step2 直接从 library_id 取最后一段时，对于 DSN 层级路径 (如 "VRTL8367RB-VB_LQ128EP_0") 会得到非法的 HDL 库目录名。

### 5.3 symbol.css 偏移对比

参考 get_prop_offsets() (L27-66):
- 逐行解析 symbol.css 的 "P " 行
- 提取属性名、默认值、坐标(x,y)、旋转(rot)、对齐(just)
- 用于 VALUE, PATH, PART_NAME, PACKAGE_TYPE, JEDEC_TYPE, $LOCATION

当前 csa_writer.py:
- VALUE: (x-5, y-50) 硬编码
- LOCATION: (x-5, y+220) 硬编码
- 其他属性: (x, y) 居中
- SymbolCSSParser 类存在但未集成到 CSAWriter

---

## 6. 输出文件格式对比

### 6.1 .xcon 格式

参考 out_hdl.xcon:
- schemaVersion 16.6
- cells 节点含完整单元定义
- instances 节点含实例-引脚绑定
- pageName (如 "DDR3")
- lastids 跟踪

当前 output_manager._build_xcon_content():
- schemaVersion 16.6 (一致)
- cells 节点为空 (缺失单元定义)
- instances 节点为空 (缺失实例定义)
- pageName 缺失
- lastids 为空

差异: 当前生成的 .xcon 缺少 cells 和 instances 节点及 pageName

### 6.2 .con 格式

参考 b50285.con:
```
(
  (version 16.5)
  (tool (creator "conceptHDL") (last "conceptHDL"))
  (library "1_lib")
  (design "b50285" (lastIds ))
)
```

当前: 未实现

### 6.3 .dcf 格式

参考 out_hdl.dcf: 包含 DictionaryExtensions (CDS_LMAN_SYM_OUTLINE, DESCRIPTION, PACKAGE_TYPE, SN_NUM) 和 designConstraints (每个 gate 的属性快照)

当前: 不生成 .dcf, 由 DEHDL 编译后自动产生

---

## 7. 汇总与建议

### 7.1 高覆盖 (可直接使用)
- CSA 文件头/尾: 100% 一致
- C SIZE PAGE 边框: 100% 一致
- 坐标映射算法: 98% 一致
- 网格回退布局: 100% 一致
- 前缀过滤: 95% 一致

### 7.2 需修复 (P0)
- Value 精确匹配缺失: 需实现 normalize_value()

### 7.3 需改进 (P1)
- symbol.css 偏移集成: 将 SymbolCSSParser 接入 CSAWriter
- ROTATION 支持: 添加 R 行和属性偏移 rot/just 参数
- .dcf 生成: 实现独立 dcf_writer 或确保 DEHDL 正确编译

### 7.4 可选 (P2)
- .scr 脚本生成: 实现 generate_hdl_scr.py 对应功能
- .con 生成: 实现连通性约束
- COM 诊断工具: 低优先级
"""

with open(target, 'w', encoding='utf-8') as f:
    f.write(report)
size = os.path.getsize(target)
print(f"Comparison report written: {size} bytes")