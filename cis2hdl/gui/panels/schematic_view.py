"""Schematic Preview Panel — zoomable/panable schematic rendering via QGraphicsView.

Renders DSN PageIR instances and wires using the Anthropic color token system.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QVBoxLayout,
    QWidget,
)

from ..colors import Colors

# ── Schematic Scene Constants ────────────────────────────────────────────────

INSTANCE_W = 120
INSTANCE_H = 80
INSTANCE_CORNER_RADIUS = 4
FONT_SIZE = 10
WIRE_PEN_WIDTH = 2
GRID_SIZE = 40
MIN_ZOOM = 0.1
MAX_ZOOM = 5.0
ZOOM_FACTOR = 1.15


class SchematicPreviewPanel(QWidget):
    """Zoomable, panable schematic preview using QGraphicsView + QGraphicsScene.

    Renders PageIR data:
      - Component instances as rounded rectangles with refdes labels
      - Wires as line segments
      - Grid background

    Supports:
      - Mouse wheel zoom (centered on cursor)
      - Middle-button drag pan
      - Scroll bar pan
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the schematic preview panel with graphics view and scene.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setObjectName("schematic_preview")

        # ── Layout ────────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Scene ─────────────────────────────────────────────────────
        self._scene = QGraphicsScene(self)
        self._scene.setBackgroundBrush(QBrush(QColor(Colors.BG_BASE)))

        # ── View ──────────────────────────────────────────────────────
        self._view = _SchematicView(self._scene, self)
        self._view.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._view.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self._view.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setStyleSheet(
            f"QGraphicsView {{"
            f"  border: none;"
            f"  background-color: {Colors.BG_BASE};"
            f"}}"
        )

        layout.addWidget(self._view)

        # ── Internal state ────────────────────────────────────────────
        self._current_page_id: str = ""
        self._zoom_level: float = 1.0

    # ── Public API ────────────────────────────────────────────────────────

    def load_page(self, page_ir) -> None:
        """Load and render a single PageIR into the schematic view.

        Clears any existing scene content before rendering.

        Args:
            page_ir: A PageIR object with instances, wires, and metadata.
        """
        self.clear()
        if page_ir is None:
            return

        self._current_page_id = getattr(page_ir, "page_id", "")

        # Set scene rect based on page dimensions
        page_w: int = getattr(page_ir, "width", 3520)
        page_h: int = getattr(page_ir, "height", 2720)
        self._scene.setSceneRect(QRectF(0, 0, float(page_w), float(page_h)))

        # Draw grid
        self._draw_grid(page_w, page_h)

        # Draw instances
        instances: list = getattr(page_ir, "instances", [])
        for inst in instances:
            self._draw_instance(inst)

        # Draw wires
        wires: list = getattr(page_ir, "wires", [])
        for wire in wires:
            self._draw_wire(wire)

        # Fit view
        self._view.fitInView(
            self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
        )
        self._zoom_level = 1.0

    def load_pages(self, pages: list) -> None:
        """Load and render a list of PageIR objects.

        Renders all pages into a single scene, stacked vertically with
        a separator between pages.

        Args:
            pages: List of PageIR objects.
        """
        self.clear()
        if not pages:
            return

        total_height: int = 0
        separator_gap: int = 200

        # Calculate total height
        for page in pages:
            page_h: int = getattr(page, "height", 2720)
            total_height += page_h + separator_gap
        total_height -= separator_gap  # Remove trailing gap
        max_width: int = max(
            (getattr(p, "width", 3520) for p in pages),
            default=3520,
        )

        self._scene.setSceneRect(
            QRectF(0, 0, float(max_width), float(total_height))
        )

        y_offset: int = 0
        for page in pages:
            page_w: int = getattr(page, "width", 3520)
            page_h: int = getattr(page, "height", 2720)

            # Draw grid for this page region
            self._draw_grid_region(page_w, page_h, 0, y_offset)

            # Draw instances (adjusted for y_offset)
            instances: list = getattr(page, "instances", [])
            for inst in instances:
                self._draw_instance(inst, y_offset)

            # Draw wires (adjusted for y_offset)
            wires: list = getattr(page, "wires", [])
            for wire in wires:
                self._draw_wire(wire, y_offset)

            y_offset += page_h + separator_gap

        self._view.fitInView(
            self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
        )
        self._zoom_level = 1.0

    def clear(self) -> None:
        """Remove all items from the scene."""
        self._scene.clear()
        self._current_page_id = ""

    @property
    def current_page_id(self) -> str:
        """Return the ID of the currently loaded page."""
        return self._current_page_id

    # ── Drawing helpers ───────────────────────────────────────────────────

    def _draw_grid(self, page_w: int, page_h: int) -> None:
        """Draw a dot-grid background over the entire page area.

        Args:
            page_w: Page width in DSN units.
            page_h: Page height in DSN units.
        """
        self._draw_grid_region(page_w, page_h, 0, 0)

    def _draw_grid_region(
        self, page_w: int, page_h: int, offset_x: int, offset_y: int
    ) -> None:
        """Draw a dot-grid background over a region.

        Args:
            page_w: Region width.
            page_h: Region height.
            offset_x: X offset for the region.
            offset_y: Y offset for the region.
        """
        grid_pen = QPen(QColor(Colors.BORDER_SUBTLE))
        grid_pen.setWidth(0)
        grid_pen.setStyle(Qt.PenStyle.DotLine)

        # Horizontal grid lines
        y: int = (offset_y // GRID_SIZE) * GRID_SIZE
        while y <= offset_y + page_h:
            self._scene.addLine(
                float(offset_x),
                float(y),
                float(offset_x + page_w),
                float(y),
                grid_pen,
            )
            y += GRID_SIZE

        # Vertical grid lines
        x: int = (offset_x // GRID_SIZE) * GRID_SIZE
        while x <= offset_x + page_w:
            self._scene.addLine(
                float(x),
                float(offset_y),
                float(x),
                float(offset_y + page_h),
                grid_pen,
            )
            x += GRID_SIZE

    def _draw_instance(self, inst, y_offset: int = 0) -> None:
        """Draw a component instance as a rounded rectangle with refdes label.

        Args:
            inst: A ComponentInstanceIR with loc_x, loc_y, refdes.
            y_offset: Vertical offset for multi-page rendering.
        """
        loc_x: int = getattr(inst, "loc_x", 0)
        loc_y: int = getattr(inst, "loc_y", 0) + y_offset
        refdes: str = getattr(inst, "refdes", "?")

        # Instance body — rounded rect
        rect = QRectF(
            float(loc_x),
            float(loc_y),
            float(INSTANCE_W),
            float(INSTANCE_H),
        )

        body_pen = QPen(QColor(Colors.BORDER_DEFAULT))
        body_pen.setWidth(2)
        body_brush = QBrush(QColor(Colors.AUX_BLUE))
        body_brush.setStyle(Qt.BrushStyle.SolidPattern)

        body = self._scene.addRect(
            rect,
            body_pen,
            body_brush,
        )
        body.setZValue(1)

        # Refdes label
        text_item = self._scene.addText(refdes)
        text_item.setDefaultTextColor(QColor(Colors.BG_OVERLAY))
        font = QFont()
        font.setPixelSize(FONT_SIZE)
        font.setBold(True)
        text_item.setFont(font)
        text_item.setPos(
            float(loc_x + INSTANCE_W / 2 - text_item.boundingRect().width() / 2),
            float(loc_y + INSTANCE_H / 2 - text_item.boundingRect().height() / 2),
        )
        text_item.setZValue(2)

    def _draw_wire(self, wire, y_offset: int = 0) -> None:
        """Draw a wire as a line segment.

        Args:
            wire: A WireSegment with start_x, start_y, end_x, end_y, net_name.
            y_offset: Vertical offset for multi-page rendering.
        """
        start_x: int = getattr(wire, "start_x", 0)
        start_y: int = getattr(wire, "start_y", 0) + y_offset
        end_x: int = getattr(wire, "end_x", 0)
        end_y: int = getattr(wire, "end_y", 0) + y_offset

        pen = QPen(QColor(Colors.AUX_GRAY))
        pen.setWidth(WIRE_PEN_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)

        line = self._scene.addLine(
            float(start_x),
            float(start_y),
            float(end_x),
            float(end_y),
            pen,
        )
        line.setZValue(0)


class _SchematicView(QGraphicsView):
    """Custom QGraphicsView with zoom-on-scroll and middle-button pan."""

    def __init__(
        self, scene: QGraphicsScene, parent: SchematicPreviewPanel
    ) -> None:
        """Initialize the view.

        Args:
            scene: The QGraphicsScene to display.
            parent: The parent SchematicPreviewPanel for accessing _zoom_level.
        """
        super().__init__(scene)
        self._parent_panel: SchematicPreviewPanel = parent
        self._is_panning: bool = False
        self._pan_start: QPointF = QPointF(0, 0)
        self.setMouseTracking(True)

    # ── Wheel zoom ─────────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom in/out centered on the cursor position.

        Args:
            event: The wheel event.
        """
        angle_delta = event.angleDelta().y()
        if angle_delta == 0:
            return

        zoom = self._parent_panel._zoom_level
        if angle_delta > 0 and zoom < MAX_ZOOM:
            factor = ZOOM_FACTOR
            self._parent_panel._zoom_level = zoom * factor
        elif angle_delta < 0 and zoom > MIN_ZOOM:
            factor = 1.0 / ZOOM_FACTOR
            self._parent_panel._zoom_level = zoom * factor
        else:
            return

        self.scale(factor, factor)

    # ── Middle-button pan ──────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        """Begin middle-button panning.

        Args:
            event: The mouse press event.
        """
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """Pan the view during middle-button drag.

        Args:
            event: The mouse move event.
        """
        if self._is_panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """End middle-button panning.

        Args:
            event: The mouse release event.
        """
        if event.button() == Qt.MouseButton.MiddleButton and self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)
