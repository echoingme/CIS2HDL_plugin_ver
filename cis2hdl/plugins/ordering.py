"""注册顺序控制（S2 §3.3 / 决策 D1：单 hook + 逆序注册 + LIFO 反转）。

设计依据：``docs/S2-plugin-base-design.md`` §3.3。

pluggy 默认 LIFO（后注册先执行）与"yaml 顺序执行"矛盾 → 逆序注册反转：
- 外部插件（entry points）先注册 → LIFO 下最后执行（追加在默认链之后）；
- 内置插件按 stage 分组，每组 **reversed(yaml 顺序)** 注册 → LIFO 执行 =
  yaml 顺序。

配套铁律：有序 hook（load_input/match_components/beautify）的 hookimpl
**禁止** tryfirst/trylast（同一 tier 内 LIFO 才成立）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.pipeline_config import PipelineConfig
    from .manager import PluginManager
    from .spec import PluginSpec

__all__ = ["registration_order", "assert_order", "stage_hook_name"]

#: stage → 对应 hook 名（输出/测试无独立 hook，S2 仅 beautify/match/input 有序）。
_STAGE_HOOK: dict[str, str] = {
    "input": "load_input",
    "match": "match_components",
    "beautify": "beautify",
}


def _stage_plugin_order(cfg: "PipelineConfig", stage: str) -> list[str]:
    """返回 cfg 声明的 yaml 顺序（output = files + reports 合并语义）。"""
    if stage == "input":
        return list(cfg.input.plugins)
    if stage == "match":
        return list(cfg.match.plugins)
    if stage == "beautify":
        return list(cfg.beautify.plugins)
    if stage == "output":
        return list(cfg.output.files) + list(cfg.output.reports)
    if stage == "test":
        return list(cfg.test.suites)
    return []


def registration_order(
    enabled_specs: list["PluginSpec"],
    cfg: "PipelineConfig",
) -> list["PluginSpec"]:
    """返回**注册顺序**（外部先、内置 stage 分组逆 yaml 序）。

    LIFO 执行后 = yaml 声明顺序。
    """
    ordered: list["PluginSpec"] = [s for s in enabled_specs if not s.builtin]

    for stage in ("input", "match", "beautify"):
        order = _stage_plugin_order(cfg, stage)
        by_name = {
            s.name: s for s in enabled_specs if s.builtin and s.stage == stage
        }
        for name in reversed(order):
            if name in by_name:
                ordered.append(by_name[name])
                by_name.pop(name)
        # 该 stage 未在 cfg 顺序中但被启用的内置插件 → 追加（兜底）
        ordered.extend(by_name.values())

    # output/test 无独立有序 hook（S6/S8 各插件注册后按发现序执行，
    # 结果聚合与执行顺序无关）；其 spec 按发现序末尾追加
    for s in enabled_specs:
        if s.stage in ("output", "test"):
            ordered.append(s)

    return ordered


def stage_hook_name(stage: str) -> str:
    """返回 stage 对应的 hook 名（无序 stage → None）。"""
    return _STAGE_HOOK.get(stage, "")


def assert_order(pm: "PluginManager", stage: str, expected_names: list[str]) -> None:
    """断言某有序 stage 的**执行顺序** == expected（测试/调试用）。

    实现：读 ``pm.hook.<hook>.get_hookimpls()``（注册序）取逆 → 执行序；
    映射 plugin 名（``pm.get_name``）。
    """
    hook_name = stage_hook_name(stage)
    if not hook_name:
        raise AssertionError(f"stage {stage!r} 无独立 hook，无法断言顺序")
    hookcaller = getattr(pm.hook, hook_name)
    impls = hookcaller.get_hookimpls()
    # get_hookimpls() 返回注册序；执行序 = 逆序（LIFO，plain hookimpl）
    actual = [pm.get_name(i.plugin) for i in reversed(impls)]
    assert list(actual) == list(expected_names), (
        f"stage={stage} 执行顺序不符: 期望 {list(expected_names)} 实际 {actual}"
    )
