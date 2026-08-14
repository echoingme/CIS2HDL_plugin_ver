"""Phase XVI T1 — EDIF orientation geometry（system_design0811-phase16.md D.3）。

Covers:
  * rotate_point 八方向映射表（EDIF 2.0.0：镜像在前、旋转在后）
  * MYR90/MXR90 复合顺序关键断言（修正前的注释顺序会得到相反结果）
  * rotate_bbox 镜像一致性
  * closest_rotation_for_mirror：竖直双引脚四类 orientation（精确）
  * 左右列 IC 数据集 → 确定性 θ*
  * 单引脚/空引脚退化 → 返回 rotation 部分
"""

from __future__ import annotations

import pytest

from cis2hdl.core.writer.coord_transform import (
    apply_edif_orientation,
    closest_rotation_for_mirror,
    rotate_bbox,
    rotate_point,
)


# ── rotate_point：8 方向映射表 ────────────────────────────────────────


class TestRotatePointEdifOrientation:
    @pytest.mark.parametrize("rotation,mirror,expected", [
        # (x, y) = (10, 20)
        (0, 0, (10, 20)),     # R0
        (90, 0, (-20, 10)),   # R90 CCW
        (180, 0, (-10, -20)),  # R180
        (270, 0, (20, -10)),  # R270 CCW
        (0, 1, (10, -20)),    # MX 上下翻转（y → -y）
        (0, 2, (-10, 20)),    # MY 左右翻转（x → -x）
        (90, 2, (-20, -10)),  # MYR90 = MY 后 R90（y=-x 反射）
        (90, 1, (20, 10)),    # MXR90 = MX 后 R90（y=x 反射）
    ])
    def test_eight_directions(self, rotation, mirror, expected):
        assert rotate_point(10, 20, rotation, mirror) == expected

    def test_myr90_matches_edif_standard(self):
        """MYR90 = (x,y) → (-x,y) → (-y,-x)：先 MY 再 R90。"""
        assert rotate_point(10, 20, 90, 2) == (-20, -10)
        assert rotate_point(3, 5, 90, 2) == (-5, -3)

    def test_mxr90_matches_edif_standard(self):
        """MXR90 = (x,y) → (x,-y) → (y,x)：先 MX 再 R90。"""
        assert rotate_point(10, 20, 90, 1) == (20, 10)
        assert rotate_point(3, 5, 90, 1) == (5, 3)

    def test_apply_edif_orientation_alias(self):
        """apply_edif_orientation == rotate_point（表驱动入口）。"""
        for rotation, mirror in ((0, 0), (90, 0), (180, 1), (270, 2), (90, 2)):
            assert apply_edif_orientation(10, 20, rotation, mirror) == (
                rotate_point(10, 20, rotation, mirror)
            )

    def test_rotation_zero_order_irrelevant(self):
        """rotation=0 时镜像顺序无关 → 旧测试兼容。"""
        assert rotate_point(10, 20, 0, 1) == (10, -20)
        assert rotate_point(10, 20, 0, 2) == (-10, 20)

    def test_vertical_passive_offsets(self):
        """电容 sym_1 竖直双引脚：镜像真值与设计表（A.3）一致。"""
        offs = [(0, -75), (0, 50)]
        assert rotate_point(0, -75, 0, 1) == (0, 75)
        assert rotate_point(0, 50, 0, 1) == (0, -50)
        # MYR90：先 MY（x→-x）再 R90 → (0,-75) → (75,0)、(0,50) → (-50,0)
        assert rotate_point(0, -75, 90, 2) == (75, 0)
        assert rotate_point(0, 50, 90, 2) == (-50, 0)
        # MXR90：先 MX（y→-y）再 R90 → (0,-75) → (-75,0)、(0,50) → (50,0)
        assert rotate_point(0, -75, 90, 1) == (-75, 0)
        assert rotate_point(0, 50, 90, 1) == (50, 0)


class TestRotateBboxMirror:
    def test_rotate_bbox_mirror_mx(self):
        """rotate_bbox 与 rotate_point 同源（镜像变换应用到 outline）。"""
        out = rotate_bbox("-50,0,50,-25", 0, 1)
        # (x1,y1)=(-50,0)→(-50,0), (x2,y2)=(50,-25)→(50,25)  [flip Y]
        assert out == "-50,0,50,25"

    def test_rotate_bbox_pure_rotation_unchanged(self):
        assert rotate_bbox("-50,0,50,-25", 90) == "0,-50,25,50"


# ── closest_rotation_for_mirror ────────────────────────────────────────


class TestClosestRotationForMirror:
    @pytest.mark.parametrize("rotation,mirror,expected", [
        (0, 1, 180),   # MX → R180（精确）
        (0, 2, 0),     # MY → R0（精确）
        (90, 2, 90),   # MYR90 → R90（精确）
        (90, 1, 270),  # MXR90 → R270（精确）
    ])
    def test_vertical_passive_exact(self, rotation, mirror, expected):
        """竖直双引脚无源件：镜像与纯旋转精确等价。"""
        offs = [(0, -75), (0, 50)]
        theta = closest_rotation_for_mirror(offs, rotation, mirror)
        assert theta == expected
        # exact：M(p) == Rθ(p) 对全部引脚成立
        for px, py in offs:
            assert rotate_point(px, py, rotation, mirror) == (
                rotate_point(px, py, theta)
            )

    def test_horizontal_dual_pin(self):
        """横向双引脚（sym_2 视图）：MX → R0 / MY → R180。"""
        offs = [(-75, 0), (75, 0)]
        assert closest_rotation_for_mirror(offs, 0, 1) == 0    # MX flip Y 不变
        assert closest_rotation_for_mirror(offs, 0, 2) == 180  # MY flip X = R180

    def test_left_right_ic_deterministic(self):
        """左右列 IC 引脚 (±dx, y) 对称分布：θ* 确定性。"""
        offs = [(-150, 150), (-150, 50), (150, -150), (150, -50)]
        for rotation, mirror in ((0, 1), (0, 2), (90, 2), (90, 1)):
            theta = closest_rotation_for_mirror(offs, rotation, mirror)
            assert theta in (0, 90, 180, 270)
        # 同输入同输出（确定性）
        a = closest_rotation_for_mirror(offs, 90, 2)
        b = closest_rotation_for_mirror(list(offs), 90, 2)
        assert a == b

    def test_single_pin_degenerate(self):
        """单引脚 → 返回 rotation 部分（不尝试拟合）。"""
        assert closest_rotation_for_mirror([(0, -75)], 90, 2) == 90
        assert closest_rotation_for_mirror([(0, -75)], 0, 1) == 0

    def test_empty_offsets_degenerate(self):
        assert closest_rotation_for_mirror([], 180, 1) == 180
