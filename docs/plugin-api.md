# CIS2HDL 插件接口文档（Plugin API）

> 版本：S8（2026-08-17）｜依据：`docs/S2-plugin-base-design.md` + S3 输入插件化 + S4 匹配插件化 + S5 美化插件化 + S6 输出插件化 + S8 测试插件化｜框架：pluggy 1.6.0
> 铁律：**默认 profile 行为与 legacy 完全等价**（FR9，字节级 diff 验证，含全数据源 HG5015）；**run_verification 不在 convert() 内调用**（S8 独立入口 `cis2hdl verify`）

---

## 1. 插件机制总览

CIS2HDL 转换管线插件化：6 阶段管线（Diagnose→Parse→Scan→Match→Validate→Generate）
中，5 处阶段入口改为**钩子调用**（pluggy），插件按 `pipeline.yaml` 配置组合启用。
插件未处理（返回 False/None）时引擎**自动回退 legacy 实现**（NFR3 降级）。

```
pipeline.yaml ──► PluginManager（pluggy）
                     ├─ ① 扫描内置插件（cis2hdl/plugins/<stage>/*.py）
                     ├─ ② 按 cfg 过滤启用（enabled_by_cfg）
                     ├─ ③ 实例化（resolve_params 从 yaml 注入参数）
                     ├─ ④ 校验（hookspec 签名校验 + check_pending）
                     ├─ ⑤ 排序（外部先注册、内置逆 yaml 序 → LIFO 反转保顺序）
                     └─ ⑥ 执行（pm.hook.<name>(ctx=ctx)）
                          └─ 任一插件返回真值 → 接管；否则 fallback legacy
```

## 2. 核心概念

| 概念 | 说明 |
|------|------|
| **Hookspec** | 宿主定义的钩子契约（`PipelineHooks` 类），`@hookspec` 标记 |
| **Hookimpl** | 插件的钩子实现，`@hookimpl` 标记，签名须与 spec 兼容 |
| **PluginSpec** | 插件元信息（name/stage/description/cls/param_section/params/writes_keys） |
| **ConversionContext** | 插件间唯一通信通道（`ctx`），承载全部阶段产物 |
| **PluginManager** | 生命周期管理（发现/过滤/实例化/排序/执行/清理/降级） |
| **PluginHost** | 引擎内钩子调用器（统一 handled/fallback 语义） |

## 3. 钩子契约（PipelineHooks，7 个）

所有 hook `firstresult=False`（多插件链式协作）。项目名 `"cis2hdl"`。

| Hook | 阶段 | 签名 | 返回语义 | 接入点 |
|------|------|------|---------|--------|
| `load_input` | 输入 | `(ctx) -> bool\|None` | True=完成输入装载；False/None=回退 legacy 内联解析 | convert() Stage2 |
| `match_components` | 匹配 | `(ctx) -> bool\|None` | True=完成匹配；False/None=回退 `_stage_match` | convert() Stage4 |
| `apply_manual_overrides` | 手动干预 | `(ctx) -> bool\|None` | True=完成；False/None=回退 `_apply_phase14_matching` | convert() 引脚注入后 |
| `beautify` | 美化 | `(ctx) -> bool\|None` | 美化钩子链（按 yaml 顺序）；S5 迁入逻辑 | convert() Stage6 前 |
| `write_output` | 输出 | `(ctx) -> list[Path]\|None` | 返回写出的文件路径；False/None=回退 `_stage_generate` | convert() Stage6 |
| `write_report` | 报告 | `(ctx) -> list[Path]\|None` | 返回写出的报告路径；False/None=回退 `_legacy_reports` | convert() 报告段 |
| `run_verification` | 测试 | `(ctx) -> list[str]\|None` | 验证结果（S8 接入，convert() 内不调用） | S8 独立入口 |

### hookspec 定义（cis2hdl/plugins/hookspecs.py）

```python
from pluggy import HookspecMarker
hookspec = HookspecMarker("cis2hdl")

class PipelineHooks:
    @hookspec(firstresult=False)
    def load_input(self, ctx: ConversionContext) -> bool | None: ...
    # ...（match_components / apply_manual_overrides / beautify /
    #      write_output / write_report / run_verification 同上模式）
```

## 4. 编写一个插件

### 4.1 最小插件（输入阶段，S3 真实现示例）

输入插件通过构造注入的 `engine` 编排调用引擎子步骤（薄包装，不重写解析
逻辑）；写 `ctx.ir`（PluginSpec.writes_keys 须声明 `("ir",)`）；返回 True
表示接管解析。S3 内置 5 个真实现：`edif`/`dsn`（解析编排器）、`cross_ref`/
`pstxnet`/`pstchip`（增量）。

```python
# cis2hdl/plugins/input/my_format.py
from typing import Any

from cis2hdl.plugins.hookspecs import hookimpl
from cis2hdl.plugins.context import ConversionContext
from cis2hdl.plugins.spec import PluginSpec

class MyFormatPlugin:
    """自定义格式解析（示例）：编排引擎子步骤，写 ctx.ir。"""

    def __init__(self, engine: Any = None, **params):
        # engine 由 PluginManager 构造注入（resolve_params 检测签名含 engine）
        self.engine = engine
        self.params = params

    @hookimpl
    def load_input(self, ctx: ConversionContext) -> bool | None:
        if ctx is None or ctx.ir is not None:
            return False              # 已被其他解析插件接管
        if self.engine is None:
            return False              # 未处理 → legacy fallback
        input_path = ctx.input_files[0] if ctx.input_files else None
        if input_path is None:
            return False
        design = self.engine._stage_parse(input_path, ctx.report, None)
        if design is None:
            return False
        ctx.ir = design               # 写 ctx.ir（writes_keys 声明）
        self.engine._log_parse_statistics(design)
        # 可选：cross_ref/pst 增量委托（见 edif 插件编排语义）
        return True                   # 已接管

    def cleanup(self) -> None:
        """可逆卸载（Cordis unload 理念）：清理副作用。"""
        self.engine = None
        self.params = {}


PLUGIN = PluginSpec(
    name="my_format",
    stage="input",
    description="自定义格式解析（示例）",
    cls=MyFormatPlugin,
    module=__name__,
    writes_keys=("ir",),
    builtin=True,
)
```

S3 编排语义（FR9 关键）：
- **解析编排器**（`edif`/`dsn`）：P0-D2 EDIF 优先 + `_stage_parse` + 页统计；
  对**未启用**的增量插件做内联补偿（`cross_ref` → `_load_cross_ref_csv`；
  `pstxnet`/`pstchip` → `_load_pst_files(keys=..., log_summary=False)`）。
- **增量插件**（`cross_ref`/`pstxnet`/`pstchip`）：在 `ctx.ir` 就绪后执行，
  原地增强 `design.metadata`（component_catalog / pst_data）。
- **引擎 post-chain**：插件链全部执行后 `_finalize_plugin_input` 统一做
  PST 汇总 + catalog 重建 + `_last_*` 副作用——保证任意含 edif 的 profile
  与 legacy 字节等价。

### 4.2 注册到插件目录

- 内置插件：文件放 `cis2hdl/plugins/<stage>/<name>.py`，模块名 = 插件名；
  `__init__.py` 汇总 `_SPECS`（`PluginSpec` 列表，含 cls/param_section 等）。
- 外部插件：pyproject.toml entry points group `cis2hdl.plugins`，
  格式 `name = module.path:PLUGIN`。

### 4.1b 匹配阶段插件（S4，FR2/FR3）

匹配插件链（`match_components` / `apply_manual_overrides` 钩子）实现
"链首编排 + 其余跳过"语义（FR9 默认等价 + FR2 独立启停）：

```python
# cis2hdl/plugins/match/exact.py（结构示意；fuzzy/passive/fallback 同构）
from cis2hdl.plugins.hookspecs import hookimpl
from cis2hdl.plugins.context import ConversionContext
from cis2hdl.plugins.spec import PluginSpec

class ExactMatchPlugin:
    """exact（优先级 1）：链首启用时 = 阶段编排器（委托 legacy 管线）。"""

    def __init__(self, engine=None, weights=None, prefix_scope=None,
                 thresholds=None, **kw):
        self.engine = engine                # PluginManager 注入
        self.weights = weights              # yaml match.weights
        self.prefix_scope = prefix_scope    # yaml match.prefix_scope
        self.thresholds = thresholds        # yaml match.thresholds

    @hookimpl
    def match_components(self, ctx: ConversionContext) -> bool | None:
        if ctx is None or ctx.matches:
            return False                    # 链中先前插件已接管 → 跳过
        if ctx.ir is None or ctx.hdl_db is None or self.engine is None:
            return False                    # 前置未就绪 → 回退 legacy
        # ① 应用 yaml 参数（thresholds/weights，finally 恢复）
        # ② 按需收窄候选库副本（prefix_scope，默认空 = 原样）
        # ③ engine.run_match_stage(...) → ctx.matches（= legacy 等价）
        return True

PLUGIN = PluginSpec(name="exact", stage="match", cls=ExactMatchPlugin,
                    module=__name__,
                    param_fields=("weights", "prefix_scope", "thresholds"),
                    writes_keys=("matches",), builtin=True)
```

六个 match 插件：`matcher_pipeline`（显式编排）、`exact`/`fuzzy`/`passive`/
`fallback`（参数化阶段插件，任一单独启用即运行完整匹配阶段）、
`manual_overrides`（FR3 手动干预，默认不启用）。

### 4.1c 美化阶段插件（S5，FR4）

美化插件链（`beautify` 钩子）实现"**配置编排**"语义：插件**不重写美化逻辑**
（writer 模块保持原实现），而是在 generate 之前把 yaml `beautify.params`
（RoutingConfig，S1 K1 复用）**完整应用**到全局 `config.routing` ——
CSAWriter 读取该对象，内置美化逻辑（overlap_resolver / gnd_cluster_planner
/ wire_simplifier / wire_layout / text_layout）按配置开关在正确阶段执行
（顺序由 writer 内部保证）。

```python
# cis2hdl/plugins/beautify/overlap_resolve.py（结构示意；其余 5 个同构）
from cis2hdl.plugins.hookspecs import hookimpl
from cis2hdl.plugins.context import ConversionContext
from cis2hdl.plugins.spec import PluginSpec

class OverlapResolvePlugin:
    """防重叠（D2 检测 + R5 避让；overlap_resolver 编排）。"""

    def __init__(self, engine=None, check=False, resolve=True,
                 avoid_margin=50, **kw):
        self.engine = engine                # PluginManager 注入
        self.enabled = bool(resolve)        # enabled 门 = overlap.resolve
        self.order_trace: list[str] = []

    @hookimpl
    def beautify(self, ctx: ConversionContext) -> bool | None:
        self.order_trace.append("overlap_resolve")
        if not self.enabled or self.engine is None:
            return False                    # disabled → 不应用
        self.engine.apply_beautify_params(ctx)  # 完整 params → 全局 config.routing
        ctx.routed_nets = {"applied_plugins": ["overlap_resolve"]}
        return True

PLUGIN = PluginSpec(name="overlap_resolve", stage="beautify",
                    cls=OverlapResolvePlugin, module=__name__,
                    param_section="overlap",
                    param_fields=("check", "resolve", "avoid_margin"),
                    writes_keys=("routed_nets",), builtin=True)
```

六个 beautify 插件及 enabled 门（来自 params）：

| 插件 | param_section | enabled 门 | 默认 |
|------|---------------|-----------|:---:|
| `overlap_resolve` | `overlap` | `overlap.resolve` | ✅ |
| `gnd_cluster` | `gnd_distribution` | `gnd_distribution.enabled` | ➖ |
| `parallel_short` | `gnd_distribution` | `gnd_distribution.parallel_short` | ✅ |
| `three_stage_stub` | `""`（顶层） | `routing.three_stage_stub` | ✅ |
| `wire_simplify` | `wire_simplify` | `wire_simplify.enabled` | ➖ |
| `text_layout` | `text_layout` | `text_layout.enabled` | ➖ |

**为什么是"完整 params 应用"？** legacy（S1 CLI）把 `beautify.params` 全量
写回全局 `cfg.routing`（`cfg_obj.routing = cfg.to_routing_config()`）；writer
美化开关分布在多个子节（如 `wire_simplify.parallel_short`、
`placement.max_passive_move`、`routing.mode`）。完整应用对任意配置都与
legacy 逐字段一致（构造性 FR9 保证），默认 profile 时应用 == RoutingConfig
默认 → no-op。链内任意启用插件应用一次（幂等）；全禁用/空链 → 不应用。

### 4.2 注册到插件目录

- 内置插件：文件放 `cis2hdl/plugins/<stage>/<name>.py`，模块名 = 插件名；
  `__init__.py` 汇总 `_SPECS`（`PluginSpec` 列表，含 cls/param_section 等）。
- 外部插件：pyproject.toml entry points group `cis2hdl.plugins`，
  格式 `name = module.path:PLUGIN`。

### 4.3 在 pipeline.yaml 启用

```yaml
input:
  plugins: [edif, pstxnet, pstchip, my_format]   # 追加你的插件
  params:
    my_format: { enabled: true, option_a: 42 }   # 构造参数
```

## 5. ConversionContext（插件唯一通信通道）

```python
@dataclass
class ConversionContext:
    cfg: PipelineConfig            # S1 PipelineConfig（beautify.params 复用 RoutingConfig）
    profile: str = "default"       # 当前 profile 名
    input_files: list[Path]        # FR1 多输入
    output_dir: Path | None
    ir: DesignIR | None            # Stage2 产物（load_input 写）
    hdl_db: ComponentDB | None     # Stage3 产物（scan 写）
    matches: list[MatchResult]     # Stage4 产物
    manual_overrides: dict         # FR3 手动匹配/强制 mock
    routed_nets: dict | None       # 美化阶段共享
    report: ConversionReport       # 报告聚合
    _locked: set[str]              # 只读守卫内部状态
```

**只读守卫**：插件通过 `PluginSpec.writes_keys` 声明可写字段；PluginHost 在
调用前后快照校验，非声明字段被改动 → warning（strict_ctx=True 时 raise）。
`ctx.writable("ir")` 上下文管理器可临时声明可写。

## 6. PluginManager API

```python
pm = build_plugin_manager(cfg, engine=None)   # 主入口
pm.list_plugins(stage=None) -> list[PluginSpec]   # 已发现插件（S1 白名单替换）
pm.build(cfg, engine=None)                    # 完整组装（幂等）
pm.get_plugin(name) / pm.get_name(plugin)     # 实例查询
pm.hook.<hook_name>(ctx=ctx)                  # 触发钩子链
pm.cleanup() / pm.unregister_all()            # 清理（可逆卸载）
pm.degraded                                   # [(插件名, 错误)] 降级清单（NFR3）
```

## 7. 引擎接入（双模式）

```python
# legacy 模式（默认，FR9 等价基线）
engine = ConversionEngine()                    # _pm=None

# plugin 模式
engine.set_pipeline(pc)                        # 或
report = engine.convert_with_cfg(pc, input, out_dir, **kw)
```

`PluginHost.call(ctx, hook_name, fallback)` 统一语义：
- legacy（`_pm is None`）→ 直接 fallback（零 pluggy 开销）
- plugin → 钩子链；任一真值 → `(True, results)`（fallback 不执行）
- 全部 False/None → fallback → `(False, fallback())`
- hook 异常 → warning + fallback（NFR3 降级）

## 8. 顺序控制（美化钩子链）

pluggy 默认 LIFO（逆序执行）。为保 yaml 顺序：
1. 有序 hook（load_input/match_components/beautify）的 hookimpl **全部默认**
   （tryfirst/trylast 均 False）；
2. `register_ordered`：外部插件先注册 → LIFO 下最后执行；内置插件按
   **reversed(yaml 顺序)** 注册 → LIFO 执行 = yaml 顺序；
3. 未在 cfg 列表中的插件不注册（过滤即禁用）。

## 9. 验证

```bash
# S2 插件基座单测（52 passed）
pytest tests/unit/test_{plugin_manager,hookspecs,context,plugin_order,params}.py -q

# 引擎钩子化（7 passed）
pytest tests/integration/test_engine_hooks.py -q

# 核心验收：plugin vs legacy 字节级等价（2 passed）
pytest tests/e2e/test_plugin_mode_equivalence.py -q

# S3 输入插件化（24 passed + 2 passed）
pytest tests/unit/test_s3_input_plugins.py -q
pytest tests/e2e/test_s3_input_equivalence.py -q

# S4 匹配插件化（29 passed + 6 passed）
pytest tests/unit/test_s4_match_plugins.py -q
pytest tests/e2e/test_s4_match_equivalence.py -q

# S5 美化插件化（30 passed + 4 passed）
pytest tests/unit/test_s5_beautify_plugins.py -q
pytest tests/e2e/test_s5_beautify_equivalence.py -q

# S8 测试插件化（26 passed）
pytest tests/unit/test_s8_test_plugins.py -q

# S8 一键验证（FR6，独立入口）
python -m cis2hdl verify --suite unit          # 实跑 unit 套件
python -m cis2hdl verify --suite qa_package    # QA 结构检查
```

## 10. 输出插件（S6）

| 插件 | hook | 写入文件 | 控制 |
|------|------|---------|------|
| csa/con/xcon/csv/cpc/cpm/cds_lib | `write_output` | 对应格式文件 | `output.files` |
| aesthetic/ioport/mapping/error | `write_report` | 对应报告文件 | `output.reports` |

- 返回值：`list[Path]`（写出的文件路径）；False/None → 引擎回退 legacy。
- 部分组合：禁用插件对应文件不写；`hdl_lib/` 库拷贝恒写（不受插件控制）。
- 例：`output.files: [csa, con]` + `output.reports: [mapping]` → 只写
  csa/con + mapping.csv/top3.txt + 共享 infra。

## 11. 测试插件（S8，FR6）

| 插件 | hook | 运行内容 | 控制 |
|------|------|---------|------|
| unit | `run_verification` | pytest `tests/unit/` | `test.suites` |
| e2e | `run_verification` | pytest `tests/e2e/ tests/integration/` | `test.suites` |
| qa_package | `run_verification` | `scripts/verify_phaseXXI_package.py <交付目录>` 或等价结构检查 | `test.suites` |

- **返回值**：`list[str]`（验证结果/报告行）；**不在 convert() 内调用**
  （S8 独立入口 `python -m cis2hdl verify [--suite ...]` 触发）。
- **插件是运行器**：不重写测试；按 `test.suites` 选择执行 pytest/检查脚本。
- **套件启停**：Manager 按 `spec.name ∈ cfg.test.suites` 过滤注册（未启用
  不注册）；插件运行时再查 `ctx.cfg.test.suites`（双保险）。
- **结果行前缀**：`[PASS]`/`[FAIL]`/`[ERROR]`/`[SKIP]`/`[INFO]`；
  VerificationRunner 依据 `[FAIL]`/`[ERROR]` 判整体失败（退出码 1）。
- 例：`test.suites: [unit, e2e, qa_package]`（默认全开）→ `cis2hdl verify`
  依次运行 3 个套件；`--suite unit` 只跑单元。
- qa_package 交付目录优先序：`ctx.output_dir` → 构造参数 `delivery_dir` →
  项目根常见目录（`output_verify_final`/`output`）；无交付目录 → 等价
  结构检查（`[SKIP]`+`[INFO]`，不判失败）。

## 12. GUI 相关接口（S9，FR10）

GUI 工程工作台（`python -m cis2hdl gui`）经 `PipelineController` 薄层访问
插件系统，**不新增插件 hook**；复用既有 `PluginSpec` 元数据驱动表单：

| PluginSpec 字段 | GUI 用途（gui/v2） |
|----------------|-------------------|
| `name` / `stage` / `description` | PluginCard 展示 + `plugins.<stage>` 启停 |
| `param_section` | 参数源子节：beautify → `beautify.params.<section>`（空 = 顶层 scalar） |
| `param_fields` | 表单字段：`get_plugin_schema(name)` 推断控件类型（bool→QCheckBox / int→QSpinBox / float→QDoubleSpinBox / str→QLineEdit / enum→QComboBox / list→QListWidget / dict→QTreeWidget） |

- **类型推断**基于字段默认值（`isinstance`）+ 已知枚举表（`mode`/
  `net_order`/`un_name_policy`/`mock_text_cmd`，见 `gui/schema.py`）。
- **表单读写**：`controller.current_plugin_params(name)` → dotted path 值；
  `controller.apply_plugin_param(name, path, value)` 写回 cfg（dotted path
  如 `beautify.overlap.resolve` / `match.weights.footprint`）。
- **手动干预（FR3）**：`set_manual_match(refdes, hdl, force_mock)` 写
  `chip_config_gui.yaml`（v2.0 schema，`ManualMatchesConfig.write_yaml`）
  并接线 `match.manual_overrides.file`；`match.mock.prefixes` 承载强制
  mock 前缀（J/T/U/IC）。
- **yaml 双通道**：`gui/yaml_bridge.py`（FormState ↔ cfg ↔ 文本；
  原子写 `save_pipeline_atomic`；冲突检测 `is_text_in_sync`）——yaml 权威。
