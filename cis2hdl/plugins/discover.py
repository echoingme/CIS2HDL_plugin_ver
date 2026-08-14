"""插件发现：内置=目录扫描，外部=entry points（S2 §3.1 / 决策 D6）。

设计依据：``docs/S2-plugin-base-design.md`` §3.1。

内置插件约定：
- 目录：``cis2hdl/plugins/<stage>/*.py``；**模块名 = 插件名**。
- 每个模块声明 ``PLUGIN: PluginSpec`` 类变量。
- ``__init__.py`` 汇总 ``_SPECS``（list[PluginSpec]）——用于 output/test
  的"白名单 spec"（无独立模块文件时也纳入扫描）。
- 扫描跳过 ``_`` 前缀模块与 ``__init__`` 自身（但读取其 ``_SPECS``）。

外部插件约定：
- entry points group：``cis2hdl.plugins``，格式 ``name = module.path:PLUGIN``。
- 缺 entry points 包 → 空列表，不报错。

降级（NFR3）：单个插件导入失败 → warning + 记入调用方 degraded，不中断。
"""

from __future__ import annotations

import importlib
import importlib.metadata
import logging
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .spec import PluginSpec

logger = logging.getLogger(__name__)

#: 外部插件 entry points group。
ENTRYPOINT_GROUP = "cis2hdl.plugins"


def _default_plugins_dir() -> Path:
    """返回 ``cis2hdl/plugins`` 包目录（默认扫描根）。"""
    return Path(__file__).resolve().parent


def scan_builtin_plugins(
    plugins_dir: Path | None = None,
) -> tuple[list["PluginSpec"], list[tuple[str, str]]]:
    """扫描包内 ``plugins/<stage>/*.py``，返回 (specs, errors)。

    - 每个 stage 目录的 ``__init__.py`` ``_SPECS`` 汇总优先纳入（output/test
      白名单 spec 所在）。
    - 逐模块读 ``PLUGIN``；跳过 ``__init__`` 与 ``_`` 前缀模块。
    - 导入/读取失败 → errors 记录（(插件名, 错误)，供 manager.degraded）。
    """
    from .spec import STAGES

    root = Path(plugins_dir) if plugins_dir is not None else _default_plugins_dir()
    specs: list["PluginSpec"] = []
    errors: list[tuple[str, str]] = []
    for stage in STAGES:
        stage_dir = root / stage
        if not stage_dir.is_dir():
            continue
        # ① __init__._SPECS 汇总（output/test 白名单）
        try:
            pkg = importlib.import_module(f"cis2hdl.plugins.{stage}")
            init_specs = getattr(pkg, "_SPECS", None) or []
            for s in init_specs:
                specs.append(s)
        except Exception as exc:  # noqa: BLE001 — NFR3 降级
            logger.warning("插件包 %s 加载失败: %s", stage, exc)
            errors.append((f"{stage}.__init__", str(exc)))
        # ② 逐模块 PLUGIN
        for mod_info in pkgutil.iter_modules([str(stage_dir)]):
            if mod_info.name.startswith("_"):
                continue
            module_name = f"{stage}.{mod_info.name}"
            try:
                module = importlib.import_module(f"cis2hdl.plugins.{module_name}")
                spec = getattr(module, "PLUGIN", None)
                if spec is None:
                    logger.warning("插件模块 %s 缺 PLUGIN 声明，跳过", module_name)
                    errors.append((module_name, "缺 PLUGIN 声明"))
                    continue
                specs.append(spec)
            except Exception as exc:  # noqa: BLE001 — NFR3 降级
                logger.warning("插件模块 %s 加载失败: %s", module_name, exc)
                errors.append((module_name, str(exc)))
    return specs, errors


def load_entrypoint_plugins() -> tuple[list["PluginSpec"], list[tuple[str, str]]]:
    """加载外部插件（entry points group=cis2hdl.plugins）。

    缺 entry points 包 / 单插件损坏 → 空/跳过 + warning，不报错。
    """
    from .spec import PluginSpec

    specs: list["PluginSpec"] = []
    errors: list[tuple[str, str]] = []
    try:
        eps = importlib.metadata.entry_points(group=ENTRYPOINT_GROUP)
    except Exception as exc:  # noqa: BLE001 — 旧 Python/无 entry points 包
        logger.debug("entry points 不可用: %s", exc)
        return specs, errors
    for ep in eps:
        try:
            loaded = ep.load()
            if isinstance(loaded, PluginSpec):
                spec = loaded
            else:
                spec = getattr(loaded, "PLUGIN", None)
            if spec is None:
                logger.warning("外部插件 %s 缺 PLUGIN 声明，跳过", ep.name)
                errors.append((ep.name, "缺 PLUGIN 声明"))
                continue
            specs.append(spec)
        except Exception as exc:  # noqa: BLE001 — NFR3 降级
            logger.warning("外部插件 %s 加载失败: %s", ep.name, exc)
            errors.append((ep.name, str(exc)))
    return specs, errors


def discover_all(
    plugins_dir: Path | None = None,
) -> tuple[list["PluginSpec"], list[tuple[str, str]]]:
    """内置 + 外部，按 (stage, name) 去重（内置优先）。返回 (specs, errors)。"""
    builtin, builtin_errors = scan_builtin_plugins(plugins_dir)
    external, external_errors = load_entrypoint_plugins()
    seen: set[tuple[str, str]] = set()
    result: list["PluginSpec"] = []
    for spec in builtin + external:
        key = (spec.stage, spec.name)
        if key in seen:
            continue
        seen.add(key)
        result.append(spec)
    return result, builtin_errors + external_errors
