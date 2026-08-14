"""CIS2HDL entry point — CLI or GUI."""

import sys
from pathlib import Path

from cis2hdl import __version__


def main() -> None:
    """Main entry point. No args → GUI. 'convert' → CLI."""
    if len(sys.argv) < 2:
        from cis2hdl.gui.app import run_gui
        run_gui()
        return

    cmd = sys.argv[1]
    if cmd == "convert":
        import cis2hdl as _pkg
        from cis2hdl.core.engine.conversion_engine import ConversionEngine
        from cis2hdl.core.config import config as cfg

        input_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
        output_dir = None
        hdl_lib = None
        extra_hdl_libs: list[Path] = []
        # cis2hdl/config/routing.yaml（包目录下的 config 子目录）
        routing_config = Path(_pkg.__file__).parent / "config" / "routing.yaml"

        def _flag_value(flag: str) -> str | None:
            if flag in sys.argv:
                idx = sys.argv.index(flag)
                if idx + 1 < len(sys.argv):
                    return sys.argv[idx + 1]
            return None

        if "--output" in sys.argv:
            v = _flag_value("--output")
            if v:
                output_dir = Path(v)
        if "--hdl-lib" in sys.argv:
            v = _flag_value("--hdl-lib")
            if v:
                hdl_lib = Path(v)
        if "--extra-hdl-lib" in sys.argv:
            v = _flag_value("--extra-hdl-lib")
            if v:
                extra_hdl_libs.append(Path(v))
        if "--benchmark" in sys.argv:
            cfg.app.benchmark = True
        if "--max-workers" in sys.argv:
            v = _flag_value("--max-workers")
            if v:
                cfg.app.max_workers = int(v)

        # ── Phase XIV D5: 先加载 routing.yaml（默认关），再应用 CLI 覆盖 ──
        if routing_config.exists():
            try:
                cfg.load_from_file(routing_config)
            except Exception as exc:
                print(f"Warning: routing config load failed: {exc}")
        if "--routing" in sys.argv:
            v = _flag_value("--routing")
            if v in ("p0", "detour", "edif_reuse"):
                cfg.routing.mode = v
            else:
                print(f"Warning: unknown --routing {v!r} (p0|detour|edif_reuse) — using p0")
        # Phase XVII R2: 非均匀轨道 + 网布线顺序（SKiDL 思想 A/B 对比）。
        if "--nonuniform-tracks" in sys.argv:
            cfg.routing.nonuniform_tracks = True
        if "--net-order" in sys.argv:
            v = _flag_value("--net-order")
            if v in ("short_first", "long_first"):
                cfg.routing.net_order = v
            else:
                print(
                    f"Warning: unknown --net-order {v!r} "
                    "(short_first|long_first) — using long_first",
                )
        # Phase XVII M4: wire_simplify 后处理 CLI 开关（routing.yaml 等价）。
        if "--wire-simplify" in sys.argv:
            cfg.routing.wire_simplify.enabled = True
        if "--manual-matches" in sys.argv:
            v = _flag_value("--manual-matches")
            if v:
                cfg.routing.manual_matches = v
        # Phase XVII M8（用户 D7）：--chip-config 主入口（统一 chip_config
        # v2.0）；--manual-matches 保留为别名。两者同时存在时 v2.0 覆盖
        # v1.0 同 refdes。
        if "--chip-config" in sys.argv:
            v = _flag_value("--chip-config")
            if v:
                cfg.routing.chip_config = v
        if "--export-unmatched" in sys.argv:
            v = _flag_value("--export-unmatched")
            if v:
                cfg.routing.export_unmatched = v
        if "--text-layout" in sys.argv:
            cfg.routing.text_layout.enabled = True
        if "--power-ic" in sys.argv:
            cfg.routing.power_ic.enabled = True
        if "--aesthetic" in sys.argv:
            cfg.routing.aesthetic.enabled = True
            cfg.routing.text_layout.enabled = True
            cfg.routing.overlap.check = True
            cfg.routing.power_ic.enabled = True
            # Phase XV P1-G（用户反馈"A*美化与普通版无区别"根因）：
            # aesthetic 必须启用美观布线（detour + stub 引出段），
            # 否则电线排布与默认 p0 完全相同。仅当用户未显式 --routing
            # 指定时自动置 detour。
            if "--routing" not in sys.argv and cfg.routing.mode == "p0":
                cfg.routing.mode = "detour"
            # Phase XV P1-C/P1-D（用户决策）：aesthetic 同时启用
            # 跨页口边缘分布 + GND 每芯片分布（硬件设计规范）。
            cfg.routing.ioport.edge_layout = True
            cfg.routing.gnd_distribution.enabled = True
            # Phase XVI（用户决策）：aesthetic 同时开启 IOPORT 一致性核对。
            cfg.routing.ioport.audit = True
        if "--gnd-distribute" in sys.argv:
            cfg.routing.gnd_distribution.enabled = True
            # Phase XXIII P1-3：--gnd-distribute 同时开启密度补点/trunk
            # 避让/outlet 绕行（distribute_density 默认关，默认行为等价）。
            cfg.routing.gnd_distribution.distribute_density = True
        # Phase XXIII P1-4：被动元件符号方向随连线（默认关）。
        if "--rotate-passives" in sys.argv:
            cfg.routing.placement.rotate_passives = True
        if "--ioport-edge" in sys.argv:
            cfg.routing.ioport.edge_layout = True
        if "--ioport-audit" in sys.argv:
            cfg.routing.ioport.audit = True
        # Phase XVII M5（用户 D2）：跨页网用网络名表达（不生成 IOPORT）。
        if "--use-net-name" in sys.argv:
            cfg.routing.ioport.use_net_name = True
        if "--no-mirror-normalize" in sys.argv:
            cfg.routing.mirror.normalize = False
        if "--no-report" in sys.argv:
            # Phase XVI（用户要求默认出报告）：逃生舱关闭默认诊断报告。
            cfg.routing.report.always_write = False
        if "--cross-page-opt" in sys.argv:
            cfg.routing.cross_page_opt = True

        if not input_path or not input_path.exists():
            print(f"Error: file not found: {input_path}")
            sys.exit(1)

        engine = ConversionEngine()
        report = engine.convert(
            input_path, output_dir or Path("output"),
            hdl_lib_path=hdl_lib,
            config_file=None,
            extra_lib_paths=extra_hdl_libs,
        )
        print(f"Conversion complete: {report}")

        if cfg.app.benchmark:
            print()
            print(report.benchmark_report())

    elif cmd == "gui":
        from cis2hdl.gui.app import run_gui
        run_gui()

    else:
        print(f"CIS2HDL v{__version__} — OrCAD CIS to HDL Schematic Converter")
        print("Usage:")
        print("  cis2hdl                        Launch GUI")
        print("  cis2hdl gui                    Launch GUI")
        print(
            "  cis2hdl convert <input> [--output <dir>] [--hdl-lib <dir>] "
            "[--extra-hdl-lib <dir>] [--routing p0|detour|edif_reuse] "
            "[--manual-matches <file.yaml>] [--chip-config <file.yaml>] "
            "[--export-unmatched <out.yaml>] "
            "[--text-layout] [--power-ic] [--aesthetic] [--cross-page-opt] "
            "[--gnd-distribute] [--rotate-passives] [--ioport-edge] [--ioport-audit] "
            "[--use-net-name] [--nonuniform-tracks] "
            "[--net-order short_first|long_first] [--wire-simplify] "
            "[--no-mirror-normalize] [--no-report] "
            "[--benchmark] [--max-workers <n>]  CLI conversion"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
