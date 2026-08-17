"""S2 T03 — plugin 模式 vs legacy 模式字节级等价性 e2e（S2 核心验收）。

设计依据：``docs/S2-plugin-base-design.md`` §4.1 双模式引擎 + §T03 验收。

铁律（FR9）：**默认 profile 的 plugin 模式输出与 legacy 模式逐文件字节级
等价**。S2 内置插件是"薄包装 + 占位"（input/beautify 返回 False 回退
legacy），因此 plugin 模式应产出与 legacy 完全相同的结果。

覆盖：
  1. 默认 profile：legacy（ConversionEngine 默认） vs plugin
     （set_pipeline 后 convert）→ 字节级 diff 空
  2. convert_with_cfg 便捷入口同样等价
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

from cis2hdl.core.config import Config
from cis2hdl.core.engine.conversion_engine import ConversionEngine
from cis2hdl.core.pipeline_config import PipelineConfig

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE_YAML = _PROJECT_ROOT / "pipeline.yaml"
_INPUT = _PROJECT_ROOT / "tests" / "fixtures" / "RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN"

# 秒级 + 分钟级（HTML 报告用分钟精度）时间戳均归一化——防分钟翻转 flake。
_TS_RE = re.compile(
    rb"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
    rb"|\d{4}-\d{2}-\d{2} \d{2}:\d{2}"
    rb"|\d{2}:\d{2}:\d{2}"
)


@pytest.fixture(autouse=True)
def _restore_global_config() -> None:
    """保存/恢复全局 Config 单例（防顺序依赖污染）。"""
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


def _convert_legacy(out_dir: Path) -> None:
    """legacy 模式：默认引擎（_pm=None），routing.yaml 配置。"""
    cfg = Config.get()
    cfg.reset()
    cfg.load_from_file(_PROJECT_ROOT / "cis2hdl" / "config" / "routing.yaml")
    ConversionEngine().convert(
        _INPUT, out_dir, hdl_lib_path=None, config_file=None, extra_lib_paths=[],
    )


def _convert_plugin(out_dir: Path, pc: PipelineConfig) -> None:
    """plugin 模式：set_pipeline 激活，默认 profile。"""
    cfg = Config.get()
    cfg.reset()
    cfg.routing = pc.to_routing_config()
    cfg.app.max_workers = pc.engine.max_workers
    cfg.app.benchmark = pc.engine.benchmark
    engine = ConversionEngine()
    engine.set_pipeline(pc)
    engine.convert(_INPUT, out_dir, hdl_lib_path=None, config_file=None,
                   extra_lib_paths=[])


def _walk_files(root: Path) -> dict[str, Path]:
    return {p.relative_to(root).as_posix(): p for p in sorted(root.rglob("*")) if p.is_file()}


def _normalize(data: bytes, out_dir: Path) -> bytes:
    data = data.replace(str(out_dir).encode("utf-8"), b"<OUT>")
    return _TS_RE.sub(b"<TS>", data)


def _assert_equivalent(legacy_dir: Path, plugin_dir: Path) -> None:
    legacy_files = _walk_files(legacy_dir)
    plugin_files = _walk_files(plugin_dir)
    assert set(legacy_files) == set(plugin_files), (
        f"输出文件集合不一致: {sorted(set(legacy_files) ^ set(plugin_files))}"
    )
    for rel in legacy_files:
        legacy_bytes = _normalize(legacy_files[rel].read_bytes(), legacy_dir)
        plugin_bytes = _normalize(plugin_files[rel].read_bytes(), plugin_dir)
        assert legacy_bytes == plugin_bytes, f"字节不一致: {rel}"


class TestPluginLegacyEquivalence:
    """S2 核心验收：默认 profile 的 plugin 模式 == legacy 模式。"""

    def test_default_profile_plugin_equivalent(self, tmp_path: Path) -> None:
        """默认 profile：plugin 模式输出与 legacy 逐文件字节等价。"""
        _require_input()
        legacy_dir = tmp_path / "legacy"
        plugin_dir = tmp_path / "plugin"
        legacy_dir.mkdir()
        plugin_dir.mkdir()

        _convert_legacy(legacy_dir)
        pc = PipelineConfig.from_yaml(_PIPELINE_YAML)
        assert pc.profile == "default"
        _convert_plugin(plugin_dir, pc)

        _assert_equivalent(legacy_dir, plugin_dir)

    def test_convert_with_cfg_equivalent(self, tmp_path: Path) -> None:
        """convert_with_cfg 入口与 legacy 等价（CLI S3 将走此路径）。"""
        _require_input()
        legacy_dir = tmp_path / "legacy2"
        plugin_dir = tmp_path / "plugin2"
        legacy_dir.mkdir()
        plugin_dir.mkdir()

        _convert_legacy(legacy_dir)
        pc = PipelineConfig.from_yaml(_PIPELINE_YAML)
        cfg = Config.get()
        cfg.reset()
        cfg.routing = pc.to_routing_config()
        engine = ConversionEngine()
        engine.convert_with_cfg(pc, _INPUT, plugin_dir,
                                hdl_lib_path=None, extra_lib_paths=[])

        _assert_equivalent(legacy_dir, plugin_dir)
