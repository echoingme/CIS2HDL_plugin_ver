"""S2 T01 — PipelineHooks 契约单元测试。

Covers（docs/S2-plugin-base-design.md T01）：
  * 7 个 hook 存在（load_input/match_components/apply_manual_overrides/
    beautify/write_output/write_report/run_verification）
  * 合法 hookimpl 全部可匹配 + check_pending 通过
  * 非法 hookimpl（多参数/未知 hook）被 pluggy 拒绝（签名校验生效）
  * 全部 hook firstresult=False（链式协作）
  * PROJECT_NAME 一致性
"""

from __future__ import annotations

import inspect

import pytest
from pluggy import HookimplMarker, PluginValidationError, PluginManager as _Pm

from cis2hdl.plugins.context import ConversionContext
from cis2hdl.plugins.hookspecs import PROJECT_NAME, PipelineHooks

_HOOK_NAMES = {
    "load_input",
    "match_components",
    "apply_manual_overrides",
    "beautify",
    "write_output",
    "write_report",
    "run_verification",
}


def _make_pm() -> _Pm:
    pm = _Pm(PROJECT_NAME)
    pm.add_hookspecs(PipelineHooks)
    return pm


class _LegalPlugin:
    """合法插件：7 个 hook 全部实现，签名与 hookspec 完全一致。"""

    @HookimplMarker(PROJECT_NAME)
    def load_input(self, ctx: ConversionContext) -> bool | None:  # noqa: ARG002
        return None

    @HookimplMarker(PROJECT_NAME)
    def match_components(self, ctx: ConversionContext) -> bool | None:  # noqa: ARG002
        return None

    @HookimplMarker(PROJECT_NAME)
    def apply_manual_overrides(self, ctx: ConversionContext) -> bool | None:  # noqa: ARG002
        return None

    @HookimplMarker(PROJECT_NAME)
    def beautify(self, ctx: ConversionContext) -> bool | None:  # noqa: ARG002
        return None

    @HookimplMarker(PROJECT_NAME)
    def write_output(self, ctx: ConversionContext) -> list | None:  # noqa: ARG002
        return None

    @HookimplMarker(PROJECT_NAME)
    def write_report(self, ctx: ConversionContext) -> list | None:  # noqa: ARG002
        return None

    @HookimplMarker(PROJECT_NAME)
    def run_verification(self, ctx: ConversionContext) -> list | None:  # noqa: ARG002
        return None


class TestHookSpecs:
    def test_seven_hooks_defined(self):
        hook_names = {
            name for name, _ in inspect.getmembers(PipelineHooks, inspect.isfunction)
            if not name.startswith("_")
        }
        assert _HOOK_NAMES == hook_names

    def test_all_firstresult_false(self):
        pm = _make_pm()
        for name in _HOOK_NAMES:
            hookcaller = getattr(pm.hook, name)
            assert hookcaller.spec.opts.get("firstresult", False) is False, name

    def test_legal_plugin_registers_and_check_pending(self):
        pm = _make_pm()
        plugin = _LegalPlugin()
        pm.register(plugin)
        pm.check_pending()  # 不抛异常 = 全部 hookimpl 匹配

    def test_hook_calls_return_none(self):
        pm = _make_pm()
        pm.register(_LegalPlugin())
        for name in _HOOK_NAMES:
            result = getattr(pm.hook, name)(ctx=None)
            assert all(r is None for r in result), name

    def test_project_name_consistency(self):
        assert PROJECT_NAME == "cis2hdl"


class TestIllegalHookimpls:
    def test_extra_argument_rejected(self):
        """非法 hookimpl 多一个参数 → pluggy 校验时拒绝。"""
        impl = HookimplMarker(PROJECT_NAME)

        class _BadPlugin:
            @impl
            def beautify(self, ctx: ConversionContext, extra: str) -> bool | None:  # noqa: ARG002
                return None

        pm = _make_pm()
        with pytest.raises(PluginValidationError):
            pm.register(_BadPlugin())

    def test_unknown_hook_rejected(self):
        impl = HookimplMarker(PROJECT_NAME)

        class _GhostPlugin:
            @impl
            def no_such_hook(self, ctx: ConversionContext) -> bool | None:  # noqa: ARG002
                return None

        pm = _make_pm()
        pm.register(_GhostPlugin())
        with pytest.raises(PluginValidationError):
            pm.check_pending()
