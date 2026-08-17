# CIS2HDL 插件接口文档（Plugin API）

> 版本：S3（2026-08-17）｜依据：`docs/S2-plugin-base-design.md` + S3 输入插件化｜框架：pluggy 1.6.0
> 铁律：**默认 profile 行为与 legacy 完全等价**（FR9，字节级 diff 验证，含全数据源 HG5015）

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
```
