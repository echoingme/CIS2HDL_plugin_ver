"""S4 e2e — match 插件组合字节级等价（FR9 强化验证）。

设计依据：``docs/developer-guide.md`` S4 章节。

S2/S3 e2e 覆盖默认 profile（match: [exact, fuzzy, passive, fallback]）与
legacy 字节级等价；本测试在 **HG5015** 上验证 **match 插件组合的可变配置**
与 legacy 字节级等价：

  1. 单匹配插件 profile（[exact] / [fuzzy] / [passive] / [fallback] /
     [matcher_pipeline]）——任一匹配插件单独启用即编排完整匹配阶段
     （FR2 独立启停），输出必须与 legacy 逐字节一致。
  2. 空匹配插件 profile（[]）——match_components 钩子无人处理 → 引擎回退
     legacy _stage_match，输出一致。

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
    cfg = Config.get()
    cfg.reset()
    cfg.load_from_file(_PROJECT_ROOT / "cis2hdl" / "config" / "routing.yaml")
    ConversionEngine().convert(
        _HG_DSN, out_dir,
        hdl_lib_path=_HDL if _HDL.exists() else None,
        config_file=None, extra_lib_paths=[],
    )


def _convert_plugin(out_dir: Path, pc: PipelineConfig) -> None:
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
    _require_input()
    out = tmp_path_factory.mktemp("lg")
    _convert_legacy(out)
    return out


#: match 插件组合：单插件 + 显式编排 + 空（回退 legacy）。
_MATCH_PROFILES: list[list[str]] = [
    ["exact"],
    ["fuzzy"],
    ["passive"],
    ["fallback"],
    ["matcher_pipeline"],
    [],
]


class TestS4MatchPluginEquivalence:
    """S4 核心验收：match 插件组合 == legacy 字节级（HG5015）。"""

    @pytest.mark.parametrize("plugins", _MATCH_PROFILES, ids=lambda p: ",".join(p) or "none")
    def test_match_profile_equivalent(
        self,
        legacy_output: Path,
        tmp_path_factory,
        plugins: list[str],
    ) -> None:
        _require_input()
        pc = PipelineConfig.from_yaml(_PIPELINE_YAML)
        pc.match.plugins = list(plugins)
        plugin_dir = tmp_path_factory.mktemp("pl")
        _convert_plugin(plugin_dir, pc)
        _assert_equivalent(legacy_output, plugin_dir)
