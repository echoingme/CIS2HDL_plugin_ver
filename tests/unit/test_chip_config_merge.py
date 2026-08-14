"""Phase XVII M8 — chip_config / manual_matches 统一合并（用户 D7）。

Covers:
  * ManualMatch 扩展字段（pin_map/hanging/placement）
  * ManualMatchesConfig.load v2.0 解析 + v1.0 兼容升级
  * dump/write_yaml（统一 chip_config.yaml v2.0 schema）
  * load_merged：v2.0 覆盖 v1.0 同 refdes
  * apply_manual_matches 消费 pin_map/hanging/placement
"""

from __future__ import annotations

from pathlib import Path


class TestManualMatchFields:
    def test_extra_fields_default(self):
        from cis2hdl.core.matcher.manual_matches import ManualMatch

        mm = ManualMatch("U6H", "u6h_ph")
        assert mm.pin_map == {}
        assert mm.hanging == []
        assert mm.placement == {}

    def test_to_dict(self):
        from cis2hdl.core.matcher.manual_matches import ManualMatch

        mm = ManualMatch(
            "U6H", "u6h_ph", pin_map={"K18": "18"},
            hanging=["V25"], placement={"dx": 25},
        )
        d = mm.to_dict()
        assert d["refdes"] == "U6H"
        assert d["pin_map"] == {"K18": "18"}
        assert d["hanging"] == ["V25"]
        assert d["placement"] == {"dx": 25}


class TestLoadV2:
    def test_load_v2_fields(self, tmp_path):
        from cis2hdl.core.matcher.manual_matches import ManualMatchesConfig

        p = tmp_path / "chip_config.yaml"
        p.write_text(
            'version: "2.0"\n'
            "matches:\n"
            "  - refdes: U6H\n"
            "    library_id: u6h_ph\n"
            "    pin_map:\n"
            "      K18: '18'\n"
            "      G20: '20'\n"
            "    hanging: [V25, W27]\n",
            encoding="utf-8",
        )
        cfg = ManualMatchesConfig.load(p)
        assert cfg.version == "2.0"
        mm = cfg.matches[0]
        assert mm.pin_map == {"K18": "18", "G20": "20"}
        assert mm.hanging == ["V25", "W27"]

    def test_load_v1_auto_upgrade(self, tmp_path):
        from cis2hdl.core.matcher.manual_matches import ManualMatchesConfig

        p = tmp_path / "manual.yaml"
        p.write_text(
            'version: "1.0"\n'
            "matches:\n"
            "  - refdes: U1\n"
            "    library_id: CAPACITOR\n"
            "    section: 1\n",
            encoding="utf-8",
        )
        cfg = ManualMatchesConfig.load(p)
        assert cfg.matches[0].library_id == "CAPACITOR"
        assert cfg.matches[0].pin_map == {}
        assert cfg.matches[0].hanging == []

    def test_load_invalid_raises(self, tmp_path):
        from cis2hdl.core.matcher.manual_matches import ManualMatchesConfig

        p = tmp_path / "bad.yaml"
        p.write_text("not_a_mapping: true\n", encoding="utf-8")
        import pytest

        with pytest.raises(ValueError):
            ManualMatchesConfig.load(p)


class TestDumpWrite:
    def test_write_and_reload_roundtrip(self, tmp_path):
        from cis2hdl.core.matcher.manual_matches import (
            ManualMatch,
            ManualMatchesConfig,
        )

        cfg = ManualMatchesConfig(version="2.0", matches=[
            ManualMatch("U6H", "u6h_ph", pin_map={"K18": "18"}),
        ])
        p = cfg.write_yaml(tmp_path / "chip_config.yaml")
        assert p.exists()
        loaded = ManualMatchesConfig.load(p)
        assert loaded.matches[0].pin_map == {"K18": "18"}


class TestLoadMerged:
    def _write(self, path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")

    def test_v2_overrides_v1_same_refdes(self, tmp_path):
        from cis2hdl.core.matcher.manual_matches import load_merged

        v1 = tmp_path / "manual.yaml"
        v2 = tmp_path / "chip_config.yaml"
        self._write(
            v1,
            'version: "1.0"\nmatches:\n'
            "  - refdes: U1\n    library_id: CAPACITOR\n"
            "  - refdes: U2\n    library_id: RESISTOR\n",
        )
        self._write(
            v2,
            'version: "2.0"\nmatches:\n'
            "  - refdes: U1\n    library_id: DIODE\n    hanging: ['3']\n",
        )
        merged = load_merged(v2, v1)
        by_ref = {m.refdes.upper(): m for m in merged.matches}
        # v2.0 覆盖 v1.0 同 refdes U1
        assert by_ref["U1"].library_id == "DIODE"
        assert by_ref["U1"].hanging == ["3"]
        # v1.0 独有条目保留
        assert by_ref["U2"].library_id == "RESISTOR"

    def test_only_legacy(self, tmp_path):
        from cis2hdl.core.matcher.manual_matches import load_merged

        v1 = tmp_path / "manual.yaml"
        self._write(v1, 'version: "1.0"\nmatches:\n  - refdes: U1\n    library_id: C\n')
        merged = load_merged(None, v1)
        assert len(merged.matches) == 1

    def test_only_chip_config(self, tmp_path):
        from cis2hdl.core.matcher.manual_matches import load_merged

        v2 = tmp_path / "chip_config.yaml"
        self._write(v2, 'version: "2.0"\nmatches:\n  - refdes: U1\n    library_id: D\n')
        merged = load_merged(v2, None)
        assert len(merged.matches) == 1

    def test_missing_files_warn_not_raise(self, tmp_path):
        from cis2hdl.core.matcher.manual_matches import load_merged

        merged = load_merged(tmp_path / "missing.yaml", None)
        assert merged.matches == []


class TestApplyManualMatches:
    def _make_result(self):
        from cis2hdl.core.ir.match import MatchResult, MatchStrategy

        m = MatchResult(
            source_library_id="U6H",
            target_library_id="auto_fallback",
            confidence=0.3,
            strategy=MatchStrategy.FUZZY,
        )
        m.extra_data["hdl_pin_count"] = 2
        return m

    def test_apply_consumes_new_fields(self):
        from cis2hdl.core.matcher.manual_matches import (
            ManualMatch,
            ManualMatchesConfig,
            apply_manual_matches,
        )

        class _Comp:
            library_id = "u6h_ph"
            pins = [object(), object()]

        class _DB:
            def get_by_library_id(self, lid):
                return _Comp() if lid == "u6h_ph" else None

        result = self._make_result()
        manual = ManualMatchesConfig(version="2.0", matches=[
            ManualMatch(
                "U6H", "u6h_ph", pin_map={"K18": "18"},
                hanging=["V25"], placement={"dx": 25},
            ),
        ])
        results, warnings = apply_manual_matches(
            [result], manual, _DB(),
        )
        assert not warnings
        m = results[0]
        assert m.pin_mapping == {"K18": "18"}
        assert m.extra_data["hanging_pins"] == ["V25"]
        assert m.extra_data["placement"] == {"dx": 25}
