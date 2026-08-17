"""S8 — 测试插件化（FR6）单测：3 个 test 插件真实现 + verify 编排/CLI。

设计依据：``docs/developer-guide.md`` S8 章节 / ``cis2hdl/plugins/test/_base.py`` /
``cis2hdl/verify.py``。

覆盖：
  1. 3 个 test 插件（unit/e2e/qa_package）元数据：cls 非 None、stage="test"、
     writes_keys 契约、独立模块 PLUGIN。
  2. PluginManager 按 test.suites 过滤注册（全开/部分/全关）。
  3. run_verification 钩子：套件未启用（ctx.cfg.test.suites）→ None；
     启用 → 返回 list[str]（monkeypatch 子进程）。
  4. pytest 结果解析（parse_pytest_summary / format_pytest_summary）。
  5. qa_package：交付目录优先序 + 无交付目录等价结构检查 + 脚本运行。
  6. VerificationRunner：--suite 过滤（深拷贝不污染）、未知套件失败、
     结果聚合、降级处理。
  7. CLI verify_main：退出码 0/1/2、报告行打印。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cis2hdl.cli import verify_main
from cis2hdl.core.pipeline_config import PipelineConfig
from cis2hdl.plugins.context import ConversionContext
from cis2hdl.plugins.manager import build_plugin_manager
from cis2hdl.plugins.test._base import (
    format_pytest_summary,
    parse_pytest_summary,
)
from cis2hdl.verify import VerificationRunner, list_test_suites

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: 3 个 test 插件名。
_TEST_PLUGINS = ("unit", "e2e", "qa_package")


class _FakeProc:
    """伪造 subprocess.CompletedProcess（monkeypatch _subprocess_run 用）。"""

    def __init__(self, rc: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = rc
        self.stdout = stdout
        self.stderr = stderr


def _pm_with_fake_subprocess(cfg: PipelineConfig, fake: _FakeProc):
    """构建 manager 并把 test 插件子进程替换为伪造输出。"""
    pm = build_plugin_manager(cfg)
    for name in _TEST_PLUGINS:
        plugin = pm.get_plugin(name)
        if plugin is not None:
            plugin._subprocess_run = lambda *a, **k: fake
            if name == "qa_package":
                plugin._find_delivery_dir = lambda ctx: None
    return pm


def _ctx(cfg: PipelineConfig) -> ConversionContext:
    return ConversionContext(cfg=cfg)


# ─────────────────────────────────────────────────────────────────────────
# 1. 插件元数据
# ─────────────────────────────────────────────────────────────────────────


class TestPluginMetadata:
    def test_three_test_plugins_real(self):
        """3 个 test 插件真实现：cls 非 None、stage=test、writes_keys=()。"""
        pm = build_plugin_manager(PipelineConfig())
        for name in _TEST_PLUGINS:
            spec = next(s for s in pm.list_plugins("test") if s.name == name)
            assert spec.cls is not None, name
            assert spec.stage == "test"
            assert spec.writes_keys == ()
            assert spec.module.endswith(f"plugins.test.{name}")
            assert spec.builtin is True

    def test_default_registered_all(self):
        """默认 test.suites 全开 → 3 个插件全部注册。"""
        pm = build_plugin_manager(PipelineConfig())
        for name in _TEST_PLUGINS:
            assert pm.get_plugin(name) is not None, name
            assert name in pm._registered_names

    def test_suites_filter_registration(self):
        """test.suites 部分/全关 → 对应插件不注册。"""
        cfg = PipelineConfig()
        cfg.test.suites = ["unit"]
        pm = build_plugin_manager(cfg)
        assert pm.get_plugin("unit") is not None
        assert pm.get_plugin("e2e") is None
        assert pm.get_plugin("qa_package") is None

        cfg2 = PipelineConfig()
        cfg2.test.suites = []
        pm2 = build_plugin_manager(cfg2)
        for name in _TEST_PLUGINS:
            assert pm2.get_plugin(name) is None, name

    def test_list_test_suites(self):
        assert list_test_suites() == ["e2e", "qa_package", "unit"]


# ─────────────────────────────────────────────────────────────────────────
# 2. run_verification 钩子 + 套件启停
# ─────────────────────────────────────────────────────────────────────────


class TestRunVerification:
    def test_disabled_suite_returns_none(self):
        """套件未启用（ctx.cfg.test.suites 不含本插件名）→ None（pluggy 丢弃）。"""
        cfg = PipelineConfig()
        cfg.test.suites = ["unit"]
        pm = build_plugin_manager(cfg)
        fake = _FakeProc(rc=0, stdout="=== 3 passed in 0.5s ===")
        pm.get_plugin("unit")._subprocess_run = lambda *a, **k: fake
        results = pm.hook.run_verification(ctx=_ctx(cfg))
        # 只有 unit 注册并返回结果
        assert len(results) == 1
        assert results[0][0].startswith("[PASS] unit:")

    def test_enabled_returns_result_lines(self):
        """启用套件 → 返回 list[str] 结果行（[PASS] 前缀 + 摘要）。"""
        cfg = PipelineConfig()
        pm = _pm_with_fake_subprocess(
            cfg, _FakeProc(rc=0, stdout="=== 1238 passed, 17 skipped in 42.3s ==="),
        )
        results = pm.hook.run_verification(ctx=_ctx(cfg))
        assert len(results) == 3  # 3 个插件各一组
        flat = [ln for group in results for ln in group]
        unit_lines = [ln for ln in flat if ln.startswith("[PASS] unit:")]
        assert unit_lines
        assert "1238 passed" in unit_lines[0]
        assert "17 skipped" in unit_lines[0]

    def test_failed_rc_marks_fail(self):
        """pytest rc!=0 / failed 计数 → [FAIL] 行。"""
        cfg = PipelineConfig()
        pm = _pm_with_fake_subprocess(
            cfg, _FakeProc(rc=1, stdout="=== 1 failed, 5 passed in 3.2s ==="),
        )
        results = pm.hook.run_verification(ctx=_ctx(cfg))
        flat = [ln for group in results for ln in group]
        assert any(ln.startswith("[FAIL] unit:") for ln in flat)
        assert "1 failed" in flat[0]

    def test_exception_degraded_error_line(self, monkeypatch):
        """子进程异常 → warning + 单行 [ERROR]（NFR3 独立降级）。"""
        cfg = PipelineConfig()
        pm = build_plugin_manager(cfg)
        plugin = pm.get_plugin("unit")

        def _boom(*a, **k):
            raise RuntimeError("boom")

        plugin._subprocess_run = _boom
        lines = plugin.run_verification(ctx=_ctx(cfg))
        assert lines is not None
        assert lines[0] == "[ERROR] unit: boom"

    def test_cleanup_resets(self):
        """cleanup 幂等复位（suites/params 清空）。"""
        pm = build_plugin_manager(PipelineConfig())
        plugin = pm.get_plugin("unit")
        plugin.cleanup()
        assert plugin.suites == []
        assert plugin.params == {}
        plugin.cleanup()  # 幂等


# ─────────────────────────────────────────────────────────────────────────
# 3. pytest 结果解析
# ─────────────────────────────────────────────────────────────────────────


class TestParseSummary:
    def test_full_summary(self):
        counts = parse_pytest_summary("=== 1238 passed, 17 skipped in 42.3s ===")
        assert counts["passed"] == 1238
        assert counts["skipped"] == 17
        assert counts["failed"] == 0
        assert counts["error"] == 0

    def test_failed_only(self):
        counts = parse_pytest_summary("=== 1 failed, 5 passed in 3.2s ===")
        assert counts["failed"] == 1
        assert counts["passed"] == 5

    def test_errors_plural(self):
        counts = parse_pytest_summary("=== 2 errors in 1.1s ===")
        assert counts["error"] == 2

    def test_empty_output(self):
        counts = parse_pytest_summary("")
        assert counts == {k: 0 for k in counts}

    def test_format(self):
        assert format_pytest_summary({"passed": 1238, "skipped": 17}) == "1238 passed, 17 skipped"
        assert format_pytest_summary({"failed": 2}) == "2 failed"
        assert format_pytest_summary({}) == "0 passed"


# ─────────────────────────────────────────────────────────────────────────
# 4. qa_package
# ─────────────────────────────────────────────────────────────────────────


class TestQaPackage:
    def test_no_delivery_structural_check(self):
        """无交付目录 → SKIP + INFO（不判失败）。"""
        cfg = PipelineConfig()
        pm = build_plugin_manager(cfg)
        plugin = pm.get_plugin("qa_package")
        plugin._find_delivery_dir = lambda ctx: None
        lines = plugin.run_verification(ctx=_ctx(cfg))
        assert lines[0].startswith("[SKIP] qa_package:")
        assert lines[1].startswith("[INFO] qa_package:")

    def test_delivery_dir_runs_script(self, tmp_path: Path):
        """有交付目录 → 调用 verify_phaseXXI_package.py，解析 PASS/FAIL 计数。"""
        cfg = PipelineConfig()
        pm = build_plugin_manager(cfg)
        plugin = pm.get_plugin("qa_package")
        fake = _FakeProc(
            rc=0,
            stdout="[PASS] 1. mock cell 数=100\n[PASS] 2. 引脚重叠=0\n"
                   "[FAIL] 3. C/X 字号≥29 — 2 违规\n",
        )
        plugin._subprocess_run = lambda *a, **k: fake
        plugin._find_delivery_dir = lambda ctx: tmp_path
        lines = plugin.run_verification(ctx=_ctx(cfg))
        assert lines[0].startswith("[FAIL] qa_package:")
        assert "2 PASS / 1 FAIL" in lines[0]
        assert any(ln.startswith("[FAIL] 3.") for ln in lines)

    def test_delivery_dir_missing_fail(self, tmp_path: Path):
        """显式交付目录不存在 → [FAIL]。"""
        cfg = PipelineConfig()
        pm = build_plugin_manager(cfg)
        plugin = pm.get_plugin("qa_package")
        missing = tmp_path / "nope"
        plugin._find_delivery_dir = lambda ctx: missing
        lines = plugin.run_verification(ctx=_ctx(cfg))
        assert lines[0].startswith("[FAIL] qa_package:")
        assert "不存在" in lines[0]

    def test_structural_missing_fail(self, tmp_path: Path):
        """等价结构检查：基础文件缺失 → [FAIL]。"""
        cfg = PipelineConfig()
        pm = build_plugin_manager(cfg)
        plugin = pm.get_plugin("qa_package")
        plugin.root_dir = tmp_path  # 空目录 → 全部缺失
        plugin._find_delivery_dir = lambda ctx: None
        lines = plugin.run_verification(ctx=_ctx(cfg))
        assert lines[0].startswith("[FAIL] qa_package:")


# ─────────────────────────────────────────────────────────────────────────
# 5. VerificationRunner
# ─────────────────────────────────────────────────────────────────────────


class TestVerificationRunner:
    def test_default_all_suites(self, monkeypatch):
        """缺省跑 cfg.test.suites 全部（monkeypatch 子进程避免真实运行）。"""
        cfg = PipelineConfig()
        fake = _FakeProc(rc=0, stdout="=== 3 passed in 0.5s ===")
        pm = _pm_with_fake_subprocess(cfg, fake)
        monkeypatch.setattr("cis2hdl.verify.build_plugin_manager", lambda *a, **k: pm)
        report = VerificationRunner(cfg).run()
        assert report.lines, "应有结果行"
        assert report.failed is False

    def test_suite_filter(self):
        """--suite 过滤：只运行指定套件且不污染原 cfg。"""
        cfg = PipelineConfig()
        original_suites = list(cfg.test.suites)
        runner = VerificationRunner(cfg)
        report = runner.run(suites=["qa_package"])
        assert all("qa_package" in ln for ln in report.lines)
        unit_prefixes = ("[PASS] unit", "[FAIL] unit", "[ERROR] unit", "[SKIP] unit")
        assert not any(ln.startswith(unit_prefixes) for ln in report.lines)
        # 原 cfg 未被污染
        assert cfg.test.suites == original_suites

    def test_unknown_suite_fails(self):
        cfg = PipelineConfig()
        report = VerificationRunner(cfg).run(suites=["bogus"])
        assert report.failed is True
        assert "未知测试套件" in report.lines[0]

    def test_empty_suites_info(self):
        """test.suites 为空 → INFO 行（不判失败）。"""
        cfg = PipelineConfig()
        cfg.test.suites = []
        report = VerificationRunner(cfg).run()
        assert report.failed is False
        assert any("没有启用的测试套件" in ln for ln in report.lines)

    def test_failed_propagates(self, monkeypatch):
        """任一 [FAIL] 行 → 整体失败。"""
        cfg = PipelineConfig()
        pm = _pm_with_fake_subprocess(
            cfg, _FakeProc(rc=1, stdout="=== 1 failed in 1.0s ==="),
        )
        monkeypatch.setattr("cis2hdl.verify.build_plugin_manager", lambda *a, **k: pm)
        report = VerificationRunner(cfg).run()
        assert report.failed is True
        assert any(ln.startswith("[FAIL]") for ln in report.lines)


# ─────────────────────────────────────────────────────────────────────────
# 6. CLI verify_main
# ─────────────────────────────────────────────────────────────────────────


class TestVerifyMain:
    def test_qa_package_exit_zero(self, capsys):
        """qa_package（无交付目录 → SKIP）退出码 0。"""
        rc = verify_main(["--suite", "qa_package"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "[SKIP] qa_package:" in out
        assert "verify 通过" in out

    def test_unknown_suite_exit_one(self, capsys):
        rc = verify_main(["--suite", "bogus"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "未知测试套件" in out

    def test_missing_pipeline_exit_one(self, capsys):
        rc = verify_main(["--pipeline", "/no/such/pipeline.yaml"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "pipeline.yaml 不存在" in out
