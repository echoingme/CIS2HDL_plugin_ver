"""S6 e2e — 输出插件组合字节级等价 + 细粒度独立启停（FR5/FR9）。

设计依据：``docs/developer-guide.md`` S6 章节。

在 **HG5015** 上验证 S6 真实现后：

  1. 默认 profile（output.files 全 7 + reports 全 4）与 legacy 逐字节等价
     （FR9 —— S2-S5 等价性 e2e 继续全绿）。
  2. 部分组合（细粒度独立启停）：
     - ``files: [csa, con] + reports: [mapping]`` → 只写 csa/con +
       共享 infra + mapping 报告；xcon/csv/cpc/cpm/cds.lib/hdldirect/
       origin/errors 不写；aesthetic/ioport 诊断报告被抑制。
     - ``files: [csv, cpc] + reports: [error]`` → 只写 csv/cpc + infra +
       error 日志；mapping 报告不写。
     部分组合断言：插件文件集合 = 期望子集 ⊆ legacy 文件集合；非
     清单内嵌文件（csa/con/csv/cpc/dcf/module_order/page.map/master.tag/
     scr）与 legacy 逐字节等价。report.html / mapping.csv 内嵌
     ``report.output_files`` 清单（部分组合清单不同属预期，跳过字节比对）。

铁律（FR9）：时间戳归一化后逐文件 diff 为空；目录名等长（report.html
内嵌路径 → mapping.csv 大小列随目录名长度变化，S5 教训）。
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


def _convert_plugin(out_dir: Path, pc: PipelineConfig) -> None:
    """plugin 模式：S1 CLI 预置 + engine.set_pipeline（output 插件真实现）。"""
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
    """默认 profile：文件集合 + 逐文件字节（时间戳归一化）等价。"""
    legacy_files = _walk_files(legacy_dir)
    plugin_files = _walk_files(plugin_dir)
    assert set(legacy_files) == set(plugin_files), (
        f"输出文件集合不一致: {sorted(set(legacy_files) ^ set(plugin_files))}"
    )
    for rel in legacy_files:
        legacy_bytes = _normalize(legacy_files[rel].read_bytes(), legacy_dir)
        plugin_bytes = _normalize(plugin_files[rel].read_bytes(), plugin_dir)
        assert legacy_bytes == plugin_bytes, f"字节不一致: {rel}"


#: 内嵌 output_files 清单/执行摘要的文件（部分组合下内容与 legacy 不同属预期）。
#: - report.html/_mapping.csv：内嵌输出文件清单。
#: - *_errors.log/*_errors.txt：内嵌警告/错误计数 —— 部分组合跳过部分
#:   writer 后警告数天然不同（如 xcon/csa 相关警告），属预期行为。
_INVENTORY_EMBEDDING = ("report.html", "_mapping.csv", "_errors.log", "_errors.txt")


def _assert_partial(
    legacy_dir: Path,
    plugin_dir: Path,
    expect_rel_subset: set[str],
) -> None:
    """部分组合：插件文件集合 = 期望子集；非清单内嵌文件与 legacy 字节等价。

    Args:
        legacy_dir: legacy 全量输出目录（参考基线）。
        plugin_dir: 插件部分输出目录。
        expect_rel_subset: 期望存在的相对路径集合（⊆ legacy 文件集合）。
    """
    legacy_files = _walk_files(legacy_dir)
    plugin_files = _walk_files(plugin_dir)
    # ① 文件集合 = 期望子集
    assert set(plugin_files) == expect_rel_subset, (
        f"插件文件集合不符: 多余 {sorted(set(plugin_files) - expect_rel_subset)} "
        f"缺失 {sorted(expect_rel_subset - set(plugin_files))}"
    )
    # ② 期望子集 ⊆ legacy（部分 = legacy 的子集）
    assert expect_rel_subset <= set(legacy_files), (
        f"期望子集超出 legacy: {sorted(expect_rel_subset - set(legacy_files))}"
    )
    # ③ 非清单内嵌文件逐字节等价
    for rel in sorted(expect_rel_subset):
        if any(rel.endswith(suffix) for suffix in _INVENTORY_EMBEDDING):
            continue
        legacy_bytes = _normalize(legacy_files[rel].read_bytes(), legacy_dir)
        plugin_bytes = _normalize(plugin_files[rel].read_bytes(), plugin_dir)
        assert legacy_bytes == plugin_bytes, f"字节不一致: {rel}"


def _pc_default() -> PipelineConfig:
    return PipelineConfig.from_yaml(_PIPELINE_YAML)


def _pc_partial_csa_con_mapping() -> PipelineConfig:
    pc = _pc_default()
    pc.output.files = ["csa", "con"]
    pc.output.reports = ["mapping"]
    return pc


def _pc_partial_csv_cpc_error() -> PipelineConfig:
    pc = _pc_default()
    pc.output.files = ["csv", "cpc"]
    pc.output.reports = ["error"]
    return pc


def _expect_subset_csa_con_mapping(legacy_files: dict[str, Path]) -> set[str]:
    """files=[csa, con] + reports=[mapping] 的期望文件集合。

    规则：以 legacy 文件集合为参照 —— 保留 csa/con/mapping（含 mapping.csv/
    top3.txt 报告产物）+ 共享 infra（.dcf/module_order.dat/page.map/
    master.tag/.scr/hdl_lib 库拷贝/report.html/placeholder/temp_lib），
    剔除 xcon/csv/cpc/cpm/cds.lib/hdldirect.dat/origin/aesthetic/ioport/
    errors。

    注意：
    - ``hdl_lib/`` 内的库拷贝文件（含 .xcon 等）**不受输出插件控制**，
      始终保留 —— 只剔除根目录/其它目录的输出产物。
    - mapping 报告产物 ``*_mapping.csv``/``*_top3.txt`` **保留**（mapping
      插件启用时写入）；``*_errors.log``/``*_errors.txt`` **剔除**（error
      插件未启用）。
    """
    drop_suffixes = (
        ".xcon", ".cpc", ".cpm",
        "cds.lib", "hdldirect.dat",
        "aesthetic_report.txt", "ioport_audit_report.txt",
        "_errors.log", "_errors.txt",
    )
    drop_prefixes = ("origin/",)
    kept = set()
    for rel in legacy_files:
        if rel.startswith(drop_prefixes):
            continue
        if rel.startswith("hdl_lib/"):
            kept.add(rel)  # 库拷贝不受输出插件控制，始终保留
            continue
        if rel.endswith(drop_suffixes):
            continue
        if rel.endswith(".csv") and not rel.endswith("_mapping.csv"):
            continue  # 普通 pageN.csv 剔除；mapping 报告产物保留
        kept.add(rel)
    return kept


def _expect_subset_csv_cpc_error(legacy_files: dict[str, Path]) -> set[str]:
    """files=[csv, cpc] + reports=[error] 的期望文件集合。

    保留 csv/cpc/error（含 errors.log/txt 报告产物）+ 共享 infra；剔除
    csa/con/xcon/cpm/cds.lib/hdldirect.dat/origin/aesthetic/ioport/mapping/
    top3。

    注意：
    - ``hdl_lib/`` 内的库拷贝文件不受输出插件控制，始终保留。
    - error 报告产物 ``*_errors.log``/``*_errors.txt`` **保留**（error
      插件启用时写入）；``*_mapping.csv``/``*_top3.txt`` **剔除**。
    """
    drop_suffixes = (
        ".csa", ".con", ".xcon", ".cpm",
        "cds.lib", "hdldirect.dat",
        "aesthetic_report.txt", "ioport_audit_report.txt",
        "_mapping.csv", "_top3.txt", "pin_audit_report.txt",
    )
    drop_prefixes = ("origin/", "temp_lib/")
    kept = set()
    for rel in legacy_files:
        if rel.startswith(drop_prefixes):
            continue
        if rel.startswith("hdl_lib/"):
            kept.add(rel)  # 库拷贝不受输出插件控制，始终保留
            continue
        if rel.endswith(drop_suffixes):
            continue
        kept.add(rel)
    return kept


class TestS6OutputPluginEquivalence:
    """S6 核心验收：默认 profile == legacy 字节级；部分组合独立启停。"""

    def test_default_profile_equivalent(self, tmp_path_factory) -> None:
        """默认 profile（7 文件 + 4 报告）与 legacy 逐字节等价（FR9）。"""
        _require_input()
        legacy_dir = tmp_path_factory.mktemp("lg")
        plugin_dir = tmp_path_factory.mktemp("pl")
        _convert_legacy(legacy_dir)
        _convert_plugin(plugin_dir, _pc_default())
        _assert_equivalent(legacy_dir, plugin_dir)

    def test_partial_csa_con_mapping(self, tmp_path_factory) -> None:
        """部分组合 1：[csa, con] + [mapping] → 只写这两个文件 + infra。"""
        _require_input()
        legacy_dir = tmp_path_factory.mktemp("lg_csa")
        plugin_dir = tmp_path_factory.mktemp("pl_csa")
        _convert_legacy(legacy_dir)
        _convert_plugin(plugin_dir, _pc_partial_csa_con_mapping())
        legacy_files = _walk_files(legacy_dir)
        expect = _expect_subset_csa_con_mapping(legacy_files)
        _assert_partial(legacy_dir, plugin_dir, expect)
        # 显式断言：被禁插件对应文件不存在（hdl_lib 库拷贝排除在外）
        plugin_files = _walk_files(plugin_dir)
        non_lib = [rel for rel in plugin_files if not rel.startswith("hdl_lib/")]
        assert not any(rel.endswith((".xcon", ".cpc", ".cpm")) for rel in non_lib)
        assert not any(
            rel.endswith(".csv") and not rel.endswith("_mapping.csv")
            for rel in non_lib
        )  # 普通 csv 剔除；mapping 报告产物保留
        assert not any(rel.endswith(("cds.lib", "hdldirect.dat")) for rel in non_lib)
        assert not any(rel.endswith(("aesthetic_report.txt", "ioport_audit_report.txt")) for rel in non_lib)
        assert not any(rel.endswith("_errors") for rel in non_lib)

    def test_partial_csv_cpc_error(self, tmp_path_factory) -> None:
        """部分组合 2：[csv, cpc] + [error] → 只写 csv/cpc + infra + 错误日志。"""
        _require_input()
        legacy_dir = tmp_path_factory.mktemp("lg_csv")
        plugin_dir = tmp_path_factory.mktemp("pl_csv")
        _convert_legacy(legacy_dir)
        _convert_plugin(plugin_dir, _pc_partial_csv_cpc_error())
        legacy_files = _walk_files(legacy_dir)
        expect = _expect_subset_csv_cpc_error(legacy_files)
        _assert_partial(legacy_dir, plugin_dir, expect)
        # 显式断言：被禁插件对应文件不存在（hdl_lib 库拷贝排除在外）
        plugin_files = _walk_files(plugin_dir)
        non_lib = [rel for rel in plugin_files if not rel.startswith("hdl_lib/")]
        assert not any(rel.endswith((".csa", ".con", ".xcon")) for rel in non_lib)
        assert not any(rel.endswith(("_mapping.csv", "_top3.txt")) for rel in non_lib)
