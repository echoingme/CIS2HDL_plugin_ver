"""S9 GUI 测试 — PipelineController（§3.1 全部接口，mock 无 PySide6）。

覆盖：list/load/save/delete/export/import/check_duplicate + 插件清单/schema
+ 参数应用 + 手动匹配 + mock 前缀 + 转换前置校验。
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cis2hdl.core.pipeline_config import PipelineConfig
from cis2hdl.gui.controller import (
    ControllerError,
    DuplicateInfo,
    PipelineController,
)

REPO_PROFILES = Path(__file__).resolve().parents[2] / "profiles"


@pytest.fixture()
def ctl(tmp_path: Path) -> PipelineController:
    """隔离的 PipelineController（临时 profiles 目录 + 拷贝内置 profile）。"""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    for src in REPO_PROFILES.glob("*.yaml"):
        shutil.copy2(src, profiles_dir / src.name)
    return PipelineController(profiles_dir=profiles_dir)


# ── Profile 管理 ──────────────────────────────────────────────────────────


def test_list_profiles(ctl: PipelineController) -> None:
    names = ctl.list_profiles()
    assert "default" in names
    assert "max-beauty" in names
    infos = {i["name"]: i for i in ctl.profile_infos()}
    assert infos["default"]["builtin"] is True


def test_load_profile(ctl: PipelineController) -> None:
    cfg = ctl.load_profile("max-beauty")
    assert cfg.profile == "max-beauty"
    # 当前配置同步
    assert ctl.current_config.profile == "max-beauty"


def test_save_and_delete_custom_profile(ctl: PipelineController) -> None:
    cfg = ctl.load_profile("default")
    cfg.beautify.params.text_layout.enabled = True
    ctl.save_profile("my-design", cfg)
    assert "my-design" in ctl.list_profiles()
    loaded = ctl.load_profile("my-design")
    assert loaded.beautify.params.text_layout.enabled is True
    ctl.delete_profile("my-design")
    assert "my-design" not in ctl.list_profiles()


def test_delete_builtin_rejected(ctl: PipelineController) -> None:
    from cis2hdl.core.profile_manager import ProfileReadOnlyError

    with pytest.raises(ProfileReadOnlyError):
        ctl.delete_profile("default")


def test_save_builtin_rejected(ctl: PipelineController) -> None:
    from cis2hdl.core.profile_manager import ProfileReadOnlyError

    with pytest.raises(ProfileReadOnlyError):
        ctl.save_profile("default", ctl.current_config)


def test_export_profile(ctl: PipelineController, tmp_path: Path) -> None:
    out = tmp_path / "exported.yaml"
    path = ctl.export_profile("default", out)
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "profile:" in text


def test_import_profile(ctl: PipelineController, tmp_path: Path) -> None:
    src = tmp_path / "foreign.yaml"
    src.write_text(
        "schema_version: 1\n"
        "profile:\n"
        "  name: foreign-design\n"
        "  builtin: false\n"
        "  plugins:\n"
        "    input: [edif]\n"
        "    match: [exact]\n"
        "    beautify: [overlap_resolve]\n"
        "    output: [csa]\n"
        "    test: [unit]\n"
        "  params: {}\n",
        encoding="utf-8",
    )
    name = ctl.import_profile(src)
    assert name == "foreign-design"
    assert "foreign-design" in ctl.list_profiles()


def test_import_profile_conflict_rename(ctl: PipelineController, tmp_path: Path) -> None:
    # 先建一个已存在的自定义 profile（改动参数避免查重），制造名称冲突
    cfg = ctl.load_profile("default")
    cfg.beautify.params.text_layout.enabled = True
    ctl.save_profile("dup-design", cfg)
    src = tmp_path / "dup.yaml"
    src.write_text(
        "schema_version: 1\n"
        "profile:\n"
        "  name: dup-design\n"
        "  builtin: false\n"
        "  plugins:\n"
        "    input: [edif]\n"
        "    match: [exact]\n"
        "    beautify: [overlap_resolve]\n"
        "    output: [csa]\n"
        "    test: [unit]\n"
        "  params: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(FileExistsError):
        ctl.import_profile(src)
    name = ctl.import_profile(src, rename_to="dup-copy")
    assert name == "dup-copy"


# ── 查重 ──────────────────────────────────────────────────────────────────


def test_check_duplicate_ok(ctl: PipelineController) -> None:
    cfg = ctl.load_profile("default")
    # 改插件组合（组合不同 → 不判重）
    cfg.beautify.plugins.append("wire_simplify")
    assert ctl.check_duplicate("new-design", cfg) is None


def test_check_duplicate_full(ctl: PipelineController) -> None:
    cfg = ctl.load_profile("fast")
    info = ctl.check_duplicate("new-name", cfg)
    assert info is not None
    assert isinstance(info, DuplicateInfo)
    assert info.status == "duplicate"
    assert info.duplicate_of == "fast"


def test_check_duplicate_same_combo_diff_params(ctl: PipelineController) -> None:
    cfg = ctl.load_profile("max-beauty")
    # max-beauty 未设置 overlap.avoid_margin → 组合同、参数异
    cfg.beautify.params.overlap.avoid_margin = 123
    info = ctl.check_duplicate("tweak", cfg)
    assert info is not None
    assert info.status == "same_combo_diff_params"
    assert "beautify" in info.stage or info.param_diffs


# ── 插件清单与 schema ─────────────────────────────────────────────────────


def test_list_plugins_by_stage(ctl: PipelineController) -> None:
    beautify = ctl.list_plugins("beautify")
    names = {m.name for m in beautify}
    assert "overlap_resolve" in names
    assert "text_layout" in names
    assert all(m.stage == "beautify" for m in beautify)
    assert ctl.list_plugins("input")  # 非空


def test_get_plugin_schema_types(ctl: PipelineController) -> None:
    schema = ctl.get_plugin_schema("overlap_resolve")
    by_key = {f["key"]: f for f in schema["fields"]}
    assert by_key["resolve"]["type"] == "bool"
    assert by_key["avoid_margin"]["type"] == "int"

    schema = ctl.get_plugin_schema("text_layout")
    assert schema["fields"][0]["type"] == "bool"

    schema = ctl.get_plugin_schema("exact")
    by_key = {f["key"]: f for f in schema["fields"]}
    assert by_key["weights"]["type"] == "dict"

    schema = ctl.get_plugin_schema("unit")
    assert schema["fields"][0]["type"] == "list"


def test_apply_plugin_param_updates_cfg(ctl: PipelineController) -> None:
    ctl.load_profile("default")
    ctl.apply_plugin_param("text_layout", "beautify.text_layout.enabled", True)
    assert ctl.current_config.beautify.params.text_layout.enabled is True


def test_apply_plugin_param_rejects_foreign_path(ctl: PipelineController) -> None:
    ctl.load_profile("default")
    with pytest.raises(ControllerError):
        ctl.apply_plugin_param("text_layout", "beautify.overlap.resolve", True)


def test_current_plugin_params(ctl: PipelineController) -> None:
    ctl.load_profile("default")
    paths = ctl.current_plugin_params("overlap_resolve")
    assert "beautify.overlap.resolve" in paths
    assert paths["beautify.overlap.resolve"] is True


# ── 手动匹配 / mock ───────────────────────────────────────────────────────


def test_set_manual_match_writes_chip_config(ctl: PipelineController, tmp_path: Path) -> None:
    ctl.load_profile("default")
    ctl.set_output_dir(tmp_path / "out")
    ctl.set_manual_match("R12", "RES_0603", force_mock=False)
    cfg = ctl.current_config
    assert cfg.match.manual_overrides.file != ""
    chip = Path(cfg.match.manual_overrides.file)
    assert chip.exists()
    text = chip.read_text(encoding="utf-8")
    assert "R12" in text and "RES_0603" in text


def test_set_manual_match_clear(ctl: PipelineController, tmp_path: Path) -> None:
    ctl.load_profile("default")
    ctl.set_output_dir(tmp_path / "out")
    ctl.set_manual_match("U3", "CH347", force_mock=False)
    ctl.set_manual_match("U3", None, force_mock=False)
    assert ctl.current_config.match.manual_overrides.file == ""


def test_set_manual_match_force_mock_prefix(ctl: PipelineController, tmp_path: Path) -> None:
    ctl.load_profile("default")
    ctl.set_output_dir(tmp_path / "out")
    ctl.set_manual_match("J9", "CONN_2X5", force_mock=True)
    assert "J" in ctl.current_config.match.mock.prefixes


def test_toggle_mock_prefix(ctl: PipelineController) -> None:
    ctl.load_profile("default")
    prefixes = ctl.current_config.match.mock.prefixes
    ctl.toggle_mock_prefix("IC", True)
    assert "IC" in prefixes
    ctl.toggle_mock_prefix("IC", False)
    assert "IC" not in prefixes


# ── 转换前置校验 ──────────────────────────────────────────────────────────


def test_run_conversion_requires_input(ctl: PipelineController) -> None:
    with pytest.raises(ControllerError):
        ctl.run_conversion(ctl.current_config)


def test_save_pipeline_atomic(ctl: PipelineController, tmp_path: Path) -> None:
    target = tmp_path / "pipeline.yaml"
    ctl.save_pipeline(target)
    assert target.exists()
    parsed = PipelineConfig.from_yaml(target)
    assert parsed.to_dict() == ctl.current_config.to_dict()
