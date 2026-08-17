"""S5 e2e — 美化插件组合字节级等价（FR9 强化验证：默认 + max-beauty + 单美化）。

设计依据：``docs/developer-guide.md`` S5 章节。

S2/S3/S4 e2e 已覆盖默认 profile 与 legacy 字节级等价（beautify 占位时期）；
本测试在 **HG5015** 上验证 S5 真实现后：

  1. 默认 profile（beautify: [overlap_resolve, gnd_cluster, parallel_short]）
     与 legacy 逐字节等价（FR9 —— S2/S3/S4 等价性 e2e 继续全绿）。
  2. max-beauty profile（beautify 全 6 插件 + routing.mode=detour +
     wire_simplify.enabled + text_layout.enabled）与 legacy 等价 ——
     完整 params 应用（非仅单插件 param_fields）保证 routing.mode 等字段
     生效（S5 核心设计点）。
  3. 单美化插件独立启停（[text_layout] / [wire_simplify] enabled）与 legacy
     等价（FR2 —— 插件独立启用即应用 params，writer 内置逻辑执行）。

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
from cis2hdl.core.profile_manager import ProfileManager

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE_YAML = _PROJECT_ROOT / "pipeline.yaml"
_ROUTING_YAML = _PROJECT_ROOT / "cis2hdl" / "config" / "routing.yaml"
_HG_DIR = _PROJECT_ROOT / "tests" / "fixtures" / "HG5015test"
_HG_DSN = _HG_DIR / "HG5015-BE36_V10.DSN"
_HDL = _PROJECT_ROOT / "tests" / "fixtures" / "hdl_lib"

_TS_RE = re.compile(
    rb"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
    rb"|\d{4}-\d{2}-\d{2} \d{2}:\d{2}"
    rb"|\d{2}:\d{2}:\d{2}"
)


@pytest.fixture(autouse=True)
def _restore_global_config() -> None:
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
    """legacy 基线：routing.yaml + ConversionEngine().convert()（无插件）。"""
    cfg = Config.get()
    cfg.reset()
    cfg.load_from_file(_ROUTING_YAML)
    ConversionEngine().convert(
        _HG_DSN, out_dir,
        hdl_lib_path=_HDL if _HDL.exists() else None,
        config_file=None, extra_lib_paths=[],
    )


def _convert_legacy_with(out_dir: Path, pc: PipelineConfig) -> None:
    """legacy + yaml params：等价 S1 CLI ``cfg_obj.routing = to_routing_config()``。"""
    cfg = Config.get()
    cfg.reset()
    cfg.load_from_file(_ROUTING_YAML)
    cfg.routing = pc.to_routing_config()
    cfg.app.max_workers = pc.engine.max_workers
    cfg.app.benchmark = pc.engine.benchmark
    ConversionEngine().convert(
        _HG_DSN, out_dir,
        hdl_lib_path=_HDL if _HDL.exists() else None,
        config_file=None, extra_lib_paths=[],
    )


def _convert_plugin(out_dir: Path, pc: PipelineConfig) -> None:
    """plugin 模式：S1 CLI 预置 + engine.set_pipeline（beautify 插件真实现）。"""
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
    """默认 profile legacy 基线（routing.yaml；目录名 'lg' 长度 = 插件 'pl'）。"""
    _require_input()
    out = tmp_path_factory.mktemp("lg")
    _convert_legacy(out)
    return out


def _plugin_dir(tmp_path_factory, case: str) -> Path:
    """插件输出目录。注意：report.html 内嵌输出路径（1008 处），文件大小随
    目录名长度变化 → mapping.csv 的大小列会随之变化。为保证与 legacy 目录
    字节等价，目录名长度必须与 legacy 一致：
      - default 用例：legacy='lg'（2 字符）→ 插件='pl'（2 字符）
      - 其它用例：legacy='lg_<case>' → 插件='pl_<case>'（同长）
    """
    if case == "default":
        return tmp_path_factory.mktemp("pl")
    return tmp_path_factory.mktemp(f"pl_{case}")


#: S5 美化组合：(用例名, PipelineConfig 构造器, legacy 转换器)。
def _pc_default() -> PipelineConfig:
    return PipelineConfig.from_yaml(_PIPELINE_YAML)


def _pc_max_beauty() -> PipelineConfig:
    return ProfileManager().get("max-beauty")


def _pc_text_layout() -> PipelineConfig:
    pc = _pc_default()
    pc.beautify.plugins = ["text_layout"]
    pc.beautify.params.text_layout.enabled = True
    return pc


def _pc_wire_simplify() -> PipelineConfig:
    pc = _pc_default()
    pc.beautify.plugins = ["wire_simplify"]
    pc.beautify.params.wire_simplify.enabled = True
    return pc


class TestS5BeautifyPluginEquivalence:
    """S5 核心验收：美化插件组合 == legacy 字节级（HG5015）。"""

    @pytest.mark.parametrize(
        "case,pc_builder,legacy_kind",
        [
            pytest.param("default", _pc_default, "plain",
                         id="default"),
            pytest.param("max-beauty", _pc_max_beauty, "with_params",
                         id="max-beauty"),
            pytest.param("text_layout", _pc_text_layout, "with_params",
                         id="text_layout"),
            pytest.param("wire_simplify", _pc_wire_simplify, "with_params",
                         id="wire_simplify"),
        ],
    )
    def test_beautify_profile_equivalent(
        self,
        legacy_output: Path,
        tmp_path_factory,
        case: str,
        pc_builder,
        legacy_kind: str,
    ) -> None:
        _require_input()
        pc = pc_builder()
        if legacy_kind == "plain":
            legacy_dir = legacy_output
        else:
            legacy_dir = tmp_path_factory.mktemp(f"lg_{case}")
            _convert_legacy_with(legacy_dir, pc)
        plugin_dir = _plugin_dir(tmp_path_factory, case)
        _convert_plugin(plugin_dir, pc)
        _assert_equivalent(legacy_dir, plugin_dir)
