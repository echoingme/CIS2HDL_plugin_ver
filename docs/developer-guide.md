# CIS2HDL 开发者指南

> 面向 CIS2HDL 插件化改造（S0–S8）的开发者文档。
> 本文件随阶段演进持续更新；当前覆盖 **S1 配置层**。

---

## S1 配置层（pipeline.yaml / PipelineConfig / ProfileManager / CLI）

### 1. 权威链

```
pipeline.yaml（唯一权威）
    ↓ --profile <name> 覆盖（ProfileManager 合并增量）
    ↓ 旧 CLI 参数覆盖（S10 前保留，含 deprecation 警告）
    ↓ to_routing_config() 兼容桥
RoutingConfig / Config 单例（引擎消费，零改动）
    ↓
ConversionEngine.convert(...)
```

- **铁律（FR9）**：默认 profile 行为与基线（Phase XXIII，929 passed）**完全等价**。
  任何"新字段/新默认值"都需先比对 `RoutingConfig` 默认值。
- **ConversionEngine 不动**：引擎只消费 `RoutingConfig` / `Config` 单例；
  S1 全部桥接在 `cis2hdl/cli.py` 完成。

### 2. pipeline.yaml 结构（顶层七节）

| 节 | 内容 | 引擎消费（S1） |
|----|------|----------------|
| `profile` | 当前生效 profile 名 | 否（ProfileManager 用） |
| `input` | hdl_lib / extra_hdl_libs / plugins | ✅ 库路径 → CLI 传参 |
| `match` | plugins / weights / prefix_scope / thresholds / mock / manual_overrides | ✅ manual_overrides → chip_config/manual_matches/export_unmatched |
| `beautify` | plugins + **params**（= RoutingConfig 全量） | ✅ params → to_routing_config() |
| `output` | files / reports | 否（S6 驱动；S1 承载+校验+查重） |
| `test` | suites | 否（S8 驱动） |
| `engine` | output_dir / max_workers / benchmark | ✅ → cfg.app / CLI 输出目录 |

**关键设计（K1）**：`beautify.params` **直接复用 `RoutingConfig`**——
默认值/`from_dict` 子节合并逻辑全部继承，迁移零成本；等价性可逐字段断言。

**序列化规则**：
- 顶层标量（mode/lane_pitch/...）收在 `beautify.params.routing` 下；
- 17 个子节（text_layout/overlap/...）与 `routing` 平级；
- **不出现** `manual_matches`/`chip_config`/`export_unmatched`
  （已迁移到 `match.manual_overrides`；`to_routing_config()` 负责回填）。

### 3. Python API（PipelineConfig）

```python
from pathlib import Path
from cis2hdl.core.pipeline_config import PipelineConfig
from cis2hdl.core.config import RoutingConfig

# 加载/保存
cfg = PipelineConfig.from_yaml(Path("pipeline.yaml"))
cfg.to_yaml(Path("out.yaml"))                      # 原子写（临时文件 + os.replace）

# 兼容桥（FR9 核心）
rc = cfg.to_routing_config()                       # → RoutingConfig（引擎消费）
cfg2 = PipelineConfig.from_routing_config(rc)      # ← RoutingConfig 反向

# 查重辅助
cfg.plugin_combos()  # {stage: frozenset(plugins)}，顺序无关

# 参数工具
from cis2hdl.core.pipeline_config import (
    deep_eq_params, params_to_routing, routing_to_params, routing_params_deep_diff,
)
```

### 4. ProfileManager（查重 / 导入导出）

**目录布局**（内置与自定义同目录，`builtin: true` 区分）：

```
cis2hdl_plugin_ver/profiles/
├── default.yaml        # 内置只读（= pipeline.yaml 默认行为，FR9）
├── max-beauty.yaml     # 内置只读
├── fast.yaml           # 内置只读
├── match-only.yaml     # 内置只读
└── <user>.yaml         # 用户自定义（原子写）
```

**CLI 子命令**（`python -m cis2hdl profile ...`）：

```bash
python -m cis2hdl profile list                    # 表格：NAME / BUILTIN / DESCRIPTION
python -m cis2hdl profile show default            # yaml.dump 完整合并后配置
python -m cis2hdl profile create my-x [--from-file pipeline.yaml] [--overwrite]
python -m cis2hdl profile delete my-x
python -m cis2hdl profile export my-x -o out.yaml
python -m cis2hdl profile import other.yaml [--rename NEW]
```

退出码：`0` 成功；`1` 转换/运行错误；`2` profile 查重/校验失败；
`3` 内置只读/禁止操作。

**Python API**：

```python
from cis2hdl.core.profile_manager import ProfileManager, DuplicateProfileError

pm = ProfileManager()                     # 默认 <项目根>/profiles
cfg = pm.get("max-beauty")                # 合并 default + 增量 → 完整 PipelineConfig
pm.create("my-x", cfg, overwrite=False)   # 查重：duplicate → DuplicateProfileError
pm.delete("my-x")                         # 内置 → ProfileReadOnlyError
out = pm.export("my-x")                   # builtin→false、去 created
name = pm.import_file(Path("a.yaml"))     # 校验链：结构/白名单/类型/路径安全/schema
diff = pm.diff(cfg_a, cfg_b)              # 首个差异阶段（组合 set 比较 + 参数深度）
```

**查重规则**（§5.4）：
- 插件组合：`set` 比较逐阶段，**顺序无关**；
- 参数：深度比较，list **顺序敏感**（`gnd_power_lastpin_offset` 等有序参数），
  float 精确 `==`（S1 决策 6）；
- 组合同、参数异：允许保存，`pm.last_note` 记录提示；
- 名称冲突：trim + `casefold()`，同名 → 非 overwrite 拒绝。

**导入白名单**：S1 用内置常量表 `BUILTIN_PLUGIN_NAMES`（见
`cis2hdl/core/profile_manager.py`）；S2 起改由 `PluginManager.list_plugins()` 提供。

### 5. CLI 用法（convert）

```bash
python -m cis2hdl convert in.dsn                              # 读 ./pipeline.yaml
python -m cis2hdl convert in.dsn --profile max-beauty         # 切 profile
python -m cis2hdl convert in.dsn --profile fast --output out  # profile + 旧参数叠加
python -m cis2hdl convert in.dsn --pipeline my.yaml           # 显式配置文件
```

**旧 CLI 参数**（23 个，S10 前保留）：`--output / --hdl-lib / --extra-hdl-lib /
--benchmark / --max-workers / --routing / --nonuniform-tracks / --net-order /
--wire-simplify / --manual-matches / --chip-config / --export-unmatched /
--text-layout / --power-ic / --aesthetic / --gnd-distribute / --rotate-passives /
--ioport-edge / --ioport-audit / --use-net-name / --no-mirror-normalize /
--no-report / --cross-page-opt`

每个参数映射到 `pipeline.yaml` 对应字段并打印一次 deprecation 警告
（stderr，格式 `[deprecation] ...`）。完整迁移对照表见
`docs/S1-config-design.md` §6.3。

> 注意：`--aesthetic` 是 8 字段复合置位（保 FR9 严格等价），**不等价于**
> `--profile max-beauty`（后者额外开启 wire_simplify 等）。详见设计 §6.3。

### 6. 等价性验证（FR9）

- 单元级：`tests/unit/test_pipeline_config.py`——`from_routing_config(rc)
  .to_routing_config() == rc`；pipeline.yaml 与旧 routing.yaml 的 routing 字段全等。
- e2e 级：`tests/e2e/test_default_profile_equivalence.py`——同一真实输入
  （RTL8367RB，5 页/1687 输出文件）分别走旧/新路径，归一化输出目录与时间戳后
  **字节级 diff 为空**。

### 7. 路径解析约定

`input.hdl_lib` / `extra_hdl_libs` / `engine.output_dir` 等路径**相对当前工作
目录（CWD）解析**，与旧 CLI 一致（S1 决策 2）。如需相对 pipeline.yaml 所在
目录的可移植解析，属后续增强（设计 §9 待确认项）。

### 8. S1 测试速查

```bash
python -m pytest tests/unit/test_pipeline_config.py        # 19
python -m pytest tests/unit/test_profile_manager.py        # 39
python -m pytest tests/unit/test_cli_legacy_mapping.py     # 50
python -m pytest tests/e2e/test_default_profile_equivalence.py  # 5（slow）
```

---

# S2 插件基座（2026-08-17）

> 阶段目标：pluggy 插件基座落地（hookspecs + PluginManager + ctx + 引擎钩子化），
> 默认 profile 行为与 legacy 完全等价（字节级 diff 验证）。
> 设计：`docs/S2-plugin-base-design.md`（980 行）｜接口：`docs/plugin-api.md`

## 2.1 新增模块

| 模块 | 职责 |
|------|------|
| `cis2hdl/plugins/hookspecs.py` | PipelineHooks 7 hook 契约（load_input/match_components/apply_manual_overrides/beautify/write_output/write_report/run_verification） |
| `cis2hdl/plugins/context.py` | ConversionContext dataclass + 只读守卫（writable/快照/校验） |
| `cis2hdl/plugins/spec.py` | PluginSpec（name/stage/description/cls/param_section/params/writes_keys/builtin） |
| `cis2hdl/plugins/manager.py` | PluginManager 生命周期（发现/过滤/实例化/逆序注册/降级/清理）+ build_plugin_manager |
| `cis2hdl/plugins/discover.py` | scan_builtin_plugins（pkgutil 目录扫描）+ load_entrypoint_plugins |
| `cis2hdl/plugins/params.py` | resolve_params（从 PipelineConfig 构造插件构造参数） |
| `cis2hdl/plugins/ordering.py` | register_ordered（逆序注册 → LIFO 反转保 yaml 顺序）+ assert_order |
| `cis2hdl/plugins/_stubs.py` | 内置插件 stub 工厂（input/beautify 占位返回 False 回退 legacy） |
| `cis2hdl/plugins/input/` | EDIF/DSN/CrossRef/pstxnet/pstchip 占位插件（S2） |
| `cis2hdl/plugins/match/` | matcher_pipeline/manual_overrides 薄包装（真委托，S2） |
| `cis2hdl/plugins/beautify/` | overlap/gnd/parallel/stub/simplify/text_layout 顺序占位（S2，S5 迁入逻辑） |
| `cis2hdl/plugins/output/` | default_writer/reports 薄包装（真委托，S2） |
| `cis2hdl/core/engine/plugin_host.py` | PluginHost 统一钩子调用器（handled/fallback 语义） |
| `scripts/s2_extract_legacy.py` | legacy 内联块提取工具（_legacy_load_input/_legacy_reports） |

## 2.2 引擎钩子化（双模式）

`ConversionEngine` 5 处钩子调用点（legacy `_pm=None` 时零 pluggy 开销）：

| 钩子 | 调用点 | fallback |
|------|--------|---------|
| `load_input` | convert() Stage2 | `_legacy_load_input`（原内联解析块） |
| `match_components` | convert() Stage4 | `_stage_match` + `_append_power_symbol_matches` |
| `apply_manual_overrides` | 引脚注入后 | `_apply_phase14_matching` |
| `beautify` | Stage6 前 | `None`（S5 迁入逻辑） |
| `write_output` | Stage6 | `_stage_generate` |
| `write_report` | 报告段 | `_legacy_reports` |

API：`set_pipeline(cfg)` / `convert_with_cfg(cfg, input, out_dir, **kw)`。

## 2.3 验证

```bash
pytest tests/unit/test_{plugin_manager,hookspecs,context,plugin_order,params}.py -q   # 52
pytest tests/integration/test_engine_hooks.py -q                                      # 7
pytest tests/e2e/test_plugin_mode_equivalence.py -q                                   # 2（字节级等价）
```

# S3 输入插件化（FR1，2026-08-17）

> 阶段目标：把 conversion_engine.py 的 `_legacy_load_input`（原内联解析块：
> EDIF 解析 + ComponentCatalog 重建 + PST 加载 + 实例注入）拆分为 **5 个可
> 独立启用的输入插件**（edif/dsn/cross_ref/pstxnet/pstchip），默认 profile
> 行为与 legacy **完全等价**（FR9 字节级 diff 验证，含全数据源 HG5015）。

## 3.1 五个输入插件

| 插件 | 默认 | 职责（薄包装编排，不重写解析逻辑） |
|------|------|------------------------------------|
| `edif` | ✅ | **默认解析编排器**：P0-D2 EDIF 优先（`.dsn`+禁用 DSN 元件源 → 同名 `.EDF`）+ `_stage_parse`（ParserRegistry 按扩展名选 EDIFParser/DSNParser）+ 页统计；cross_ref/pst 子步骤按"增量插件是否启用"委托或内联 |
| `dsn` | ➖ | 直接 DSN 解析编排（不走 EDIF 优先；配合 `use_dsn_components`）；其余编排同 edif |
| `cross_ref` | ➖ | 载入 `<input>.CSV/.csv` → ComponentCatalog + 坐标注入（提高转换质量） |
| `pstxnet` | ✅ | 载入 `pstxprt.dat`（PstxnetParser，INS→refdes 桥接）+ `pstxnet.dat`（PstxnetNetlistParser，pin→net 数据源） |
| `pstchip` | ✅ | 载入 `pstchip.dat`（PstchipParser，JEDEC_TYPE/VALUE/pins + 真实引脚名） |

组合由 `pipeline.yaml → input.plugins` 控制；默认 `[edif, pstxnet, pstchip]`。

## 3.2 引擎重构（纯代码搬移，FR9 等价基座）

`_legacy_load_input` 拆分为子步骤方法，行为逐字节不变：

| 方法 | 原位置 | 职责 |
|------|--------|------|
| `_resolve_parse_path(input_path)` | P0-D2 块 | `.dsn`+禁用 DSN 元件源 → 同名 `.EDF/.edf` 兄弟文件 |
| `_log_parse_statistics(design)` | 页统计块 | 页内 refdes 异常统计（ConversionLogger） |
| `_load_cross_ref_csv(design, input_path)` | Stage 2.5 | CSV → catalog + 坐标注入；返回 `(cross_ref_map, catalog)` |
| `_load_pst_files(design, input_path, keys=None, log_summary=True)` | Stage 2.3 | pstchip/pstxprt/pstxnet 增量载入（keys 过滤 + 合并进 pst_data） |
| `_rebuild_from_catalog(design, report)` | v0.5.0 大块 | catalog 驱动实例重建（power 保留/恢复、EDIF 占位替换、PST JEDEC 注入、cache 失效、report 统计、readiness） |
| `_log_pst_summary(design, input_path)` | PST 汇总 | 单条 PST 汇总事件（固定序 pstchip/pstxprt/pstxnet） |
| `_finalize_plugin_input(design, report, input_path)` | 新增 | **plugin post-chain 收尾**：PST 汇总 + catalog 重建 + `_last_cross_ref_map`/`_last_catalog` 副作用 |

## 3.3 plugin 模式接管语义

```
convert() Stage 2:
  handled, _res = host.call(ctx, "load_input", fallback=_legacy_load_input)
  if handled and ctx.ir is not None:
      design = ctx.ir
      self._finalize_plugin_input(design, report, input_path)   # S3 post-chain
  elif not handled:
      design = _res                                            # legacy 全链
  else:                                                        # 异常插件兜底
      design = self._legacy_load_input(...)
```

- `edif`/`dsn`（解析编排器）返回 True（ctx.ir 已写）；`cross_ref`/`pstxnet`/
  `pstchip`（增量）在 ctx.ir 就绪后执行并返回 True；无解析器时全部返回 False
  → 引擎回退 legacy 全链（NFR3）。
- **编排器补偿（FR9 关键）**：edif/dsn 对**未启用**的增量插件做内联补偿——
  `cross_ref` 未启用 → 内联 `_load_cross_ref_csv`；`pstxnet`/`pstchip` 未启用
  → 内联对应文件。因此**任意含 edif 的 profile 输出与 legacy 等价**；启用某
  增量插件则改由该插件执行对应子步骤（谁干活可变，结果不变）。
- **事件流一致**：PST 汇总 ConversionLogger 事件由 post-chain 统一输出一次
  （固定序），与 legacy 单条逐字节一致——错误日志文件字节等价的前提。

## 3.4 ctx 契约与副作用

- 插件写 `ctx.ir`（PluginSpec.writes_keys 声明 `("ir",)`）；增量插件原地
  修改 `design.metadata`（可变对象，守卫不拦截）。
- 副作用暴露给后续阶段（与 legacy 一致）：
  - `engine._last_cross_ref_map`：CrossRefParser 结果（match 钩子/CSA 属性）。
  - `engine._last_catalog`：ComponentCatalog（低置信度日志 value 补全）。
- `ConversionLogger` 事件顺序 = legacy（SOURCE → PARSE → XREF → PST → INST），
  保证 `*_errors.log/.txt` 字节等价。

## 3.5 验证

```bash
pytest tests/unit/test_s3_input_plugins.py -q                     # 24（独立启停 + 组合 + post-chain）
pytest tests/e2e/test_s3_input_equivalence.py -q                  # 2（HG5015 字节级等价，默认 + 全增量）
pytest tests/e2e/test_plugin_mode_equivalence.py -q               # 2（RTL8367RB 字节级等价，S2 保绿）
pytest -q                                                         # 1121 passed / 17 skipped / 0 failed
```

铁律（FR9）：默认 profile 的 plugin 模式输出与 legacy 逐文件字节级 diff 为空。
