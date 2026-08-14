"""S2 T02 — PluginManager 单元测试。

Covers（docs/S2-plugin-base-design.md T02）：
  * discover/list_plugins 全量（含 S1 白名单同名）
  * enabled_by_cfg 五阶段语义（default profile 组合）
  * 破坏性测试：造 import 失败插件 → skip + degraded，其余正常
  * 实例化/注册降级（NFR3）
  * cleanup 幂等 + 注册清零
  * build() 幂等（重复 build 前 cleanup）
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cis2hdl.core.pipeline_config import PipelineConfig
from cis2hdl.plugins.manager import PluginManager, build_plugin_manager


@pytest.fixture()
def default_cfg() -> PipelineConfig:
    return PipelineConfig()


class TestDiscover:
    def test_list_plugins_full(self):
        pm = PluginManager()
        specs = pm.list_plugins()
        names = {(s.stage, s.name) for s in specs}
        # S1 白名单同名（input 5 / beautify 6 / output 2 / test 3）
        assert ("input", "edif") in names
        assert ("input", "dsn") in names
        assert ("input", "cross_ref") in names
        assert ("input", "pstxnet") in names
        assert ("input", "pstchip") in names
        assert ("beautify", "overlap_resolve") in names
        assert ("beautify", "gnd_cluster") in names
        assert ("beautify", "parallel_short") in names
        assert ("beautify", "wire_simplify") in names
        assert ("beautify", "three_stage_stub") in names
        assert ("beautify", "text_layout") in names
        assert ("output", "default_writer") in names
        assert ("output", "reports") in names
        assert ("test", "unit") in names
        assert ("test", "e2e") in names
        assert ("test", "qa_package") in names

    def test_list_plugins_stage_filter(self):
        pm = PluginManager()
        assert {s.name for s in pm.list_plugins("beautify")} == {
            "overlap_resolve", "gnd_cluster", "parallel_short",
            "wire_simplify", "three_stage_stub", "text_layout",
        }

    def test_whitelist_names_all_stages(self):
        """list_plugins(stage) 非空且不重复（S2 起白名单 = PluginManager.list_plugins）。

        注：match 阶段插件在 T03 落地（matcher_pipeline/manual_overrides），
        T02 阶段 match 为空是预期。
        """
        pm = PluginManager()
        for stage in ("input", "beautify", "output", "test"):
            specs = pm.list_plugins(stage)
            assert specs, f"{stage} 无插件"
            names = [s.name for s in specs]
            assert len(names) == len(set(names)), f"{stage} 插件名重复: {names}"


class TestBuild:
    def test_build_default_profile_success(self, default_cfg: PipelineConfig):
        pm = build_plugin_manager(default_cfg)
        assert pm.degraded == []
        assert pm._enabled != []

    def test_enabled_by_cfg_default(self, default_cfg: PipelineConfig):
        pm = build_plugin_manager(default_cfg)
        enabled = [s.name for s in pm._enabled]
        assert {"edif", "pstxnet", "pstchip"} <= set(enabled)
        assert {"overlap_resolve", "gnd_cluster", "parallel_short"} <= set(enabled)
        assert {"unit", "e2e", "qa_package"} <= set(enabled)
        # 未启用：wire_simplify / text_layout 不在默认 beautify 组合
        assert "wire_simplify" not in enabled
        assert "text_layout" not in enabled

    def test_output_coarse_always_registered(self, default_cfg: PipelineConfig):
        """S2 粗粒度：output default_writer/reports 恒注册（默认 profile 必需）。"""
        pm = build_plugin_manager(default_cfg)
        enabled = [s.name for s in pm._enabled]
        assert "default_writer" in enabled
        assert "reports" in enabled

    def test_disabled_plugin_not_registered(self):
        """把 gnd_cluster 从 beautify 组合移除 → 不注册。"""
        cfg = PipelineConfig()
        cfg.beautify.plugins = ["overlap_resolve", "parallel_short"]
        pm = build_plugin_manager(cfg)
        assert pm.get_plugin("gnd_cluster") is None
        assert pm.get_plugin("overlap_resolve") is not None

    def test_build_twice_idempotent(self, default_cfg: PipelineConfig):
        pm = build_plugin_manager(default_cfg)
        first_names = list(pm._registered_names)
        pm.build(default_cfg)
        assert pm._registered_names == first_names
        # 无重复注册（cleanup 已清）
        assert len(pm.hook.beautify.get_hookimpls()) == 3


class TestDegrade:
    def _broken_dir(self, tmp_path: Path) -> Path:
        """构造一个含坏插件的临时 plugins 目录（import 失败）。"""
        import shutil

        src = Path(__file__).resolve().parents[2] / "cis2hdl" / "plugins"
        dst = tmp_path / "plugins"
        shutil.copytree(src, dst)
        bad = dst / "beautify" / "bad_plugin.py"
        bad.write_text("raise ImportError('boom')\n", encoding="utf-8")
        return dst

    def test_import_failure_degraded_others_ok(self, tmp_path: Path, default_cfg: PipelineConfig):
        pm = PluginManager(plugins_dir=self._broken_dir(tmp_path))
        pm.build(default_cfg)
        degraded_names = [n for n, _ in pm.degraded]
        assert "beautify.bad_plugin" in degraded_names
        # 其余插件正常注册
        assert pm.get_plugin("overlap_resolve") is not None
        assert pm.get_plugin("gnd_cluster") is not None

    def test_missing_cls_spec_not_instantiated(self, default_cfg: PipelineConfig):
        """cls=None 的白名单 spec（output/test）不实例化不注册。"""
        pm = build_plugin_manager(default_cfg)
        assert pm.get_plugin("default_writer") is None  # T03 才有 cls
        assert pm.get_plugin("unit") is None


class TestCleanup:
    def test_cleanup_idempotent(self, default_cfg: PipelineConfig):
        pm = build_plugin_manager(default_cfg)
        pm.cleanup()
        pm.cleanup()  # 幂等
        assert pm._registered_names == []
        assert len(pm.hook.beautify.get_hookimpls()) == 0

    def test_cleanup_calls_plugin_cleanup(self):
        """cleanup 后插件 enabled 被复位（stub cleanup 语义）。"""
        cfg = PipelineConfig()
        cfg.beautify.params.gnd_distribution.enabled = True
        pm = build_plugin_manager(cfg)
        gnd = pm.get_plugin("gnd_cluster")
        assert gnd.enabled is True
        pm.cleanup()
        assert gnd.enabled is False
