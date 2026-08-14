"""Phase XXIII P1-4 — 被动元件符号方向随连线（orientation_planner）。

Covers:
  * `passive_axis`：水平 / 垂直 / 45°（方形）判定
  * `rotation_for_axis`：水平 0/180、垂直 90/270，同轴类保持现状
  * `swap_outline`：outline 尺寸 swap（200×100 ↔ 100×200，中心不动）
  * `apply_passive_orientation`：R/L/FB/FERRI/BEAD 判定 + 尺寸 swap +
    45° / 非被动零回归
  * `rotate_pin_coords`：coord_transform 旋转链复用（引脚偏移随旋转）
"""

from __future__ import annotations

from cis2hdl.core.writer.orientation_planner import (
    apply_passive_orientation,
    is_passive_refdes,
    passive_axis,
    rotate_pin_coords,
    rotation_for_axis,
    swap_outline,
)

#: 典型水平 mock R 符号 outline（200×100）。
_H_OUTLINE = "-100,50,100,-50"
#: 对应垂直 outline（100×200）。
_V_OUTLINE = "-50,100,50,-100"


class TestPassiveAxis:
    def test_horizontal(self):
        assert passive_axis([(0, 0), (200, 10)]) == "horizontal"

    def test_vertical(self):
        assert passive_axis([(0, 0), (10, 200)]) == "vertical"

    def test_45_degree_square(self):
        assert passive_axis([(0, 0), (100, 100)]) == "square"

    def test_near_45_square(self):
        """Δx 与 Δy 差 ≤25 视为方形（不判定）。"""
        assert passive_axis([(0, 0), (100, 80)]) == "square"

    def test_single_pin_square(self):
        assert passive_axis([(0, 0)]) == "square"


class TestRotationForAxis:
    def test_horizontal_keeps_180(self):
        assert rotation_for_axis("horizontal", 180) == 180

    def test_horizontal_keeps_0(self):
        assert rotation_for_axis("horizontal", 0) == 0

    def test_horizontal_from_vertical(self):
        """当前 90（垂直）但连线水平 → 0。"""
        assert rotation_for_axis("horizontal", 90) == 0

    def test_vertical_keeps_90(self):
        assert rotation_for_axis("vertical", 90) == 90

    def test_vertical_keeps_270(self):
        assert rotation_for_axis("vertical", 270) == 270

    def test_vertical_from_horizontal(self):
        """当前 0（水平）但连线垂直 → 90。"""
        assert rotation_for_axis("vertical", 0) == 90


class TestSwapOutline:
    def test_swap_dimensions(self):
        """200×100 → 100×200（中心不动）。"""
        assert swap_outline(_H_OUTLINE) == _V_OUTLINE

    def test_swap_back(self):
        assert swap_outline(_V_OUTLINE) == _H_OUTLINE

    def test_square_noop(self):
        assert swap_outline("-150,150,150,-150") == "-150,150,150,-150"

    def test_invalid_unchanged(self):
        assert swap_outline("garbage") == "garbage"


class TestApplyPassiveOrientation:
    def test_non_passive_unchanged(self):
        """非被动前缀（U1）→ 原样返回。"""
        assert apply_passive_orientation(
            "U1", [(0, 0), (0, 200)], _H_OUTLINE, 0,
        ) == (0, _H_OUTLINE)

    def test_horizontal_resistor(self):
        """Δx>Δy（水平连线）→ rotation 0，outline 不 swap。"""
        rot, outline = apply_passive_orientation(
            "R12", [(0, 0), (200, 0)], _H_OUTLINE, 90,
        )
        assert rot == 0
        assert outline == _H_OUTLINE

    def test_vertical_resistor(self):
        """Δy>Δx（垂直连线）→ rotation 90，outline swap。"""
        rot, outline = apply_passive_orientation(
            "R12", [(0, 0), (0, 200)], _H_OUTLINE, 0,
        )
        assert rot == 90
        assert outline == _V_OUTLINE

    def test_vertical_keeps_270(self):
        """已在垂直类（270）→ 保持 270（outline swap 结果相同）。"""
        rot, outline = apply_passive_orientation(
            "R12", [(0, 0), (0, 200)], _H_OUTLINE, 270,
        )
        assert rot == 270
        assert outline == _V_OUTLINE

    def test_inductor_and_bead_and_ferrite(self):
        """L / FB / FERRI 同规则。"""
        for refdes in ("L20", "FB3", "FERRI1", "BEAD2"):
            rot, outline = apply_passive_orientation(
                refdes, [(0, 0), (0, 200)], _H_OUTLINE, 0,
            )
            assert rot == 90, refdes
            assert outline == _V_OUTLINE, refdes

    def test_45_degree_unchanged(self):
        """45° / 方形 → 保持现状（零回归）。"""
        assert apply_passive_orientation(
            "R1", [(0, 0), (100, 100)], _H_OUTLINE, 0,
        ) == (0, _H_OUTLINE)

    def test_single_pin_unchanged(self):
        assert apply_passive_orientation(
            "R1", [(0, 0)], _H_OUTLINE, 0,
        ) == (0, _H_OUTLINE)

    def test_rotation_normalized(self):
        """非法角度归一（360 → 0）。"""
        rot, _o = apply_passive_orientation(
            "R1", [(0, 0), (200, 0)], _H_OUTLINE, 360,
        )
        assert rot == 0


class TestRotatePinCoords:
    def test_rotate_90_reuses_rotation_chain(self):
        """两引脚偏移经 rotate_point(90) 旋转后绝对坐标正确。"""
        body = (-3000, 5000)
        offsets = [(-100, 0), (100, 0)]  # 水平两引脚
        coords = rotate_pin_coords([], body, offsets, 90)
        # rotate_point((-100,0), 90) = (0, -100) → (-3000, 4900)
        # rotate_point((100,0), 90) = (0, 100) → (-3000, 5100)
        assert coords == [(-3000, 4900), (-3000, 5100)]

    def test_grid_preserved(self):
        body = (-3000, 5000)
        offsets = [(-150, 0), (150, 0)]
        coords = rotate_pin_coords([], body, offsets, 90)
        for c in coords:
            assert c[0] % 25 == 0 and c[1] % 25 == 0


class TestIsPassiveRefdes:
    def test_prefixes(self):
        for refdes in ("R12", "L20", "FB3", "FERRI1", "BEAD2"):
            assert is_passive_refdes(refdes), refdes

    def test_non_passive(self):
        for refdes in ("U6", "C10", "J4", "TP1"):
            assert not is_passive_refdes(refdes), refdes
