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
