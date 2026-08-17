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
  3. 特性组合等价（detour + wire_simplify）：S10 起用户经 pipeline.yaml
     配置对应字段（--routing/--wire-simplify 已移除），新旧路径仍字节等价
  4. --profile default 经 ProfileManager 解析后与旧路径等价
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
from cis2hdl.core.profile_manager import ProfileManager


@pytest.fixture(autouse=True)
def _restore_global_config() -> None:
    """保存/恢复全局 Config 单例状态 —— 防止前序测试污染导致顺序依赖失败。

    问题：``test_legacy_flag_combination_equivalence`` 单独跑通过、全量顺序跑
    失败 —— 全局 Config 单例被前序测试（其它 e2e/单元测试）污染，残留的
    routing/app 等字段使本次转换行为漂移。

    方案：autouse fixture 在**每个**测试前后快照/恢复 ``Config._instance``
    的完整 ``__dict__``（含可能被整体替换的实例本身），保证本文件内测试
    相互隔离、也不向后续测试泄漏状态。
    """
    from cis2hdl.core.config import Config as _Config

    saved_instance = _Config._instance
    saved_state = (
        copy.deepcopy(saved_instance.__dict__) if saved_instance is not None else None
    )
    yield
    if saved_instance is not None:
        _Config._instance = saved_instance
        saved_instance.__dict__.clear()
        saved_instance.__dict__.update(saved_state)
    else:
        _Config._instance = None

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE_YAML = _PROJECT_ROOT / "pipeline.yaml"
_ROUTING_YAML = _PROJECT_ROOT / "cis2hdl" / "config" / "routing.yaml"
_INPUT = _PROJECT_ROOT / "tests" / "fixtures" / "RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN"

#: 报告内的转换时间戳（非确定性，等价比较时归一化）。
#: 三种格式：``2026-08-14 17:11:10``（日志/CSV）、``17:11:36 ... August 14, 2026``
#: （cpm 头）与 ``2026-08-14 17:11``（HTML 报告分钟精度）——分钟级也必须
#: 归一化，否则跨分钟运行会 flake。
_TS_RE = re.compile(
    rb"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
    rb"|\d{4}-\d{2}-\d{2} \d{2}:\d{2}"
    rb"|\d{2}:\d{2}:\d{2}"
)


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


def _convert_new(out_dir: Path, *, mode: str | None = None,
                 wire_simplify: bool = False) -> None:
    """新路径：pipeline.yaml（+ 直接配置覆盖，等价用户改 yaml）→ to_routing_config。

    S10 起旧行为参数（--routing/--wire-simplify/...）已移除，用户改由
    pipeline.yaml 字段配置——这里直接覆盖 PipelineConfig 字段即等价
    "用户按迁移表改 yaml"的语义。
    """
    cfg = Config.get()
    cfg.reset()
    pc = PipelineConfig.from_yaml(_PIPELINE_YAML)
    if mode is not None:
        pc.beautify.params.mode = mode
    if wire_simplify:
        pc.beautify.params.wire_simplify.enabled = True
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

    def test_config_equivalence_detour_wire_simplify(self, tmp_path: Path) -> None:
        """特性组合等价（detour + wire_simplify）：S10 起用户经 pipeline.yaml
        配置（--routing/--wire-simplify 已移除），新旧路径输出仍字节等价。"""
        _require_input()
        old_dir = tmp_path / "old_cfg"
        new_dir = tmp_path / "new_cfg"
        _convert_old(old_dir, mode="detour", wire_simplify=True)
        _convert_new(new_dir, mode="detour", wire_simplify=True)
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
