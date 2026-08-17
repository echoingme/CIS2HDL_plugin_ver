"""S9 GUI v2 QSS 样式表 — 复用 ``cis2hdl/gui/colors.py`` Token（Anthropic 暖米色）。

设计依据：``docs/gui-design.md`` §6（视觉方向：工程工作台，克制中性色 +
深色可停靠面板 + 清晰层级）。所有样式值来自 colors.py Token，禁止裸值。
"""

from __future__ import annotations

from ..colors import (
    Colors,
    Fonts,
    FontSize,
    Layout,
    Radius,
    Spacing,
    rgba,
)

__all__ = ["STYLE_V2", "STYLE_RUNNER", "STYLE_YAML", "STYLE_REPORT", "STYLE_SIDEBAR"]

#: 侧边栏（Profile 列表）样式。
STYLE_SIDEBAR = f"""
    QWidget#v2_sidebar {{
        background-color: {Colors.BG_RAISED};
        border-right: 1px solid {Colors.BORDER_SUBTLE};
    }}
    QListWidget#profile_list {{
        background-color: {Colors.BG_RAISED};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.LG};
        padding: {Spacing.XS}px;
    }}
    QListWidget#profile_list::item {{
        padding: {Spacing.SM}px {Spacing.MD}px;
        border-radius: {Radius.MD};
        color: {Colors.TEXT_PRIMARY};
        font-size: {FontSize.SM}px;
    }}
    QListWidget#profile_list::item:selected {{
        background-color: {rgba(Colors.ACCENT, 0.14)};
        color: {Colors.TEXT_PRIMARY};
        border-left: 3px solid {Colors.ACCENT};
    }}
    QListWidget#profile_list::item:hover:!selected {{
        background-color: {rgba(Colors.ACCENT, 0.06)};
    }}
"""

#: Profile 工具栏 / 配置编辑器区样式。
STYLE_V2 = f"""
    QWidget#v2_root {{
        background-color: {Colors.BG_BASE};
        color: {Colors.TEXT_PRIMARY};
        font-family: {Fonts.UI};
        font-size: {FontSize.SM}px;
    }}
    QWidget#card {{
        background-color: {Colors.BG_RAISED};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.LG};
    }}
    QLabel#section_title {{
        color: {Colors.TEXT_SECONDARY};
        font-size: {FontSize.XS}px;
        font-weight: bold;
        letter-spacing: 1px;
    }}
    QLabel#plugin_desc {{
        color: {Colors.TEXT_SECONDARY};
        font-size: {FontSize.XS}px;
    }}
    QLabel#badge_builtin {{
        background-color: {rgba(Colors.AUX_BLUE, 0.16)};
        color: {Colors.INFO};
        border-radius: {Radius.SM};
        padding: 1px {Spacing.SM}px;
        font-size: {FontSize.XXS}px;
    }}
    QLabel#badge_custom {{
        background-color: {rgba(Colors.AUX_SAND, 0.30)};
        color: {Colors.TEXT_SECONDARY};
        border-radius: {Radius.SM};
        padding: 1px {Spacing.SM}px;
        font-size: {FontSize.XXS}px;
    }}
    QLabel#dup_feedback {{
        background-color: {rgba(Colors.WARNING, 0.12)};
        color: {Colors.WARNING};
        border: 1px solid {rgba(Colors.WARNING, 0.4)};
        border-radius: {Radius.MD};
        padding: {Spacing.SM}px {Spacing.MD}px;
        font-size: {FontSize.XS}px;
    }}
    QPushButton {{
        background-color: {Colors.BG_OVERLAY};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER_DEFAULT};
        border-radius: {Radius.MD};
        padding: {Spacing.SM}px {Spacing.MD}px;
        font-size: {FontSize.SM}px;
        min-height: {Layout.BUTTON_MIN_H - 8}px;
    }}
    QPushButton:hover {{
        border-color: {Colors.ACCENT};
        color: {Colors.ACCENT};
    }}
    QPushButton#primary {{
        background-color: {Colors.ACCENT};
        color: {Colors.BG_OVERLAY};
        border: none;
        font-weight: bold;
    }}
    QPushButton#primary:hover {{
        background-color: {Colors.ACCENT_HOVER};
        color: {Colors.BG_OVERLAY};
    }}
    QPushButton#danger {{
        color: {Colors.ERROR};
        border-color: {Colors.ERROR};
    }}
    QTabWidget::pane {{
        border: none;
        background: transparent;
    }}
    QTabBar::tab {{
        padding: 8px 18px;
        border: none;
        color: {Colors.TEXT_SECONDARY};
        font-size: {FontSize.SM}px;
    }}
    QTabBar::tab:selected {{
        color: {Colors.TEXT_PRIMARY};
        border-bottom: 2px solid {Colors.ACCENT};
    }}
    QTabBar::tab:hover:!selected {{
        color: {Colors.TEXT_PRIMARY};
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
    }}
    QScrollBar::handle:vertical {{
        background: {Colors.BORDER_DEFAULT};
        border-radius: 5px;
        min-height: 24px;
    }}
"""

#: 转换执行区样式（进度条/日志）。
STYLE_RUNNER = f"""
    QWidget#v2_runner {{
        background-color: {Colors.BG_RAISED};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.LG};
    }}
    QProgressBar {{
        border: none;
        border-radius: {Radius.SM};
        background-color: {rgba(Colors.ACCENT, 0.12)};
        height: 8px;
        text-align: center;
        font-size: {FontSize.XXS}px;
    }}
    QProgressBar::chunk {{
        background-color: {Colors.ACCENT};
        border-radius: {Radius.SM};
    }}
    QPlainTextEdit#log_content {{
        background-color: {Colors.BG_INVERTED};
        color: {Colors.TEXT_INVERTED};
        border: none;
        border-radius: {Radius.MD};
        font-family: {Fonts.MONO};
        font-size: {FontSize.XS}px;
    }}
    QLabel#stage_label {{
        font-size: {FontSize.XXS}px;
        color: {Colors.TEXT_SECONDARY};
    }}
"""

#: yaml 编辑器样式（等宽 + 深色）。
STYLE_YAML = f"""
    QPlainTextEdit#yaml_editor {{
        background-color: {Colors.BG_INVERTED};
        color: {Colors.TEXT_INVERTED};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.MD};
        font-family: {Fonts.MONO};
        font-size: {FontSize.XS}px;
        selection-background-color: {rgba(Colors.ACCENT, 0.45)};
    }}
    QLabel#yaml_invalid {{
        color: {Colors.ERROR};
        font-size: {FontSize.XS}px;
    }}
"""

#: 结果面板样式。
STYLE_REPORT = f"""
    QWidget#v2_result {{
        background-color: {Colors.BG_RAISED};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.LG};
    }}
    QPlainTextEdit#report_content {{
        background-color: {Colors.BG_OVERLAY};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.MD};
        font-family: {Fonts.MONO};
        font-size: {FontSize.XS}px;
    }}
    QTableWidget {{
        background-color: {Colors.BG_OVERLAY};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.MD};
        font-size: {FontSize.XS}px;
    }}
    QHeaderView::section {{
        background-color: {Colors.BG_RAISED};
        color: {Colors.TEXT_SECONDARY};
        border: none;
        border-bottom: 1px solid {Colors.BORDER_SUBTLE};
        padding: {Spacing.XS}px;
        font-size: {FontSize.XS}px;
        font-weight: bold;
    }}
    QTableWidget::item:selected {{
        background-color: {rgba(Colors.AUX_BLUE, 0.18)};
    }}
"""
