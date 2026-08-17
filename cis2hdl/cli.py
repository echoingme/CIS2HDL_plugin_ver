"""CIS2HDL 新 CLI（S1 配置层，§6；S10 兼容窗口结束）。

设计依据：``docs/S1-config-design.md`` §6（架构师高见远交付）+ S10 交付。

结构::

    cis2hdl                              # 无参数 → GUI（保留）
    cis2hdl gui                          # GUI（保留）
    cis2hdl convert <input> [options]    # 读 pipeline.yaml + --profile + 路径类参数
    cis2hdl profile list|show|create|delete|export|import
    cis2hdl verify [--suite NAME ...]    # S8 运行 test.suites 验证套件（FR6）
    cis2hdl --version                    # 版本

convert 解析流程（§6.2；S10 起）:
  1. 定位 pipeline.yaml：--pipeline <path> → ./pipeline.yaml → <pkg>/config/pipeline.yaml
     → 都不存在则用 PipelineConfig()（纯默认）
  2. cfg = PipelineConfig.from_yaml(path)
  3. 若 --profile <name> 给出：cfg = ProfileManager.get(name)
  4. 路径类 CLI 参数（--output/--hdl-lib/--extra-hdl-lib）覆盖 cfg（S10 保留）；
     其余旧行为参数（--routing/--aesthetic/... 共 20 个）已在 S10 移除——
     传入时报错并提示迁移至 pipeline.yaml 字段 / --profile
  5. rc = cfg.to_routing_config()；写回全局 Config 单例 routing + app
  6. ConversionEngine.convert(...)（引擎零改动）

verify 流程（S8 §）:
  1. 定位 pipeline.yaml（同 convert）；cfg = PipelineConfig.from_yaml(path)
  2. 可选 --profile 覆盖；可选 --suite 过滤（默认 cfg.test.suites 全部）
  3. VerificationRunner(cfg).run(suites) → 打印报告行
  4. 退出码 0=通过；1=存在 [FAIL]/[ERROR] 或未知套件/配置错误

退出码：0 成功；1 转换/运行错误；2 profile 查重/校验失败；3 内置只读/禁止操作。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from cis2hdl import __version__

from .core.config import Config
from .core.engine.conversion_engine import ConversionEngine
from .core.pipeline_config import PipelineConfig
from .core.profile_manager import (
    DuplicateProfileError,
    ProfileError,
    ProfileManager,
    ProfileReadOnlyError,
)

__all__ = ["main", "gui_main", "convert_main", "profile_main", "verify_main"]

# ─────────────────────────────────────────────────────────────────────────────
# S10 移除的旧 CLI 参数 → pipeline.yaml 字段迁移提示（兼容窗口结束）
# ─────────────────────────────────────────────────────────────────────────────

#: {flag: yaml 字段提示}——旧参数报错文案用（S10 起仅报错，不再映射）。
#: 权威对照表：docs/archive/temp files/phase24-cli-yaml-migration.md（归档参考）。
_REMOVED_FLAGS_TARGETS: dict[str, str] = {
    "--benchmark": "engine.benchmark",
    "--max-workers": "engine.max_workers",
    "--routing": "beautify.params.routing.mode",
    "--nonuniform-tracks": "beautify.params.routing.nonuniform_tracks",
    "--net-order": "beautify.params.routing.net_order",
    "--wire-simplify": "beautify.params.wire_simplify.enabled",
    "--manual-matches": "match.manual_overrides.file",
    "--chip-config": "match.manual_overrides.file",
    "--export-unmatched": "match.manual_overrides.export_unmatched",
    "--text-layout": "beautify.params.text_layout.enabled",
    "--power-ic": "beautify.params.power_ic.enabled",
    "--aesthetic": "beautify.params.* 对应字段（--profile max-beauty 可近似）",
    "--gnd-distribute": "beautify.params.gnd_distribution.enabled + .distribute_density",
    "--rotate-passives": "beautify.params.placement.rotate_passives",
    "--ioport-edge": "beautify.params.ioport.edge_layout",
    "--ioport-audit": "beautify.params.ioport.audit",
    "--use-net-name": "beautify.params.ioport.use_net_name",
    "--no-mirror-normalize": "beautify.params.mirror.normalize",
    "--no-report": "beautify.params.report.always_write",
    "--cross-page-opt": "beautify.params.routing.cross_page_opt",
}

_MIGRATION_REF = "docs/archive/temp files/phase24-cli-yaml-migration.md"


# ─────────────────────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """Main entry point。无参数 → GUI；'convert'/'profile'/'verify' → 新 CLI 分支。"""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        return gui_main([])
    cmd = args[0]
    if cmd == "gui":
        return gui_main(args[1:])
    if cmd in ("-v", "--version", "version"):
        print(f"CIS2HDL v{__version__}")
        return 0
    if cmd == "convert":
        return convert_main(args[1:])
    if cmd == "profile":
        return profile_main(args[1:])
    if cmd == "verify":
        return verify_main(args[1:])
    _print_usage()
    return 1


def gui_main(argv: list[str] | None = None) -> int:
    """GUI 子命令（S9）：启动工程工作台（v2）；无 PySide6 时优雅降级。

    返回 QApplication.exec 退出码；PySide6 缺失 → 友好提示 + 退出码 1
    （不抛 traceback）。
    """
    del argv  # GUI 不接受额外参数（预留）
    try:
        from cis2hdl.gui.v2.app import run_gui
    except ImportError as exc:
        print(f"Error: 无法启动 GUI（缺少 PySide6）: {exc}", file=sys.stderr)
        print("请先安装依赖：pip install PySide6", file=sys.stderr)
        return 1
    try:
        return run_gui()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _print_usage() -> None:
    print(f"CIS2HDL v{__version__} — OrCAD CIS to HDL Schematic Converter")
    print("Usage:")
    print("  cis2hdl                        Launch GUI")
    print("  cis2hdl gui                    Launch GUI")
    print("  cis2hdl convert <input> [options]")
    print("  cis2hdl profile list|show|create|delete|export|import")
    print("  cis2hdl verify [--suite unit|e2e|qa_package] [--pipeline PATH] [--profile NAME]")
    print("  cis2hdl --version")


# ─────────────────────────────────────────────────────────────────────────────
# convert 分支（§6.2 / §6.3）
# ─────────────────────────────────────────────────────────────────────────────


def _build_convert_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cis2hdl convert", add_help=True)
    p.add_argument("input", nargs="?", help="输入文件 (.dsn/.edf)")
    p.add_argument("--pipeline", metavar="PATH", help="显式 pipeline.yaml 路径")
    p.add_argument("--profile", metavar="NAME", help="使用内置/自定义 profile")

    # ── 保留的路径类参数（S10 起仅这些行为参数 + --profile/--pipeline）──
    # 其余旧行为参数（--routing/--aesthetic/... 共 20 个）已在 S10 移除，
    # 传入时由 convert_main 报错并提示迁移（见 _REMOVED_FLAGS_TARGETS）。
    p.add_argument("--output", metavar="DIR", help="输出目录（engine.output_dir）")
    p.add_argument("--hdl-lib", metavar="DIR", help="主 HDL 元件库路径（input.hdl_lib）")
    p.add_argument("--extra-hdl-lib", metavar="DIR", action="append", default=[],
                   help="附加 HDL 库（input.extra_hdl_libs，可多次）")
    return p


def _locate_pipeline(explicit: str | None) -> Path | None:
    """定位 pipeline.yaml：--pipeline → ./pipeline.yaml → <pkg>/config/pipeline.yaml。"""
    if explicit:
        p = Path(explicit)
        if not p.exists():
            raise FileNotFoundError(f"pipeline.yaml 不存在: {p}")
        return p
    candidates = [
        Path("pipeline.yaml"),
        Path(__file__).resolve().parent / "config" / "pipeline.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _apply_path_args(cfg: PipelineConfig, args: argparse.Namespace) -> None:
    """保留的路径类 CLI 参数 → cfg 覆盖（S10 起仅路径类，无 deprecation）。

    优先级与旧 CLI 一致：显式路径参数 > yaml/profile（CLI 覆盖 yaml 语义）。
    """
    if args.output is not None:
        cfg.engine.output_dir = str(args.output)
    if args.hdl_lib is not None:
        cfg.input.hdl_lib = str(args.hdl_lib)
    if args.extra_hdl_lib:
        cfg.input.extra_hdl_libs = [str(x) for x in args.extra_hdl_lib]


def convert_main(argv: list[str]) -> int:
    """convert 分支：新解析流程（§6.2；S10 起旧参数报错）。"""
    parser = _build_convert_parser()
    args, unknown = parser.parse_known_args(argv)

    # S10 兼容窗口结束：识别已移除的旧行为参数 → 报错并提示迁移。
    # 用 parse_known_args 拦截（旧参数未注册，直接 parse_args 只会报
    # "unrecognized arguments"，无法给出迁移指引）。
    for flag in unknown:
        key = flag.split("=", 1)[0]
        if key in _REMOVED_FLAGS_TARGETS:
            parser.error(
                f"{key} 已移除（S10 兼容窗口结束）：该功能已迁移至 "
                f"pipeline.yaml 的 {_REMOVED_FLAGS_TARGETS[key]}，"
                f"请用 --profile 或修改 pipeline.yaml 配置"
                f"（迁移对照表见 {_MIGRATION_REF}）"
            )
    if unknown:
        parser.error(f"unrecognized arguments: {' '.join(unknown)}")

    if not args.input:
        parser.error("convert 需要输入文件")
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        return 1

    try:
        pipeline_path = _locate_pipeline(args.pipeline)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1
    cfg = PipelineConfig.from_yaml(pipeline_path) if pipeline_path else PipelineConfig()

    if args.profile:
        try:
            cfg = ProfileManager().get(args.profile)
        except ProfileError as exc:
            print(f"Error: {exc}")
            return 2

    _apply_path_args(cfg, args)

    cfg_obj = Config.get()
    cfg_obj.routing = cfg.to_routing_config()
    cfg_obj.app.max_workers = cfg.engine.max_workers
    cfg_obj.app.benchmark = cfg.engine.benchmark

    try:
        engine = ConversionEngine()
        report = engine.convert(
            input_path,
            Path(cfg.engine.output_dir),
            hdl_lib_path=Path(cfg.input.hdl_lib) if cfg.input.hdl_lib else None,
            config_file=None,
            extra_lib_paths=[Path(p) for p in cfg.input.extra_hdl_libs],
        )
    except Exception as exc:  # noqa: BLE001 — CLI 顶层捕获
        print(f"Error: conversion failed: {exc}")
        return 1

    print(f"Conversion complete: {report}")
    if cfg_obj.app.benchmark:
        print()
        print(report.benchmark_report())
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# profile 子命令（§6.4）
# ─────────────────────────────────────────────────────────────────────────────


def _profile_list(pm: ProfileManager) -> None:
    print(f"{'NAME':<20} {'BUILTIN':<8} DESCRIPTION")
    for info in pm.list_profiles():
        builtin = "yes" if info.builtin else "no"
        print(f"{info.name:<20} {builtin:<8} {info.description}")


def _profile_show(pm: ProfileManager, name: str) -> int:
    try:
        cfg = pm.get(name)
    except ProfileError as exc:
        print(f"Error: {exc}")
        return 2
    text = yaml.safe_dump(
        cfg.to_dict(), allow_unicode=True, sort_keys=False, default_flow_style=None,
    )
    print(text, end="")
    return 0


def _profile_create(pm: ProfileManager, argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="cis2hdl profile create")
    p.add_argument("name")
    p.add_argument("--from-file", metavar="PATH", help="源 pipeline.yaml（缺省当前 pipeline.yaml）")
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args(argv)
    try:
        if args.from_file:
            cfg = PipelineConfig.from_yaml(Path(args.from_file))
        else:
            pipe = _locate_pipeline(None)
            cfg = PipelineConfig.from_yaml(pipe) if pipe else PipelineConfig()
        pm.create(args.name, cfg, overwrite=args.overwrite)
    except DuplicateProfileError as exc:
        print(f"Error: {exc}")
        return 2
    except ProfileReadOnlyError as exc:
        print(f"Error: {exc}")
        return 3
    except (ProfileError, FileExistsError) as exc:
        print(f"Error: {exc}")
        return 2
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1
    if pm.last_note:
        print(pm.last_note)
    print(f"profile 已保存: {pm.profiles_dir / args.name}.yaml")
    return 0


def _profile_delete(pm: ProfileManager, argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="cis2hdl profile delete")
    p.add_argument("name")
    args = p.parse_args(argv)
    try:
        pm.delete(args.name)
    except ProfileReadOnlyError as exc:
        print(f"Error: {exc}")
        return 3
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1
    print(f"profile 已删除: {args.name}")
    return 0


def _profile_export(pm: ProfileManager, argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="cis2hdl profile export")
    p.add_argument("name")
    p.add_argument("-o", "--output", metavar="OUT", help="导出路径（缺省 profiles/export_<name>_<ts>.yaml）")
    args = p.parse_args(argv)
    try:
        out = pm.export(args.name, Path(args.output) if args.output else None)
    except ProfileReadOnlyError as exc:
        print(f"Error: {exc}")
        return 3
    except ProfileError as exc:
        print(f"Error: {exc}")
        return 2
    print(f"已导出: {out}")
    return 0


def _profile_import(pm: ProfileManager, argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="cis2hdl profile import")
    p.add_argument("path")
    p.add_argument("--rename", metavar="NAME", help="改名导入（解决名称冲突）")
    args = p.parse_args(argv)
    try:
        name = pm.import_file(Path(args.path), rename_to=args.rename)
    except ProfileReadOnlyError as exc:
        print(f"Error: {exc}")
        return 3
    except (ProfileError, FileExistsError) as exc:
        print(f"Error: {exc}")
        return 2
    print(f"已导入: {pm.profiles_dir / name}.yaml")
    return 0


def profile_main(argv: list[str]) -> int:
    """profile 子命令分发（§6.4）。退出码 0/1/2/3。"""
    if not argv:
        _print_profile_usage()
        return 1
    sub = argv[0]
    pm = ProfileManager()
    if sub == "list":
        _profile_list(pm)
        return 0
    if sub == "show":
        if len(argv) < 2:
            print("Error: profile show 需要 <name>")
            return 1
        return _profile_show(pm, argv[1])
    if sub == "create":
        return _profile_create(pm, argv[1:])
    if sub == "delete":
        return _profile_delete(pm, argv[1:])
    if sub == "export":
        return _profile_export(pm, argv[1:])
    if sub == "import":
        return _profile_import(pm, argv[1:])
    _print_profile_usage()
    return 1


def _print_profile_usage() -> None:
    print("Usage:")
    print("  cis2hdl profile list")
    print("  cis2hdl profile show <name>")
    print("  cis2hdl profile create <name> [--from-file <pipeline.yaml>] [--overwrite]")
    print("  cis2hdl profile delete <name>")
    print("  cis2hdl profile export <name> [-o <out.yaml>]")
    print("  cis2hdl profile import <path> [--rename <NAME>]")


# ─────────────────────────────────────────────────────────────────────────────
# verify 子命令（S8/FR6：测试插件化独立入口）
# ─────────────────────────────────────────────────────────────────────────────


def verify_main(argv: list[str]) -> int:
    """verify 子命令：运行 test.suites 指定的验证套件（S8/FR6）。

    流程：定位 pipeline.yaml（同 convert）→ PipelineConfig → 可选
    --profile 覆盖 → VerificationRunner.run(suites) → 打印报告行。
    退出码：0 通过；1 存在 [FAIL]/[ERROR] 结果 / 未知套件 / 配置错误。
    """
    p = argparse.ArgumentParser(prog="cis2hdl verify")
    p.add_argument("--suite", action="append", metavar="NAME",
                   help="仅运行指定套件（unit|e2e|qa_package，可多次；缺省 test.suites 全部）")
    p.add_argument("--pipeline", metavar="PATH", help="显式 pipeline.yaml 路径")
    p.add_argument("--profile", metavar="NAME", help="使用内置/自定义 profile")
    args = p.parse_args(argv)

    try:
        pipeline_path = _locate_pipeline(args.pipeline)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1
    cfg = PipelineConfig.from_yaml(pipeline_path) if pipeline_path else PipelineConfig()

    if args.profile:
        try:
            cfg = ProfileManager().get(args.profile)
        except ProfileError as exc:
            print(f"Error: {exc}")
            return 2

    try:
        from .verify import VerificationRunner

        report = VerificationRunner(cfg).run(suites=args.suite)
    except Exception as exc:  # noqa: BLE001 — CLI 顶层捕获
        print(f"Error: verify 失败: {exc}")
        return 1

    for line in report.lines:
        print(line)
    if report.failed:
        print("verify 失败（存在 FAIL/ERROR 结果）")
        return 1
    print("verify 通过")
    return 0
