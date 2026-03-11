"use client";

import { LessonDetail } from "@/types/course";
import VideoEmbed from "./VideoEmbed";
import QuizWidget from "./QuizWidget";
import SyntaxHighlighter from "react-syntax-highlighter/dist/esm/prism";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

interface LessonContentProps {
  lesson: LessonDetail;
}

function extractCodeBlocks(text: string): { type: "text" | "code"; lang: string; content: string }[] {
  const parts: { type: "text" | "code"; lang: string; content: string }[] = [];
  const regex = /```(\w*)\n([\s\S]*?)```/g;
  let lastIndex = 0;
  let match;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: "text", lang: "", content: text.slice(lastIndex, match.index) });
    }
    parts.push({ type: "code", lang: match[1] || "text", content: match[2] });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    parts.push({ type: "text", lang: "", content: text.slice(lastIndex) });
  }
  return parts;
}

export default function LessonContent({ lesson }: LessonContentProps) {
  const exampleParts = lesson.practical_example
    ? extractCodeBlocks(lesson.practical_example)
    : [];

  return (
    <div
      style={{
        maxWidth: "780px",
        margin: "0 auto",
        padding: "2rem 2rem 4rem",
        display: "flex",
        flexDirection: "column",
        gap: "0",
      }}
    >
      {/* ── Header ── */}
      <div style={{ marginBottom: "1.5rem" }}>
        <h1
          style={{
            margin: "0 0 0.5rem",
            fontSize: "1.75rem",
            fontWeight: 700,
            color: "var(--text-primary)",
            lineHeight: 1.25,
          }}
        >
          {lesson.lesson_title}
        </h1>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.35rem",
            fontSize: "0.78rem",
            fontWeight: 600,
            color: "var(--text-muted)",
            background: "var(--bg-hover)",
            border: "1px solid var(--border)",
            borderRadius: "999px",
            padding: "0.2em 0.75em",
          }}
        >
          ⏱ {lesson.estimated_time_minutes} min
        </span>
      </div>

      {/* ── Video ── */}
      {lesson.video_url && (
        <VideoEmbed url={lesson.video_url} title={lesson.lesson_title} />
      )}

      {/* ── Concept Summary ── */}
      <div
        style={{
          background: "linear-gradient(135deg, #1e1b4b 0%, #312e81 100%)",
          border: "1px solid #4338ca55",
          borderRadius: "12px",
          padding: "1.5rem",
          marginBottom: "1.5rem",
        }}
      >
        <p
          style={{
            margin: "0 0 0.5rem",
            fontSize: "0.72rem",
            fontWeight: 700,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "#a5b4fc",
          }}
        >
          💡 Core Concept
        </p>
        <p
          style={{
            margin: 0,
            fontSize: "1.1rem",
            lineHeight: 1.75,
            color: "#e0e7ff",
            fontWeight: 400,
          }}
        >
          {lesson.concept_summary}
        </p>
      </div>

      {/* ── Practical Example ── */}
      {lesson.practical_example && exampleParts.length > 0 && (
        <div
          style={{
            borderRadius: "12px",
            overflow: "hidden",
            border: "1px solid var(--border)",
            marginBottom: "1.5rem",
          }}
        >
          <div
            style={{
              padding: "0.6rem 1rem",
              background: "#161b22",
              borderBottom: "1px solid var(--border)",
              fontSize: "0.75rem",
              fontWeight: 600,
              color: "#7d8590",
              letterSpacing: "0.05em",
              textTransform: "uppercase",
            }}
          >
            🔧 Practical Example
          </div>
          <div style={{ background: "var(--code-bg)" }}>
            {exampleParts.map((part, i) =>
              part.type === "code" ? (
                <SyntaxHighlighter
                  key={i}
                  style={oneDark as Record<string, React.CSSProperties>}
                  language={part.lang}
                  PreTag="div"
                  customStyle={{ margin: 0, borderRadius: 0, fontSize: "0.875rem" }}
                >
                  {part.content.trim()}
                </SyntaxHighlighter>
              ) : (
                part.content.trim() ? (
                  <p
                    key={i}
                    style={{
                      margin: 0,
                      padding: "0.75rem 1rem",
                      color: "var(--text-secondary)",
                      fontSize: "0.9rem",
                      lineHeight: 1.6,
                    }}
                  >
                    {part.content.trim()}
                  </p>
                ) : null
              )
            )}
          </div>
        </div>
      )}

      {/* ── Quiz ── */}
      {lesson.exercises && lesson.exercises.length > 0 && (
        <QuizWidget exercises={lesson.exercises} />
      )}

      {/* ── Key Takeaways ── */}
      {lesson.key_takeaways && lesson.key_takeaways.length > 0 && (
        <div
          style={{
            marginTop: "2rem",
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            borderRadius: "12px",
            padding: "1.25rem 1.5rem",
          }}
        >
          <h3
            style={{
              margin: "0 0 0.875rem",
              fontSize: "0.875rem",
              fontWeight: 700,
              color: "var(--text-primary)",
              letterSpacing: "0.05em",
              textTransform: "uppercase",
            }}
          >
            🎯 Key Takeaways
          </h3>
          <ul
            style={{
              margin: 0,
              padding: 0,
              listStyle: "none",
              display: "flex",
              flexDirection: "column",
              gap: "0.6rem",
            }}
          >
            {lesson.key_takeaways.map((t, i) => (
              <li
                key={i}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "0.6rem",
                  color: "var(--text-secondary)",
                  fontSize: "0.9375rem",
                  lineHeight: 1.55,
                }}
              >
                <span
                  style={{
                    flexShrink: 0,
                    marginTop: "2px",
                    width: "18px",
                    height: "18px",
                    borderRadius: "50%",
                    background: "#14532d",
                    border: "1px solid #22c55e44",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "0.65rem",
                    color: "#86efac",
                    fontWeight: 700,
                  }}
                >
                  ✓
                </span>
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
