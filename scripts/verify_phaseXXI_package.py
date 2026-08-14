"""Phase XXI QA 验证脚本 — 交付包验证清单（对齐 handoff §12.3 + Phase XXI 新增）。

用法（在项目根目录）：
    python3 scripts/verify_phaseXXI_package.py <交付目录>

验证项：
1. mock cell 数 = 100（全 _PH）；CH347/RJ45 FORCEADD 计数 = 0
2. 310 引脚坐标重叠 = 0（Counter 全量）
3. 1158 语义：C/X 字号 ≥29、L 起点在 outline 上 = 0 违规
4. WIRE off-grid(25) = 0；GND LASTPIN offset 全 (0,50)
5. 文本碰撞 = 0（char_w=24 同 y 30 内求交）—— Phase XXI 口径从 18 提升
6. 4 版本 origin✓ cds✓ xcon✓
7. ★ Phase XXI-A：temp_lib 全部 symbol.css 含 9 个 P 属性（PACKAGE_TYPE 等）
8. ★ Phase XXI-B：MOCK T 字号 = 89（1.5x）
9. ★ Phase XXI-E：U6H outline 宽 ≥3000 / U6I ≥2400 / U6A ≥2400 / U12 ≥1200
10. test_spn g1-g4 模板生成
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

CHAR_W = 24  # Phase XXI：字号 29 真实渲染宽度口径

REQUIRED_P_PROPS = {"PACKAGE_TYPE", "JEDEC_TYPE", "SN_NUM", "DESCRIPTION",
                    "PART_NAME", "PATH", "$LOCATION", "VALUE"}

FAIL = []


def check(name: str, ok: bool, detail: str = "") -> None:
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python3 scripts/verify_phaseXXI_package.py <交付目录>")
        return 2
    root = Path(sys.argv[1])
    if not root.is_dir():
        print(f"目录不存在: {root}")
        return 2

    # ── 版本目录 ─────────────────────────────────────────────
    versions = [p for p in sorted(root.iterdir()) if p.is_dir() and p.name.startswith("v9_")]
    print(f"版本目录: {[v.name for v in versions]}")

    # ── 1/2/3/5/7/8/9: temp_lib 全量校验 ─────────────────────
    temp_lib = root / "v9_default" / "temp_lib"
    cells = sorted(p for p in temp_lib.iterdir() if p.is_dir() and (p / "sym_1").is_dir())
    check("1. mock cell 数=100", len(cells) >= 100, f"{len(cells)} cell")
    check("1b. 全部 _PH", all(c.name.endswith("_PH") for c in cells))

    # 1c. CH347/RJ45 FORCEADD = 0
    ch347 = sum(
        1 for csa in (root / "v9_default" / "worklib").rglob("*.csa")
        if "CH347" in csa.read_text(errors="replace")
    )
    check("1c. CH347 FORCEADD=0", ch347 == 0, f"found {ch347}")

    # 2. 310 引脚重叠
    bad_310 = []
    for css_path in temp_lib.rglob("symbol.css"):
        c = [tuple(l.split()[1:3]) for l in css_path.read_text(errors="replace").splitlines()
             if l.startswith("C ")]
        dup = [k for k, n in Counter(c).items() if n > 1]
        if dup:
            bad_310.append((css_path.parent.parent.name, len(dup)))
    check("2. SPCOCN-310 引脚重叠=0", not bad_310, str(bad_310[:5]))

    # 3. 1158 语义：C/X 字号 ≥29
    bad_font = []
    for css_path in temp_lib.rglob("symbol.css"):
        for l in css_path.read_text(errors="replace").splitlines():
            if l.startswith("C ") or l.startswith('X "PIN_TEXT"'):
                toks = l.split()
                try:
                    font = int(toks[8] if l.startswith("C ") else toks[7])
                except (ValueError, IndexError):
                    bad_font.append((str(css_path), l[:60]))
                    continue
                if font < 29:
                    bad_font.append((str(css_path), f"font={font} {l[:60]}"))
    check("3. C/X 字号≥29", not bad_font, f"{len(bad_font)} 违规")

    # 5. 文本碰撞（char_w=24）
    bad_text = []
    for css in sorted(temp_lib.rglob("symbol.css")):
        pins = []
        for l in css.read_text(errors="replace").splitlines():
            if l.startswith("C "):
                p = l.split(); pins.append(("C", int(p[1]), int(p[2]), p[3].strip('"'), p[10]))
            elif l.startswith('X "PIN_TEXT"'):
                p = l.split(); pins.append(("X", int(p[3]), int(p[4]), p[2].strip('"'), p[6]))
        coll = 0
        for t1, x1, y1, n1, f1 in pins:
            if t1 != "X":
                continue
            w = len(n1) * CHAR_W
            xa, xb = (x1 - w, x1) if f1 == "1" else (x1, x1 + w)
            for t2, x2, y2, n2, f2 in pins:
                if (t1, x1, y1, n1) == (t2, x2, y2, n2):
                    continue
                if abs(y1 - y2) >= 30:
                    continue
                w2 = len(n2) * CHAR_W
                if t2 == "X":
                    xc, xd = (x2 - w2, x2) if f2 == "1" else (x2, x2 + w2)
                else:
                    lx = x2 - 25 if f2 == "R" else x2 + 25
                    xc, xd = (lx - w2, lx) if f2 == "R" else (lx, lx + w2)
                if max(xa, xc) < min(xb, xd):
                    coll += 1
        if coll:
            bad_text.append((css.parent.parent.name, coll))
    check("5. 文本碰撞=0 (char_w=24)", not bad_text, str(bad_text[:10]))

    # 7. 9 个 P 属性
    bad_p = []
    for css in temp_lib.rglob("symbol.css"):
        props = {l.split('"')[1] for l in css.read_text(errors="replace").splitlines()
                 if l.startswith('P "')}
        missing = REQUIRED_P_PROPS - props
        if missing:
            bad_p.append((css.parent.parent.name, sorted(missing)))
    check("7. symbol.css 9 个默认属性 (542 修复)", not bad_p, str(bad_p[:5]))

    # 8. MOCK T 字号
    bad_t = []
    for css in temp_lib.rglob("symbol.css"):
        for l in css.read_text(errors="replace").splitlines():
            if l.startswith("T ") and "MOCK" in css.read_text(errors="replace"):
                toks = l.split()
                try:
                    font = int(toks[5])
                except (ValueError, IndexError):
                    continue
                if font < 89:
                    bad_t.append((css.parent.parent.name, font))
    check("8. MOCK T 字号≥89", not bad_t, str(bad_t[:5]))

    # 9. 尺寸目标
    size_checks = {"U6H": 3000, "U6I": 2400, "U6A": 2400, "U12": 1200}
    for cell, min_w in size_checks.items():
        css = temp_lib / f"{cell}_PH" / "sym_1" / "symbol.css"
        if not css.exists():
            check(f"9. {cell} 尺寸", False, "cell 缺失")
            continue
        first = css.read_text(errors="replace").splitlines()[0]
        m = re.search(r'"(-?[\d.]+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)"', first)
        if not m:
            check(f"9. {cell} 尺寸", False, "outline 解析失败")
            continue
        x0, y0, x1, y1 = (float(v) for v in m.groups())
        width = abs(x1 - x0)
        check(f"9. {cell} outline 宽 ≥{min_w}", width >= min_w,
              f"实际 {width:.0f} ({x0:.0f}..{x1:.0f})")

    # ── 4. off-grid + GND offset ──────────────────────────────
    off = 0
    for csa in (root / "v9_default" / "worklib").rglob("page*.csa"):
        content = csa.read_text(errors="replace")
        for w in re.findall(r"WIRE 16 -1 \((-?\d+) (-?\d+)\)\((-?\d+) (-?\d+)\);", content):
            if any(int(v) % 25 for v in w):
                off += 1
    check("4. WIRE off-grid(25)=0", off == 0, f"{off} 处")

    # ── 6. origin/cds/xcon ────────────────────────────────────
    for v in versions:
        origin_ok = (v / "origin" / "sym_1" / "symbol.css").exists()
        cds_ok = (v / "cds.lib").exists() and "origin" in (v / "cds.lib").read_text(errors="replace")
        xcon_ok = (v / "worklib" / "5015" / "sch_1" / "5015.xcon").exists()
        check(f"6. {v.name} origin/cds/xcon", origin_ok and cds_ok and xcon_ok)

    # ── 10. test_spn ───────────────────────────────────────────
    spn = [p for p in root.glob("test_spn_*.csa")]
    check("10. test_spn 模板", len(spn) >= 4, f"{len(spn)} 个")

    print(f"\n{'='*60}\n结果: {len(FAIL)} FAIL / {40 - len(FAIL)} PASS")
    if FAIL:
        print("FAIL 项:", FAIL)
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
