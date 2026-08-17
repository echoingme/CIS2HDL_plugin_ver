"""yaml ``match`` 段参数应用（NFR5 去硬编码；S4 接入）。

把 pipeline.yaml ``match`` 段的 ``weights`` / ``thresholds`` 应用到 matcher
运行时配置（**只改配置、不改匹配逻辑**；应用前记录原值、``finally`` 恢复）：

- **thresholds** → 全局 ``Config.routing.matching``（``ComponentMatchingConfig``
  四阈值 exact/fuzzy/feature/fallback；各 matcher 运行时读取
  ``config.matching.*_threshold``）。默认 yaml 值与 ``ComponentMatchingConfig``
  完全一致（S1 测试断言）→ 应用后行为不变（FR9）；显式修改 → 不同匹配结果
  （FR2）。
- **weights** → ``ActiveMatcher.WITHIN_TYPE_WEIGHTS`` 类属性临时覆盖
  （编排级配置注入，``try/finally`` 恢复；不修改 ``active_matcher.py`` 源码）。
  S4 已把 ``MatchSection.weights`` 默认值对齐 ``WITHIN_TYPE_WEIGHTS``
  （footprint/value/jedec/pin_count/part_name）→ 默认应用后行为不变（FR9）；
  显式修改 → 不同打分（FR2）。旧 yaml key ``jedec_type`` 作为 ``jedec`` 别名
  兼容（S1 占位字段）。
- **prefix_scope** → 由 ``_prefix_scope`` 在编排器内处理（候选库收窄；
  默认空 = 不限制，FR9 安全）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from cis2hdl.core.config import config as _global_config
from cis2hdl.core.matcher.active_matcher import ActiveMatcher

logger = logging.getLogger(__name__)

__all__ = [
    "THRESHOLD_ATTRS",
    "WEIGHT_KEY_ALIASES",
    "AppliedMatchParams",
    "apply_match_params",
    "restore_match_params",
]

#: ``match.thresholds`` yaml key → ``ComponentMatchingConfig`` 字段。
THRESHOLD_ATTRS: dict[str, str] = {
    "exact": "exact_threshold",
    "fuzzy": "fuzzy_threshold",
    "feature": "feature_threshold",
    "fallback": "fallback_threshold",
}

#: ``match.weights`` yaml key → ``ActiveMatcher.WITHIN_TYPE_WEIGHTS`` dim。
#: ``jedec_type`` 为 S1 占位 key 的向后兼容别名（正式 key = ``jedec``）。
WEIGHT_KEY_ALIASES: dict[str, str] = {
    "jedec_type": "jedec",
}


@dataclass
class AppliedMatchParams:
    """记录应用前原值，供 ``restore_match_params`` 恢复。"""

    prev_thresholds: dict[str, float] = field(default_factory=dict)
    prev_weights: dict[str, float] | None = None


def apply_match_params(
    thresholds: dict[str, float] | None = None,
    weights: dict[str, float] | None = None,
) -> AppliedMatchParams:
    """应用 yaml match 段参数到 matcher 运行时配置。

    Args:
        thresholds: ``match.thresholds``（exact/fuzzy/feature/fallback）。
        weights: ``match.weights``（WITHIN_TYPE_WEIGHTS dims；jedec_type 别名）。

    Returns:
        原值快照（传给 ``restore_match_params`` 恢复）。
    """
    applied = AppliedMatchParams()

    # ── thresholds → ComponentMatchingConfig（matchers 运行时读取） ──
    if thresholds:
        matching = _global_config.routing.matching
        for key, attr in THRESHOLD_ATTRS.items():
            if key in thresholds:
                prev = getattr(matching, attr)
                new = float(thresholds[key])
                if new != prev:
                    applied.prev_thresholds[attr] = prev
                    setattr(matching, attr, new)

    # ── weights → ActiveMatcher.WITHIN_TYPE_WEIGHTS 类属性（临时覆盖） ──
    if weights:
        prev = dict(ActiveMatcher.WITHIN_TYPE_WEIGHTS)
        merged = dict(prev)
        changed = False
        for key, value in weights.items():
            dim = WEIGHT_KEY_ALIASES.get(key, key)
            if dim not in merged:
                logger.warning("match.weights 忽略未知维度 %r", key)
                continue
            new = float(value)
            if new != merged[dim]:
                merged[dim] = new
                changed = True
        if changed:
            applied.prev_weights = prev
            ActiveMatcher.WITHIN_TYPE_WEIGHTS = merged

    return applied


def restore_match_params(applied: AppliedMatchParams) -> None:
    """恢复应用前原值（编排 finally 调用；幂等）。"""
    if applied.prev_thresholds:
        matching = _global_config.routing.matching
        for attr, prev in applied.prev_thresholds.items():
            setattr(matching, attr, prev)
    if applied.prev_weights is not None:
        ActiveMatcher.WITHIN_TYPE_WEIGHTS = applied.prev_weights
