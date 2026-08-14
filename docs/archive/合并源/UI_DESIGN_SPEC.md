# CIS2HDL 用户界面设计规范

> 版本: v1.1.0 | 日期: 2026-08-07 | 状态: 强制生效
> 基于: Anthropic Design Language（工具优先模式）
> 实现: `cis2hdl/gui/colors.py` — 完整 Token 体系
> 整合说明: 本文档为 UI 设计规范唯一权威，整合原 UI_DESIGN_SPEC（v3.0，2026-07-30）与 FRONTEND_DESIGN（v2.0，2026-07-30）；交互流程设计见「13. 交互流程设计（原 FRONTEND_DESIGN）」。

---

## 1. 设计哲学

CIS2HDL 是 EDA 专业工具，遵循 Anthropic Design Language 的**"工具优先"模式**：
- **密度优先**：信息密度高于留白美学，功能完整性优先
- **暖色克制**：暖米色底色 + 单一橙色 CTA，拒绝多彩
- **Token 一切**：颜色/间距/字体/圆角全部通过 Python 常量引用，禁止硬编码
- **红色强制**：所有不可逆操作用红色按钮强调，不用克制灰色

参考来源：Anthropic 官方前端设计规范（SKILL.md、design-rules.md、systems.md、typography-cn.md、dashboard.md）

---

## 2. Token 体系总览

所有样式定义集中在 `cis2hdl/gui/colors.py`，通过 7 层 Token 常量类管理：

| 层 | 类名 | Token 数 | 作用域 |
|----|------|:--:|------|
| 颜色 | `Colors` | 22 | 背景/强调/辅助/文字/语义/边框 |
| 间距 | `Spacing` | 7 | 4px 网格系统 |
| 圆角 | `Radius` | 5 | 外圆角 > 内圆角 |
| 字号 | `FontSize` | 5 | 双数体系 (10-20px) |
| 字体 | `Fonts` | 2 | UI / MONO 字体栈 |
| 阴影 | `Shadow` | 3 | 卡片/悬浮/浮层阴影 |
| 布局 | `Layout` | 9 | 尺寸/高度/宽度常量 |

---

## 3. 颜色系统

### 3.1 颜色 Token（22 色 Anthropic 暖米色体系）

```python
class Colors:
    # 背景层级 — 暖色分层，不用纯白
    BG_BASE     = "#ECE9E0"  # 页面底色（暖米色）
    BG_RAISED   = "#F5F3EC"  # 卡片/面板背景
    BG_OVERLAY  = "#FFFFFF"  # 浮层（Dropdown/Tooltip）
    BG_INVERTED = "#1E1D19"  # 深色区块（代码预览/终端）

    # 强调色系 — 暖橙唯一 CTA
    ACCENT       = "#D97757"  # 主 CTA（暖橙色）
    ACCENT_HOVER = "#C96442"  # 橙色 hover 态
    ACCENT_MUTED = "#F0D5C8"  # 橙色弱态（进度条轨道/图标背景）

    # 辅助色 — 图表/波形/状态
    AUX_BLUE   = "#6A9BCC"   # 辅助蓝
    AUX_GREEN  = "#788C5D"   # 辅助绿
    AUX_SAND   = "#C4B99A"   # 沙棕（禁用态/空状态）
    AUX_GRAY   = "#9B9890"   # 中灰

    # 文字层级 — 暖色调深字
    TEXT_PRIMARY   = "#141413"   # 主文字
    TEXT_SECONDARY = "#6B6860"   # 次要文字
    TEXT_MUTED     = "#9D9A91"   # 最淡文字
    TEXT_INVERTED  = "#C9C5B8"   # 深色背景文字

    # 语义色 — 强制红色危险操作
    ERROR    = "#C0453A"   # 错误/危险（红色）
    SUCCESS  = "#6B8F47"   # 成功（绿色）
    WARNING  = "#C9943A"   # 警告（黄褐）
    INFO     = "#5A89B8"   # 信息（蓝色）

    # 边框层级 — 透明度替代实色
    BORDER_SUBTLE  = "#D8D5CC"   # 柔和边框（默认）
    BORDER_DEFAULT = "#C4C0B5"   # 标准边框
    BORDER_STRONG  = "#A8A499"   # 强调边框（焦点态）
```

### 3.2 颜色使用规则

| 规则 | 说明 |
|------|------|
| **底色不用纯白** | 页面背景用 `BG_BASE`，卡片用 `BG_RAISED`，禁止 `#FFFFFF` 做页面底色 |
| **主 CTA 只用橙色** | 主按钮/激活态用 `ACCENT`，禁止蓝色/青色做主按钮 |
| **危险操作强制红色** | 删除/覆盖/不可逆操作用 `ERROR`，不用灰色或中性色 |
| **边框用透明度** | 优先 `rgba()` 透明度边框，减少实色分割线 |
| **颜色不超过 5 种** | 图表/波形/信号线配色从辅助色轮候，禁止彩虹色 |

### 3.3 辅助函数

```python
def rgb(hex_color: str) -> str:
    """#D97757 → 217, 119, 87"""
    ...

def rgba(hex_color: str, alpha: float) -> str:
    """#D97757, 0.15 → rgba(217, 119, 87, 0.15)"""
    ...
```

---

## 4. 间距系统（4px 网格）

```python
class Spacing:
    XS   = 4    # 极紧凑（图标与文字间距）
    SM   = 8    # 紧凑（同类元素间距）
    MD   = 12   # 默认内间距
    BASE = 16   # 标准内边距（卡片/面板）
    LG   = 24   # 区块间距（数据密集）
    XL   = 32   # 区块间距（工具优先）
    XXL  = 64   # 页面级间距
```

### 使用规则

| 场景 | Token | 值 |
|------|-------|:--:|
| 卡片内边距 | `Spacing.BASE` | 16px |
| 卡片间距 | `Spacing.LG` | 24px |
| 同类元素间距 | `Spacing.SM` | 8px |
| 栅格上下间距 | 大于左右间距 | 上=SM, 左=XS |
| 按钮水平内边距 | `Spacing.LG` | 24px |
| 按钮垂直内边距 | `Spacing.SM` | 8px |

> ⚠️ 所有间距必须是 4 的倍数。工具优先模式下留白可压缩至 `Spacing.MD`(12px)。

---

## 5. 圆角规范（外圆角 > 内圆角）

```python
class Radius:
    SM   = "4px"     # 内圆角：进度条、小标签
    MD   = "8px"     # 中圆角：按钮、输入框
    LG   = "12px"    # 外圆角：卡片、面板
    XL   = "16px"    # 大圆角：对话框、Modal
    FULL = "9999px"  # 全圆角：头像、Badge
```

### 使用规则

| 场景 | Token | 说明 |
|------|-------|------|
| 进度条、标签 | `SM` | 内层小元素 |
| 按钮、输入框 | `MD` | 交互控件 |
| 卡片、面板 | `LG` | 外层容器 |
| 对话框 | `XL` | 弹窗 |
| 状态圆点 | `FULL` | 圆形 |

> ⚠️ 嵌套元素的内圆角必须小于外圆角（内 `MD` + 外 `LG`）。

---

## 6. 字体、阴影与排版

### 6.1 字号 Token（双数体系）

```python
class FontSize:
    XXS = 10   # 微小：版本号、角标
    XS  = 12   # 辅助：表格数据、输入框、日志
    SM  = 14   # 正文：按钮、导航、Tab
    MD  = 16   # 标题：面板标题、指标数值
    LG  = 20   # 大标题：品牌标识
```

### 6.2 字体 Token

```python
class Fonts:
    UI   = '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif'
    MONO = '"JetBrains Mono", "Cascadia Code", "Consolas", monospace'
```

### 使用规则

| 用途 | 字体 | 字号 | 字重 |
|------|------|:--:|:--:|
| 品牌名称 | `Fonts.UI` | `LG`(20) | 600 |
| 面板标题 | `Fonts.UI` | `MD`(16) | 600 |
| 指标数值 | `Fonts.UI` | `MD`(16) | 700 |
| 正文/导航 | `Fonts.UI` | `SM`(14) | 400 |
| 表格/日志 | `Fonts.UI`/`MONO` | `XS`(12) | 400 |
| 辅助文字 | `Fonts.UI` | `XS`(12) | 400 |
| 版本号/角标 | `Fonts.UI` | `XXS`(10) | 400 |

> ⚠️ 字号必须是双数，最小不低于 10px。中文 UI 字体字重用 400（视觉上等同于 semibold）。

### 6.3 阴影 Token

```python
class Shadow:
    CARD    = "0 1px 4px rgba(20,20,19,0.06)"    # 卡片常态
    RAISED  = "0 4px 12px rgba(20,20,19,0.10)"   # 卡片悬浮
    OVERLAY = "0 8px 32px rgba(20,20,19,0.20)"   # Modal/Drawer
```

| 场景 | Token | 说明 |
|------|-------|------|
| 卡片常态 | `Shadow.CARD` | 默认卡片阴影 |
| 卡片悬浮 | `Shadow.RAISED` | hover 提升层级 |
| Modal/Drawer | `Shadow.OVERLAY` | 浮层阴影 |

> ⚠️ 阴影必须引用 `Shadow` Token，禁止硬编码 `box-shadow`/`QGraphicsDropShadowEffect` 数值。

---

## 7. 布局尺寸

```python
class Layout:
    SIDEBAR_WIDTH    = 240      # 侧边栏宽度
    SUMMARY_BAR_H    = 96       # 指标条高度
    METRIC_CARD_MIN  = 160      # 指标卡片最小宽
    TAB_HEIGHT       = 38       # Tab 标签高度
    LOG_COLLAPSED_H  = 36       # 日志折叠高度
    LOG_EXPANDED_H   = 160      # 日志展开高度
    WINDOW_MIN_W     = 1200     # 最小窗口宽
    WINDOW_MIN_H     = 800      # 最小窗口高
    BUTTON_MIN_H     = 32       # 按钮最小高度
```

---

## 8. 组件样式规范

### 8.1 按钮（三种）

```
主按钮（Primary — STYLE_BUTTON_PRIMARY）:
  background: ACCENT (#D97757)
  color: BG_OVERLAY (#FFFFFF)
  border: none; border-radius: Radius.MD (8px)
  padding: Spacing.SM(8) Spacing.LG(24)
  font-weight: bold; min-height: 32px
  :hover → ACCENT_HOVER (#C96442)
  :disabled → ACCENT_MUTED (#F0D5C8)

次按钮（Secondary — STYLE_BUTTON_SECONDARY）:
  background: BG_OVERLAY (#FFFFFF)
  color: ACCENT (#D97757)
  border: 1px solid ACCENT
  border-radius: Radius.MD (8px)
  padding: Spacing.SM(8) Spacing.LG(24)
  min-height: 32px
  :hover → background: rgba(ACCENT, 0.08)

危险按钮（Danger — STYLE_BUTTON_DANGER）:
  background: ERROR (#C0453A)  ← 强制红色
  color: BG_OVERLAY (#FFFFFF)
  border: none; border-radius: Radius.MD (8px)
  padding: Spacing.SM(8) Spacing.LG(24)
  font-weight: bold; min-height: 32px
  :hover → #A83830
```

### 8.2 卡片

```
（STYLE_CARD）:
  background: BG_RAISED (#F5F3EC)
  border: 1px solid BORDER_SUBTLE (#D8D5CC)
  border-radius: Radius.LG (12px)
  padding: Spacing.BASE (16px)
  shadow: 0 1px 4px rgba(20,20,19,0.06) — 使用 Shadow.CARD
```

### 8.3 侧边栏

```
（STYLE_SIDEBAR）:
  width: Layout.SIDEBAR_WIDTH (240px)
  background: BG_RAISED (#F5F3EC)
  border-right: 1px solid BORDER_SUBTLE
  导航项: 36px 高, flat, 选中态左侧 2px ACCENT 条
```

### 8.4 Tab 控件

```
（STYLE_TAB_WIDGET）:
  QTabBar::tab: 8px 20px padding, 14px font
  未选中: TEXT_SECONDARY
  选中: TEXT_PRIMARY + 底部 2px ACCENT 线条
  :hover: TEXT_PRIMARY
  QTabWidget::pane: 无边框, 透明背景
```

### 8.5 进度条

```
（STYLE_PROGRESS）:
  轨道: rgba(ACCENT, 0.12), 无边框, 4px 圆角, 6px 高
  chunk: ACCENT (#D97757), 4px 圆角
```

### 8.6 菜单栏与状态栏

```
（STYLE_MENUBAR）:
  background: BG_RAISED; border-bottom: 1px solid BORDER_SUBTLE
  item:selected → rgba(ACCENT, 0.10)

（STYLE_STATUSBAR）:
  background: BG_RAISED; border-top: 1px solid BORDER_SUBTLE
  font-size: XS(12); color: TEXT_SECONDARY
```

### 8.7 日志面板

```
（STYLE_LOG）:
  卡片: BG_RAISED + BORDER_SUBTLE + Radius.LG(12px)
  内容: MONO 字体, XS(12px)字号, TEXT_PRIMARY 颜色
  折叠态: 36px 标题栏; 展开态: 160px
```

### 8.8 指标卡片

```
（STYLE_SUMMARY_BAR / metric_card）:
  background: BG_RAISED; border: 1px solid BORDER_SUBTLE
  border-radius: Radius.MD(8px); padding: MD(12) BASE(16)
  值: MD(16px) Bold TEXT_PRIMARY
  标签: XS(12px) TEXT_MUTED
```

---

## 9. 状态指示

| 状态 | 颜色 Token | 色值 |
|------|-----------|------|
| 成功/已加载 | `ACCENT` | #D97757（暖橙圆点） |
| 警告/待确认 | `WARNING` | #C9943A |
| 错误/未匹配 | `ERROR` | #C0453A |
| 信息/处理中 | `TEXT_MUTED` | #9D9A91 |
| 已匹配 | `SUCCESS` | #6B8F47 |

---

## 10. 布局架构

```
┌──────────────────────────────────────────────────────┐
│  Menu Bar (STYLE_MENUBAR)                            │
├─────────────┬────────────────────────────────────────┤
│  SIDEBAR    │  Summary Bar (4 指标卡片)              │
│  240px      ├────────────────────────────────────────┤
│  ┌────────┐ │  TabContainer                          │
│  │CIS2HDL │ │   [诊断] [预览] [匹配]* [差异]*        │
│  └────────┘ │  ┌──────────────────────────────────┐  │
│             │  │ 当前 Tab 内容（卡片容器）         │  │
│  项目信息    │  └──────────────────────────────────┘  │
│  导航菜单    ├────────────────────────────────────────┤
│  快捷按钮    │  Log Panel（可折叠卡片）               │
│  v1.1.0     │                                        │
├─────────────┴────────────────────────────────────────┤
│  Status Bar (STYLE_STATUSBAR)                        │
└──────────────────────────────────────────────────────┘
```

---

## 11. QSS 样式表清单

所有 QSS 通过 `colors.py` 中的 `STYLE_*` 字典动态生成：

| 样式表 | 覆盖范围 |
|--------|---------|
| `STYLE_BASE` | 全局默认样式 |
| `STYLE_SIDEBAR` | 侧边栏 |
| `STYLE_CARD` | 通用卡片 |
| `STYLE_TAB_WIDGET` | Tab 控件 |
| `STYLE_SUMMARY_BAR` | 指标条 + 指标卡片 |
| `STYLE_BUTTON_PRIMARY` | 主按钮 |
| `STYLE_BUTTON_SECONDARY` | 次按钮 |
| `STYLE_BUTTON_DANGER` | 危险按钮 |
| `STYLE_LOG` | 日志面板 |
| `STYLE_PROGRESS` | 进度条 |
| `STYLE_MENUBAR` | 菜单栏 |
| `STYLE_STATUSBAR` | 状态栏 |

---

## 12. 合规检查清单

- [ ] 所有颜色必须来自 `Colors` 22 色板，无硬编码 hex
- [ ] 所有间距使用 `Spacing` Token，为 4 的倍数
- [ ] 所有圆角使用 `Radius` Token，内圆角 < 外圆角
- [ ] 所有字号使用 `FontSize` Token，双数，≥ 10px
- [ ] 界面文字使用 `Fonts.UI` 字体栈
- [ ] 等宽文字使用 `Fonts.MONO` 字体栈
- [ ] 所有阴影使用 `Shadow` Token，无硬编码 box-shadow
- [ ] 页面底色不用纯白（用 `BG_BASE` 或 `BG_RAISED`）
- [ ] 主 CTA 用橙色（`ACCENT`），不用青色/蓝色
- [ ] 危险操作按钮用红色（`STYLE_BUTTON_DANGER`）
- [ ] 全部 QSS 通过 `colors.py` 中的 `STYLE_*` 引用，不内联
- [ ] 透明度优先用 `rgba()` 函数，减少实色边框
- [ ] 按钮高度 ≥ 32px（`BUTTON_MIN_H`）

---

## 13. 交互流程设计（原 FRONTEND_DESIGN）

> 说明: 本章由原 `FRONTEND_DESIGN.md`（v2.0，2026-07-30）整合吸收，原文内容保全保留。其中「13.6 文件依赖」为原文档依赖树，与实际结构有出入，以「13.6.2 当前实际 GUI 结构」为准。

### 13.1 技术选型

| 组件 | 技术 | 理由 |
|------|------|------|
| GUI 框架 | PySide6 (Qt 6 for Python) | 成熟、跨平台、原生性能、丰富的布局和控件 |
| 主窗口 | QMainWindow + QDockWidget | 可停靠面板，灵活布局 |
| 列表/表格 | QTreeView + QTableView + 自定义 Model | 项目管理、数据展示 |
| 原理图渲染 | QGraphicsView + QGraphicsScene | 矢量渲染，缩放平移 |
| 差异显示 | 自研 DiffWidget | 左右对比视图 |
| 进度 | QProgressBar + QThread worker | 非阻塞后台转换 |
| 图标 | Qt 内置图标 + 自定义 SVG | 无额外依赖 |

### 13.2 界面布局

#### 13.2.1 主窗口布局

```
┌─────────────────────────────────────────────────────────────┐
│  Menu Bar:  File  Edit  View  Convert  Tools  Help         │
├─────────────────────────────────────────────────────────────┤
│  Toolbar:  [Open] [Save] [Convert ▶] [Preview] [Report]    │
├──────────┬────────────────────────────────────┬─────────────┤
│ Project  │                                    │  Properties │
│ Panel    │        Main Work Area              │  Panel      │
│ (Left)   │                                    │  (Right)    │
│          │   ┌──────────────────────────┐     │             │
│  📁 CIS  │   │                          │     │  Component: │
│   ├─p1   │   │    Schematic Preview /   │     │  Name: R1   │
│   ├─p2   │   │    Match Review /        │     │  Value:10K  │
│   └─p3   │   │    Diff View             │     │  Foot: 0603 │
│          │   │                          │     │  ...        │
│  📁 HDL  │   │                          │     │             │
│   ├─...  │   └──────────────────────────┘     │             │
│          │                                    │             │
├──────────┴────────────────────────────────────┴─────────────┤
│  Log / Status Bar                                           │
│  [INFO] 14:23:01 Parsing complete: 3 pages, 142 components  │
│  [WARN] 14:23:05 U3 (LM358) needs manual pin mapping        │
│  [ OK ] 14:23:10 Conversion finished. 0 errors, 3 warnings  │
└─────────────────────────────────────────────────────────────┘
```

#### 13.2.2 面板说明

| 面板 | 位置 | 职能 |
|------|------|------|
| **Project Panel** | 左侧 | 树形展示 CIS 源项目结构（页面、器件、网络）和 HDL 目标结构预览 |
| **Main Work Area** | 中央 | 根据当前 Tab 显示原理图预览、匹配确认、或转换差异对比 |
| **Properties Panel** | 右侧 | 展示当前选中器件/网络的详细属性 |
| **Log Panel** | 底部 | 实时日志输出，支持按级别筛选（INFO/WARN/ERROR） |
| **Toolbar** | 顶部 | 常用操作快捷按钮 |
| **Status Bar** | 最底部 | 当前状态、进度条、转换统计摘要 |

### 13.3 核心界面流程

#### 13.3.1 转换工作流（六步）

```
Step 1: Open Project
  ├─ 用户选择 .dsn 文件
  ├─ 系统解析 DSN，填充 Project Panel
  └─ 状态栏显示解析结果摘要

Step 2: Configure
  ├─ 用户指定 HDL 目标器件库路径
  ├─ 用户配置转换选项（输出目录、命名规则等）
  └─ 可选：加载已有映射规则文件

Step 3: Run Matching
  ├─ 系统后台运行匹配管道
  ├─ Main Area 切换到 Match Review 视图
  │   ├─ 左侧：CIS 器件列表（标注匹配置信度颜色）
  │   ├─ 右侧：HDL 候选器件列表
  │   └─ 底部：引脚映射预览
  └─ 用户逐一确认/修正低置信度匹配

Step 4: Validate & Preview
  ├─ 系统运行校验管道
  ├─ Main Area 切换到 Preview 视图
  │   └─ 展示目标 HDL 工程文件树
  └─ 任何校验错误/警告高亮显示

Step 5: Generate
  ├─ 用户点击 "Convert" 按钮
  ├─ 进度条显示生成进度
  └─ 完成后显示 Generation Report

Step 6: Review Report
  ├─ 统计摘要：转换器件数/成功/警告/失败
  ├─ 详细列表：每个器件的映射结果
  └─ 可导出为 PDF/HTML
```

#### 13.3.2 界面状态图（IDLE→LOADED→MATCHING→VALIDATED→COMPLETE）

```
                    ┌──────────┐
                    │  IDLE    │
                    └────┬─────┘
                         │ Open Project
                         ▼
                    ┌──────────┐
                    │ LOADED   │
                    └────┬─────┘
                         │ Configure & Run Match
                         ▼
                    ┌──────────┐
                    │ MATCHING │◄──── 人工确认循环 ────┐
                    └────┬─────┘                       │
                         │ All confirmed                │
                         ▼                             │
                    ┌──────────┐                       │
                    │ VALIDATED│                       │
                    └────┬─────┘                       │
                         │ Generate                    │
                         ▼                             │
                    ┌──────────┐                       │
                    │ COMPLETE │                       │
                    └──────────┘                       │
                         │                             │
                         └─── 可返回重新匹配 ──────────┘
```

### 13.4 关键组件设计

#### 13.4.1 Project Panel (QTreeView)

```python
class ProjectTreeModel(QAbstractItemModel):
    """CIS 项目结构树模型"""
    
    # 树结构
    # 📁 Project "my_design"
    #   ├─ 📄 Page 1 (top.sch.1.1)  → SchematicPageIR
    #   │   ├─ 🔲 R1 (RES_0603_10K)
    #   │   ├─ 🔲 R2 (RES_0603_1K)
    #   │   ├─ 🔳 U1 (LM358)
    #   │   └─ ...
    #   ├─ 📄 Page 2 (top.sch.1.2)
    #   └─ ...
    
    # 每个节点包含：
    # - 图标（颜色表示匹配状态：绿=已匹配，黄=待确认，红=未匹配）
    # - 名称
    # - 位号/器件名
```

#### 13.4.2 Match Review Panel (QSplitter)

```python
class MatchReviewPanel(QWidget):
    """器件匹配确认面板"""
    
    # 布局：三栏
    # ┌──────────────┬──────────────┬──────────────┐
    # │ CIS Devices   │ HDL Candidates│ Pin Mapping  │
    # │ (QListWidget) │ (QListWidget) │ (QTableWidget)│
    # │               │               │               │
    # │ R1 (matched)  │ RES_0603_10K │ CIS Pin  HDL  │
    # │ R2 (pending)  │ RES_0603_1K  │ 1     →  1    │
    # │ U1 (unmatched)│ RES_0402_10K │ 2     →  2    │
    # │ ...           │ ...           │               │
    # └──────────────┴──────────────┴──────────────┘
    #                          [Accept] [Skip] [Manual]
```

#### 13.4.3 Diff View (QSplitter)

```python
class DiffView(QWidget):
    """转换前后差异对比"""
    
    # 左右分屏
    # ┌──────────────────┬──────────────────┐
    # │ CIS Source        │ HDL Target       │
    # │ ┌──────────────┐ │ ┌──────────────┐ │
    # │ │ R1 RES_0603   │ │ │ R1 RES_0603  │ │ ← 绿色：匹配
    # │ │ R2 CAP_0805   │ │ │ R2 CAP_0805  │ │ ← 绿色
    # │ │ U3 LM358N     │ │ │ U3 ⚠ MANUAL │ │ ← 黄色：待确认
    # │ │ C5 100nF      │ │ │ --- MISSING  │ │ ← 红色：缺失
    # │ └──────────────┘ │ └──────────────┘ │
    # └──────────────────┴──────────────────┘
```

#### 13.4.4 Log Panel (QPlainTextEdit + Filter)

```python
class LogPanel(QWidget):
    """实时日志面板"""
    
    # 功能：
    # - QPlainTextEdit 只读输出
    # - 工具栏：[INFO ✓] [WARN ✓] [ERROR ✓] [Clear]
    # - 使用 HTML 富文本着色
    # - 支持复制/导出
```

### 13.5 交互设计原则

| 原则 | 实现 |
|------|------|
| **非阻塞** | 所有耗时操作在 QThread worker 中执行，GUI 始终响应 |
| **可撤销** | 匹配确认支持撤销/重做（Undo/Redo 栈） |
| **进度可见** | QProgressBar 显示当前操作进度，状态栏显示预估剩余时间 |
| **批量操作** | 支持 Ctrl/Shift 多选 → 批量确认匹配 |
| **搜索过滤** | 器件列表、日志面板支持实时搜索和正则过滤 |
| **键盘快捷键** | 核心操作有快捷键（Ctrl+O 打开, Ctrl+R 转换等） |

### 13.6 文件依赖（原 FRONTEND_DESIGN §6，与实际结构有出入，以正文为准）

> ⚠️ 以下 13.6.1 为原 FRONTEND_DESIGN 依赖树（历史保留，仅供参考）；实际结构以 13.6.2 为准。

#### 13.6.1 原 FRONTEND_DESIGN 依赖树（历史，与实际结构有出入）

```
gui/
├── __init__.py
├── app.py                   # QApplication, 主入口
├── main_window.py           # 主窗口
├── panels/
│   ├── __init__.py
│   ├── project_panel.py     # 项目结构树
│   ├── match_review.py      # 匹配确认
│   ├── preview_panel.py     # 转换预览
│   └── log_panel.py         # 日志面板
├── dialogs/
│   ├── __init__.py
│   ├── settings_dialog.py   # 设置对话框
│   └── match_confirm.py     # 确认对话框
├── widgets/
│   ├── __init__.py
│   ├── diff_view.py         # 差异对比视图
│   └── status_indicator.py  # 状态指示器
└── models/
    ├── __init__.py
    ├── project_tree.py      # 项目树 Model
    └── match_table.py       # 匹配表 Model
```

#### 13.6.2 当前实际 GUI 结构（2026-08-07 实测）

```
cis2hdl/gui/
├── __init__.py
├── app.py                   # QApplication, 主入口
├── main_window.py           # 主窗口（804 行）
├── colors.py                # Token 体系（310 行，7 类）
├── candidate_selector.py    # 候选选择（798 行）
├── panels/
│   ├── __init__.py
│   ├── sidebar.py           # 侧边栏
│   ├── summary_bar.py       # 指标条
│   ├── tab_container.py     # Tab 容器
│   ├── project_panel.py     # 项目结构树
│   ├── match_review.py      # 匹配确认
│   ├── preview_panel.py     # 转换预览
│   ├── log_panel.py         # 日志面板
│   ├── report_panel.py      # 报告面板
│   ├── diff_view.py         # 差异对比视图
│   ├── schematic_view.py    # 原理图视图
│   ├── diagnostic_panel.py  # 诊断面板
│   ├── error_diagnostic_panel.py  # 错误诊断面板
│   └── rules_panel.py       # 规则面板
├── dialogs/
│   ├── __init__.py
│   ├── settings_dialog.py   # 设置对话框
│   ├── match_confirm.py     # 匹配确认对话框
│   └── recovery_dialog.py   # 恢复对话框
└── widgets/
    ├── __init__.py
    └── conversion_worker.py # 转换后台线程

注: 不存在 models/ 目录与 status_indicator.py（原 FRONTEND_DESIGN 依赖树中的这两项已核实不存在）。
```
