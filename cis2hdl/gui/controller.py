"""PipelineController — GUI ↔ 后端（插件化）唯一接口（S9 §3.1）。

设计依据：``docs/gui-design.md`` §3.1（12 个接口签名）+ §7（后端 API 对齐）。
薄层封装：ProfileManager / PipelineConfig / PluginManager / ConversionEngine /
VerificationRunner —— **不修改后端任何签名**（铁律）。

纯逻辑模块（**不依赖 PySide6**），可单测；UI 层经本类访问后端。

扩展接口（超出 §3.1 的 12 个，均为 GUI 组装所需，见方法 docstring）：
- :meth:`set_input_path` / :meth:`set_output_dir` —— 转换输入/输出
- :meth:`current_config` / :meth:`set_current_config` —— 当前工作配置
- :meth:`save_pipeline` —— 原子写 pipeline.yaml（§4 保存通道）
- :meth:`run_verify` —— 侧边栏 verify 快捷入口（FR6）
- :meth:`toggle_mock_prefix` —— 手动匹配面板强制 mock 前缀开关
- :meth:`profile_infos` —— 内置/自定义徽标信息
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.engine.conversion_engine import ConversionEngine, ConversionReport
from ..core.pipeline_config import PipelineConfig
from ..core.profile_manager import (
    ProfileDiff,
    ProfileError,
    ProfileManager,
)
from ..plugins.manager import PluginManager
from ..plugins.spec import PluginSpec
from .schema import build_plugin_schema

logger = logging.getLogger(__name__)

__all__ = [
    "PipelineController",
    "PluginMeta",
    "UnmatchedEntry",
    "DuplicateInfo",
    "ControllerError",
]


class ControllerError(RuntimeError):
    """GUI 控制器层错误（包装后端异常，统一提示）。"""


@dataclass
class PluginMeta:
    """``list_plugins`` 返回项（PluginSpec 的 GUI 视图）。"""

    name: str
    stage: str
    description: str
    builtin: bool
    param_section: str = ""
    param_fields: tuple[str, ...] = ()


@dataclass
class UnmatchedEntry:
    """``get_unmatched`` 返回项（FR3 手动干预）。"""

    refdes: str
    """元件位号（R12 / U3 / J5 ...）。"""
    source_library_id: str
    """CIS 库 ID。"""
    confidence: float
    """匹配置信度（0.0-1.0；MANUAL 策略为 0.0）。"""
    strategy: str = ""
    """匹配策略名（MANUAL/EXACT/FUZZY/...）。"""
    recommended_hdl: str = ""
    """推荐 HDL 器件（候选第一位；无则空）。"""


@dataclass
class DuplicateInfo(ProfileDiff):
    """查重反馈（§3.8.2）：``status`` ∈ ok|duplicate|conflict_name|same_combo_diff_params。

    - ``duplicate``：插件组合+参数与已有 profile 全等（拒绝保存）
    - ``same_combo_diff_params``：组合同、参数异（允许保存，提示差异明细）
    - ``conflict_name``：名称冲突（要求重命名/覆盖确认）
    - ``ok``：无冲突
    """

    status: str = "ok"
    duplicate_of: str = ""


def _locate_pipeline(explicit: Path | None = None) -> Path | None:
    """定位 pipeline.yaml：显式 → ./pipeline.yaml → <pkg>/config/pipeline.yaml。"""
    if explicit is not None:
        p = Path(explicit)
        return p if p.exists() else None
    candidates = [
        Path("pipeline.yaml"),
        Path(__file__).resolve().parents[1] / "config" / "pipeline.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


class PipelineController:
    """GUI ↔ 后端唯一接口（S9 §3.1 全 12 个 + 扩展）。"""

    def __init__(
        self,
        *,
        profiles_dir: Path | None = None,
        plugins_dir: Path | None = None,
        pipeline_path: Path | None = None,
    ) -> None:
        self._pm = ProfileManager(profiles_dir=profiles_dir)
        self._plugin_mgr = PluginManager(plugins_dir=plugins_dir)
        self._plugin_mgr.discover()

        self._pipeline_path = _locate_pipeline(pipeline_path)
        self._cfg = self._load_default_config()
        self._last_report: ConversionReport | None = None
        self._last_output_dir: Path | None = None
        self._input_path: Path | None = None
        self._output_dir: Path | None = None
        self._manual_overrides: dict[str, str] = {}
        """GUI 手动匹配缓存 {refdes: hdl_library_id}（set_manual_match 写）。"""

    # ── 扩展：当前工作配置 ────────────────────────────────────────────────

    @property
    def current_config(self) -> PipelineConfig:
        """当前工作配置（表单/引擎共用）。"""
        return self._cfg

    def set_current_config(self, cfg: PipelineConfig) -> None:
        self._cfg = cfg

    @property
    def pipeline_path(self) -> Path | None:
        return self._pipeline_path

    def set_input_path(self, path: Path | None) -> None:
        """设置转换输入文件（ConversionRunner 输入选择）。"""
        self._input_path = Path(path) if path is not None else None

    def set_output_dir(self, path: Path | None) -> None:
        """覆盖输出目录（缺省用 cfg.engine.output_dir）。"""
        self._output_dir = Path(path) if path is not None else None

    # ── Profile 管理（§3.1 ①-⑦） ─────────────────────────────────────────

    def list_profiles(self) -> list[str]:
        """内置 + 自定义全部 profile 名（ProfileManager.list_profiles）。"""
        return [info.name for info in self._pm.list_profiles()]

    def profile_infos(self) -> list[dict]:
        """profile 详情（GUI 侧边栏徽标用；内置只读）。"""
        return [
            {
                "name": info.name,
                "builtin": info.builtin,
                "description": info.description,
                "path": str(info.path),
            }
            for info in self._pm.list_profiles()
        ]

    def load_profile(self, name: str) -> PipelineConfig:
        """解析为完整配置（ProfileManager.get）；并设为当前工作配置。"""
        cfg = self._pm.get(name)
        self._cfg = cfg
        return cfg

    def save_profile(self, name: str, cfg: PipelineConfig) -> None:
        """保存为当前 profile（ProfileManager.create：查重 + 原子写）。

        Raises:
            DuplicateProfileError / ProfileReadOnlyError / FileExistsError
            / ProfileError（原样透传，UI 捕获展示）。
        """
        self._pm.create(name, cfg)

    def delete_profile(self, name: str) -> None:
        """删除自定义 profile（内置禁删，ProfileManager.delete）。"""
        self._pm.delete(name)

    def export_profile(self, name: str, out_path: Path) -> Path:
        """导出为可分发的 .yaml（ProfileManager.export）。"""
        return self._pm.export(name, Path(out_path))

    def import_profile(self, path: Path, rename_to: str | None = None) -> str:
        """导入他人配置（ProfileManager.import_file：校验链 + 冲突处理）。"""
        return self._pm.import_file(Path(path), rename_to=rename_to)

    def check_duplicate(self, name: str, cfg: PipelineConfig) -> DuplicateInfo | None:
        """查重：与已有 profile 比对（ProfileManager.diff/diff_all 语义）。

        Returns:
            - ``None``：无冲突（status ok，可直接保存）
            - :class:`DuplicateInfo`：duplicate / same_combo_diff_params /
              conflict_name（含 duplicate_of 与 param_diffs 明细）
        """
        name = (name or "").strip()
        if not name:
            return DuplicateInfo(
                stage="", added=[], removed=[], param_diffs={},
                equivalent=False, status="conflict_name", duplicate_of="",
            )
        for info in self._pm.list_profiles():
            if info.name.casefold() == name.casefold():
                continue  # 自身不参与查重
            try:
                existing = self._pm.get(info.name)
            except Exception:  # noqa: BLE001 — 损坏 profile 跳过
                continue
            diff = self._pm.diff(existing, cfg)
            if diff.equivalent:
                return DuplicateInfo(
                    stage="", added=[], removed=[], param_diffs={},
                    equivalent=True, status="duplicate", duplicate_of=info.name,
                )
            if not diff.added and not diff.removed and diff.param_diffs:
                # 组合同、参数异 → 允许保存，展示差异明细（§3.8.2）
                return DuplicateInfo(
                    stage=diff.stage,
                    added=[],
                    removed=[],
                    param_diffs=diff.param_diffs,
                    equivalent=False,
                    status="same_combo_diff_params",
                    duplicate_of=info.name,
                )
        return None

    # ── 插件清单与参数 schema（§3.1 ⑧⑨） ────────────────────────────────

    def list_plugins(self, stage: str) -> list[PluginMeta]:
        """某阶段全部插件元信息（PluginManager.list_plugins）。"""
        specs = self._plugin_mgr.list_plugins(stage)
        return [self._to_meta(s) for s in specs]

    def get_plugin_schema(self, name: str) -> dict:
        """插件参数 schema（驱动 ParamForm 表单生成；§3.3）。"""
        spec = self._find_spec(name)
        base = self._param_source(spec)
        return build_plugin_schema(spec, base)

    def current_plugin_params(self, name: str) -> dict[str, Any]:
        """当前配置下某插件的参数（dotted path → 值；ParamForm 初始值）。"""
        spec = self._find_spec(name)
        from .yaml_bridge import plugin_param_paths

        return plugin_param_paths(spec, self._cfg)

    def apply_plugin_param(self, name: str, path: str, value: Any) -> None:
        """把表单改动写回当前配置（双通道：表单 → cfg → yaml 预览）。"""
        spec = self._find_spec(name)
        from .yaml_bridge import apply_param_path, plugin_param_paths

        declared = set(plugin_param_paths(spec, PipelineConfig()).keys())
        if path not in declared:
            raise ControllerError(f"参数 {path!r} 不在插件 {name!r} 的声明字段内")
        apply_param_path(self._cfg, path, value)

    # ── 转换执行（§3.1 ⑩） ────────────────────────────────────────────────

    def run_conversion(
        self,
        cfg: PipelineConfig,
        cb: Callable[[str, float, str], None] | None = None,
    ) -> ConversionReport:
        """执行转换（进度回调 stage/pct/msg）。

        输入文件须先经 :meth:`set_input_path` 设置（缺省拒绝执行）。
        输出目录 = :meth:`set_output_dir` 或 ``cfg.engine.output_dir``。
        """
        if self._input_path is None or not self._input_path.exists():
            raise ControllerError("请先选择输入文件（.dsn/.edf）再运行转换")
        output_dir = self._output_dir or Path(cfg.engine.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        engine = ConversionEngine()
        try:
            report = engine.convert_with_cfg(
                cfg,
                self._input_path,
                output_dir,
                progress_callback=cb,
                hdl_lib_path=Path(cfg.input.hdl_lib) if cfg.input.hdl_lib else None,
                extra_lib_paths=[Path(p) for p in cfg.input.extra_hdl_libs],
            )
        except Exception as exc:  # noqa: BLE001 — 转换失败包装
            logger.exception("GUI conversion failed")
            raise ControllerError(f"转换失败: {exc}") from exc
        self._last_report = report
        self._last_output_dir = output_dir
        return report

    # ── 报告与手动干预（§3.1 ⑪⑫） ───────────────────────────────────────

    def get_report(self, kind: str) -> str:
        """获取报告内容（aesthetic/ioport/mapping/error）。

        优先读上次转换输出目录中的报告文件；缺失时回退 ConversionReport
        摘要文本（不抛错，UI 可空态展示）。
        """
        if self._last_output_dir is None:
            return "（尚未运行转换）"
        out = self._last_output_dir
        project = self._last_report.project_name if self._last_report else ""
        candidates: dict[str, list[str]] = {
            "aesthetic": ["aesthetic_report.txt"],
            "ioport": ["ioport_audit_report.txt"],
            "mapping": [
                f"{project}_mapping.csv" if project else "",
                f"{project}_top3.txt" if project else "",
                "mapping_report.txt",
            ],
            "error": [
                f"{project}_error.log" if project else "",
                "error_report.txt",
                "error.log",
            ],
        }
        for name in candidates.get(kind, []):
            if not name:
                continue
            p = out / name
            if p.exists():
                try:
                    return p.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    return f"（读取报告失败: {exc}）"
        return self._report_fallback(kind)

    def get_unmatched(self) -> list[UnmatchedEntry]:
        """未匹配元件列表（FR3）：MANUAL 策略或置信度 < 0.85。"""
        if self._last_report is None or not self._last_report.match_results:
            return []
        entries: list[UnmatchedEntry] = []
        for mr in self._last_report.match_results:
            strategy = str(getattr(mr, "strategy", "") or "")
            confidence = float(getattr(mr, "confidence", 0.0) or 0.0)
            if strategy == "MANUAL" or confidence < 0.85:
                rec = ""
                extras = getattr(mr, "extra_data", None) or {}
                if isinstance(extras, dict):
                    rec = str(extras.get("top1_library_id", "") or "")
                entries.append(UnmatchedEntry(
                    refdes=str(getattr(mr, "source_library_id", "") or ""),
                    source_library_id=str(getattr(mr, "source_library_id", "") or ""),
                    confidence=confidence,
                    strategy=strategy,
                    recommended_hdl=rec,
                ))
        return entries

    def set_manual_match(
        self, refdes: str, hdl: str | None, force_mock: bool = False,
    ) -> None:
        """手动指定匹配 / 强制 mock（写回 yaml match.manual_overrides）。

        - ``hdl`` 非空 → 记录 refdes→hdl 并写 chip_config.yaml（v2.0 schema，
          后端 :class:`ManualMatchesConfig.write_yaml`），再把
          ``cfg.match.manual_overrides.file`` 指向该文件（下次转换生效）。
        - ``hdl`` 为空 → 从缓存移除该 refdes（撤销手动指定）。
        - ``force_mock`` → 确保 refdes 的 prefix 进入 ``match.mock.prefixes``。
        """
        refdes = (refdes or "").strip()
        if not refdes:
            raise ControllerError("手动匹配需要 refdes")
        if hdl:
            self._manual_overrides[refdes] = hdl
        else:
            self._manual_overrides.pop(refdes, None)
        self._flush_manual_overrides()
        if force_mock and refdes:
            prefix = refdes[0].upper()
            if prefix not in self._cfg.match.mock.prefixes:
                self._cfg.match.mock.prefixes.append(prefix)

    def toggle_mock_prefix(self, prefix: str, enabled: bool) -> None:
        """强制 mock 前缀开关（J/T/U/IC；ManualMatchPanel 复选框）。"""
        prefix = (prefix or "").upper()
        prefixes = self._cfg.match.mock.prefixes
        if enabled and prefix not in prefixes:
            prefixes.append(prefix)
        elif not enabled and prefix in prefixes:
            prefixes.remove(prefix)

    # ── 扩展：保存 / 验证 ─────────────────────────────────────────────────

    def save_pipeline(self, path: Path | None = None) -> Path:
        """原子写当前配置到 pipeline.yaml（§4 保存通道）。

        ``path`` 缺省 = 定位到的 pipeline.yaml（无则 CWD/pipeline.yaml）。
        """
        from .yaml_bridge import save_pipeline_atomic

        target = Path(path) if path is not None else (
            self._pipeline_path or Path("pipeline.yaml")
        )
        save_pipeline_atomic(target, self._cfg)
        self._pipeline_path = target
        return target

    def run_verify(self, suites: list[str] | None = None) -> list[str]:
        """侧边栏 verify 快捷入口（FR6；VerificationRunner）。"""
        from ..verify import VerificationRunner

        report = VerificationRunner(self._cfg).run(suites=suites)
        return list(report.lines)

    # ── 内部 ──────────────────────────────────────────────────────────────

    def _load_default_config(self) -> PipelineConfig:
        """初始配置：pipeline.yaml → 当前 profile（权威）。"""
        if self._pipeline_path is not None:
            try:
                cfg = PipelineConfig.from_yaml(self._pipeline_path)
            except Exception as exc:  # noqa: BLE001 — 损坏配置回退默认
                logger.warning("pipeline.yaml 解析失败，使用默认: %s", exc)
                cfg = PipelineConfig()
        else:
            cfg = PipelineConfig()
        with contextlib.suppress(ProfileError):
            cfg = self._pm.get(cfg.profile)  # profile 缺失 → 保留 yaml/默认配置
        return cfg

    def _find_spec(self, name: str) -> PluginSpec:
        specs = [s for s in self._plugin_mgr.list_plugins() if s.name == name]
        if not specs:
            raise ControllerError(f"未知插件: {name!r}")
        return specs[0]

    def _param_source(self, spec: PluginSpec) -> Any:
        """插件参数源对象（默认配置；schema 类型/默认值推断用）。"""
        defaults = PipelineConfig()
        if spec.stage == "beautify":
            base: Any = defaults.beautify.params
        elif spec.stage == "match":
            base = defaults.match
        elif spec.stage == "test":
            base = defaults.test
        elif spec.stage == "input":
            base = defaults.input
        elif spec.stage == "output":
            base = defaults.output
        else:
            base = None
        if spec.param_section and base is not None:
            base = getattr(base, spec.param_section, None)
        return base

    @staticmethod
    def _to_meta(spec: PluginSpec) -> PluginMeta:
        return PluginMeta(
            name=spec.name,
            stage=spec.stage,
            description=spec.description or "",
            builtin=spec.builtin,
            param_section=spec.param_section or "",
            param_fields=tuple(spec.param_fields or ()),
        )

    def _report_fallback(self, kind: str) -> str:
        """报告文件缺失时的摘要回退（不抛错）。"""
        if self._last_report is None:
            return "（尚未运行转换）"
        r = self._last_report
        if kind == "aesthetic":
            return (
                f"[aesthetic 报告摘要]\n"
                f"页面: {r.pages}  元件: {r.instances}  网络: {r.nets}\n"
                f"输出文件: {len(r.output_files)}\n"
                f"（完整 aesthetic_report.txt 由 csa 插件在转换时写出）"
            )
        if kind == "ioport":
            return (
                "[ioport 报告摘要]\n"
                "（ioport_audit_report.txt 由 csa 插件在转换时写出）"
            )
        if kind == "mapping":
            lines = [f"[mapping 报告摘要] 匹配 {len(r.match_results)} 项"]
            for m in r.match_results[:50]:
                lines.append(
                    f"  {getattr(m, 'source_library_id', '?')} → "
                    f"{getattr(m, 'target_library_id', '(无)')} "
                    f"({getattr(m, 'strategy', '?')} "
                    f"{getattr(m, 'confidence', 0.0):.0%})"
                )
            return "\n".join(lines)
        if kind == "error":
            if r.errors:
                return "\n".join(f"  [ERROR] {e}" for e in r.errors)
            if r.warnings:
                return "\n".join(f"  [WARN] {w}" for w in r.warnings)
            return "[error 报告] 无错误，转换成功"
        return "（未知报告类型）"

    def _flush_manual_overrides(self) -> None:
        """把缓存的手动匹配写为 chip_config.yaml（v2.0 schema）并接线。"""
        if not self._manual_overrides:
            self._cfg.match.manual_overrides.file = ""
            return
        from ..core.matcher.manual_matches import (
            ManualMatch,
            ManualMatchesConfig,
        )

        out_dir = self._output_dir or Path(self._cfg.engine.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        chip_path = out_dir / "chip_config_gui.yaml"
        cfg = ManualMatchesConfig(matches=[
            ManualMatch(refdes=refdes, library_id=hdl)
            for refdes, hdl in sorted(self._manual_overrides.items())
        ])
        cfg.write_yaml(chip_path)
        self._cfg.match.manual_overrides.file = str(chip_path)
