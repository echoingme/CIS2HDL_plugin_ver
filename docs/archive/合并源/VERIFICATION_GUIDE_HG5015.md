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
