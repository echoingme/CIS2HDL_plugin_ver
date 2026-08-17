"""CIS2HDL 新 CLI（S1 配置层，§6）。

设计依据：``docs/S1-config-design.md`` §6（架构师高见远交付）。

结构::

    cis2hdl                              # 无参数 → GUI（保留）
    cis2hdl gui                          # GUI（保留）
    cis2hdl convert <input> [options]    # 读 pipeline.yaml + --profile + 旧参数映射
    cis2hdl profile list|show|create|delete|export|import
    cis2hdl verify [--suite NAME ...]    # S8 运行 test.suites 验证套件（FR6）
    cis2hdl --version                    # 版本

convert 解析流程（§6.2）:
  1. 定位 pipeline.yaml：--pipeline <path> → ./pipeline.yaml → <pkg>/config/pipeline.yaml
     → 都不存在则用 PipelineConfig()（纯默认）
  2. cfg = PipelineConfig.from_yaml(path)
  3. 若 --profile <name> 给出：cfg = ProfileManager.get(name)
  4. 旧 CLI 参数逐个映射覆盖 cfg（§6.3）+ deprecation 警告（每参数一次）
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
# 旧 CLI 参数 → yaml 字段迁移对照表（§6.3 全量 23 个；S10 前保留）
# ─────────────────────────────────────────────────────────────────────────────

#: {flag: yaml 路径提示}——deprecation 警告文案用。
_LEGACY_DEPRECATION_TARGETS: dict[str, str] = {
    "--output": "engine.output_dir",
    "--hdl-lib": "input.hdl_lib",
    "--extra-hdl-lib": "input.extra_hdl_libs",
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

_MIGRATION_REF = "docs/S1-config-design.md §6.3 迁移表"


def _deprecation_warn(flag: str, warned: set[str]) -> None:
    """打印 deprecation 警告到 stderr（每个参数仅一次，set 去重）。"""
    if flag in warned:
        return
    warned.add(flag)
    target = _LEGACY_DEPRECATION_TARGETS.get(flag, flag)
    print(
        f"[deprecation] {flag} 已废弃，将在 S10 移除；"
        f"请改用 pipeline.yaml: {target}（见 {_MIGRATION_REF}）",
        file=sys.stderr,
    )


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

    # ── 旧参数（S10 前保留，映射 + deprecation 警告） ──
    p.add_argument("--output", metavar="DIR", help="输出目录")
    p.add_argument("--hdl-lib", metavar="DIR", help="主 HDL 元件库路径")
    p.add_argument("--extra-hdl-lib", metavar="DIR", action="append", default=[],
                   help="附加 HDL 库（可多次）")
    p.add_argument("--benchmark", action="store_true", help="性能基准报告")
    p.add_argument("--max-workers", metavar="N", type=int, help="并行度")
    p.add_argument("--routing", metavar="MODE", help="p0|detour|edif_reuse")
    p.add_argument("--nonuniform-tracks", action="store_true", help="非均匀轨道")
    p.add_argument("--net-order", metavar="ORDER", help="short_first|long_first")
    p.add_argument("--wire-simplify", action="store_true", help="电线化简")
    p.add_argument("--manual-matches", metavar="FILE", help="手动匹配（别名）")
    p.add_argument("--chip-config", metavar="FILE", help="chip_config.yaml（v2.0 主入口）")
    p.add_argument("--export-unmatched", metavar="OUT", help="未匹配导出路径")
    p.add_argument("--text-layout", action="store_true", help="文本/标签去冲突")
    p.add_argument("--power-ic", action="store_true", help="电源芯片匹配")
    p.add_argument("--aesthetic", action="store_true", help="极致美化（复合置位）")
    p.add_argument("--gnd-distribute", action="store_true", help="GND 符号分布")
    p.add_argument("--rotate-passives", action="store_true", help="被动元件方向随连线")
    p.add_argument("--ioport-edge", action="store_true", help="跨页 IOPORT 边缘分布")
    p.add_argument("--ioport-audit", action="store_true", help="IOPORT 一致性核对")
    p.add_argument("--use-net-name", action="store_true", help="跨页网用网络名表达")
    p.add_argument("--no-mirror-normalize", action="store_true", help="关闭镜像归一化")
    p.add_argument("--no-report", action="store_true", help="关闭默认诊断报告")
    p.add_argument("--cross-page-opt", action="store_true", help="跨页网视觉优化")
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


def _apply_legacy_args(cfg: PipelineConfig, args: argparse.Namespace, warned: set[str]) -> None:
    """旧 CLI 参数逐个映射覆盖 cfg（§6.3 全量 23 个）+ deprecation 警告。

    显式旧参数优先级高于 yaml/profile（与现有"CLI 覆盖 yaml"语义一致）。
    ``--aesthetic`` 复合展开与旧 __main__.py 逐行一致（保 FR9 严格等价）。
    """
    if args.output is not None:
        _deprecation_warn("--output", warned)
        cfg.engine.output_dir = str(args.output)
    if args.hdl_lib is not None:
        _deprecation_warn("--hdl-lib", warned)
        cfg.input.hdl_lib = str(args.hdl_lib)
    if args.extra_hdl_lib:
        _deprecation_warn("--extra-hdl-lib", warned)
        cfg.input.extra_hdl_libs = [str(x) for x in args.extra_hdl_lib]
    if args.benchmark:
        _deprecation_warn("--benchmark", warned)
        cfg.engine.benchmark = True
    if args.max_workers is not None:
        _deprecation_warn("--max-workers", warned)
        cfg.engine.max_workers = int(args.max_workers)

    if args.routing is not None:
        _deprecation_warn("--routing", warned)
        if args.routing in ("p0", "detour", "edif_reuse"):
            cfg.beautify.params.mode = args.routing
        else:
            print(
                f"Warning: unknown --routing {args.routing!r} "
                "(p0|detour|edif_reuse) — using p0",
            )
    if args.nonuniform_tracks:
        _deprecation_warn("--nonuniform-tracks", warned)
        cfg.beautify.params.nonuniform_tracks = True
    if args.net_order is not None:
        _deprecation_warn("--net-order", warned)
        if args.net_order in ("short_first", "long_first"):
            cfg.beautify.params.net_order = args.net_order
        else:
            print(
                f"Warning: unknown --net-order {args.net_order!r} "
                "(short_first|long_first) — using long_first",
            )
    if args.wire_simplify:
        _deprecation_warn("--wire-simplify", warned)
        cfg.beautify.params.wire_simplify.enabled = True

    if args.manual_matches is not None:
        _deprecation_warn("--manual-matches", warned)
        cfg.match.manual_overrides.file = str(args.manual_matches)
    if args.chip_config is not None:
        _deprecation_warn("--chip-config", warned)
        # v2.0 主入口：同时给出时 chip_config 覆盖 manual_matches
        cfg.match.manual_overrides.file = str(args.chip_config)
    if args.export_unmatched is not None:
        _deprecation_warn("--export-unmatched", warned)
        cfg.match.manual_overrides.export_unmatched = str(args.export_unmatched)

    if args.text_layout:
        _deprecation_warn("--text-layout", warned)
        cfg.beautify.params.text_layout.enabled = True
    if args.power_ic:
        _deprecation_warn("--power-ic", warned)
        cfg.beautify.params.power_ic.enabled = True
    if args.aesthetic:
        _deprecation_warn("--aesthetic", warned)
        # §6.3 --aesthetic 复合展开（8 字段；与旧 __main__.py 逐行一致）
        cfg.beautify.params.aesthetic.enabled = True
        cfg.beautify.params.text_layout.enabled = True
        cfg.beautify.params.overlap.check = True
        cfg.beautify.params.power_ic.enabled = True
        # 仅当用户未显式 --routing 且 mode==p0 时置 detour（保严格等价）
        if args.routing is None and cfg.beautify.params.mode == "p0":
            cfg.beautify.params.mode = "detour"
        cfg.beautify.params.ioport.edge_layout = True
        cfg.beautify.params.gnd_distribution.enabled = True
        cfg.beautify.params.ioport.audit = True
    if args.gnd_distribute:
        _deprecation_warn("--gnd-distribute", warned)
        cfg.beautify.params.gnd_distribution.enabled = True
        cfg.beautify.params.gnd_distribution.distribute_density = True
    if args.rotate_passives:
        _deprecation_warn("--rotate-passives", warned)
        cfg.beautify.params.placement.rotate_passives = True
    if args.ioport_edge:
        _deprecation_warn("--ioport-edge", warned)
        cfg.beautify.params.ioport.edge_layout = True
    if args.ioport_audit:
        _deprecation_warn("--ioport-audit", warned)
        cfg.beautify.params.ioport.audit = True
    if args.use_net_name:
        _deprecation_warn("--use-net-name", warned)
        cfg.beautify.params.ioport.use_net_name = True
    if args.no_mirror_normalize:
        _deprecation_warn("--no-mirror-normalize", warned)
        cfg.beautify.params.mirror.normalize = False
    if args.no_report:
        _deprecation_warn("--no-report", warned)
        cfg.beautify.params.report.always_write = False
    if args.cross_page_opt:
        _deprecation_warn("--cross-page-opt", warned)
        cfg.beautify.params.cross_page_opt = True


def convert_main(argv: list[str]) -> int:
    """convert 分支：新解析流程（§6.2）。"""
    parser = _build_convert_parser()
    args = parser.parse_args(argv)

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

    warned: set[str] = set()
    _apply_legacy_args(cfg, args, warned)

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
