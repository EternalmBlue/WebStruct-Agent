import type { FieldSpec, SchemaSpec } from "../types/webstruct";

export const FIELD_TYPE_OPTIONS: FieldSpec["type"][] = [
  "string",
  "text",
  "number",
  "date",
  "url",
  "list",
];

export function cloneSchema(schema: SchemaSpec): SchemaSpec {
  return JSON.parse(JSON.stringify(schema)) as SchemaSpec;
}

export function updateField(
  schema: SchemaSpec | null,
  index: number,
  field: FieldSpec
): SchemaSpec | null {
  if (!schema) {
    return schema;
  }
  const fields = [...schema.fields];
  fields[index] = field;
  return { ...schema, fields };
}

export function removeField(
  schema: SchemaSpec | null,
  index: number
): SchemaSpec | null {
  if (!schema) {
    return schema;
  }
  return { ...schema, fields: schema.fields.filter((_, i) => i !== index) };
}

export function appendEmptyField(schema: SchemaSpec | null): SchemaSpec | null {
  if (!schema) {
    return schema;
  }
  return {
    ...schema,
    fields: [
      ...schema.fields,
      {
        name: `field_${schema.fields.length + 1}`,
        description: "新字段",
        type: "string",
        required: false,
        aliases: [],
        examples: [],
      },
    ],
  };
}
