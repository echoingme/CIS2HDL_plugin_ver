# HDL 原理图排版美观自动化分析与版本兼容性规范

> 版本: v1.0 | 日期: 2026-07-29 | 基于: 公司《硬件设计规范》+ Cadence SPB 16.6 实践项目

---

## 一、原理图排版美观：软件可实现 vs 人工调整

### 1.1 公司 HDL 规范要求（摘录自《硬件设计规范》）

| 规范条目 | 具体要求 |
|----------|---------|
| **网络名对齐** | 网络名左边统一为 7.5 格点处对齐 |
| **Net 长短一致** | 相邻网络的 net 线长度保持一致 |
| **Port 对齐** | Port 需要在同一水平线或垂直线上对齐 |
| **不相互重叠** | 所有命名不相互重叠，至少重要信息不重叠 |
| **字体样式** | 字体大小颜色均采用默认，方便统一 |
| **格点设置** | Grid = 0.05 inch，Grid Multiple = 10 |
| **Symbol 宽度** | 采用 6.10, 24 三种规格（逐步规范） |
| **IC 管脚** | 只左右分布 |
| **差分对** | 上 P 下 N |
| **Port 网络** | 同层设计不加 port |
| **电源/地** | 统一使用 hdl_lib 中的电源地和地符号，不用 signal |
| **库器件不可修改** | 不能移动 value 值和位号，不能镜像翻转 |
| **字符对齐** | 位号（RefDes）和 value 值统一位置，不可移动 |

### 1.2 可自动化实现的部分

| 规范 | 自动化可行性 | 实现难度 | 实现方式 |
|------|:----------:|:------:|---------|
| **网络名位置对齐（7.5格点）** | ✅ 可自动化 | 低 | 所有 net name 的 x 坐标统一设为 `7.5 * 0.05 * grid_multiple` |
| **Net 线长度一致** | ✅ 可自动化 | 低 | 根据相邻网络的参考点，统一 net 线段终点坐标 |
| **Port 对齐** | ✅ 可自动化 | 低 | 同侧 port 的 y 坐标等间距排列，x 坐标统一 |
| **格点对齐** | ✅ 可自动化 | 低 | 所有坐标值强制对齐到 `grid * grid_multiple` 的整数倍 |
| **字体统一** | ✅ 可自动化 | 极低 | 所有文本使用默认字体，生成时统一 |
| **不重叠检测** | ✅ 可自动化 | 中 | 对所有 label 边界框进行碰撞检测，自动微调偏移 |
| **Symbol 宽度** | ✅ 可自动化 | 低 | 生成 .sym 时按规范设置宽度 |
| **IC 管脚左右分布** | ✅ 可自动化 | 低 | 自动判断符号方向，IC 类管脚只放左右两侧 |
| **差分对排列（上P下N）** | ✅ 可自动化 | 低 | 解析差分对信号名，排序时 P 在 N 上方 |
| **BOM_SEQ 编码** | ✅ 可自动化 | 低 | 根据器件类型和封装自动生成编码 |
| **器件位号前缀** | ✅ 可自动化 | 低 | 根据器件类型（电阻→R，电容→C...）自动分配 |
| **Value 位置（右上/左上）** | ✅ 可自动化 | 低 | 小器件（阻容）value 在右上或左上 |

### 1.3 需要人工调整的部分

| 规范 | 自动化可行性 | 原因 |
|------|:----------:|------|
| **走线美观（全局布局）** | ❌ 难自动化 | 布线美学（避免交叉、对称性、空间利用）需要人工审美判断 |
| **原理图可读性** | ❌ 难自动化 | 电路功能分组、信号流向、模块边界划分依赖设计意图 |
| **复杂 IC 管脚排列** | ⚠️ 半自动 | 可提供功能分组建议，但最终排布需工程师确认 |
| **设计检查（逻辑正确性）** | ⚠️ 半自动 | 可做 DRC/ERC 检查，但设计意图的理解需人工 |

### 1.4 推荐策略：自动化 + 人工微调

```
软件自动排版（80%的美观工作）
    ↓
   生成符合规范的 .sch 文件
    ↓
   工程师在 Design Entry HDL 中微调（20%的审美工作）
    ↓
   最终交付
```

> **当前口径（2026-08-07）**：输出以 **CSA 原生格式（`.csa`）** 为准；`.sch.*` 为历史格式，不再作为交付格式。相关格式差异与兼容性经验详见"五、Cadence 兼容性经验速查"。

**软件负责**：所有"可以有明确规则"的事情——网格对齐、命名规范、标签位置、端口对齐、编码生成。

**人工负责**：需要"审美判断"的事情——全局布线优化、功能分组、空间美感。

---

## 二、HDL 器件库自动导入规范

### 2.1 HDL 库标准目录结构（基于公司实践项目）

```
hdl_lib/
├── <component_name>/           ← 器件库目录（全小写或无特殊字符）
│   ├── chips/
│   │   ├── chips.prt           ← 管脚定义文件（文本）
│   │   └── master.tag          ← 版本标记
│   ├── sym_1/                  ← 符号1（器件可能有多个符号 sym_2, sym_3...）
│   │   ├── symbol.css          ← 符号图形定义（文本）
│   │   └── master.tag
│   ├── sym_2/                  ← 符号2（如有）
│   │   └── ...
│   ├── part_table/
│   │   ├── part.ptf            ← Part Table 属性表（文本）
│   │   └── master.tag
│   ├── entity/
│   │   ├── pc.db               ← 实体数据
│   │   ├── verilog.v           ← Verilog 模型
│   │   └── vhdl.vhd            ← VHDL 模型
│   ├── metadata/
│   │   ├── pinlist.txt         ← 引脚列表
│   │   ├── pdv_validation.txt  ← 验证数据
│   │   ├── revision.dat        ← 版本信息
│   │   └── revHistory.log      ← 版本历史
│   └── cfg_package/            ← 配置包（可选）
│       └── expand.cfg
```

### 2.2 可自动导入的文件类型

| 文件 | 可解析内容 | 用途 |
|------|-----------|------|
| **chips.prt** | 管脚名称、编号、电气类型、Part 名称、位号前缀、CLASS | 快速建立器件 Pin 列表 |
| **symbol.css** | 符号图形坐标、引脚位置/名称/方向、value 位置 | 读取符号的图形布局信息 |
| **part.ptf** | 器件型号、封装、描述、SN_NUM、BOM_SEQ、规格参数 | 建立完善器件属性数据库 |
| **pinlist.txt** | 引脚功能列表 | 辅助验证 |
| **pad 文件 (.pad)** | 焊盘尺寸、形状、层定义 | PCB 封装信息 |
| **dra 文件 (.dra)** | 封装图形 | PCB 封装外形 |
| **psm 文件 (.psm)** | 封装符号模型 | PCB 完整封装 |

### 2.3 库导入工具需求

```python
class HDLLibraryImporter:
    """HDL 器件库导入器
    
    自动扫描指定目录，解析所有器件库文件，
    建立完整的 HDLComponentDB 数据库。
    """
    
    def scan_library(self, lib_root: Path) -> HDLComponentDB:
        """扫描整个 hdl_lib 目录树"""
        for comp_dir in lib_root.iterdir():
            component = ComponentInfo(name=comp_dir.name)
            
            # 解析 chips.prt
            chips_path = comp_dir / "chips" / "chips.prt"
            if chips_path.exists():
                component.pins = self._parse_chips_prt(chips_path)
            
            # 解析 part.ptf
            ptf_path = comp_dir / "part_table" / "part.ptf"
            if ptf_path.exists():
                component.properties = self._parse_part_ptf(ptf_path)
            
            # 解析 symbol.css (所有 sym_1, sym_2...)
            for sym_dir in comp_dir.glob("sym_*"):
                css_path = sym_dir / "symbol.css"
                if css_path.exists():
                    symbol = self._parse_symbol_css(css_path)
                    component.symbols.append(symbol)
            
            db.add(component)
        return db
    
    def import_pcb_library(self, lib_root: Path) -> PCBFootprintDB:
        """导入 PCB 封装库 (.pad, .dra, .psm)"""
        ...
```

### 2.4 chips.prt 解析规则

```python
# chips.prt 结构（示例）
# FILE_TYPE=LIBRARY_PARTS;
# primitive 'CAPACITOR_0402';
#   pin
#     '1':
#       PIN_NUMBER='(1)';
#       PINUSE='UNSPEC';
#     '2':
#       PIN_NUMBER='(2)';
#   end_pin;
#   body
#     PART_NAME='CAPACITOR_0402';
#     PHYS_DES_PREFIX='C';
#     CLASS='DISCRETE';
#   end_body;
# end_primitive;

# 解析要点:
# - FILE_TYPE 确认文件类型
# - primitive 'NAME' → 器件类型名称
# - pin 'NUM': PIN_NUMBER='(X)' → 管脚编号
# - PHYS_DES_PREFIX → 位号前缀 (R/C/L/U...)
# - CLASS → IC / DISCRETE
```

### 2.5 symbol.css 解析规则

```python
# symbol.css 结构（示例）
# P "CDS_LMAN_SYM_OUTLINE" "-50,0,50,-25" ...  ← 符号外形矩形
# M -40 0 40 0 -1 0                              ← 内部图形线
# P "$LOCATION" "?" -5 -100 90 0 40 0 0 1 0 ...  ← 位号位置
# P "VALUE" "?" -5 100 90 0 40 0 0 1 0 ...       ← Value 位置
# L 0 -75 0 -25 -1 0                               ← 引脚线 (x1,y1,x2,y2)
# C 0 -75 "1" 0 -60 0 0 32 1 R                     ← 引脚编号标注

# 解析要点:
# - P 行: 属性位置（CDS_LMAN_SYM_OUTLINE=外形, $LOCATION=位号, VALUE=值）
# - L 行: 引脚线坐标
# - C 行: 引脚编号标注位置
# - M 行: 内部图形线段
```

### 2.6 part.ptf 解析规则

```python
# part.ptf 结构（示例）
# FILE_TYPE = MULTI_PHYS_TABLE;
# PART 'CAPACITOR_0402'
# :PACKAGE_TYPE | VALUE | DESCRIPTION | JEDEC_TYPE | SN_NUM | BOM_SEQ | ...
# 'C0402' | '100NF' | '片式电容...' | '0402C-S' | 'M01.010024' | 'AA01' | ...

# 解析要点:
# - 分隔符为 '|' 的表格
# - PART 'NAME' → 器件逻辑名
# - 表格行 → 具体型号的属性（封装、值、描述、封装代码、料号、BOM码）
```

---

## 三、Cadence SPB 16.6 版本兼容性设计

### 3.1 16.6 版本特征（基于 .cpm 文件分析）

```ini
# 从实际 switch_practice.cpm 提取的 16.6 特征
cpm_version '16.6'

START_CONCEPTHDL
LOGIC_GRID_SIZE '0.05'
LOGIC_GRID_MULTIPLE '10'
SYMBOL_GRID_MULTIPLE '10'
DOC_GRID_SIZE '0.05'
DOC_GRID_MULTIPLE '10'
END_CONCEPTHDL

START_PKGRXL
feedback 'ALLEGRO'
regenerate_physical_net_name 'OFF'
electrical_constraints 'ON'
END_PKGRXL
```

### 3.2 多版本兼容策略

```
版本适配层 (VersionAdapter)
    ├── SPB16_6Adapter   ← 主目标版本
    ├── SPB17_2Adapter   ← 兼容版本
    └── SPB17_4Adapter   ← 兼容版本
```

> **规划状态（2026-08-07）**：VersionAdapter 为规划设计，当前代码中**未见独立实现**；实际以 SPB 16.6 为目标版本（兼容 17.2/17.4 的能力按上述基类-注册模式规划，待后续实现）。

**实现方式**：通过基类-注册模式：

```python
class VersionAdapter(ABC):
    """版本适配器基类"""
    
    @abstractmethod
    def grid_size(self) -> float: ...
    
    @abstractmethod
    def cpm_format(self) -> str: ...
    
    @abstractmethod
    def sch_header(self) -> str: ...
    
    @abstractmethod
    def supported_cdslib_syntax(self) -> list[str]: ...

class SPB16_6Adapter(VersionAdapter):
    VERSION = "16.6"
    
    def grid_size(self) -> float:
        return 0.05
    
    def cpm_format(self) -> str:
        return "16.6"
    
    def sch_header(self) -> str:
        return "VERSION 6"

# 注册
VersionRegistry.register(SPB16_6Adapter)
VersionRegistry.register(SPB17_2Adapter)
VersionRegistry.register(SPB17_4Adapter)
```

### 3.3 各版本差异点（需在生成时适配）

| 差异项 | 16.6 | 17.2 | 17.4 |
|--------|------|------|------|
| `.sch` 格式 | VERSION 6 | VERSION 6 | VERSION 6 |
| `.cpm` cpm_version | '16.6' | '17.2' | '17.4' |
| `cds.lib` 语法 | 一致 | 一致 | 一致 |
| 字体支持 | 矢量字体（默认）| TrueType 字体 | TrueType 字体 |
| 约束管理器 | 基础 | 增强 | 增强 |
| Design Sync 选项 | 基础 | 增加选项 | 增加选项 |
| Packager-XL 网表格式 | 一致 | 一致 | 一致 |

### 3.4 兼容性测试矩阵

| 生成目标版本 → | 16.6 | 17.2 | 17.4 |
|---------------|:---:|:---:|:---:|
| 在 16.6 中打开 | ✅ 目标 | ⚠️ 测试 | ⚠️ 测试 |
| 在 17.2 中打开 | ✅ 向上兼容 | ✅ 目标 | ⚠️ 测试 |
| 在 17.4 中打开 | ✅ 向上兼容 | ✅ 向上兼容 | ✅ 目标 |

**开发优先级**：
1. **P0**: 16.6 版本（目标版本，必须完美支持）
2. **P1**: 17.2 版本（主流企业版本）
3. **P2**: 17.4 版本（最新版本）

---

## 四、BOM_SEQ 编码规则（从规范文档提取）

### 4.1 编码结构

```
BOM_SEQ = 第1位(安装方式) + 第2位(器件类型) + 第3-4位(封装代码)
```

### 4.2 第1位：安装方式

| 代码 | 含义 |
|:----:|------|
| A | 贴片（SMD） |
| B | 插件（Through-hole） |
| C | 定位孔/过孔/测试点/金手指 |

### 4.3 第2位：器件类型

| 代码 | 器件类型 |
|:----:|---------|
| A | 电容 |
| B | 电阻 |
| C | 集成电路 |
| D | 晶体/晶振 |
| E | 二极管 |
| F | 三极管/MOS管 |
| G | 网络变压器/其他变压器 |
| H | 磁珠 |
| I | 电感 |
| J | LED灯 |
| K | 插针/插座 |
| L | RJ11 |
| M | RJ45 |
| N | BOM不出（如测试点） |

### 4.4 第3-4位：封装代码

| 代码 | 封装 |
|:----:|------|
| 00 | IC 或非常规封装 |
| 01 | 0201 / 0402 |
| 02 | 0603 |
| 03 | 0805 |
| 04 | 1206 |
| 05 | 1210 |
| 06 | 1808 |
| 07 | 1812 |
| 08 | 2010 |
| 09 | 2512 |
| 0X | 非常规封装 |

### 4.5 自动生成规则

```python
class BOMSEQGenerator:
    """根据器件属性自动生成 BOM_SEQ"""
    
    # 类型→类型代码
    TYPE_MAP = {
        'CAPACITOR': 'A', 'RESISTOR': 'B', 'IC': 'C',
        'CRYSTAL': 'D', 'OSCILLATOR': 'D',
        'DIODE': 'E', 'TRANSISTOR': 'F', 'MOSFET': 'F',
        'BEAD': 'H', 'FERRITE': 'H',
        'INDUCTOR': 'I', 'LED': 'J',
        'CONNECTOR': 'K', 'RJ11': 'L', 'RJ45': 'M',
    }
    
    # 封装→封装代码
    PACKAGE_MAP = {
        '0402': '01', '0603': '02', '0805': '03',
        '1206': '04', '1210': '05', '1808': '06',
        '1812': '07', '2010': '08', '2512': '09',
    }
    
    MOUNT_MAP = {'SMD': 'A', 'THT': 'B', 'MECHANICAL': 'C'}
    
    def generate(self, component: ComponentInfo) -> str:
        mount = self.MOUNT_MAP.get(component.mount_type, 'A')
        dtype = self.TYPE_MAP.get(component.category, 'C')
        package = self.PACKAGE_MAP.get(component.package, '00')
        return f"{mount}{dtype}{package}"
```

---

## 五、Cadence 兼容性经验速查

> 本章为 Cadence SPB 16.6 环境下的实测经验汇总，供生成器开发与排障参考。
> 内容提炼自人工验证操作记录（`docs/test1.txt`，操作 18/19）与参考实现比对报告（`docs/_comparison_report.md`，2026-08-03）。

### 5.1 UPREV 机制与 cpm_version

- **触发条件**：Cadence Project Manager 打开 `.cpm` 时检测到版本信息缺失/不匹配，触发 UPREV（项目升级）流程；若 `write.exe` 不在 PATH 中，升级会失败。
- **关键字段**：`.cpm` 必须包含 `cpm_version '16.6'`（位于 `START_GLOBAL`/`END_GLOBAL` 段之间）。
- **旧格式教训**：旧版 CPM 使用 `START_DESIGN`/`END_DESIGN` 格式且缺少 `cpm_version` 字段，Cadence 无法判断版本 → 触发 UPREV。当前生成器已统一输出 `START_GLOBAL` + `cpm_version '16.6'`。
- **绕过参数**：命令行参数 `-nonetlistuprev` 可绕过 UPREV 流程（用于调试/验证，不建议作为常规交付路径）。

### 5.2 SPCOCN 错误速查表

| SPCOCN 错误码 | 含义 | 常见根因 / 处置方向 |
|:---:|------|---------------------|
| 543 | SIG_NAME 引脚属性被删除 | 页面文件中手动定义 `$PN` 引脚属性，与 hdl_lib 定义不一致；不应手动生成 `$PN`/`LASTPIN`，交由 DEHDL 从器件库自动获取 |
| 542 | 默认属性相关 | 页面/器件默认属性处理；具体细节 [待填写] |
| 515 | cds.lib 缺少库定义 | `cds.lib` 中未 `DEFINE` 对应库或库路径无效；检查库路径是否有效 |
| 1908 | 括号不匹配 | 生成文件中括号配对错误；检查 S-expr/CSA 文件括号 |
| 1909 | Unknown word | 生成文件中出现 Cadence 无法识别的关键字；对照参考格式修正关键字 |
| 1910 | bad token | 词法错误、token 非法；检查文件编码与转义 |
| 1891 | syntax error | 语法错误（Cadence 16.6 不支持的写法）；检查生成文件语法 |

### 5.3 配置要点

- **PAGE_NAME_PROP**：`.cpm` 的 `START_CONCEPTHDL` 段需包含 `PAGE_NAME_PROP 'EDIT PAGE NAME'`，用于页面名属性定义。
- **CDS_EDITOR**：Cadence 环境变量，用于指定 Design Entry HDL 编辑器相关配置；具体取值以 Cadence 安装环境为准。
- **人工验证操作**：在 Cadence 电脑上执行 Project Manager → 导入设计 → 逐页检查符号/网络/引脚 → BOM 对比（详细步骤与核对表见 `docs/test1.txt` 操作 18/19）。

### 5.4 CSA 格式差异速查（当前实现 vs 参考实现）

> 基于 `docs/_comparison_report.md` 第 2 节（2026-08-03 比特级比对）；部分差异项已在后续修复中处理（详见 `docs/fix_proposal.md` 与 `docs/HDL_OUTPUT_FIX_PLAN.md`）。

| 对比项 | 参考实现 | 当前实现 | 判定 |
|--------|---------|---------|:---:|
| 文件头 | `FILE_TYPE = MACRO_DRAWING;` + `SET COLOR_*` 系列 | `csa_writer.py` 生成相同输出 | ✅ 完全一致 |
| C SIZE PAGE 边框 | `EDIT PAGE NAME` 硬编码 "DDR3" | 逐行相同 | ✅ 完全一致 |
| FORCEADD | `FORCEADD CAPACITOR..1` ... | `FORCEADD..{section}` 语义等价 | ✅ 等价 |
| VALUE 属性 ROTATION | `R 1` | 无 R 行 | ⚠️ 差异（规划支持） |
| VALUE 属性 JUSTIFICATION | `J 1` | `J 0` | ⚠️ 差异 |
| VALUE 属性偏移来源 | symbol.css（`get_prop_offsets()` 逐行解析） | 硬编码 `(x-5, y-50)` | ⚠️ 差异（规划接入 SymbolCSSParser） |
| CDS_LMAN_SYM_OUTLINE | 按器件（电容 `-50,0,50,-25`；电阻 `-50,25,50,-25`） | 硬编码 `-50,0,50,-25`（统一用电容值） | ⚠️ BUG |
