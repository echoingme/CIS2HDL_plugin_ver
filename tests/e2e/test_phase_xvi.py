"""Phase XVI e2e — 镜像归一化 + IOPORT 审计（system_design0811-phase16.md D.3）。

Runs the full HG5015 conversion and asserts:
  1. --aesthetic 输出 aesthetic_report.txt 含 [MIRROR] 节（total≈217，
     exact/approx 计数），且 07-SOC_PWR1/13-DDR3/21-4GE 抽查页 LASTPIN ∈
     WIRE 端点（连接重合硬约束）。
  2. --aesthetic 同时产出 ioport_audit_report.txt（三节可解析）。
  3. --no-mirror-normalize 输出与默认（normalize on）不同（逃生舱对照：
     mirror 实例引脚坐标未镜像）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

from cis2hdl.core.engine.conversion_engine import ConversionEngine


def _hg5015_dir(fixtures_dir: Path) -> Path | None:
    base = fixtures_dir / "HG5015test"
    if not (base / "HG5015-BE36_V10.DSN").exists():
        return None
    return base


def _convert(hg: Path, out_dir: Path, aes: bool = False,
             no_mirror: bool = False) -> object:
    """Mimic __main__.py convert 分支：加载 routing.yaml + CLI 覆盖。

    转换后恢复全局 config.routing（避免污染同会话其他测试）。
    """
    import cis2hdl as _pkg
    from cis2hdl.core.config import config as cfg

    routing_config = Path(_pkg.__file__).parent / "config" / "routing.yaml"
    saved_routing = cfg.routing
    try:
        if routing_config.exists():
            cfg.load_from_file(routing_config)
        # 默认开关（等价 CLI 未指定任何 flag）
        cfg.routing.aesthetic.enabled = False
        cfg.routing.text_layout.enabled = False
        cfg.routing.overlap.check = False
        cfg.routing.power_ic.enabled = False
        cfg.routing.mode = "p0"
        cfg.routing.ioport.edge_layout = False
        cfg.routing.gnd_distribution.enabled = False
        cfg.routing.ioport.audit = False
        cfg.routing.mirror.normalize = True
        if aes:
            cfg.routing.aesthetic.enabled = True
            cfg.routing.text_layout.enabled = True
            cfg.routing.overlap.check = True
            cfg.routing.power_ic.enabled = True
            cfg.routing.mode = "detour"
            cfg.routing.ioport.edge_layout = True
            cfg.routing.gnd_distribution.enabled = True
            cfg.routing.ioport.audit = True
        if no_mirror:
            cfg.routing.mirror.normalize = False
        engine = ConversionEngine()
        hdl = hg.parent / "hdl_lib"
        return engine.convert(
            hg / "HG5015-BE36_V10.DSN",
            out_dir,
            hdl_lib_path=hdl if hdl.exists() else None,
        )
    finally:
        cfg.routing = saved_routing


@pytest.fixture(scope="module")
def hg5015_dir(fixtures_dir: Path) -> Path:
    base = _hg5015_dir(fixtures_dir)
    if base is None:
        pytest.skip("HG5015 fixtures not available")
    return base


@pytest.fixture(scope="module")
def aes_out(hg5015_dir: Path, tmp_path_factory):
    """--aesthetic 转换（含 ioport audit + mirror 报告）。"""
    out_dir = tmp_path_factory.mktemp("phase_xvi_aes")
    report = _convert(hg5015_dir, out_dir, aes=True)
    return report, out_dir


@pytest.fixture(scope="module")
def default_out(hg5015_dir: Path, tmp_path_factory):
    """默认转换（p0 + mirror.normalize=true）。"""
    out_dir = tmp_path_factory.mktemp("phase_xvi_default")
    report = _convert(hg5015_dir, out_dir)
    return report, out_dir


@pytest.fixture(scope="module")
def nomirror_out(hg5015_dir: Path, tmp_path_factory):
    """--no-mirror-normalize 转换（p0 + mirror 关闭；逃生舱对照）。"""
    out_dir = tmp_path_factory.mktemp("phase_xvi_nomirror")
    report = _convert(hg5015_dir, out_dir, no_mirror=True)
    return report, out_dir


class TestPhaseXviMirror:
    @staticmethod
    def _sch_dir(out_dir: Path) -> Path:
        worklib = out_dir / "worklib"
        cells = [d for d in worklib.iterdir() if d.is_dir()]
        return cells[0] / "sch_1"

    def test_aes_report_mirror_section(self, aes_out):
        report, out_dir = aes_out
        assert report.errors == []
        aes = out_dir / "aesthetic_report.txt"
        assert aes.exists(), "aesthetic_report.txt missing"
        text = aes.read_text(encoding="utf-8")
        m = re.search(r"\[MIRROR\] total=(\d+)", text)
        assert m, f"[MIRROR] section missing:\n{text[:800]}"
        total = int(m.group(1))
        # 实测 154（catalog 管线保留的 mirror 实例；设计预估 217 为不同
        # 实例源口径——"数字为示例，实测为准"）
        assert 140 <= total <= 180, f"mirror total={total} out of range"
        assert re.search(r"exact=\d+ approx=\d+", text)
        assert "方向近似（镜像无法用纯旋转表达），需人工复核" in text

    def test_aes_report_lastpin_miss_zero(self, aes_out):
        """Phase XXII D8（P1-7）：aes 模式 [LASTPIN_MISS] total=0。

        根因修复：①key 前置（微移引脚正确豁免）②expected 用 _pin_offset_map
        同源链（不再简化 css 查找假 miss）③位移后 snap50 网格对齐。
        """
        _, out_dir = aes_out
        aes = out_dir / "aesthetic_report.txt"
        text = aes.read_text(encoding="utf-8")
        m = re.search(r"\[LASTPIN_MISS\] (none|total=(\d+)( exempt=(\d+))?)", text)
        assert m, f"[LASTPIN_MISS] section missing:\n{text[:800]}"
        if m.group(2) is None:
            assert m.group(1) == "none", f"unexpected format: {m.group(1)}"
        else:
            total = int(m.group(2))
            exempt = int(m.group(4) or 0)
            # total=0（修复后）；或全部证据化豁免（Q5 方案 b 兜底）。
            assert total == 0 or total == exempt, (
                f"unexempted LASTPIN misses (total={total} exempt={exempt}):\n"
                f"{text[:1200]}"
            )

    @staticmethod
    def _blocks_by_refdes(content: str) -> dict[str, str]:
        blocks: dict[str, str] = {}
        for part in re.split(r"(?=FORCEADD )", content):
            if not part.startswith("FORCEADD "):
                continue
            m_loc = re.search(r"\$LOCATION (\S+)", part)
            if m_loc:
                blocks[m_loc.group(1)] = part
        return blocks

    def test_mirror_instances_rline_and_endpoints(self, aes_out):
        """抽查全部 154 镜像实例：R 行与报告一致 + 引脚坐标是 WIRE 端点
        （单引脚网豁免——镜像归一化不引入新的断线）。"""
        _, out_dir = aes_out
        aes = out_dir / "aesthetic_report.txt"
        text = aes.read_text(encoding="utf-8")
        entries = re.findall(
            r"page=(\S+)  refdes=(\S+)  orient=(\S+)  → (R \d+|\(no R line\))",
            text,
        )
        assert len(entries) >= 140
        sch = self._sch_dir(out_dir)
        rline_mismatch = 0
        checked = 0
        endpoint_violations = 0
        for page, refdes, orient, rline in entries:
            pnum = int(page.split("-")[0])
            csa = sch / f"page{pnum}.csa"
            content = csa.read_text(encoding="utf-8", errors="replace")
            block = self._blocks_by_refdes(content).get(refdes)
            assert block is not None, f"{refdes} block missing on page{pnum}"
            # R 行（组件级：FORCEADD 后紧跟坐标前的 `R n`）
            m_r = re.search(r"\nR ([123])\n\((-?\d+) (-?\d+)\);", block)
            actual_r = int(m_r.group(1)) if m_r else 0
            expected_angle = int(rline.split()[-1]) if rline.startswith("R") else 0
            expected_r = {90: 1, 180: 2, 270: 3}.get(expected_angle, 0)
            if actual_r != expected_r:
                rline_mismatch += 1
            # 引脚坐标 ∈ WIRE 端点（多引脚网硬约束；单引脚网无 WIRE 属
            # 正常豁免 —— 镜像归一化不引入新的断线）
            wires = re.findall(
                r"WIRE 16 -1 \((-?\d+) (-?\d+)\)\((-?\d+) (-?\d+)\);", content
            )
            endpoints = set()
            for w in wires:
                endpoints.add((int(w[0]), int(w[1])))
                endpoints.add((int(w[2]), int(w[3])))
            for x, y in re.findall(r"LASTPIN \((-?\d+) (-?\d+)\)", block):
                checked += 1
            # SIG_NAME 引脚（入网引脚）必须 ∈ WIRE 端点；否则按网内引脚数
            # 判定：>1 即断线（fail），==1 为单引脚网豁免
            for lp in re.findall(
                r"FORCEPROP \d LASTPIN \((-?\d+) (-?\d+)\) SIG_NAME (\S+)",
                block,
            ):
                coord = (int(lp[0]), int(lp[1]))
                if coord in endpoints:
                    continue
                net = lp[2].rstrip("\\g")
                pins_on_net = len(re.findall(
                    r"FORCEPROP \d LASTPIN \([^)]+\) SIG_NAME "
                    + re.escape(net) + r"(?:\\g)?", content,
                ))
                if pins_on_net > 1:
                    endpoint_violations += 1
                    if endpoint_violations <= 5:
                        print(
                            f"  PIN NOT WIRE ENDPOINT {refdes} page{pnum} "
                            f"pin {coord} net={net} pins_on_net={pins_on_net}"
                        )
        assert rline_mismatch == 0, f"{rline_mismatch} mirror R-line mismatches"
        assert endpoint_violations == 0, (
            f"{endpoint_violations} mirror pins on multi-pin nets not WIRE endpoints"
        )
        assert checked > 300, f"checked only {checked} mirror pins"

    def test_all_mirror_csa_on_grid(self, aes_out):
        """镜像后所有 WIRE 端点仍在 25 网格（无 off-grid）。"""
        _, out_dir = aes_out
        sch = self._sch_dir(out_dir)
        off_grid = 0
        for csa in sorted(sch.glob("page*.csa")):
            content = csa.read_text(encoding="utf-8", errors="replace")
            for w in re.findall(
                r"WIRE 16 -1 \((-?\d+) (-?\d+)\)\((-?\d+) (-?\d+)\);", content
            ):
                if any(int(v) % 25 for v in w):
                    off_grid += 1
        assert off_grid == 0, f"{off_grid} off-grid WIRE endpoints"


class TestPhaseXviIoportAudit:
    def test_ioport_audit_report_exists(self, aes_out):
        _, out_dir = aes_out
        path = out_dir / "ioport_audit_report.txt"
        assert path.exists(), "ioport_audit_report.txt missing (--aesthetic → audit)"
        text = path.read_text(encoding="utf-8")
        assert "[SUMMARY]" in text
        assert "[UNWIRED]" in text
        assert "[NAME_CONFLICT]" in text
        assert "[ORPHAN]" in text
        assert "[FIX_SUGGESTION]" in text
        # ioport_total 与 522 页级 off_page 计数一致量级
        m = re.search(r"ioport_total=(\d+)", text)
        assert m, f"SUMMARY missing ioport_total:\n{text[:400]}"
        assert 500 <= int(m.group(1)) <= 540
        # 接线核对有豁免（跨页网本页仅连接器属正常）
        assert re.search(r"exempt_name_only=\d+", text)

    def test_default_audit_report_exists(self, default_out):
        """默认转换也产生审计报告（Phase XVI 用户要求：默认出诊断报告）。"""
        _, out_dir = default_out
        path = out_dir / "ioport_audit_report.txt"
        assert path.exists(), "default conversion should emit ioport_audit_report.txt"
        text = path.read_text(encoding="utf-8")
        assert "[SUMMARY]" in text and "[UNWIRED]" in text
        # 默认（p0）与 --aesthetic 的审计结果一致（audit 与布线模式无关）
        assert re.search(r"unwired=0", text)

    def test_default_aesthetic_report_exists(self, default_out):
        """默认转换也产生 aesthetic_report.txt（[MIRROR] 节可见）。"""
        _, out_dir = default_out
        path = out_dir / "aesthetic_report.txt"
        assert path.exists(), "default conversion should emit aesthetic_report.txt"
        text = path.read_text(encoding="utf-8")
        assert re.search(r"\[MIRROR\] total=\d+", text)


class TestPhaseXviNoMirrorRegression:
    @staticmethod
    def _sch_dir(out_dir: Path) -> Path:
        worklib = out_dir / "worklib"
        cells = [d for d in worklib.iterdir() if d.is_dir()]
        return cells[0] / "sch_1"

    def test_no_mirror_normalize_differs_from_default(self, default_out, nomirror_out):
        """逃生舱对照（同为 p0 模式）：--no-mirror-normalize 输出与默认不同。"""
        _, default_dir = default_out
        _, nom_dir = nomirror_out
        d_sch = self._sch_dir(default_dir)
        n_sch = self._sch_dir(nom_dir)
        # 07-SOC_PWR1 页（44 个 mirror 实例）两种模式必须不同
        d_page7 = (d_sch / "page7.csa").read_text(encoding="utf-8", errors="replace")
        n_page7 = (n_sch / "page7.csa").read_text(encoding="utf-8", errors="replace")
        assert d_page7 != n_page7, "page7 (44 mirror) identical under both modes"
        # 无 mirror 页（page1 封面无元件）→ 选一个无 mirror 的元件页
        # 逐页找无 mirror 页并断言逐字节一致（回归零影响）
        mirror_pages = {5, 6, 7, 10, 12, 13, 14, 16, 17, 18, 19, 20, 21, 22, 23, 24}
        identical = 0
        for pnum in range(1, 25):
            if pnum in mirror_pages:
                continue
            d = d_sch / f"page{pnum}.csa"
            n = n_sch / f"page{pnum}.csa"
            if not d.exists() or not n.exists():
                continue
            assert d.read_text(encoding="utf-8", errors="replace") == n.read_text(
                encoding="utf-8", errors="replace"
            ), f"non-mirror page{pnum} must be byte-identical (regression)"
            identical += 1
        assert identical >= 5, f"only {identical} non-mirror pages compared"
