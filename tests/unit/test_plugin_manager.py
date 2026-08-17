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
        # S1 白名单同名（input 5 / beautify 6 / output 11 / test 3）
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
        # S6 细粒度输出插件（7 文件 + 4 报告）
        for name in ("csa", "con", "xcon", "csv", "cpc", "cpm", "cds_lib"):
            assert ("output", name) in names, name
        for name in ("aesthetic", "ioport", "mapping", "error"):
            assert ("output", name) in names, name
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

    def test_output_fine_grained_default_registered(self, default_cfg: PipelineConfig):
        """S6 细粒度：默认 profile 注册 7 文件 + 4 报告插件（= legacy 全文件）。"""
        pm = build_plugin_manager(default_cfg)
        enabled = [s.name for s in pm._enabled]
        assert {"csa", "con", "xcon", "csv", "cpc", "cpm", "cds_lib"} <= set(enabled)
        assert {"aesthetic", "ioport", "mapping", "error"} <= set(enabled)

    def test_output_independent_enable_disable(self):
        """S6 独立启停：output.files/reports 精确控制注册（禁 csv 不注册）。"""
        cfg = PipelineConfig()
        cfg.output.files = ["csa", "con"]
        cfg.output.reports = ["mapping"]
        pm = build_plugin_manager(cfg)
        enabled = [s.name for s in pm._enabled]
        assert "csa" in enabled and "con" in enabled
        assert "csv" not in enabled and "xcon" not in enabled
        assert "cpm" not in enabled and "cds_lib" not in enabled
        assert "mapping" in enabled
        assert "error" not in enabled and "aesthetic" not in enabled
        assert "ioport" not in enabled
        # 注册层面同样（未启用插件不实例化不注册）
        assert pm.get_plugin("csv") is None
        assert pm.get_plugin("mapping") is not None

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

    def test_missing_cls_spec_not_instantiated(self, monkeypatch, default_cfg: PipelineConfig):
        """cls=None 的 spec 不实例化不注册（机制）；S8 起 test 插件真实现。

        S8 变化：test 白名单占位（cls=None）退役，unit/e2e/qa_package 全部
        真实现并注册；本测试改用 monkeypatch 注入占位 spec 验证机制仍生效。
        """
        pm = build_plugin_manager(default_cfg)
        for name in ("unit", "e2e", "qa_package"):
            assert pm.get_plugin(name) is not None

        # 机制：cls=None 的 spec 即使启用也不实例化不注册。
        from cis2hdl.plugins import manager as manager_mod
        from cis2hdl.plugins.spec import PluginSpec

        placeholder = PluginSpec(
            name="placeholder_test", stage="test", description="占位",
            cls=None, module="cis2hdl.plugins.test",
        )
        real_specs, errors = manager_mod.discover_all()
        patched = [s for s in real_specs if s.name != "unit"] + [placeholder]
        monkeypatch.setattr(
            manager_mod, "discover_all",
            lambda *a, **k: (patched, errors),
        )
        pm2 = build_plugin_manager(default_cfg)
        assert pm2.get_plugin("placeholder_test") is None
        assert "placeholder_test" not in pm2._registered_names
        # 其它真实现插件仍正常注册
        assert pm2.get_plugin("e2e") is not None


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
