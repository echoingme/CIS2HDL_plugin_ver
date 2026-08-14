# CIS2HDL 开发规范

> 版本: v1.2 | 日期: 2026-07-30 | 状态: 生效（2026-07-30 起，v1.2） | 更新: 新增诊断器开发规范、44 错误码体系、用户引导式错误处理

---

## 1. 总则

### 1.1 语言与工具

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

### 1.2 理念

- **高内聚、低耦合**：每个模块只做一件事
- **基类-注册模式**：通过抽象基类（ABC）定义接口，注册表管理实现
- **switch-case 优先于 if-else**：对于多分支的平行模式/选项使用字典分发或 match-case
- **显式优于隐式**：不做魔法行为，所有转换参数显式传递
- **失败优于静默**：异常情况抛异常或记录日志，不静默吞掉错误
- **代码复用优先**：优先搜索现有函数/类是否可复用，避免重复造轮子
- **变量语义化**：变量名必须反映其业务含义，禁止 `x`, `tmp`, `data` 等无意义名称（循环变量除外）

### 1.3 代码复用原则

| 原则 | 说明 | 示例 |
|------|------|------|
| **先搜索后编写** | 新增功能前，先在项目中搜索是否已有类似实现 | `grep "def parse" core/parser/` |
| **提取公共函数** | 两个以上模块使用相同逻辑 → 提取到 `utils/` | `strip_quotes()`, `normalize_net_name()` |
| **基类共享逻辑** | 多个子类有相同方法 → 提升到基类实现 | `ParserBase.validate_input()` |
| **组合优于继承** | 跨层级共享逻辑 → 使用 Mixin 或工具类 | `LoggingMixin`, `ConfigMixin` |
| **函数尽量复用调用** | 公开函数应设计为可被多处调用，避免硬编码 | `parse_chips_prt(path)` 而非在 Scanner 内硬编码 

---

## 2. 命名规范

### 2.1 文件

```
小写下划线:  project_panel.py, dsn_parser.py, fuzzy_matcher.py
一个文件一个主类:  文件名 = 主类名转小写下划线
测试文件:  test_<模块名>.py
```

### 2.2 类

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

### 2.3 函数与方法

```python
# 小写下划线（snake_case）
def parse_design(self, file_path: Path) -> DesignIR: ...
def compute_similarity(self, a: str, b: str) -> float: ...
def _extract_package_info(self, raw: bytes) -> dict: ...

# 私有方法以下划线开头
def _decode_cfb_stream(self, stream_name: str) -> bytes: ...
```

### 2.4 变量

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

### 2.5 变量定义规范（强制执行）

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

## 3. 代码风格

### 3.1 分支控制：switch-case 优先

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

### 3.2 函数定义规范

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

### 3.3 类定义规范

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

### 3.4 模块关联原则

| 原则 | 说明 |
|------|------|
| **依赖方向** | IR ← Parser/Matcher/Validator/Generator（单向依赖） |
| **循环依赖零容忍** | 如出现循环依赖，提取公共接口到独立模块 |
| **只暴露公共 API** | `__all__` 或 `__init__.py` 明确导出内容 |
| **内部实现用 `_` 前缀** | 不在 `__init__.py` 中导出的模块和函数 |

---

## 4. 基类-注册模式

### 4.1 设计模式

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

### 4.2 实现模板

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

## 5. 错误处理规范

### 5.1 异常层次

```
CIS2HDLError (base)
├── CIS2HDLParseError        ← 解析错误
├── CIS2HDLMatchError        ← 匹配错误
└── CIS2HDLConfigError       ← 配置错误

> **现状核实（2026-08-07，exceptions.py）**：以上为代码中的实际异常层次。早期设计稿中的细分子类（`DSNParseError`/`OLBParseError`、`NoMatchFoundError`/`AmbiguousMatchError`、`ValidationError`、`DiagnosticError`、`GenerationError` 等）**未在代码中落地**，异常统一收敛到上述三个子类；诊断模块按 5.1a 契约实现，不依赖细分子类。
```

### 5.1a 诊断器开发规范（新增）

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

### 5.2 处理原则

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

## 6. 日志规范

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

## 7. 测试规范

### 7.1 测试金字塔

```
        ┌──────┐
        │ E2E  │  少量端到端测试
       ┌┴──────┴┐
       │  Int.  │  模块集成测试
      ┌┴────────┴┐
      │   Unit   │  大量单元测试
      └──────────┘
```

### 7.2 测试结构

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

### 7.3 测试命名

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

## 8. 总体结构框架设计规范

### 8.1 包结构原则

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

> **现状核实（2026-08-07）**：上表 core/generator/、core/version/、core/layout/、cli/ 四项为规划结构，**均未实施**——实际生成层为 `core/writer/`（WriterRegistry，见 BACKEND_DESIGN §5），CLI 入口走 `cis2hdl/__main__.py`（`python -m cis2hdl convert`），不存在独立 cli/ 目录。实际目录：cis2hdl/{config,core,gui,utils}；core/{parser,matcher,writer,validator,ir,engine,db,diagnostics}。

**依赖方向（单向，不可逆）**：

```
config/ ──▶ utils/ ──▶ core/ ◀── gui/
                           ◀── cli/
```

### 8.2 模块间通信

- **core ↔ gui**：仅通过 `ConversionEngine` 类
- **core 内部**：各层通过 IR 数据模型通信
- **gui 内部**：通过 Qt 信号/槽机制

### 8.3 新增模块检查清单

每次新增模块时，必须确认：

- [ ] 是否放在正确的包下（core / gui / utils；CLI 走 `__main__.py`，无独立 cli/ 目录）
- [ ] 是否遵循基类-注册模式
- [ ] 是否已有可复用的函数/类（先搜索再开发）
- [ ] IR 模型是否需要扩展
- [ ] 依赖方向是否正确（无循环依赖）
- [ ] 设计文档 `design/` 是否已更新

### 8.4 UI 设计规范引用（Anthropic Token 体系）

所有前端 GUI 开发必须遵循 `specs/UI_DESIGN_SPEC.md` v3.0（基于 Anthropic Design Language）。

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
