"""Phase XIV T6 — D3 人工匹配 → 自动配线（manual_matches.py）。

Covers:
  * ManualMatchesConfig.load 解析
  * apply_manual_matches 覆盖后 strategy=MANUAL / confidence=1.0
  * 引脚数不匹配 → warning 且不崩溃（保留自动结果）
  * 未知 library_id → 忽略
  * export_unmatched 输出 candidates（含电源候选）
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cis2hdl.core.ir.match import MatchResult, MatchStrategy


def _make_match(sid="U6", conf=0.4475, strategy=MatchStrategy.ACTIVE_WITHIN_TYPE,
                pin_count=15):
    return MatchResult(
        confidence=conf,
        strategy=strategy,
        source_library_id=sid,
        target_library_id="ch347",
        extra_data={"hdl_pin_count": pin_count},
        warnings=[],
    )


class _FakeComp:
    def __init__(self, library_id, pins):
        self.library_id = library_id
        self.pins = [object() for _ in range(pins)]


class _FakeDB:
    def __init__(self, comps):
        self._comps = {c.library_id: c for c in comps}

    def get_by_library_id(self, library_id):
        return self._comps.get(library_id)


class TestManualMatchesConfig:
    def test_load(self, tmp_path):
        from cis2hdl.core.matcher.manual_matches import ManualMatchesConfig

        p = tmp_path / "manual_matches.yaml"
        p.write_text(
            "version: \"1.0\"\n"
            "matches:\n"
            "  - refdes: U6\n"
            "    library_id: dc_dc\n"
            "    section: 1\n"
            "  - refdes: U12\n"
            "    library_id: ldo\n"
            "    section: 2\n",
            encoding="utf-8",
        )
        cfg = ManualMatchesConfig.load(p)
        assert len(cfg.matches) == 2
        assert cfg.matches[0].refdes == "U6"
        assert cfg.matches[0].library_id == "dc_dc"
        assert cfg.matches[1].section == 2

    def test_load_missing_raises(self, tmp_path):
        from cis2hdl.core.matcher.manual_matches import ManualMatchesConfig

        with pytest.raises(FileNotFoundError):
            ManualMatchesConfig.load(tmp_path / "nope.yaml")


class TestApplyManualMatches:
    def test_override_applied(self):
        from cis2hdl.core.matcher.manual_matches import (
            ManualMatch,
            ManualMatchesConfig,
            apply_manual_matches,
        )

        results = [_make_match(sid="U6", pin_count=6)]
        db = _FakeDB([_FakeComp("dc_dc", 6)])
        manual = ManualMatchesConfig(matches=[
            ManualMatch(refdes="U6", library_id="dc_dc", section=1),
        ])
        results, warnings = apply_manual_matches(results, manual, db)
        assert not warnings
        assert results[0].strategy == MatchStrategy.MANUAL
        assert results[0].confidence == 1.0
        assert results[0].target_library_id == "dc_dc"
        assert results[0].extra_data["manual_section"] == 1

    def test_pin_count_mismatch_warns(self):
        from cis2hdl.core.matcher.manual_matches import (
            ManualMatch,
            ManualMatchesConfig,
            apply_manual_matches,
        )

        results = [_make_match(sid="U6", pin_count=15)]
        db = _FakeDB([_FakeComp("dc_dc", 6)])  # 6 ≠ 15
        manual = ManualMatchesConfig(matches=[
            ManualMatch(refdes="U6", library_id="dc_dc", section=1),
        ])
        results, warnings = apply_manual_matches(results, manual, db)
        assert any("pin count mismatch" in w for w in warnings)
        # 未注入 → 保留自动结果
        assert results[0].strategy == MatchStrategy.ACTIVE_WITHIN_TYPE

    def test_unknown_library_ignored(self):
        from cis2hdl.core.matcher.manual_matches import (
            ManualMatch,
            ManualMatchesConfig,
            apply_manual_matches,
        )

        results = [_make_match(sid="U6", pin_count=6)]
        db = _FakeDB([])  # no dc_dc
        manual = ManualMatchesConfig(matches=[
            ManualMatch(refdes="U6", library_id="dc_dc", section=1),
        ])
        results, warnings = apply_manual_matches(results, manual, db)
        assert any("unknown library_id" in w for w in warnings)

    def test_refdes_not_found_warns(self):
        from cis2hdl.core.matcher.manual_matches import (
            ManualMatch,
            ManualMatchesConfig,
            apply_manual_matches,
        )

        results = [_make_match(sid="U6")]
        db = _FakeDB([_FakeComp("dc_dc", 6)])
        manual = ManualMatchesConfig(matches=[
            ManualMatch(refdes="U99", library_id="dc_dc", section=1),
        ])
        results, warnings = apply_manual_matches(results, manual, db)
        assert any("not in match results" in w for w in warnings)

    def test_section_written_to_instances(self):
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.ir.design import DesignIR, PageIR
        from cis2hdl.core.matcher.manual_matches import (
            ManualMatch,
            ManualMatchesConfig,
            apply_manual_matches,
        )

        inst = ComponentInstanceIR(refdes="U6", library_id="U6", loc_x=1, loc_y=2)
        design = DesignIR(project_name="T", pages=[PageIR(page_id="1.1", instances=[inst])])
        results = [_make_match(sid="U6", pin_count=6)]
        db = _FakeDB([_FakeComp("dc_dc", 6)])
        manual = ManualMatchesConfig(matches=[
            ManualMatch(refdes="U6", library_id="dc_dc", section=3),
        ])
        apply_manual_matches(results, manual, db, design)
        assert inst.section == 3


class TestExportUnmatched:
    def test_export_lists_unmatched(self):
        from cis2hdl.core.matcher.manual_matches import export_unmatched

        results = [_make_match(sid="U6", conf=0.4475, pin_count=6)]
        data = export_unmatched(results, None, threshold=0.80)
        assert data["version"] == "1.0"
        assert len(data["unmatched"]) == 1
        entry = data["unmatched"][0]
        assert entry["refdes"] == "U6"
        assert entry["pin_count"] == 6
        assert "fill" in entry

    def test_export_with_power_candidates(self):
        from cis2hdl.core.matcher.manual_matches import export_unmatched
        from cis2hdl.core.matcher.power_ic_scorer import PowerCandidateScorer

        results = [_make_match(sid="U6", conf=0.4475, pin_count=6)]
        scorer = PowerCandidateScorer(Path("cis2hdl/config/power_ic.yaml"))
        data = export_unmatched(results, None, power_candidates=scorer)
        entry = data["unmatched"][0]
        assert entry["candidates"], "expected power candidates"
        top = entry["candidates"][0]
        assert top["library_id"] == "dc_dc"
        assert top["section"] == 1
        # 无引脚名/网名时 score = 引脚数权重 0.40；有特征时更高
        assert top["score"] >= 0.40
