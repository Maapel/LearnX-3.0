"use client";

import { useState } from "react";
import { Exercise } from "@/types/course";

interface QuizWidgetProps {
  exercises: Exercise[];
}

interface QuestionState {
  selected: string | null;
  revealed: boolean;
}

export default function QuizWidget({ exercises }: QuizWidgetProps) {
  const [states, setStates] = useState<QuestionState[]>(
    exercises.map(() => ({ selected: null, revealed: false }))
  );

  if (!exercises || exercises.length === 0) return null;

  function handleSelect(qIdx: number, option: string) {
    if (states[qIdx].revealed) return;
    setStates((prev) => {
      const next = [...prev];
      next[qIdx] = { selected: option, revealed: true };
      return next;
    });
  }

  const score = states.filter(
    (s, i) => s.revealed && s.selected === exercises[i].correct_answer
  ).length;
  const answeredCount = states.filter((s) => s.revealed).length;
  const allDone = answeredCount === exercises.length;

  return (
    <div
      style={{
        marginTop: "2rem",
        display: "flex",
        flexDirection: "column",
        gap: "1.5rem",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h3
          style={{
            margin: 0,
            fontSize: "1rem",
            fontWeight: 700,
            color: "var(--text-primary)",
          }}
        >
          🧠 Practice Questions
        </h3>
        {allDone && (
          <span
            style={{
              fontSize: "0.8rem",
              fontWeight: 600,
              padding: "0.25em 0.75em",
              borderRadius: "999px",
              background: score === exercises.length ? "#14532d" : "#1e3a5f",
              color: score === exercises.length ? "#86efac" : "#bfdbfe",
              border: `1px solid ${score === exercises.length ? "#22c55e44" : "#3b82f644"}`,
            }}
          >
            {score}/{exercises.length} correct
          </span>
        )}
      </div>

      {exercises.map((ex, qIdx) => {
        const state = states[qIdx];
        const isCorrect = state.selected === ex.correct_answer;

        return (
          <div
            key={qIdx}
            style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border)",
              borderRadius: "12px",
              padding: "1.25rem",
            }}
          >
            <p
              style={{
                margin: "0 0 1rem",
                fontSize: "0.9375rem",
                fontWeight: 600,
                color: "var(--text-primary)",
                lineHeight: 1.5,
              }}
            >
              {qIdx + 1}. {ex.question}
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {ex.options.map((opt, oIdx) => {
                const isSelected = state.selected === opt;
                const isCorrectOpt = opt === ex.correct_answer;
                let bg = "var(--bg-hover)";
                let border = "1px solid var(--border)";
                let color = "var(--text-secondary)";

                if (state.revealed) {
                  if (isCorrectOpt) {
                    bg = "#14532d";
                    border = "1px solid #22c55e";
                    color = "#86efac";
                  } else if (isSelected && !isCorrectOpt) {
                    bg = "#7f1d1d";
                    border = "1px solid #ef4444";
                    color = "#fca5a5";
                  }
                } else if (isSelected) {
                  bg = "var(--accent)";
                  border = "1px solid var(--accent)";
                  color = "#fff";
                }

                return (
                  <button
                    key={oIdx}
                    onClick={() => handleSelect(qIdx, opt)}
                    disabled={state.revealed}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.75rem",
                      width: "100%",
                      padding: "0.65rem 1rem",
                      background: bg,
                      border,
                      borderRadius: "8px",
                      color,
                      fontSize: "0.875rem",
                      fontFamily: "inherit",
                      textAlign: "left",
                      cursor: state.revealed ? "default" : "pointer",
                      transition: "all 0.15s",
                      fontWeight: isSelected || (state.revealed && isCorrectOpt) ? 600 : 400,
                    }}
                    onMouseEnter={(e) => {
                      if (!state.revealed)
                        e.currentTarget.style.borderColor = "var(--accent)";
                    }}
                    onMouseLeave={(e) => {
                      if (!state.revealed)
                        e.currentTarget.style.borderColor = "var(--border)";
                    }}
                  >
                    <span
                      style={{
                        width: "22px",
                        height: "22px",
                        borderRadius: "50%",
                        border: `2px solid ${color}`,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "0.7rem",
                        flexShrink: 0,
                        fontWeight: 700,
                      }}
                    >
                      {state.revealed && isCorrectOpt
                        ? "✓"
                        : state.revealed && isSelected && !isCorrectOpt
                        ? "✗"
                        : String.fromCharCode(65 + oIdx)}
                    </span>
                    {opt}
                  </button>
                );
              })}
            </div>

            {state.revealed && (
              <div
                style={{
                  marginTop: "1rem",
                  padding: "0.875rem 1rem",
                  borderRadius: "8px",
                  background: isCorrect ? "#052e16" : "#450a0a",
                  border: `1px solid ${isCorrect ? "#166534" : "#7f1d1d"}`,
                  display: "flex",
                  gap: "0.5rem",
                  alignItems: "flex-start",
                }}
              >
                <span style={{ flexShrink: 0, fontSize: "1rem" }}>
                  {isCorrect ? "✅" : "❌"}
                </span>
                <div>
                  {!isCorrect && (
                    <p
                      style={{
                        margin: "0 0 0.25rem",
                        fontSize: "0.8rem",
                        fontWeight: 600,
                        color: "#fca5a5",
                      }}
                    >
                      Correct answer: {ex.correct_answer}
                    </p>
                  )}
                  <p
                    style={{
                      margin: 0,
                      fontSize: "0.85rem",
                      color: isCorrect ? "#86efac" : "#fca5a5",
                      lineHeight: 1.5,
                    }}
                  >
                    {ex.explanation}
                  </p>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
