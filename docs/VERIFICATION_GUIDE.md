# CIS2HDL 项目验证指南

> 版本: v1.1.0 | 日期: 2026-08-07 | 状态: 生效
> 主验证对象: HG5015-BE36_V10（**24 CSA / 889 元件 / 3717 网络**）
> 测试基线: **268 passed / 23 skipped / 0 failed（291 collected，2026-08-07 实测）**
> 整合说明: 本文档为验证指南唯一权威，合并原 VERIFICATION_GUIDE（v0.3.5，RTL8367RB 时代）与 VERIFICATION_GUIDE_HG5015。**过往历史内容不删除，完整保留于「Part II 历史验证信息」**。

---

# Part I 当前验证指南（以 HG5015 为主验证对象）

## ⚡ 快速验证（3 步走）

```bash
cd D:\26暑假\cis2hdl

# 第1步: 全量测试 (268 passed / 23 skipped / 291 collected)
python -m pytest tests/unit/ tests/integration/ tests/e2e/ -q

# 第2步: HG5015 转换验证
python -m cis2hdl convert \
  tests/fixtures/HG5015-BE36_V10.DSN \
  --output output_hg5015 \
  --hdl-lib docs_for_reference/CIStoHDL_standard/hdl_lib

# 第3步: 检查输出 (在 Cadence 机器上打开 5015.cpm)
```

---

## 一、测试套件验证

### 1.1 测试基线（2026-08-07 实测）

- **结果**: 268 passed / 23 skipped / 0 failed
- **收集**: 291 collected
- **命令**: `python -m pytest tests/unit/ tests/integration/ tests/e2e/ -q`

### 1.2 测试文件分布

| 目录 | 文件数 | 说明 |
|------|:--:|------|
| `tests/unit/` | 14 | 单元测试；含 `test_matcher_v2.py`（**134 个测试**，pytest 实测收集；handoff 记 133） |
| `tests/integration/` | 3 | 集成测试 |
| `tests/e2e/` | 2 | 端到端测试：`test_rtl8367rb_full.py`（11）+ `test_verify_fixes.py`（11） |

> ⚠️ 已核实：**不存在** `test_config.py` / `test_csa_writer.py` / `test_edif_parser.py`（旧版验证指南引用的 3 个文件已核实不存在，详见 Part II 历史信息）。

### 1.3 分目录运行

```bash
# 单元测试
python -m pytest tests/unit/ -q

# 集成测试
python -m pytest tests/integration/ -q

# 端到端测试
python -m pytest tests/e2e/ -q
```

---

## 二、CLI 转换验证（HG5015）

### 2.1 HG5015 转换命令与预期输出

```bash
cd D:\26暑假\cis2hdl
python -m cis2hdl convert \
  tests/fixtures/HG5015-BE36_V10.DSN \
  --output output_hg5015 \
  --hdl-lib docs_for_reference/CIStoHDL_standard/hdl_lib
```

**预期输出**:
- **24 个 CSA**（page1~page24 = 20 原理图页 + 4 信息页 Cover/Block/Clock/Power）
- **889 元件** / **3717 网络**
- 匹配 **889/889**、quality=**72%**、NEEDS_REVIEW **67**

### 2.2 输出文件结构验证清单（13 项）

```
output_hg5015/
├── 5015.cpm                     ← 项目文件（SPI 工具名）
├── cds.lib                      ← 库定义（无 ./ 前缀）
├── hdldirect.dat                ← HDL Direct 配置
├── HG5015-BE36_V10_mapping.csv  ← 映射报告
├── HG5015-BE36_V10_report.html  ← HTML 报告
├── hdl_lib/                     ← 完整器件库
├── temp/
└── worklib/5015/sch_1/
    ├── page1.csa ~ page24.csa   ← 24 页原理图（20 原理图 + 4 信息页）
    ├── 5015.xcon                ← CS Schema XML
    ├── 5015.dcf                 ← 设计约束
    ├── 5015.con                 ← 约束文件
    ├── master.tag               ← 文件清单
    ├── module_order.dat         ← 模块排序
    └── page.map                 ← 页面映射
```

验证每一项（以实际输出目录 `HG5015_tests/output_v2b/` 为基准）：

```bash
# 检查输出文件存在
cd D:\26暑假\cis2hdl\HG5015_tests\output_v2b
ls 5015.cpm cds.lib hdldirect.dat HG5015-BE36_V10_mapping.csv HG5015-BE36_V10_report.html
ls worklib/5015/sch_1/

echo "=== 检查1: cpm_version ==="
grep "cpm_version" 5015.cpm
# 预期: cpm_version '16.6'

echo "=== 检查2: SPI 工具名 ==="
head -1 5015.cpm
# 预期: { Machine generated file created by SPI }

echo "=== 检查3: cds.lib 无 ./ 前缀 ==="
cat cds.lib
# 预期: DEFINE 5015_lib worklib (NOT ./worklib)

echo "=== 检查4: CSA 有 QUIT ==="
tail -1 worklib/5015/sch_1/page5.csa
# 预期: QUIT

echo "=== 检查5: CSA 有 C SIZE PAGE ==="
grep "C SIZE PAGE" worklib/5015/sch_1/page5.csa
# 预期: FORCEADD C SIZE PAGE..1

echo "=== 检查6: FORCEADD 使用 HDL 库 cell 名 ==="
grep "FORCEADD" worklib/5015/sch_1/page5.csa
# 预期: FORCEADD CAPACITOR..1 (cell 名，非 primitive 名)

echo "=== 检查7: COLOR 设置正确 ==="
grep "COLOR_PROP\|COLOR_NOTE" worklib/5015/sch_1/page5.csa
# 预期: ORANGE 和 PURPLE

echo "=== 检查8: master.tag 内容 ==="
cat worklib/5015/sch_1/master.tag
# 预期: page1~24.csa + 5015.xcon + 5015.dcf (+ page1~24.cpc)

echo "=== 检查9: .xcon 存在 ==="
wc -c worklib/5015/sch_1/5015.xcon
# 预期: > 1500 bytes（实测 6356 bytes）

echo "=== 检查10: module_order.dat 格式 ==="
cat worklib/5015/sch_1/module_order.dat
# 预期: @5015_lib.5015(sch_1) (没有反斜杠)

echo "=== 检查11: worklib 文件 CRLF 行尾 ==="
head -1 worklib/5015/sch_1/page1.csa | cat -v
# 预期: 行末有 ^M

echo "=== 检查12: 根文件 LF 行尾 ==="
head -1 5015.cpm | cat -v
# 预期: 行末无 ^M

echo "=== 检查13: 坐标在合理范围 ==="
grep -P "^\(-?[0-9]+ -?[0-9]+\)" worklib/5015/sch_1/page5.csa | head -5
# 预期: 坐标在 C SIZE PAGE 范围内 (-10750~0, 0~8275)
```

---

## 三、CSA 质量检查

| 检查项 | 命令 | 预期 |
|--------|------|------|
| FORCEADD | `grep FORCEADD page5.csa` | 使用 HDL 库 cell 名（如 CAPACITOR） |
| QUIT | `tail -1 page5.csa` | 每页以 QUIT 结尾 |
| C SIZE PAGE | `grep "C SIZE PAGE" page5.csa` | FORCEADD C SIZE PAGE..1 |
| COLOR | `grep COLOR_PROP/COLOR_NOTE page5.csa` | ORANGE / PURPLE |
| 坐标 | `grep "^(-?[0-9]+ -?[0-9]+)" page5.csa` | 在 C SIZE PAGE 范围内 |

> ⚠️ **ADD_COMMENT** 在 Cadence SPB 16.6 受限，已被跳过（不生成）。
> ⚠️ **PAINT WIRE** 生成器已于 v1.1.0 移除（Cadence 16.6 不支持）；原"7 页 16 段"为当时的临时接线状态记载（见 Part II）。

---

## 四、映射报告检查

打开 `HG5015-BE36_V10_mapping.csv`，确认:

- [x] 转换统计节包含所有指标
- [x] 器件映射表列出所有 **889** 个器件
- [x] 匹配成功/失败/模糊匹配数量正确（NEEDS_REVIEW **67**）
- [x] 异常报告列出未匹配器件
- [x] 文件清单完整

---

## 五、Cadence SPB 16.6 实测步骤

1. 拷贝 `output_hg5015/`（或 `HG5015_tests/output_v2b/`）到 Cadence 机器
2. 双击 `5015.cpm` 用 Project Manager 打开
3. 确认不弹 UPREV（版本升级）对话框
4. 双击页面进入 Design Entry HDL
5. 运行 Check References
6. 逐页检查 **24 个页面**（20 原理图页 + 4 信息页 Cover/Block/Clock/Power）的器件和连接
7. 检查信息页的文本注释

> 注: RTL8367RB_CADENCE_TEST 输出目录已清理，历史 Cadence 实测记录见 Part II；HG5015 的 Cadence SPB 16.6 二次实测为待办项。

---

## 六、回归测试

```bash
cd D:\26暑假\cis2hdl
python -m pytest tests/unit/ tests/integration/ tests/e2e/ -q
```

**预期**: 268 passed / 23 skipped / 0 failed（291 collected），零回归

---

## 七、GBK 乱码修复验证

验证 strLst 中的 GBK 编码中文已正确解码：

```bash
cd D:\26暑假\cis2hdl
python -c "
from cis2hdl.core.parser.dsn.library_parser import parse_strlst
from cis2hdl.core.parser.dsn.ole_reader import OleReader
from pathlib import Path

ole = OleReader(Path('tests/fixtures/HG5015-BE36_V10.DSN'))
lib = ole.read_stream('Library')
strlst = parse_strlst(lib)

# Check for GBK-decoded Chinese text
for i, s in enumerate(strlst):
    if '电' in s or '感' in s or '电感' in s:
        print(f'[{i}] \"{s}\"')
        if i < 5:
            break
"
```

**预期**: 输出 `片式电感` 和 `终端功率电感` 而非 `Æ¬Ê½µç¸Ð` 等乱码。

---

## 八、非 refdes 过滤验证

验证 DESCRIPTION/SOURCE_LIBRARY 属性值不会被误用为 refdes：

```bash
cd D:\26暑假\cis2hdl
python -c "
from cis2hdl.core.parser.dsn.structures import _is_valid_rtl_name

# 应拒绝的条目
assert not _is_valid_rtl_name('片式电感'), 'Should reject Chinese description'
assert not _is_valid_rtl_name('终端功率电感'), 'Should reject Chinese description'
assert not _is_valid_rtl_name(r'D:\\WORK_PCB\\HW_RF.OLB'), 'Should reject path'
assert not _is_valid_rtl_name(''), 'Should reject empty'

# 应接受的条目
assert _is_valid_rtl_name('R1'), 'Should accept refdes'
assert _is_valid_rtl_name('C460'), 'Should accept refdes'
assert _is_valid_rtl_name('NT5CC256M16ER-EKI'), 'Should accept IC part number'
assert _is_valid_rtl_name('C_0402'), 'Should accept library ID'

print('All _is_valid_rtl_name assertions passed.')
"
```

**预期**: 全部断言通过。

---

## 九、BOM 交叉验证方法论（吸收自 test1.txt 操作 19）

### 9.1 CDS 属性系统

Cadence 的 HDL 工程中，每个器件/网络/引脚都有标准属性。这些属性需要从 CIS 源工程正确迁移：

| 属性类别 | 关键属性名 | 在 CIS 中的来源 |
|---------|-----------|---------------|
| 器件标识 | `REFDES`（位号，如 R1/C5/U3） | CIS Instance → Reference |
| 器件值 | `VALUE`（如 10K/0.1uF） | CIS Instance → Value |
| 封装 | `PCB Footprint`（如 0805/SOIC8） | CIS Instance → PCB Footprint |
| 器件名 | `PART_NAME` | CIS Instance → Part Name |
| 库引用 | `SOURCE_LIBRARY` | OLB 文件路径 |
| 引脚属性 | `PIN_NUMBER` / `PIN_NAME` | CIS Pin → Number / Name |
| 网络属性 | `NET_NAME` / `NET_PHYSICAL_TYPE` | CIS Net → Name / Type |
| BOM 信息 | `BOM_IGNORE` / `BOM_SEQ` | CIS Instance 属性 |

### 9.2 方法 1：在 Project Manager 中直接查看

```bash
# 打开 HDL 工程后，双击打开任意 .sch 页面
# 选中一个器件 → 右键 → Properties → 查看属性面板
```

```
检查每个器件类别的属性：

  R（电阻）:
    □ REFDES = R?（从 CIS 迁移）
    □ VALUE = 具体阻值（如 10K）
    □ PCB Footprint = 封装名（如 0805）
    □ PART_NAME = 器件库名
    □ 引脚 1 和 2 的网络名

  C（电容）:
    □ REFDES = C?
    □ VALUE = 具体容值（如 0.1uF）
    □ PCB Footprint = 封装名
    □ 极性电容的 pin 1（正极）是否正确标记

  U（芯片）:
    □ REFDES = U?
    □ VALUE = 芯片型号
    □ PCB Footprint = 封装（如 LQFP128EP）
    □ 所有引脚编号和名称
    □ 电源引脚是否连接到正确的电源网络
```

### 9.3 方法 2：导出 BOM 交叉验证

```
Step 1: 在 Capture CIS 中打开原始 DSN 工程
  Tools → Bill of Materials → 导出 BOM 为 CSV

Step 2: 在 Project Manager 中打开 HDL 工程
  Tools → Bill of Materials → 导出 BOM 为 CSV

Step 3: 用 Excel 对比两个 BOM
  · 列：位号 / 器件值 / 封装
  · 逐行对比，标记差异
```

### 9.4 方法 3：用 Python 脚本自动对比

```python
# 在 Cadence 电脑上运行（需要能访问两个 BOM CSV）
import csv

def load_bom(csv_path):
    with open(csv_path) as f:
        return {row['REFDES']: row for row in csv.DictReader(f)}

cis_bom = load_bom("cis_bom.csv")
hdl_bom = load_bom("hdl_bom.csv")

mismatches = []
for refdes in cis_bom:
    if refdes not in hdl_bom:
        mismatches.append(f"{refdes}: MISSING in HDL")
    elif cis_bom[refdes]['VALUE'] != hdl_bom[refdes]['VALUE']:
        mismatches.append(f"{refdes}: VALUE mismatch ({cis_bom[refdes]['VALUE']} vs {hdl_bom[refdes]['VALUE']})")

print(f"Total mismatches: {len(mismatches)}")
for m in mismatches[:20]:
    print(f"  {m}")
```

### 9.5 验证失败排查

| 症状 | 可能原因 | 修复方向 |
|------|---------|---------|
| 打开工程报 "library not found" | cds.lib 路径错误 | 检查 cds.lib 中的库路径是否有效 |
| 器件显示为红色矩形 | 符号文件缺失 | 需要提供 OLB 库并配置符号降级路径 |
| 网络名空白 | DSN net 解析不完整 | 检查 T0x10/Net 解析日志 |
| 属性值为空 | 属性迁移未完成 | 检查 CIS→HDL 属性映射配置 |
| 电源引脚未连接 | 电源网络分类错误 | 检查 `classify_net()` 逻辑 |

---

# Part II 历史验证信息（完整保留）

> ⚠️ 本部分为历史版本内容完整保留，**不作为当前验证基线**；当前基线以 Part I 为准。此处数字（如 136 tests、20 pages/1001 instances/4115 nets）均为历史口径。

## II.1 原 VERIFICATION_GUIDE.md（历史口径，2026-08-03，主验证对象 RTL8367RB）

> 以下为原 VERIFICATION_GUIDE.md 全文（生成于 2026-08-03 16:25）。其中 **136 tests**、**99 单元测试** 等数字为**历史口径，2026-08-03**，已被 Part I 的 **268 passed / 23 skipped / 291 collected** 取代；其引用的 `test_config.py` / `test_csa_writer.py` / `test_edif_parser.py` 三个测试文件**已核实不存在**；RTL8367RB 为历史验证对象（6 页/12 实例/423 网/16 输出，RTL8367RB_CADENCE_TEST 输出目录已清理）。

---

# CIS2HDL 项目验证指南 v0.3.5

> 生成时间: 2026-08-03 16:25
> 项目状态: Phase I/II/III/IV/V 全部完成, 70+ 任务, 136 tests
> 最后更新: 代码重构 + 测试重组 + 参考比对完成

---

## ⚡ 快速验证（3 步走）

```bash
cd D:\26暑假\cis2hdl

# 第1步: 全量测试 (136 tests)
python -m pytest tests/unit/ tests/integration/ tests/e2e/ -v

# 第2步: 生成验证输出
python -m cis2hdl convert \
  "tests/fixtures/RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN" \
  --output "output_verify_final" \
  --hdl-lib "docs_for_reference/CIStoHDL_standard/hdl_lib" \
  --benchmark

# 第3步: 检查输出 (在 Cadence 机器上打开 8367.cpm)
```

---

## 一、测试套件验证

### 1.1 单元测试 (99 tests)

```bash
cd D:\26暑假\cis2hdl
python -m pytest tests/unit/ -v --tb=short
```

覆盖模块:
| 模块 | 测试文件 | 测试数 |
|------|---------|:--:|
| IR 数据模型 | `test_ir_models.py` | 11 |
| 配置系统 | `test_config.py` | ~8 |
| CPM Writer | `test_cpm_writer.py` | ~4 |
| CSA Writer | test_csa_writer.py | ~3 |
| DSN Parser | `test_dsn_parser.py` | ~6 |
| EDIF Parser | `test_edif_parser.py` | ~3 |
| 输出兼容性 | `test_output_compatibility.py` | 23 |
| SCH Writer | `test_sch_writer.py` | 6 |
| 其他 | (matcher/diagnostics/utils) | ~35 |

**预期**: 99 passed ✅

### 1.2 集成测试 (17 tests)

```bash
python -m pytest tests/integration/ -v --tb=short
```

| 测试文件 | 测试数 | 说明 |
|---------|:--:|------|
| `test_full_pipeline.py` | 2 | 六阶段全管道 |
| `test_matcher_pipeline.py` | 15 | 四级匹配链 |

**预期**: 17 passed ✅

### 1.3 端到端测试 (10 tests)

```bash
python -m pytest tests/e2e/ -v --tb=short
```

| 测试文件 | 测试数 | 说明 |
|---------|:--:|------|
| `test_rtl8367rb_full.py` | 10 | 真实 RTL8367RB 工程 (667KB DSN) |
| `test_verify_fixes.py` | 11 | UPREV 兼容性 12 项修复验证 |

**预期**: 20+ passed ✅

### 1.4 全量汇总

```bash
python -m pytest tests/unit/ tests/integration/ tests/e2e/ -q
```

预期输出:
```
========================== 136 passed, 1 skipped in XXs ==========================
```

---

## 二、命令行转换验证

### 2.1 执行真实 DSN 转换

```bash
cd D:\26暑假\cis2hdl
python -m cis2hdl convert \
  "tests/fixtures/RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN" \
  --output "output_verify_final" \
  --hdl-lib "docs_for_reference/CIStoHDL_standard/hdl_lib" \
  --benchmark
```

**预期**: `Conversion complete: SUCCESS pages=6 instances=12 nets=423 outputs=16 matched=6/6 quality=70%`

### 2.2 输出文件结构验证清单

```
output_verify_final/
├── 8367.cpm                  ← 项目文件（SPI 工具名）
├── cds.lib                   ← 库定义（无 ./ 前缀）
├── hdldirect.dat             ← HDL Direct 配置
├── *_report.html             ← 转换报告
├── hdl_lib/                  ← 完整器件库
├── temp/
└── worklib/8367/sch_1/
    ├── page1.csa ~ page6.csa ← 6页原理图
    ├── 8367.xcon             ← CS Schema XML
    ├── 8367.dcf              ← 设计约束
    ├── 8367.con              ← 约束文件
    ├── master.tag            ← 文件清单
    ├── module_order.dat      ← 模块排序
    └── page.map              ← 页面映射
```

验证每一项：
```bash
# 检查输出文件存在
cd D:\26暑假\cis2hdl\output_verify_final
ls 8367.cpm cds.lib hdldirect.dat *_report.html
ls worklib/8367/sch_1/

echo "=== 检查1: cpm_version ==="
grep "cpm_version" 8367.cpm
# 预期: cpm_version '16.6'

echo "=== 检查2: SPI 工具名 ==="
head -1 8367.cpm
# 预期: { Machine generated file created by SPI }

echo "=== 检查3: cds.lib 无 ./ 前缀 ==="
cat cds.lib
# 预期: DEFINE 8367_lib worklib (NOT ./worklib)

echo "=== 检查4: CSA 有 QUIT ==="
tail -1 worklib/8367/sch_1/page1.csa
# 预期: QUIT

echo "=== 检查5: CSA 有 C SIZE PAGE ==="
grep "C SIZE PAGE" worklib/8367/sch_1/page1.csa
# 预期: FORCEADD C SIZE PAGE..1

echo "=== 检查6: FORCEADD 使用 HDL 库名 ==="
grep "FORCEADD RTL" worklib/8367/sch_1/page1.csa
# 预期: FORCEADD RTL8367..1 (不是 VRTL8367RB-VB_LQ128EP_0)

echo "=== 检查7: COLOR 设置正确 ==="
grep "COLOR_PROP\|COLOR_NOTE" worklib/8367/sch_1/page1.csa
# 预期: ORANGE 和 PURPLE

echo "=== 检查8: master.tag 内容 ==="
cat worklib/8367/sch_1/master.tag
# 预期: page1~6.csa + .xcon + .dcf

echo "=== 检查9: .xcon 存在 ==="
wc -c worklib/8367/sch_1/8367.xcon
# 预期: > 1500 bytes

echo "=== 检查10: module_order.dat 格式 ==="
cat worklib/8367/sch_1/module_order.dat
# 预期: @8367_lib.8367(sch_1) (没有反斜杠)

echo "=== 检查11: worklib 文件 CRLF 行尾 ==="
head -1 worklib/8367/sch_1/page1.csa | cat -v
# 预期: 行末有 ^M

echo "=== 检查12: 根文件 LF 行尾 ==="
head -1 8367.cpm | cat -v
# 预期: 行末无 ^M

echo "=== 检查13: 坐标在合理范围 ==="
grep -P "^\(-?[0-9]+ -?[0-9]+\)" worklib/8367/sch_1/page1.csa | head -5
# 预期: 坐标在 C SIZE PAGE 范围内 (-10750~0, 0~8275)
```

---

## 三、Cadence SPB 16.6 环境验证

### 3.1 准备工作

1. 将 `D:\26暑假\cis2hdl\output_verify_final\` 整个文件夹拷贝到有 Cadence 的电脑
2. 确保 Cadence 环境变量 `CDSROOT` 已设置（指向 SPB 16.6 安装目录，如 `C:\Cadence\SPB_16.6`）
3. 确保 `CDSROOT\tools\bin` 在 PATH 中

### 3.2 步骤

```
步骤1: 双击 8367.cpm → Cadence Project Manager 启动
  ✅ 预期: 不弹 UPREV（版本升级）对话框
  ✅ 预期: 项目正常加载，显示 8367 工程

步骤2: 查看 Project Manager 项目树
  ✅ 预期: 显示 8367_lib → 8367 → sch_1，包含 6 个页面

步骤3: 双击 page1 → Design Entry HDL 打开
  ✅ 预期: 不报 SPCOCN-1891 (syntax error)
  ✅ 预期: 不报 SPCOCN-515 (找不到器件)
  ✅ 预期: 页面显示 C SIZE PAGE 边框
  ✅ 预期: 页面中有 RTL8367 芯片符号

步骤4: 检查坐标
  ✅ 预期: 芯片在 C SIZE PAGE 边框内部（不在原点角落）
  ✅ 预期: 符号不重叠

步骤5 (可选): 尝试编辑保存
  ✅ 预期: 可正常保存，不报 SPCOCN-543 (引脚属性错误)
```

### 3.3 备选方案（如果 UPREV 仍弹窗）

```powershell
cd 到 output_verify_final 目录
concepthdl.exe -nonetlistuprev -proj "8367.cpm"
```

---

## 四、GUI 功能验证

### 4.1 启动

```bash
cd D:\26暑假\cis2hdl
python -m cis2hdl gui
```

### 4.2 逐功能验证

| 功能 | 操作 | 预期结果 |
|------|------|---------|
| 打开项目 | `Ctrl+O` → 选择 DSN 文件 | 文件树显示、诊断自动运行 |
| 诊断页 | 观察 "Diagnostics" Tab | 文件状态树 + 四维进度条 |
| 预览页 | `Ctrl+2` → "Preview" Tab | 原理图图形渲染（器件矩形+连线） |
| 报告页 | "Report" Tab | 彩色状态总览 + 逐页详情 |
| 错误页 | `Ctrl+3` → "Errors" Tab | 39 错误码分类树 |
| 匹配确认 | 低置信度自动弹出 MatchConfirmDialog | 三栏确认界面 |
| 快速诊断 | `Ctrl+D` | 诊断结果自动刷新 |
| 运行转换 | `Ctrl+R` | 状态栏显示进度 + 完成统计 |
| 规则管理 | "Rules" Tab（有规则时显示） | QTableWidget 规则列表 |
| 历史记录 | 关闭窗口 | `~/.cis2hdl/conversion_history.json` 更新 |

### 4.3 快捷键速查

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+O` | 打开项目 |
| `Ctrl+R` | 运行转换 |
| `Ctrl+D` | 运行诊断 |
| `Ctrl+1` | 切换到 Diagnostics Tab |
| `Ctrl+2` | 切换到 Preview Tab |
| `Ctrl+3` | 切换到 Errors Tab |
| `Ctrl+Q` | 退出 |

---

## 五、批量转换验证

```python
# 创建测试脚本 tests/e2e/verify_batch.py
from pathlib import Path
from cis2hdl.core.engine.batch_engine import (
    BatchConversionEngine, ProjectSpec
)

specs = [
    ProjectSpec(
        dsn_path=Path("tests/fixtures/RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN"),
        output_dir=Path("output_batch_test"),
        hdl_lib_path=Path("docs_for_reference/CIStoHDL_standard/hdl_lib"),
    ),
]

engine = BatchConversionEngine()
report = engine.batch_convert(specs)

print(f"Batch: {report.success_count}/{report.projects_total} succeeded")
print(f"Elapsed: {report.elapsed_seconds:.1f}s")
print(report.summary())

# 质量趋势
trend = report.quality_trend()
print(f"Avg match rate: {trend['avg_match_rate']:.1%}")
```

---

## 六、OLB 解析验证

```bash
cd D:\26暑假\cis2hdl
python -c "
from cis2hdl.core.parser.olb.olb_parser import OLBParser
from pathlib import Path

p = OLBParser()
ir = p.parse(Path('tests/fixtures/LIBRARY2CLEAN.OLB'))
comps = ir.component_db.list_all()
print(f'OLB Packages: {len(comps)}')
for c in comps[:5]:
    print(f'  {c.library_id} → prefix={c.refdes_prefix} pins={c.pin_count}')
"
```

**预期**: 20/21 Package 成功解析 ✅

---

## 七、完整性测试

### 7.1 损坏 DSN 恢复测试

```bash
# 截断文件恢复
python -m cis2hdl convert \
  "tests/fixtures/RTL8367RB-CORRUPTED-TRUNCATED.DSN" \
  --output "output_truncated_test" \
  --hdl-lib "docs_for_reference/CIStoHDL_standard/hdl_lib"

# 扇区损坏恢复
python -m cis2hdl convert \
  "tests/fixtures/RTL8367RB-CORRUPTED-SECTOR.DSN" \
  --output "output_sector_test" \
  --hdl-lib "docs_for_reference/CIStoHDL_standard/hdl_lib"
```

**预期**: FileRecoveryStrategy 5 条降级路径触发，每个路径标注数据损失

### 7.2 Benchmark 性能

```bash
python -m cis2hdl convert \
  "tests/fixtures/RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN" \
  --output "output_bench" \
  --hdl-lib "docs_for_reference/CIStoHDL_standard/hdl_lib" \
  --benchmark
```

**预期输出示例**:
```
Benchmark:
  Diagnose:  0.0s
  Parse:     12.3s
  Scan:      31.8s  ← 通常是瓶颈（HDL 库扫描）
  Match:     0.5s
  Validate:  0.2s
  Generate:  19.4s
  Total:     64.2s
```

---

## 八、打包验证

```bash
cd D:\26暑假\cis2hdl
python scripts/build_exe.py --onefile --clean
```

**预期输出**: `dist/CIS2HDL.exe`（约 50-80MB）

验证:
```bash
dist/CIS2HDL.exe --help
dist/CIS2HDL.exe convert tests/fixtures/xxx.DSN --output test --hdl-lib hdl_lib/
```

---

## 九、当前已知限制

| 限制 | 现象 | 状态 |
|------|------|:--:|
| 层次化 DSN | 每页仅显示顶层芯片，无叶子器件 | Phase IV 代码已就绪，RTL8367RB DSN 的 CFB 目录树损坏限制验证 |
| 坐标映射 | 使用 DSN→DEHDL BoundingBox 映射，可靠性待更多 DSN 文件测试 | 算法已实现 |
| 批量转换 UI | 批量队列界面 F3.3 待 P2 阶段实现 | 后端已完成 |
| Properties Panel | F2.4 P1 预留 | Phase III 未实施 |

---

## 十、验证通过/失败记录表

| # | 验证项 | 命令/操作 | 预期 | 实测 | 状态 |
|:--:|------|---------|------|------|:--:|
| 1 | 单元测试 | `pytest tests/unit/ -q` | 99 pass | | ⬜ |
| 2 | 集成测试 | `pytest tests/integration/ -q` | 17 pass | | ⬜ |
| 3 | E2E 测试 | `pytest tests/e2e/ -q` | 20+ pass | | ⬜ |
| 4 | CLI 转换 | `python -m cis2hdl convert ...` | SUCCESS | | ⬜ |
| 5 | cpm_version | `grep cpm_version 8367.cpm` | 16.6 | | ⬜ |
| 6 | cds.lib 无 ./ | `cat cds.lib` | DEFINE 8367_lib worklib | | ⬜ |
| 7 | CSA QUIT | `tail -1 page1.csa` | QUIT | | ⬜ |
| 8 | CSA C SIZE PAGE | `grep "C SIZE PAGE" page1.csa` | 存在 | | ⬜ |
| 9 | FORCEADD HDL名 | `grep FORCEADD page1.csa` | RTL8367 | | ⬜ |
| 10 | COLOR 设置 | `grep COLOR_PROP page1.csa` | ORANGE/PURPLE | | ⬜ |
| 11 | master.tag | `cat master.tag` | page1~6.csa | | ⬜ |
| 12 | .xcon 存在 | `wc -c 8367.xcon` | >1500 bytes | | ⬜ |
| 13 | module_order | `cat module_order.dat` | @lib.cell(view) | | ⬜ |
| 14 | worklib CRLF | `head -1 page1.csa \| cat -v` | ^M | | ⬜ |
| 15 | 根文件 LF | `head -1 8367.cpm \| cat -v` | 无^M | | ⬜ |
| 16 | 坐标范围 | `grep FORCEADD page1.csa` | -11000<x<0 | | ⬜ |
| 17 | Cadence UPREV | 双击 .cpm | 不弹升级对话框 | | ⬜ |
| 18 | Cadence 打开 | 双击页面 | 不报 SPCOCN-* | | ⬜ |
| 19 | GUI 启动 | `python -m cis2hdl gui` | 无 crash | | ⬜ |
| 20 | GUI 预览 | `Ctrl+2` | 原理图渲染 | | ⬜ |
| 21 | OLB 解析 | `OLBParser.parse(OLB)` | 20/21 | | ⬜ |
| 22 | Batch 转换 | `BatchConversionEngine` | 项目队列 | | ⬜ |
| 23 | PyInstaller | `build_exe.py` | .exe 生成 | | ⬜ |

---

## 附录: 输出目录文件大小参考（历史口径，2026-08-03）

> ⚠️ 对应输出目录已清理（RTL8367RB_CADENCE_TEST），**无法复核**。以下为原记录。

| 文件 | 大小 | 说明 |
|------|-----:|------|
| `8367.cpm` | 822 bytes | 项目配置文件 |
| `cds.lib` | 96 bytes | 库定义 |
| `hdldirect.dat` | 48 bytes | HDL Direct |
| `*_report.html` | ~10KB | 转换报告 |
| `8367.xcon` | 2,474 bytes | CS Schema XML |
| `8367.dcf` | 631 bytes | 设计约束 |
| `8367.con` | 311 bytes | 约束文件 |
| `master.tag` | 87 bytes | 文件清单 |
| `module_order.dat` | 84 bytes | 模块排序 |
| `page.map` | 10 bytes | 页面映射 |
| `page1~6.csa` | ~3.3KB each | 原理图页面 |

---

## II.2 原 VERIFICATION_GUIDE_HG5015.md（历史口径，2026-08-04）

> 以下为原 VERIFICATION_GUIDE_HG5015.md 全文。其中 **20 pages / 1001 instances / 4115 nets** 为**历史口径，2026-08-04**，已被 Part I 的 **24 CSA / 889 元件 / 3717 网络** 取代。

---

# HG5015-BE36_V10 CIS→HDL 转换验证指南

## 前置条件

1. 已安装 Python 3.13.12
2. 项目已安装依赖: `pip install -e .`

## 步骤 1: 运行转换

```bash
cd D:\26暑假\cis2hdl
python -m cis2hdl convert \
  tests/fixtures/HG5015-BE36_V10.DSN \
  --output output_hg5015 \
  --hdl-lib docs_for_reference/CIStoHDL_standard/hdl_lib
```

**预期输出**: 20 pages, 1001 instances, 4115 nets

## 步骤 2: 检查输出文件

确认 `output_hg5015/` 目录存在以下文件:

- [x] `5015.cpm`
- [x] `cds.lib` (无 `./` 前缀)
- [x] `hdldirect.dat`
- [x] `worklib/5015/sch_1/5015.xcon` (可 XML 解析)
- [x] `worklib/5015/sch_1/5015.dcf`
- [x] `worklib/5015/sch_1/master.tag`
- [x] `worklib/5015/sch_1/page1.csa` ~ `page20.csa`
- [x] `HG5015-BE36_V10_mapping.csv` (映射报告)
- [x] `HG5015-BE36_V10_report.html` (HTML 报告)

## 步骤 3: 检查 CSA 质量

```bash
# 检查 FORCEADD 行
cd output_hg5015
grep -c FORCEADD worklib/5015/sch_1/page*.csa

# 检查 QUIT
grep QUIT worklib/5015/sch_1/page5.csa

# 检查 C SIZE PAGE
grep "C SIZE PAGE" worklib/5015/sch_1/page5.csa

# 检查信息页文本
grep ADD_COMMENT worklib/5015/sch_1/page9.csa | head -5
```

## 步骤 4: 检查映射报告

打开 `HG5015-BE36_V10_mapping.csv`，确认:

- [x] 转换统计节包含所有指标
- [x] 器件映射表列出所有 1001 个器件
- [x] 匹配成功/失败/模糊匹配数量正确
- [x] 异常报告列出未匹配器件
- [x] 文件清单完整

## 步骤 5: Cadence SPB 16.6 实测

1. 拷贝 `output_hg5015/` 到 Cadence 机器
2. 双击 `5015.cpm` 用 Project Manager 打开
3. 确认不弹 UPREV
4. 双击页面进入 Design Entry HDL
5. 运行 Check References
6. 逐页检查 20 个页面的器件和连接
7. 检查信息页 (Cover/Block/Clock/Power) 的文本注释

## 步骤 6: 回归测试

```bash
cd D:\26暑假\cis2hdl
python -m pytest tests/unit/ -q
```

**预期**: 全通过，零回归

## 步骤 7: GBK 乱码修复验证

验证 strLst 中的 GBK 编码中文已正确解码：

```bash
cd D:\26暑假\cis2hdl
python -c "
from cis2hdl.core.parser.dsn.library_parser import parse_strlst
from cis2hdl.core.parser.dsn.ole_reader import OleReader
from pathlib import Path

ole = OleReader(Path('tests/fixtures/HG5015-BE36_V10.DSN'))
lib = ole.read_stream('Library')
strlst = parse_strlst(lib)

# Check for GBK-decoded Chinese text
for i, s in enumerate(strlst):
    if '电' in s or '感' in s or '电感' in s:
        print(f'[{i}] \"{s}\"')
        if i < 5:
            break
"
```

**预期**: 输出 `片式电感` 和 `终端功率电感` 而非 `Æ¬Ê½µç¸Ð` 等乱码。

## 步骤 8: 非 refdes 过滤验证

验证 DESCRIPTION/SOURCE_LIBRARY 属性值不会被误用为 refdes：

```bash
cd D:\26暑假\cis2hdl
python -c "
from cis2hdl.core.parser.dsn.structures import _is_valid_rtl_name

# 应拒绝的条目
assert not _is_valid_rtl_name('片式电感'), 'Should reject Chinese description'
assert not _is_valid_rtl_name('终端功率电感'), 'Should reject Chinese description'
assert not _is_valid_rtl_name(r'D:\\WORK_PCB\\HW_RF.OLB'), 'Should reject path'
assert not _is_valid_rtl_name(''), 'Should reject empty'

# 应接受的条目
assert _is_valid_rtl_name('R1'), 'Should accept refdes'
assert _is_valid_rtl_name('C460'), 'Should accept refdes'
assert _is_valid_rtl_name('NT5CC256M16ER-EKI'), 'Should accept IC part number'
assert _is_valid_rtl_name('C_0402'), 'Should accept library ID'

print('All _is_valid_rtl_name assertions passed.')
"
```

**预期**: 全部断言通过。

---

# Part II 完

---

## Phase XV 验证指南（2026-08-11 追加）

### Cadence 16.6 复测重点（用户环境）

1. **打开 `output_phaseXV_final`（默认 p0）**：
   - SPCOCN-543 应大幅消失（LASTPIN 格式已对齐 04p4）
   - 电容引脚不再"偏下差一点"（属性绑定恢复）
   - U6 等主芯片显示占位符号（非 CH347），标注 PLACEHOLDER
   - L20/L14 旋转方向正确（90↔270 互换）
2. **打开 `output_phaseXV_aes`（--aesthetic 美观化）对比**：
   - 电线排布与默认**明显不同**：stub 引出段（线不贴引脚）、绕障、差异化的引出距离
   - GND 符号每芯片附近分布（非整图 1 个）
   - 跨页 IO 口右缘单列等间距（非右上角挤堆）
3. **未解决项确认**：
   - 若 L20 仍翻转 → mirror（M 行）问题，反馈后启用 MY/MX
   - 若 IO 口仍多余 → 页内网 IOPORT 语义核对

### 本机自动化检查

```bash
pytest tests/ -q  # 519 passed / 5 skipped
# 转换：p0 84% / aes 85%，$PN 无 PAINT、CH347 0、GND 1082、WIRE +132%
```
