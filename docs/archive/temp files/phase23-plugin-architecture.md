# CIS2HDL 插件化重构 — 完整需求规格与架构设计（v2）

> 文档：Phase XXIII（2026-08-14，v2 更新）｜ 撰写：齐活林（主理人）｜ 状态：**草案待确认**
> 性质：**只读规划文档** —— 本文件不修改任何代码；所有改动须经本设计评审通过后分阶段实施。
> 当前基线：git `b0dd63d`（Phase XXII 末，877 passed / 6 skipped / 0 failed，工作区干净）

---

## 〇、TL;DR（决策速览 v2）

| 项 | 决策 |
|----|------|
| 目标 | 插件化 Pipeline 架构：所有模块（输入/解析/匹配/美化/输出/测试）变为可独立启用的插件，Pipeline 主线一条代码，配置决定组合 |
| 灵感 | DeepSeek Harness（Cordis 插件元框架：一切皆插件、Profile 组合、可逆卸载） |
| **开发方式** | **新建独立文件夹 `cis2hdl_plugin_ver/`（项目根级，与 cis2hdl 平行）**——把现有代码读取复制到新文件夹中创建 plugin 版本；**现有 cis2hdl 代码零改动** |
| 插件框架 | **pluggy**（pytest 同款：hookspec/hookimpl、entry points、可卸载）；**写入 requirements.txt**（pyproject.toml 同步） |
| 配置载体 | **pipeline.yaml**（全量配置）+ **--profile** 切换（DeepSeek Harness 的 profile/bundle 理念） |
| GUI | **本轮不实现 GUI**。先产两份文档：①开发者文档（主线配置/参数/实现/接口 + 全插件全方位信息）②GUI 界面设计方案（完整重新设计编辑器，含接口定义）；GUI 实现放后端全部完成后 |
| 默认行为 | **默认 profile 与当前版本完全等价**（877 测试不回归）；新能力进新 profile 显式开启 |
| 重构范围 | 插件化改造为主 + **先扫后改**（vulture 死代码 + .bak + 重复块基线报告）+ **追踪清单**（REFACTORING_BACKLOG.md）防遗漏 |
| 执行节奏 | 本轮只出文档 → 评审确认 → 分阶段实施（每阶段 git tag）→ 每阶段全量测试 ≥877 |
| **CLI 兼容** | **旧 CLI 参数保留至 S10 再移除**（兼容窗口确认）；S1 起接受旧参数并映射为等价 yaml（deprecation 警告） |
| 前端规范 | GUI 页面按 anthropic-style-frontend-cn 风格规范开发（S9 实施时） |

---

## 一、背景与动机

### 1.1 现状（代码级实锤，2026-08-14 调查）

| 维度 | 现状 | 证据 |
|------|------|------|
| Pipeline 骨架 | 已有 6 阶段：Diagnose→Parse→Scan→Match→Validate→Generate | `conversion_engine.py` docstring |
| Registry | 存在 ParserRegistry/WriterRegistry/MatcherRegistry/ValidatorRegistry | 但**硬编码 import 全量注册**（`_bootstrap_parsers()` 模块级执行），无配置化选择、无插件接口、无卸载 |
| CLI | 参数散布 `__main__.py` 手工 sys.argv 解析（--routing/--aesthetic/--wire-simplify/--chip-config…） | 每种组合手敲长串，无 profile 复用 |
| GUI | PySide6 雏形存在（main_window/panels/dialogs） | 与配置未打通 |
| 冗余 | `.bak` 文件：`sch_writer.py.bak` / `config.py.bak` / `pipeline.py.bak`；历史死代码（如 resolve_passives 双重赋值 bug 曾在 Phase XXI 修复） | git 有历史，.bak 应删 |
| 规模 | 5.4 万行 Python | — |

### 1.2 痛点（用户原始诉求）

1. **消除冗余、重复、被迭代掉的代码**（.bak、死代码、重复实现）
2. **耦合度降至最小**（模块间隐式共享状态 → 显式契约）
3. **插件化**：所有模块/功能做成独立"工具"，可在转换 pipeline 中即插即用、按需选择
4. **Pipeline 主线一条代码**，通过配置组合插件，而不是代码分支

### 1.3 灵感来源：DeepSeek Harness（Cordis）

2026-08-13 DeepSeek 开源 Harness v0.1（MIT），核心是 Cordis 插件元框架：

| Cordis 概念 | 本项目映射 |
|------------|-----------|
| 一切皆插件（模型/工具/会话/沙箱/UI 均可替换） | 一切转换模块皆插件（解析/匹配/美化/输出/测试） |
| ctx 服务仓库（ctx.tools/ctx.llm/ctx.sessions 稳定键） | ctx 上下文对象（ctx.ir/ctx.routed_nets/ctx.report） |
| inject 依赖声明（依赖决定激活） | 插件声明 `requires_stage`（依赖哪个阶段产物） |
| 事件通信（observation/wrap/parallel/ordered） | hookspec 钩子链（ordered invocation） |
| 可逆注册（unload 清理监听/工具/副作用） | pluggy 卸载 + 插件 cleanup() |
| profile/bundle（有序插件栈 + 用户覆盖） | pipeline.yaml + --profile（默认/快速/极致美化） |

### 1.4 开发方式：独立文件夹 cis2hdl_plugin_ver（用户决策 1）

**核心原则：现有 cis2hdl 代码零改动。**

```
项目根/
├── cis2hdl/                  # 现有代码（不动，基线 b0dd63d 保持）
│   ├── cis2hdl/              # 包源码（5.4 万行）
│   ├── tests/                # 877 测试
│   └── docs/                 # 文档
│
└── cis2hdl_plugin_ver/       # 新建（插件版，本重构的开发战场）
    ├── cis2hdl/              # 复制现有包 → 插件化改造
    ├── tests/                # 复制现有测试 → 插件测试新增
    ├── plugins/              # 新增：插件目录（input/match/beautify/output/test）
    ├── pipeline.yaml         # 新增：插件配置（权威）
    ├── requirements.txt      # pluggy 等依赖（用户决策 2）
    └── docs/                 # 开发者文档 + GUI 设计方案（用户决策 4）
```

**工作流**：
1. **S0 基线**：`cp -r cis2hdl cis2hdl_plugin_ver`（保留 .git 或新建独立 git，待用户定）→ 立即跑 877 测试确认副本等价
2. 之后所有重构开发**只在 cis2hdl_plugin_ver 内进行**；cis2hdl 保持只读参考
3. 每阶段结束：插件版全量测试 + 与 cis2hdl 基线输出 diff（默认 profile 等价）
4. 验证成熟后再决定：插件版替代现有版（用户拍板）或长期双轨

**为什么这样做**：①重构风险完全隔离（现有可用版本永远可回退）②对比验证方便（两版本输出 diff 即等价性证明）③用户"不动现有代码"的强约束得到满足。

### 1.5 未开发内容清点（Phase XX/XXI/XXII 排期全量核查，2026-08-14 代码级）

**核查方法**：对 Phase XX/XXI/XXII 排期表逐项 grep 源码验证，不轻信文档记录。

| 编号 | 排期任务 | 状态 | 代码证据 | 未开发原因 |
|------|---------|:---:|---------|-----------|
| P0-1 | 三段式 stub 默认开 | ✅ 完成 | wire_layout 条件三段式（Phase XXII） | — |
| P0-2 | 避让默认开 | ✅ 完成 | WIRE_THROUGH_BODY 三口径（Phase XXII） | — |
| P0-3 | net_name_endpoints 接线 | ✅ 完成 | csa_writer use_net_name 单点（Phase XXII） | — |
| P0-4 | J/T/S 匹配修复（J4 强制 mock） | ✅ 完成 | config.py:645 `connector_pin_check: bool = True` | — |
| P0-5 | resolve_passives 默认开 | ✅ 完成 | config.py:384 `resolve: bool = True`（Phase XX 接线） | — |
| P0-6 | mock_all 全量模拟图标 | ✅ 完成 | 后端默认（Phase XX 追加） | — |
| P0-7 | OverlapResolver 接线 | ✅ 完成 | config.py overlap.resolve=true（Phase XX 追加） | — |
| P1-1 | 引脚标签布局 | ✅ 完成 | connectivity_model orient（Phase XI 已有+XX 补丁） | — |
| P1-2 | IO port 按网络聚类 | ✅ 完成 | `_build_ioport_cluster_order`（Phase XXII D5） | — |
| P1-5 | 并联扩展到所有信号 | ✅ 完成 | plan_parallel_short（Phase XXII D4） | — |
| P1-6 | wire simplify 阈值调优 | ✅ 完成 | config.py:519 `max_wire_len: int = 5000` + split_long_wires（Phase XVIII） | — |
| P1-7 | aes LASTPIN miss 归零 | ✅ 完成 | key 前置+同源+snap50（Phase XXII D8） | — |
| P2-1 | 542/545 属性提示抑制 | ✅ 完成 | 9 P 属性补全（Phase XXI P0-A） | — |
| P2-3 | 两套 xcon 合并 | ✅ 完成 | xcon_writer 唯一源（Phase XXII D6） | — |
| P2-4 | 标签文字方向随元件 | ✅ 完成 | text_layout（Phase XXII D7，默认关） | — |
| P2-6 | MOCK 颜色属性标签 | ✅ 完成 | T 字号 89 + PAINT PINK（Phase XXI P0-B） | — |
| **P1-3** | **GND 分布增强**（密度+避让+接入电路） | ✅ **完成**（Phase XXIII） | `ensure_gnd_symbols` 密度补点 + GND trunk 避让余量 + outlet 绕行；开关 `gnd.distribute_density`（默认关，--gnd-distribute） | 详见 phase23-incremental-design.md + QA 报告（真实补点 2 个，数据特性） |
| **P1-4** | **电阻/LB 旋转感知**（方向随连线） | ✅ **完成**（Phase XXIII） | `apply_passive_orientation`（R/L/FB/BEAD 随连线旋转 + outline swap）；开关 `placement.rotate_passives`（默认关，--rotate-passives）；一致率 100% | 详见 phase23-incremental-design.md + QA 报告 |
| **P2-2** | **origin 库补全**（entity/part_table/chips） | 🟡 **未开发** | hdl_lib 已有 entity/part_table（自包含）；"补全"= 更多真实库符号 | 待用户复测确认无 ORIGIN 报错后再决定（ROADMAP R-5）；输出包已自包含可开 |
| **P2-5 / R-6** | **GUI mock_all 面板**（复选框+手动选匹配） | 🟡 **未开发** | gui/panels 15 面板无 mock_all 控件（chip_config_panel 无 mock 逻辑） | 环境无 PySide6 依赖配置完善；**本重构 S9 重新设计**（见 §GUI 方案）——但用户决策：GUI 本轮不实现，先出文档 |
| **P0-4+ / R-3** | **AMS1117 真实符号**（hdl_lib） | 🟡 **未开发** | part.ptf 有 AMS1117-5.0 记录；但 ldo/symbols/ **无 AMS1117 实体符号**（现用 mock 图标 + pstchip 引脚名覆盖） | 需真实 SOT223 符号资源（外部素材）；现 mock+pstchip 已可读可用；依赖外部资源供给 |
| **R-2** | **violations=506 收敛**（trunk 级避让） | ✅ **完成**（Phase XXIII） | `_avoid_outlines` span 感知推离 + 冲突计数优先；**violations 506→457（trunk 穿体=0、trunk_blocked=0）**；WIRE 6492 不增反降；报告分项 trunk_blocked/non_trunk | 详见 phase23-incremental-design.md + QA 报告；剩余 457 为 stub 穿体（完整绕障属 detour） |
| **R-7** | 三段式折线避其他网段 | 🟡 部分 | busy_h/busy_v 已传三段式（跨网共线避让）；个别共线段未消 | 待 Cadence 目视发现后上报（增量增强） |
| R-1/R-8/R-5 | Cadence 复测 / Hotfix / ORIGIN 添加 | ⚪ 用户侧 | — | 依赖用户 Cadence 环境操作 |
| **P2-5（GUI 重设计）** | **完整 GUI 设计编辑器** | 🔴 **未开发** | 现有 GUI 15 面板为旧交互（项目/diagnostic/match_review/schematic 等），无插件清单/参数表单/配置编辑 | 用户决策：**本轮只出 GUI 设计方案文档，不实现**（见 §GUI 设计方案） |

**清点结论（v2，2026-08-14 三项开发后）**：Phase XX/XXI/XXII 排期表中，**功能性任务 16/16 已完成**；增强类 3 项（GND 分布增强、电阻旋转、trunk 避让）**已在 Phase XXIII 完成**（详见 phase23-incremental-design.md / phase23-qa-report.md，929 passed）；剩余 🟡 2 项（origin 库补全、AMS1117 真实符号）为"补全/资源类"，原因均为**依赖外部资源或用户复测反馈**；🔴 1 项 GUI 重设计为**本轮新规划**（用户决策先文档后实现）。无"漏开发的功能性缺陷"。

---

## 二、需求规格

### 2.1 功能需求（FR）

| 编号 | 需求 | 优先级 | 验收口径 |
|------|------|:---:|---------|
| FR1 | **输入插件化**：可选择 EDIF 解析、DSN 解析、CrossRef 载入、pstxnet/pstchip/pstxprt 载入等；可多文件组合 | P0 | 单输入插件可独立启用/禁用；多输入插件组合后数据正确合并 |
| FR2 | **匹配插件化**：元件匹配模块可配置权重参数、各 prefix（R/C/U/J/T/IC…）搜索范围 | P0 | match_config 权重/prefix 范围全进 yaml；不同配置产出不同匹配结果 |
| FR3 | **手动匹配干预**：手动匹配未 exact 匹配的元件 / 改选系统错误匹配 / 对 J/T/U/IC 选 mock 图标 | P0 | chip_config 已有雏形 → 插件化；GUI 可操作 |
| FR4 | **美化插件化**：防重叠、GND 聚类、并联优化、减少连接点、三段式 stub、电线化简等各为独立插件，可选 | P0 | 每美化功能独立插件；组合任意启停；默认 profile 行为=现状 |
| FR5 | **输出插件化**：可选择输出哪些文件（csa/con/xcon/csv/cpc/cpm/cds.lib）、哪些报告（aesthetic/ioport/mapping/error） | P0 | 输出插件独立启停；默认 profile 输出文件=现状 |
| FR6 | **测试插件化**：可选择执行哪些测试套件，确保功能有对应测试 | P1 | 测试插件（unit/e2e/qa 包检查）可选；每插件强制配测试 |
| FR7 | **Profile 机制**：多套预设（默认/快速/极致美化/仅匹配），--profile 一键切换 | P0 | 配置组合可命名保存复用；CLI/GUI 均支持 |
| FR8 | **配置全进 YAML**：权重、prefix、美化参数、输出选择全部 yaml；CLI 只留高频参数 | P0 | 旧 CLI 参数 → yaml 字段迁移对照表（见 §7） |
| FR9 | **默认行为等价**：默认 profile 转换结果与当前 b0dd63d 完全一致 | P0 | 877 测试断言不回归；对比包输出可 diff |
| FR10 | **GUI 文档先行 + 双通道（用户决策 4）**：本轮**不实现 GUI**；先产出 `gui-design.md`（完整重新设计编辑器方案：插件清单面板/参数表单/Profile 管理/手动匹配干预，含页面结构+组件+接口+数据流+yaml 映射）；后端全部完成后 S9 实现 | P1 | 后端完成前 GUI 设计文档评审通过；S9 实现后 GUI 保存 = 写 yaml；CLI 读 yaml = GUI 可见 |

### 2.2 非功能需求（NFR）

| 编号 | 需求 | 验收口径 |
|------|------|---------|
| NFR1 | 低耦合 | 模块间无隐式全局状态；只通过 ctx 显式传参；hookspec 签名校验 |
| NFR2 | 可维护性 | 每插件单文件可读；每插件有独立单测；接口文档齐全 |
| NFR3 | 稳定性 | 全量测试 ≥877 不回归；插件加载失败不阻塞整体（降级警告） |
| NFR4 | 可回退 | 每阶段 git tag；默认 profile 随时回退现状 |
| NFR5 | 去硬编码 | 所有魔数/阈值/权重进 yaml（含默认值），代码零硬编码 |
| NFR6 | 去冗余 | .bak 全删；死代码基线扫描+追踪清单；重复实现合并 |
| **NFR7** | **开发者文档实时撰写**（用户决策 4） | **每阶段开发的同时**实时更新 `cis2hdl_plugin_ver/docs/developer-guide.md`——完整记录主线所有配置/参数/实现/接口 + 所有插件全方位信息（名称/阶段/参数/依赖/输出/默认值/示例） |
| **NFR8** | **GUI 文档先行**（用户决策 4） | **后端开发前**先产出 `cis2hdl_plugin_ver/docs/gui-design.md`（完整 GUI 设计方案：页面结构/组件/接口/数据流/与 yaml 映射）；GUI 代码实现放后端全部完成后 |

---

## 三、架构设计

### 3.1 总体分层

```
┌─────────────────────────────────────────────────────────────┐
│                    Config 层（pipeline.yaml + --profile）    │
│  profile: default | fast | max-beauty | match-only          │
│  plugins: {input: [...], match: [...], beautify: [...],     │
│            output: [...], test: [...]}                      │
└──────────────┬──────────────────────────────────────────────┘
               │ 加载并校验
┌──────────────▼──────────────────────────────────────────────┐
│                PluginManager（pluggy）                       │
│  ① 注册内置插件（builtin 目录扫描）                           │
│  ② 按配置过滤启用（enabled_by_cfg）                          │
│  ③ hookspec 签名校验（写错参数启动即报错）                    │
│  ④ 顺序执行（tryfirst/trylast）                             │
└──────────────┬──────────────────────────────────────────────┘
               │ 触发各阶段钩子
┌──────────────▼──────────────────────────────────────────────┐
│               Pipeline 主线（ConversionEngine）              │
│  Stage1 diagnose ──► Stage2 parse ──► Stage3 scan           │
│       │                │                 │                  │
│       │                ▼                 ▼                  │
│       │           DesignIR          ComponentDB             │
│       │                │                 │                  │
│       ▼                ▼                 ▼                  │
│  Stage4 match ──► Stage5 validate ──► Stage6 generate       │
│  MatchResult         errors            output files+reports │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 ctx 上下文对象（插件间唯一通信通道）

```python
@dataclass
class ConversionContext:
    """插件间共享的上下文（稳定键，仿 Cordis ctx.*）。"""
    cfg: PipelineConfig          # 解析后的 yaml 配置
    profile: str                 # 当前 profile 名
    input_files: list[Path]      # FR1 多输入
    ir: DesignIR | None          # Stage2 产物
    hdl_db: ComponentDB | None   # Stage3 产物
    matches: list[MatchResult]   # Stage4 产物
    manual_overrides: dict       # FR3 手动匹配/强制 mock
    routed_nets: dict | None     # 美化阶段共享（仿现有 routed_nets）
    report: AestheticReport      # 报告聚合
    # 只读守卫：插件写入 ctx 需声明；防止插件互踩（防线 3）
    _locked: set[str] = field(default_factory=set)
```

### 3.3 插件接口规范（hookspec 定义）

```python
# cis2hdl/plugins/hookspecs.py
from pluggy import HookspecMarker

hookspec = HookspecMarker("cis2hdl")

class PipelineHooks:
    # ── FR1 输入解析 ─────────────────────────────
    @hookspec
    def load_input(self, ctx: ConversionContext) -> None:
        """载入并解析一种输入格式（EDIF/DSN/CrossRef/pstxnet…）。"""

    # ── FR2/FR3 元件匹配 ─────────────────────────
    @hookspec
    def match_components(self, ctx: ConversionContext) -> None:
        """对 ctx.ir 做元件匹配（exact/fuzzy/fallback…按优先级）。"""

    @hookspec
    def apply_manual_overrides(self, ctx: ConversionContext) -> None:
        """应用手动匹配/强制 mock（chip_config 插件化）。"""

    # ── FR4 布线美化（每美化功能一个插件）─────────
    @hookspec(firstresult=False)
    def beautify(self, ctx: ConversionContext) -> None:
        """美化钩子链：overlap_resolve/gnd_cluster/parallel_short/
        three_stage_stub/wire_simplify… 按 yaml 顺序执行。"""

    # ── FR5 输出 ────────────────────────────────
    @hookspec
    def write_output(self, ctx: ConversionContext) -> None:
        """写一种输出文件（csa/con/xcon/csv/cpc…）。"""

    @hookspec
    def write_report(self, ctx: ConversionContext) -> None:
        """写一种报告（aesthetic/ioport/mapping/error…）。"""

    # ── FR6 测试 ────────────────────────────────
    @hookspec
    def run_verification(self, ctx: ConversionContext) -> None:
        """执行一类验证/测试（unit/e2e/qa-package-check…）。"""
```

### 3.4 插件实现规范（示例）

```python
# cis2hdl/plugins/beautify/gnd_cluster.py
from pluggy import HookimplMarker
from ..hookspecs import ConversionContext

hookimpl = HookimplMarker("cis2hdl")

class GndClusterPlugin:
    name = "gnd_cluster"
    stage = "beautify"
    description = "GND 聚类：簇内先并联再统一引出（Phase XVII R3 迁移）"

    def __init__(self, dist: int = 500, enabled: bool = True):
        self._dist = dist
        self._enabled = enabled

    @hookimpl
    def beautify(self, ctx: ConversionContext) -> None:
        if not self._enabled:
            return
        # 从 ctx 读，写回 ctx（不碰其它插件私有状态）
        ctx.routed_nets = gnd_cluster(ctx.routed_nets, self._dist)

    def cleanup(self) -> None:  # 可逆注册（Cordis unload 理念）
        self._enabled = False
```

### 3.5 插件发现与注册

```python
# cis2hdl/plugins/manager.py
import pluggy
from .hookspecs import PipelineHooks

def build_plugin_manager(cfg: PipelineConfig) -> pluggy.PluginManager:
    pm = pluggy.PluginManager("cis2hdl")
    pm.add_hookspecs(PipelineHooks)
    # ① 扫描 builtin 插件目录（约定：plugins/<stage>/*.py）
    for plugin in scan_builtin_plugins():
        pm.register(plugin, name=plugin.name)
    # ② 按 cfg 过滤启用（enabled_by_cfg）
    # ③ 校验（pluggy 自动做 hookspec 签名校验）
    # ④ 配置插件参数（从 yaml 构造插件实例）
    return pm

# Pipeline 主线（ConversionEngine 改造）
def convert(ctx: ConversionContext) -> ConversionReport:
    pm = build_plugin_manager(ctx.cfg)
    pm.hook.load_input(ctx=ctx)              # 所有启用的输入插件
    pm.hook.match_components(ctx=ctx)        # 匹配插件链（优先级序）
    pm.hook.apply_manual_overrides(ctx=ctx)  # FR3 手动干预
    pm.hook.beautify(ctx=ctx)                # 美化钩子链（yaml 顺序）
    pm.hook.write_output(ctx=ctx)            # 输出插件
    pm.hook.write_report(ctx=ctx)            # 报告插件
    return ctx.report
```

### 3.6 pipeline.yaml 草案

```yaml
# pipeline.yaml — CIS2HDL 转换配置（权威）
profile: default            # default | fast | max-beauty | match-only

input:
  plugins:                  # FR1 多输入组合
    - edif                   # EDIF 解析（默认）
    # - dsn                  # DSN 解析（可选）
    # - cross_ref           # CrossRef CSV（提高转换质量）
    - pstxnet                # pstxnet 网络注入（默认）
    - pstchip                # pstchip 引脚名恢复（默认）

match:                      # FR2 匹配权重/prefix 范围
  plugins: [exact, fuzzy, passive, fallback]
  weights:                  # 全进 yaml（NFR5 去硬编码）
    part_name: 0.5
    footprint: 0.3
    value: 0.2
    jedec_type: 0.1
  prefix_scope:             # 各 prefix 搜索范围
    R:  [0603, 0402, 0805]
    C:  [0603, 0402, 0805]
    U:  [sot223, qfp, bga]
    J:  [connector]
    IC: [any]
  mock:                     # FR3 强制 mock 的 prefix
    prefixes: [J, T]
    auto_icon: true         # J/T/U/IC 用模拟图标

beautify:                   # FR4 美化插件（按顺序执行）
  plugins:
    - overlap_resolve       # 防重叠（默认）
    - gnd_cluster           # GND 聚类（默认）
    - parallel_short        # 并联优化（默认）
    # - wire_simplify       # 电线化简（默认关，--wire-simplify 时代）
  params:
    overlap:  { max_passive_move: 200 }
    gnd:     { cluster_radius: 500 }
    parallel:{ short_dist: 500 }

output:                     # FR5 输出选择
  files:    [csa, con, xcon, csv, cpc, cpm, cds_lib]
  reports:  [aesthetic, ioport, mapping, error]

test:                       # FR6 测试选择
  suites: [unit, e2e, qa_package]
```

### 3.7 Profile 预设

| profile | 说明 | 插件组合 |
|---------|------|---------|
| `default` | 与当前 b0dd63d 行为完全等价（FR9） | input: edif+pstxnet+pstchip；match 全链；beautify: overlap+gnd+parallel；output 全文件 |
| `fast` | 快速转换（跳诊断/少报告） | 同上但 report 只 error；test 跳过 |
| `max-beauty` | 极致美化 | default + wire_simplify + three_stage_stub 全开 + text_layout |
| `match-only` | 只做匹配导出 | 只跑到 Stage4 + 输出 mapping 报告 |
| `debug` | 全插件 + 全报告 + 全测试 | 诊断全开 |

### 3.8 Profile 自定义 / 查重 / 导入导出（用户决策 10，2026-08-14 追加）

> 预设 profile 只是起点，用户必须能**基于当前插件组合自定义保存新 profile**、
> **与已有 profile 查重**、**导入他人配置文件**。本节为完整功能规格（**仍不开发**，
> 由 S9 GUI 阶段实现；后端 ProfileManager 在 S1/S2 落地）。

#### 3.8.1 交互流程（GUI 场景）

```
┌────────────────────────────────────────────────────────────┐
│ GUI 主窗口 · 配置编辑器                                        │
│                                                              │
│  [Profile 下拉框] ▼ default           [新建] [复制] [导入]     │
│                                                              │
│  阶段标签页:  输入 | 匹配 | 手动干预 | 美化 | 输出 | 测试       │
│  ┌─ 美化 页 ─────────────────────────────────────────────┐  │
│  │  ☑ overlap_resolve    参数折叠表单                      │  │
│  │  ☑ gnd_cluster                                        │  │
│  │  ☑ parallel_short                                     │  │
│  │  ☐ wire_simplify      ← 用户新勾选（与 default 不同）    │  │
│  │  ☐ three_stage_stub   ← 用户新勾选                      │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  [💾 保存为当前 Profile]  [＋ 用当前组合新建 Profile]          │
└────────────────────────────────────────────────────────────┘
```

**场景 A（改预设）**：选中 `default` → 插件自动全勾 → 用户勾掉/勾上新插件
→ 点「保存为当前 Profile」→ 覆盖 `default`（或另存为自定义名）。

**场景 B（无预设自由组合）**：不选任何 profile → 手动勾选插件清单
→ 点「＋ 用当前组合新建 Profile」→ 触发查重 → 通过后填名称/描述保存。

**场景 C（导入）**：点「导入」→ 选择他人 `.yaml` 配置文件 → 读取其中
`profile:` 段 → 若名称冲突提示重命名或覆盖 → 加入本地 profile 列表。

#### 3.8.2 查重规则（新建/保存时强制）

| 维度 | 规则 |
|------|------|
| **插件组合等价** | 新组合与已有 profile 的 `plugins.<stage>:[...]` **逐阶段逐项比较**（顺序无关，set 比较）——完全相同则判重 |
| **参数等价** | 插件组合相同**且** `params.<plugin>.<key>` 全等 → 判重（提示"与 XX 完全相同"） |
| **组合同、参数异** | 允许保存（参数不同=不同配置），提示"插件组合与 XX 相同但参数不同" |
| **名称冲突** | profile 名称已存在 → 拒绝或要求覆盖确认（不静默覆盖） |
| **大小写/空白** | 名称比较前 trim + 忽略大小写；插件名/参数 key 严格区分大小写 |

**查重结果反馈**：
```yaml
# 判重响应（GUI 提示）
profile_check:
  status: duplicate | conflict_name | ok
  duplicate_of: "max-beauty"      # status=duplicate 时指出
  diff: {stage: "beautify", added: [wire_simplify], removed: []}  # 差异明细
```

#### 3.8.3 自定义 Profile 存储（独立配置文件）

**存储位置**：`cis2hdl_plugin_ver/profiles/` 目录（**独立于 pipeline.yaml**，
用户自定义 profile 不混入主配置）：

```
cis2hdl_plugin_ver/
├── pipeline.yaml          # 主配置（内置 profile 引用 + 当前生效 profile 名）
└── profiles/
    ├── default.yaml       # 内置预设（只读，禁止覆盖）
    ├── max-beauty.yaml    # 内置预设
    └── my-power-design.yaml  # 用户自定义（GUI 保存生成）
```

**自定义 profile 文件格式**（与 pipeline.yaml 的 profile 段同构，可独立分发）：
```yaml
# profiles/my-power-design.yaml
profile:
  name: my-power-design
  description: "电源板专属：全美化 + 网络名标签"
  created: 2026-08-14
  plugins:            # 完整插件组合（快照，不引用其他 profile）
    input:   [edif, pstxnet, pstchip]
    match:   [exact, fuzzy, passive, fallback, power_ic]
    beautify:[overlap_resolve, gnd_cluster, parallel_short, wire_simplify, text_layout]
    output:  [csa, con, xcon, csv, cpc, cpm, cds_lib]
    test:    [unit, e2e]
  params:             # 仅存与默认值不同的参数（增量）
    gnd:      { cluster_radius: 700 }
    parallel: { short_dist: 400 }
    text_layout: { enabled: true }
```

**后端 ProfileManager 接口**（S1 落地，GUI 经 PipelineController 调用）：
```python
class ProfileManager:
    """自定义 profile 的增删改查 + 查重 + 导入导出。"""
    def list_profiles(self) -> list[str]           # 内置 + 自定义
    def get(self, name: str) -> PipelineConfig     # 解析为完整配置（合并内置默认）
    def create(self, name: str, cfg: PipelineConfig, overwrite: bool = False) -> None
        # ① 名称校验（trim/大小写/非法字符）
        # ② 查重：插件组合+参数 与已有 profile 比对（§3.8.2）
        # ③ 写入 profiles/<name>.yaml（原子写：临时文件+rename）
    def delete(self, name: str) -> None            # 内置 profile 禁止删除
    def export(self, name: str) -> Path            # 导出为可分发的 .yaml
    def import_file(self, path: Path, rename_to: str | None = None) -> None
        # ① 读取 yaml 校验结构（必填 name/plugins）
        # ② 名称冲突 → rename_to 或拒绝
        # ③ 复制到 profiles/ 目录
    def diff(self, a: PipelineConfig, b: PipelineConfig) -> ProfileDiff
        # 查重核心：插件组合 set 比较 + 参数深度比较（§3.8.2）
```

**ProfileDiff**（查重/差异展示的数据结构）：
```python
@dataclass
class ProfileDiff:
    stage: str                       # 差异所在阶段（beautify 等）
    added: list[str]                 # 新组合多出的插件
    removed: list[str]               # 新组合缺少的插件
    param_diffs: dict[str, dict]     # {plugin: {key: (旧值, 新值)}}
    equivalent: bool                 # True = 插件组合+参数全等（判重）
```

#### 3.8.4 导入校验与安全

| 项 | 规则 |
|----|------|
| 结构校验 | 必填 `profile.name`（字符串）+ `profile.plugins`（dict，至少 1 阶段非空）；未知字段忽略 |
| 插件白名单 | 引用的插件名必须 ∈ 已注册插件（`PluginManager.list_plugins()`）——未知插件 → 导入失败并列出 |
| 参数类型 | params 值类型与插件参数 schema 比对（int/bool/str）——类型错误警告 |
| 路径安全 | 导入路径仅允许读取（不执行）；profile 文件内禁止路径/命令字段（防御性） |
| 版本兼容 | 文件头建议写 `schema_version: 1`；低版本兼容读取（缺失字段用默认值） |

#### 3.8.5 CLI 支持（后端先行，GUI 未实现时可用）

```bash
python -m cis2hdl profile list                          # 列出所有 profile
python -m cis2hdl profile show <name>                   # 显示完整配置
python -m cis2hdl profile create <name> --from-args ... # 从 CLI 参数组合新建（查重）
python -m cis2hdl profile delete <name>                 # 删除自定义（内置禁删）
python -m cis2hdl profile export <name> -o out.yaml     # 导出
python -m cis2hdl profile import <path> [--rename NAME] # 导入（查重/冲突处理）
python -m cis2hdl convert --profile <name>              # 用自定义 profile 转换
```

#### 3.8.6 与现有功能的衔接

| 衔接点 | 说明 |
|--------|------|
| `--profile` 解析 | S1 起 CLI `--profile` 支持自定义名（内置+自定义统一查 ProfileManager） |
| pipeline.yaml `profile:` 字段 | 记录"当前生效 profile 名"；用户自定义 profile 存 profiles/ 目录 |
| GUI PipelineController | `list_profiles/load_profile/save_profile` 扩展为 ProfileManager 薄封装 |
| 默认行为等价 | 内置 `default` 不可覆盖（只读），FR9 铁律不受影响 |
| 旧 CLI 参数 | 用户可用 `--profile my-x` 代替一长串参数（§7 迁移表补充说明） |

---

## 四、冗余清理计划（NFR6）

### 4.1 先扫后改（基线扫描）

| 扫描项 | 工具/方法 | 产出 |
|--------|----------|------|
| 死代码 | `vulture cis2hdl/` | 未使用函数/类/变量清单 |
| 备份文件 | `find . -name "*.bak" -o -name "*.orig" -o -name "*.rej"` | 已知：sch_writer.py.bak / config.py.bak / pipeline.py.bak |
| 重复实现 | 相似代码检测（如 `simian`/手动 grep 同名函数） | 已知：历史两套 xcon（已合并）需复核是否还有残留 |
| 未使用依赖 | `pipdeptree` + import 扫描 | 可移除依赖清单 |
| TODO/FIXME | grep | 遗留标记汇总 |

**产出**：`docs/archive/temp files/refactoring-baseline.md`（存入 git，重构后再扫对比增量）

### 4.2 追踪清单

**文件**：`docs/archive/temp files/REFACTORING_BACKLOG.md`
**格式**：

```markdown
| # | 文件:行 | 问题类型 | 处理方式 | 状态 |
|---|--------|---------|---------|:---:|
| 1 | cis2hdl/core/writer/sch_writer.py.bak | 备份冗余 | 删除（git 有历史） | ✅ |
| 2 | cis2hdl/core/matcher/pipeline.py.bak | 备份冗余 | 删除 | ✅ |
| 3 | … | 死代码 | 确认无引用后删 | 🟡 |
```

---

## 五、迁移计划（分阶段，每阶段 git tag + 全量测试 ≥877）

> 原则（FR9）：**每阶段结束，默认 profile 行为与上一阶段完全等价**。
> 开发环境：**仅 cis2hdl_plugin_ver 内开发**（§1.4）；cis2hdl 保持只读基线。
> 文档原则（NFR7）：**每阶段开发的同时实时更新 developer-guide.md**（主线配置/参数/实现/接口 + 全插件信息）。

| 阶段 | 内容 | 涉及 | 风险 | git tag |
|------|------|------|:---:|---------|
| **S0 基线** | `cp -r cis2hdl cis2hdl_plugin_ver` → 副本跑 877 测试确认等价；打基线 tag + 冗余基线扫描报告 + 建立 REFACTORING_BACKLOG.md | 复制/只读 | 低 | `refactor-s0-baseline` |
| **S1 配置层** | 引入 pipeline.yaml + PipelineConfig dataclass（全量参数从 routing.yaml/CLI 迁移）；CLI 解析改为读 yaml（**旧 CLI 参数保留至 S10**，映射等价 yaml + deprecation 警告）；旧 CLI 参数→yaml 迁移对照表 | config.py / __main__.py | 中 | `refactor-s1-config` |
| **S2 插件基座** | requirements.txt 加 pluggy；hookspecs.py + PluginManager + ctx 上下文；ConversionEngine 6 阶段改为钩子调用（内置插件 = 现有模块包装，行为不变） | plugins/ 新目录 / conversion_engine.py | 高 | `refactor-s2-base` |
| **S3 输入插件化** | EDIF/DSN/CrossRef/pstxnet/pstchip 包装为输入插件 | parser/ → plugins/input/ | 中 | `refactor-s3-input` |
| **S4 匹配插件化** | exact/fuzzy/passive/fallback + manual_overrides（chip_config 迁移）插件化；权重/prefix 全进 yaml | matcher/ → plugins/match/ | 中 | `refactor-s4-match` |
| **S5 美化插件化** | overlap_resolve/gnd_cluster/parallel_short/three_stage_stub/wire_simplify/text_layout 各成独立插件；美化钩子链按 yaml 顺序 | writer/ 美化类 → plugins/beautify/ | 高 | `refactor-s5-beautify` |
| **S6 输出插件化** | csa/con/xcon/csv/cpc/cpm/cds_lib/report 各成输出插件 | writer/ → plugins/output/ | 中 | `refactor-s6-output` |
| **S7 清理落地** | 删 .bak、删死代码（按基线报告+追踪清单）、合并重复实现；默认 profile 等价回归 | 全仓（plugin_ver 内） | 中 | `refactor-s7-clean` |
| **S8 测试插件化** | unit/e2e/qa-package 包装为测试插件；每插件补独立单测（FR6/NFR2） | tests/ → plugins/test/ | 低 | `refactor-s8-test` |
| **S8.5 开发者文档 + GUI 设计文档** | 汇总 developer-guide.md（全插件全方位信息）+ **gui-design.md（完整重新设计编辑器：页面/组件/接口/数据流/yaml 映射）** —— 按 anthropic-style-frontend-cn 规范定义视觉方向 | docs/ | 低 | `refactor-s85-docs` |
| **S9 GUI 实现** | 按 gui-design.md 实现 PySide6 面板（插件清单/参数表单/Profile 管理/手动匹配干预）读写 pipeline.yaml（双通道 FR10） | gui/ | 中 | `refactor-s9-gui` |
| **S10 交付** | 全量测试 + 默认 profile 等价 diff + 对比包重建（新目录）+ **移除旧 CLI 参数**（兼容窗口结束）+ 文档收尾 | 全仓（plugin_ver 内） | 低 | `refactor-s10-done` |

---

## 六、GUI 界面设计方案（文档先行，用户决策 4）

> **本轮不实现 GUI**。以下为 `gui-design.md` 的**框架大纲**（S8.5 产出完整版）。
> 目标：**完整重新设计编辑器**（非修补现有 15 面板），后端全部完成后 S9 按此实现。
> 视觉规范：anthropic-style-frontend-cn（Poppins+Lora、有温度、差异化美学方向）。

### 6.1 GUI 定位

| 项 | 说明 |
|----|------|
| 形态 | 桌面应用（PySide6）+ pipeline.yaml 双通道（yaml 是权威，GUI 是编辑/执行入口） |
| 用户 | 转换工程师：配置 pipeline → 预览插件链 → 执行转换 → 查看报告/手动干预 |
| 核心价值 | 所见即所得的"插件组合器"（对应 DeepSeek Harness 的 profile 管理 UI） |

### 6.2 页面结构（文本级框架）

```
主窗口
├── ① 侧边栏（导航）        — Profile 列表 + 转换历史
├── ② 配置编辑器（中央）     — 插件化 pipeline 编辑（核心）
│   ├── Profile 工具栏       — 新建/复制/重命名/保存/切换 profile
│   ├── 阶段标签页           — 输入 | 匹配 | 手动干预 | 美化 | 输出 | 测试
│   │   └── 每页：插件清单（勾选+顺序拖拽）+ 参数表单（来自 yaml schema）
│   └── yaml 预览/直接编辑   — 双通道：表单改动实时同步 yaml，yaml 改动刷新表单
├── ③ 转换执行区（底部）     — 运行按钮 + 进度条（6 阶段）+ 日志流
└── ④ 结果面板（可停靠）     — 报告视图（aesthetic/ioport/mapping/error）
    ├── 手动匹配干预子面板    — FR3：未匹配列表 → 手动指定/强制 mock（写回 yaml）
    └── 原理图预览子面板      — 转换结果可视化（现有 schematic_view 增强）
```

### 6.3 关键组件与接口（框架）

```python
# GUI 与后端（插件化）的边界 —— 全部经 PipelineController（薄层）访问后端
class PipelineController:
    """GUI ↔ 后端唯一接口（供 gui-design.md 详化）。"""
    def list_profiles(self) -> list[str]
    def load_profile(self, name: str) -> PipelineConfig
    def save_profile(self, name: str, cfg: PipelineConfig) -> None
    def list_plugins(self, stage: str) -> list[PluginMeta]     # 名称/描述/参数 schema/默认
    def get_plugin_schema(self, name: str) -> dict             # 参数表单驱动
    def run_conversion(self, cfg: PipelineConfig, cb: Callable[[Stage, int], None])
    def get_report(self, kind: str) -> str                     # aesthetic/ioport/...
    def get_unmatched(self) -> list[UnmatchedEntry]            # FR3
    def set_manual_match(self, refdes: str, hdl: str | None, force_mock: bool)
```

### 6.4 yaml 映射（双通道核心）

| GUI 操作 | yaml 变化 |
|---------|----------|
| 勾选/拖拽插件 | `plugins.<stage>:[...]` 顺序 |
| 改参数表单 | `params.<plugin>.<key>` |
| 切换 profile | `profile: <name>` + 整段配置替换 |
| 手动匹配干预 | `match.manual_overrides:` 追加条目 |
| 保存 | 写回 pipeline.yaml（原子写：临时文件+rename） |

### 6.5 视觉方向（anthropic-style-frontend-cn 规范）

- 美学方向：**"工程工作台"**——克制的中性色 + 深色可停靠面板 + 清晰的层级引导
- 字体：Poppins（UI）+ 等宽字体（yaml 预览区）
- 组件：插件卡片（勾选/启停/参数折叠）、阶段步骤条（6 步可视化）、配置差异视图
- 原则：信息密度高但呼吸感充足；插件启停有明确视觉反馈（选中态/禁用态/冲突警告）

---

## 七、旧 CLI 参数 → yaml 迁移对照表（FR8）

| 旧 CLI | 新 yaml 位置 | 说明 |
|--------|-------------|------|
| `--routing p0|detour` | `beautify.params.routing.mode` | p0→default；detour→max-beauty 预设 |
| `--aesthetic` | `profile: max-beauty` 或 `beautify.plugins: [all]` | 语义=全美化 |
| `--wire-simplify` | `beautify.plugins: [..., wire_simplify]` | 并入美化钩子链 |
| `--gnd-distribute` | `beautify.plugins: [..., gnd_cluster]` | GND 聚类插件 |
| `--use-net-name` | `output.reports: [..., net_name]` + net 配置 | 网络名标签 |
| `--text-layout` | `beautify.plugins: [..., text_layout]` | 标签方向 |
| `--chip-config` | `match.manual_overrides.file` | FR3 手动匹配 |
| `--manual-matches` | 同上（别名保留） | 兼容 |
| `--power-ic` | `match.plugins: [..., power_ic]` | 电源 IC 规则 |
| `--hdl-lib / --extra-hdl-lib` | `input.hdl_libs: [lib1, lib2]` | 库路径 |
| `--max-workers` | `engine.max_workers` | 并行度 |
| `--benchmark` | `output.reports: [..., benchmark]` | 基准报告 |
| `--nonuniform-tracks` | `beautify.params.tracks.nonuniform` | 轨道 |

**兼容策略**：S1 阶段 CLI 解析仍接受旧参数并映射为等价 yaml（打印 deprecation 警告），S10 后移除（文档说明）。

---

## 八、测试策略（NFR3）

| 层 | 覆盖 | 工具 |
|----|------|------|
| 单插件测试 | 每插件独立输入→输出（S5 起新增 `tests/plugins/` 目录，每插件 ≥2 用例） | pytest |
| 组合测试 | 2-3 插件组合不冲突（如 gnd_cluster+parallel_short 顺序） | pytest |
| 配置等价测试 | 默认 profile 输出 vs b0dd63d 输出 **字节级 diff**（新机制专用） | pytest + diff |
| 全量回归 | 现有 877 测试（每阶段必须全绿） | pytest |
| CLI/GUI 双通道 | yaml 写→CLI 读→结果一致；GUI 存→yaml 一致 | pytest + 手动 |

**关键断言**：S2-S7 每阶段结束，跑 `tests/` 全量 + 默认 profile 对比包 diff（用 `output_phaseXXV_compare` 等新目录，沿用递增约定）。

---

## 九、风险与应对

| 风险 | 等级 | 应对 |
|------|:---:|------|
| S2 基座改造影响全部 6 阶段 | 高 | 内置插件=现有模块薄包装（不重写逻辑）；默认等价 diff 守门 |
| 美化钩子链顺序导致行为变化 | 高 | yaml 显式顺序 + 组合测试 + 默认等价 diff |
| 现有 877 测试引用内部 API（非插件接口） | 中 | 插件保留兼容方法（薄包装），测试先不动，S8 再迁 |
| pluggy 引入依赖风险 | 低 | pluggy 零传递依赖，pytest 已用它（环境已有） |
| 手动匹配/GUI 与插件化冲突 | 中 | chip_config 保留为 match 阶段一个插件；GUI 只读写 yaml |
| 清理误删仍在用的代码 | 中 | 基线报告+追踪清单+git 可回退；删除前 grep 引用确认 |

---

## 十、交付物清单

| 交付物 | 位置 | 状态 |
|--------|------|:---:|
| 本设计文档 | `docs/archive/temp files/phase23-plugin-architecture.md` | ✅ 本轮产出（v2） |
| **未开发内容清点** | 本 §1.5（代码级核查 22 项） | ✅ 本轮产出 |
| **插件版目录** | `cis2hdl_plugin_ver/`（复制现有代码） | 🟡 S0 创建 |
| 冗余基线扫描报告 | `cis2hdl_plugin_ver/docs/refactoring-baseline.md` | 🟡 S0 产出 |
| 追踪清单 | `cis2hdl_plugin_ver/docs/REFACTORING_BACKLOG.md` | 🟡 S0 建立 |
| pipeline.yaml 完整示例 | `cis2hdl_plugin_ver/pipeline.example.yaml` | 🟡 评审后补全 |
| **开发者文档（实时撰写）** | `cis2hdl_plugin_ver/docs/developer-guide.md`（主线配置/参数/实现/接口 + 全插件全方位信息） | 🟡 每阶段实时更新（NFR7） |
| **GUI 设计文档** | `cis2hdl_plugin_ver/docs/gui-design.md`（完整重新设计编辑器方案，框架见 §6；**含 Profile 自定义/查重/导入导出 §3.8**） | 🟡 S8.5 产出 |
| **Profile 管理后端** | `cis2hdl_plugin_ver/profiles/` 目录 + ProfileManager（查重/导入导出，§3.8） | 🟡 S1 产出 |
| 插件接口文档 | `cis2hdl_plugin_ver/docs/plugin-api.md` | 🟡 S2 产出 |
| 迁移对照表 | 本 §7 | ✅ 已含 |
| 前端 GUI 规范 | 按 anthropic-style-frontend-cn skill | 🟡 S9 引用 |

---

## 十一、决策确认记录（v2 更新）

### 10.1 已确认（用户本轮拍板）

| # | 决策 | 落实章节 |
|---|------|---------|
| 1 | **独立文件夹 cis2hdl_plugin_ver**：复制现有代码到新文件夹开发插件版，现有代码零改动 | §1.4、§5 |
| 2 | **pluggy 引入**：写入 requirements.txt（pyproject.toml 同步） | §3.5、§5 S2 |
| 3 | **旧 CLI 参数保留至 S10** 再移除（兼容窗口） | §5 S1/S10 |
| 4 | **GUI 本轮不实现**：先实时撰写开发者文档（developer-guide.md）+ 完整 GUI 界面设计方案（gui-design.md，完整重新设计编辑器含接口）；GUI 实现放后端全部完成后（S9） | §2.2 NFR7/NFR8、§5 S8.5/S9 |
| 5 | 插件框架 pluggy / 配置全进 yaml+profile / 默认行为等价 / 插件化+基线扫描+追踪清单 | 全文档 |
| 6 | **独立 git 仓库存储 plugin 版**（用户已建，S0 时确认路径） | §1.4 |
| 7 | **复制范围含 tests/fixtures**（测试等价需要） | §1.4 |
| 8 | **GUI 设计文档用文本级**（页面结构+组件树+接口签名，不画 mockup） | §6 |
| 9 | **先完成三项未开发任务再开发 plugin 版**（Phase XXIII：P1-3/P1-4/R-2 已在现有仓库完成，929 passed） | §1.5 |
| 10 | **Profile 自定义/查重/导入导出**：GUI 选 profile 自动勾选插件 → 用户改勾选 → 新建 profile（查重防重复 + 填名称）→ 存 profiles/ 独立目录；支持导入他人配置文件 | §3.8 |

### 10.2 仍需用户确认

1. **cis2hdl_plugin_ver 的 git 策略**：复制时保留独立 git 仓库（推荐，可独立 tag/回退），还是并入现有仓库作为子目录（统一历史）？
2. **S0-S10 阶段划分**（含新增 S8.5 文档阶段）是否合理？
3. **复制范围**：cis2hdl_plugin_ver 是否包含 tests/fixtures（hdl_lib/HG5015 测试数据）？建议包含（测试等价需要）。
4. **GUI 设计文档范围**：`gui-design.md` 的详细度——包含 mockup 级别的页面草图（文本描述）即可，还是需要像素级原型？建议：文本级页面结构 + 组件树 + 接口签名 + 数据流（不画图）。

---

## 附：参考资料（资料收集结论）

| 来源 | 要点 | 引用到本设计 |
|------|------|-------------|
| DeepSeek Harness v0.1 发布（2026-08-13，MIT） | 一切皆插件；ctx 服务仓库；可逆注册；profile/bundle | §1.3、§3.2、§3.4 |
| Cordis 插件元框架 | inject 依赖声明；事件通信；卸载清理 | §1.3、§3.4 cleanup() |
| pluggy（pytest/tox 同款） | hookspec/hookimpl；entry points；签名校验；tryfirst/trylast | §3.3、§3.5 |
| Kedro（数据 pipeline 框架） | hooks 生命周期注入 | §3.5 钩子链模式 |
| 本项目现有架构 | 6 阶段 + Registry 机制 | §1.1、§3.1 |
| 本项目排期记录 | Phase XX/XXI/XXII 未开发清点 | §1.5 |
