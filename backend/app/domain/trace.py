from pydantic import BaseModel, Field

from app.domain.types import AgentStatus


class AgentRunTrace(BaseModel):
    name: str
    role: str
    status: AgentStatus
    runtime_ms: int = Field(ge=0)
    input_summary: str = ""
    output_summary: str = ""
    error_message: str | None = None
