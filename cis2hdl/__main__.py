"""CIS2HDL entry point — CLI or GUI（S1 起转发到 cis2hdl.cli.main）。"""

import sys

from cis2hdl.cli import main

if __name__ == "__main__":
    sys.exit(main())
