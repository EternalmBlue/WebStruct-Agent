import type { Dispatch, SetStateAction } from "react";
import { FloppyDisk } from "@phosphor-icons/react";

import type {
  ExtractionResponse,
  ReviewField,
  RunState,
} from "../../types/webstruct";
import { updateReviewField } from "../../lib/reviewFields";

export function ManualReviewPanel({
  extraction,
  reviewFields,
  setReviewFields,
  ruleName,
  setRuleName,
  markProgramVerified,
  setMarkProgramVerified,
  reviewState,
  reviewMessage,
  onSubmitReview,
}: {
  extraction: ExtractionResponse | null;
  reviewFields: ReviewField[];
  setReviewFields: Dispatch<SetStateAction<ReviewField[]>>;
  ruleName: string;
  setRuleName: (value: string) => void;
  markProgramVerified: boolean;
  setMarkProgramVerified: (value: boolean) => void;
  reviewState: RunState;
  reviewMessage: string;
  onSubmitReview: () => void;
}) {
  return (
    <section className="panel review-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-kicker">REVIEW</p>
          <h2>复核并保存规则</h2>
        </div>
        <button
          className="button-secondary"
          type="button"
          onClick={onSubmitReview}
          disabled={
            !extraction?.program_spec ||
            reviewState === "running" ||
            (markProgramVerified && !ruleName.trim())
          }
        >
          {reviewState === "running" ? (
            "保存中"
          ) : (
            <>
              <FloppyDisk size={15} weight="fill" />
              保存规则草稿
            </>
          )}
        </button>
      </div>
      {reviewFields.length ? (
        <div className="review-list">
          <label className="review-rule-name">
            <span>规则名称</span>
            <input
              value={ruleName}
              onChange={(event) => setRuleName(event.target.value)}
              placeholder="例如：中石油新闻详情页抽取规则"
            />
            <small>保存为可复用规则后，运行页会用这个名称展示。</small>
          </label>
          {reviewFields.map((field, index) => (
            <article className="review-item" key={field.field_name}>
              <div className="review-item-header">
                <strong>{field.field_name}</strong>
                <label className="checkbox-control compact-checkbox">
                  <input
                    type="checkbox"
                    checked={field.accepted}
                    onChange={(event) =>
                      setReviewFields((current) =>
                        updateReviewField(current, index, {
                          ...field,
                          accepted: event.target.checked,
                        })
                      )
                    }
                  />
                  接受
                </label>
              </div>
              <label>
                <span>确认值</span>
                <input
                  value={field.value}
                  onChange={(event) =>
                    setReviewFields((current) =>
                      updateReviewField(current, index, {
                        ...field,
                        value: event.target.value,
                      })
                    )
                  }
                />
              </label>
              <label>
                <span>备注</span>
                <input
                  value={field.note}
                  onChange={(event) =>
                    setReviewFields((current) =>
                      updateReviewField(current, index, {
                        ...field,
                        note: event.target.value,
                      })
                    )
                  }
                />
              </label>
            </article>
          ))}
          <label className="checkbox-control verify-program">
            <input
              type="checkbox"
              checked={markProgramVerified}
              onChange={(event) => setMarkProgramVerified(event.target.checked)}
            />
            保存为可复用规则
          </label>
          <p className="verify-program-note">
            勾选后，这个 ProgramSpec 会进入“运行规则”页，供同类页面直接复用。
          </p>
          {reviewMessage ? (
            <p className="success-banner">{reviewMessage}</p>
          ) : null}
        </div>
      ) : (
        <div className="empty-state">
          <strong>暂无可复核字段</strong>
          <p>抽取完成后，可以在这里确认字段值，并决定是否保存为可复用规则。</p>
        </div>
      )}
    </section>
  );
}
