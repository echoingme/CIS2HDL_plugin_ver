"""CIS2HDL GUI 设计 Token 系统 — 基于 Anthropic Design Language"""

# ============================================================
# 颜色 Token（20 色 Anopic 暖米色体系）
# ============================================================
class Colors:
    # 背景层级
    BG_BASE     = "#ECE9E0"  # 页面底色（暖米色，不用纯白）
    BG_RAISED   = "#F5F3EC"  # 卡片/面板背景
    BG_OVERLAY  = "#FFFFFF"  # 浮层（Dropdown/Tooltip）
    BG_INVERTED = "#1E1D19"  # 深色区块（代码预览/终端）

    # 强调色系
    ACCENT       = "#D97757"  # 主 CTA（暖橙色，唯一强调色）
    ACCENT_HOVER = "#C96442"  # 橙色 hover 态
    ACCENT_MUTED = "#F0D5C8"  # 橙色弱态（进度条轨道/图标背景）

    # 辅助色（图表/波形/状态）
    AUX_BLUE   = "#6A9BCC"   # 辅助蓝
    AUX_GREEN  = "#788C5D"   # 辅助绿
    AUX_SAND   = "#C4B99A"   # 沙棕（禁用态/空状态）
    AUX_GRAY   = "#9B9890"   # 中灰（第5信号线）

    # 文字层级
    TEXT_PRIMARY   = "#141413"   # 主文字
    TEXT_SECONDARY = "#6B6860"   # 次要文字
    TEXT_MUTED     = "#9D9A91"   # 最淡文字（占位符/水印）
    TEXT_INVERTED  = "#C9C5B8"   # 深色背景文字

    # 语义色
    ERROR    = "#C0453A"   # 错误/危险（红色）
    SUCCESS  = "#6B8F47"   # 成功（绿色）
    WARNING  = "#C9943A"   # 警告（黄褐）
    INFO     = "#5A89B8"   # 信息（蓝色）

    # 边框层级
    BORDER_SUBTLE  = "#D8D5CC"   # 柔和边框（默认）
    BORDER_DEFAULT = "#C4C0B5"   # 标准边框（数据密集/工具优先）
    BORDER_STRONG  = "#A8A499"   # 强调边框（焦点态）


# ============================================================
# 间距 Token（4px 网格系统）
# ============================================================
class Spacing:
    XS   = 4    # 极紧凑（图标与文字间距）
    SM   = 8    # 紧凑（同类元素间距）
    MD   = 12   # 默认内间距
    BASE = 16   # 标准内边距（卡片/面板）
    LG   = 24   # 区块间距（数据密集）
    XL   = 32   # 区块间距（工具优先）
    XXL  = 64   # 页面级间距


# ============================================================
# 圆角 Token（4 档：外圆角 > 内圆角）
# ============================================================
class Radius:
    SM   = "4px"     # 内圆角：进度条、小标签
    MD   = "8px"     # 中圆角：按钮、输入框
    LG   = "12px"    # 外圆角：卡片、面板
    XL   = "16px"    # 大圆角：对话框、Modal
    FULL = "9999px"  # 全圆角：头像、Badge


# ============================================================
# 字号 Token（双数体系，10-20px）
# ============================================================
class FontSize:
    XXS = 10   # 微小：版本号、角标
    XS  = 12   # 辅助：说明文字、路径
    SM  = 14   # 正文：按钮、表格、输入框
    MD  = 16   # 标题：卡片标题、面板标题
    LG  = 20   # 大标题：指标数值、品牌


# ============================================================
# 字体 Token
# ============================================================
class Fonts:
    UI   = '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif'
    MONO = '"JetBrains Mono", "Cascadia Code", "Consolas", monospace'


# ============================================================
# 阴影 Token（PySide6 QGraphicsDropShadowEffect 或 QSS）
# ============================================================
class Shadow:
    CARD   = "0 1px 4px rgba(20,20,19,0.06)"    # 卡片常态
    RAISED = "0 4px 12px rgba(20,20,19,0.10)"   # 卡片悬浮
    OVERLAY = "0 8px 32px rgba(20,20,19,0.20)"  # Modal/Drawer


# ============================================================
# 布局尺寸 Token
# ============================================================
class Layout:
    SIDEBAR_WIDTH    = 240      # 侧边栏宽度（从 Crowz 260 缩小到 Anthropic 240）
    SUMMARY_BAR_H    = 96       # 指标条高度
    METRIC_CARD_MIN  = 160      # 指标卡片最小宽度
    TAB_HEIGHT       = 38       # Tab 标签高度
    LOG_COLLAPSED_H  = 36       # 日志折叠高度
    LOG_EXPANDED_H   = 160      # 日志展开高度
    WINDOW_MIN_W     = 1200     # 最小窗口宽度（与 config.gui.window_min_width 一致）
    WINDOW_MIN_H     = 800      # 最小窗口高度（与 config.gui.window_min_height 一致）
    BUTTON_MIN_H     = 32       # 按钮最小高度


# ============================================================
# 辅助函数
# ============================================================
def rgb(hex_color: str) -> str:
    """#D97757 → 217, 119, 87"""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r}, {g}, {b}"

def rgba(hex_color: str, alpha: float) -> str:
    """#D97757, 0.15 → rgba(217, 119, 87, 0.15)"""
    return f"rgba({rgb(hex_color)}, {alpha})"


# ============================================================
# 全局 QSS 样式表（基于 Token 动态生成）
# ============================================================

STYLE_BASE = f"""
    QMainWindow {{
        background-color: {Colors.BG_BASE};
        color: {Colors.TEXT_PRIMARY};
        font-family: {Fonts.UI};
        font-size: {FontSize.SM}px;
    }}
"""

STYLE_SIDEBAR = f"""
    QWidget#sidebar {{
        background-color: {Colors.BG_RAISED};
        border-right: 1px solid {Colors.BORDER_SUBTLE};
    }}
"""

STYLE_CARD = f"""
    QWidget#card {{
        background-color: {Colors.BG_RAISED};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.LG};
        padding: {Spacing.BASE}px;
    }}
"""

STYLE_TAB_WIDGET = f"""
    QTabWidget::pane {{
        border: none;
        background: transparent;
    }}
    QTabBar::tab {{
        padding: 8px 20px;
        border: none;
        color: {Colors.TEXT_SECONDARY};
        font-size: {FontSize.SM}px;
        font-family: {Fonts.UI};
    }}
    QTabBar::tab:selected {{
        color: {Colors.TEXT_PRIMARY};
        border-bottom: 2px solid {Colors.ACCENT};
    }}
    QTabBar::tab:hover:!selected {{
        color: {Colors.TEXT_PRIMARY};
    }}
"""

STYLE_SUMMARY_BAR = f"""
    QWidget#summary_bar {{
        background: transparent;
    }}
    QWidget#metric_card {{
        background-color: {Colors.BG_RAISED};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.MD};
        padding: {Spacing.MD}px {Spacing.BASE}px;
    }}
"""

STYLE_BUTTON_PRIMARY = f"""
    QPushButton#primary {{
        background-color: {Colors.ACCENT};
        color: {Colors.BG_OVERLAY};
        border: none;
        border-radius: {Radius.MD};
        padding: {Spacing.SM}px {Spacing.LG}px;
        font-weight: bold;
        min-height: {Layout.BUTTON_MIN_H}px;
    }}
    QPushButton#primary:hover {{
        background-color: {Colors.ACCENT_HOVER};
    }}
    QPushButton#primary:pressed {{
        background-color: {Colors.ACCENT_HOVER};
    }}
    QPushButton#primary:disabled {{
        background-color: {Colors.ACCENT_MUTED};
    }}
"""

STYLE_BUTTON_SECONDARY = f"""
    QPushButton#secondary {{
        background-color: {Colors.BG_OVERLAY};
        color: {Colors.ACCENT};
        border: 1px solid {Colors.ACCENT};
        border-radius: {Radius.MD};
        padding: {Spacing.SM}px {Spacing.LG}px;
        min-height: {Layout.BUTTON_MIN_H}px;
    }}
    QPushButton#secondary:hover {{
        background-color: {rgba(Colors.ACCENT, 0.08)};
    }}
"""

STYLE_BUTTON_DANGER = f"""
    QPushButton#danger {{
        background-color: {Colors.ERROR};
        color: {Colors.BG_OVERLAY};
        border: none;
        border-radius: {Radius.MD};
        padding: {Spacing.SM}px {Spacing.LG}px;
        font-weight: bold;
        min-height: {Layout.BUTTON_MIN_H}px;
    }}
    QPushButton#danger:hover {{
        background-color: #A83830;
    }}
"""

STYLE_LOG = f"""
    QWidget#log_card {{
        background-color: {Colors.BG_RAISED};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.LG};
    }}
    QPlainTextEdit#log_content {{
        background-color: {Colors.BG_RAISED};
        border: none;
        font-family: {Fonts.MONO};
        font-size: {FontSize.XS}px;
        color: {Colors.TEXT_PRIMARY};
    }}
"""

STYLE_PROGRESS = f"""
    QProgressBar {{
        border: none;
        border-radius: {Radius.SM};
        background-color: {rgba(Colors.ACCENT, 0.12)};
        height: 6px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {Colors.ACCENT};
        border-radius: {Radius.SM};
    }}
"""

STYLE_MENUBAR = f"""
    QMenuBar {{
        background-color: {Colors.BG_RAISED};
        border-bottom: 1px solid {Colors.BORDER_SUBTLE};
        padding: {Spacing.XS}px 0px;
        font-size: {FontSize.SM}px;
    }}
    QMenuBar::item:selected {{
        background-color: {rgba(Colors.ACCENT, 0.10)};
    }}
    QMenu {{
        background-color: {Colors.BG_OVERLAY};
        border: 1px solid {Colors.BORDER_DEFAULT};
        border-radius: {Radius.MD};
        padding: {Spacing.XS}px;
    }}
    QMenu::item:selected {{
        background-color: {rgba(Colors.ACCENT, 0.10)};
    }}
"""

STYLE_STATUSBAR = f"""
    QStatusBar {{
        background-color: {Colors.BG_RAISED};
        border-top: 1px solid {Colors.BORDER_SUBTLE};
        font-size: {FontSize.XXS}px;
        color: {Colors.TEXT_SECONDARY};
    }}
"""

STYLE_TREE = f"""
    QTreeView, QTreeWidget {{
        font-size: {FontSize.XS}px;
        background-color: {Colors.BG_RAISED};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.LG};
    }}
"""

STYLE_PANEL = f"""
    QWidget#panel {{
        background-color: {Colors.BG_RAISED};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.LG};
        padding: {Spacing.MD}px;
    }}
"""
