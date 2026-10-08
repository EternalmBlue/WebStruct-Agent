import { ChatCircleText, CheckCircle, MagicWand, Play } from "@phosphor-icons/react";

import type {
  ExtractionResponse,
  RunState,
  SpecAssistantResponse,
} from "../../types/webstruct";

export function SpecAssistantPanel({
  extraction,
  draft,
  message,
  setMessage,
  state,
  error,
  isOpen,
  setIsOpen,
  onSend,
  onApply,
  onRerun,
}: {
  extraction: ExtractionResponse | null;
  draft: SpecAssistantResponse | null;
  message: string;
  setMessage: (message: string) => void;
  state: RunState;
  error: string;
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
  onSend: () => void;
  onApply: () => void;
  onRerun: () => void;
}) {
  if (!extraction) {
    return null;
  }

  return (
    <div className="spec-assistant">
      <button
        className="button-secondary spec-assistant-trigger"
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <ChatCircleText size={16} weight="duotone" />
        让 AI 修订规则
      </button>
      {isOpen ? (
        <div className="spec-assistant-popover">
          <div className="spec-assistant-chat">
            <div className="assistant-copy">
              <strong>规则修订助手</strong>
              <p>描述字段、证据位置或页面对应关系，AI 会基于当前页面内容修订字段和 ProgramSpec 草稿。</p>
            </div>
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              rows={4}
              placeholder="例如：把作者字段对应到页面上方的署名；发布日期取正文标题下方日期，不要取底部更新时间。"
            />
            {error ? <p className="inline-error">{error}</p> : null}
            {draft ? (
              <div className="assistant-reply">
                <strong>AI 回复</strong>
                <p>{draft.assistant_message}</p>
              </div>
            ) : null}
            <div className="inline-actions">
              <button
                className="primary-button"
                type="button"
                onClick={onSend}
                disabled={!message.trim() || state === "running"}
              >
                {state === "running" ? (
                  "修订中"
                ) : (
                  <>
                    <MagicWand size={15} weight="fill" />
                    生成修订建议
                  </>
                )}
              </button>
              <button
                className="button-secondary"
                type="button"
                onClick={onApply}
                disabled={!draft || state === "running"}
              >
                <CheckCircle size={15} weight="fill" />
                替换当前草稿
              </button>
              <button
                className="button-secondary"
                type="button"
                onClick={onRerun}
                disabled={!draft || state === "running"}
              >
                <Play size={15} weight="fill" />
                用新规则重新运行
              </button>
            </div>
            {draft ? (
              <p className="assistant-hint">
                替换草稿只更新字段和规则预览；重新运行才会重新计算抽取结果。
              </p>
            ) : null}
          </div>
          <aside className="spec-assistant-preview">
            <div className="assistant-copy">
              <strong>{draft?.schema_spec.name ?? extraction.schema_spec.name}</strong>
              <p>
                {draft
                  ? `${draft.schema_spec.fields.length} 个字段，${draft.program_spec.field_programs.length} 条 ProgramSpec 规则`
                  : "生成修订建议后会在这里预览字段契约。"}
              </p>
            </div>
            {draft?.change_summary.length ? (
              <ul className="compact-list">
                {draft.change_summary.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
            {draft?.validation_issues.length ? (
              <ul className="compact-list warning-list">
                {draft.validation_issues.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
            <div className="field-preview-list">
              {(draft?.schema_spec.fields ?? extraction.schema_spec.fields).map((field) => (
                <div className="field-preview" key={field.name}>
                  <strong>{field.description || field.name}</strong>
                  <span>
                    {field.name} · {field.type}
                    {field.required ? " · 必填" : ""}
                  </span>
                </div>
              ))}
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}
