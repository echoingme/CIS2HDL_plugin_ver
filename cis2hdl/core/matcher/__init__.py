"""Component matching layer — CIS ↔ HDL component matching pipeline.

v2.0: Two-phase matching architecture.

Exports:
    PrefixAffinityCalculator  — Dynamic prefix affinity learning matrix
    MatcherBase               — Abstract base class for all matchers
    MatcherRegistry           — Class-level matcher instance registry
    MatcherPipeline           — Two-phase matching pipeline
    ManualMatchResolver       — Last-resort manual match resolver
    ExactMatcher              — Fingerprint-based exact matching
    FuzzyNameMatcher          — rapidfuzz token_sort_ratio name matching
    FeatureExtractMatcher     — Regex feature extraction matching
    ValueMatcher              — Electrical value matching via part.ptf data
    FallbackMatcher           — Simplified prefix-filter fallback (v2.0)
    TypeHypothesisGenerator   — Phase 1 type hypothesis generation
    PassiveMatcher            — Phase 2A deterministic passive matching
    ActiveMatcher             — Phase 2B within-type scoring matcher
    CandidatePoolBuilder      — Phase 1.5 candidate pool construction
"""

from cis2hdl.core.matcher.base import MatcherBase
from cis2hdl.core.matcher.exact import ExactMatcher
from cis2hdl.core.matcher.fallback import FallbackMatcher
from cis2hdl.core.matcher.feature import FeatureExtractMatcher
from cis2hdl.core.matcher.fuzzy import FuzzyNameMatcher
from cis2hdl.core.matcher.value_matcher import ValueMatcher
from cis2hdl.core.matcher.pipeline import ManualMatchResolver, MatcherPipeline
from cis2hdl.core.matcher.registry import MatcherRegistry
from cis2hdl.core.matcher.scoring import PrefixAffinityCalculator
from cis2hdl.core.matcher.type_hypothesis import TypeHypothesisGenerator
from cis2hdl.core.matcher.passive_matcher import PassiveMatcher
from cis2hdl.core.matcher.active_matcher import ActiveMatcher
from cis2hdl.core.matcher.candidate_pool import CandidatePoolBuilder

__all__ = [
    "PrefixAffinityCalculator",
    "MatcherBase",
    "MatcherRegistry",
    "MatcherPipeline",
    "ManualMatchResolver",
    "ExactMatcher",
    "FuzzyNameMatcher",
    "FeatureExtractMatcher",
    "ValueMatcher",
    "FallbackMatcher",
    "TypeHypothesisGenerator",
    "PassiveMatcher",
    "ActiveMatcher",
    "CandidatePoolBuilder",
]
