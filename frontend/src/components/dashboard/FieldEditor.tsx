import { Trash } from "@phosphor-icons/react";

import type { FieldSpec } from "../../types/webstruct";
import { FIELD_TYPE_OPTIONS } from "../../lib/schemaDraft";

export function FieldEditor({
  field,
  index,
  onChange,
  onRemove,
  disabled = false,
}: {
  field: FieldSpec;
  index: number;
  onChange: (field: FieldSpec) => void;
  onRemove: () => void;
  disabled?: boolean;
}) {
  return (
    <article className="field-editor">
      <div className="field-editor-header">
        <strong>字段 {index + 1}</strong>
        <button
          className="icon-button danger-button"
          type="button"
          onClick={onRemove}
          disabled={disabled}
        >
          <Trash size={15} />
          <span>删除</span>
        </button>
      </div>
      <div className="field-editor-grid">
        <label>
          <span>字段名</span>
          <input
            value={field.name}
            onChange={(event) => onChange({ ...field, name: event.target.value })}
            disabled={disabled}
          />
        </label>
        <label>
          <span>类型</span>
          <select
            value={field.type}
            disabled={disabled}
            onChange={(event) =>
              onChange({
                ...field,
                type: event.target.value as FieldSpec["type"],
              })
            }
          >
            {FIELD_TYPE_OPTIONS.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>
        <label className="checkbox-control">
          <input
            type="checkbox"
            checked={field.required}
            disabled={disabled}
            onChange={(event) =>
              onChange({ ...field, required: event.target.checked })
            }
          />
          必填
        </label>
      </div>
      <label>
        <span>描述</span>
        <input
          value={field.description}
          disabled={disabled}
          onChange={(event) =>
            onChange({ ...field, description: event.target.value })
          }
        />
      </label>
      <label>
        <span>别名，用逗号分隔</span>
        <input
          value={field.aliases.join(",")}
          disabled={disabled}
          onChange={(event) =>
            onChange({
              ...field,
              aliases: event.target.value
                .split(",")
                .map((item) => item.trim())
                .filter(Boolean),
            })
          }
        />
      </label>
    </article>
  );
}
