"""prefix_scope 候选范围过滤（S4；FR2 各 prefix 搜索范围）。

语义（S4 设计假设，详见 developer-guide S4 章节 / 交付报告"设计假设"）：

- ``prefix_scope`` 映射 ``{prefix: [关键字, ...]}``；``["any"]`` 或空列表 =
  该 prefix 不限制；空 dict（默认）= 完全不过滤。
- 候选保留条件（**并集语义，保守实现**）：候选的 ``footprint`` /
  ``package_type`` / ``jedec_type`` / ``part_name`` 任一字段**包含**任一
  prefix 配置的关键字即保留。此实现不改 matcher 内部候选池构建
  （``CandidatePoolBuilder``），只在编排器把传给 pipeline 的 ComponentDB
  **副本**收窄——避免触碰匹配逻辑（铁律）。
- 默认（``{}``）返回原 DB 引用不变 → 默认 profile 与 legacy 字节等价
  （FR9）；用户显式配置 prefix_scope 后收窄候选 → 不同匹配结果（FR2）。

限制（已记录）：并集语义无法表达"仅 R prefix 限制到 0603"这类**逐 prefix**
收窄（那是 matcher 内部 per-source 语义，需要改 CandidatePoolBuilder，
S4 铁律不允许）；S4 提供的是全局候选范围收窄。未来 S 阶段可把
``_filter_by_type`` 扩展为感知 prefix_scope 时再升级为逐 prefix 语义。
"""

from __future__ import annotations

import logging
from typing import Any

from cis2hdl.core.db.component_db import ComponentDB

logger = logging.getLogger(__name__)

__all__ = ["is_scope_effective", "candidate_in_scope", "apply_prefix_scope"]


def _effective_scope(prefix_scope: dict[str, list[str]] | None) -> dict[str, list[str]]:
    """返回实际生效的 scope 映射（过滤掉空 / ["any"] 条目）。"""
    effective: dict[str, list[str]] = {}
    for prefix, keywords in (prefix_scope or {}).items():
        kws = [str(k).strip().lower() for k in (keywords or []) if str(k).strip()]
        if kws and not (len(kws) == 1 and kws[0] == "any"):
            effective[str(prefix).upper()] = kws
    return effective


def is_scope_effective(prefix_scope: dict[str, list[str]] | None) -> bool:
    """prefix_scope 是否有实际生效的收窄（默认空 / any / 空列表 → False）。"""
    return bool(_effective_scope(prefix_scope))


def candidate_in_scope(candidate: Any, keywords: list[str]) -> bool:
    """单个候选是否命中任一 scope 关键字（footprint/package/jedec/part_name）。"""
    fields = [
        getattr(candidate, "footprint", "") or "",
        getattr(candidate, "package_type", "") or "",
        getattr(candidate, "jedec_type", "") or "",
        getattr(candidate, "part_name", "") or "",
    ]
    # ptf_rows 里的 package_type/jedec_type 也纳入（ComponentDef 常见载体）
    extra = getattr(candidate, "extra_data", {}) or {}
    if isinstance(extra, dict):
        for row in extra.get("ptf_rows", []) or []:
            if isinstance(row, dict):
                fields.append(row.get("package_type", "") or "")
                fields.append(row.get("jedec_type", "") or "")
    haystack: str = " ".join(f.lower() for f in fields if f)
    return any(kw in haystack for kw in keywords)


def apply_prefix_scope(
    prefix_scope: dict[str, list[str]] | None,
    db: ComponentDB,
) -> ComponentDB:
    """按 prefix_scope 收窄 ComponentDB（返回新 DB 副本；默认返回原引用）。

    Args:
        prefix_scope: ``match.prefix_scope``（默认空 → 原样返回）。
        db: 原始 HDL ComponentDB。

    Returns:
        收窄后的 ComponentDB 副本（仅 ``list_all()`` 被 pipeline 消费，
        与 hdl_lib_only 过滤正交）；无生效 scope 时返回原 db 引用。
    """
    effective = _effective_scope(prefix_scope)
    if not effective:
        return db

    # 并集关键字集合（任意 prefix 配置的关键字命中即保留）
    keywords: set[str] = set()
    for kws in effective.values():
        keywords.update(kws)
    if not keywords:
        return db

    kept = [
        c for c in db.list_all()
        if any(candidate_in_scope(c, [kw]) for kw in keywords)
    ]
    logger.info(
        "prefix_scope: 候选库 %d → %d（并集关键字 %s）",
        len(db), len(kept), sorted(keywords),
    )
    filtered = ComponentDB()
    filtered.add_batch(kept)
    return filtered
