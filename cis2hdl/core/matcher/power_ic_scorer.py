"""PowerCandidateScorer — D4 电源芯片匹配评分器（Phase XIV）。

按"引脚数 + 引脚名集合 + 电源网名"对 U* 实例打分，候选来自
``cis2hdl/config/power_ic.yaml``（practice hdl_lib 实测引脚清单）。

评分公式（§D.2.1）：
    score = w_pin_count * pin_count_hit
          + w_pin_name_jaccard * jaccard(实例引脚名, 符号引脚名)
          + w_net_pattern * any(网名命中 power_net_patterns)

用途：
    * score ≥ min_score_auto  → 直接替换 MatchResult（strategy=POWER_IC_AUTO）
    * min_score_candidate ≤ score < min_score_auto → 进 --export-unmatched 候选
    * 全部 < min_score_candidate → 维持原自动匹配（不动）

HG5015 实测（2026-08-11）：
    U1/U3/U10/U11/U14/U15/U18/U20 = 6 引脚 {BST,VIN,GND,EN,SW,FB}
    → 归一化 {BST,IN,GND,EN,SW,FB} = dc_dc/sym_1 引脚集（Jaccard 6/6）。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

#: 默认配置文件（相对项目根）。
_DEFAULT_CONFIG: str = "cis2hdl/config/power_ic.yaml"


class PowerCandidateScorer:
    """电源芯片候选评分器（D4）。"""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """Load power_ic.yaml rules.

        Args:
            config_path: power_ic.yaml 路径；缺省用默认配置文件。
        """
        self._cfg: dict = self._load_config(config_path)
        self._candidates: dict[int, list[dict]] = {}
        for key, value in (self._cfg.get("candidates_by_pin_count") or {}).items():
            try:
                self._candidates[int(key)] = list(value or [])
            except (TypeError, ValueError):
                continue
        scoring = self._cfg.get("scoring") or {}
        self.w_pin_count = float(scoring.get("w_pin_count", 0.40))
        self.w_pin_name_jaccard = float(scoring.get("w_pin_name_jaccard", 0.40))
        self.w_net_pattern = float(scoring.get("w_net_pattern", 0.20))
        self.min_score_auto = float(scoring.get("min_score_auto", 0.80))
        self.min_score_candidate = float(scoring.get("min_score_candidate", 0.50))
        self.max_pin_count = int(scoring.get("max_pin_count", 20))
        self._patterns = [
            re.compile(p) for p in (self._cfg.get("power_net_patterns") or [])
        ]
        self._aliases: dict[str, str] = {
            str(k).upper(): str(v).upper()
            for k, v in (self._cfg.get("pin_name_aliases") or {}).items()
        }

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def candidates_for(
        self,
        pin_count: int,
        pin_names: Optional[list[str]] = None,
        connected_nets: Optional[list[str]] = None,
    ) -> list[dict]:
        """按引脚数 + 引脚名 + 网名打分，返回降序候选列表。

        Args:
            pin_count: 实例引脚数。
            pin_names: 实例引脚名（功能名；缺省空列表）。
            connected_nets: 实例相连网名（辅助特征）。

        Returns:
            ``[{library_id, section, pins, score, reason}]`` 降序。
        """
        names = [self._normalize(n) for n in (pin_names or [])]
        nets = [str(n) for n in (connected_nets or [])]
        net_hit = 1.0 if any(self._net_matches(n) for n in nets) else 0.0

        out: list[dict] = []
        for cand in self._candidates.get(int(pin_count), []):
            lib = str(cand.get("library_id", ""))
            section = int(cand.get("section", 1))
            cand_pins = self._symbol_pin_names(lib, section)
            jac = self._jaccard(names, cand_pins)
            score = (
                self.w_pin_count * 1.0
                + self.w_pin_name_jaccard * jac
                + self.w_net_pattern * net_hit
            )
            score = round(min(max(score, 0.0), 1.0), 4)
            reason = self._reason(jac, net_hit)
            out.append({
                "library_id": lib,
                "section": section,
                "pins": len(cand_pins) if cand_pins else int(pin_count),
                "score": score,
                "reason": reason,
            })
        out.sort(key=lambda c: c["score"], reverse=True)
        return out

    def best_auto(
        self,
        pin_count: int,
        pin_names: Optional[list[str]] = None,
        connected_nets: Optional[list[str]] = None,
    ) -> Optional[dict]:
        """返回自动采用的最佳候选（score ≥ min_score_auto），否则 None。"""
        if int(pin_count) > self.max_pin_count:
            return None
        cands = self.candidates_for(pin_count, pin_names, connected_nets)
        for cand in cands:
            if cand["score"] >= self.min_score_auto:
                return cand
        return None

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def _symbol_pin_names(self, library_id: str, section: int) -> list[str]:
        """practice 符号引脚名（从 extra 表读取，未收录时返回空）。

        ``power_ic.yaml`` 未携带逐符号引脚表 —— 引脚名 Jaccard 依赖调用方
        提供（工程实测回填）。此处提供常见符号的静态表作为兜底。
        """
        static: dict[tuple[str, int], list[str]] = {
            ("dc_dc", 1): ["FB", "IN", "GND", "EN", "SW", "BST"],
            ("dc_dc", 2): ["EN", "GND", "SW", "VIN", "FB"],
            ("dc_dc", 4): ["IN", "GND", "EN", "SS", "EPAD"],
            ("dc_dc", 8): ["EN", "FREQ", "EPAD", "VIN", "GND"],
            ("dc_dc", 9): ["EN", "VIN", "VDD", "SS", "FSET"],
            ("dc_dc", 10): ["IN", "PMID", "CELL", "VB", "ISET", "ILIM", "VDPM", "PMID_S"],
            ("dc_dc", 11): ["BD1", "BD2", "EN", "SVIN", "ILIM", "FS", "COMP"],
            ("dc_dc", 12): ["SD", "VDDQ", "AVIN", "PVIN"],
            ("dc_dc", 13): ["EN", "GND", "FREQ", "VIN", "EPAD"],
            ("dc_dc", 15): ["IN", "PG", "EN", "IMLT", "BYP", "VCC"],
            ("dc_dc", 18): ["IN", "GND", "EN", "LX", "BS", "FB"],
            ("ldo", 1): ["VIN", "GND", "4", "VOUT"],
            ("ldo", 2): ["VIN", "GND", "VOUT", "EN", "ADJ"],
            ("power_dip4", 1): ["NC2", "VCC-", "VCC+", "NC1"],
        }
        return static.get((library_id.lower(), int(section)), [])

    def _normalize(self, name: str) -> str:
        """归一化引脚名（VIN→IN、BOOT→BST 等）。"""
        upper = str(name).upper().strip()
        return self._aliases.get(upper, upper)

    def _net_matches(self, net_name: str) -> bool:
        """网名是否命中电源网模式。"""
        for pat in self._patterns:
            if pat.search(str(net_name)):
                return True
        return False

    @staticmethod
    def _jaccard(a: list[str], b: list[str]) -> float:
        """两集合 Jaccard 相似度（0.0-1.0）。"""
        set_a = set(a)
        set_b = set(b)
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        inter = len(set_a & set_b)
        union = len(set_a | set_b)
        return inter / union if union else 0.0

    def _reason(self, jac: float, net_hit: float) -> str:
        """候选原因描述。"""
        parts = []
        if jac >= 1.0:
            parts.append("引脚名集合完全匹配")
        elif jac > 0:
            parts.append(f"引脚名 Jaccard={jac:.2f}")
        if net_hit:
            parts.append("相连网含电源网名")
        return "；".join(parts) if parts else "引脚数匹配"

    @staticmethod
    def _load_config(config_path: Optional[Path]) -> dict:
        """加载 power_ic.yaml（失败 → 空 dict，评分退化为引脚数匹配）。"""
        import yaml

        path = Path(config_path) if config_path else Path(_DEFAULT_CONFIG)
        if not path.exists():
            # 尝试从项目根解析（cwd 可能是项目根或子目录）
            for root in (Path.cwd(), Path.cwd().parent):
                cand = root / _DEFAULT_CONFIG
                if cand.exists():
                    path = cand
                    break
        if not path.exists():
            logger.warning("power_ic.yaml not found at %s — using defaults", path)
            return {}
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.warning("power_ic.yaml load failed %s: %s", path, exc)
            return {}


def extract_pin_names_from_pstxnet(
    pstxnet_path: Path, refdes: str,
) -> list[str]:
    """从 pstxnet.dat 提取某 refdes 的功能引脚名（去重、保序）。

    NODE_NAME 行的后续行 ``'GND':;`` 提供功能引脚名
    （§D.3 步骤 2；HG5015 实测：U1 → BOOT/GND/FB/EN/VIN/SW）。

    Args:
        pstxnet_path: pstxnet.dat 路径。
        refdes: 实例位号（如 "U1"）。

    Returns:
        引脚名列表（去重保序）；解析失败返回空列表。
    """
    try:
        text = Path(pstxnet_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = text.splitlines()
    names: list[str] = []
    seen: set[str] = set()
    for i, line in enumerate(lines):
        m = re.match(rf"^\s*NODE_NAME\s+{re.escape(refdes)}\s+\S+\s*$", line)
        if not m:
            continue
        for j in range(i + 1, min(i + 4, len(lines))):
            mn = re.match(r"^\s*'([^']*)':;\s*$", lines[j])
            if mn:
                name = mn.group(1).strip()
                if name and name not in seen:
                    seen.add(name)
                    names.append(name)
                break
    return names
