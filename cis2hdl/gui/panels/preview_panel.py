"""Preview Panel — placeholder for HDL project file tree preview."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..colors import Colors, FontSize, STYLE_CARD


class PreviewPanel(QWidget):
    """Preview panel showing HDL project structure after conversion.

    In Phase I this is a placeholder with centered instructional text.
    Phase II will populate a file tree from the conversion report.
    """

    PLACEHOLDER_TEXT = (
        "\u8f6c\u6362\u5b8c\u6210\u540e\uff0c\u6b64\u5904\u5c06\u663e\u793a "
        "HDL \u5de5\u7a0b\u6587\u4ef6\u6811\u9884\u89c8"
    )
    # "转换完成后，此处将显示 HDL 工程文件树预览"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(STYLE_CARD)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addStretch()

        self._placeholder = QLabel(self.PLACEHOLDER_TEXT)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(
            f"font-size: {FontSize.SM}px;"
            f"color: {Colors.TEXT_MUTED};"
            f"border: none;"
            f"background: transparent;"
        )
        self._placeholder.setWordWrap(True)
        layout.addWidget(self._placeholder)

        layout.addStretch()

    def set_preview_data(self, conversion_report: Any = None) -> None:
        """Populate the preview panel with conversion output.

        Args:
            conversion_report: The ConversionReport object from the engine.
                (Placeholder — implementation deferred to Phase II.)

        Note:
            This method is intentionally empty in Phase I.  Phase II will
            read the report's file structure and populate a QTreeWidget.
        """
        # Phase II will:
        # 1. Clear existing tree
        # 2. Iterate conversion_report.output_files
        # 3. Build a QTreeWidget mirroring the HDL project tree
        pass
