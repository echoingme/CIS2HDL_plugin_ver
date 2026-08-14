# CIS2HDL 文件完整性校验与诊断系统设计

> 版本: v1.1.0 | 日期: 2026-08-07 | 状态: 生效
> 基于对现有设计文档的全面审查 — 发现错误处理/文件校验/用户反馈机制存在重大设计空白
> 规划落地: 规划模块已全部落地（2026-08-07 核实：diagnostics/ 14 个模块存在）

---

## 0. 现状审查结论

### 0.1 已有能力

| 能力 | 位置 | 状态 |
|------|------|:--:|
| Python 异常层次定义 | CODING_STANDARDS §5.1 | 📄 设计稿 |
| Validator Layer 框架 | SYSTEM_ARCHITECTURE §2.3 | 📄 设计稿（Phase II） |
| EDIF↔DSN 交叉验证器 | BACKEND_DESIGN §3.0b / 已实现 | ✅ 代码 |
| BinaryReader 边界检查 | dsn/binary_reader.py | ✅ 代码 |
| FutureDataList 检查点 | dsn/structures.py | ✅ 代码 |
| Pydantic 自动类型验证 | IR 模型层 | ✅ 代码 |
| UI 颜色语义（红/橘/金） | UI_DESIGN_SPEC §2 | 📄 设计稿 |

### 0.2 关键空白（对标 Cadence Allegro 专业工具）

| 空白领域 | 严重程度 | Cadence 对标功能 | 当前缺失 |
|----------|:--------:|-----------------|---------|
| **文件清单与完整性校验** | 🔴 CRITICAL | `Project Manager → Check References` | 完全缺失：不告知用户缺了什么文件 |
| **多文件依赖解析** | 🔴 CRITICAL | DSN 内部引用 OLB 库的自动查找 | `.dsn` 内部引用的 `.olb` 文件路径未知 |
| **分文件逐项读取报告** | 🔴 CRITICAL | Packager-XL 的逐文件状态 | 无结构化读取状态报告 |
| **解析失败诊断与引导** | 🔴 CRITICAL | Canvas 44 错误码体系 | 无用户友好的错误分类和修复建议 |
| **降级转换路径** | 🟠 MAJOR | Cadence `Partial Design` 模式 | 无可选文件列表或降级策略 |
| **前置条件检查器** | 🟠 MAJOR | DRC 规则预检查 | 无法在转换前告知用户问题 |
| **增量恢复与断点续转** | 🟡 MINOR | SDM 版本管理 | 无中间结果保存机制 |
| **转换报告（结构化）** | 🟡 MINOR | Packager-XL Report | 仅有基础日志，无结构化报告 |

> **核心结论**：当前程序只能处理"完美输入"，对不完整输入、损坏数据、引用缺失等现实场景完全没有应对设计。

---

## 1. CIS 项目文件完整清单

### 1.1 CIS 项目标准文件结构

一个完整的 OrCAD Capture CIS 项目由以下文件组成：

```
MyProject/
├── MyProject.opj              ← 项目配置文件（文本）
├── MyProject.dsn              ← 原理图主文件（CFB 二进制容器）★
├── MyProject.dsn.lck          ← 文件锁（OrCAD 打开时存在）
├── MyProject-DBK/             ← 自动备份目录
│   ├── MyProject.dbk          ← DSN 备份×1（前一次保存）
│   ├── MyProject.dbk.001      ← DSN 备份×2
│   └── ...
├── Library/                   ← 本项目的器件库
│   ├── MyLib.olb              ← 自定义器件库（CFB 二进制）
│   └── CAPSYM.olb             ← 系统符号库引用（电源/端口符号）
├── Simulation/                ← 仿真配置（PSpice）
│   ├── PROFILE.sim
│   ├── PROFILE.prp
│   └── ...
└── Outputs/                   ← 网表/报告输出目录
    ├── MyProject.edf          ← EDIF 导出（文本）
    └── allegro/               ← PCB 网表
        ├── pstxnet.dat        ← 网络连接网表
        ├── pstxprt.dat        ← 器件-封装网表
        └── pstchip.dat        ← 器件引脚网表
```

### 1.2 DSN 文件内部结构（CFB 容器）

`.dsn` 是 MS-CFB 复合容器，内部包含多个流：

```
MyProject.dsn (CFB Container)
├── Root Entry
├── Views/
│   └── SCHEMATIC1/             ← 原理图视图
│       └── Pages/              ← 页面流目录
│           ├── PAGE1           ← 第1页（Type=10 页面结构体流）
│           ├── PAGE2           ← 第2页
│           └── PAGE3           ← 第3页
├── Cache/                      ← 设计缓存（器件定义）
│   ├── Package1                ← 器件封装（Type=31）
│   ├── Package2
│   └── ...
├── Library/                    ← 字符串表
│   └── strLst                  ← 全局字符串索引表
├── Hierarchy/                  ← 层次结构信息
│   └── Hierarchy               ← 层次树定义
└── Metadata                    ← 元数据
    ├── DesignProperties        ← 设计属性
    └── Annotation              ← 位号分配信息
```

### 1.3 ⚠️ DSN 内部对 OLB 文件的隐含依赖

`.dsn` 内部的 `PlacedInstance.source_package` 和 `Package.name` 字段引用了器件库（`.olb`）中的器件定义。转换需要知道：

| 依赖类型 | 引用来源 | 如何满足 |
|----------|---------|---------|
| **器件符号定义** | `PlacedInstance.pkgName` → `.olb` 中的 Package | 提供对应的 `.olb` 文件 |
| **器件引脚映射** | `PlacedInstance.t0x10.pinIndex` → Device.pinMap | `.olb` 的 Cache 流 |
| **属性默认值** | CachedLibraryPart.defaultVal | `.olb` 的 Library 流 |
| **标准符号** | CAPSYM.olb（VCC/GND/Port 符号） | Cadence 安装目录自带 |

**如果 `.olb` 缺失**，器件将有：
- ✅ 位号（reference）
- ✅ 放置坐标（locX/Y）
- ✅ 引脚连接（T0x10.netId）
- ❌ 引脚名称（pinNames 缺失）
- ❌ 符号图形（symbol graphics 缺失）
- ❌ 属性默认值（value/footprint 可能为空）

### 1.4 完整文件依赖分析表

| 文件 | 格式 | 提供信息 | 必需性 | 缺失后果 |
|------|:--:|---------|:------:|---------|
| **P0 核心必选** |
| `*.dsn` | 二进制 CFB | 全部逻辑 + 坐标 + 属性 | 🔴 **强制** | 无法进行任何转换 |
| **P1 强烈建议** |
| `*.opj` | 文本 INI | 项目配置、库路径、页面尺寸 | 🟠 **建议** | 使用默认配置；可能丢失库路径引用 |
| `*.olb` (项目库) | 二进制 CFB | 器件符号、引脚名、属性 | 🟠 **建议** | 器件无引脚名/符号/默认值（见 1.3） |
| `CAPSYM.olb` | 二进制 CFB | 电源/地/Port 等系统符号 | 🟠 **建议** | 可用默认符号替代；可能缺失 Port 方向 |
| **P2 可选增强** |
| `*.edf` | 文本 S-expr | 完整逻辑验证基线 | 🟡 **可选** | EDIF↔DSN 交叉验证不可用（不影响转换） |
| `*.dbk` / `*.dbk.001` | 二进制 CFB | 备份版 dsn（结构完全相同） | 🟡 **可选** | DSN 损坏时的恢复备选 |
| `pstxnet.dat` | 文本 | 网络连接的第三方验证 | 🟡 **可选** | 额外验证不可用 |
| `pstxprt.dat` | 文本 | 器件-封装映射验证 | 🟡 **可选** | 额外验证不可用 |
| `pstchip.dat` | 文本 | 引脚定义验证 | 🟡 **可选** | 额外验证不可用 |
| **P3 增强可选（仿真/制造）** |
| `*.sim` | 键值对 | 仿真配置 | ⚪ **高级** | 无损基本转换 |
| `*.cir` | SPICE 文本 | 仿真激励文件 | ⚪ **高级** | 无损基本转换 |
| `*.net` | SPICE 文本 | 仿真网表 | ⚪ **高级** | 无损基本转换 |
| `*.bom` / `.xlsx` | 文本/XLSX | BOM 材料清单 | ⚪ **高级** | 从 DSN 重新提取 |

---

## 2. 文件校验与诊断系统设计

### 2.1 系统架构：三层诊断管道

对标 Cadence 的 `Project Manager → Check References → DRC` 三层验证：

```
用户输入文件集
      ↓
┌──────────────────────────────────────────────────────────────┐
│ Layer 1: File Integrity Check (文件完整性校验)               │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│ │ 文件存在  │ │ 格式验证  │ │ 版本检测  │                     │
│ │ 性检查   │ │ (魔数/头) │ │ (CFB版)   │                     │
│ └──────────┘ └──────────┘ └──────────┘                     │
│     ↓              ↓           ↓                            │
│  FILE_MISSING   BAD_FORMAT  VERSION_MISMATCH                │
└────────────────────┬─────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────────┐
│ Layer 2: Dependency Resolution & Cross-Reference Check       │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│ │ OLB引用  │ │ 层次引用  │ │ 跨页引用  │ │ 全局网络  │        │
│ │ 解析     │ │ 解析     │ │ 解析     │ │ 解析     │        │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
│     ↓              ↓           ↓           ↓                │
│  MISSING_OLB  BROKEN_HIER  DANGLING_OFFPAGE  UNCONNECTED    │
└────────────────────┬─────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────────┐
│ Layer 3: Data Completeness Report (数据完整度评估)           │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│ │ 逻辑数据  │ │ 坐标数据  │ │ 属性数据  │ │ 图形数据  │        │
│ │ 完整度   │ │ 完整度   │ │ 完整度   │ │ 完整度   │        │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
│     ↓              ↓           ↓           ↓                │
│  百分比评分      百分比评分   百分比评分    百分比评分         │
└────────────────────┬─────────────────────────────────────────┘
                     ↓
            ┌────────────────┐
            │ Conversion     │
            │ Readiness       │  ← 综合评分 + 建议
            │ Assessment     │
            └────────────────┘
```

### 2.2 新增模块设计

#### 2.2.1 `FileInventory` — 文件清单与状态追踪

```python
@dataclass
class FileStatus:
    """单个文件的解析状态。"""
    path: Path
    file_type: str               # "DSN", "OLB", "OPJ", "EDF", "DBK", "PSTXNET", "PSTXPRT", "PSTCHIP", "SIM", "CIR"
    status: FileState            # FOUND / MISSING / CORRUPTED / PARTIAL / UNSUPPORTED_VERSION
    size: int = 0
    summary: str = ""            # 人可读摘要
    error_detail: str = ""       # 失败原因
    data_quality: float = 0.0    # 0.0-1.0 数据质量评分

@dataclass
class ProjectInventory:
    """CIS 项目文件清单。"""
    project_root: Path
    files: dict[str, FileStatus]  # key = relative path
    dsn_internal: DSNInternalInventory  # DSN 内部引用清单
    missing_olbs: list[str]         # 引用但缺失的 OLB 名称
    missing_hdl_equivalents: list[str]  # 转换所需但缺失的 HDL 对应物
```

#### 2.2.2 `DSNInternalInventory` — DSN 内部引用清单

```python
@dataclass
class DSNInternalInventory:
    """DSN 内部流结构和引用清单。"""
    streams_found: dict[str, bool]   # Root/Views/Pages/Cache/Library/Hierarchy→是否成功读取
    pages_parsed: int                # 成功解析的页面数
    total_pages: int                 # 总页面数
    instances_parsed: int            # 成功解析的器件实例数
    total_instances: int             # 总器件实例数
    olb_references: list[str]        # 引用的 OLB 名称列表
    referenced_packages: dict[str, tuple[str, int]]  # package→(OLB名, 实例数)
    strlst_entries: int              # 字符串表条目数
    cache_entries: int               # 缓存中的 Package 数
```

#### 2.2.3 `ConversionReadinessEvaluator` — 转换就绪度评估器

```python
class ConversionReadinessEvaluator:
    """综合评估当前文件集是否足以进行转换。"""
    
    def evaluate(self, inventory: ProjectInventory) -> ReadinessReport:
        """返回结构化评估报告。
        
        评估维度：
        - 逻辑完整性：器件/引脚/网络是否完整可读
        - 坐标可用性：器件位置/连线路径是否可用
        - 器件可匹配性：引脚名/属性是否足以匹配到 HDL 库
        - 符号可生成性：是否有足够信息生成 HDL 符号
        """
    
    def suggest_next_steps(self, report: ReadinessReport) -> list[ActionItem]:
        """根据评估结果生成用户操作建议。
        
        示例：
        - "缺少器件库文件 CAP01631.olb，请上传该文件以获取引脚名称和器件属性"
        - "已解析 14/14 个器件，但 3 个缺少引脚名。请提供对应的 .olb 文件"
        - "当前文件集可完成基本转换（逻辑正确但器件符号使用默认样式）"
        - "已满足完整转换条件，可以开始转换"
        """
```

#### 2.2.4 `FileRecoveryStrategy` — 文件损坏恢复策略

```python
class FileRecoveryStrategy:
    """当核心文件损坏时的恢复策略。"""
    
    AVAILABLE_STRATEGIES = {
        "DSN_CORRUPTED": [
            ("USE_BACKUP", "从 .dbk 备份文件恢复"),
            ("USE_EDIF_FALLBACK", "使用 .edf 文件完成逻辑转换（坐标将丢失）"),
            ("PARTIAL_PARSE", "尝试跳过损坏页面解析其余内容"),
            ("ATTEMPT_REPAIR", "尝试修复损坏的 CFB 扇区"),
        ],
        "OLB_MISSING": [
            ("USE_CACHE_EMBEDDED", "使用 DSN 内部 Cache 中的器件定义（可能不完整）"),
            ("USE_DEFAULT_SYMBOL", "使用默认矩形符号替代缺失符号"),
            ("SKIP_WITH_WARNING", "跳过该器件并列出缺失项"),
        ],
    }
```

---

## 3. 用户交互流程设计

### 3.1 文件导入阶段的诊断面板

```
┌──────────────────────────────────────────────────────────────┐
│  📁 项目文件状态                                              │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ✅ DSN 文件              MyProject.dsn          3页 42器件   │
│  ✅ EDIF 文件             MyProject.edf          42器件       │
│  ❌ 器件库 1              CAP01631.olb           未找到       │
│  ⚠️  器件库 2              Discrete.olb           解析警告     │
│  ℹ️  PCB 网表              pstxnet.dat            未提供       │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 📊 数据完整度：逻辑 92%  |  坐标 100%  |  属性 67%    │ │
│  │                                                          │ │
│  │ 🔴 缺失: CAP01631.olb — 3 个器件将无引脚名称              │ │
│  │ 🟡 可选: pstxnet.dat — 可用于交叉验证网络连接             │ │
│  │                                                          │ │
│  │ [上传缺失文件]  [忽略并继续]  [查看详情]                   │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  📋 建议操作：                                                │
│  ─────────────────────────────────────────────────────        │
│  1. 上传 CAP01631.olb 获取引脚名称和器件属性                  │
│  2. (可选) 上传 pstxnet.dat 启用交叉验证                      │
│                                                               │
│  [开始转换]  [仅逻辑转换（无符号）]  [取消]                    │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 转换后报告面板

```
┌──────────────────────────────────────────────────────────────┐
│  📊 转换报告 — MyProject (2026-07-30 14:30)                  │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ╔══════════════════════════════════════════════════════════╗ │
│  ║  ✅ 转换完成  ║  ✅ 42/42 器件   ║  ⚠️  3 警告    ║     ║ │
│  ╚══════════════════════════════════════════════════════════╝ │
│                                                               │
│  ┌─ 页面 ───────────────────────────────────────────────────┐ │
│  │ ✅ PAGE1 (02_Power)         12 器件, 8 网络              │ │
│  │ ✅ PAGE2 (03_RTL8367RB)      18 器件, 24 网络             │ │
│  │ ✅ PAGE3 (04_MDI)            12 器件, 15 网络             │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─ 匹配结果 ───────────────────────────────────────────────┐ │
│  │ ✅ R1  (RES_10K)         → standard/resistor       1.00  │ │
│  │ ✅ C5  (CAP_100nF)       → standard/capacitor      1.00  │ │
│  │ ⚠️  U3  (LM358)          → manual confirmation     0.65  │ │
│  │ ❌ U7  (CAP01631)        → NO MATCH FOUND                │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─ 警告详情 ───────────────────────────────────────────────┐ │
│  │ ⚠️  U3 (LM358): 引脚名不匹配，需人工确认                  │ │
│  │ ⚠️  CAP01631.olb 缺失: U7 使用默认通用符号                 │ │
│  │ ⚠️  NET_003: 网络名含非法字符，已自动清洗为 NET_003_X     │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─ 生成文件 ───────────────────────────────────────────────┐ │
│  │ ✅ MyProject.cpm             ✅ cds.lib                  │ │
│  │ ✅ top.sch.1.1               ✅ top.sch.1.2              │ │
│  │ ✅ top.sch.1.3               ⚠️  sym/ (3个默认符号)      │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  📋 后续建议：                                                │
│  ─────────────────────────────────────────────────────        │
│  1. 确认 U3 (LM358) 的引脚映射                                │
│  2. 提供 CAP01631.olb 替换 U7 的默认符号                      │
│  3. 运行 Packager-XL 验证生成的设计                           │
│                                                               │
│  [导出报告 HTML]  [导出报告 PDF]  [打开输出目录]               │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

> **注**：以上交互原型为 `.sch.*` 时代的设计快照（历史快照，现输出为 CSA 原生格式 `.csa`，2026-08-07 核实）。

---

## 4. 与 Cadence 专业工具的功能对比

### 4.1 对标分析

| Cadence 功能 | 功能描述 | 本项目状态 | 优先级 | 对应模块 |
|-------------|---------|:--:|:------:|---------|
| **Project Manager → Check References** | 检查设计引用的所有文件是否存在 | ❌ 缺失 | 🔴 P0 | `FileInventory` |
| **Packager-XL Pre-check** | 打包前检查所有器件/引脚/网络的完整性 | ❌ 缺失 | 🔴 P0 | `ConversionReadinessEvaluator` |
| **DRC (Design Rule Check)** | 7 种规则检查（已在 ORCAD_SOURCE §11.4 记录） | 📄 设计稿 | 🟠 P1 | `validator/` 层 |
| **Canvas 44 错误码** | 明确的错误码和修复建议 | ❌ 缺失 | 🟠 P1 | `ErrorDiagnosisEngine` |
| **Export Physical 验证** | 导出网表并验证 | 📄 设计稿 | 🟡 P2 | `pstxnet.dat` 验证 |
| **SDM 版本管理** | 设计生命周期管理 | ❌ 缺失 | 🟡 P2 | — |
| **Partial Design Mode** | 允许部分设计打开/编辑 | ❌ 缺失 | 🟡 P2 | `FileRecoveryStrategy` |
| **Backup/AutoSave** | .dbk 自动备份 | 仅读取 | ⚪ P3 | — |
| **Constraint Manager** | 约束规则管理 | ❌ 不适用 | — | — |

### 4.2 当前设计文档中缺失的顶层能力

| 缺失能力 | 说明 | 影响 |
|---------|------|------|
| **文件清单与状态追踪** | 没有中心化的文件状态管理系统 | 用户不知道哪些文件可用、哪些缺失 |
| **结构化错误报告** | 仅有日志，无结构化报告 | 无法程序化地分析转换质量 |
| **用户引导系统** | 无"下一步操作建议" | 用户遇到问题后只能自己排查 |
| **降级转换路径** | 不支持"部分数据可用时尽可能转换" | 一个文件缺失就完全无法工作 |
| **数据质量量化** | 无百分比/评分体系 | 无法量化"当前能转多少" |
| **可选文件利用** | 未设计可选数据的利用管道 | `.dbk`/pstx*/`.cir` 等未被利用 |
| **多语言编码处理** | 字符串表可能含 GBK/Shift-JIS | 属性值可能乱码 |
| **CFB 版本兼容** | 仅支持单一 CFB 版本 | 不同 OrCAD 版本的 DSN 可能不兼容 |
| **增量转换** | 不支持"已转换3/5页，继续" | 大工程转换中断后需重来 |
| **配置校验** | Config 单例未经校验 | 路径错误/格式不合法时无提示 |

---

## 5. 推荐新增模块开发计划

### 5.1 Phase I-B 追加（当前阶段立即补充）

| 模块 | 文件 | 描述 | 估算 |
|------|------|------|:--:|
| `FileInventory` | `core/diagnostics/file_inventory.py` | 文件清单与状态追踪 | ~200 行 |
| `DSNInternalInventory` | `core/diagnostics/dsn_inventory.py` | DSN 内部引用清单提取 | ~150 行 |
| `DiagnosticReport` | `core/diagnostics/diagnostic_report.py` | 结构化诊断报告数据模型 | ~100 行 |

### 5.2 Phase II 追加

| 模块 | 文件 | 描述 | 估算 |
|------|------|------|:--:|
| `ConversionReadinessEvaluator` | `core/diagnostics/readiness.py` | 转换就绪度综合评分 | ~250 行 |
| `FileRecoveryStrategy` | `core/diagnostics/recovery.py` | 损坏/缺失文件的降级策略 | ~200 行 |
| `ErrorDiagnosisEngine` | `core/diagnostics/error_diagnosis.py` | 44 错误码体系 + 修复建议 | ~300 行 |
| `StructuredReportGenerator` | `core/diagnostics/report_gen.py` | HTML/JSON 结构化报告输出 | ~200 行 |
| GUI 诊断面板 | `gui/panels/diagnostic_panel.py` | 文件状态树 + 质量评分条 + 操作建议 | ~400 行 |
| GUI 转换报告面板 | `gui/panels/report_panel.py` | 彩色状态 + 折叠详情 + 导出 | ~350 行 |

### 5.3 总计新增工作量

| 阶段 | 后端 | 前端 | 合计 |
|------|:---:|:---:|:---:|
| Phase I-B 追加 | ~450 行 | — | ~450 行 |
| Phase II 追加 | ~950 行 | ~750 行 | ~1,700 行 |
| **合计** | **~1,400 行** | **~750 行** | **~2,150 行** |

---

## 6. 可选的增强文件清单（完整）

### 6.1 可选但可增强转换质量的文件

| 文件 | 格式 | 提供能力 | 增强效果 |
|------|:--:|---------|---------|
| `*.dbk` / `*.dbk.001` | 二进制 CFB | DSN 备份（结构完全相同） | 🛡️ **容错**：DSN 损坏时自动恢复 |
| `*.edf` | 文本 S-expr | 完整逻辑数据 | 🔍 **交叉验证**：自动比对 EDIF↔DSN 一致性 |
| `pstxnet.dat` | 文本 | 网络连接关系 | ✅ **验证**：第三方格式确认连接正确性 |
| `pstxprt.dat` | 文本 | 器件-封装映射 | ✅ **验证**：验证 PCB 封装引用 |
| `pstchip.dat` | 文本 | 引脚定义 | ✅ **验证**：验证引脚编号/名称 |
| `*.bom` / `*.xlsx` | 文本/XLSX | BOM 材料清单 | 📋 **增强**：保留原始 BOM 格式 |
| `*.olb` (标准库) | 二进制 CFB | 标准符号定义 | 🎨 **符号增强**：使用原始符号图形 |
| `*.sim` | 键值对文本 | 仿真配置 | ⚡ **仿真**：保留仿真设置 |
| `*.cir` | SPICE 文本 | 仿真激励 | ⚡ **仿真**：保留仿真电路 |
| `*.prp` | S-expr 文本 | 属性映射 | 📋 **属性完善**：保留 PSpice 属性映射 |

### 6.2 转换输出可选增强

| 可选输出 | 用途 | 需额外输入 |
|---------|------|-----------|
| `*.sym` 符号文件 | 生成自定义符号 | `.olb` 文件或手动定义 |
| `*.ptf` 属性表 | 多封装器件配置 | `.olb` 或公司库规范 |
| `*.bom` BOM 文件 | 材料清单 | `.bom` 模板或公司 BOM 规范 |
| `*.vhd` / `*.v` | FPGA 仿真存根 | 器件引脚定义完整时 |
| `report.html` | 转换报告 | 所有输入文件 |

---

## 7. 自检清单

- [x] 完成现状审查：识别 8 个关键空白（0.2 节）
- [x] CIS 项目文件完整清单（1 节）
- [x] DSN 内部结构与隐含依赖分析（1.2-1.3 节）
- [x] 必需/建议/可选文件分级表（1.4 节）
- [x] 三层诊断管道架构设计（2.1 节）
- [x] 新增模块接口定义（2.2 节）
- [x] 用户交互流程设计（3 节：导入诊断面板 + 转换报告面板）
- [x] 与 Cadence 专业工具的对标分析（4 节：9 项对标 + 10 项缺失）
- [x] 新增模块开发计划与工作量估算（5 节）
- [x] 完整可选文件增强清单（6 节）
