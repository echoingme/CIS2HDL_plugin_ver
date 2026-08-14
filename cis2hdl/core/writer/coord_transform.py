"""CoordTransform — unified CIS/CrossRef/EDIF coordinate → DEHDL C-paper mapping.

Phase XI P0-B (system_design.md B.3): the EDIF ``(pt x y)``, the Capture
CrossRef CSV coordinates and the Cadence DEHDL CSA coordinates use mutually
different origins/units.  The correct strategy is **self-consistency**, not
faithful reconstruction:

1. instance body coordinates are produced by a single affine transform that
   adapts the source bounding box into the C SIZE PAGE usable area — applied
   uniformly to every instance on the page (preserves relative placement);
2. pin coordinates = body coordinates + ``symbol.css`` ``C``-command offset
   (SymbolCssPinParser);
3. wire endpoints = pin coordinates (topology synthesis), guaranteeing
   WIRE and LASTPIN geometric coincidence — Cadence's only connection rule.

This class wraps the previous ``CSAWriter._map_coords_to_dehdl`` heuristic so
the csa/csv/cpc writers share one coordinate source (shared-knowledge rule:
"coordinate single source of truth").
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from ..config import config as cfg

logger = logging.getLogger(__name__)


@dataclass
class CoordTransform:
    """Maps page instance coordinates into the DEHDL C SIZE PAGE area.

    The transform is a uniform scale + centering + Y-flip computed from the
    source bounding box, so every instance on a page gets the **same**
    transform (no per-instance independent scaling).

    Attributes:
        page_x0/page_x1/page_y0/page_y1: C-page usable area (config).
        scale_factor: extra shrink applied after fit (config, default 0.7).
    """

    page_x0: int = -10200
    page_x1: int = -550
    page_y0: int = 400
    page_y1: int = 7200
    scale_factor: float = 0.7

    def __post_init__(self) -> None:
        self.page_cx: float = (self.page_x0 + self.page_x1) / 2.0
        self.page_cy: float = (self.page_y0 + self.page_y1) / 2.0
        self.page_w: int = self.page_x1 - self.page_x0
        self.page_h: int = self.page_y1 - self.page_y0

    @classmethod
    def from_config(cls) -> "CoordTransform":
        """Build a CoordTransform from the global PageConfig."""
        p = cfg.page
        return cls(
            page_x0=p.c_page_x0,
            page_x1=p.c_page_x1,
            page_y0=p.c_page_y0,
            page_y1=p.c_page_y1,
            scale_factor=p.c_page_scale,
        )

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    @staticmethod
    def _snap25(value: float) -> int:
        """Snap a DEHDL coordinate to the 25-unit grid.

        Cadence 16.6 moves off-grid wires with ``SPCOCN-1329`` warnings and
        renders components at the nearest grid point, breaking the
        LASTPIN/WIRE coincidence rule.  Snapping the body coordinate (the
        single source for both LASTPIN and WIRE endpoints) keeps every
        generated coordinate on-grid while preserving exact coincidence.
        """
        return int(round(float(value) / 25.0)) * 25

    def map_page(self, instances: Iterable) -> dict[str, tuple[int, int]]:
        """Map every instance on a page to C-paper coordinates.

        Instances at (0,0) are treated as having no valid source coordinates
        and are excluded from the bounding box and the output mapping.

        Args:
            instances: Iterable of objects with ``refdes`` / ``loc_x`` /
                ``loc_y`` attributes.

        Returns:
            Dict ``refdes -> (dehdl_x, dehdl_y)`` for valid instances only.
        """
        positions: list[tuple[str, float, float]] = []
        for inst in instances:
            x = float(getattr(inst, "loc_x", 0) or 0)
            y = float(getattr(inst, "loc_y", 0) or 0)
            if x == 0 and y == 0:
                continue
            positions.append((inst.refdes, x, y))
        if not positions:
            return {}

        xs = [p[1] for p in positions]
        ys = [p[2] for p in positions]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        src_w = max(max_x - min_x, 1.0)
        src_h = max(max_y - min_y, 1.0)
        src_cx = (min_x + max_x) / 2.0
        src_cy = (min_y + max_y) / 2.0

        scale = min(self.page_w / src_w, self.page_h / src_h) * self.scale_factor

        result: dict[str, tuple[int, int]] = {}
        for refdes, sx, sy in positions:
            dx = sx - src_cx
            dy = sy - src_cy
            # Phase XIII T1: snap to the DEHDL 25-unit grid so body
            # coordinates (and therefore LASTPIN/WIRE endpoints derived
            # from them) are on-grid — eliminates SPCOCN-1329.
            dehdl_x = self._snap25(self.page_cx + dx * scale)
            # Y-axis inversion: source Y-down → DEHDL Y-up
            dehdl_y = self._snap25(self.page_cy - dy * scale)
            result[refdes] = (dehdl_x, dehdl_y)

        logger.debug(
            "CoordTransform: %d instances → C SIZE PAGE, scale=%.4f",
            len(result), scale,
        )
        return result

    def map_point(self, x: float, y: float, src_bbox: tuple[float, float, float, float]) -> tuple[int, int]:
        """Map a single point using an externally computed source bbox.

        Useful for mapping wire polylines with the same affine transform
        that was used for the instances (self-consistency).

        Args:
            x/y: Source point coordinates.
            src_bbox: (min_x, min_y, max_x, max_y) of the source layout.

        Returns:
            Mapped (dehdl_x, dehdl_y).
        """
        min_x, min_y, max_x, max_y = src_bbox
        src_w = max(max_x - min_x, 1.0)
        src_h = max(max_y - min_y, 1.0)
        src_cx = (min_x + max_x) / 2.0
        src_cy = (min_y + max_y) / 2.0
        scale = min(self.page_w / src_w, self.page_h / src_h) * self.scale_factor
        dx = x - src_cx
        dy = y - src_cy
        return (
            self._snap25(self.page_cx + dx * scale),
            self._snap25(self.page_cy - dy * scale),
        )

    @staticmethod
    def source_bbox(instances: Iterable) -> tuple[float, float, float, float]:
        """Compute the source bounding box of valid instances.

        Returns:
            (min_x, min_y, max_x, max_y); (0,0,0,0) when no valid coords.
        """
        xs: list[float] = []
        ys: list[float] = []
        for inst in instances:
            x = float(getattr(inst, "loc_x", 0) or 0)
            y = float(getattr(inst, "loc_y", 0) or 0)
            if x == 0 and y == 0:
                continue
            xs.append(x)
            ys.append(y)
        if not xs:
            return (0.0, 0.0, 0.0, 0.0)
        return (min(xs), min(ys), max(xs), max(ys))

    # ------------------------------------------------------------------
    #  Grid fallback (instances without valid coordinates)
    # ------------------------------------------------------------------

    @staticmethod
    def grid_position(index: int) -> tuple[int, int]:
        """Auto-layout grid position for an instance without coordinates.

        Args:
            index: Zero-based instance index within the page.

        Returns:
            (x, y) on the C-paper grid.
        """
        # Phase XIII T1: grid fallback is already on the 25-unit grid —
        # page_start/step are all multiples of 25 (verified).
        start_x: int = cfg.page.c_page_start_x
        start_y: int = cfg.page.c_page_start_y
        step_x: int = cfg.page.c_page_step_x
        step_y: int = cfg.page.c_page_step_y
        cols: int = cfg.page.c_page_cols
        col = index % cols
        row = index // cols
        return (start_x + col * step_x, start_y - row * step_y)

    @staticmethod
    def power_symbol_position(k: int) -> tuple[int, int]:
        """Fallback placement for power symbols without usable coordinates.

        Phase XI P0-遗留#2 (2026-08-10): power symbols with no valid source
        placement go to the page's top-right edge region (``(-600, 7200)``
        in DEHDL C-paper space), decrementing with the page-local k so
        multiple symbols per page never overlap the component grid.

        Args:
            k: Page-local instance index (1-based).

        Returns:
            (x, y) in DEHDL C-paper coordinates.
        """
        # Phase XIII T1: already on the 25-unit grid — offsets -600 and
        # 150 (and the 7200 top edge) are multiples of 25 (verified).
        step: int = 150
        return (-600 - (k - 1) * step, 7200 - (k - 1) * step)

    @classmethod
    def map_page_instances(cls, instances: Iterable) -> dict[str, tuple[int, int]]:
        """Map every page instance (regular + power symbols) to C-paper.

        Regular components are fit into the page usable area as one group.
        Power symbols (``is_power_symbol=True``) are excluded from that
        group bounding box — their EDIF ``portImplementation`` origins live
        in a different coordinate space and would skew the affine fit — and
        are mapped individually through the same transform, falling back to
        the corner region when the origin is missing or out of bounds.

        Args:
            instances: Iterable of connectivity-model InstanceRecord objects
                (refdes / loc_x / loc_y / is_power_symbol / page_local_k).

        Returns:
            Dict ``refdes -> (dehdl_x, dehdl_y)`` covering every instance.
        """
        regular = [
            i for i in instances
            if not getattr(i, "is_power_symbol", False)
            and (getattr(i, "loc_x", 0) or getattr(i, "loc_y", 0))
        ]
        transform = CoordTransform.from_config()
        mapped = transform.map_page(regular)
        bbox = CoordTransform.source_bbox(regular)
        result: dict[str, tuple[int, int]] = dict(mapped)
        for i in instances:
            if i.refdes in result:
                continue
            if getattr(i, "is_power_symbol", False):
                loc_x = int(getattr(i, "loc_x", 0) or 0)
                loc_y = int(getattr(i, "loc_y", 0) or 0)
                if (loc_x or loc_y) and bbox and bbox != (0.0, 0.0, 0.0, 0.0):
                    pt = transform.map_point(loc_x, loc_y, bbox)
                    if (transform.page_x0 <= pt[0] <= transform.page_x1
                            and transform.page_y0 <= pt[1] <= transform.page_y1):
                        result[i.refdes] = pt
                        continue
                result[i.refdes] = CoordTransform.power_symbol_position(
                    int(getattr(i, "page_local_k", 1) or 1)
                )
            else:
                result[i.refdes] = CoordTransform.grid_position(
                    (int(getattr(i, "page_local_k", 1) or 1)) - 1
                )
        return result


# ---------------------------------------------------------------------------
# P2-1: per-instance rotation / mirror of symbol.css pin offsets.
#
# DEHDL renders a component using the sym_N view chosen by the source
# design's orientation.  EDIF orientation (R90/R180/R270, MY/MX mirrors)
# is captured on ComponentInstanceIR.rotation / .mirror (P1-4).  Rather
# than switching sym_N (which is ambiguous — dc_dc sym_N are device
# variants, capacitor sym_1/sym_2 are rotation views), we rotate the pin
# offsets geometrically around the body origin, matching how DEHDL places
# pins after a rotation.  Mirror axes: mirror=1 → X-axis (flip Y),
# mirror=2 → Y-axis (flip X).
# ---------------------------------------------------------------------------


def rotate_point(
    x: float, y: float, rotation: int = 0, mirror: int = 0
) -> tuple[int, int]:
    """Rotate (and optionally mirror) a pin offset around the body origin.

    Phase XVI (system_design0811-phase16.md A.2): EDIF 2.0.0 composes the
    eight orientations as **mirror first, rotation second** (``MYR90`` =
    ``MY`` followed by R90 → reflection about y=-x).  The previous comment
    claimed the opposite order but no writer path ever passed ``mirror``
    with a nonzero ``rotation`` (csa_writer only forwarded the DEHDL
    rotation angle), so the fix has no legacy output impact.

    Args:
        x, y: symbol.css pin offset relative to body origin.
        rotation: 0 / 90 / 180 / 270 degrees (counter-clockwise, EDIF).
        mirror: 0 = none, 1 = flip about X axis (Y → -Y, EDIF ``MX``),
            2 = flip about Y axis (X → -X, EDIF ``MY``).

    Returns:
        Transformed (x, y) offset.
    """
    rx, ry = float(x), float(y)
    # EDIF 2.0.0: mirror is applied BEFORE the rotation.
    if mirror == 1:      # MX：先镜像（flip Y）
        ry = -ry
    elif mirror == 2:    # MY：先镜像（flip X）
        rx = -rx
    rot = int(rotation or 0) % 360
    if rot == 90:
        rx, ry = -ry, rx
    elif rot == 180:
        rx, ry = -rx, -ry
    elif rot == 270:
        rx, ry = ry, -rx
    return int(round(rx)), int(round(ry))


def apply_edif_orientation(
    x: float, y: float, rotation: int = 0, mirror: int = 0
) -> tuple[int, int]:
    """Table-driven alias for ``rotate_point`` (EDIF orientation semantics).

    Phase XVI (system_design0811-phase16.md A.2): the writer's single entry
    point for EDIF orientation — mirror first, rotation second, exactly as
    ``rotate_point`` implements.  Kept as a distinct name so callers express
    intent (an EDIF orientation) instead of a bare geometric rotation.

    Args:
        x, y: pin offset relative to body origin.
        rotation: EDIF rotation angle (0/90/180/270).
        mirror: 0 = none, 1 = MX, 2 = MY.

    Returns:
        Transformed (x, y) offset (rounded to ints).
    """
    return rotate_point(x, y, rotation, mirror)


def closest_rotation_for_mirror(
    pin_offsets: list[tuple[int, int]],
    rotation: int,
    mirror: int,
) -> int:
    """Pick the EDIF rotation whose pins best approximate the mirror truth.

    Phase XVI (system_design0811-phase16.md A.3): DEHDL ``R n`` lines can
    only rotate (0/90/180/270), never mirror.  For a mirror instance we
    choose the rotation ``θ*`` minimizing the total squared displacement
    between the exact EDIF mirror transform ``M(p)`` and each pure-rotation
    candidate ``Rθ(p)`` over all css pin offsets.

    The returned angle is in **EDIF angle space**; callers must map it to
    the DEHDL ``R``-line convention via ``csa_writer._dehdl_rotation``
    (Phase XV P0-E: DEHDL renders 90↔270 swapped).

    Args:
        pin_offsets: symbol.css pin offsets of the instance (relative to
            body origin); >= 2 pins required for a meaningful fit.
        rotation: EDIF rotation (0/90/180/270).
        mirror: 1 = MX, 2 = MY (nonzero mirror required).

    Returns:
        ``θ*`` in ``{0, 90, 180, 270}``; for degenerate (single-pin /
        empty) instances returns the rotation-only component unchanged.
    """
    if not pin_offsets or len(pin_offsets) < 2:
        return int(rotation or 0)
    best_t: int = 0
    best_err: float | None = None
    for theta in (0, 90, 180, 270):
        err = 0
        for px, py in pin_offsets:
            mx, my = rotate_point(px, py, rotation, mirror)
            rx, ry = rotate_point(px, py, theta)
            err += (mx - rx) ** 2 + (my - ry) ** 2
        if best_err is None or err < best_err:
            best_t, best_err = theta, err
    return best_t


def rotate_bbox(
    outline: str, rotation: int = 0, mirror: int = 0
) -> str:
    """Rotate a ``"x1,y1,x2,y2"`` CDS_LMAN_SYM_OUTLINE value.

    The outline is transformed by the same affine map as pin offsets so
    body-avoidance and CSV size attributes stay consistent with the pins.
    """
    try:
        x1, y1, x2, y2 = (float(v) for v in outline.split(","))
    except ValueError:
        return outline
    p1 = rotate_point(x1, y1, rotation, mirror)
    p2 = rotate_point(x2, y2, rotation, mirror)
    return f"{p1[0]},{p1[1]},{p2[0]},{p2[1]}"
