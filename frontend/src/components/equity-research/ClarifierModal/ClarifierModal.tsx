import { useState } from "react";
import type { ClarifierOutput } from "../../../api/clarifier";
import styles from "./ClarifierModal.module.css";

interface Props {
  output: ClarifierOutput;
  round: number;
  onSubmit: (data: {
    warningActions: Record<string, string>;
    clarifications: Record<string, string>;
    questionAnswers: Record<string, string>;
  }) => void;
  onCancel: () => void;
}

const MAX_ROUNDS = 3;

export function ClarifierModal({ output, round, onSubmit, onCancel }: Props) {
  const [warningActions, setWarningActions] = useState<Record<string, string>>({});
  const [clarifications, setClarifications] = useState<Record<string, string>>({});
  const [questionAnswers, setQuestionAnswers] = useState<Record<string, string>>({});

  const allWarningsResolved = output.blocking_warnings.every(
    (w) => warningActions[w.capability_id] !== undefined,
  );

  const showClarify = round < MAX_ROUNDS;

  return (
    <div className={styles.modal}>
      <div className={styles.header}>
        <h2>Clarifying questions</h2>
        <span className={styles.roundCounter}>
          Round {round} of {MAX_ROUNDS}
        </span>
      </div>

      {output.blocking_warnings.length > 0 && (
        <div className={styles.warningSection}>
          <h3>
            {output.blocking_warnings.length} capability warning(s)
          </h3>
          {output.blocking_warnings.map((w) => {
            const action = warningActions[w.capability_id];
            return (
              <div key={w.capability_id} className={styles.warning}>
                <p>"{w.detected_phrase}"</p>
                <p className={styles.warningMsg}>{w.user_message}</p>
                <div className={styles.actions}>
                  <button
                    className={action === "proceed_without" ? styles.selected : ""}
                    onClick={() =>
                      setWarningActions({
                        ...warningActions,
                        [w.capability_id]: "proceed_without",
                      })
                    }
                  >
                    Proceed without it
                  </button>
                  <button onClick={onCancel}>Cancel &amp; Edit</button>
                  {showClarify && (
                    <button
                      className={action === "clarify" ? styles.selected : ""}
                      onClick={() =>
                        setWarningActions({
                          ...warningActions,
                          [w.capability_id]: "clarify",
                        })
                      }
                    >
                      Clarify
                    </button>
                  )}
                </div>
                {action === "clarify" && (
                  <textarea
                    placeholder="What did you actually mean?"
                    value={clarifications[w.capability_id] ?? ""}
                    onChange={(e) =>
                      setClarifications({
                        ...clarifications,
                        [w.capability_id]: e.target.value,
                      })
                    }
                  />
                )}
              </div>
            );
          })}
        </div>
      )}

      {output.questions.map((q) => (
        <div key={q.id} className={styles.question}>
          <label htmlFor={`q-${q.id}`}>{q.text}</label>
          {q.kind === "multiple_choice" && q.options != null ? (
            <select
              id={`q-${q.id}`}
              value={questionAnswers[q.id] ?? ""}
              onChange={(e) =>
                setQuestionAnswers({ ...questionAnswers, [q.id]: e.target.value })
              }
            >
              <option value="">—</option>
              {q.options.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          ) : (
            <input
              id={`q-${q.id}`}
              type="text"
              value={questionAnswers[q.id] ?? ""}
              onChange={(e) =>
                setQuestionAnswers({ ...questionAnswers, [q.id]: e.target.value })
              }
            />
          )}
        </div>
      ))}

      <button
        disabled={!allWarningsResolved}
        onClick={() => onSubmit({ warningActions, clarifications, questionAnswers })}
      >
        Submit answers
      </button>
    </div>
  );
}
