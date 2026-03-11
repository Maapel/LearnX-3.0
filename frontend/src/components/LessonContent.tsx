"use client";

import ReactMarkdown from "react-markdown";
import SyntaxHighlighter from "react-syntax-highlighter/dist/esm/prism";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { LessonDetail, LessonSection, LessonSource } from "@/types/course";
import VideoEmbed from "./VideoEmbed";
import QuizWidget from "./QuizWidget";

interface LessonContentProps {
  lesson: LessonDetail;
}

// Renders markdown with syntax-highlighted code blocks
function RichMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      components={{
        code({ className, children }) {
          const match = /language-(\w+)/.exec(className || "");
          if (match) {
            return (
              <SyntaxHighlighter
                style={oneDark as Record<string, React.CSSProperties>}
                language={match[1]}
                PreTag="div"
                customStyle={{ borderRadius: "8px", fontSize: "0.875rem", margin: "0.75rem 0 0" }}
              >
                {String(children).replace(/\n$/, "")}
              </SyntaxHighlighter>
            );
          }
          return (
            <code
              style={{
                background: "var(--code-bg)",
                padding: "0.15em 0.4em",
                borderRadius: "4px",
                fontSize: "0.875em",
                fontFamily: "monospace",
                color: "#a5b4fc",
              }}
            >
              {children}
            </code>
          );
        },
        p({ children }) {
          return (
            <p style={{ margin: "0 0 0.875rem", lineHeight: 1.75, color: "var(--text-secondary)" }}>
              {children}
            </p>
          );
        },
        ul({ children }) {
          return (
            <ul style={{ margin: "0 0 0.875rem", paddingLeft: "1.5rem", color: "var(--text-secondary)", lineHeight: 1.75 }}>
              {children}
            </ul>
          );
        },
        li({ children }) {
          return <li style={{ marginBottom: "0.3rem" }}>{children}</li>;
        },
        strong({ children }) {
          return <strong style={{ color: "var(--text-primary)", fontWeight: 700 }}>{children}</strong>;
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function SectionCard({ section }: { section: LessonSection }) {
  return (
    <div
      style={{
        marginBottom: "2rem",
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderRadius: "14px",
        overflow: "hidden",
      }}
    >
      {/* Section header */}
      <div
        style={{
          padding: "1rem 1.5rem 0.875rem",
          borderBottom: "1px solid var(--border)",
          background: "var(--bg-secondary)",
        }}
      >
        <h2
          style={{
            margin: 0,
            fontSize: "1.05rem",
            fontWeight: 700,
            color: "var(--text-primary)",
            lineHeight: 1.3,
          }}
        >
          {section.section_title}
        </h2>
      </div>

      {/* Explanation */}
      <div style={{ padding: "1.25rem 1.5rem 0.5rem" }}>
        <RichMarkdown content={section.explanation} />
      </div>

      {/* Analogy callout */}
      {section.visual_analogy && (
        <div
          style={{
            margin: "0 1.5rem 1rem",
            padding: "0.875rem 1rem",
            background: "linear-gradient(135deg, #1c1917 0%, #292524 100%)",
            border: "1px solid #44403c",
            borderLeft: "3px solid #f59e0b",
            borderRadius: "8px",
            display: "flex",
            gap: "0.6rem",
            alignItems: "flex-start",
          }}
        >
          <span style={{ fontSize: "1rem", flexShrink: 0 }}>💡</span>
          <div>
            <p
              style={{
                margin: "0 0 0.15rem",
                fontSize: "0.7rem",
                fontWeight: 700,
                color: "#d97706",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              Analogy
            </p>
            <p style={{ margin: 0, fontSize: "0.9rem", color: "#d6d3d1", lineHeight: 1.6 }}>
              {section.visual_analogy}
            </p>
          </div>
        </div>
      )}

      {/* Code snippet */}
      {section.code_snippet && (
        <div style={{ margin: "0 1.5rem 1.25rem" }}>
          <SyntaxHighlighter
            style={oneDark as Record<string, React.CSSProperties>}
            language={
              (() => {
                const match = /```(\w+)/.exec(section.code_snippet);
                return match ? match[1] : "text";
              })()
            }
            PreTag="div"
            customStyle={{ borderRadius: "8px", fontSize: "0.875rem", margin: 0 }}
          >
            {section.code_snippet
              .replace(/^```\w*\n?/, "")
              .replace(/\n?```$/, "")
              .trim()}
          </SyntaxHighlighter>
        </div>
      )}
    </div>
  );
}

function SourcesSection({ sources }: { sources: LessonSource[] }) {
  if (!sources || sources.length === 0) return null;
  return (
    <div
      style={{
        marginTop: "1.5rem",
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderRadius: "12px",
        padding: "1.25rem 1.5rem",
      }}
    >
      <h3
        style={{
          margin: "0 0 0.875rem",
          fontSize: "0.8rem",
          fontWeight: 700,
          color: "var(--text-primary)",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
        }}
      >
        📚 Further Reading
      </h3>
      <ul
        style={{
          margin: 0,
          padding: 0,
          listStyle: "none",
          display: "flex",
          flexDirection: "column",
          gap: "0.75rem",
        }}
      >
        {sources.map((src, i) => (
          <li key={i}>
            <a
              href={src.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "block",
                textDecoration: "none",
                padding: "0.6rem 0.875rem",
                background: "var(--bg-secondary)",
                border: "1px solid var(--border)",
                borderRadius: "8px",
                transition: "border-color 0.15s",
              }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = "#6366f1")}
              onMouseLeave={e => (e.currentTarget.style.borderColor = "var(--border)")}
            >
              <div
                style={{
                  fontSize: "0.9rem",
                  fontWeight: 600,
                  color: "#818cf8",
                  marginBottom: src.snippet ? "0.2rem" : 0,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {src.title}
              </div>
              {src.snippet && (
                <div
                  style={{
                    fontSize: "0.8rem",
                    color: "var(--text-muted)",
                    lineHeight: 1.5,
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                  }}
                >
                  {src.snippet}
                </div>
              )}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function LessonContent({ lesson }: LessonContentProps) {
  return (
    <div
      style={{
        maxWidth: "820px",
        margin: "0 auto",
        padding: "2rem 2rem 5rem",
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: "1.75rem" }}>
        <h1
          style={{
            margin: "0 0 0.6rem",
            fontSize: "1.8rem",
            fontWeight: 800,
            color: "var(--text-primary)",
            lineHeight: 1.2,
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
            padding: "0.2em 0.85em",
          }}
        >
          ⏱ {lesson.estimated_time_minutes} min read
        </span>
      </div>

      {/* Video embed */}
      {lesson.video_url && (
        <VideoEmbed url={lesson.video_url} title={lesson.lesson_title} />
      )}

      {/* Content sections */}
      {lesson.sections && lesson.sections.length > 0 && (
        <div style={{ marginBottom: "1rem" }}>
          {lesson.sections.map((section, i) => (
            <SectionCard key={i} section={section} />
          ))}
        </div>
      )}

      {/* Quiz */}
      {lesson.exercises && lesson.exercises.length > 0 && (
        <QuizWidget exercises={lesson.exercises} />
      )}

      {/* Sources */}
      <SourcesSection sources={lesson.sources ?? []} />

      {/* Key takeaways */}
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
              fontSize: "0.8rem",
              fontWeight: 700,
              color: "var(--text-primary)",
              letterSpacing: "0.08em",
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
                    marginTop: "3px",
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
