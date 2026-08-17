"""S10 T — CLI 旧参数移除与迁移提示单元测试（兼容窗口结束）。

S10 起（docs/developer-guide.md S10 章节）：
  * 20 个旧行为参数（--routing/--aesthetic/--wire-simplify/... 全量见
    ``_REMOVED_FLAGS_TARGETS``）已从 convert 移除——传入即报错
    （SystemExit(2)），文案包含 pipeline.yaml 迁移目标与迁移对照表。
  * 路径类参数保留：``--output / --hdl-lib / --extra-hdl-lib``（无 deprecation，
    直接覆盖 cfg，CLI 覆盖 yaml 语义与旧 CLI 一致）。
  * ``--profile / --pipeline`` 保留。
  * profile 子命令 + main 分发 + convert_main 退出码行为不变。

覆盖：
  * 20 个移除参数逐个 → 报错 + 迁移提示（含 ``--flag=value`` 形式）
  * 真未知参数 → "unrecognized arguments"（argparse 标准）
  * 保留路径类参数仍可解析并覆盖 cfg
  * profile 子命令成功/失败路径 + 退出码 0/1/2/3
  * convert_main 缺文件/缺 pipeline 路径的退出码
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
import yaml

from cis2hdl.cli import (
    _REMOVED_FLAGS_TARGETS,
    _apply_path_args,
    _build_convert_parser,
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

# ── S10：旧参数移除 → 迁移报错（全量 20 个） ─────────────────────────────


class TestRemovedFlags:
    @pytest.mark.parametrize("flag", sorted(_REMOVED_FLAGS_TARGETS))
    def test_removed_flag_errors_with_migration_hint(
        self, flag: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """每个移除参数：convert_main 报 SystemExit(2) + 迁移提示。

        输入文件故意不存在——移除参数检查先于文件存在性检查，报错文案
        必须包含该参数已移除与 pipeline.yaml 迁移目标。
        """
        with pytest.raises(SystemExit) as exc:
            convert_main(["no_such_file.dsn", flag])
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert f"{flag} 已移除" in err
        assert "pipeline.yaml" in err
        assert "S10" in err

    @pytest.mark.parametrize("flag", sorted(_REMOVED_FLAGS_TARGETS))
    def test_removed_flag_equals_form_errors(
        self, flag: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--flag=value`` 形式同样报迁移错误（split('=') 识别）。"""
        with pytest.raises(SystemExit) as exc:
            convert_main(["in.dsn", f"{flag}=x"])
        assert exc.value.code == 2
        assert f"{flag} 已移除" in capsys.readouterr().err

    def test_removed_flag_value_token_also_rejected(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """取值型参数（--routing detour）的值 token 不再被吞。"""
        with pytest.raises(SystemExit) as exc:
            convert_main(["in.dsn", "--routing", "detour"])
        assert exc.value.code == 2
        assert "--routing 已移除" in capsys.readouterr().err

    def test_unknown_flag_is_standard_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """真未知参数：argparse 标准 unrecognized arguments。"""
        with pytest.raises(SystemExit) as exc:
            convert_main(["in.dsn", "--no-such-flag"])
        assert exc.value.code == 2
        assert "unrecognized arguments" in capsys.readouterr().err


# ── S10：保留路径类参数 ──────────────────────────────────────────────────


def _path_ns(**overrides: object) -> argparse.Namespace:
    base = argparse.Namespace(output=None, hdl_lib=None, extra_hdl_lib=[])
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


class TestKeptPathArgs:
    def test_output_overrides_engine(self) -> None:
        cfg = PipelineConfig()
        _apply_path_args(cfg, _path_ns(output="out_dir"))
        assert cfg.engine.output_dir == "out_dir"

    def test_hdl_lib_overrides_input(self) -> None:
        cfg = PipelineConfig()
        _apply_path_args(cfg, _path_ns(hdl_lib="lib"))
        assert cfg.input.hdl_lib == "lib"

    def test_extra_hdl_lib_append(self) -> None:
        cfg = PipelineConfig()
        _apply_path_args(cfg, _path_ns(extra_hdl_lib=["a", "b"]))
        assert cfg.input.extra_hdl_libs == ["a", "b"]

    def test_none_path_args_leave_defaults(self) -> None:
        cfg = PipelineConfig()
        _apply_path_args(cfg, _path_ns())
        assert cfg.engine.output_dir == "output"
        assert cfg.input.hdl_lib == ""
        assert cfg.input.extra_hdl_libs == []

    def test_parser_accepts_path_args(self) -> None:
        """保留路径参数仍可被 convert 解析器接受（无 unknown）。"""
        parser = _build_convert_parser()
        args, unknown = parser.parse_known_args(
            ["in.dsn", "--output", "o", "--hdl-lib", "h",
             "--extra-hdl-lib", "x", "--extra-hdl-lib", "y"]
        )
        assert unknown == []
        assert args.output == "o"
        assert args.hdl_lib == "h"
        assert args.extra_hdl_lib == ["x", "y"]

    def test_path_args_overlay_profile(self) -> None:
        """保留路径参数叠加 profile：--output 覆盖 profile 的 engine.output_dir。"""
        pm = ProfileManager()
        cfg = pm.get("fast")
        _apply_path_args(cfg, _path_ns(output="custom_out"))
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
