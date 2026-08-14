"""S1 T02 — PipelineConfig 数据层单元测试。

Covers（docs/S1-config-design.md T02）：
  * 往返恒等：from_routing_config(rc).to_routing_config() == rc（字段级）
  * from_yaml 加载 pipeline.yaml → to_routing_config 与
    Config().load_from_file(routing.yaml) 的 routing 字段全等（FR9）
  * 未知字段忽略
  * 序列化往返：from_dict(to_dict(x)) == x
  * plugin_combos / 桥接字段映射（manual_overrides ↔ chip_config）
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from cis2hdl.core.config import Config, RoutingConfig
from cis2hdl.core.pipeline_config import (
    BeautifySection,
    EngineSection,
    InputSection,
    MatchSection,
    OutputSection,
    PipelineConfig,
    TestSection,
    deep_eq_params,
    params_to_routing,
    routing_params_deep_diff,
    routing_to_params,
)

_PKG_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE_YAML = _PKG_ROOT / "pipeline.yaml"
_ROUTING_YAML = _PKG_ROOT / "cis2hdl" / "config" / "routing.yaml"


# ── 往返恒等（FR9 核心） ───────────────────────────────────────────────


class TestRoundTripRoutingConfig:
    def test_from_to_routing_config_identity(self):
        """from_routing_config(rc).to_routing_config() == rc（字段级）。"""
        rc = RoutingConfig()
        rc.mode = "detour"
        rc.nonuniform_tracks = True
        rc.text_layout.enabled = True
        rc.gnd_distribution.cluster_radius = 700
        rc.ioport.manual_names = {"RAW": "TARGET"}
        rc.chip_config = "chip.yaml"
        rc.manual_matches = "manual.yaml"
        rc.export_unmatched = "unmatched.yaml"

        cfg = PipelineConfig.from_routing_config(rc)
        rc2 = cfg.to_routing_config()

        assert rc2.mode == "detour"
        assert rc2.nonuniform_tracks is True
        assert rc2.text_layout.enabled is True
        assert rc2.gnd_distribution.cluster_radius == 700
        assert rc2.ioport.manual_names == {"RAW": "TARGET"}
        # 桥接回填：chip_config 优先，manual_matches 同步
        assert rc2.chip_config == "chip.yaml"
        assert rc2.manual_matches == "chip.yaml"
        assert rc2.export_unmatched == "unmatched.yaml"

    def test_manual_overrides_file_prefers_chip_config(self):
        """from_routing_config: manual_overrides.file = chip_config or manual_matches。"""
        rc = RoutingConfig()
        rc.chip_config = "chip.yaml"
        rc.manual_matches = "manual.yaml"
        cfg = PipelineConfig.from_routing_config(rc)
        assert cfg.match.manual_overrides.file == "chip.yaml"

        rc2 = RoutingConfig()
        rc2.chip_config = ""
        rc2.manual_matches = "manual.yaml"
        cfg2 = PipelineConfig.from_routing_config(rc2)
        assert cfg2.match.manual_overrides.file == "manual.yaml"

    def test_to_routing_config_returns_copy(self):
        """to_routing_config 返回副本，不共享内部 mutable 状态。"""
        cfg = PipelineConfig()
        rc = cfg.to_routing_config()
        rc.mode = "detour"
        assert cfg.beautify.params.mode == "p0"


# ── pipeline.yaml 与旧 routing.yaml 全等（FR9 字段级） ─────────────────


class TestPipelineYamlEquivalence:
    @pytest.fixture()
    def pipeline_cfg(self) -> PipelineConfig:
        return PipelineConfig.from_yaml(_PIPELINE_YAML)

    @pytest.fixture()
    def legacy_cfg(self) -> Config:
        cfg = Config()
        cfg.load_from_file(_ROUTING_YAML)
        return cfg

    def test_pipeline_yaml_exists(self):
        assert _PIPELINE_YAML.exists(), "pipeline.yaml missing"

    def test_yaml_round_trip(self, pipeline_cfg: PipelineConfig):
        """from_dict(to_dict(x)) 逐字段相等。"""
        cfg2 = PipelineConfig.from_dict(pipeline_cfg.to_dict())
        assert cfg2 == pipeline_cfg
        assert cfg2.beautify.params == pipeline_cfg.beautify.params

    def test_routing_equivalence_with_legacy(self, pipeline_cfg: PipelineConfig, legacy_cfg: Config):
        """新路径 to_routing_config == 旧路径 routing.yaml 全等（FR9）。"""
        rc_new = pipeline_cfg.to_routing_config()
        rc_old = legacy_cfg.routing
        assert rc_new == rc_old, "default profile 与旧 routing.yaml 必须逐字段相等"
        # 再逐字段断言（dataclass __eq__ 已覆盖；此处补标量抽查）
        assert rc_new.mode == rc_old.mode == "p0"
        assert rc_new.temp_lib.enabled is True
        assert rc_new.report.always_write is True
        assert rc_new.ioport.un_name_policy == "rename"

    def test_params_key_sets_match_routing_config(self, pipeline_cfg: PipelineConfig):
        """beautify.params 的 key 集合 == RoutingConfig 字段全集（标量+子节）。"""
        params = pipeline_cfg.beautify.params
        data = yaml.safe_load(_PIPELINE_YAML.read_text(encoding="utf-8"))
        yaml_params = data["beautify"]["params"]
        assert set(yaml_params) == {"routing"} | set(
            f.name for f in __import__("dataclasses").fields(RoutingConfig)
            if f.name in (
                "text_layout", "overlap", "power_ic", "aesthetic", "report",
                "placeholder", "ioport", "mirror", "gnd_distribution", "temp_lib",
                "wire_simplify", "pin_audit", "attribute", "matching", "placement",
                "net_name",
            )
        )


# ── 未知字段忽略 / 部分加载 ────────────────────────────────────────────


class TestUnknownFields:
    def test_unknown_top_level_ignored(self):
        data = {
            "schema_version": 1,
            "profile": "default",
            "future_section": {"x": 1},
            "input": {"hdl_lib": "/lib", "future_key": 42},
        }
        cfg = PipelineConfig.from_dict(data)
        assert cfg.input.hdl_lib == "/lib"
        assert cfg.profile == "default"

    def test_unknown_section_fields_ignored(self):
        data = {
            "beautify": {
                "params": {
                    "routing": {"mode": "detour", "future": 1},
                    "text_layout": {"enabled": True, "future": "x"},
                }
            }
        }
        cfg = PipelineConfig.from_dict(data)
        assert cfg.beautify.params.mode == "detour"
        assert cfg.beautify.params.text_layout.enabled is True

    def test_empty_dict_returns_defaults(self):
        cfg = PipelineConfig.from_dict({})
        assert cfg == PipelineConfig()


# ── 序列化往返 ─────────────────────────────────────────────────────────


class TestSerialization:
    def test_to_dict_structure(self):
        cfg = PipelineConfig()
        d = cfg.to_dict()
        assert set(d) == {
            "schema_version", "profile", "input", "match",
            "beautify", "output", "test", "engine",
        }
        assert set(d["beautify"]) == {"plugins", "params"}
        assert "routing" in d["beautify"]["params"]
        assert "text_layout" in d["beautify"]["params"]

    def test_routing_to_params_excludes_migrated_fields(self):
        rc = RoutingConfig()
        rc.chip_config = "chip.yaml"
        rc.manual_matches = "manual.yaml"
        rc.export_unmatched = "unmatched.yaml"
        params = routing_to_params(rc)
        assert "chip_config" not in params["routing"]
        assert "manual_matches" not in params["routing"]
        assert "export_unmatched" not in params["routing"]
        assert params["routing"]["mode"] == "p0"

    def test_params_to_routing_round_trip(self):
        rc = RoutingConfig()
        rc.mode = "detour"
        rc.overlap.check = True
        rc.gnd_distribution.gnd_power_lastpin_offset = [0, 100]
        rc2 = params_to_routing(routing_to_params(rc))
        assert rc2.mode == "detour"
        assert rc2.overlap.check is True
        assert rc2.gnd_distribution.gnd_power_lastpin_offset == [0, 100]

    def test_to_yaml_round_trip(self, tmp_path: Path):
        cfg = PipelineConfig()
        cfg.profile = "custom"
        cfg.beautify.params.mode = "detour"
        out = tmp_path / "pipeline.yaml"
        cfg.to_yaml(out)
        assert out.exists()
        cfg2 = PipelineConfig.from_yaml(out)
        assert cfg2 == cfg


# ── 各节默认值（与设计 §3.2 对齐） ─────────────────────────────────────


class TestSectionDefaults:
    def test_default_plugins(self):
        cfg = PipelineConfig()
        assert cfg.input.plugins == ["edif", "pstxnet", "pstchip"]
        assert cfg.match.plugins == ["exact", "fuzzy", "passive", "fallback"]
        assert cfg.beautify.plugins == ["overlap_resolve", "gnd_cluster", "parallel_short"]
        assert cfg.output.files == ["csa", "con", "xcon", "csv", "cpc", "cpm", "cds_lib"]
        assert cfg.output.reports == ["aesthetic", "ioport", "mapping", "error"]
        assert cfg.test.suites == ["unit", "e2e", "qa_package"]
        assert cfg.engine.output_dir == "output"
        assert cfg.engine.max_workers == 4
        assert cfg.engine.benchmark is False

    def test_match_thresholds_match_component_matching(self):
        from cis2hdl.core.config import ComponentMatchingConfig

        cfg = PipelineConfig()
        cmc = ComponentMatchingConfig()
        assert cfg.match.thresholds["exact"] == cmc.exact_threshold
        assert cfg.match.thresholds["fuzzy"] == cmc.fuzzy_threshold
        assert cfg.match.thresholds["feature"] == cmc.feature_threshold
        assert cfg.match.thresholds["fallback"] == cmc.fallback_threshold


# ── 查重辅助 ───────────────────────────────────────────────────────────


class TestPluginCombos:
    def test_plugin_combos_frozensets(self):
        cfg = PipelineConfig()
        combos = cfg.plugin_combos()
        assert combos["input"] == frozenset(["edif", "pstxnet", "pstchip"])
        assert combos["output"] == frozenset(cfg.output.files)
        assert combos["test"] == frozenset(cfg.test.suites)
        # 顺序无关
        cfg2 = PipelineConfig()
        cfg2.beautify.plugins = ["parallel_short", "gnd_cluster", "overlap_resolve"]
        assert cfg.plugin_combos()["beautify"] == cfg2.plugin_combos()["beautify"]

    def test_deep_eq_params(self):
        assert deep_eq_params({"a": [1, 2]}, {"a": [1, 2]})
        assert not deep_eq_params({"a": [1, 2]}, {"a": [2, 1]})  # list 顺序敏感
        assert not deep_eq_params({"a": 1}, {"a": 1, "b": 2})

    def test_routing_params_deep_diff(self):
        base = RoutingConfig()
        other = RoutingConfig()
        other.mode = "detour"
        other.gnd_distribution.cluster_radius = 700
        diffs = routing_params_deep_diff(base, other)
        assert diffs["routing"]["mode"] == ("p0", "detour")
        assert diffs["gnd_distribution"]["cluster_radius"] == (2000, 700)
        assert "text_layout" not in diffs
