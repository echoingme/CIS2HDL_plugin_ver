"""ORIGIN 依赖链审计（Phase XVIII R4/Q1）。

Q1 用户决策：所有匹配函数只能在 hdl_lib 匹配符号，不能使用系统库符号
（含 ORIGIN）。本模块全量扫描 hdl_lib symbol.css 与输出 CSA 页：

1. hdl_lib 内任何 symbol.css 不得出现 ORIGIN 系统库引用；
2. 输出 CSA 任何 ``CDS_LIB`` 值必须 ∈ {hdl_lib, temp_lib}；
3. 输出 CSA 不得出现 ORIGIN 引用。

返回违规清单（空 = 通过）；由 T05 打包门禁自动调用（``attribute.
rewrite_origin`` 开启时违规可改写为 hdl_lib 自引用）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

#: 输出 CSA 允许的 CDS_LIB 库名（hdl_lib + mock temp_lib）。
_ALLOWED_CDS_LIB: frozenset[str] = frozenset({"hdl_lib", "temp_lib"})

#: CDS_LIB 属性行正则：``FORCEPROP <n> LAST CDS_LIB <libname>``
_CDS_LIB_RE = re.compile(
    r"^\s*FORCEPROP\s+\d+\s+LAST\s+CDS_LIB\s+(\S+)",
    re.IGNORECASE,
)


def audit_origin_refs(hdl_lib_root: Path, csa_pages: Iterable[Path]) -> list[str]:
    """全量扫描 hdl_lib symbol.css 与输出 CSA 的 ORIGIN 依赖链。

    断言：
    1. hdl_lib 内 symbol.css 无任何 ORIGIN / 系统库引用；
    2. 输出 CSA 无任何 ORIGIN 引用；
    3. 输出 CSA 的 CDS_LIB 值 ∈ {hdl_lib, temp_lib}（无 hdl_lib 之外的库）。

    Args:
        hdl_lib_root: hdl_lib 库根目录（如 ``output/hdl_lib``）。
        csa_pages: 输出 CSA 页文件路径的可迭代对象。

    Returns:
        违规清单（空 = 通过）。
    """
    violations: list[str] = []
    hdl_root = Path(hdl_lib_root)

    # ── 1. hdl_lib symbol.css ORIGIN / 系统库引用 ─────────────────
    if hdl_root.exists() and hdl_root.is_dir():
        for css in sorted(hdl_root.rglob("symbol.css")):
            try:
                text = css.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                violations.append(f"{css}: read failed: {exc}")
                continue
            for idx, line in enumerate(text.splitlines(), 1):
                if "ORIGIN" in line.upper():
                    violations.append(
                        f"{css}:{idx}: ORIGIN reference: {line.strip()[:120]}"
                    )
                if _CDS_LIB_RE.search(line):
                    lib = _CDS_LIB_RE.search(line).group(1)
                    if lib.lower() not in _ALLOWED_CDS_LIB:
                        violations.append(
                            f"{css}:{idx}: CDS_LIB {lib} not allowed "
                            f"in hdl_lib symbol.css: {line.strip()[:120]}"
                        )
    else:
        violations.append(f"{hdl_root}: hdl_lib root missing")

    # ── 2/3. 输出 CSA：ORIGIN + CDS_LIB 白名单 ────────────────────
    for page in csa_pages or []:
        p = Path(page)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            violations.append(f"{p}: read failed: {exc}")
            continue
        for idx, line in enumerate(text.splitlines(), 1):
            if "ORIGIN" in line.upper():
                violations.append(
                    f"{p}:{idx}: ORIGIN reference: {line.strip()[:120]}"
                )
            m = _CDS_LIB_RE.search(line)
            if m and m.group(1).lower() not in _ALLOWED_CDS_LIB:
                violations.append(
                    f"{p}:{idx}: CDS_LIB {m.group(1)} not in "
                    f"{sorted(_ALLOWED_CDS_LIB)}: {line.strip()[:120]}"
                )
    return violations
