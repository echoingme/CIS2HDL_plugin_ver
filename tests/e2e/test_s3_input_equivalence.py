"""S3 e2e — HG5015 插件组合字节级等价（FR9 强化验证）。

设计依据：``docs/developer-guide.md`` S3 章节。

S2 e2e（test_plugin_mode_equivalence）只覆盖 RTL8367RB（无 CSV/pst）。
本测试在 **HG5015**（含 CrossRef CSV + pstchip/pstxprt/pstxnet 全数据源）
上验证 plugin 模式与 legacy 逐文件字节级等价：

  1. 默认 profile ``[edif, pstxnet, pstchip]`` —— edif 编排器内联
     cross_ref（未启用）→ 与 legacy 等价。
  2. 全增量 ``[edif, cross_ref, pstxnet, pstchip]`` —— 每个子步骤由
     独立插件执行 → 与 legacy 等价。

铁律（FR9）：输出文件集合 + 逐文件字节（时间戳归一化）diff 为空。
"""

from __future__ import annotations

import copy
import difflib
import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

from cis2hdl.core.config import Config
from cis2hdl.core.engine.conversion_engine import ConversionEngine
from cis2hdl.core.pipeline_config import PipelineConfig

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE_YAML = _PROJECT_ROOT / "pipeline.yaml"
_HG_DIR = _PROJECT_ROOT / "tests" / "fixtures" / "HG5015test"
_HG_DSN = _HG_DIR / "HG5015-BE36_V10.DSN"
_HDL = _PROJECT_ROOT / "tests" / "fixtures" / "hdl_lib"

# 秒级 + 分钟级（HTML 报告用分钟精度）时间戳均归一化。
_TS_RE = re.compile(
    rb"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
    rb"|\d{4}-\d{2}-\d{2} \d{2}:\d{2}"
    rb"|\d{2}:\d{2}:\d{2}"
)


@pytest.fixture(autouse=True)
def _restore_global_config() -> None:
    """保存/恢复全局 Config 单例（防顺序依赖污染）。"""
    saved_instance = Config._instance
    saved_state = (
        copy.deepcopy(saved_instance.__dict__)
        if saved_instance is not None
        else None
    )
    yield
    if saved_instance is not None:
        Config._instance = saved_instance
        saved_instance.__dict__.clear()
        saved_instance.__dict__.update(saved_state)
    else:
        Config._instance = None


def _require_input() -> None:
    if not _HG_DSN.exists():
        pytest.skip(f"fixture 缺失: {_HG_DSN}")


def _convert_legacy(out_dir: Path) -> None:
    """legacy 模式：默认引擎（_pm=None），routing.yaml 配置。"""
    cfg = Config.get()
    cfg.reset()
    cfg.load_from_file(_PROJECT_ROOT / "cis2hdl" / "config" / "routing.yaml")
    ConversionEngine().convert(
        _HG_DSN, out_dir,
        hdl_lib_path=_HDL if _HDL.exists() else None,
        config_file=None, extra_lib_paths=[],
    )


def _convert_plugin(out_dir: Path, pc: PipelineConfig) -> None:
    """plugin 模式：set_pipeline 激活 + 指定 input 插件组合。"""
    cfg = Config.get()
    cfg.reset()
    cfg.routing = pc.to_routing_config()
    cfg.app.max_workers = pc.engine.max_workers
    cfg.app.benchmark = pc.engine.benchmark
    engine = ConversionEngine()
    engine.set_pipeline(pc)
    engine.convert(
        _HG_DSN, out_dir,
        hdl_lib_path=_HDL if _HDL.exists() else None,
        config_file=None, extra_lib_paths=[],
    )


def _walk_files(root: Path) -> dict[str, Path]:
    return {p.relative_to(root).as_posix(): p for p in sorted(root.rglob("*")) if p.is_file()}


def _normalize(data: bytes, out_dir: Path) -> bytes:
    data = data.replace(str(out_dir).encode("utf-8"), b"<OUT>")
    return _TS_RE.sub(b"<TS>", data)


def _assert_equivalent(legacy_dir: Path, plugin_dir: Path) -> None:
    legacy_files = _walk_files(legacy_dir)
    plugin_files = _walk_files(plugin_dir)
    assert set(legacy_files) == set(plugin_files), (
        f"输出文件集合不一致: {sorted(set(legacy_files) ^ set(plugin_files))[:10]}"
    )
    for rel in legacy_files:
        legacy_bytes = _normalize(legacy_files[rel].read_bytes(), legacy_dir)
        plugin_bytes = _normalize(plugin_files[rel].read_bytes(), plugin_dir)
        if legacy_bytes != plugin_bytes:
            la = legacy_bytes.decode("utf-8", "replace").splitlines()
            lb = plugin_bytes.decode("utf-8", "replace").splitlines()
            diff = list(difflib.unified_diff(la, lb, lineterm="", n=1))
            raise AssertionError(
                f"字节不一致: {rel}\n" + "\n".join(diff[:40])
            )


@pytest.fixture(scope="module")
def legacy_output(tmp_path_factory) -> Path:
    """模块级 legacy 输出（一次转换，两个 plugin 用例复用）。

    注意：输出目录名必须与 plugin 用例**等长**（如 ``lg``/``pl``）——
    mapping.csv 记录输出文件原始大小，而 report.html 等文件嵌入了输出目录
    路径，路径长度不同 → 原始大小不同 → 大小列 diff（S2 e2e 用等长的
    ``legacy``/``plugin`` 目录所以未踩中）。
    """
    _require_input()
    out = tmp_path_factory.mktemp("lg")
    _convert_legacy(out)
    return out


class TestHg5015PluginLegacyEquivalence:
    """S3 核心验收：HG5015 上 plugin 组合 == legacy 字节级。"""

    def test_default_profile_equivalent(self, legacy_output: Path, tmp_path_factory) -> None:
        """默认 profile [edif, pstxnet, pstchip]（edif 内联 cross_ref）。"""
        _require_input()
        pc = PipelineConfig.from_yaml(_PIPELINE_YAML)
        assert pc.input.plugins == ["edif", "pstxnet", "pstchip"]
        plugin_dir = tmp_path_factory.mktemp("pl")
        _convert_plugin(plugin_dir, pc)
        _assert_equivalent(legacy_output, plugin_dir)

    def test_full_increment_equivalent(self, legacy_output: Path, tmp_path_factory) -> None:
        """全增量 [edif, cross_ref, pstxnet, pstchip]。"""
        _require_input()
        pc = PipelineConfig.from_yaml(_PIPELINE_YAML)
        pc.input.plugins = ["edif", "cross_ref", "pstxnet", "pstchip"]
        plugin_dir = tmp_path_factory.mktemp("pl")
        _convert_plugin(plugin_dir, pc)
        _assert_equivalent(legacy_output, plugin_dir)
