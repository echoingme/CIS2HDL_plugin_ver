"""S1 T04 — CLI 改造与旧参数迁移单元测试。

Covers（docs/S1-config-design.md T04）：
  * 23 个旧 CLI 参数逐个映射到正确 yaml 字段
  * --aesthetic 复合展开断言（与旧 __main__.py 行为逐一对比）
  * deprecation 警告只打印一次（set 去重）
  * --profile 与旧参数叠加时旧参数优先
  * profile 子命令成功/失败路径 + 退出码 0/1/2/3
  * convert_main 缺文件/缺 pipeline 路径的退出码
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
import yaml

from cis2hdl.cli import (
    _apply_legacy_args,
    _deprecation_warn,
    _profile_create,
    _profile_delete,
    _profile_export,
    _profile_import,
    _profile_show,
    convert_main,
    main,
)
from cis2hdl.core.pipeline_config import PipelineConfig
from cis2hdl.core.profile_manager import ProfileManager


def _ns(**overrides: object) -> argparse.Namespace:
    """构造全默认的 convert 参数 Namespace（只覆盖被测试字段）。"""
    base = argparse.Namespace(
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
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _apply(**overrides: object) -> tuple[PipelineConfig, set[str]]:
    """应用旧参数映射到全新 PipelineConfig，返回 (cfg, warned)。"""
    cfg = PipelineConfig()
    warned: set[str] = set()
    _apply_legacy_args(cfg, _ns(**overrides), warned)
    return cfg, warned


# ── 23 个旧参数映射（§6.3 全量） ───────────────────────────────────────


class TestLegacyMapping:
    def test_output_maps_to_engine(self):
        cfg, _ = _apply(output="out_dir")
        assert cfg.engine.output_dir == "out_dir"

    def test_hdl_lib_maps_to_input(self):
        cfg, _ = _apply(hdl_lib="lib")
        assert cfg.input.hdl_lib == "lib"

    def test_extra_hdl_lib_append(self):
        cfg, _ = _apply(extra_hdl_lib=["a", "b"])
        assert cfg.input.extra_hdl_libs == ["a", "b"]

    def test_benchmark(self):
        cfg, _ = _apply(benchmark=True)
        assert cfg.engine.benchmark is True

    def test_max_workers(self):
        cfg, _ = _apply(max_workers=8)
        assert cfg.engine.max_workers == 8

    def test_routing(self):
        cfg, _ = _apply(routing="detour")
        assert cfg.beautify.params.mode == "detour"

    def test_nonuniform_tracks(self):
        cfg, _ = _apply(nonuniform_tracks=True)
        assert cfg.beautify.params.nonuniform_tracks is True

    def test_net_order(self):
        cfg, _ = _apply(net_order="short_first")
        assert cfg.beautify.params.net_order == "short_first"

    def test_wire_simplify(self):
        cfg, _ = _apply(wire_simplify=True)
        assert cfg.beautify.params.wire_simplify.enabled is True

    def test_manual_matches(self):
        cfg, _ = _apply(manual_matches="manual.yaml")
        assert cfg.match.manual_overrides.file == "manual.yaml"

    def test_chip_config_overrides_manual_matches(self):
        cfg, _ = _apply(manual_matches="manual.yaml", chip_config="chip.yaml")
        assert cfg.match.manual_overrides.file == "chip.yaml"

    def test_export_unmatched(self):
        cfg, _ = _apply(export_unmatched="unmatched.yaml")
        assert cfg.match.manual_overrides.export_unmatched == "unmatched.yaml"

    def test_text_layout(self):
        cfg, _ = _apply(text_layout=True)
        assert cfg.beautify.params.text_layout.enabled is True

    def test_power_ic(self):
        cfg, _ = _apply(power_ic=True)
        assert cfg.beautify.params.power_ic.enabled is True

    def test_aesthetic_expansion(self):
        """--aesthetic 复合展开：8 字段逐一断言（与旧 __main__.py 行为一致）。"""
        cfg, warned = _apply(aesthetic=True)
        params = cfg.beautify.params
        assert params.aesthetic.enabled is True
        assert params.text_layout.enabled is True
        assert params.overlap.check is True
        assert params.power_ic.enabled is True
        assert params.mode == "detour"          # 未显式 --routing 且 mode==p0 → detour
        assert params.ioport.edge_layout is True
        assert params.gnd_distribution.enabled is True
        assert params.ioport.audit is True
        assert "--aesthetic" in warned

    def test_aesthetic_keeps_explicit_routing(self):
        """显式 --routing p0 时 --aesthetic 不改 mode（保等价）。"""
        cfg, _ = _apply(aesthetic=True, routing="p0")
        assert cfg.beautify.params.mode == "p0"

    def test_aesthetic_keeps_non_p0_routing(self):
        cfg, _ = _apply(aesthetic=True, routing="edif_reuse")
        assert cfg.beautify.params.mode == "edif_reuse"

    def test_gnd_distribute(self):
        cfg, _ = _apply(gnd_distribute=True)
        assert cfg.beautify.params.gnd_distribution.enabled is True
        assert cfg.beautify.params.gnd_distribution.distribute_density is True

    def test_rotate_passives(self):
        cfg, _ = _apply(rotate_passives=True)
        assert cfg.beautify.params.placement.rotate_passives is True

    def test_ioport_edge(self):
        cfg, _ = _apply(ioport_edge=True)
        assert cfg.beautify.params.ioport.edge_layout is True

    def test_ioport_audit(self):
        cfg, _ = _apply(ioport_audit=True)
        assert cfg.beautify.params.ioport.audit is True

    def test_use_net_name(self):
        cfg, _ = _apply(use_net_name=True)
        assert cfg.beautify.params.ioport.use_net_name is True

    def test_no_mirror_normalize(self):
        cfg, _ = _apply(no_mirror_normalize=True)
        assert cfg.beautify.params.mirror.normalize is False

    def test_no_report(self):
        cfg, _ = _apply(no_report=True)
        assert cfg.beautify.params.report.always_write is False

    def test_cross_page_opt(self):
        cfg, _ = _apply(cross_page_opt=True)
        assert cfg.beautify.params.cross_page_opt is True

    def test_invalid_routing_warns_and_defaults(self, capsys: pytest.CaptureFixture[str]):
        cfg, _ = _apply(routing="bogus")
        assert cfg.beautify.params.mode == "p0"
        out = capsys.readouterr().out
        assert "Warning: unknown --routing" in out

    def test_invalid_net_order_warns_and_defaults(self, capsys: pytest.CaptureFixture[str]):
        cfg, _ = _apply(net_order="bogus")
        assert cfg.beautify.params.net_order == "long_first"
        assert "Warning: unknown --net-order" in capsys.readouterr().out


# ── deprecation 警告 ────────────────────────────────────────────────────


class TestDeprecationWarning:
    def test_warning_once_per_flag(self, capsys: pytest.CaptureFixture[str]):
        cfg = PipelineConfig()
        warned: set[str] = set()
        # 两次 --routing 只警告一次
        _apply_legacy_args(cfg, _ns(routing="detour"), warned)
        _apply_legacy_args(cfg, _ns(routing="p0"), warned)
        err = capsys.readouterr().err
        assert err.count("[deprecation] --routing") == 1

    def test_warning_format(self, capsys: pytest.CaptureFixture[str]):
        _deprecation_warn("--routing", set())
        err = capsys.readouterr().err
        assert err.startswith("[deprecation] --routing 已废弃，将在 S10 移除")
        assert "beautify.params.routing.mode" in err
        assert "docs/S1-config-design.md §6.3" in err

    def test_no_warning_without_legacy(self, capsys: pytest.CaptureFixture[str]):
        _apply()
        err = capsys.readouterr().err
        assert err == ""


# ── --profile 与旧参数叠加 ──────────────────────────────────────────────


class TestProfileOverlay:
    def test_legacy_overrides_profile(self):
        """fast profile 的 report.always_write=False 被 --no-report 语义覆盖？否——
        旧参数覆盖 profile 对应字段：--output 覆盖 profile 无关字段；
        --wire-simplify 叠加到 max-beauty 之上。"""
        pm = ProfileManager()  # 仓库内置
        cfg = pm.get("max-beauty")
        assert cfg.beautify.params.mode == "detour"
        warned: set[str] = set()
        _apply_legacy_args(cfg, _ns(wire_simplify=True, routing="p0"), warned)
        assert cfg.beautify.params.wire_simplify.enabled is True  # 旧参数叠加
        assert cfg.beautify.params.mode == "p0"                   # 旧参数覆盖 profile

    def test_legacy_output_overrides_profile_engine(self):
        pm = ProfileManager()
        cfg = pm.get("fast")
        warned: set[str] = set()
        _apply_legacy_args(cfg, _ns(output="custom_out"), warned)
        assert cfg.engine.output_dir == "custom_out"


# ── profile 子命令（§6.4） ─────────────────────────────────────────────


@pytest.fixture()
def tmp_pm(tmp_path: Path) -> ProfileManager:
    return ProfileManager(profiles_dir=tmp_path)


class TestProfileSubcommands:
    def test_create_duplicate_exit_2(self, tmp_pm: ProfileManager, capsys: pytest.CaptureFixture[str]):
        cfg = PipelineConfig()
        tmp_pm.create("first", cfg)
        code = _profile_create(tmp_pm, ["second"])
        assert code == 2
        assert "重复" in capsys.readouterr().out

    def test_create_builtin_exit_3(self, tmp_pm: ProfileManager, capsys: pytest.CaptureFixture[str]):
        code = _profile_create(tmp_pm, ["default"])
        assert code == 3

    def test_create_ok(self, tmp_pm: ProfileManager, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        pipe = tmp_path / "pipeline.yaml"
        pipe.write_text(yaml.safe_dump(PipelineConfig().to_dict()), encoding="utf-8")
        code = _profile_create(tmp_pm, ["mine", "--from-file", str(pipe)])
        assert code == 0
        assert (tmp_path / "mine.yaml").exists()
        assert "已保存" in capsys.readouterr().out

    def test_delete_builtin_exit_3(self, tmp_pm: ProfileManager, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        # 内置 profile 需真实存在才触发只读保护
        (tmp_path / "default.yaml").write_text(yaml.safe_dump({
            "schema_version": 1,
            "profile": {"name": "default", "builtin": True, "plugins": {"test": ["unit"]}},
        }), encoding="utf-8")
        code = _profile_delete(tmp_pm, ["default"])
        assert code == 3
        assert "只读" in capsys.readouterr().out

    def test_delete_missing_exit_1(self, tmp_pm: ProfileManager):
        assert _profile_delete(tmp_pm, ["ghost"]) == 1

    def test_delete_ok(self, tmp_pm: ProfileManager, tmp_path: Path):
        tmp_pm.create("bye", PipelineConfig())
        assert _profile_delete(tmp_pm, ["bye"]) == 0
        assert not (tmp_path / "bye.yaml").exists()

    def test_export_ok(self, tmp_pm: ProfileManager, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        tmp_pm.create("exp", PipelineConfig())
        out = tmp_path / "out.yaml"
        code = _profile_export(tmp_pm, ["exp", "-o", str(out)])
        assert code == 0
        assert out.exists()
        assert "已导出" in capsys.readouterr().out

    def test_export_missing_exit_2(self, tmp_pm: ProfileManager):
        assert _profile_export(tmp_pm, ["ghost"]) == 2

    def test_import_ok(self, tmp_pm: ProfileManager, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        src = tmp_path / "src.yaml"
        src.write_text(yaml.safe_dump({
            "schema_version": 1,
            "profile": {"name": "incoming", "plugins": {"test": ["unit"]}, "params": {}},
        }), encoding="utf-8")
        code = _profile_import(tmp_pm, [str(src)])
        assert code == 0
        assert (tmp_path / "incoming.yaml").exists()
        assert "已导入" in capsys.readouterr().out

    def test_import_conflict_exit_2(self, tmp_pm: ProfileManager, tmp_path: Path):
        src = tmp_path / "src.yaml"
        src.write_text(yaml.safe_dump({
            "schema_version": 1,
            "profile": {"name": "incoming", "plugins": {"test": ["unit"]}, "params": {}},
        }), encoding="utf-8")
        tmp_pm.import_file(src)
        assert _profile_import(tmp_pm, [str(src)]) == 2

    def test_show_ok(self, tmp_pm: ProfileManager, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        tmp_pm.create("shown", PipelineConfig())
        assert _profile_show(tmp_pm, "shown") == 0
        assert "schema_version" in capsys.readouterr().out

    def test_show_missing_exit_2(self, tmp_pm: ProfileManager):
        assert _profile_show(tmp_pm, "ghost") == 2


# ── main() 分发 / convert_main 退出码 ──────────────────────────────────


class TestMainDispatch:
    def test_version(self, capsys: pytest.CaptureFixture[str]):
        code = main(["--version"])
        assert code == 0
        assert "CIS2HDL v" in capsys.readouterr().out

    def test_unknown_command(self, capsys: pytest.CaptureFixture[str]):
        code = main(["bogus"])
        assert code == 1
        assert "Usage" in capsys.readouterr().out

    def test_profile_list(self, capsys: pytest.CaptureFixture[str]):
        code = main(["profile", "list"])
        assert code == 0
        out = capsys.readouterr().out
        assert "default" in out
        assert "BUILTIN" in out

    def test_convert_missing_file_exit_1(self, capsys: pytest.CaptureFixture[str]):
        code = convert_main(["no_such_file.dsn"])
        assert code == 1
        assert "file not found" in capsys.readouterr().out

    def test_convert_missing_pipeline_exit_1(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        # 输入文件需存在，才能走到 pipeline 定位步骤
        inp = tmp_path / "in.dsn"
        inp.write_text("dummy", encoding="utf-8")
        code = convert_main([str(inp), "--pipeline", str(tmp_path / "nope.yaml")])
        assert code == 1
        assert "pipeline.yaml 不存在" in capsys.readouterr().out

    def test_convert_no_input_exits_2(self):
        # argparse parser.error → SystemExit(2)
        with pytest.raises(SystemExit) as exc:
            convert_main([])
        assert exc.value.code == 2
