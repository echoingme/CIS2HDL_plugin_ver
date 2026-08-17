"""S2 T03 — 引擎钩子调用点测试（integration）。

设计依据：``docs/S2-plugin-base-design.md`` §4（ConversionEngine 钩子化）。

验证：
  1. legacy 模式（plugin_manager=None）：5 处钩子全部走 fallback，行为与
     改造前等价（ConversionEngine 默认构造零 pluggy 开销）。
  2. plugin 模式（set_pipeline / convert_with_cfg）：钩子被调用、ctx 正确
     传递；插件返回 False/None → fallback 仍执行（NFR3 降级）。
  3. PluginHost 的 handled 语义：任一插件返回真值 → fallback 不执行。

铁律：**不修改任何业务代码**，只做行为验证。
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

from cis2hdl.core.config import Config
from cis2hdl.core.engine.conversion_engine import ConversionEngine
from cis2hdl.core.pipeline_config import PipelineConfig
from cis2hdl.plugins.context import ConversionContext
from cis2hdl.plugins.hookspecs import hookimpl
from cis2hdl.plugins.manager import build_plugin_manager

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE_YAML = _PROJECT_ROOT / "pipeline.yaml"
_INPUT = _PROJECT_ROOT / "tests" / "fixtures" / "RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN"


@pytest.fixture(autouse=True)
def _restore_global_config() -> None:
    """保存/恢复全局 Config 单例（防顺序依赖污染，同 S1 T05）。"""
    from cis2hdl.core.config import Config as _Config

    saved_instance = _Config._instance
    saved_state = (
        copy.deepcopy(saved_instance.__dict__)
        if saved_instance is not None
        else None
    )
    yield
    if saved_instance is not None:
        _Config._instance = saved_instance
        saved_instance.__dict__.clear()
        saved_instance.__dict__.update(saved_state)
    else:
        _Config._instance = None


def _require_input() -> None:
    if not _INPUT.exists():
        pytest.skip(f"fixture 缺失: {_INPUT}")


def _fresh_pipeline() -> PipelineConfig:
    return PipelineConfig.from_yaml(_PIPELINE_YAML)


class TestLegacyModeFallback:
    """legacy 模式（默认构造）：钩子全部回退，不引入 pluggy 路径。"""

    def test_engine_constructor_legacy_default(self) -> None:
        """默认构造 engine：_pm 为 None（legacy），_host 存在但无 pluggy。"""
        engine = ConversionEngine()
        assert engine._pm is None
        assert engine._host is not None

    def test_set_pipeline_activates_plugin_mode(self) -> None:
        """set_pipeline 后 _pm 非 None（build_plugin_manager 已注册内置插件）。"""
        pc = _fresh_pipeline()
        engine = ConversionEngine()
        engine.set_pipeline(pc)
        assert engine._pm is not None
        # 默认 profile 应发现全部内置插件（PluginSpec 列表）
        specs = engine._pm.list_plugins()
        names = {s.name for s in specs}
        assert "edif" in names or "matcher_pipeline" in names
        assert len(specs) > 0

    def test_plugin_host_legacy_fallback(self) -> None:
        """PluginHost.call 在 legacy 模式直接执行 fallback（零 pluggy 开销）。"""
        engine = ConversionEngine()
        marker: list[str] = []

        def _fb() -> str:
            marker.append("fb")
            return "LEGACY"

        handled, result = engine._host.call(None, "load_input", fallback=_fb)
        assert handled is False
        assert result == "LEGACY"
        assert marker == ["fb"]


class TestPluginModeHooks:
    """plugin 模式：钩子被调用、ctx 正确、降级语义。"""

    def _make_engine(self, pc: PipelineConfig, extra_plugin) -> ConversionEngine:
        pm = build_plugin_manager(pc, engine=ConversionEngine())
        # 直接向底层 pluggy 管理器注册探测插件（包装类未透传 register）
        pm._pm.register(extra_plugin, name="probe_input")
        return ConversionEngine(plugin_manager=pm, pipeline_cfg=pc)

    def test_plugin_hooks_receive_ctx(self) -> None:
        """插件 hook 收到 ConversionContext 且 cfg 来自 pipeline.yaml。"""
        _require_input()
        pc = _fresh_pipeline()
        received: list[ConversionContext] = []

        class ProbePlugin:
            @hookimpl
            def load_input(self, ctx: ConversionContext) -> bool | None:
                received.append(ctx)
                return False  # 未处理 → fallback

        engine = self._make_engine(pc, ProbePlugin())
        engine.convert(_INPUT, Path("/tmp/s2_hook_probe"), hdl_lib_path=None,
                       config_file=None, extra_lib_paths=[])

        assert received, "load_input 钩子未被调用"
        assert received[0].cfg.profile == pc.profile
        assert received[0].input_files, "ctx.input_files 应为输入文件列表"

    def test_false_plugin_falls_back_to_legacy(self, tmp_path: Path) -> None:
        """全部插件返回 False/None → fallback 执行（legacy 结果可用）。

        S3 起默认 edif 为真实现（返回 True 接管），故先清空 input 插件
        组合，仅保留探测插件返回 False，确保走到 legacy fallback 路径。
        """
        _require_input()
        pc = _fresh_pipeline()
        pc.input.plugins = []  # S3：清空 input 组合 → 无内置插件接管

        class FalsePlugin:
            @hookimpl
            def load_input(self, ctx: ConversionContext) -> bool | None:
                return False

        engine = self._make_engine(pc, FalsePlugin())
        report = engine.convert(_INPUT, tmp_path, hdl_lib_path=None,
                                config_file=None, extra_lib_paths=[])
        # fallback 执行后 report 应有内容（页面数 > 0 表示 parse 成功）
        assert report is not None
        assert report.pages > 0

    def test_true_plugin_bypasses_fallback(self, tmp_path: Path) -> None:
        """任一插件返回真值 → fallback 不执行（handled 语义）。"""
        _require_input()
        pc = _fresh_pipeline()

        class TruePlugin:
            @hookimpl
            def load_input(self, ctx: ConversionContext) -> bool | None:
                return True

        engine = self._make_engine(pc, TruePlugin())
        fallback_called: list[bool] = []
        engine._host.call(
            None, "load_input",
            fallback=lambda: fallback_called.append(True) or "FB",
        )
        assert fallback_called == [], "handled=True 时 fallback 不应执行"

    def test_convert_with_cfg_api(self, tmp_path: Path) -> None:
        """convert_with_cfg：显式传 PipelineConfig → plugin 模式转换可完成。"""
        _require_input()
        pc = _fresh_pipeline()
        engine = ConversionEngine()
        report = engine.convert_with_cfg(pc, _INPUT, tmp_path,
                                         hdl_lib_path=None, extra_lib_paths=[])
        assert report is not None
        # plugin 模式（默认 profile）转换应成功，页面数正确
        assert report.pages > 0
