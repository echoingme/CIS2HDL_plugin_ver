# Phase XXIV 插件化重构 · pluggy 框架调研笔记

> 日期：2026-08-14｜搜集：齐活林（多引擎搜索）｜用途：S2 插件基座实现参考
> 依据：pluggy 官方文档 + 社区最佳实践（2026-08-14 检索）

## 1. 核心 API 速查

### 标记器（Markers）
```python
from pluggy import HookspecMarker, HookimplMarker
hookspec = HookspecMarker("cis2hdl")   # hook 规范
hookimpl = HookimplMarker("cis2hdl")   # hook 实现
```
> 两个标记器与 PluginManager 必须使用**相同的项目名**。

### PluginManager 关键方法
| 方法 | 作用 |
|------|------|
| `pm = pluggy.PluginManager("cis2hdl")` | 创建管理器 |
| `pm.add_hookspecs(PipelineHooks)` | 注册 hook 规范 |
| `pm.register(plugin_obj, name=plugin.name)` | 注册插件 |
| `pm.hook.load_input(ctx=ctx)` | 调用 hook（**必须关键字参数**） |
| `pm.unregister(plugin)` / `pm.is_registered(name)` | 注销/检查 |
| `pm.load_setuptools_entrypoints("cis2hdl_plugins")` | entry points 自动加载 |
| `pm.check_pending()` | 校验所有 hookimpl 有对应 hookspec |

### 调用语义
- 默认**逆序调用**（LIFO：后注册先执行）；返回值收集为列表
- 任何 hookimpl 抛异常 → 停止后续调用，异常向上传播

## 2. 签名校验规则（写错参数启动即报错——方案 §3.3 的防线）
- ✅ hookimpl 可接受**更少**参数（便于 hookspec 演化）
- ❌ hookimpl 接受**更多**参数 → 非法
- `self` 参数总是被忽略（类方法）
- `@hookimpl(optionalhook=True)` 跳过校验
- `@hookimpl(specname="setup_project")` 函数名与 spec 不一致时指定匹配

## 3. 关键选项
| 选项 | 用途 |
|------|------|
| `@hookimpl(trylast=True)` | 最后执行（默认实现） |
| `@hookimpl(tryfirst=True)` | 最先执行（日志/预处理） |
| `@hookspec(firstresult=True)` | 取第一个非 None 结果即停（返回单值非列表） |
| `@hookimpl(wrapper=True)` | 包装器：生成器 `result = yield` 环绕所有普通 impl（1.1+） |
| `@hookspec(historic=True)` | 插件注册前可调用，晚注册插件立即回放 |

## 4. 最小示例（本项目形态）
```python
# hookspecs.py
from pluggy import HookspecMarker
hookspec = HookspecMarker("cis2hdl")

class PipelineHooks:
    @hookspec
    def load_input(self, ctx) -> None: ...

# 插件
from pluggy import HookimplMarker
hookimpl = HookimplMarker("cis2hdl")

class EdifInputPlugin:
    name = "edif"
    stage = "input"
    @hookimpl
    def load_input(self, ctx) -> None:
        ...
```

## 5. 本项目 S2 落地要点（对齐方案 §3.3/§3.5）
- 内置插件 = 现有模块**薄包装**（不重写逻辑），默认 profile 行为不变
- 顺序控制：美化钩子链按 yaml 顺序 → 方案用 `beautify` 单 hook + 插件内 self._enabled 控制？**注意**：pluggy 逆序执行，若要按 yaml 顺序需在 manager 层按配置排序注册，或单插件按顺序调用（架构师 S1 设计应明确此点）
- 卸载：`pm.unregister` + 插件 cleanup()（Cordis unload 理念）
- 加载失败不阻塞整体：try/except 包注册，失败插件 warning 降级（NFR3）

## 6. 最佳实践（社区）
1. hookspec 文档齐全 + 参数类型明确 + 返回值一致
2. hook 接口变更做版本控制（向后兼容）
3. 插件测试套件（加载/调用/错误处理）
4. tryfirst/trylast 控制执行顺序；firstresult 减少重复计算
5. entry points 用于 pip 安装插件；目录扫描用于内置插件
