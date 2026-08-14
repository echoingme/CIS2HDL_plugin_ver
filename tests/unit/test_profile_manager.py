"""S1 T03 — ProfileManager 配置服务单元测试。

Covers（docs/S1-config-design.md T03）：
  * list_profiles（内置 4 个、排序、损坏条目跳过）
  * get() 合并逻辑（default 增量覆盖、output 扩展）
  * create() 查重全分支（duplicate / 组合同参数异 / 名称冲突 / 内置只读 / 非法名）
  * delete()（内置拒绝 / 不存在 / 自定义成功）
  * export()（builtin→false、去 created、原子写）
  * import_file()（成功 / rename / 白名单拒绝 / schema_version>1 拒绝）
  * diff() / diff_all()（插件组合 set 比较 + 参数深度比较）
  * 原子写无 .tmp 残留
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from cis2hdl.core.config import RoutingConfig
from cis2hdl.core.pipeline_config import PipelineConfig
from cis2hdl.core.profile_manager import (
    BUILTIN_PLUGIN_NAMES,
    STAGES,
    DuplicateProfileError,
    ProfileError,
    ProfileManager,
    ProfileReadOnlyError,
)


@pytest.fixture()
def pm(tmp_path: Path) -> ProfileManager:
    """隔离的 ProfileManager（临时 profiles 目录，不污染仓库内置）。"""
    return ProfileManager(profiles_dir=tmp_path)


@pytest.fixture()
def repo_pm() -> ProfileManager:
    """读仓库内置 profiles/ 的 ProfileManager（只读验证用）。"""
    return ProfileManager()


# ── list_profiles ───────────────────────────────────────────────────────


class TestListProfiles:
    def test_builtin_four(self, repo_pm: ProfileManager):
        names = [i.name for i in repo_pm.list_profiles()]
        assert set(names) == {"default", "max-beauty", "fast", "match-only"}
        for i in repo_pm.list_profiles():
            assert i.builtin is True

    def test_sort_builtin_first(self, pm: ProfileManager):
        pm._atomic_write(pm.profiles_dir / "zebra.yaml", yaml.safe_dump(
            {"schema_version": 1, "profile": {"name": "zebra", "builtin": False, "plugins": {"test": ["unit"]}}}
        ))
        infos = pm.list_profiles()
        assert infos[-1].name == "zebra"  # 自定义排在内置之后

    def test_broken_entry_skipped(self, pm: ProfileManager, tmp_path: Path):
        (tmp_path / "broken.yaml").write_text("::: not yaml :::", encoding="utf-8")
        infos = pm.list_profiles()
        assert all(i.name != "broken" for i in infos)


# ── get() 合并逻辑 ─────────────────────────────────────────────────────


class TestGet:
    def test_get_default_equals_pipeline_defaults(self, repo_pm: ProfileManager):
        cfg = repo_pm.get("default")
        assert cfg.profile == "default"
        assert cfg.beautify.plugins == ["overlap_resolve", "gnd_cluster", "parallel_short"]
        assert cfg.beautify.params.mode == "p0"

    def test_get_max_beauty_incremental(self, repo_pm: ProfileManager):
        cfg = repo_pm.get("max-beauty")
        assert cfg.beautify.params.mode == "detour"
        assert cfg.beautify.params.wire_simplify.enabled is True
        assert cfg.beautify.params.text_layout.enabled is True
        # 未提及字段保持默认
        assert cfg.beautify.params.overlap.check is False
        assert cfg.beautify.params.gnd_distribution.enabled is False

    def test_get_fast(self, repo_pm: ProfileManager):
        cfg = repo_pm.get("fast")
        assert cfg.test.suites == []
        assert cfg.beautify.params.report.always_write is False

    def test_get_match_only_output_extension(self, repo_pm: ProfileManager):
        cfg = repo_pm.get("match-only")
        assert cfg.beautify.plugins == []
        assert cfg.test.suites == []
        assert cfg.output.reports == ["mapping"]

    def test_get_missing_raises(self, pm: ProfileManager):
        with pytest.raises(ProfileError):
            pm.get("no-such-profile")


# ── create() 查重全分支 ────────────────────────────────────────────────


def _custom_cfg(**kwargs) -> PipelineConfig:
    cfg = PipelineConfig()
    for key, value in kwargs.items():
        if key == "mode":
            cfg.beautify.params.mode = value
        elif key == "report_off":
            cfg.beautify.params.report.always_write = False
        elif key == "beautify_plugins":
            cfg.beautify.plugins = value
        elif key == "test_suites":
            cfg.test.suites = value
        elif key == "output_reports":
            cfg.output.reports = value
    return cfg


class TestCreate:
    def test_create_writes_atomic_file(self, pm: ProfileManager, tmp_path: Path):
        pm.create("my-x", _custom_cfg(mode="detour"))
        out = tmp_path / "my-x.yaml"
        assert out.exists()
        data = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert data["profile"]["name"] == "my-x"
        assert data["profile"]["builtin"] is False
        assert data["profile"]["params"]["routing"]["mode"] == "detour"
        # plugins 全量快照
        assert data["profile"]["plugins"]["beautify"] == [
            "overlap_resolve", "gnd_cluster", "parallel_short",
        ]

    def test_create_incremental_params_only_diffs(self, pm: ProfileManager, tmp_path: Path):
        pm.create("minimal", _custom_cfg())
        data = yaml.safe_load((tmp_path / "minimal.yaml").read_text(encoding="utf-8"))
        assert data["profile"]["params"] == {}  # 与默认全等 → 无增量

    def test_create_duplicate_rejected(self, pm: ProfileManager):
        pm.create("dup-a", _custom_cfg(mode="detour"))
        with pytest.raises(DuplicateProfileError) as exc:
            pm.create("dup-b", _custom_cfg(mode="detour"))
        assert exc.value.duplicate_of == "dup-a"

    def test_create_same_combos_diff_params_allowed(self, pm: ProfileManager):
        pm.create("same-a", _custom_cfg(mode="detour"))
        pm.create("same-b", _custom_cfg(mode="detour", report_off=True))  # 不抛错
        assert pm.last_note != ""
        assert "same-a" in pm.last_note

    def test_create_name_conflict_rejected(self, pm: ProfileManager):
        pm.create("conflict", _custom_cfg())
        with pytest.raises(FileExistsError):
            pm.create("conflict", _custom_cfg(mode="detour"))

    def test_create_overwrite_allowed(self, pm: ProfileManager, tmp_path: Path):
        pm.create("ow", _custom_cfg())
        pm.create("ow", _custom_cfg(mode="detour"), overwrite=True)
        data = yaml.safe_load((tmp_path / "ow.yaml").read_text(encoding="utf-8"))
        assert data["profile"]["params"]["routing"]["mode"] == "detour"

    def test_create_builtin_name_rejected(self, pm: ProfileManager):
        with pytest.raises(ProfileReadOnlyError):
            pm.create("default", _custom_cfg())

    def test_create_invalid_name(self, pm: ProfileManager):
        for bad in ("", "  ", "a b", "1bad*start", "x" * 65, "-lead-dash"):
            with pytest.raises(ProfileError):
                pm.create(bad, _custom_cfg())

    def test_create_output_extension_stored(self, pm: ProfileManager, tmp_path: Path):
        pm.create("report-only", _custom_cfg(output_reports=["mapping"]))
        data = yaml.safe_load((tmp_path / "report-only.yaml").read_text(encoding="utf-8"))
        assert data["profile"]["output"]["reports"] == ["mapping"]


# ── delete() ────────────────────────────────────────────────────────────


class TestDelete:
    def test_delete_builtin_rejected(self, repo_pm: ProfileManager):
        with pytest.raises(ProfileReadOnlyError):
            repo_pm.delete("default")

    def test_delete_missing_raises(self, pm: ProfileManager):
        with pytest.raises(FileNotFoundError):
            pm.delete("ghost")

    def test_delete_custom_success(self, pm: ProfileManager, tmp_path: Path):
        pm.create("bye", _custom_cfg())
        pm.delete("bye")
        assert not (tmp_path / "bye.yaml").exists()


# ── export() ────────────────────────────────────────────────────────────


class TestExport:
    def test_export_builtin_flips_flag_and_drops_created(self, repo_pm: ProfileManager, tmp_path: Path):
        out = repo_pm.export("max-beauty", tmp_path / "mb.yaml")
        assert out == tmp_path / "mb.yaml"
        data = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert data["profile"]["builtin"] is False
        assert "created" not in data["profile"]
        assert data["profile"]["name"] == "max-beauty"

    def test_export_default_path(self, repo_pm: ProfileManager):
        out = repo_pm.export("fast")
        assert out.name.startswith("export_fast_")
        assert out.parent == repo_pm.profiles_dir
        out.unlink()  # 清理

    def test_export_missing_raises(self, pm: ProfileManager):
        with pytest.raises(ProfileError):
            pm.export("ghost")


# ── import_file() ───────────────────────────────────────────────────────


def _importable_yaml(name: str = "imported", plugins=None, params=None, schema=1) -> str:
    return yaml.safe_dump({
        "schema_version": schema,
        "profile": {
            "name": name,
            "description": "imported",
            "plugins": plugins or {"test": ["unit"]},
            "params": params or {},
        },
    }, allow_unicode=True)


class TestImport:
    def test_import_success(self, pm: ProfileManager, tmp_path: Path):
        src = tmp_path / "src.yaml"
        src.write_text(_importable_yaml(), encoding="utf-8")
        name = pm.import_file(src)
        assert name == "imported"
        assert (pm.profiles_dir / "imported.yaml").exists()

    def test_import_rename(self, pm: ProfileManager, tmp_path: Path):
        src = tmp_path / "src.yaml"
        src.write_text(_importable_yaml(), encoding="utf-8")
        name = pm.import_file(src, rename_to="renamed")
        assert name == "renamed"
        assert not (pm.profiles_dir / "imported.yaml").exists()
        assert (pm.profiles_dir / "renamed.yaml").exists()

    def test_import_conflict_requires_rename(self, pm: ProfileManager, tmp_path: Path):
        src = tmp_path / "src.yaml"
        src.write_text(_importable_yaml(), encoding="utf-8")
        pm.import_file(src)
        with pytest.raises(FileExistsError):
            pm.import_file(src)

    def test_import_unknown_plugin_rejected(self, pm: ProfileManager, tmp_path: Path):
        src = tmp_path / "bad.yaml"
        src.write_text(_importable_yaml(plugins={"beautify": ["not_a_plugin"]}), encoding="utf-8")
        with pytest.raises(ProfileError) as exc:
            pm.import_file(src)
        assert "not_a_plugin" in str(exc.value)

    def test_import_schema_too_new_rejected(self, pm: ProfileManager, tmp_path: Path):
        src = tmp_path / "new.yaml"
        src.write_text(_importable_yaml(schema=99), encoding="utf-8")
        with pytest.raises(ProfileError):
            pm.import_file(src)

    def test_import_builtin_name_rejected(self, pm: ProfileManager, tmp_path: Path):
        src = tmp_path / "def.yaml"
        src.write_text(_importable_yaml(name="default"), encoding="utf-8")
        with pytest.raises(ProfileReadOnlyError):
            pm.import_file(src)

    def test_import_missing_plugins_rejected(self, pm: ProfileManager, tmp_path: Path):
        src = tmp_path / "empty.yaml"
        src.write_text(yaml.safe_dump({
            "schema_version": 1,
            "profile": {"name": "empty", "plugins": {"test": []}},
        }), encoding="utf-8")
        with pytest.raises(ProfileError):
            pm.import_file(src)

    def test_import_round_trip_get(self, pm: ProfileManager, tmp_path: Path):
        src = tmp_path / "rt.yaml"
        src.write_text(_importable_yaml(
            plugins={"beautify": ["gnd_cluster"], "test": ["unit", "e2e"]},
            params={"gnd_distribution": {"cluster_radius": 700}},
        ), encoding="utf-8")
        pm.import_file(src)
        cfg = pm.get("imported")
        assert cfg.beautify.plugins == ["gnd_cluster"]
        assert cfg.test.suites == ["unit", "e2e"]
        assert cfg.beautify.params.gnd_distribution.cluster_radius == 700


# ── diff() / diff_all() ─────────────────────────────────────────────────


class TestDiff:
    def test_diff_equivalent(self, pm: ProfileManager):
        a = _custom_cfg(mode="detour")
        b = _custom_cfg(mode="detour")
        d = pm.diff(a, b)
        assert d.equivalent is True
        assert d.stage == ""

    def test_diff_plugin_stage_first(self, pm: ProfileManager):
        a = _custom_cfg()
        b = _custom_cfg(beautify_plugins=["gnd_cluster"])
        d = pm.diff(a, b)
        assert d.equivalent is False
        assert d.stage == "beautify"
        assert d.removed == ["overlap_resolve", "parallel_short"]
        assert d.added == []

    def test_diff_params_only(self, pm: ProfileManager):
        a = _custom_cfg()
        b = _custom_cfg(mode="detour", report_off=True)
        d = pm.diff(a, b)
        assert d.stage == "beautify"
        assert d.equivalent is False
        assert d.param_diffs["routing"]["mode"] == ("p0", "detour")
        assert d.param_diffs["report"]["always_write"] == (True, False)

    def test_diff_order_insensitive(self, pm: ProfileManager):
        a = _custom_cfg()
        b = _custom_cfg(beautify_plugins=["parallel_short", "gnd_cluster", "overlap_resolve"])
        d = pm.diff(a, b)
        assert d.equivalent is True  # 顺序无关

    def test_diff_all_stages(self, pm: ProfileManager):
        a = _custom_cfg()
        b = _custom_cfg(test_suites=[])
        diffs = pm.diff_all(a, b)
        assert len(diffs) == len(STAGES) + 1
        by_stage = {d.stage: d for d in diffs}
        assert by_stage["test"].equivalent is False
        assert by_stage["input"].equivalent is True
        assert by_stage["beautify.params"].equivalent is True


# ── 原子写 / 白名单常量 ────────────────────────────────────────────────


class TestAtomicWrite:
    def test_no_tmp_residue(self, pm: ProfileManager, tmp_path: Path):
        pm.create("atomic", _custom_cfg(mode="detour"))
        leftovers = list(tmp_path.glob(".*.tmp"))
        assert leftovers == []

    def test_overwrite_no_tmp_residue(self, pm: ProfileManager, tmp_path: Path):
        pm.create("a2", _custom_cfg())
        pm.create("a2", _custom_cfg(mode="detour"), overwrite=True)
        assert list(tmp_path.glob(".*.tmp")) == []


class TestPluginWhitelist:
    def test_whitelist_covers_all_stages(self):
        assert set(BUILTIN_PLUGIN_NAMES) == set(STAGES)
        for stage, names in BUILTIN_PLUGIN_NAMES.items():
            assert len(names) > 0
            assert all(isinstance(n, str) for n in names)
