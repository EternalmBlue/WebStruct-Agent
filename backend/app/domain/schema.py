from pydantic import BaseModel, Field, field_validator

from app.domain.types import FieldType


class FieldSpec(BaseModel):
    name: str
    description: str = ""
    type: FieldType = "string"
    required: bool = True
    aliases: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)


class SchemaSpec(BaseModel):
    name: str
    description: str = ""
    domain: str = ""
    fields: list[FieldSpec]

    @field_validator("fields")
    @classmethod
    def fields_must_be_unique(cls, fields: list[FieldSpec]) -> list[FieldSpec]:
        names = [field.name for field in fields]
        if len(names) != len(set(names)):
            raise ValueError("field names must be unique")
        return fields
