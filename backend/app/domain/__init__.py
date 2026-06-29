"""Domain models shared by APIs, workflows, and persistence."""

from app.domain.api_models import (
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
from app.domain.benchmark import (
    BenchmarkDataset,
    BenchmarkItem,
    BenchmarkMethodResult,
    BenchmarkReport,
)
from app.domain.evidence import (
    EvidenceBundle,
    FieldEvidence,
    VerificationIssue,
    VerificationReport,
)
from app.domain.extraction import (
    ExtractionPlan,
    ExtractionResult,
    FieldExtractionPlan,
    FieldExtractionResult,
)
from app.domain.page import PageObservation, ViewBundle
from app.domain.program import FieldProgramSpec, ProgramSpec
from app.domain.schema import FieldSpec, SchemaSpec
from app.domain.state import GraphRunState
from app.domain.trace import AgentRunTrace
from app.domain.types import (
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
    "PostprocessFunction",
    "ProgramSpec",
    "ProgramStrategy",
    "SchemaSpec",
    "SpecAssistantRequest",
    "SpecAssistantResponse",
    "VerificationIssue",
    "VerificationReport",
    "ViewBundle",
]
