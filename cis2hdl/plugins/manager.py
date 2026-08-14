"""PluginManager — 插件生命周期管理（S2 §3.5）。

设计依据：``docs/S2-plugin-base-design.md`` §3.5。

流程：发现 → 过滤（enabled_by_cfg）→ 实例化（resolve_params）→ 排序
（register_ordered）→ 校验（check_pending）→ 执行（pm.hook）→ 清理。

降级（NFR3）：每个插件 导入/实例化/注册 各自 try/except；失败 →
``logger.warning`` + ``self.degraded`` + skip；**绝不因单插件失败中断整体**。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pluggy import PluginManager as _Pm

from .discover import discover_all, _default_plugins_dir
from .hookspecs import PROJECT_NAME, PipelineHooks
from .ordering import registration_order
from .params import resolve_params

if TYPE_CHECKING:
    from ..core.pipeline_config import PipelineConfig
    from .spec import PluginSpec

logger = logging.getLogger(__name__)

__all__ = ["PluginManager", "build_plugin_manager"]


class PluginManager:
    """插件生命周期管理：发现 → 过滤 → 实例化 → 排序 → 执行 → 清理。"""

    def __init__(
        self,
        *,
        plugins_dir: Path | None = None,
        strict_ctx: bool = False,
    ) -> None:
        self._pm = _Pm(PROJECT_NAME)
        self._pm.add_hookspecs(PipelineHooks)
        self._plugins_dir = Path(plugins_dir) if plugins_dir is not None else _default_plugins_dir()
        self.strict_ctx = strict_ctx
        self.degraded: list[tuple[str, str]] = []
        """[(插件名, 错误信息)]（NFR3）。"""
        self._specs: list["PluginSpec"] = []
        self._enabled: list["PluginSpec"] = []
        self._instances: dict[str, Any] = {}
        self._registered_names: list[str] = []

    # ── 发现 ──────────────────────────────────────────────────────────

    def discover(self) -> list["PluginSpec"]:
        """scan_builtin_plugins + load_entrypoint_plugins，去重。

        发现阶段（导入）失败 → 记入 ``self.degraded``（NFR3）。
        """
        specs, errors = discover_all(self._plugins_dir)
        self._specs = specs
        for err in errors:
            self.degraded.append(err)
        return list(self._specs)

    def list_plugins(self, stage: str | None = None) -> list["PluginSpec"]:
        """已发现（全部）插件；S1 ProfileManager 白名单替换入口。"""
        if not self._specs:
            self.discover()
        if stage is not None:
            return [s for s in self._specs if s.stage == stage]
        return list(self._specs)

    # ── 组装 ──────────────────────────────────────────────────────────

    def build(self, cfg: "PipelineConfig", engine: Any = None) -> "PluginManager":
        """完整流程（幂等：重复 build 前先 cleanup）。

        ① discover() 全部 spec
        ② enabled_by_cfg：spec.name ∈ cfg.<stage>.plugins（output 用
           files+reports 合并语义 + S2 粗粒度 default_writer/reports 恒注册）
        ③ instantiate：resolve_params + cls(**params)；失败 → degraded + skip
        ④ register_ordered：外部先、内置逆 yaml 序注册
        ⑤ check_pending() 校验；失败插件 degraded + 继续
        ⑥ 返回 self
        """
        self.cleanup()
        self.degraded = []
        self._instances = {}
        self._registered_names = []

        self.discover()
        enabled = self._enabled_by_cfg(cfg)
        self._enabled = enabled

        # ③ 实例化（降级）
        for spec in enabled:
            if spec.cls is None:
                continue  # 白名单占位（不实例化不注册）
            try:
                params = resolve_params(cfg, spec, engine=engine)
                self._instances[spec.name] = spec.cls(**params)
            except Exception as exc:  # noqa: BLE001 — NFR3 降级
                self.degraded.append((spec.name, f"实例化失败: {exc}"))

        # ④ 注册（降级；register_ordered 顺序）
        for spec in registration_order(enabled, cfg):
            if spec.cls is None or spec.name not in self._instances:
                continue
            try:
                self._pm.register(self._instances[spec.name], name=spec.name)
                self._registered_names.append(spec.name)
            except Exception as exc:  # noqa: BLE001 — NFR3 降级
                self.degraded.append((spec.name, f"注册失败: {exc}"))
                self._instances.pop(spec.name, None)

        # ⑤ check_pending 校验
        try:
            self._pm.check_pending()
        except Exception as exc:  # noqa: BLE001 — 校验失败降级
            logger.warning("check_pending 校验失败: %s", exc)

        if self.degraded:
            logger.warning(
                "插件加载降级 %d 个: %s",
                len(self.degraded),
                [n for n, _ in self.degraded],
            )
        return self

    def _enabled_by_cfg(self, cfg: "PipelineConfig") -> list["PluginSpec"]:
        """按 cfg 各阶段插件组合过滤（未在列表中的插件 = 禁用，不注册）。"""
        enabled: list["PluginSpec"] = []
        for spec in self._specs:
            hit = False
            if spec.stage == "input":
                hit = spec.name in cfg.input.plugins
            elif spec.stage == "match":
                hit = spec.name in cfg.match.plugins
            elif spec.stage == "beautify":
                hit = spec.name in cfg.beautify.plugins
            elif spec.stage == "output":
                hit = spec.name in cfg.output.files or spec.name in cfg.output.reports
            elif spec.stage == "test":
                hit = spec.name in cfg.test.suites
            if hit:
                enabled.append(spec)
        # S2 粗粒度：output default_writer/reports 恒注册（默认 profile 必需；
        # S6 再按 files/reports 精确过滤）
        for name in ("default_writer", "reports"):
            if not any(s.stage == "output" and s.name == name for s in enabled):
                for spec in self._specs:
                    if spec.stage == "output" and spec.name == name:
                        enabled.append(spec)
                        break
        return enabled

    # ── 执行 / 查询 ───────────────────────────────────────────────────

    @property
    def hook(self) -> Any:
        return self._pm.hook

    def get_plugin(self, name: str) -> Any:
        return self._pm.get_plugin(name)

    def get_name(self, plugin: Any) -> str | None:
        return self._pm.get_name(plugin)

    # ── 卸载 / 清理 ───────────────────────────────────────────────────

    def cleanup(self) -> None:
        """逆注册顺序调用各插件 cleanup()（存在时），再 unregister 全部；
        幂等；失败仅 warning。"""
        for name in reversed(self._registered_names):
            plugin = self._pm.get_plugin(name)
            if plugin is not None and hasattr(plugin, "cleanup"):
                try:
                    plugin.cleanup()
                except Exception as exc:  # noqa: BLE001 — 清理失败不阻断
                    logger.warning("插件 %s cleanup 失败: %s", name, exc)
        self.unregister_all()

    def unregister_all(self) -> None:
        for name in list(self._registered_names):
            try:
                self._pm.unregister(name=name)
            except Exception:  # noqa: BLE001 — 幂等
                pass
        self._registered_names = []
        self._instances = {}


def build_plugin_manager(
    cfg: "PipelineConfig",
    *,
    plugins_dir: Path | None = None,
    strict_ctx: bool = False,
    engine: Any = None,
) -> PluginManager:
    """主入口（方案 §3.5 同名函数）：PluginManager().build(cfg)。"""
    return PluginManager(
        plugins_dir=plugins_dir, strict_ctx=strict_ctx,
    ).build(cfg, engine=engine)
