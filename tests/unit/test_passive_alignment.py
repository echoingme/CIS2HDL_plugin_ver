"""Phase XVIII R11 — 元件对齐/腾挪（被动元件微调 ≤50）。

Covers:
  * `OverlapResolver.resolve_passives`：被动元件重叠微调
  * 位移 ≤ max_move（50，Q12 用户决策）
  * 固定件（芯片）不移动
"""

from __future__ import annotations


class TestResolvePassives:
    def test_overlapping_resistors_resolved(self):
        """I18/I15 重叠 → I15 微调（≤50）消除重叠。"""
        from cis2hdl.core.writer.overlap_resolver import OverlapResolver

        r = OverlapResolver(max_iter=4, grid=25)
        result = r.resolve_passives(
            {"I18": (0, 0, 100, 50), "I15": (80, 0, 180, 50)},
            max_move=50,
        )
        assert "I15" in result.displacements
        dx = result.displacements["I15"][0]
        assert 0 < dx <= 50, f"I15 位移 {dx} 应 >0 且 <=50"

    def test_chip_fixed_not_moved(self):
        """芯片（固定件）位移恒为 0。"""
        from cis2hdl.core.writer.overlap_resolver import OverlapResolver

        r = OverlapResolver(max_iter=4, grid=25)
        result = r.resolve_passives(
            {"C1": (0, 0, 100, 50), "R1": (80, 0, 180, 50)},
            fixed=[(200, 200, 400, 400)],
            max_move=50,
        )
        # 固定件不参与 displacements（只有被动件记录位移）
        assert not any(k.startswith("__fixed") for k in result.displacements)

    def test_non_overlapping_no_move(self):
        """无重叠 → 无位移。"""
        from cis2hdl.core.writer.overlap_resolver import OverlapResolver

        r = OverlapResolver(max_iter=4, grid=25)
        result = r.resolve_passives(
            {"C1": (0, 0, 100, 50), "R1": (300, 0, 400, 50)},
            max_move=50,
        )
        assert result.displacements == {}

    def test_max_move_respected(self):
        """位移超限的元件不移动（或移动被限制）。"""
        from cis2hdl.core.writer.overlap_resolver import OverlapResolver

        r = OverlapResolver(max_iter=4, grid=25)
        # 大幅重叠（重叠 100 + margin 25 → 位移 125 > 50 超限）
        result = r.resolve_passives(
            {"C1": (0, 0, 100, 50), "R1": (0, 0, 100, 50)},
            max_move=50,
        )
        for _k, v in result.displacements.items():
            assert abs(v[0]) <= 50 and abs(v[1]) <= 50

    def test_grid_25(self):
        """位移 snap 25 网格。"""
        from cis2hdl.core.writer.overlap_resolver import OverlapResolver

        r = OverlapResolver(max_iter=4, grid=25)
        result = r.resolve_passives(
            {"I18": (0, 0, 100, 50), "I15": (80, 0, 180, 50)},
            max_move=50,
        )
        for v in result.displacements.values():
            assert v[0] % 25 == 0 and v[1] % 25 == 0
