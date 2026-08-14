"""Diagnostics layer — file integrity, readiness evaluation, and structured reporting.

All modules follow Cadence Professional's three-tier validation pattern:
    Layer 1: File Integrity Check
    Layer 2: Dependency Resolution & Cross-Reference
    Layer 3: Data Completeness & Quality Assessment
"""

from .diagnostic_report import (
    Severity,
    ActionVerb,
    FileState,
    DiagnosisError,
    DiagnosticReport,
    FileStatus,
    ProjectInventory,
    DSNInternalInventory,
    ActionItem,
    ReadinessReport,
    ConversionReadinessEvaluator,
)
from .file_inventory import (
    FileInventory,
    DSNInternalInventoryBuilder,
)
from .file_validator import (
    ProjectFileValidator,
    DependencyResolver,
)

# ── Phase II new modules ────────────────────────────────────────────────────
from .error_diagnosis import (
    ErrorCodeTemplate,
    ERROR_CODES,
    ErrorDiagnosisEngine,
)
from .recovery import (
    DataLossLevel,
    RecoveryPath,
    FileRecoveryStrategy,
)
from .quality import (
    QualityReport,
    ConversionQualityEstimator,
)
from .pipeline import (
    DiagnosticPipeline,
)
from .config_validator import (
    ConfigValidator,
)
from .tracker import (
    IncrementalConversionTracker,
)
from .report_gen import (
    StructuredReportGenerator,
)
from .history import (
    HistoryEntry,
    ConversionHistoryManager,
)
from .olb_integrity import (
    OLBIntegrityChecker,
    OLB_ERROR_CODES,
)
from .multi_source import (
    MultiSourceCrossValidator,
    MultiSourceValidationReport,
    MultiSourceIssue,
    PstxnetData,
    parse_pstxnet,
)

__all__ = [
    # Enums
    "Severity",
    "ActionVerb",
    "FileState",
    "DataLossLevel",
    # Data models
    "DiagnosisError",
    "DiagnosticReport",
    "FileStatus",
    "ProjectInventory",
    "DSNInternalInventory",
    "ActionItem",
    "ReadinessReport",
    "ErrorCodeTemplate",
    "RecoveryPath",
    "QualityReport",
    # Error codes
    "ERROR_CODES",
    # Engines (Phase I)
    "FileInventory",
    "DSNInternalInventoryBuilder",
    "ProjectFileValidator",
    "DependencyResolver",
    "ConversionReadinessEvaluator",
    # Engines (Phase II)
    "ErrorDiagnosisEngine",
    "FileRecoveryStrategy",
    "ConversionQualityEstimator",
    "DiagnosticPipeline",
    "ConfigValidator",
    "IncrementalConversionTracker",
    "StructuredReportGenerator",
    "HistoryEntry",
    "ConversionHistoryManager",
    # OLB integrity
    "OLBIntegrityChecker",
    "OLB_ERROR_CODES",
    # Multi-source cross-validation
    "MultiSourceCrossValidator",
    "MultiSourceValidationReport",
    "MultiSourceIssue",
    "PstxnetData",
    "parse_pstxnet",
]
