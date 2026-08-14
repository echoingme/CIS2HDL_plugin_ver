"""S2 T01 — ConversionContext 只读守卫单元测试。

Covers（docs/S2-plugin-base-design.md T01）：
  * 字段默认值 / 构造
  * 快照 + 校验：未改动 → 无违规
  * 未声明字段被赋值 → 返回违规名；strict=True → ReadOnlyViolation
  * 声明字段（writes_keys）赋值 → 放行
  * writable() 临时声明 → 放行
  * 可变对象**原地修改** → 不判违规（报告聚合合法）
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cis2hdl.core.pipeline_config import PipelineConfig
from cis2hdl.plugins.context import ConversionContext, ReadOnlyViolation


def _ctx(**overrides) -> ConversionContext:
    base = ConversionContext(cfg=PipelineConfig())
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


class TestFields:
    def test_defaults(self):
        ctx = _ctx()
        assert ctx.profile == "default"
        assert ctx.input_files == []
        assert ctx.output_dir is None
        assert ctx.ir is None
        assert ctx.hdl_db is None
        assert ctx.matches == []
        assert ctx.manual_overrides == {}
        assert ctx.routed_nets is None
        assert ctx.report is not None  # ConversionReport 惰性构造

    def test_cfg_required(self):
        with pytest.raises(TypeError):
            ConversionContext()  # type: ignore[call-arg]

    def test_input_files_paths(self):
        ctx = _ctx(input_files=[Path("a.dsn")])
        assert ctx.input_files[0].name == "a.dsn"


class TestGuard:
    def test_unchanged_no_violation(self):
        ctx = _ctx()
        ctx._snapshot_fields({"ir", "matches", "report"})
        violated = ctx._verify_unchanged(allowed={"matches"}, strict=False)
        assert violated == []

    def test_undeclared_assignment_detected(self):
        ctx = _ctx()
        ctx._snapshot_fields({"ir", "matches"})
        ctx.ir = "CHANGED"  # 未声明 writes_keys
        violated = ctx._verify_unchanged(allowed={"matches"}, strict=False)
        assert violated == ["ir"]

    def test_declared_assignment_allowed(self):
        ctx = _ctx()
        ctx._snapshot_fields({"ir", "matches"})
        ctx.matches = ["changed"]  # 声明在 writes_keys
        violated = ctx._verify_unchanged(allowed={"matches"}, strict=True)
        assert violated == []

    def test_strict_raises(self):
        ctx = _ctx()
        ctx._snapshot_fields({"ir"})
        ctx.ir = "CHANGED"
        with pytest.raises(ReadOnlyViolation) as exc:
            ctx._verify_unchanged(allowed=set(), strict=True)
        assert "ir" in str(exc.value)

    def test_strict_no_raise_when_allowed(self):
        ctx = _ctx()
        ctx._snapshot_fields({"ir"})
        ctx.ir = "CHANGED"
        ctx._verify_unchanged(allowed={"ir"}, strict=True)  # 不抛

    def test_writable_declares_temporary_write(self):
        ctx = _ctx()
        ctx._snapshot_fields({"ir"})
        with ctx.writable("ir"):
            ctx.ir = "INSIDE"  # 临时声明可写
        # 声明在本次调用期间持续（PluginHost 的 finally 校验需要）；下次
        # _snapshot_fields 才重置
        assert "ir" in ctx._locked
        ctx._verify_unchanged(allowed=set(), strict=True)  # _locked 并集 → 放行

    def test_writable_reset_on_next_snapshot(self):
        """下一插件调用前 _snapshot_fields 重置 writable 声明，不泄漏。"""
        ctx = _ctx()
        with ctx.writable("ir"):
            ctx.ir = "INSIDE"
        assert "ir" in ctx._locked
        ctx._snapshot_fields({"ir"})  # 新一轮调用
        assert "ir" not in ctx._locked


class TestInPlaceMutation:
    def test_inplace_mutation_not_flagged(self):
        """报告聚合：原地 append 合法（只护字段赋值，不护内部修改）。"""
        ctx = _ctx()
        ctx._snapshot_fields({"report"})
        ctx.report.warnings.append("some warning")  # 原地修改
        violated = ctx._verify_unchanged(allowed=set(), strict=True)
        assert violated == []

    def test_inplace_mutation_matches_list(self):
        ctx = _ctx()
        ctx._snapshot_fields({"matches"})
        ctx.matches.append("m1")  # 原地修改，引用不变
        violated = ctx._verify_unchanged(allowed=set(), strict=True)
        assert violated == []

    def test_full_replacement_flagged(self):
        ctx = _ctx()
        ctx._snapshot_fields({"matches"})
        ctx.matches = ["brand_new"]  # 整体替换 → 违规
        violated = ctx._verify_unchanged(allowed=set(), strict=False)
        assert violated == ["matches"]
