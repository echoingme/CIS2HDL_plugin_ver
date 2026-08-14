"""S1 T05 — 默认 profile 等价性 e2e（FR9 字节级验证）。

设计依据：``docs/S1-config-design.md`` T05 / §12 等价铁律。

同一输入分别走：
  - 旧路径：``Config.load_from_file(routing.yaml)`` + ConversionEngine（= 旧 __main__.py 行为）
  - 新路径：``PipelineConfig.from_yaml(pipeline.yaml).to_routing_config()`` + ConversionEngine

断言输出目录逐文件**字节级** diff 为空。唯一允许的差异是输出目录绝对路径
（两次转换目标目录不同，是测试自身产物）——比较前归一化为 ``<OUT>``。

覆盖：
  1. 默认 profile 全量字节等价
  2. routing.mode ∈ {p0, detour} 等价（新/旧两路径同时改 mode）
  3. 旧参数组合（--routing detour --wire-simplify）经新 CLI 映射后与旧路径等价
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

from cis2hdl.cli import _apply_legacy_args
from cis2hdl.core.config import Config
from cis2hdl.core.engine.conversion_engine import ConversionEngine
from cis2hdl.core.pipeline_config import PipelineConfig
from cis2hdl.core.profile_manager import ProfileManager

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE_YAML = _PROJECT_ROOT / "pipeline.yaml"
_ROUTING_YAML = _PROJECT_ROOT / "cis2hdl" / "config" / "routing.yaml"
_INPUT = _PROJECT_ROOT / "tests" / "fixtures" / "RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN"

#: 报告内的转换时间戳（非确定性，等价比较时归一化）。
#: 两种格式：``2026-08-14 17:11:10``（日志/CSV）与 ``17:11:36 ... August 14, 2026``（cpm 头）。
_TS_RE = re.compile(rb"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}|\d{2}:\d{2}:\d{2}")


def _require_input() -> None:
    if not _INPUT.exists():
        pytest.skip(f"fixture 缺失: {_INPUT}")


def _convert_old(out_dir: Path, *, mode: str | None = None, wire_simplify: bool = False) -> None:
    """旧路径：routing.yaml + 旧 __main__.py 风格的 CLI 覆盖。"""
    cfg = Config.get()
    cfg.reset()
    cfg.load_from_file(_ROUTING_YAML)
    if mode is not None:
        cfg.routing.mode = mode
    if wire_simplify:
        cfg.routing.wire_simplify.enabled = True
    ConversionEngine().convert(
        _INPUT, out_dir, hdl_lib_path=None, config_file=None, extra_lib_paths=[],
    )


def _convert_new(out_dir: Path, *, mode: str | None = None, legacy: dict | None = None) -> None:
    """新路径：pipeline.yaml（+ profile/旧参数映射）→ to_routing_config。"""
    cfg = Config.get()
    cfg.reset()
    pc = PipelineConfig.from_yaml(_PIPELINE_YAML)
    if mode is not None:
        pc.beautify.params.mode = mode
    if legacy:
        ns = argparse.Namespace(
            input=None, pipeline=None, profile=None,
            output=None, hdl_lib=None, extra_hdl_lib=[], benchmark=False,
            max_workers=None, routing=None, nonuniform_tracks=False,
            net_order=None, wire_simplify=False, manual_matches=None,
            chip_config=None, export_unmatched=None, text_layout=False,
            power_ic=False, aesthetic=False, gnd_distribute=False,
            rotate_passives=False, ioport_edge=False, ioport_audit=False,
            use_net_name=False, no_mirror_normalize=False, no_report=False,
            cross_page_opt=False,
        )
        for key, value in legacy.items():
            setattr(ns, key, value)
        _apply_legacy_args(pc, ns, set())
    cfg.routing = pc.to_routing_config()
    cfg.app.max_workers = pc.engine.max_workers
    cfg.app.benchmark = pc.engine.benchmark
    ConversionEngine().convert(
        _INPUT, out_dir, hdl_lib_path=None, config_file=None, extra_lib_paths=[],
    )


def _walk_files(root: Path) -> dict[str, Path]:
    return {p.relative_to(root).as_posix(): p for p in sorted(root.rglob("*")) if p.is_file()}


def _normalize(data: bytes, out_dir: Path) -> bytes:
    """归一化输出目录绝对路径 + 转换时间戳（两次转换的非确定性产物）。"""
    data = data.replace(str(out_dir).encode("utf-8"), b"<OUT>")
    return _TS_RE.sub(b"<TS>", data)


def _assert_equivalent(old_dir: Path, new_dir: Path) -> None:
    old_files = _walk_files(old_dir)
    new_files = _walk_files(new_dir)
    assert set(old_files) == set(new_files), (
        f"输出文件集合不一致: {sorted(set(old_files) ^ set(new_files))}"
    )
    for rel in old_files:
        old_bytes = _normalize(old_files[rel].read_bytes(), old_dir)
        new_bytes = _normalize(new_files[rel].read_bytes(), new_dir)
        assert old_bytes == new_bytes, f"字节不一致: {rel}"


class TestDefaultProfileEquivalence:
    def test_byte_level_identical(self, tmp_path: Path) -> None:
        """默认 profile：新路径与旧路径输出字节级全等（FR9）。"""
        _require_input()
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        _convert_old(old_dir)
        _convert_new(new_dir)
        _assert_equivalent(old_dir, new_dir)

    @pytest.mark.parametrize("mode", ["p0", "detour"])
    def test_routing_mode_equivalence(self, tmp_path: Path, mode: str) -> None:
        """routing.mode 等价：新旧两路径同时改 mode，输出仍字节级全等。"""
        _require_input()
        old_dir = tmp_path / f"old_{mode}"
        new_dir = tmp_path / f"new_{mode}"
        _convert_old(old_dir, mode=mode)
        _convert_new(new_dir, mode=mode)
        _assert_equivalent(old_dir, new_dir)

    def test_legacy_flag_combination_equivalence(self, tmp_path: Path) -> None:
        """旧参数组合（--routing detour --wire-simplify）经新 CLI 映射后等价。"""
        _require_input()
        old_dir = tmp_path / "old_legacy"
        new_dir = tmp_path / "new_legacy"
        _convert_old(old_dir, mode="detour", wire_simplify=True)
        _convert_new(new_dir, legacy={"routing": "detour", "wire_simplify": True})
        _assert_equivalent(old_dir, new_dir)

    def test_profile_default_equivalence(self, tmp_path: Path) -> None:
        """--profile default 经 ProfileManager 解析后与旧路径等价。"""
        _require_input()
        old_dir = tmp_path / "old_pd"
        new_dir = tmp_path / "new_pd"
        _convert_old(old_dir)
        cfg = Config.get()
        cfg.reset()
        pc = ProfileManager().get("default")
        cfg.routing = pc.to_routing_config()
        cfg.app.max_workers = pc.engine.max_workers
        cfg.app.benchmark = pc.engine.benchmark
        ConversionEngine().convert(
            _INPUT, new_dir, hdl_lib_path=None, config_file=None, extra_lib_paths=[],
        )
        _assert_equivalent(old_dir, new_dir)
