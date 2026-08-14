# CIS2HDL 软件开发 SOP（标准操作流程）

> 版本: v1.1 | 日期: 2026-07-29 | 状态: 生效 | 更新: 增加强制架构设计、CHANGELOG更新、前后端配套、回归测试要求

---

## 1. 总则

### 1.1 目的

确保 CIS2HDL 项目的所有功能开发、测试、Bug 修复、代码审查和版本发布等环节遵循统一的标准化流程，保证代码质量和项目可持续性。

### 1.2 适用范围

- 所有项目成员（开发、测试、文档维护）
- 所有代码变更（新功能、修复、重构、文档更新）

### 1.3 核心理念

- **一个功能一个分支** — 避免多个功能混合
- **先写测试再写代码** — TDD（测试驱动开发）
- **不通过审查不合并** — 所有 PR 必须经过 Code Review
- **先设计后开发** — **每一次**开发都必须包含架构设计部分
- **前后端配套开发** — 后端功能实现必须同步配套前端交互，禁止单端先行
- **每次变更必更新文档** — CHANGELOG 和关联设计文档随代码同步提交

### 1.4 强制纪律（违反即退回）

| 纪律 | 要求 | 检查方式 |
|------|------|---------|
| **架构设计** | 每次开发（含 Bug 修复）必须评估是否需要更新 `design/` 文档 | PR Review 时检查 |
| **CHANGELOG** | 每次 PR 合并必须更新 `CHANGELOG.md` 相应条目 | PR 模板 Checkbox 强制勾选 |
| **前后端配套** | 后端 API 变更必须同步更新前端调用代码 | PR Review 时检查 |
| **回归测试** | 每次 Bug 修复后必须新增回归测试，确保同样 Bug 不再出现 | CI 统计测试数量 |
| **文档同步** | 接口变更、新增模块、配置变更必须同步更新对应文档 | PR Review 检查清单 |

---

## 2. 开发流程

### 2.1 功能开发全流程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 1. Issue │───▶│ 2. Branch│───▶│ 3. Design│───▶│ 4. Code  │───▶│ 5. Test  │
│  创建    │    │  创建    │    │  与实现  │    │  开发    │    │  与审查  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                                    │
                                                                    ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│10. Release│◀──│ 9. Merge │◀──│ 8. Review│◀──│ 7. Doc   │◀──│ 6. PR    │
│  发布     │    │  合并    │    │  Code    │    │  更新    │    │  提交    │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### 2.2 各步骤详细说明

#### Step 1: Issue 创建

```markdown
标题格式: [类型] 简短描述
类型: Feature / Bug / Refactor / Docs / Chore

内容必须包含:
- 背景/动机
- 具体需求描述
- 验收标准（Acceptance Criteria）
- 关联的 Phase/版本号
- 指派人 + 标签
```

**示例**：
```
[Feature] 实现 ExactMatcher 精确匹配器
- 背景: Phase II 匹配管道的第一阶段
- 需求: 通过 Footprint + Value + PinCount 指纹哈希进行精确匹配
- 验收标准:
  1. 相同指纹的器件匹配置信度 = 1.0
  2. 不同指纹的器件返回 no_match
  3. 单元测试覆盖率 > 90%
```

#### Step 2: Branch 创建

```bash
# 分支命名规范
feature/<issue-id>-<简短描述>     # 新功能
bugfix/<issue-id>-<简短描述>       # Bug 修复
refactor/<issue-id>-<简短描述>     # 重构
docs/<issue-id>-<简短描述>         # 文档

# 示例
git checkout -b feature/12-exact-matcher
git checkout -b bugfix/23-fix-pin-mapping-offset
```

**规则**：
- 从最新的 `main` 或 `develop` 分支创建
- 分支名全小写，用短横线连接
- 一个分支只做一个功能

#### Step 3: 设计与实现

**每一次开发都必须包含架构设计评估**：

1. **新功能开发**：必须在 `design/` 目录下创建或更新设计文档，包含：接口定义、核心算法伪代码、数据流图、前后端交互协议
2. **Bug 修复**：评估是否因架构缺陷引起，若是则先更新设计文档再修复代码
3. **重构**：必须先写重构设计文档，说明动机、影响范围、迁移方案
4. 设计文档通过 Review 后方可编码

**前后端配套开发要求**：

```
后端 API 变更                   前端同步变更
─────────────────              ─────────────────
新增 Parser 接口        →      文件选择对话框支持新格式
新增 Matcher 返回字段    →      Match Review Panel 展示新字段
Generator 进度回调变更   →      ProgressBar 适配新回调
Engine 接口变更          →      CLI 参数同步更新
```

**编码要求**：
- 严格遵循 `specs/CODING_STANDARDS.md`
- 使用基类-注册模式
- switch-case/match-case 优先于 if-else
- 所有公共方法包含 docstring
- **尽量复用已有代码**：新增功能前先搜索是否有可复用的函数/类

#### Step 4: 测试

**测试驱动开发（TDD）流程**：

```
1. 先写测试 → 2. 运行测试（红）→ 3. 写最少代码 → 4. 运行测试（绿）→ 5. 重构
```

**测试要求**：

| 测试类型 | 覆盖要求 | 位置 |
|----------|---------|------|
| 单元测试 | > 90% 代码覆盖 | `tests/unit/` |
| 集成测试 | 每个管道阶段至少 1 个 | `tests/integration/` |
| 端到端测试 | Phase 结束时添加 | `tests/e2e/` |

**测试文件命名**：
```
tests/unit/test_<模块名>.py
tests/integration/test_<功能名>_pipeline.py
```

#### Step 5: PR 提交

**PR 模板**：

```markdown
## 概述
简短描述变更内容

## 关联 Issue
Closes #12

## 变更类型
- [ ] 新功能
- [ ] Bug修复
- [ ] 重构
- [ ] 文档更新

## 测试
- [ ] 单元测试通过: 15 tests passed
- [ ] 集成测试通过: 3 tests passed
- [ ] 新增测试覆盖: test_exact_matcher.py (12 tests)

## 检查清单
- [ ] 遵循 CODING_STANDARDS.md
- [ ] 所有公共方法有 docstring
- [ ] 无循环依赖
- [ ] CHANGELOG 已更新
- [ ] 相关设计文档已更新
```

#### Step 6: Code Review

**Review 检查项**：

| 检查项 | 标准 |
|--------|------|
| 命名规范 | 类名 PascalCase，函数 snake_case |
| 分支控制 | match-case 或字典分发，避免长 if-elif 链 |
| 高内聚低耦合 | 单一职责，无循环依赖 |
| 基类-注册模式 | 新功能通过注册机制加入，不修改已有代码 |
| 错误处理 | 抛出具体异常，不静默失败 |
| 日志 | 关键步骤有 info，异常有 warning/error |
| 测试覆盖 | 单元测试覆盖新增代码 |
| 版本兼容 | 不引入不兼容的 API 变更（除非 MAJOR 版本） |

**Review 规则**：
- 至少 1 人 Review 通过后方可合并
- 核心模块（parser/matcher/generator）至少 2 人 Review
- Review 意见必须在合并前解决

#### Step 7: 合并

```bash
# Squash Merge（推荐）：将分支上的所有 commit 压缩为一个
git merge --squash feature/12-exact-matcher
git commit -m "[Feature] ExactMatcher: fingerprint-based exact component matching (#12)"
```

**Commit Message 规范**：

```
[类型] 模块名: 简短描述 (#Issue编号)

类型: Feature / Fix / Refactor / Docs / Chore / Test
```

---

## 3. Bug 修复流程

```
1. 创建 Bug Issue（描述现象、复现步骤、期望行为）
2. 创建 bugfix/<id>-<desc> 分支
3. 先写复现测试（确认 Bug 存在）
4. 修复代码（测试变绿）
5. 【强制】添加回归测试（覆盖 Bug 涉及的代码路径，防止未来复现）
6. 【强制】评估是否需要更新设计文档（如 Bug 根因是架构缺陷）
7. 【强制】更新 CHANGELOG（Fixed 条目）
8. PR → Review → Merge
```

**回归测试要求**：

| Bug 类型 | 回归测试方法 |
|---------|-------------|
| 解析错误 | 添加包含该边缘情况的测试数据文件，验证解析不再报错 |
| 匹配失败 | 添加该器件对到测试集，验证匹配成功 |
| UI 崩溃 | 添加 GUI 自动化测试，覆盖触发该 Bug 的操作路径 |
| 性能退化 | 添加性能基准测试（benchmark），设定最大耗时阈值 |
| 数据丢失 | 添加完整性校验测试，逐字段比较输入输出 |

**测试判断流程**：
```
Bug 修复完成
    ↓
当前测试是否已覆盖此 Bug 场景？
    ├── 是 → 确认现有测试通过 → 完成
    └── 否 → 必须新增回归测试 → Review → 完成
```

---

## 4. 代码审查会议

| 频率 | 内容 | 参与者 |
|------|------|--------|
| 每日（开发阶段） | 进度同步、阻塞项报告 | 所有开发者 |
| 每周 | Code Review 回顾、技术难点讨论 | 所有开发者 |
| 每 Phase 结束 | 阶段验收评审、下阶段计划 | 全体 |

---

## 5. 版本发布流程

### 5.1 版本号规则

遵循语义化版本：`MAJOR.MINOR.PATCH`

- **MAJOR**: 不兼容的 API 变更、核心架构重构
- **MINOR**: 向后兼容的新功能
- **PATCH**: 向后兼容的 Bug 修复

### 5.2 发布步骤

```
1. 确认所有 Phase 任务完成
2. 确认所有测试通过（CI）
3. 更新 CHANGELOG.md（确定版本号和发布日期）
4. 更新 README.md（如有需要）
5. **四文件同步检查单**（版本号必须一致，不一致时禁止打 Tag）：
   - [ ] `cis2hdl/__init__.py` — `__version__`
   - [ ] `pyproject.toml` — `project.version`
   - [ ] `CHANGELOG.md` — 当前版本标题
   - [ ] `README.md` — 版本徽章/说明
6. 创建 Git Tag: git tag -a v0.1.0 -m "Phase I: Foundation"
7. 打包发布（PyInstaller 生成 .exe）
```

---

## 6. 紧急修复流程（Hotfix）

当生产环境发现阻塞性 Bug 时：

```
1. 从最新的 release tag 创建 hotfix/<desc> 分支
2. 修复 → 测试 → Review → 合并到 main
3. 同时 cherry-pick 到 develop 分支
4. 立即创建新的 PATCH 版本 Tag
5. 发布新版本
```

---

## 7. 文档维护规则

### 7.1 强制更新表

| 文档 | 何时更新 | 谁更新 | 强制级别 |
|------|---------|--------|:--------:|
| `CHANGELOG.md` | **每次 PR 合并时** | 开发者 | **强制** |
| `design/*.md` | 架构、接口、数据流变更时 | 开发者 | **强制（评估后）** |
| `README.md` | 新功能完成或接口变更时 | 开发者 | 推荐 |
| `specs/*.md` | 规范变更时 | 全员提案，主程审核 | 推荐 |
| `docs/*.md` | 需求变更或新调研时 | 调研者 | 推荐 |

### 7.2 CHANGELOG 更新规范

**每一次开发和改动都必须更新 CHANGELOG**，无例外。

```markdown
## [Unreleased]

### Added
- 新增的 Feature

### Changed
- 变更的现有功能

### Fixed
- 修复的 Bug

### Deprecated
- 即将移除的功能
```

**CHANGELOG 条目必须包含 Issue 编号**：
```markdown
### Fixed
- 修复 DSN 解析器在空页面时崩溃的问题 (#45)
- 修复模糊匹配器在器件名为空时返回 None 的问题 (#46)
```

> **CHANGELOG 补录纪律**：版本发布后若发现 CHANGELOG 长期未更新，必须在下一个版本发布前补录。历史教训：v0.9.0 → v1.1.0 期间 CHANGELOG 曾长期未更新，已于 2026-08-07 补录；禁止出现"版本号已升、CHANGELOG 空白"的情况。

### 7.3 规则

- **代码和文档同步提交**（同一个 PR），不允许"先合代码后补文档"
- 文档文件先于代码文件创建（设计阶段）
- 过时文档标记 `[DEPRECATED]` 前缀而非删除
- PR 模板中 CHANGELOG Checkbox 未勾选 → Review 不通过

---

## 8. 环境与工具链

### 8.1 开发环境

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 安装依赖（必须在项目根目录 cis2hdl/ 下执行；包位于 cis2hdl/ 而非 src/）
pip install -e ".[dev]"

# 代码质量检查
ruff check .
ruff format --check .
mypy cis2hdl/

# 运行测试
pytest tests/ -v --cov=cis2hdl/
```

### 8.2 CI/CD（推荐）

```yaml
# .github/workflows/ci.yml 示例结构
on: [push, pull_request]
jobs:
  lint:
    - ruff check
    - ruff format --check
    - mypy
  test:
    - pytest --cov
  build:
    - PyInstaller 打包
```

---

## 9. 问题升级路径

| 问题类型 | 处理者 | 升级条件 |
|---------|--------|---------|
| 编译/运行错误 | 开发者自行解决 | 超过 2 小时无进展 → 主程 |
| 设计决策分歧 | 开发者讨论 | 无法达成一致 → 主程裁决 |
| 第三方依赖问题 | 开发者调查 | 不可解决 → 讨论替代方案 |
| 性能瓶颈 | 开发者优化 | 超过 Phase 指标 → 架构评审 |
| 安全/合规问题 | 立即上报主程 | 无需等待 |
