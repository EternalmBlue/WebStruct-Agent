# Schema Spec

## Purpose

`SchemaSpec` will describe target information fields before extraction starts.

## Planned Objects

- `SchemaSpec`
- `FieldSpec`

## Implemented Status

`SchemaSpec` and `FieldSpec` are implemented as Pydantic models in the backend.

Built-in schemas are available from:

- `GET /api/schemas`

Current built-in schemas:

- 高校通知
- 招聘公告
- 政务公开 / 政策法规

Custom schemas can be supplied to `POST /api/extract` through `schema_spec`.
The frontend workbench can start from a built-in schema, then add, edit, and
remove fields before extraction. The backend validates custom schemas through
`POST /api/schemas/validate`.

Validated schemas and schemas used by persisted extraction runs are recorded in
PostgreSQL by stable schema signature. Schema versions can be read back through:

- `GET /api/schemas/versions`
- `GET /api/schemas/versions?schema_name=高校通知`

## Editable Field Example

```json
{
  "name": "deadline",
  "description": "截止日期或报名截止时间",
  "type": "date",
  "required": false,
  "aliases": ["截止时间", "截止日期", "报名截止"],
  "examples": []
}
```

Validation currently checks that schemas have fields, field names are non-empty,
required fields have descriptions, and date fields include date/time semantics in
their description or aliases.
