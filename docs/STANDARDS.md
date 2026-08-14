# STANDARDS（开发规范与标准总文档）

> **文档类型**：规范与标准总文档（内容保全式合并）
> **权威版本口径**：v1.1.0（2026-08-07；各源文档自身版本号保留于原文）
> **测试基线**：268 passed / 23 skipped / 0 failed（291 collected）
> **错误码**：44 条（31/39 为历史口径）
> **匹配架构**：v2.0 ｜ **输出格式**：CSA 原生格式（.csa）｜ **GUI 框架**：PySide6
> **合并日期**：2026-08-07

---

## 合并说明

### 合并来源与原则

本文档由 **3 份规范类源文档** 内容保全式合并而成，统一承载 CIS2HDL 项目的开发规范、开发流程 SOP 与 HDL/原理图输出标准。

**合并原则（内容保全式，用户已确认）**：

- 源文档**章节逐节保留**（含表格、代码块、附录、注记），仅调整标题层级：原 H1 由 Part 标题承载，原 H2/H3/H4 逐级降一级；
- **不改写原文句子**，仅更新跨文档交叉引用（指向已合并/归档文档的引用改为新位置）；
- 重复/交叠内容保留原文，并加「合并注记」标注；
- 源文档只读，不修改、不删除；合并后由主理人统一归档管理。

**权威口径（合并时统一）**：版本 v1.1.0；测试 268/23（291）；错误码 44（31/39 为历史口径）；匹配 v2.0；PAINT WIRE 已移除；输出以 CSA 原生格式（`.csa`）为准；GUI PySide6；目录结构实测（包在 `cis2hdl/` 非 `src/`，无 version/layout/cli/generator 目录，CLI 走 `__main__.py`）。

### 章节映射表

#### 三源文档 → 合并 Part（总表）

| 来源文档（docs/） | 行数 | 合并位置 | 关键内容 |
|---|---|---|---|
| `CODING_STANDARDS.md` | 586 | **Part I 编码规范** | 44 错误码分配表、异常层次、基类-注册模式、UI Token 铁律 |
| `DEVELOPMENT_SOP.md` | 403 | **Part II 开发流程 SOP** | 四文件版本同步检查单、CHANGELOG 补录纪律 |
| `HDL_SCHEMATIC_STANDARDS.md` | 443 | **Part III 原理图与 HDL 输出规范** | Cadence 兼容性经验速查、BOM_SEQ 规则 |

#### 章节级映射（源 H1/H2 → 合并后标题）

**Part I 编码规范（原 CODING_STANDARDS.md）**

| 源章节（H1/H2） | 合并后标题 |
|---|---|
| H1 CIS2HDL 开发规范 | Part I 标题（含原版本说明） |
| H2 1. 总则 | ### 1. 总则 |
| H2 2. 命名规范 | ### 2. 命名规范 |
| H2 3. 代码风格 | ### 3. 代码风格 |
| H2 4. 基类-注册模式 | ### 4. 基类-注册模式 |
| H2 5. 错误处理规范 | ### 5. 错误处理规范 |
| H2 6. 日志规范 | ### 6. 日志规范 |
| H2 7. 测试规范 | ### 7. 测试规范 |
| H2 8. 总体结构框架设计规范 | ### 8. 总体结构框架设计规范 |

**Part II 开发流程 SOP（原 DEVELOPMENT_SOP.md）**

| 源章节（H1/H2） | 合并后标题 |
|---|---|
| H1 CIS2HDL 软件开发 SOP（标准操作流程） | Part II 标题（含原版本说明） |
| H2 1. 总则 | ### 1. 总则 |
| H2 2. 开发流程 | ### 2. 开发流程 |
| H2 3. Bug 修复流程 | ### 3. Bug 修复流程 |
| H2 4. 代码审查会议 | ### 4. 代码审查会议 |
| H2 5. 版本发布流程 | ### 5. 版本发布流程 |
| H2 6. 紧急修复流程（Hotfix） | ### 6. 紧急修复流程（Hotfix） |
| H2 7. 文档维护规则 | ### 7. 文档维护规则 |
| H2 8. 环境与工具链 | ### 8. 环境与工具链 |
| H2 9. 问题升级路径 | ### 9. 问题升级路径 |

**Part III 原理图与 HDL 输出规范（原 HDL_SCHEMATIC_STANDARDS.md）**

| 源章节（H1/H2） | 合并后标题 |
|---|---|
| H1 HDL 原理图排版美观自动化分析与版本兼容性规范 | Part III 标题（含原版本说明） |
| H2 一、原理图排版美观：软件可实现 vs 人工调整 | ### 一、原理图排版美观：软件可实现 vs 人工调整 |
| H2 二、HDL 器件库自动导入规范 | ### 二、HDL 器件库自动导入规范 |
| H2 三、Cadence SPB 16.6 版本兼容性设计 | ### 三、Cadence SPB 16.6 版本兼容性设计 |
| H2 四、BOM_SEQ 编码规则（从规范文档提取） | ### 四、BOM_SEQ 编码规则（从规范文档提取） |
| H2 五、Cadence 兼容性经验速查 | ### 五、Cadence 兼容性经验速查 |

> **合并注记**：原 `specs/` 下的三份规范文件（CODING_STANDARDS / DEVELOPMENT_SOP / HDL_SCHEMATIC_STANDARDS）内容已统一并入本文档 Part I / II / III；如 `specs/*.md` 仍保留其他规范文件，其更新纪律以原文（Part II §7 文档维护规则）为准。

### 交叉引用更新说明

| 原文引用（位置） | 更新后指向 |
|---|---|
| CODING_STANDARDS §8.1「见 BACKEND_DESIGN §5」 | 详见 **ARCHITECTURE.md Part II**（原 BACKEND_DESIGN）§5 |
| CODING_STANDARDS §8.4「遵循 `specs/UI_DESIGN_SPEC.md`」 | 遵循 **ARCHITECTURE.md Part V**（原 `specs/UI_DESIGN_SPEC.md`） |
| DEVELOPMENT_SOP Step 3「遵循 `specs/CODING_STANDARDS.md`」 | 遵循 **本 STANDARDS.md Part I**（原 `specs/CODING_STANDARDS.md`） |
| DEVELOPMENT_SOP PR 模板「遵循 CODING_STANDARDS.md」 | 遵循 **STANDARDS.md Part I**（原 CODING_STANDARDS.md） |
| 「见 DIAGNOSTICS_AND_RECOVERY」类引用（诊断体系） | 详见 **ARCHITECTURE.md Part IV**（诊断体系） |
| 「见 HDL_SCHEMATIC_STANDARDS」类引用 | 见 **本 STANDARDS.md Part III** |

> **注**：诊断体系、后端详设、GUI 设计等原独立文档已并入 `ARCHITECTURE.md`（Part I 架构总览 / Part II 后端详设 / Part III 器件模型 / Part IV 诊断体系 / Part V GUI 设计）；匹配系统并入 `MATCHING.md`。历史验证记录引用（`docs/test1.txt`、`docs/_comparison_report.md`、`docs/fix_proposal.md`、`docs/HDL_OUTPUT_FIX_PLAN.md`）属历史源证，保留原文未改。

---
## Part I 编码规范（原 CODING_STANDARDS.md · CIS2HDL 开发规范）

> **来源**：`docs/CODING_STANDARDS.md`（586 行，版本 v1.2）。本 Part 原文逐节保全，仅调标题层级；跨文档引用已更新（见文首合并说明 §3）。
>
> **合并注记**：原 `specs/CODING_STANDARDS.md` 内容已并入本文档 Part I；文内「见 BACKEND_DESIGN」→「详见 ARCHITECTURE.md Part II」，「遵循 specs/UI_DESIGN_SPEC.md」→「遵循 ARCHITECTURE.md Part V」。

---

> 版本: v1.2 | 日期: 2026-07-30 | 状态: 生效（2026-07-30 起，v1.2） | 更新: 新增诊断器开发规范、44 错误码体系、用户引导式错误处理

---

### 1. 总则

#### 1.1 语言与工具

| 项目 | 选型 |
|------|------|
| 语言 | Python 3.12+ |
| 构建 | `pyproject.toml` (PEP 621) |
| 格式化 | `ruff format` |
| Lint | `ruff check` |
| 类型检查 | `mypy` (strict mode) |
| 测试 | `pytest` |
| 文档 | Google-style docstrings |
| 版本管理 | Git + 语义化版本 |

#### 1.2 理念

- **高内聚、低耦合**：每个模块只做一件事
- **基类-注册模式**：通过抽象基类（ABC）定义接口，注册表管理实现
- **switch-case 优先于 if-else**：对于多分支的平行模式/选项使用字典分发或 match-case
- **显式优于隐式**：不做魔法行为，所有转换参数显式传递
- **失败优于静默**：异常情况抛异常或记录日志，不静默吞掉错误
- **代码复用优先**：优先搜索现有函数/类是否可复用，避免重复造轮子
- **变量语义化**：变量名必须反映其业务含义，禁止 `x`, `tmp`, `data` 等无意义名称（循环变量除外）

#### 1.3 代码复用原则

| 原则 | 说明 | 示例 |
|------|------|------|
| **先搜索后编写** | 新增功能前，先在项目中搜索是否已有类似实现 | `grep "def parse" core/parser/` |
| **提取公共函数** | 两个以上模块使用相同逻辑 → 提取到 `utils/` | `strip_quotes()`, `normalize_net_name()` |
| **基类共享逻辑** | 多个子类有相同方法 → 提升到基类实现 | `ParserBase.validate_input()` |
| **组合优于继承** | 跨层级共享逻辑 → 使用 Mixin 或工具类 | `LoggingMixin`, `ConfigMixin` |
| **函数尽量复用调用** | 公开函数应设计为可被多处调用，避免硬编码 | `parse_chips_prt(path)` 而非在 Scanner 内硬编码 

---

### 2. 命名规范

#### 2.1 文件

```
小写下划线:  project_panel.py, dsn_parser.py, fuzzy_matcher.py
一个文件一个主类:  文件名 = 主类名转小写下划线
测试文件:  test_<模块名>.py
```

#### 2.2 类

```python
# 大驼峰（PascalCase）
class DSNParser(ParserBase): ...
class ExactMatcher(MatcherBase): ...
class ComponentInstanceIR(BaseModel): ...

# 抽象基类以 Base 结尾
class ParserBase(ABC): ...
class MatcherBase(ABC): ...

# 异常类以 Error 结尾
class ParseError(Exception): ...
class MatchError(Exception): ...
```

#### 2.3 函数与方法

```python
# 小写下划线（snake_case）
def parse_design(self, file_path: Path) -> DesignIR: ...
def compute_similarity(self, a: str, b: str) -> float: ...
def _extract_package_info(self, raw: bytes) -> dict: ...

# 私有方法以下划线开头
def _decode_cfb_stream(self, stream_name: str) -> bytes: ...
```

#### 2.4 变量

```python
# 小写下划线（snake_case）
component_count = len(design.components)
net_name = "VCC_3V3"

# 常量全大写
MAX_PAGE_COUNT = 500
DEFAULT_CONFIDENCE_THRESHOLD = 0.8

# 布尔变量用 is_ / has_ / should_ 前缀
is_matched: bool = False
has_power_pins: bool = True
should_retry: bool = False
```

#### 2.5 变量定义规范（强制执行）

| 规则 | 示例（✅ 正确） | 反例（❌ 禁止） |
|------|----------------|----------------|
| **语义化命名** | `unmatched_components: list[ComponentIR]` | `data`, `items`, `result` |
| **类型注解** | `confidence: float = 0.0` | `confidence = 0.0`（无注解） |
| **集合用复数** | `parsed_pages: list[PageIR]` | `parsed_page: list[PageIR]` |
| **字典用映射名** | `refdes_to_component: dict[str, ComponentIR]` | `d: dict`, `mapping: dict` |
| **临时变量有意义** | `extracted_value = re.match(...)` | `tmp`, `temp`, `x`, `foo` |
| **避免缩写歧义** | `component_instance` | `ci`, `comp_inst`（不熟悉的缩写） |

**允许的通用缩写**（团队共识）：

| 缩写 | 全称 | 使用场景 |
|------|------|---------|
| `ir` | Intermediate Representation | 数据模型变量 |
| `refdes` | Reference Designator | 位号变量 |
| `hdl` | Design Entry HDL | 目标格式相关 |
| `cis` | Capture CIS | 源格式相关 |
| `cfg` | Configuration | 配置对象 |
| `ctx` | Context | 上下文对象 |
| `db` | Database | 数据库对象 |

---

### 3. 代码风格

#### 3.1 分支控制：switch-case 优先

对于多个平行选项，使用**字典分发**或 **Python 3.10+ match-case** 替代长 if-elif 链。

```python
# ❌ 不推荐
def get_parser(file_ext: str) -> ParserBase:
    if file_ext == ".dsn":
        return DSNParser()
    elif file_ext == ".olb":
        return OLBParser()
    elif file_ext == ".dat":
        return NetlistParser()
    else:
        raise ValueError(f"Unsupported format: {file_ext}")

# ✅ 推荐：字典分发
PARSER_REGISTRY: dict[str, type[ParserBase]] = {
    ".dsn": DSNParser,
    ".olb": OLBParser,
    ".dat": NetlistParser,
}

def get_parser(file_ext: str) -> ParserBase:
    parser_cls = PARSER_REGISTRY.get(file_ext)
    if parser_cls is None:
        raise ValueError(f"Unsupported format: {file_ext}")
    return parser_cls()

# ✅ 推荐：Python 3.10+ match-case
def dispatch_match_stage(stage: MatchStage, source, candidates):
    match stage:
        case MatchStage.EXACT:
            return ExactMatcher().match(source, candidates)
        case MatchStage.FUZZY:
            return FuzzyNameMatcher().match(source, candidates)
        case MatchStage.FEATURE:
            return FeatureExtractMatcher().match(source, candidates)
        case MatchStage.MANUAL:
            return ManualMatchResolver().resolve(source, candidates)
        case _:
            raise ValueError(f"Unknown match stage: {stage}")
```

#### 3.2 函数定义规范

```python
def function_name(
    required_param: Type,
    optional_param: Type = default_value,
    *,
    keyword_only_param: Type,   # 强制关键字参数
) -> ReturnType:
    """简短的一句话描述。

    Args:
        required_param: 参数说明。
        optional_param: 参数说明，包含默认值信息。
        keyword_only_param: 参数说明。

    Returns:
        返回值的类型和含义。

    Raises:
        SomeError: 什么情况下会抛出此异常。
    """
    ...
```

**原则**：
- 函数不超过 50 行，超过则拆分
- 参数不超过 5 个，超过则封装为 dataclass/Pydantic model
- 一个函数只做一件事
- 优先使用关键字参数提高可读性

#### 3.3 类定义规范

```python
from abc import ABC, abstractmethod
from typing import ClassVar

class ParserBase(ABC):
    """解析器抽象基类。

    所有格式解析器必须继承此类并实现 parse() 方法。
    通过 ParserRegistry 自动注册。
    """

    # 类变量（子类覆盖）
    FORMAT_NAME: ClassVar[str] = ""
    FILE_EXTENSIONS: ClassVar[list[str]] = []

    @abstractmethod
    def parse(self, file_path: Path) -> DesignIR:
        """解析文件为中间表示。

        Args:
            file_path: 源文件路径。

        Returns:
            标准化的中间表示对象。

        Raises:
            ParseError: 解析失败时抛出。
        """
        ...

    def validate_input(self, file_path: Path) -> None:
        """基类提供的输入验证，子类可复用或覆盖。"""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if file_path.suffix not in self.FILE_EXTENSIONS:
            raise ValueError(
                f"Expected {self.FILE_EXTENSIONS}, got {file_path.suffix}"
            )
```

#### 3.4 模块关联原则

| 原则 | 说明 |
|------|------|
| **依赖方向** | IR ← Parser/Matcher/Validator/Generator（单向依赖） |
| **循环依赖零容忍** | 如出现循环依赖，提取公共接口到独立模块 |
| **只暴露公共 API** | `__all__` 或 `__init__.py` 明确导出内容 |
| **内部实现用 `_` 前缀** | 不在 `__init__.py` 中导出的模块和函数 |

---

### 4. 基类-注册模式

#### 4.1 设计模式

```
┌─────────────────────┐
│   BaseClass (ABC)   │  ← 定义接口契约
│   + abstractmethod  │
└──────────┬──────────┘
           │ 继承
    ┌──────┼──────┐
    ▼      ▼      ▼
  Impl1  Impl2  Impl3    ← 具体实现

         │
         ▼
┌─────────────────────┐
│   Registry (dict)   │  ← 注册表，key → class
│   + register()      │
│   + get()           │
│   + list_all()      │
└─────────────────────┘
```

#### 4.2 实现模板

```python
from abc import ABC, abstractmethod
from typing import ClassVar

# ---- Base Class ----

class MatcherBase(ABC):
    MATCHER_NAME: ClassVar[str] = ""
    MATCHER_PRIORITY: ClassVar[int] = 0   # 越小越优先

    @abstractmethod
    def match(self, source, candidates) -> MatchResult: ...

# ---- Registry ----

class MatcherRegistry:
    _matchers: dict[str, type[MatcherBase]] = {}

    @classmethod
    def register(cls, matcher_cls: type[MatcherBase]) -> None:
        name = matcher_cls.MATCHER_NAME
        if not name:
            raise ValueError(f"{matcher_cls.__name__} must define MATCHER_NAME")
        cls._matchers[name] = matcher_cls

    @classmethod
    def get(cls, name: str) -> type[MatcherBase]:
        return cls._matchers[name]

    @classmethod
    def list_all(cls) -> list[type[MatcherBase]]:
        return sorted(
            cls._matchers.values(),
            key=lambda c: c.MATCHER_PRIORITY,
        )

# ---- Concrete Implementation ----

class ExactMatcher(MatcherBase):
    MATCHER_NAME: ClassVar[str] = "exact"
    MATCHER_PRIORITY: ClassVar[int] = 1

    def match(self, source, candidates) -> MatchResult:
        ...

# ---- Auto-register ----
MatcherRegistry.register(ExactMatcher)
```

---

### 5. 错误处理规范

#### 5.1 异常层次

```
CIS2HDLError (base)
├── CIS2HDLParseError        ← 解析错误
├── CIS2HDLMatchError        ← 匹配错误
└── CIS2HDLConfigError       ← 配置错误

> **现状核实（2026-08-07，exceptions.py）**：以上为代码中的实际异常层次。早期设计稿中的细分子类（`DSNParseError`/`OLBParseError`、`NoMatchFoundError`/`AmbiguousMatchError`、`ValidationError`、`DiagnosticError`、`GenerationError` 等）**未在代码中落地**，异常统一收敛到上述三个子类；诊断模块按 5.1a 契约实现，不依赖细分子类。
```

#### 5.1a 诊断器开发规范（新增）

所有诊断模块必须遵循以下契约：

```python
class DiagnosticBase(ABC):
    """诊断器的抽象基类。"""
    
    @abstractmethod
    def diagnose(self, *args) -> DiagnosticReport:
        """执行诊断，返回结构化报告。
        
        关键原则：
        1. 永不抛出异常 — 所有错误都记录在报告中
        2. 每条诊断信息必须包含 suggestion（修复建议）
        3. 支持聚合 — 同类错误合并而非逐条列出
        """
        ...
    
    def aggregate_errors(self, errors: list[DiagnosisError]) -> list[DiagnosisError]:
        """合并同类错误。"""
        ...
```

**诊断数据模型规范**：

```python
from enum import IntEnum
from dataclasses import dataclass

class Severity(IntEnum):
    FATAL = 0    # 严重：无法继续，必须解决
    ERROR = 1    # 错误：当前操作失败，可能可恢复
    WARNING = 2  # 警告：可能影响质量，可忽略
    INFO = 3     # 信息：仅供参考

class ActionVerb(str, Enum):
    """用户操作动词 — 所有建议统一使用这些动词开头。"""
    PROVIDE = "请提供"           # 缺失文件
    REPAIR = "请修复"            # 损坏文件
    UPGRADE = "请升级"           # 版本不兼容
    UPLOAD = "请上传"            # 可选增强文件
    CONFIRM = "请确认"           # 需要人工裁决
    IGNORE = "可忽略"            # 允许跳过继续
    CHECK = "请检查"             # 需人工验证
    RERUN = "请重新运行"          # 需重新执行
```

**44 错误码分配表**：

| 码段 | 分类 | 示例 |
|:--:|------|------|
| 1-10 | 文件级 | 1=DSN缺失, 2=CFB损坏, 3=版本不兼容, 5=OLB缺失引用 |
| 11-20 | 解析级 | 11=前导码错, 12=结构体溢出, 15=strLst索引超界 |
| 21-30 | 语义级 | 21=引脚名缺失, 22=网络名非法, 25=层次引用断裂 |
| 31-40 | 生成级 | 31=符号生成失败, 32=文件写入失败, 35=磁盘空间不足 |
| 41-50 | 配置级 | 41=HDL库路径不存在, 42=输出目录不可写 |

> **注（2026-08-07 核实）**：上表为 1-50 五个码段的规划分配表；实际代码 `core/diagnostics/error_diagnosis.py` 的 `ERROR_CODES` 实注册 **44 条**：1-15、21-34、41-50、51-55（含 OLB 51-55）。历史口径 31（早期对标目标）与 39（漏算 OLB 51-55）均已被 44 取代。

#### 5.2 处理原则

```python
# ✅ 明确失败：抛出具体异常
def parse_dsn(self, path: Path) -> DesignIR:
    if not self._validate_header(data):
        raise CIS2HDLParseError(f"Invalid DSN header in {path}")
    ...

# ✅ 可恢复：记录警告，继续
def validate_net_name(self, name: str) -> str:
    if contains_illegal_chars(name):
        cleaned = self._clean_name(name)
        logger.warning(f"Net name '{name}' cleaned to '{cleaned}'")
        return cleaned
    return name

# ❌ 不推荐：静默失败
def parse_dsn(self, path: Path) -> DesignIR | None:
    try:
        ...
    except:
        return None  # 调用方不知道发生了什么
```

---

### 6. 日志规范

```python
# 使用标准 logging 模块
import logging
logger = logging.getLogger(__name__)

# 级别约定
logger.debug("DSN stream 0x04 decoded: 15 components found")  # 调试细节
logger.info("Parsing DSN: project.dsn (3 pages, 142 components)")  # 关键步骤
logger.warning("Pin VCC on U3 has no matching HDL pin")  # 可恢复问题
logger.error("Failed to write .sch file: permission denied")  # 阻塞性错误
logger.critical("Core engine initialization failed")  # 致命错误
```

---

### 7. 测试规范

> **合并注记**：开发流程侧的测试要求见 Part II §2 Step 4（原 DEVELOPMENT_SOP Step 4）；两侧测试规范互为补充。


#### 7.1 测试金字塔

```
        ┌──────┐
        │ E2E  │  少量端到端测试
       ┌┴──────┴┐
       │  Int.  │  模块集成测试
      ┌┴────────┴┐
      │   Unit   │  大量单元测试
      └──────────┘
```

#### 7.2 测试结构

```
tests/
├── conftest.py              # 共享 fixtures
├── fixtures/                # 测试数据
│   ├── simple.dsn           # 最简单的 CIS 工程
│   ├── with_bus.dsn         # 含总线的工程
│   └── multi_page.dsn       # 多页工程
├── unit/
│   ├── test_dsn_parser.py
│   ├── test_exact_matcher.py
│   ├── test_fuzzy_matcher.py
│   └── test_sch_writer.py
└── integration/
    ├── test_full_pipeline.py
    └── test_reimport.py     # 生成后能否被 HDL 识别
```

#### 7.3 测试命名

```python
def test_<功能>_<场景>_<期望结果>():
    ...

# 示例
def test_exact_matcher_same_footprint_returns_high_confidence():
    ...

def test_dsn_parser_empty_file_raises_parse_error():
    ...

def test_sch_writer_generates_valid_header():
    ...
```

---

### 8. 总体结构框架设计规范

#### 8.1 包结构原则

```
cis2hdl/
├── core/           # 核心引擎（纯逻辑，零 GUI 依赖）
│   ├── ir/         # 数据模型（Pydantic BaseModel）
│   ├── parser/     # 解析层（基类 + 注册表 + 实现）
│   ├── matcher/    # 匹配层
│   ├── validator/  # 校验层
│   ├── generator/  # 生成层（规划未实施，实际生成层为 core/writer/）
│   ├── version/    # 版本适配层（规划未实施）
│   └── layout/     # 排版层（规划未实施）
├── gui/            # 前端（仅依赖 core，不反向）
├── cli/            # 命令行（规划未实施，CLI 走 __main__.py）
├── utils/          # 工具函数（无业务逻辑）
├── config/         # 配置与规则文件
└── tests/          # 测试（依赖 core + gui）
```

> **现状核实（2026-08-07）**：上表 core/generator/、core/version/、core/layout/、cli/ 四项为规划结构，**均未实施**——实际生成层为 `core/writer/`（WriterRegistry，详见 ARCHITECTURE.md Part II（原 BACKEND_DESIGN §5）），CLI 入口走 `cis2hdl/__main__.py`（`python -m cis2hdl convert`），不存在独立 cli/ 目录。实际目录：cis2hdl/{config,core,gui,utils}；core/{parser,matcher,writer,validator,ir,engine,db,diagnostics}。

**依赖方向（单向，不可逆）**：

```
config/ ──▶ utils/ ──▶ core/ ◀── gui/
                           ◀── cli/
```

#### 8.2 模块间通信

- **core ↔ gui**：仅通过 `ConversionEngine` 类
- **core 内部**：各层通过 IR 数据模型通信
- **gui 内部**：通过 Qt 信号/槽机制

#### 8.3 新增模块检查清单

每次新增模块时，必须确认：

- [ ] 是否放在正确的包下（core / gui / utils；CLI 走 `__main__.py`，无独立 cli/ 目录）
- [ ] 是否遵循基类-注册模式
- [ ] 是否已有可复用的函数/类（先搜索再开发）
- [ ] IR 模型是否需要扩展
- [ ] 依赖方向是否正确（无循环依赖）
- [ ] 设计文档 `design/` 是否已更新

#### 8.4 UI 设计规范引用（Anthropic Token 体系）

所有前端 GUI 开发必须遵循 ARCHITECTURE.md Part V（原 `specs/UI_DESIGN_SPEC.md`）v3.0（基于 Anthropic Design Language）。

**Token 使用铁律**：

```python
from cis2hdl.gui.colors import Colors, Spacing, Radius, FontSize, Fonts, Layout, Shadow, rgb, rgba

# ✅ 正确：使用 Token
button.setStyleSheet(f"background-color: {Colors.ACCENT}; border-radius: {Radius.MD};")
label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: {FontSize.SM}px;")

# ❌ 禁止：硬编码颜色
button.setStyleSheet("background-color: #D97757;")  # 禁止！
label.setStyleSheet("color: #141413;")               # 禁止！

# ❌ 禁止：硬编码间距/圆角
widget.setContentsMargins(16, 16, 16, 16)  # 用 Spacing.BASE！
```

**Token 速查表**：

| 用途 | Token | 示例值 |
|------|-------|--------|
| 页面底色 | `Colors.BG_BASE` | #ECE9E0 |
| 卡片背景 | `Colors.BG_RAISED` | #F5F3EC |
| 主按钮 | `Colors.ACCENT` | #D97757 |
| 文字 | `Colors.TEXT_PRIMARY` | #141413 |
| 错误/危险 | `Colors.ERROR` | #C0453A |
| 卡片内距 | `Spacing.BASE` | 16px |
| 卡片间距 | `Spacing.LG` | 24px |
| 卡片圆角 | `Radius.LG` | 12px |
| 按钮圆角 | `Radius.MD` | 8px |
| 正文 | `FontSize.SM` | 14px |
| 侧边栏宽 | `Layout.SIDEBAR_WIDTH` | 240px |
| QSS 引用 | `STYLE_CARD` 等 | 从 colors.py import |

**QSS 预置样式表**：优先使用 `colors.py` 中预定义的 `STYLE_*` 字典，禁止在各面板文件中内联重复的样式字符串。


---

## Part II 开发流程 SOP（原 DEVELOPMENT_SOP.md · CIS2HDL 软件开发 SOP（标准操作流程））

> **来源**：`docs/DEVELOPMENT_SOP.md`（403 行，版本 v1.1）。本 Part 原文逐节保全，仅调标题层级；跨文档引用已更新（见文首合并说明 §3）。
>
> **合并注记**：原 `specs/DEVELOPMENT_SOP.md` 内容已并入本文档 Part II；文内「遵循 specs/CODING_STANDARDS.md」→「遵循本 STANDARDS.md Part I」。

---

> 版本: v1.1 | 日期: 2026-07-29 | 状态: 生效 | 更新: 增加强制架构设计、CHANGELOG更新、前后端配套、回归测试要求

---

### 1. 总则

#### 1.1 目的

确保 CIS2HDL 项目的所有功能开发、测试、Bug 修复、代码审查和版本发布等环节遵循统一的标准化流程，保证代码质量和项目可持续性。

#### 1.2 适用范围

- 所有项目成员（开发、测试、文档维护）
- 所有代码变更（新功能、修复、重构、文档更新）

#### 1.3 核心理念

- **一个功能一个分支** — 避免多个功能混合
- **先写测试再写代码** — TDD（测试驱动开发）
- **不通过审查不合并** — 所有 PR 必须经过 Code Review
- **先设计后开发** — **每一次**开发都必须包含架构设计部分
- **前后端配套开发** — 后端功能实现必须同步配套前端交互，禁止单端先行
- **每次变更必更新文档** — CHANGELOG 和关联设计文档随代码同步提交

#### 1.4 强制纪律（违反即退回）

| 纪律 | 要求 | 检查方式 |
|------|------|---------|
| **架构设计** | 每次开发（含 Bug 修复）必须评估是否需要更新 `design/` 文档 | PR Review 时检查 |
| **CHANGELOG** | 每次 PR 合并必须更新 `CHANGELOG.md` 相应条目 | PR 模板 Checkbox 强制勾选 |
| **前后端配套** | 后端 API 变更必须同步更新前端调用代码 | PR Review 时检查 |
| **回归测试** | 每次 Bug 修复后必须新增回归测试，确保同样 Bug 不再出现 | CI 统计测试数量 |
| **文档同步** | 接口变更、新增模块、配置变更必须同步更新对应文档 | PR Review 检查清单 |

---

### 2. 开发流程

#### 2.1 功能开发全流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 1. Issue │───▶│ 2. Branch│───▶│ 3. Design│───▶│ 4. Code  │───▶│ 5. Test  │
│  创建    │    │  创建    │    │  与实现  │    │  开发    │    │  与审查  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                                    │
                                                                    ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│10. Release│◀──│ 9. Merge │◀──│ 8. Review│◀──│ 7. Doc   │◀──│ 6. PR    │
│  发布     │    │  合并    │    │  Code    │    │  更新    │    │  提交    │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

#### 2.2 各步骤详细说明

##### Step 1: Issue 创建

```markdown
标题格式: [类型] 简短描述
类型: Feature / Bug / Refactor / Docs / Chore

内容必须包含:
- 背景/动机
- 具体需求描述
- 验收标准（Acceptance Criteria）
- 关联的 Phase/版本号
- 指派人 + 标签
```

**示例**：
```
[Feature] 实现 ExactMatcher 精确匹配器
- 背景: Phase II 匹配管道的第一阶段
- 需求: 通过 Footprint + Value + PinCount 指纹哈希进行精确匹配
- 验收标准:
  1. 相同指纹的器件匹配置信度 = 1.0
  2. 不同指纹的器件返回 no_match
  3. 单元测试覆盖率 > 90%
```

##### Step 2: Branch 创建

```bash
# 分支命名规范
feature/<issue-id>-<简短描述>     # 新功能
bugfix/<issue-id>-<简短描述>       # Bug 修复
refactor/<issue-id>-<简短描述>     # 重构
docs/<issue-id>-<简短描述>         # 文档

# 示例
git checkout -b feature/12-exact-matcher
git checkout -b bugfix/23-fix-pin-mapping-offset
```

**规则**：
- 从最新的 `main` 或 `develop` 分支创建
- 分支名全小写，用短横线连接
- 一个分支只做一个功能

##### Step 3: 设计与实现

**每一次开发都必须包含架构设计评估**：

1. **新功能开发**：必须在 `design/` 目录下创建或更新设计文档，包含：接口定义、核心算法伪代码、数据流图、前后端交互协议
2. **Bug 修复**：评估是否因架构缺陷引起，若是则先更新设计文档再修复代码
3. **重构**：必须先写重构设计文档，说明动机、影响范围、迁移方案
4. 设计文档通过 Review 后方可编码

**前后端配套开发要求**：

```
后端 API 变更                   前端同步变更
─────────────────              ─────────────────
新增 Parser 接口        →      文件选择对话框支持新格式
新增 Matcher 返回字段    →      Match Review Panel 展示新字段
Generator 进度回调变更   →      ProgressBar 适配新回调
Engine 接口变更          →      CLI 参数同步更新
```

**编码要求**：
- 严格遵循 STANDARDS.md Part I（原 `specs/CODING_STANDARDS.md`）
- 使用基类-注册模式
- switch-case/match-case 优先于 if-else
- 所有公共方法包含 docstring
- **尽量复用已有代码**：新增功能前先搜索是否有可复用的函数/类

##### Step 4: 测试

> **合并注记**：测试金字塔与测试结构详见 Part I §7 测试规范（原 CODING_STANDARDS §7）。


**测试驱动开发（TDD）流程**：

```
1. 先写测试 → 2. 运行测试（红）→ 3. 写最少代码 → 4. 运行测试（绿）→ 5. 重构
```

**测试要求**：

| 测试类型 | 覆盖要求 | 位置 |
|----------|---------|------|
| 单元测试 | > 90% 代码覆盖 | `tests/unit/` |
| 集成测试 | 每个管道阶段至少 1 个 | `tests/integration/` |
| 端到端测试 | Phase 结束时添加 | `tests/e2e/` |

**测试文件命名**：
```
tests/unit/test_<模块名>.py
tests/integration/test_<功能名>_pipeline.py
```

##### Step 5: PR 提交

**PR 模板**：

```markdown
## 概述
简短描述变更内容

## 关联 Issue
Closes #12

## 变更类型
- [ ] 新功能
- [ ] Bug修复
- [ ] 重构
- [ ] 文档更新

## 测试
- [ ] 单元测试通过: 15 tests passed
- [ ] 集成测试通过: 3 tests passed
- [ ] 新增测试覆盖: test_exact_matcher.py (12 tests)

## 检查清单
- [ ] 遵循 STANDARDS.md Part I（原 CODING_STANDARDS.md）
- [ ] 所有公共方法有 docstring
- [ ] 无循环依赖
- [ ] CHANGELOG 已更新
- [ ] 相关设计文档已更新
```

##### Step 6: Code Review

**Review 检查项**：

| 检查项 | 标准 |
|--------|------|
| 命名规范 | 类名 PascalCase，函数 snake_case |
| 分支控制 | match-case 或字典分发，避免长 if-elif 链 |
| 高内聚低耦合 | 单一职责，无循环依赖 |
| 基类-注册模式 | 新功能通过注册机制加入，不修改已有代码 |
| 错误处理 | 抛出具体异常，不静默失败 |
| 日志 | 关键步骤有 info，异常有 warning/error |
| 测试覆盖 | 单元测试覆盖新增代码 |
| 版本兼容 | 不引入不兼容的 API 变更（除非 MAJOR 版本） |

**Review 规则**：
- 至少 1 人 Review 通过后方可合并
- 核心模块（parser/matcher/generator）至少 2 人 Review
- Review 意见必须在合并前解决

##### Step 7: 合并

```bash
# Squash Merge（推荐）：将分支上的所有 commit 压缩为一个
git merge --squash feature/12-exact-matcher
git commit -m "[Feature] ExactMatcher: fingerprint-based exact component matching (#12)"
```

**Commit Message 规范**：

```
[类型] 模块名: 简短描述 (#Issue编号)

类型: Feature / Fix / Refactor / Docs / Chore / Test
```

---

### 3. Bug 修复流程

```
1. 创建 Bug Issue（描述现象、复现步骤、期望行为）
2. 创建 bugfix/<id>-<desc> 分支
3. 先写复现测试（确认 Bug 存在）
4. 修复代码（测试变绿）
5. 【强制】添加回归测试（覆盖 Bug 涉及的代码路径，防止未来复现）
6. 【强制】评估是否需要更新设计文档（如 Bug 根因是架构缺陷）
7. 【强制】更新 CHANGELOG（Fixed 条目）
8. PR → Review → Merge
```

**回归测试要求**：

| Bug 类型 | 回归测试方法 |
|---------|-------------|
| 解析错误 | 添加包含该边缘情况的测试数据文件，验证解析不再报错 |
| 匹配失败 | 添加该器件对到测试集，验证匹配成功 |
| UI 崩溃 | 添加 GUI 自动化测试，覆盖触发该 Bug 的操作路径 |
| 性能退化 | 添加性能基准测试（benchmark），设定最大耗时阈值 |
| 数据丢失 | 添加完整性校验测试，逐字段比较输入输出 |

**测试判断流程**：
```
Bug 修复完成
    ↓
当前测试是否已覆盖此 Bug 场景？
    ├── 是 → 确认现有测试通过 → 完成
    └── 否 → 必须新增回归测试 → Review → 完成
```

---

### 4. 代码审查会议

| 频率 | 内容 | 参与者 |
|------|------|--------|
| 每日（开发阶段） | 进度同步、阻塞项报告 | 所有开发者 |
| 每周 | Code Review 回顾、技术难点讨论 | 所有开发者 |
| 每 Phase 结束 | 阶段验收评审、下阶段计划 | 全体 |

---

### 5. 版本发布流程

#### 5.1 版本号规则

遵循语义化版本：`MAJOR.MINOR.PATCH`

- **MAJOR**: 不兼容的 API 变更、核心架构重构
- **MINOR**: 向后兼容的新功能
- **PATCH**: 向后兼容的 Bug 修复

#### 5.2 发布步骤

```
1. 确认所有 Phase 任务完成
2. 确认所有测试通过（CI）
3. 更新 CHANGELOG.md（确定版本号和发布日期）
4. 更新 README.md（如有需要）
5. **四文件同步检查单**（版本号必须一致，不一致时禁止打 Tag）：
   - [ ] `cis2hdl/__init__.py` — `__version__`
   - [ ] `pyproject.toml` — `project.version`
   - [ ] `CHANGELOG.md` — 当前版本标题
   - [ ] `README.md` — 版本徽章/说明
6. 创建 Git Tag: git tag -a v0.1.0 -m "Phase I: Foundation"
7. 打包发布（PyInstaller 生成 .exe）
```

---

### 6. 紧急修复流程（Hotfix）

当生产环境发现阻塞性 Bug 时：

```
1. 从最新的 release tag 创建 hotfix/<desc> 分支
2. 修复 → 测试 → Review → 合并到 main
3. 同时 cherry-pick 到 develop 分支
4. 立即创建新的 PATCH 版本 Tag
5. 发布新版本
```

---

### 7. 文档维护规则

#### 7.1 强制更新表

| 文档 | 何时更新 | 谁更新 | 强制级别 |
|------|---------|--------|:--------:|
| `CHANGELOG.md` | **每次 PR 合并时** | 开发者 | **强制** |
| `design/*.md` | 架构、接口、数据流变更时 | 开发者 | **强制（评估后）** |
| `README.md` | 新功能完成或接口变更时 | 开发者 | 推荐 |
| `specs/*.md` | 规范变更时 | 全员提案，主程审核 | 推荐 |
| `docs/*.md` | 需求变更或新调研时 | 调研者 | 推荐 |

#### 7.2 CHANGELOG 更新规范

**每一次开发和改动都必须更新 CHANGELOG**，无例外。

```markdown
## [Unreleased]

### Added
- 新增的 Feature

### Changed
- 变更的现有功能

### Fixed
- 修复的 Bug

### Deprecated
- 即将移除的功能
```

**CHANGELOG 条目必须包含 Issue 编号**：
```markdown
### Fixed
- 修复 DSN 解析器在空页面时崩溃的问题 (#45)
- 修复模糊匹配器在器件名为空时返回 None 的问题 (#46)
```

> **CHANGELOG 补录纪律**：版本发布后若发现 CHANGELOG 长期未更新，必须在下一个版本发布前补录。历史教训：v0.9.0 → v1.1.0 期间 CHANGELOG 曾长期未更新，已于 2026-08-07 补录；禁止出现"版本号已升、CHANGELOG 空白"的情况。

#### 7.3 规则

- **代码和文档同步提交**（同一个 PR），不允许"先合代码后补文档"
- 文档文件先于代码文件创建（设计阶段）
- 过时文档标记 `[DEPRECATED]` 前缀而非删除
- PR 模板中 CHANGELOG Checkbox 未勾选 → Review 不通过

---

### 8. 环境与工具链

#### 8.1 开发环境

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 安装依赖（必须在项目根目录 cis2hdl/ 下执行；包位于 cis2hdl/ 而非 src/）
pip install -e ".[dev]"

# 代码质量检查
ruff check .
ruff format --check .
mypy cis2hdl/

# 运行测试
pytest tests/ -v --cov=cis2hdl/
```

#### 8.2 CI/CD（推荐）

```yaml
# .github/workflows/ci.yml 示例结构
on: [push, pull_request]
jobs:
  lint:
    - ruff check
    - ruff format --check
    - mypy
  test:
    - pytest --cov
  build:
    - PyInstaller 打包
```

---

### 9. 问题升级路径

| 问题类型 | 处理者 | 升级条件 |
|---------|--------|---------|
| 编译/运行错误 | 开发者自行解决 | 超过 2 小时无进展 → 主程 |
| 设计决策分歧 | 开发者讨论 | 无法达成一致 → 主程裁决 |
| 第三方依赖问题 | 开发者调查 | 不可解决 → 讨论替代方案 |
| 性能瓶颈 | 开发者优化 | 超过 Phase 指标 → 架构评审 |
| 安全/合规问题 | 立即上报主程 | 无需等待 |


---

## Part III 原理图与 HDL 输出规范（原 HDL_SCHEMATIC_STANDARDS.md · HDL 原理图排版美观自动化分析与版本兼容性规范）

> **来源**：`docs/HDL_SCHEMATIC_STANDARDS.md`（443 行，版本 v1.0）。本 Part 原文逐节保全，仅调标题层级；跨文档引用已更新（见文首合并说明 §3）。
>
> **合并注记**：原 `specs/HDL_SCHEMATIC_STANDARDS.md` 内容已并入本文档 Part III；文中「见 HDL_SCHEMATIC_STANDARDS」类引用均指本 Part。历史验证记录引用（`docs/test1.txt`、`docs/_comparison_report.md`、`docs/fix_proposal.md`、`docs/HDL_OUTPUT_FIX_PLAN.md`）为历史源证，保留原文未改。

---

> 版本: v1.0 | 日期: 2026-07-29 | 基于: 公司《硬件设计规范》+ Cadence SPB 16.6 实践项目

---

### 一、原理图排版美观：软件可实现 vs 人工调整

#### 1.1 公司 HDL 规范要求（摘录自《硬件设计规范》）

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

#### 1.2 可自动化实现的部分

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

#### 1.3 需要人工调整的部分

| 规范 | 自动化可行性 | 原因 |
|------|:----------:|------|
| **走线美观（全局布局）** | ❌ 难自动化 | 布线美学（避免交叉、对称性、空间利用）需要人工审美判断 |
| **原理图可读性** | ❌ 难自动化 | 电路功能分组、信号流向、模块边界划分依赖设计意图 |
| **复杂 IC 管脚排列** | ⚠️ 半自动 | 可提供功能分组建议，但最终排布需工程师确认 |
| **设计检查（逻辑正确性）** | ⚠️ 半自动 | 可做 DRC/ERC 检查，但设计意图的理解需人工 |

#### 1.4 推荐策略：自动化 + 人工微调

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

### 二、HDL 器件库自动导入规范

#### 2.1 HDL 库标准目录结构（基于公司实践项目）

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

#### 2.2 可自动导入的文件类型

| 文件 | 可解析内容 | 用途 |
|------|-----------|------|
| **chips.prt** | 管脚名称、编号、电气类型、Part 名称、位号前缀、CLASS | 快速建立器件 Pin 列表 |
| **symbol.css** | 符号图形坐标、引脚位置/名称/方向、value 位置 | 读取符号的图形布局信息 |
| **part.ptf** | 器件型号、封装、描述、SN_NUM、BOM_SEQ、规格参数 | 建立完善器件属性数据库 |
| **pinlist.txt** | 引脚功能列表 | 辅助验证 |
| **pad 文件 (.pad)** | 焊盘尺寸、形状、层定义 | PCB 封装信息 |
| **dra 文件 (.dra)** | 封装图形 | PCB 封装外形 |
| **psm 文件 (.psm)** | 封装符号模型 | PCB 完整封装 |

#### 2.3 库导入工具需求

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

#### 2.4 chips.prt 解析规则

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

#### 2.5 symbol.css 解析规则

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

#### 2.6 part.ptf 解析规则

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

### 三、Cadence SPB 16.6 版本兼容性设计

#### 3.1 16.6 版本特征（基于 .cpm 文件分析）

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

#### 3.2 多版本兼容策略

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

#### 3.3 各版本差异点（需在生成时适配）

| 差异项 | 16.6 | 17.2 | 17.4 |
|--------|------|------|------|
| `.sch` 格式 | VERSION 6 | VERSION 6 | VERSION 6 |
| `.cpm` cpm_version | '16.6' | '17.2' | '17.4' |
| `cds.lib` 语法 | 一致 | 一致 | 一致 |
| 字体支持 | 矢量字体（默认）| TrueType 字体 | TrueType 字体 |
| 约束管理器 | 基础 | 增强 | 增强 |
| Design Sync 选项 | 基础 | 增加选项 | 增加选项 |
| Packager-XL 网表格式 | 一致 | 一致 | 一致 |

#### 3.4 兼容性测试矩阵

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

### 四、BOM_SEQ 编码规则（从规范文档提取）

#### 4.1 编码结构

```
BOM_SEQ = 第1位(安装方式) + 第2位(器件类型) + 第3-4位(封装代码)
```

#### 4.2 第1位：安装方式

| 代码 | 含义 |
|:----:|------|
| A | 贴片（SMD） |
| B | 插件（Through-hole） |
| C | 定位孔/过孔/测试点/金手指 |

#### 4.3 第2位：器件类型

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

#### 4.4 第3-4位：封装代码

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

#### 4.5 自动生成规则

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

### 五、Cadence 兼容性经验速查

> 本章为 Cadence SPB 16.6 环境下的实测经验汇总，供生成器开发与排障参考。
> 内容提炼自人工验证操作记录（`docs/test1.txt`，操作 18/19）与参考实现比对报告（`docs/_comparison_report.md`，2026-08-03）。

#### 5.1 UPREV 机制与 cpm_version

- **触发条件**：Cadence Project Manager 打开 `.cpm` 时检测到版本信息缺失/不匹配，触发 UPREV（项目升级）流程；若 `write.exe` 不在 PATH 中，升级会失败。
- **关键字段**：`.cpm` 必须包含 `cpm_version '16.6'`（位于 `START_GLOBAL`/`END_GLOBAL` 段之间）。
- **旧格式教训**：旧版 CPM 使用 `START_DESIGN`/`END_DESIGN` 格式且缺少 `cpm_version` 字段，Cadence 无法判断版本 → 触发 UPREV。当前生成器已统一输出 `START_GLOBAL` + `cpm_version '16.6'`。
- **绕过参数**：命令行参数 `-nonetlistuprev` 可绕过 UPREV 流程（用于调试/验证，不建议作为常规交付路径）。

#### 5.2 SPCOCN 错误速查表

| SPCOCN 错误码 | 含义 | 常见根因 / 处置方向 |
|:---:|------|---------------------|
| 543 | SIG_NAME 引脚属性被删除 | 页面文件中手动定义 `$PN` 引脚属性，与 hdl_lib 定义不一致；不应手动生成 `$PN`/`LASTPIN`，交由 DEHDL 从器件库自动获取 |
| 542 | 默认属性相关 | 页面/器件默认属性处理；具体细节 [待填写] |
| 515 | cds.lib 缺少库定义 | `cds.lib` 中未 `DEFINE` 对应库或库路径无效；检查库路径是否有效 |
| 1908 | 括号不匹配 | 生成文件中括号配对错误；检查 S-expr/CSA 文件括号 |
| 1909 | Unknown word | 生成文件中出现 Cadence 无法识别的关键字；对照参考格式修正关键字 |
| 1910 | bad token | 词法错误、token 非法；检查文件编码与转义 |
| 1891 | syntax error | 语法错误（Cadence 16.6 不支持的写法）；检查生成文件语法 |

#### 5.3 配置要点

- **PAGE_NAME_PROP**：`.cpm` 的 `START_CONCEPTHDL` 段需包含 `PAGE_NAME_PROP 'EDIT PAGE NAME'`，用于页面名属性定义。
- **CDS_EDITOR**：Cadence 环境变量，用于指定 Design Entry HDL 编辑器相关配置；具体取值以 Cadence 安装环境为准。
- **人工验证操作**：在 Cadence 电脑上执行 Project Manager → 导入设计 → 逐页检查符号/网络/引脚 → BOM 对比（详细步骤与核对表见 `docs/test1.txt` 操作 18/19）。

#### 5.4 CSA 格式差异速查（当前实现 vs 参考实现）

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

---

## 合并保全声明

本文档由以下 3 份源文档内容保全式合并而成，合并过程遵循「逐节保留、不改写原文句子、仅调标题层级与交叉引用」原则：

| 源文档 | 行数 | 合并位置 | 保全状态 |
|---|---|---|---|
| `docs/CODING_STANDARDS.md` | 586 | Part I 编码规范 | ✅ 章节 1~8 全部保留 |
| `docs/DEVELOPMENT_SOP.md` | 403 | Part II 开发流程 SOP | ✅ 章节 1~9 全部保留 |
| `docs/HDL_SCHEMATIC_STANDARDS.md` | 443 | Part III 原理图与 HDL 输出规范 | ✅ 章节 一~五 全部保留 |

**保全核对（自检）**：

- 三份源文档的 H1/H2 章节标题已全部出现在本文档对应 Part 中（见文首合并说明 · 章节映射表）；
- 表格、代码块、附录、注记（含历史口径注记）均原样保留；
- 过时表述仅保留于历史注记（如「错误码 31/39 历史口径」），未作为现行口径扩散；
- 现行口径统一：错误码 44、匹配 v2.0、测试 268/23（291）、版本 v1.1.0、输出 CSA（.csa）、GUI PySide6、目录结构 `cis2hdl/`（CLI 走 `__main__.py`）；
- 跨文档引用已更新至合并后文档位置（详见文首合并说明 · 交叉引用更新说明）。

> 合并日期：2026-08-07 ｜ 合并执行：专业文档生成团队（支笔生 Zhi / doc-generator-m4）｜ 源文档由主理人统一归档管理，未作任何修改。

---

# Phase XI P0 开发规范补充（2026-08-10 追加）

> 本节由软件交付团队追加，记录 P0 A-D 实施中新确立的开发规范与约定（详见
> `docs/system_design.md` C.5 共享约定）。

## 网络命名三态（强制约定）

| 态 | 示例 | 用途 | 生成者 |
|----|------|------|--------|
| CSV 显示名 | `GND_POWER\g` / `UN$1$CAPACITOR$I12$1` / 原样 | pageN.csv 网络清单 | net_utils |
| con 内部名 | `gnd_power` / `page21_0v9_comm` | con/xcon nets | net_utils |
| SIG_NAME | `GND_POWER\g`（电源带 \g） | csa 网络标签 | net_utils |

**规则**：三态由 `net_utils.py` 统一生成，任何 writer 不得自行拼名。

## ID 三套体系（强制约定）

| 体系 | 文件 | 编号规则 |
|------|------|----------|
| 设计级 | con/xcon | I/N/M/S/T（跨页连续） |
| 页级网络 | csv | 0..K（0=NC，页内连续） |
| 页级实例 | csv I<k> + cpc pageN_i<k> + con 内部名 | 每页从 1 连续 |

**规则**：页级实例编号每页从 1 连续，设计级 I-id 跨页连续；三方严格一致。

## 坐标唯一原则（强制约定）

一个实例只有一个"体坐标"（`CoordTransform` 输出）；LASTPIN/WIRE/csv 头行坐标
全部由"体坐标 + symbol.css C 指令偏移"派生，**禁止独立计算**。

## 电源符号特例（强制约定）

gnd_power/vcc_circle **不进** con cells/instances，但进 csv/cpc(#ISCELL)/csa；
其网在 con 中 scope=2 全局（跨页时）。

## 高内聚低耦合检查（P0 新增模块）

| 模块 | 职责 | 禁止 |
|------|------|------|
| net_utils.py | 网络名清洗/分类 | 不触碰文件写入 |
| coord_transform.py | 坐标变换 | 不触碰网络命名 |
| wire_layout.py | 拓扑合成路由 | 不直接写文件（返回 WIRE/DOT 段） |
| connectivity_model.py | 共享连接模型 | 不直接写文件（供 4 writer 消费） |
| con/xcon/csv/cpc_writer | 各写各的文件 | 不自行拼名/编号（用模型） |

## 诚实验收原则（P0 强制）

- 任何"连线显示/网表导出"成果，未在 Cadence 16.6 实测前，一律标注"待 Cadence 实测"
- 静态断言（格式/坐标/语法）≠ 实测通过；两者必须分开声明
- 数据差异（如 889 vs 906 实例）如实记录根因，不掩盖

---

# Phase XI P0 遗留修复规范补充（2026-08-10 追加）

> 记录 P0 遗留三问题修复确立的新约定（详见 docs/phaseXI_P0_fix_design.md）。

## ROUTE 跳线处理约定

- OrCAD Value="ROUTE" + COPPER0201 = **0Ω 跳线（真实元件）**，不是布线标记
- 映射到 hdl_lib `resistor`（2 引脚、引脚偏移 ±100），pin_name 用 "1"/"2"
- 跳线两端连接**不同网络**（如 J11: 2P5GE_RSTN ↔ HGPIO_17），转换后必须保留
- `_SKIP_REFDES_VALUES` 仅跳过空 Value，不跳过 ROUTE

## 电源符号处理约定（C.5 强化）

| 文件 | 电源符号处理 |
|------|-------------|
| con | **不进** cells/instances（保持） |
| csv | `%"GND"/%"VCC_CIRCLE"` 块 + HDL_POWER + BODY_TYPE + 单引脚行 |
| cpc | `#ISCELL hdl_lib gnd_power/vcc_circle * pageN_i<k>` |
| csa | FORCEADD + LASTPIN SIG_NAME(\g) + HDL_POWER + BODY_TYPE PLUMBING |

- 每页每电源网 1 个符号；坐标优先 EDIF transform origin，回退页面边缘
- POWER_SYMBOL_CELLS 含 gnd/dgnd/gnd_power/vcc_circle/gnd_earth/gnd_signal/vcc_bar/vcc_arrow
- GND/DGND 符号 → 固定网 "GND"；VCC_CIRCLE → 网名取 refdes/NETNAME

## 自动网名 UN$ 约定

- `$` 开头 = OrCAD 自动网（如 $47N777）
- con 内部名：`unnamed_<page>_<cell>_i<k>_<pin>`（小写、$→_）
- csv/csa 显示名：`UN$<page>$<CELL>$I<k>$<pin>`（大写）
- page/cell/k/pin 从该网第一个连接 (refdes, pin) 推导；推导失败回退 con_name
- scope=0（局部网），即使跨页也不做 alias

---

# Phase XI P1 开发规范补充（2026-08-10 追加）

> 记录 P1 第二轮修复确立的约定（详见 changelog_master.md P1 记录）。

## page.map 页码（强制约定）

- **页码来源**：`_extract_page_number()` 从 `page.page_name` 数字前缀提取
  （`01-Cover_Page`→1、`10-SOC_SerDes`→10），**禁止**用 enumerate 索引或 page_id
- **输出格式**：`<真实页码> <tab索引> <显示名>`，按真实页码升序排序
- **容错**：page_name 无数字前缀时回退 page_id 后缀（"1.5"→5），再回退 0

## symbol.css 默认属性（强制约定）

- 每个符号必须声明：`CDS_LMAN_SYM_OUTLINE`、`$LOCATION`、`VALUE`、`PART_NAME`、`PATH`
  （csa 会输出这些 FORCEPROP 属性，库未声明会导致 SPCOCN-542 属性丢失）
- 坐标：$LOCATION/VALUE 贴合 outline 外侧，PART_NAME/PATH 用 `0 0`（invisible）
- 新增符号进 hdl_lib 时必须对照 capacitor 属性集补全

## csa $LOCATION（强制约定）

- **统一输出 `FORCEPROP 1 LAST $LOCATION`**（单/多 section 一律）
- 依据：$LOCATION vs LOCATION 是 OrCAD 源实例级属性（同 body 不同实例不同），
  无法从 section/symbol.css 推导；04p4 实测绝大多数用 $LOCATION
- 禁止按 `section > 1` 分支输出 LOCATION

## 旋转/镜像/NC 存储（P1-4 约定）

- EDIF `(orientation R90/R180/R270/MY/MX/MYR90)` → `ComponentInstanceIR.rotation/mirror`
  （rotation 存角度、mirror 存 1=X/2=Y）
- pstxnet net="NC" 引脚 → `ComponentInstanceIR.nc_pins`（set[str]，Stage 5.5b 注入处）
- SymbolPin 新增 `electrical_type`/`pin_shape` 字段（OLB 类型打通存储）
- ⚠️ 当前仅存储，csa/csv 输出尚未消费——后续消费时用 sym_N 视图映射 rotation

## cpc #ISCELL/#CELL（强制约定）

- `#ISCELL` 仅：页框（c#20size#20page 等）、电源符号（gnd_power/vcc_circle）
- `#CELL`：一切普通元件（含 mark/test_point/tp/nc）
- mark 已在 P1-5 从 _ISCELL_CELLS 移除（8367/04p4 双实证）

## U6 双口径（数据约定）

- 主链口径：**CrossRef U6A-I**（9 section）为权威，pstxnet 母 U6 作校验参考
- pstxnet 同时含母 U6 + U6A-I（引脚 100% 重叠），注入按 U6A-I 匹配即可
- 验收：con conn == pstxnet 总连接 - 母 U6 引脚数（2821 == 3352 - 531）

---

# Phase XI P2 开发规范补充（2026-08-10 追加）

## 元件旋转/镜像（P2-1 强制约定）

- **旋转表达**：DEHDL 旋转 = sym_N 视图，但库中 sym_N 语义混合（旋转视图 + 器件变体）→ **禁止直接切换 sym_N**
- **统一方案**：用 `coord_transform.rotate_point(offset, rotation, mirror)` 对 symbol.css 引脚偏移做几何旋转（R90 (x,y)→(-y,x)，镜像 mirror=1 翻 Y/2 翻 X）
- **数据链路**：EDIF orientation → ComponentInstanceIR.rotation/mirror → 占位保留（经 pstxprt ins_to_refdes 映射到真实 refdes）→ catalog 恢复 → InstanceRecord → csa 消费
- **回退**：无 pstxprt 映射时 rotation=0（默认视图），不得报错

## NC 引脚（P2-2 强制约定）

- NC 引脚（net="NC"）**禁止**加入 net_pin_map——不生成 SIG_NAME、不画 WIRE
- NC 引脚**必须**保留 LASTPIN $PN（引脚在原理图存在，无连接）
- csv 沿用 `0"NC"` 机制；con 沿用 nc 网络 scope=0

## 旋转/NC 验收（强制）

- 全量 pytest 全绿（当前 395 passed / 23 skipped）
- 旋转验证：转换后 LASTPIN 相对 FORCEADD 体坐标的偏移方向与 EDIF orientation 一致
- NC 验证：csa 无 `SIG_NAME NC`；LASTPIN $PN 数量不因 NC 排除而减少

---

# Phase XI 收尾规范补充（2026-08-10 追加）

## off_page 提取（P0-A3 强制约定）

- 页面级 off_pages（522）：joined→portRef 无 instanceRef 且标签含 OFF_PAGE_CONNECTOR
- 设计级 design_off_pages（243）：顶层 cell view→contents→offPageConnector
- **验收**：页级 + 设计级 = EDIF 文件 OFF_PAGE_CONNECTOR 总数（765）

## IOPORT 跨页端口（P0-C5 约定）

- 每跨页连接 1 个 IOPORT 块：FORCEADD IOPORT..1 + OFFPAGE TRUE + HDL_PORT/VHDL_PORT + CDS_LIB
- 与 SIG_NAME **共存**（IOPORT = 端口符号，SIG_NAME = 网络标签）
- 方向默认 INOUT（EDIF 无方向数据）
- 符号来自 standard 库（hdl_lib/IOPORT 等）

## chips.prt 引脚（T03 强制约定）

- `PIN_NUMBER` 存 PinDef.number（数字），`'功能名':` 存 PinDef.name（RST#）
- **禁止**用 PIN_NUMBER 覆盖功能名
- 电气类型源：chips.prt PINUSE（INPUT/OUTPUT/BIDIR→ElectricalType）

## DSN RTL PlacedInstance（T04 约定）

- RTL 变体用 `_parse_placed_instance_rtl`（_RtlStructure + reference + t0x10），**禁止 raise**
- `_is_valid_result` 对引脚级实例（reference 空）放宽
- P0-D2 不变：DSN 元件源仍禁用（EDIF+pstxnet 主链）

---

# Phase XII 规范补充（2026-08-10 追加）

## 电源符号匹配（R2 强制约定）

- 电源符号（GND/DGND/VCC_CIRCLE/GND_EARTH 等）**必须**生成确定性 MatchResult：
  - 策略 `MatchStrategy.POWER_SYMBOL`、conf=1.0、`phase1_type="power"`
  - 目标映射：GND/DGND/GND_POWER/GND_SIGNAL → `gnd_power`；GND_EARTH/GND_CHASSIS → `gnd_earth`；VCC_CIRCLE/VCC_BAR/VCC_ARROW → `vcc_circle`
- mapping_csv/INFO_LOSS 检查**禁止**对电源符号报 Missing_Value/No_Pin_Connections（天然无值无引脚连接）
- 电源符号仍**不进** con cells/instances（延续 P0 约定），只参与匹配统计与报告

## 质量计数（R1 强制约定）

- quality `total_count` 用 `sum(len(p.instances) for p in design.pages)`，**禁止** `design.all_instances`（cached_property 可能陈旧）
- 匹配数用 `_count_matched_instances()` 按实例计数（refdes/library_id 命中），**禁止**按 MatchResult 数（多实例共享 key 会低估）
- Catalog 重建后必须调用 `design.invalidate_caches()`

## YAML 配置（R3 强制约定）

- `match_config.py` 硬编码 defaults **必须**与 type_gate.yaml 保持一致（RD 前缀、fixed_prefixes 等）
- PyYAML import 失败时 `logger.warning`（禁止静默 debug）——本次事故根因之一
- 环境安装：`pip install PyYAML`（requirements.txt 已声明）

## 报告候选行（R5 强制约定）

- top-1 candidate 行**必须**显示实际匹配 ptf 行数据（`_matched_row`），ptf_rows[0] 仅作空值回退
- 主行与选中候选行的 value/jedec/package_type/footprint 必须一致（C102 教训）

## 报告样式（R7 约定）

- match-main 主行：浅灰 `#E5E2D8` + 深字 `#141413`（比 top3 行 rgba(108,104,96,0.04) 深一级）
- conf 颜色按 `_score_color` 分级：≥90% 绿 / ≥75% 蓝 / ≥60% 琥珀 / ≥40% 橙 / <40% 红；禁止 `!important` 覆盖
- 新增板块（Output File Types / Default Fallback Components）置于 Match Results 上方，dashboard 密度

---

# Phase XIII 规范补充（2026-08-11 追加）

## 页面编号（T0 强制约定）

- `page_num` **必须**来自页名数字前缀（`_real_page_number`，"10-SOC_SerDes"→10），**禁止** `page_idx+1`（EDIF 解析顺序）
- pageN.csa / con / xcon / csv / cpc / page.map **六方必须同一编号**（1=01-Cover_Page … 24=24-LED_KEY）

## LASTPIN 位置（T2 强制约定）

- 每个实例的 LASTPIN **必须内联**在该实例 FORCEADD 块内（$PN 级别 2 / SIG_NAME 级别 3）
- **禁止**集中到文件尾（会绑定最后一个 FORCEADD → SPCOCN-543 属性被删）
- IOPORT 块 LASTPIN **级别 1**（`FORCEPROP 1 LASTPIN`）；引脚坐标 = body + symbol.css C 偏移（IOPORT = -50,0）；HDL_PORT 标签 = css X 偏移（325,-125）；禁止多余 CDS_LMAN_SYM_OUTLINE

## 坐标与网格（T1 强制约定）

- 所有输出坐标（body/LASTPIN/WIRE 端点）**必须** 25 网格对齐（`_snap25`），禁止 off-grid（SPCOCN-1329）
- 吸网格必须发生在 pin_coords **源头**（LASTPIN 与 WIRE 共用），保证端点精确重合（连接硬约束）

## 旋转（T1 约定）

- rotation 90/180/270 → 组件块输出 `R 1/2/3`；**必须**与引脚偏移旋转一致
- mirror：**保守策略**——不输出 MY/MX、引脚不镜像（保证渲染=坐标）；MY/MX 语法验证后 P1 启用

## 布线（T4 约定）

- 多网 trunk **必须**车道差异化（_LANE=50），禁止共线
- trunk 冲突判定用**闭区间**（`max(lo_a,lo_b) <= min(hi_a,hi_b)`，端点相接也算冲突）——防止不同网 trunk 首尾相接造成电气短路
- 必须传 body_outlines 使 trunk 避让元件体；WIRE 端点必须 = 引脚坐标（Cadence 坐标重合即连接）

---

# Phase XIV 规范补充（2026-08-11 追加）

## 布线器注册（D5 强制约定）

- 所有布线策略**必须**继承 `WireRouterBase(ABC)` 并用 `@register_router(name)` 注册进 `ROUTER_REGISTRY`
- 注册名 = `routing.mode` / CLI `--routing` 取值（p0/p0_lane/detour/edif_reuse）
- csa_writer **禁止** import 具体布线器类，只依赖 `create_router(mode)` 工厂；异常 → `logger.warning` → 回退 p0_lane
- 新布线器默认**不启用**（routing.mode=p0），用户显式 --routing 开启

## 标签布局（D1 强制约定）

- 标签去冲突**只动** DISPLAY/FORCEPROP 标签行，**禁止**改动 LASTPIN/WIRE 坐标（DEHDL 连接=坐标重合）
- 文本 bbox 估算用保守默认：字宽 0.65×字号×scale、行高 1.2、padding 12、最小宽 75
- 移动优先级：SIG_NAME@wire（沿 trunk）> VALUE/$LOCATION（就近 8 方向）> PIN_TEXT（禁动）
- 所有新标签坐标必须 snap 25 网格

## 网络名对齐（D1 规范落地）

- 网络名 x 对齐 = `snap25(trunk_min_x + 375)`（7.5 格点 × 50 单位/格）
- 同侧 IOPORT 等间距、边缘对齐；差分对 `_P/_N` 网 → P 上 N 下（无后缀不猜测）

## 人工匹配（D3 约定）

- manual_matches.yaml 格式：`refdes: {library_id: X, section: N}`；在 `_stage_match` 后注入覆盖
- 引脚数不匹配 → `logger.warning` 不注入（防错配）
- `--export-unmatched` 导出待确认清单（refdes/引脚数/引脚名/建议候选）

## 元件重叠（D2 约定）

- 重叠检测**只报告不移动**（CIS 原布局为工程师手绘）；`--aesthetic-placement` 显式开启才自动移动（远期）
- aesthetic_report.txt 每条含 fix_hint（占位符号建议 D3 人工匹配）

## 配置开关（用户强制）

- 新功能**必须**独立模块 + `routing.yaml` 开关（默认关、可回退）
- wire_layout **保持单一职责**（几何合成），布线策略在 Router 层
- 禁止硬编码：新模块参数全部进 routing.yaml（lane_pitch/grid/detour_margin/bbox 系数等）

---

# Phase XV 规范补充（2026-08-11 追加）

## LASTPIN 格式（P0-A 强制约定）

- `$PN` LASTPIN 块**禁止** `PAINT` 行（Cadence 属性绑定中断 → SPCOCN-543）；格式固定：
  ```
  FORCEPROP 2 LASTPIN (x y) $PN <n>
  R 1
  J 0
  (lx ly);
  DISPLAY 0.808511 (lx ly);
  ```
- SIG_NAME LASTPIN 保留 PAINT MONO + DISPLAY INVISIBLE（04p4 一致）

## 占位符号（P0-F 强制约定）

- 无 hdl_lib 符号或引脚不匹配的实例**必须**生成占位符号（`placeholder_lib.py`），**禁止** fallback 错误符号（CH347 教训）
- 占位符号必须：按 EDIF 引脚名/数量生成、outline 贴合、标注 `PLACEHOLDER`（元件名/属性）
- 配置 `placeholder.enabled`（默认 true，用户要求后端默认生效）

## 旋转（P0-E 强制约定）

- EDIF orientation 与 DEHDL R 行符号约定相反：**90↔270 互换**（`_dehdl_rotation`）；180 不变
- mirror：仍保守不输出 M 行（语法待 Cadence 验证），文档记录已知限制

## 美观布线（P1-G 约定）

- `--aesthetic` **必须**自动启用：routing.mode=detour + ioport.edge_layout + gnd_distribution.enabled（否则电线与默认无区别）
- stub 引出段（lead-out）在 DetourRouter override，wire_layout 保持 P0 单一职责
- 相邻引脚引出段差异化（lead_map），防并列重叠

## GND 分布（P1-D 用户决策）

- 每芯片一组 GND 符号；无芯片区域按距离阈值补放；密集/并联区多放
- 电气不变（同网 SIG_NAME 连接），只增符号数量分布到各芯片附近

## IO 口（P1-C 用户决策）

- 页内网一律 SIG_NAME 网络名（不生成 IOPORT）；跨页网 IOPORT 沿右缘等间距分布（edge_layout）

---

# Phase XVI 规范补充（2026-08-11 追加）

## 镜像处理（T1 强制约定）

- EDIF orientation **镜像在前、旋转在后**（2.0.0 标准：MYR90=MY∘R90）。`rotate_point` 是唯一变换实现
- mirror 实例：引脚坐标**必须**精确镜像（电气硬约束——LASTPIN 与 WIRE 同源 pin_coords），渲染用 `closest_rotation_for_mirror` 最接近旋转输出 R 行；**禁止**输出未验证的 M 行
- **电源符号**（GND/VCC/DGND）：LASTPIN 偏移**必须**应用 mirror（`rotate_point(0,±50,mirror)`），禁止硬编码 `y±50`（Phase XVI bug：LASTPIN 7150≠WIRE 7050）
- 镜像方向近似（approx）实例**必须**在 aesthetic_report [MIRROR] 节标注"方向近似需人工复核"

## IOPORT 审计（T2 强制约定）

- 审计**必须**基于 DesignConnectivity 模型（pin_connections 已注入），**禁止** raw EDIF PageIR（孤立检测 100% 误报）
- 接线核对：IOPORT 所在网 ≥2 引脚时必须已布线（ioport_coord ∈ routed wires 端点）；**单引脚网豁免**（仅 IOPORT 的网不生成 WIRE 属正常）
- 网名一致性：canonical 归一化（去下划线/空白/小写）分组，**只报告不自动合并**（跨页改名有电气风险）；`ioport.manual_names` 人工裁决后覆盖
- 孤立 connector：`ioport.skip_orphan=true` 时生成层跳过（不生成 IOPORT 也不入网）

## 配置（Phase XVI）

- `mirror.normalize=true`（默认开，正确性修复）；`--no-mirror-normalize` 逃生舱
- `ioport.audit=false`（默认关）；`--ioport-audit` / `--aesthetic` 开启
