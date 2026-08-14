"""Phase XIV T5 — D2 元件重叠检测（overlap_detector.py）。

Covers:
  * 两两相交检测 + 面积过滤
  * kind 分类（placeholder / grid / user）
  * AestheticReport 收集与写出
"""

from __future__ import annotations

from pathlib import Path


class _Irec:
    def __init__(self, refdes, pins=0, loc_x=100, loc_y=100,
                 outline="", power=False, cell_name=""):
        self.refdes = refdes
        self.pins = [object() for _ in range(pins)]
        self.loc_x = loc_x
        self.loc_y = loc_y
        self.properties = {"CDS_LMAN_SYM_OUTLINE": outline} if outline else {}
        self.is_power_symbol = power
        self.cell_name = cell_name


class _Page:
    def __init__(self, instances, page_num=12):
        self.instances = instances
        self.page_num = page_num


class TestOverlapDetector:
    def test_detect_overlap_pair(self):
        from cis2hdl.core.writer.overlap_detector import OverlapDetector

        page = _Page([_Irec("U1", pins=2, loc_x=0, loc_y=0),
                      _Irec("U2", pins=2, loc_x=0, loc_y=0)])
        # 两个实例同坐标 → body 轮廓 (-150,150,150,-150) 完全重叠
        body_coords = {"U1": (0, 0), "U2": (0, 0)}
        overlaps = OverlapDetector(min_area=1).detect(page, body_coords)
        assert len(overlaps) == 1
        assert overlaps[0].area > 0

    def test_area_filter(self):
        from cis2hdl.core.writer.overlap_detector import OverlapDetector

        page = _Page([_Irec("U1", pins=2, loc_x=0, loc_y=0),
                      _Irec("U2", pins=2, loc_x=0, loc_y=0)])
        body_coords = {"U1": (0, 0), "U2": (0, 0)}
        # min_area 巨大 → 过滤
        assert OverlapDetector(min_area=10 ** 9).detect(page, body_coords) == []

    def test_no_overlap(self):
        from cis2hdl.core.writer.overlap_detector import OverlapDetector

        page = _Page([_Irec("U1", pins=2, loc_x=0, loc_y=0),
                      _Irec("U2", pins=2, loc_x=5000, loc_y=5000)])
        body_coords = {"U1": (0, 0), "U2": (5000, 5000)}
        assert OverlapDetector().detect(page, body_coords) == []

    def test_kind_placeholder(self):
        from cis2hdl.core.writer.overlap_detector import OverlapDetector

        # 无 outline 且多引脚 → placeholder 分类
        page = _Page([_Irec("U6", pins=15, loc_x=0, loc_y=0),
                      _Irec("U7", pins=2, loc_x=0, loc_y=0)])
        body_coords = {"U6": (0, 0), "U7": (0, 0)}
        overlaps = OverlapDetector(min_area=1).detect(page, body_coords)
        assert overlaps
        assert overlaps[0].kind in ("placeholder", "user")

    def test_explicit_outlines(self):
        from cis2hdl.core.writer.overlap_detector import OverlapDetector

        page = _Page([])
        outlines = {
            "A": (0, 0, 100, 100),
            "B": (50, 50, 150, 150),
            "C": (500, 500, 600, 600),
        }
        overlaps = OverlapDetector(min_area=1).detect(page, {}, outlines)
        assert len(overlaps) == 1
        assert overlaps[0].refdes_a == "A"
        assert overlaps[0].refdes_b == "B"


class TestAestheticReport:
    def test_write_report(self, tmp_path):
        from cis2hdl.core.writer.aesthetic_report import AestheticReport, Overlap

        report = AestheticReport(project_name="HG5015", enabled=True)
        report.add_overlap(Overlap(
            page=12, refdes_a="U6G", refdes_b="U6F",
            bbox_a=(-8952, 5261, -8552, 5561),
            bbox_b=(-8537, 6030, -8137, 6330),
            overlap_rect=(-8537, 5411, -8552, 5561),
            area=2250, kind="placeholder",
        ))
        report.add_text_stats(37, 3, [("U12.VALUE", "U13.LOCATION")])
        report.add_align_stats(0.923, 1.0, 2, 2)
        report.add_grid_stats(0, 0)

        path = report.write(tmp_path)
        assert path is not None and path.exists()
        text = path.read_text(encoding="utf-8")
        assert "[OVERLAP]" in text
        assert "U6G" in text
        assert "[TEXT]" in text
        assert "collisions_before=37" in text
        assert "[ALIGN]" in text
        assert "[GRID]" in text

    def test_write_disabled(self, tmp_path):
        from cis2hdl.core.writer.aesthetic_report import AestheticReport

        report = AestheticReport(enabled=False)
        assert report.write(tmp_path) is None
