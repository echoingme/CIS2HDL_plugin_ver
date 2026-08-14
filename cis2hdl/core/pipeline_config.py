"""PipelineConfig — 插件化转换配置（权威，S1 配置层）。

设计依据：``docs/S1-config-design.md`` §3.1/§3.2/§3.3（架构师高见远交付）。

顶层七节：``profile / input / match / beautify / output / test / engine``，
结构与 ``pipeline.yaml`` 1:1（snake_case）。

关键决策（K1）：
  ``beautify.params`` 直接复用 :class:`RoutingConfig` —— 默认值/``from_dict``
  子节合并逻辑全部继承，迁移零成本；等价性可逐字段断言；引擎侧
  ``to_routing_config()`` 直接可用（ConversionEngine 零改动，FR9）。

兼容桥：
  :meth:`PipelineConfig.from_routing_config` / :meth:`PipelineConfig.to_routing_config`
  在 yaml 外层"插件组合视图"与引擎消费视图（RoutingConfig）之间双向映射。

yaml 读写约定：一律 ``yaml.safe_load``；写一律原子（临时文件 + ``os.replace``）；
UTF-8。
"""

from __future__ import annotations

import copy
import dataclasses
import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

from .config import RoutingConfig

__all__ = [
    "PipelineConfig",
    "InputSection",
    "MockSection",
    "ManualOverrideSection",
    "MatchSection",
    "BeautifySection",
    "OutputSection",
    "TestSection",
    "EngineSection",
    "atomic_write_text",
    "deep_eq_params",
    "params_to_routing",
    "routing_to_params",
    "routing_params_deep_diff",
]

# ─────────────────────────────────────────────────────────────────────────────
# 常量：RoutingConfig 字段分类（序列化/反序列化用）
# ─────────────────────────────────────────────────────────────────────────────

#: 17 个子节（dataclass 嵌套字段）——yaml 中与 ``routing`` 平级。
ROUTING_SUBSECTION_KEYS: frozenset[str] = frozenset({
    "text_layout", "overlap", "power_ic", "aesthetic", "report", "placeholder",
    "ioport", "mirror", "gnd_distribution", "temp_lib", "wire_simplify",
    "pin_audit", "attribute", "matching", "placement", "net_name",
})

#: 引擎消费的顶层标量——yaml 中统一收在 ``params.routing`` 下（§3.3 映射表）。
#: 已迁移字段（manual_matches/export_unmatched/chip_config）**不在**其中——
#: 见 MIGRATED_SCALAR_KEYS（设计 §4 注）。
ROUTING_SCALAR_KEYS: frozenset[str] = frozenset({
    "mode", "lane_pitch", "grid", "detour_stubs", "use_edif_wires",
    "cross_page_opt", "fallback_to_p0", "nonuniform_tracks", "net_order",
    "stub_lead", "lead_differentiate", "lead_diff_min_gap", "max_detour",
    "edge_clearance", "three_stage_stub",
})

#: 已迁移到 ``match.manual_overrides`` 的字段——序列化 params 时**不出现**
#: （设计 §4 注：beautify.params 中不出现 manual_matches/chip_config/
#: export_unmatched；``to_routing_config()`` 负责回填）。
MIGRATED_SCALAR_KEYS: frozenset[str] = frozenset({
    "manual_matches", "export_unmatched", "chip_config",
})

#: 插件组合比较的 5 个阶段（设计 §5.3；顺序 = 展示顺序）。
STAGES: tuple[str, ...] = ("input", "match", "beautify", "output", "test")


def atomic_write_text(path: Path, text: str) -> None:
    """原子写文本文件：临时文件 + ``os.replace``（跨平台；权限 0644）。

    ``ProfileManager._atomic_write`` 与 :meth:`PipelineConfig.to_yaml` 共用
    本实现，保证 S1 全部 yaml 写出均为原子操作（无半成品残留）。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def deep_eq_params(a: Any, b: Any) -> bool:
    """参数深度比较（float 精确 ``==``，S1 决策 6）。

    - dataclass → asdict 后递归
    - dict 递归（key 集合相同 + 逐值比较）
    - list/tuple **顺序敏感**（``gnd_power_lastpin_offset`` 等有序参数保持顺序）
    - 基本类型直接 ``==``
    """
    if dataclasses.is_dataclass(a) and dataclasses.is_dataclass(b):
        return deep_eq_params(asdict(a), asdict(b))
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(deep_eq_params(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return False
        return all(deep_eq_params(x, y) for x, y in zip(a, b))
    return a == b


# 内部别名（保持与既有调用一致的私有命名）
_deep_eq = deep_eq_params


def _subsection_field_names(section_name: str) -> set[str]:
    """返回 RoutingConfig 某子节的合法字段名集合（未知字段过滤用）。"""
    cls = type(getattr(RoutingConfig(), section_name))
    return {f.name for f in dataclasses.fields(cls)}


def _filter_section_dict(section_name: str, value: dict) -> dict:
    """过滤子节 dict 到合法字段（未知字段忽略，避免 ``replace`` TypeError）。"""
    allowed = _subsection_field_names(section_name)
    return {k: v for k, v in value.items() if k in allowed}


def params_to_routing(params: dict) -> RoutingConfig:
    """从 yaml ``beautify.params`` dict 构造 RoutingConfig（§3.3 映射）。

    - ``params.routing`` 子 dict → 顶层标量（mode/lane_pitch/...）
    - 17 个子节 key → 对应子节 dataclass（未知字段过滤）
    - 其余未知 key → 忽略
    """
    flat: dict[str, Any] = {}
    for key, value in (params or {}).items():
        if key == "routing" and isinstance(value, dict):
            flat.update(value)
        elif key in ROUTING_SCALAR_KEYS:
            flat[key] = value
        elif key in ROUTING_SUBSECTION_KEYS and isinstance(value, dict):
            flat[key] = _filter_section_dict(key, value)
    return RoutingConfig.from_dict(flat)


def apply_params(rc: RoutingConfig, params: dict | None) -> RoutingConfig:
    """在 ``rc`` 之上增量合并 params dict（profile 文件用，设计 §5.3 步骤 ④）。

    - ``params.routing`` 标量块 → 覆盖顶层标量
    - 顶层标量 key（mode 等）→ 直接覆盖（兼容宽松输入）
    - ``<子节>: {字段...}`` → ``dataclasses.replace`` 覆盖子节字段
    - 已迁移字段（manual_matches/chip_config/export_unmatched）忽略
    - 未知 key 忽略；返回**新对象**（不修改入参 rc）
    """
    merged = copy.deepcopy(rc)
    if not isinstance(params, dict):
        return merged
    for key, value in params.items():
        if key == "routing" and isinstance(value, dict):
            for scalar_key, scalar_val in value.items():
                if (
                    hasattr(merged, scalar_key)
                    and scalar_key not in ROUTING_SUBSECTION_KEYS
                    and scalar_key not in MIGRATED_SCALAR_KEYS
                ):
                    setattr(merged, scalar_key, scalar_val)
        elif key in ROUTING_SUBSECTION_KEYS and isinstance(value, dict):
            sub = getattr(merged, key)
            kwargs = _filter_section_dict(key, value)
            if kwargs:
                setattr(merged, key, replace(sub, **kwargs))
        elif (
            hasattr(merged, key)
            and key not in ROUTING_SUBSECTION_KEYS
            and key not in MIGRATED_SCALAR_KEYS
        ):
            # 顶层标量直接覆盖（宽松输入兼容）
            setattr(merged, key, value)
        # 其余（含 MIGRATED_SCALAR_KEYS / 未知）忽略
    return merged


def routing_to_params(rc: RoutingConfig) -> dict:
    """RoutingConfig → yaml ``beautify.params`` dict（``to_dict`` 用）。

    - 顶层标量收在 ``routing`` 下（**排除**已迁移字段
      manual_matches/chip_config/export_unmatched，设计 §4 注）
    - 17 个子节原样 asdict
    """
    d = asdict(rc)
    scalars: dict[str, Any] = {}
    for key in ROUTING_SCALAR_KEYS:
        if key in d:
            if key not in MIGRATED_SCALAR_KEYS:
                scalars[key] = d.pop(key)
            else:
                d.pop(key)
    result: dict[str, Any] = {"routing": scalars}
    result.update(d)
    return result


def routing_params_deep_diff(base: RoutingConfig, other: RoutingConfig) -> dict:
    """两 RoutingConfig 的参数差异：``{group: {key: (旧值, 新值)}}``。

    group = ``routing``（顶层标量）或子节名；仅含差异参数。list 顺序敏感。
    用于 :class:`ProfileDiff.param_diffs` 与 GUI 差异视图。
    """
    da = routing_to_params(base)
    db = routing_to_params(other)
    diffs: dict[str, dict] = {}
    for group in sorted(set(da) | set(db)):
        va, vb = da.get(group), db.get(group)
        if isinstance(va, dict) and isinstance(vb, dict):
            sub: dict[str, Any] = {}
            for key in sorted(set(va) | set(vb)):
                if not deep_eq_params(va.get(key), vb.get(key)):
                    sub[key] = (va.get(key), vb.get(key))
            if sub:
                diffs[group] = sub
        elif not deep_eq_params(va, vb):
            diffs[group] = {"value": (va, vb)}
    return diffs


# ─────────────────────────────────────────────────────────────────────────────
# 各节 dataclass（§3.2 字段清单）
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class InputSection:
    """输入段：库路径 + 输入插件组合（插件实际加载 S3，S1 承载+校验）。"""

    hdl_lib: str = ""
    """主 HDL 库路径（--hdl-lib；相对 CWD，与旧 CLI 一致）。"""
    extra_hdl_libs: list[str] = field(default_factory=list)
    """附加 HDL 库（--extra-hdl-lib，可多次）。"""
    plugins: list[str] = field(default_factory=lambda: ["edif", "pstxnet", "pstchip"])
    """FR1 输入插件组合（S3 实际加载；S1 承载/校验/查重）。"""


@dataclass
class MockSection:
    """FR3 强制 mock 配置。"""

    prefixes: list[str] = field(default_factory=lambda: ["J", "T"])
    """强制 mock 的 prefix。"""
    auto_icon: bool = True
    """J/T/U/IC 用模拟图标（temp_lib.mock_all 后端兜底）。"""


@dataclass
class ManualOverrideSection:
    """FR3 手动匹配（--chip-config 主入口 / --manual-matches 别名）。"""

    file: str = ""
    """chip_config.yaml 路径（v2.0 主入口；manual_matches 别名；空 = 不启用）。"""
    export_unmatched: str = ""
    """未匹配导出路径（--export-unmatched；空 = 不导出）。"""


@dataclass
class MatchSection:
    """匹配段：插件组合 + 权重 + prefix 范围 + 阈值 + mock + 手动干预。

    权重/prefix_scope/thresholds 由 matcher 消费（S4 接入）；S1 承载 + 校验 + 查重。
    """

    plugins: list[str] = field(default_factory=lambda: ["exact", "fuzzy", "passive", "fallback"])
    """FR2 匹配插件链（S4 驱动）。"""
    weights: dict[str, float] = field(default_factory=lambda: {
        "part_name": 0.5, "footprint": 0.3, "value": 0.2, "jedec_type": 0.1,
    })
    """匹配权重（NFR5 去硬编码；S4 接入 matcher）。"""
    prefix_scope: dict[str, list[str]] = field(default_factory=lambda: {
        "R": ["0603", "0402", "0805"],
        "C": ["0603", "0402", "0805"],
        "U": ["sot223", "qfp", "bga"],
        "J": ["connector"],
        "IC": ["any"],
    })
    """各 prefix 搜索范围（S4 接入）。"""
    thresholds: dict[str, float] = field(default_factory=lambda: {
        "exact": 0.95, "fuzzy": 0.75, "feature": 0.60, "fallback": 0.50,
    })
    """= ComponentMatchingConfig 四阈值（S4 接入）。"""
    mock: MockSection = field(default_factory=MockSection)
    """FR3 强制 mock。"""
    manual_overrides: ManualOverrideSection = field(default_factory=ManualOverrideSection)
    """FR3 手动匹配。"""


@dataclass
class BeautifySection:
    """美化段：插件组合（S2 驱动）+ params（RoutingConfig 原样承载，S1 即生效）。

    设计决策（K1/K2）：params 复用 :class:`RoutingConfig`，等价迁移零成本；
    plugins 表达"组合"（查重 set 比较），params 表达"参数"（引擎消费）。
    """

    plugins: list[str] = field(default_factory=lambda: [
        "overlap_resolve", "gnd_cluster", "parallel_short",
    ])
    """FR4 美化插件组合（顺序 = 执行顺序；S5 驱动；查重 set 比较）。"""
    params: RoutingConfig = field(default_factory=RoutingConfig)
    """★ 与旧 routing.yaml 同构（字段 = RoutingConfig 全量）。"""


@dataclass
class OutputSection:
    """输出段：文件/报告选择（S6 驱动；S1 承载 + 校验 + 查重）。"""

    files: list[str] = field(default_factory=lambda: ["csa", "con", "xcon", "csv", "cpc", "cpm", "cds_lib"])
    """FR5 输出文件（S6 驱动）。"""
    reports: list[str] = field(default_factory=lambda: ["aesthetic", "ioport", "mapping", "error"])
    """报告（report 开关见 beautify.params.report）。"""


@dataclass
class TestSection:
    """测试段：测试套件选择（S8 驱动）。"""

    __test__ = False  # 名称以 Test 开头，显式阻止 pytest 收集为测试类

    suites: list[str] = field(default_factory=lambda: ["unit", "e2e", "qa_package"])
    """FR6 测试插件（S8 驱动）。"""


@dataclass
class EngineSection:
    """运行段（--output/--max-workers/--benchmark 落点）。"""

    output_dir: str = "output"
    """输出目录（--output）。"""
    max_workers: int = 4
    """并行度（--max-workers）。"""
    benchmark: bool = False
    """性能基准报告（--benchmark）。"""


# ─────────────────────────────────────────────────────────────────────────────
# PipelineConfig（§3.1 顶层）
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PipelineConfig:
    """插件化转换配置（权威）。顶层七节：profile/input/match/beautify/output/test/engine。

    - 结构即 yaml 结构（snake_case 1:1）
    - ``beautify.params`` 复用 :class:`RoutingConfig`：默认值 = 现有行为（FR9）
    - 兼容桥：``from_routing_config()`` / ``to_routing_config()``
      （ConversionEngine 零改动）
    """

    schema_version: int = 1
    """配置结构版本（导入校验用；低版本缺失字段用默认值）。"""
    profile: str = "default"
    """当前生效 profile：--profile 或 pipeline.yaml profile:。"""
    input: InputSection = field(default_factory=InputSection)
    match: MatchSection = field(default_factory=MatchSection)
    beautify: BeautifySection = field(default_factory=BeautifySection)
    output: OutputSection = field(default_factory=OutputSection)
    test: TestSection = field(default_factory=TestSection)
    engine: EngineSection = field(default_factory=EngineSection)

    # ── 序列化 ─────────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: dict) -> "PipelineConfig":
        """从 dict 构造（未知字段忽略，缺失字段用默认值）。"""
        data = data or {}
        cfg = cls()

        if isinstance(data.get("profile"), str) and data["profile"]:
            cfg.profile = data["profile"]

        if isinstance(data.get("input"), dict):
            d = data["input"]
            cfg.input = InputSection(
                hdl_lib=str(d.get("hdl_lib", "")),
                extra_hdl_libs=[str(x) for x in (d.get("extra_hdl_libs") or [])],
                plugins=[str(x) for x in d["plugins"]] if "plugins" in d else cfg.input.plugins,
            )

        if isinstance(data.get("match"), dict):
            d = data["match"]
            match = MatchSection()
            if "plugins" in d:
                match.plugins = [str(x) for x in d["plugins"]]
            if isinstance(d.get("weights"), dict):
                match.weights = {str(k): float(v) for k, v in d["weights"].items()}
            if isinstance(d.get("prefix_scope"), dict):
                match.prefix_scope = {
                    str(k): [str(x) for x in v] for k, v in d["prefix_scope"].items()
                }
            if isinstance(d.get("thresholds"), dict):
                match.thresholds = {str(k): float(v) for k, v in d["thresholds"].items()}
            if isinstance(d.get("mock"), dict):
                m = d["mock"]
                if "prefixes" in m:
                    match.mock.prefixes = [str(x) for x in m["prefixes"]]
                if "auto_icon" in m:
                    match.mock.auto_icon = bool(m["auto_icon"])
            if isinstance(d.get("manual_overrides"), dict):
                mo = d["manual_overrides"]
                match.manual_overrides.file = str(mo.get("file", ""))
                match.manual_overrides.export_unmatched = str(mo.get("export_unmatched", ""))
            cfg.match = match

        if isinstance(data.get("beautify"), dict):
            d = data["beautify"]
            beautify = BeautifySection()
            if "plugins" in d:
                beautify.plugins = [str(x) for x in d["plugins"]]
            if isinstance(d.get("params"), dict):
                beautify.params = params_to_routing(d["params"])
            cfg.beautify = beautify

        if isinstance(data.get("output"), dict):
            d = data["output"]
            cfg.output = OutputSection(
                files=[str(x) for x in d["files"]] if "files" in d else cfg.output.files,
                reports=[str(x) for x in d["reports"]] if "reports" in d else cfg.output.reports,
            )

        if isinstance(data.get("test"), dict):
            d = data["test"]
            cfg.test = TestSection(
                suites=[str(x) for x in d["suites"]] if "suites" in d else cfg.test.suites,
            )

        if isinstance(data.get("engine"), dict):
            d = data["engine"]
            engine = EngineSection()
            if "output_dir" in d:
                engine.output_dir = str(d["output_dir"])
            if "max_workers" in d:
                engine.max_workers = int(d["max_workers"])
            if "benchmark" in d:
                engine.benchmark = bool(d["benchmark"])
            cfg.engine = engine

        return cfg

    @classmethod
    def from_yaml(cls, path: Path) -> "PipelineConfig":
        """从 yaml 文件加载（``yaml.safe_load`` + ``from_dict``）。"""
        p = Path(path)
        with p.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ValueError(f"pipeline yaml 顶层必须是 mapping: {p}")
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        """序列化为 dict（嵌套 asdict；params 经 RoutingConfig 序列化）。"""
        return {
            "schema_version": self.schema_version,
            "profile": self.profile,
            "input": asdict(self.input),
            "match": asdict(self.match),
            "beautify": {
                "plugins": list(self.beautify.plugins),
                "params": routing_to_params(self.beautify.params),
            },
            "output": asdict(self.output),
            "test": asdict(self.test),
            "engine": asdict(self.engine),
        }

    def to_yaml(self, path: Path) -> None:
        """原子写 yaml（复用共享 ``atomic_write_text``；UTF-8）。"""
        text = yaml.safe_dump(
            self.to_dict(), allow_unicode=True, sort_keys=False, default_flow_style=None,
        )
        atomic_write_text(Path(path), text)

    # ── 兼容桥（FR9 核心） ──────────────────────────────────────────────

    @classmethod
    def from_routing_config(cls, rc: RoutingConfig) -> "PipelineConfig":
        """从现有 RoutingConfig 构造（等价映射）：

        - ``beautify.params`` = deepcopy(rc)
        - ``match.manual_overrides.file`` = rc.chip_config or rc.manual_matches
        - ``match.manual_overrides.export_unmatched`` = rc.export_unmatched
        """
        cfg = cls()
        cfg.beautify.params = copy.deepcopy(rc)
        cfg.match.manual_overrides.file = rc.chip_config or rc.manual_matches
        cfg.match.manual_overrides.export_unmatched = rc.export_unmatched
        return cfg

    def to_routing_config(self) -> RoutingConfig:
        """导出为 RoutingConfig（引擎消费入口）：

        ① copy ``beautify.params``
        ② ``match.manual_overrides.file`` → chip_config & manual_matches
        ③ ``match.manual_overrides.export_unmatched`` → export_unmatched
        ④ 返回 RoutingConfig（默认 profile 时与现有逐字段相等，FR9）

        ``engine.max_workers/benchmark`` 由 CLI 写 ``cfg.app``（§6.2 步骤 6）。
        """
        rc = copy.deepcopy(self.beautify.params)
        mo = self.match.manual_overrides
        rc.chip_config = mo.file
        rc.manual_matches = mo.file
        rc.export_unmatched = mo.export_unmatched
        return rc

    # ── 查重/差异辅助 ───────────────────────────────────────────────────

    def plugin_combos(self) -> dict[str, frozenset[str]]:
        """``{stage: frozenset(plugins)}``——查重 set 比较用（顺序无关）。

        5 个阶段：input / match / beautify / output / test（STAGES）。
        """
        return {
            "input": frozenset(self.input.plugins),
            "match": frozenset(self.match.plugins),
            "beautify": frozenset(self.beautify.plugins),
            "output": frozenset(self.output.files),
            "test": frozenset(self.test.suites),
        }

    # ── 深度比较（ProfileManager 复用） ────────────────────────────────

    def deep_eq(self, other: "PipelineConfig") -> bool:
        """与另一 PipelineConfig 全等（插件组合 + 参数，顺序无关组合）。

        忽略 ``schema_version``/``profile`` 名称（查重语义：组合+参数等价）。
        """
        return self.plugin_combos() == other.plugin_combos() and deep_eq_params(
            self.beautify.params, other.beautify.params,
        )
