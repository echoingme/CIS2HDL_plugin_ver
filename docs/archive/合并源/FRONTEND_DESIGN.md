# CIS2HDL 前端 GUI 设计

> 版本: v2.0 | 日期: 2026-07-30 | 状态: 生效
> 设计系统: Anthropic Design Language（工具优先模式）
> 详细规范: 参见 `specs/UI_DESIGN_SPEC.md` v3.0

---

## 1. 技术选型

| 组件 | 技术 | 理由 |
|------|------|------|
| GUI 框架 | PySide6 (Qt 6 for Python) | 成熟、跨平台、原生性能、丰富的布局和控件 |
| 主窗口 | QMainWindow + QDockWidget | 可停靠面板，灵活布局 |
| 列表/表格 | QTreeView + QTableView + 自定义 Model | 项目管理、数据展示 |
| 原理图渲染 | QGraphicsView + QGraphicsScene | 矢量渲染，缩放平移 |
| 差异显示 | 自研 DiffWidget | 左右对比视图 |
| 进度 | QProgressBar + QThread worker | 非阻塞后台转换 |
| 图标 | Qt 内置图标 + 自定义 SVG | 无额外依赖 |

## 2. 界面布局

### 2.1 主窗口布局

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

### 2.2 面板说明

| 面板 | 位置 | 职能 |
|------|------|------|
| **Project Panel** | 左侧 | 树形展示 CIS 源项目结构（页面、器件、网络）和 HDL 目标结构预览 |
| **Main Work Area** | 中央 | 根据当前 Tab 显示原理图预览、匹配确认、或转换差异对比 |
| **Properties Panel** | 右侧 | 展示当前选中器件/网络的详细属性 |
| **Log Panel** | 底部 | 实时日志输出，支持按级别筛选（INFO/WARN/ERROR） |
| **Toolbar** | 顶部 | 常用操作快捷按钮 |
| **Status Bar** | 最底部 | 当前状态、进度条、转换统计摘要 |

---

## 3. 核心界面流程

### 3.1 转换工作流

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

### 3.2 界面状态图

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

---

## 4. 关键组件设计

### 4.1 Project Panel (QTreeView)

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

### 4.2 Match Review Panel (QSplitter)

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

### 4.3 Diff View (QSplitter)

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

### 4.4 Log Panel (QPlainTextEdit + Filter)

```python
class LogPanel(QWidget):
    """实时日志面板"""
    
    # 功能：
    # - QPlainTextEdit 只读输出
    # - 工具栏：[INFO ✓] [WARN ✓] [ERROR ✓] [Clear]
    # - 使用 HTML 富文本着色
    # - 支持复制/导出
```

---

## 5. 交互设计原则

| 原则 | 实现 |
|------|------|
| **非阻塞** | 所有耗时操作在 QThread worker 中执行，GUI 始终响应 |
| **可撤销** | 匹配确认支持撤销/重做（Undo/Redo 栈） |
| **进度可见** | QProgressBar 显示当前操作进度，状态栏显示预估剩余时间 |
| **批量操作** | 支持 Ctrl/Shift 多选 → 批量确认匹配 |
| **搜索过滤** | 器件列表、日志面板支持实时搜索和正则过滤 |
| **键盘快捷键** | 核心操作有快捷键（Ctrl+O 打开, Ctrl+R 转换等） |

---

## 6. 文件依赖

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
