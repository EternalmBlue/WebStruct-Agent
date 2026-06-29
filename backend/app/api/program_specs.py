from fastapi import APIRouter
from pydantic import BaseModel

from app.domain import SchemaSpec
from app.storage.program_repository import list_user_verified_program_specs

router = APIRouter(prefix="/program-specs", tags=["program-specs"])


class VerifiedProgramSpecSummary(BaseModel):
    schema_signature: str
    schema_name: str
    rule_name: str = ""
    schema_spec: SchemaSpec
    program_count: int
    created_at: str


@router.get("/verified", response_model=list[VerifiedProgramSpecSummary])
def list_verified_program_specs() -> list[dict[str, object]]:
    return list_user_verified_program_specs()
