"""CIS2HDL entry point — CLI or GUI（S9：gui 子命令启动工程工作台 v2）。"""

import sys


def _dispatch(argv: list[str] | None = None) -> int:
    """显式分发：``gui`` 子命令 → gui_main；其余 → cli.main（兼容无参数启动 GUI）。"""
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "gui":
        from cis2hdl.cli import gui_main

        return gui_main(args[1:])
    from cis2hdl.cli import main

    return main(args)


if __name__ == "__main__":
    sys.exit(_dispatch())
