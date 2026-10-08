"""契约层：供 API、工作流与持久化共享的类型化输入输出对象。

这是 SchemaSpec / ProgramSpec / EvidenceBundle / GraphRunState 等对象的唯一来源，
行为由 specs/features/*.feature 描述，任何字段变更都要先改规范。
"""

from app.contracts.api_models import (
    BenchmarkRequest,
    BenchmarkResponse,
    ExtractionRequest,
    ExtractionResponse,
    ManualReviewField,
    ManualReviewRequest,
    ManualReviewResponse,
    SpecAssistantRequest,
    SpecAssistantResponse,
)
from app.contracts.benchmark import (
    BenchmarkDataset,
    BenchmarkItem,
    BenchmarkMethodResult,
    BenchmarkReport,
    MetricEnvelope,
)
from app.contracts.evidence import (
    EvidenceBundle,
    FieldEvidence,
    VerificationIssue,
    VerificationReport,
)
from app.contracts.extraction import (
    ExtractionPlan,
    ExtractionResult,
    FieldExtractionPlan,
    FieldExtractionResult,
)
from app.contracts.page import PageObservation, ViewBundle
from app.contracts.program import FieldProgramSpec, ProgramSpec
from app.contracts.rsi import RSIIterationRequest, RSIIterationResponse
from app.contracts.schema import FieldSpec, SchemaSpec
from app.contracts.single_page import (
    BodyCandidate,
    BodyQualityMetrics,
    BodySelection,
    PageIntentAssessment,
    PageStructureSignature,
    StructureCompatibility,
)
from app.contracts.state import GraphRunState
from app.contracts.trace import AgentRunTrace
from app.contracts.types import (
    AgentStatus,
    FieldType,
    PostprocessFunction,
    ProgramStrategy,
)

__all__ = [
    "AgentRunTrace",
    "AgentStatus",
    "BenchmarkDataset",
    "BenchmarkItem",
    "BenchmarkMethodResult",
    "BenchmarkReport",
    "BodyCandidate",
    "BodyQualityMetrics",
    "BodySelection",
    "MetricEnvelope",
    "RSIIterationRequest",
    "RSIIterationResponse",
    "BenchmarkRequest",
    "BenchmarkResponse",
    "EvidenceBundle",
    "ExtractionPlan",
    "ExtractionRequest",
    "ExtractionResponse",
    "ExtractionResult",
    "FieldEvidence",
    "FieldExtractionPlan",
    "FieldExtractionResult",
    "FieldProgramSpec",
    "FieldSpec",
    "FieldType",
    "GraphRunState",
    "ManualReviewField",
    "ManualReviewRequest",
    "ManualReviewResponse",
    "PageObservation",
    "PageIntentAssessment",
    "PageStructureSignature",
    "PostprocessFunction",
    "ProgramSpec",
    "ProgramStrategy",
    "SchemaSpec",
    "SpecAssistantRequest",
    "SpecAssistantResponse",
    "StructureCompatibility",
    "VerificationIssue",
    "VerificationReport",
    "ViewBundle",
]
