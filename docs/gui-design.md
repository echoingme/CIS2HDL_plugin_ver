# CIS2HDL GUI 设计文档（gui-design.md）

> 版本：S8.5（2026-08-17）｜依据：phase23-plugin-architecture.md §3.8/§6 + anthropic-style-frontend-cn 规范
> 状态：**设计文档（文本级）**——GUI 实现放 S9（后端插件化全部完成后）
> 后端基线：**1264 passed / 17 skipped / 0 failed**（tag refactor-s8-test）
> 铁律：**yaml 是权威**，GUI 是编辑/执行入口（双通道）；所有后端访问经 PipelineController 薄层

---

## 1. 设计定位与用户（方案 §6.1）

| 项 | 说明 |
|----|------|
| 形态 | 桌面应用（PySide6）+ pipeline.yaml 双通道（yaml 权威，GUI 编辑/执行入口） |
| 用户 | 转换工程师：配置 pipeline → 预览插件链 → 执行转换 → 查看报告/手动干预 |
| 核心价值 | 所见即所得的"插件组合器"（对应 DeepSeek Harness 的 profile 管理 UI） |
| 视觉规范 | anthropic-style-frontend-cn（Poppins + Lora、有温度、差异化美学方向"工程工作台"） |

## 2. 页面结构与组件树（方案 §6.2 完整版）

```
主窗口（MainWindow）
├── ① 侧边栏（Sidebar）
│   ├── Profile 列表（ProfileList）
│   │   ├── 内置 profile（default/max-beauty/fast/match-only，只读徽标）
│   │   └── 自定义 profile（可删除）
│   ├── 转换历史（ConversionHistory）
│   └── 底部：版本信息 / verify 快捷入口
│
├── ② 配置编辑器（ConfigEditor，中央核心）
│   ├── Profile 工具栏（ProfileBar）
│   │   ├── Profile 下拉框（当前生效名）
│   │   ├── [新建] [复制] [重命名] [保存] [导入] [导出] [删除]
│   │   └── 查重反馈区（duplicate_of / diff 明细提示）
│   ├── 阶段标签页（StageTabs）—— 输入 | 匹配 | 手动干预 | 美化 | 输出 | 测试
│   │   └── 每页：插件清单（PluginList）
│   │       ├── 插件卡片（PluginCard）：勾选启用 + 拖拽排序 + 启停态视觉反馈
│   │       └── 参数表单（ParamForm）：来自插件参数 schema（get_plugin_schema）
│   │           ├── 布尔开关 / 数字输入 / 文本输入 / 下拉选择 / 列表编辑
│   │           └── 参数折叠（默认收起，启用插件展开）
│   └── yaml 预览/直接编辑（YamlEditor，双通道）
│       ├── 表单改动 → 实时同步 yaml
│       └── yaml 改动 → 刷新表单（防冲突校验）
│
├── ③ 转换执行区（ConversionRunner，底部）
│   ├── 运行按钮 + 6 阶段进度条（Diagnose→Parse→Scan→Match→Validate→Generate）
│   ├── 日志流（实时）
│   └── 阶段耗时统计
│
└── ④ 结果面板（ResultDock，可停靠）
    ├── 报告视图（ReportView）
    │   ├── aesthetic / ioport / mapping / error 标签页
    │   └── 报告内容渲染（文本/表格）
    ├── 手动匹配干预子面板（ManualMatchPanel，FR3）
    │   ├── 未匹配列表（get_unmatched）
    │   ├── 手动指定 hdl 库器件（set_manual_match）
    │   └── 强制 mock 开关（J/T/U/IC）
    └── 原理图预览子面板（SchematicPreview）
        └── 转换结果可视化（现有 schematic_view 增强）
```

## 3. 组件与接口（方案 §6.3 完整签名）

### 3.1 PipelineController（GUI ↔ 后端唯一接口）

```python
# cis2hdl/gui/controller.py —— 薄层，全部后端访问经此
class PipelineController:
    """GUI ↔ 后端（插件化）唯一接口。S9 实现。"""

    # ── Profile 管理（ProfileManager 薄封装）────────────
    def list_profiles(self) -> list[str]:
        """内置 + 自定义全部 profile 名（ProfileManager.list_profiles）。"""
    def load_profile(self, name: str) -> PipelineConfig:
        """解析为完整配置（ProfileManager.get：合并内置默认 + 增量）。"""
    def save_profile(self, name: str, cfg: PipelineConfig) -> None:
        """保存为当前 profile（ProfileManager.create：查重 + 原子写）。"""
    def delete_profile(self, name: str) -> None:
        """删除自定义 profile（内置禁删，ProfileManager.delete）。"""
    def export_profile(self, name: str, out_path: Path) -> Path:
        """导出为可分发的 .yaml（ProfileManager.export）。"""
    def import_profile(self, path: Path, rename_to: str | None = None) -> str:
        """导入他人配置（ProfileManager.import_file：校验链 + 冲突处理）。"""
    def check_duplicate(self, name: str, cfg: PipelineConfig) -> ProfileDiff | None:
        """查重：与已有 profile 比对（ProfileManager.diff_all）。"""

    # ── 插件清单与参数 schema ─────────────────────────
    def list_plugins(self, stage: str) -> list[PluginMeta]:
        """某阶段全部插件元信息（名称/描述/参数 schema/默认值）。"""
    def get_plugin_schema(self, name: str) -> dict:
        """插件参数 schema（驱动 ParamForm 表单生成）。"""

    # ── 转换执行 ──────────────────────────────────────
    def run_conversion(self, cfg: PipelineConfig,
                       cb: Callable[[str, float, str], None]) -> ConversionReport:
        """执行转换（进度回调 stage/pct/msg）。"""

    # ── 报告与手动干预 ────────────────────────────────
    def get_report(self, kind: str) -> str:
        """获取报告内容（aesthetic/ioport/mapping/error）。"""
    def get_unmatched(self) -> list[UnmatchedEntry]:
        """未匹配元件列表（FR3）。"""
    def set_manual_match(self, refdes: str, hdl: str | None,
                         force_mock: bool) -> None:
        """手动指定匹配 / 强制 mock（写回 yaml match.manual_overrides）。"""
```

### 3.2 组件职责表

| 组件 | 职责 | 数据源 |
|------|------|--------|
| ProfileList | profile 树（内置徽标/自定义可删） | list_profiles |
| ProfileBar | 新建/复制/重命名/保存/导入/导出 + 查重反馈 | ProfileManager 全接口 |
| StageTabs | 6 阶段标签页容器 | — |
| PluginCard | 插件勾选 + 拖拽排序（启停态视觉） | list_plugins |
| ParamForm | 参数表单（schema 驱动控件生成） | get_plugin_schema |
| YamlEditor | yaml 预览/直接编辑（双通道） | PipelineConfig.to_dict/from_dict |
| ConversionRunner | 运行 + 进度 + 日志 | run_conversion |
| ReportView | 报告渲染 | get_report |
| ManualMatchPanel | 未匹配干预（FR3） | get_unmatched / set_manual_match |
| SchematicPreview | 原理图预览 | 现有 schematic_view 增强 |

### 3.3 参数 schema → 表单控件映射

| schema 类型 | 控件 | 示例 |
|------------|------|------|
| bool | QCheckBox 开关 | overlap.resolve / text_layout.enabled |
| int | QSpinBox | max_passive_move / cluster_radius |
| float | QDoubleSpinBox | char_width_factor |
| str | QLineEdit | lib_name / mock_text_cmd |
| enum（str 限定） | QComboBox | routing.mode: p0/detour/edif_reuse |
| list[str] | QListWidget + 增删 | plugins / prefix_scope |
| dict | QTreeWidget（折叠） | manual_names / weights |

## 4. yaml 双通道映射（方案 §6.4）

| GUI 操作 | yaml 变化 |
|---------|----------|
| 勾选/拖拽插件 | `plugins.<stage>:[...]` 顺序 |
| 改参数表单 | `params.<plugin>.<key>` |
| 切换 profile | `profile: <name>` + 整段配置替换 |
| 手动匹配干预 | `match.manual_overrides:` 追加条目 |
| 保存 | 写回 pipeline.yaml（**原子写**：临时文件+rename） |

**双通道同步规则**：
- 表单改动 → 实时更新 yaml 预览（只读区高亮变更）
- yaml 直接编辑 → 校验合法后刷新表单（非法 → 红框提示不刷新）
- 冲突检测：表单与 yaml 不同步时保存 → 提示覆盖确认

## 5. Profile 自定义交互（方案 §3.8.1/3.8.2 完整）

### 场景 A（改预设）
选中 `default` → 插件自动全勾 → 用户勾掉/勾上新插件
→ 点「保存为当前 Profile」→ 覆盖 `default`（或另存为自定义名）。

### 场景 B（无预设自由组合）
不选任何 profile → 手动勾选插件清单
→ 点「＋ 用当前组合新建 Profile」→ 触发查重 → 通过后填名称/描述保存。

### 场景 C（导入）
点「导入」→ 选择他人 `.yaml` → 读取 `profile:` 段
→ 名称冲突提示重命名或覆盖 → 加入本地 profile 列表。

### 查重反馈展示（§3.8.2）

```
┌─ 查重结果 ─────────────────────────────────────┐
│ ⚠️ 插件组合与 max-beauty 完全相同，但参数不同   │
│    差异: beautify.wire_simplify.enabled        │
│          (旧 false → 新 true)                  │
│    [仍保存] [取消]                              │
└────────────────────────────────────────────────┘
# status: duplicate → 拒绝（提示 duplicate_of）
# status: conflict_name → 要求重命名/覆盖确认
# status: ok → 直接保存
```

## 6. 视觉方向（方案 §6.5 + anthropic-style-frontend-cn）

- **美学方向**："工程工作台"——克制的中性色 + 深色可停靠面板 + 清晰的层级引导
- **字体**：Poppins（UI）+ JetBrains Mono/等宽（yaml 预览区）
- **组件风格**：
  - 插件卡片：勾选/启停/参数折叠，选中态/禁用态/冲突警告三种视觉态
  - 阶段步骤条：6 步可视化（Diagnose→Parse→Scan→Match→Validate→Generate），当前步骤高亮
  - 配置差异视图：Profile 切换时新旧配置 diff 高亮（增/删/改）
- **Token 体系**：对齐现有 `cis2hdl/gui/colors.py`（Anthropic 暖米色基底）+ anthropic-style-frontend-cn 规范
- **信息密度**：高密度但呼吸感充足；插件启停有明确视觉反馈

## 7. 与后端 API 对齐说明（S9 实现依据）

| GUI 需要 | 后端已提供（S1-S8 落地） |
|---------|------------------------|
| Profile 增删改查 | ProfileManager（list/get/create 查重/delete/export/import_file/diff/diff_all） |
| 插件清单/schema | PluginManager.list_plugins / resolve_params（param_fields 驱动） |
| 配置读写 | PipelineConfig（from_yaml/to_dict/from_routing_config） |
| 转换执行 | ConversionEngine（set_pipeline/convert_with_cfg + 进度回调） |
| 报告 | write_report 插件输出（aesthetic/ioport/mapping/error） |
| 手动干预 | manual_overrides 插件（chip_config + power_ic） |
| 验证 | verify CLI（VerificationRunner） |

**S9 实现范围**：MainWindow + 上述组件 + PipelineController，全部经 yaml 双通道；
完成后 `python -m cis2hdl gui` 启动。
