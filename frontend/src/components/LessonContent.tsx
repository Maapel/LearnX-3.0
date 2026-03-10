"use client";

import ReactMarkdown from "react-markdown";
import SyntaxHighlighter from "react-syntax-highlighter/dist/esm/prism";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Lesson, ContentType } from "@/types/course";

interface LessonContentProps {
  lesson: Lesson;
}

function getYouTubeVideoId(url: string): string | null {
  try {
    const parsed = new URL(url);
    if (parsed.hostname === "youtu.be") {
      return parsed.pathname.slice(1).split("?")[0] || null;
    }
    if (
      parsed.hostname === "www.youtube.com" ||
      parsed.hostname === "youtube.com"
    ) {
      return parsed.searchParams.get("v");
    }
  } catch {
    // invalid URL
  }
  return null;
}

function contentTypeBadgeStyle(type: ContentType): React.CSSProperties {
  const base: React.CSSProperties = {
    display: "inline-block",
    padding: "0.2em 0.65em",
    borderRadius: "999px",
    fontSize: "0.75rem",
    fontWeight: 600,
    letterSpacing: "0.02em",
    textTransform: "uppercase",
  };
  if (type === "video") {
    return { ...base, background: "#581c87", color: "#e9d5ff" };
  }
  if (type === "article") {
    return { ...base, background: "#1e3a5f", color: "#bfdbfe" };
  }
  // concept_breakdown
  return { ...base, background: "#2e1065", color: "#ddd6fe" };
}

export default function LessonContent({ lesson }: LessonContentProps) {
  const isYouTube =
    lesson.content_type === "video" &&
    lesson.source_url &&
    (lesson.source_url.includes("youtube.com") ||
      lesson.source_url.includes("youtu.be"));

  const videoId = isYouTube && lesson.source_url
    ? getYouTubeVideoId(lesson.source_url)
    : null;

  return (
    <div
      style={{
        maxWidth: "860px",
        margin: "0 auto",
        padding: "2rem 2rem 4rem",
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: "1.5rem" }}>
        <h1
          style={{
            margin: "0 0 0.75rem",
            fontSize: "1.75rem",
            fontWeight: 700,
            color: "var(--text-primary)",
            lineHeight: 1.3,
          }}
        >
          {lesson.lesson_title}
        </h1>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
          <span style={contentTypeBadgeStyle(lesson.content_type)}>
            {lesson.content_type === "video"
              ? "▶ Video"
              : lesson.content_type === "article"
              ? "📄 Article"
              : "💡 Concept"}
          </span>
          {lesson.source_url && (
            <a
              href={lesson.source_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: "var(--accent-light)",
                fontSize: "0.875rem",
                textDecoration: "none",
                display: "inline-flex",
                alignItems: "center",
                gap: "0.25rem",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.textDecoration = "underline";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.textDecoration = "none";
              }}
            >
              View Source →
            </a>
          )}
        </div>
      </div>

      {/* YouTube embed */}
      {videoId && (
        <div
          style={{
            position: "relative",
            paddingBottom: "56.25%",
            height: 0,
            overflow: "hidden",
            borderRadius: "8px",
            marginBottom: "1.5rem",
            maxHeight: "400px",
            background: "#000",
          }}
        >
          <iframe
            src={`https://www.youtube.com/embed/${videoId}`}
            title={lesson.lesson_title}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              border: "none",
              borderRadius: "8px",
            }}
          />
        </div>
      )}

      {/* Markdown content */}
      <div className="prose">
        <ReactMarkdown
          components={{
            code({ className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || "");
              const isBlock = match !== null;
              if (isBlock) {
                return (
                  <SyntaxHighlighter
                    style={oneDark as Record<string, React.CSSProperties>}
                    language={match[1]}
                    PreTag="div"
                  >
                    {String(children).replace(/\n$/, "")}
                  </SyntaxHighlighter>
                );
              }
              return (
                <code className={className} {...props}>
                  {children}
                </code>
              );
            },
          }}
        >
          {lesson.content_markdown}
        </ReactMarkdown>
      </div>

      {/* Key Takeaways */}
      {lesson.key_takeaways && lesson.key_takeaways.length > 0 && (
        <div
          style={{
            marginTop: "2rem",
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            borderRadius: "10px",
            padding: "1.25rem 1.5rem",
          }}
        >
          <h3
            style={{
              margin: "0 0 0.75rem",
              fontSize: "1rem",
              fontWeight: 700,
              color: "var(--text-primary)",
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
              gap: "0.5rem",
            }}
          >
            {lesson.key_takeaways.map((takeaway, i) => (
              <li
                key={i}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "0.5rem",
                  color: "var(--text-secondary)",
                  fontSize: "0.9375rem",
                  lineHeight: 1.6,
                }}
              >
                <span style={{ flexShrink: 0 }}>✅</span>
                <span>{takeaway}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
