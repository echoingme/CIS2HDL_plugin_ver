"""manual_matches — D3 人工匹配 → 自动配线（Phase XIV）。

工作流（§C.1.3）：
    1. ``--export-unmatched`` → unmatched_report.yaml（refdes/引脚数/候选）
    2. 用户填写 manual_matches.yaml（refdes → library_id/section）
    3. ``--manual-matches manual_matches.yaml`` → 覆盖匹配 → 自动重算
       catalog / pin_coords / LASTPIN / WIRE（注入点在 _stage_match 之后，
       后续所有阶段只消费 MatchResult，覆盖一次即全链路生效）。

校验（转换时，§C.1.1）：
    * 引脚数不匹配 → logger.warning + 不注入（保留自动结果）；
    * 未知 library_id → warning + 忽略该条；
    * 同一 refdes 重复条目 → 后者覆盖 + warning。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..ir.match import MatchResult, MatchStrategy

logger = logging.getLogger(__name__)


@dataclass
class ManualMatch:
    """一条人工确认的元件匹配。

    Phase XVII M8 (用户 D7)：扩展为统一 chip_config 条目 —— 新增
    ``pin_map``（引脚级映射）、``hanging``（悬空引脚）、``placement``
    （放置覆盖，M3 腾挪结果）。v2.0 覆盖 v1.0 同 refdes。
    """

    refdes: str
    library_id: str
    section: int = 1
    value: str = ""
    note: str = ""
    pin_map: dict[str, str] = field(default_factory=dict)
    """引脚级映射 {cis_pin: hdl_pin}（可选，空=自动）。"""
    hanging: list[str] = field(default_factory=list)
    """悬空引脚列表（可选，空=全部自动连接；保留 LASTPIN 不生成 WIRE）。"""
    placement: dict = field(default_factory=dict)
    """放置覆盖（可选，M3 腾挪结果）{dx, dy}。"""

    def to_dict(self) -> dict:
        """序列化为 chip_config.yaml 条目（v2.0 schema）。"""
        entry: dict = {
            "refdes": self.refdes,
            "library_id": self.library_id,
            "section": int(self.section),
        }
        if self.value:
            entry["value"] = self.value
        if self.note:
            entry["note"] = self.note
        if self.pin_map:
            entry["pin_map"] = dict(self.pin_map)
        if self.hanging:
            entry["hanging"] = list(self.hanging)
        if self.placement:
            entry["placement"] = dict(self.placement)
        return entry


@dataclass
class ManualMatchesConfig:
    """manual_matches.yaml / chip_config.yaml 统一内容（v2.0）。

    v1.0（legacy manual_matches）自动升级：新字段补默认值。
    """

    version: str = "2.0"
    matches: list[ManualMatch] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "ManualMatchesConfig":
        """从 YAML 加载并校验（v2.0 解析 + v1.0 兼容升级）。

        Args:
            path: manual_matches.yaml / chip_config.yaml 路径。

        Returns:
            ManualMatchesConfig（version 保持源文件版本号）。

        Raises:
            FileNotFoundError: 文件不存在。
            ValueError: YAML 结构非法（无 ``matches`` 列表）。
        """
        import yaml

        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"manual_matches file not found: {p}")
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict) or not isinstance(data.get("matches"), list):
            raise ValueError(
                f"manual_matches file {p} must contain a 'matches' list"
            )
        version = str(data.get("version", "1.0"))
        matches: list[ManualMatch] = []
        for entry in data["matches"]:
            if not isinstance(entry, dict):
                logger.warning("manual_matches: skip non-dict entry: %s", entry)
                continue
            refdes = str(entry.get("refdes", "")).strip()
            library_id = str(entry.get("library_id", "")).strip()
            if not refdes or not library_id:
                logger.warning(
                    "manual_matches: skip entry without refdes/library_id: %s",
                    entry,
                )
                continue
            # v2.0 字段；v1.0 文件无这些键 → 默认空。
            pin_map = entry.get("pin_map") or {}
            hanging = entry.get("hanging") or []
            placement = entry.get("placement") or {}
            if not isinstance(pin_map, dict):
                pin_map = {}
            if not isinstance(hanging, list):
                hanging = []
            if not isinstance(placement, dict):
                placement = {}
            matches.append(ManualMatch(
                refdes=refdes,
                library_id=library_id,
                section=int(entry.get("section", 1) or 1),
                value=str(entry.get("value", "") or ""),
                note=str(entry.get("note", "") or ""),
                pin_map={str(k): str(v) for k, v in pin_map.items()},
                hanging=[str(h) for h in hanging],
                placement={str(k): v for k, v in placement.items()},
            ))
        return cls(
            version=version,
            matches=matches,
        )

    def dump(self) -> dict:
        """序列化为统一 chip_config.yaml dict（v2.0）。"""
        return {
            "version": "2.0",
            "matches": [m.to_dict() for m in self.matches],
        }

    def write_yaml(self, path: Path) -> Path:
        """写出统一 chip_config.yaml（v2.0 schema）。

        Args:
            path: 目标路径。

        Returns:
            写入的 Path。
        """
        import yaml

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            yaml.safe_dump(self.dump(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return p


def load_merged(
    chip_config_path: Path | None,
    legacy_path: Path | None,
) -> "ManualMatchesConfig":
    """加载统一 chip_config（v2.0）+ 旧 manual_matches（v1.0）并合并。

    用户 D7 优先级规则：**v2.0 条目覆盖 v1.0 同 refdes 条目**（加载时
    合并，v2.0 后写入 wins）。任一文件缺失/解析失败只记 warning。

    Args:
        chip_config_path: 统一 chip_config.yaml（主入口）。
        legacy_path: 旧 manual_matches.yaml（别名/兼容）。

    Returns:
        合并后的 ManualMatchesConfig（version="2.0"）。
    """
    merged = ManualMatchesConfig(version="2.0")
    if legacy_path:
        try:
            legacy = ManualMatchesConfig.load(legacy_path)
            merged.matches.extend(legacy.matches)
        except Exception as exc:
            logger.warning("manual_matches (legacy) load failed: %s", exc)
    if chip_config_path:
        try:
            chip = ManualMatchesConfig.load(chip_config_path)
            by_ref: dict[str, ManualMatch] = {}
            for mm in merged.matches:
                by_ref[mm.refdes.upper()] = mm
            for mm in chip.matches:
                by_ref[mm.refdes.upper()] = mm  # v2.0 覆盖 v1.0
            merged.matches = list(by_ref.values())
        except Exception as exc:
            logger.warning("chip_config load failed: %s", exc)
    return merged


def apply_manual_matches(
    match_results: list[MatchResult],
    manual: "ManualMatchesConfig",
    component_db,
    design=None,
) -> tuple[list[MatchResult], list[str]]:
    """覆盖匹配结果；返回 (match_results, warnings 列表)。

    注入点：ConversionEngine._stage_match 之后。每条人工匹配：
      * 目标库存在 + 引脚数匹配 → 覆盖 MatchResult
        （target_library_id / confidence=1.0 / strategy=MANUAL）；
      * 校验失败 → warning 收集，保留自动结果（绝不静默失败）。
    同时把 ``section`` 写回 design 实例（_compute_pin_geometry 用
    irec.section 读 css sym_N 偏移）。

    Args:
        match_results: 自动匹配结果列表（原地覆盖）。
        manual: 人工匹配配置。
        component_db: HDL ComponentDB（存在性/引脚数校验）。
        design: 可选 DesignIR（写回实例 section）。

    Returns:
        (match_results, warnings)。
    """
    warnings: list[str] = []
    by_src: dict[str, MatchResult] = {}
    for m in match_results:
        sid = getattr(m, "source_library_id", "") or ""
        by_src[sid] = m
        by_src.setdefault(sid.upper(), m)

    seen_refdes: set[str] = set()
    for mm in manual.matches:
        if mm.refdes in seen_refdes:
            warnings.append(
                f"manual match {mm.refdes}: duplicate entry — later one wins"
            )
        seen_refdes.add(mm.refdes)

        result = by_src.get(mm.refdes) or by_src.get(mm.refdes.upper())
        if result is None:
            warnings.append(
                f"manual match {mm.refdes}: refdes not in match results — ignored"
            )
            continue

        target = None
        if component_db is not None:
            try:
                target = component_db.get_by_library_id(mm.library_id)
            except Exception:
                target = None
        if target is None:
            warnings.append(
                f"manual match {mm.refdes}: unknown library_id "
                f"{mm.library_id!r} — ignored"
            )
            continue

        # ── 引脚数校验 ────────────────────────────────────────────
        # 优先用实例真实引脚数（pstxnet 注入后的 pin_connections）；
        # 无 design 上下文时退回 match_result 的 hdl_pin_count。
        target_pins = len(getattr(target, "pins", []) or [])
        src_pins = 0
        if design is not None:
            for page in design.pages:
                for inst in page.instances:
                    if (getattr(inst, "refdes", "") or "").upper() == mm.refdes.upper():
                        conns = getattr(inst, "pin_connections", None)
                        if isinstance(conns, dict) and conns:
                            src_pins = len(conns)
                            break
                if src_pins:
                    break
        if not src_pins:
            src_pins = int((result.extra_data or {}).get("hdl_pin_count", 0) or 0)
        if target_pins and src_pins and target_pins != src_pins:
            warnings.append(
                f"manual match {mm.refdes}: pin count mismatch "
                f"(source={src_pins}, target={target_pins}) — not applied"
            )
            continue

        # ── 覆盖 ─────────────────────────────────────────────────
        result.target_library_id = str(target.library_id)
        result.confidence = 1.0
        result.strategy = MatchStrategy.MANUAL
        result.pin_mapping = dict(mm.pin_map) if mm.pin_map else {}
        result.extra_data["manual_library_id"] = mm.library_id
        result.extra_data["manual_section"] = int(mm.section)
        # Phase XVII M8: hanging（悬空引脚）与 placement（放置覆盖）透传，
        # csa_writer 经 set_matches 消费（hanging 保留 LASTPIN 不生成
        # WIRE；placement 写回实例 body 坐标偏移）。
        if mm.hanging:
            result.extra_data["hanging_pins"] = [str(h) for h in mm.hanging]
        if mm.placement:
            result.extra_data["placement"] = dict(mm.placement)
        if mm.value:
            result.extra_data["hdl_value"] = mm.value
            result.extra_data["_source_value"] = mm.value
        result.extra_data["hdl_pin_count"] = target_pins or src_pins
        result.extra_data["selected_primitive"] = str(target.library_id)
        result.warnings.append(
            f"manual override → {mm.library_id}/sym_{mm.section}"
        )
        logger.info(
            "manual match applied: %s → %s (section %d)",
            mm.refdes, mm.library_id, mm.section,
        )

        # ── 写回实例 section / value（css sym_N 偏移 + VALUE 显示） ──
        if design is not None:
            for page in design.pages:
                for inst in page.instances:
                    if (getattr(inst, "refdes", "") or "").upper() == mm.refdes.upper():
                        inst.section = int(mm.section)
                        if mm.value:
                            inst.value_override = mm.value

    return match_results, warnings


def export_unmatched(
    match_results: list[MatchResult],
    component_db,
    page_conns=None,
    power_candidates=None,
    threshold: float = 0.80,
) -> dict:
    """生成 ``--export-unmatched`` 报告 dict（refdes/引脚/候选）。

    Args:
        match_results: 匹配结果。
        component_db: HDL ComponentDB。
        page_conns: 可选页面连接模型（提取实例引脚/网名）。
        power_candidates: 可选 PowerCandidateScorer（候选评分）。
        threshold: 低于该置信度视为待确认。

    Returns:
        ``{"version", "unmatched": [...], "low_confidence": [...]}``。
    """
    version = "1.0"
    unmatched: list[dict] = []
    low_confidence: list[dict] = []
    for m in match_results:
        conf = float(getattr(m, "confidence", 0.0) or 0.0)
        # MatchStrategy 是 Enum：str() 返回 "MatchStrategy.MANUAL"，必须取 .name
        # （QA Phase XIV Bug 2：原 str() 比较恒 False，人工覆盖条目从清单消失）。
        _strat = getattr(m, "strategy", None)
        strategy = getattr(_strat, "name", _strat) if _strat is not None else ""
        strategy = "" if strategy is None else str(strategy)
        refdes = getattr(m, "source_library_id", "") or ""
        if not refdes:
            continue
        pin_count = int((m.extra_data or {}).get("hdl_pin_count", 0) or 0)
        pin_names = list((m.extra_data or {}).get("manual_pin_names", []) or [])
        nets: list[str] = []
        if page_conns is not None:
            for page_conn in page_conns:
                for irec in getattr(page_conn, "instances", []) or []:
                    if (getattr(irec, "refdes", "") or "").upper() != refdes.upper():
                        continue
                    nets.extend(
                        str(v) for v in (getattr(irec, "power_nets", []) or [])
                    )
                    # PageIR 实例用 pin_connections 字典；PageConnectivity
                    # 实例用 pins 列表。
                    conns = getattr(irec, "pin_connections", None)
                    if isinstance(conns, dict):
                        nets.extend(str(v) for v in conns.values() if v)
                    nets.extend(
                        str(p.get("net_name", "")) for p in getattr(irec, "pins", [])
                        if getattr(p, "net_name", "")
                    )
        nets = list(dict.fromkeys(n for n in nets if n))

        entry = {
            "refdes": refdes,
            "pin_count": pin_count,
            "pin_names": pin_names,
            "nets": nets,
            "auto_match": {
                "library_id": getattr(m, "target_library_id", "") or "",
                "confidence": round(conf, 4),
                "strategy": strategy,
            },
            "candidates": [],
            "fill": f"refdes: {refdes}\nlibrary_id: <候选 library_id>\nsection: 1\n",
        }
        if power_candidates is not None:
            cands = power_candidates.candidates_for(pin_count, pin_names, nets)
            entry["candidates"] = [
                {
                    "library_id": c["library_id"],
                    "section": c["section"],
                    "pins": c["pins"],
                    "score": c["score"],
                    "reason": c["reason"],
                }
                for c in cands
            ]
            if cands and cands[0]["score"] >= getattr(
                power_candidates, "min_score_auto", 0.80
            ):
                entry["fill"] = (
                    f"refdes: {refdes}\n"
                    f"library_id: {cands[0]['library_id']}\n"
                    f"section: {cands[0]['section']}\n"
                )

        if strategy in ("MANUAL", "NEEDS_REVIEW") or conf < threshold:
            unmatched.append(entry)
        elif conf < 0.95:
            low_confidence.append(entry)

    return {
        "version": version,
        "unmatched": unmatched,
        "low_confidence": low_confidence,
    }
