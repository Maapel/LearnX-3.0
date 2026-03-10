"use client";

import { useState, useEffect } from "react";
import { Course, ContentType } from "@/types/course";

interface CourseSidebarProps {
  course: Course;
  activeModuleIndex: number;
  activeLessonIndex: number;
  onSelectLesson: (moduleIdx: number, lessonIdx: number) => void;
}

function contentTypeIcon(type: ContentType): string {
  if (type === "video") return "▶";
  if (type === "article") return "📄";
  return "💡";
}

function difficultyColor(level: string): string {
  if (level === "Beginner") return "#22c55e";
  if (level === "Intermediate") return "#f59e0b";
  return "#ef4444";
}

export default function CourseSidebar({
  course,
  activeModuleIndex,
  activeLessonIndex,
  onSelectLesson,
}: CourseSidebarProps) {
  const [expandedModules, setExpandedModules] = useState<boolean[]>(() =>
    course.modules.map(() => true)
  );

  // Track visited lessons as "moduleIdx-lessonIdx" strings
  const [visitedLessons, setVisitedLessons] = useState<Set<string>>(
    () => new Set([`${activeModuleIndex}-${activeLessonIndex}`])
  );

  useEffect(() => {
    setVisitedLessons((prev) => {
      const next = new Set(prev);
      next.add(`${activeModuleIndex}-${activeLessonIndex}`);
      return next;
    });
  }, [activeModuleIndex, activeLessonIndex]);

  // Compute total lessons and visited count for progress bar
  const totalLessons = course.modules.reduce(
    (sum, mod) => sum + mod.lessons.length,
    0
  );
  const visitedCount = visitedLessons.size;
  const progressPct = totalLessons > 0 ? (visitedCount / totalLessons) * 100 : 0;

  function toggleModule(idx: number) {
    setExpandedModules((prev) => {
      const next = [...prev];
      next[idx] = !next[idx];
      return next;
    });
  }

  return (
    <div
      style={{
        width: "260px",
        flexShrink: 0,
        height: "100%",
        overflowY: "auto",
        background: "var(--bg-secondary)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Course info header */}
      <div
        style={{
          padding: "1.25rem 1rem 1rem",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <p
          title={course.course_title}
          style={{
            margin: "0 0 0.5rem",
            fontWeight: 700,
            fontSize: "0.875rem",
            color: "var(--text-primary)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {course.course_title}
        </p>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
          <span
            style={{
              fontSize: "0.7rem",
              fontWeight: 600,
              padding: "0.15em 0.55em",
              borderRadius: "999px",
              background: "var(--bg-hover)",
              color: difficultyColor(course.difficulty_level),
              border: `1px solid ${difficultyColor(course.difficulty_level)}44`,
            }}
          >
            {course.difficulty_level}
          </span>
          <span
            style={{
              fontSize: "0.75rem",
              color: "var(--text-muted)",
            }}
          >
            ⏱ {course.estimated_hours}h
          </span>
        </div>
      </div>

      {/* Module / lesson list */}
      <div style={{ flex: 1, overflowY: "auto", padding: "0.5rem 0" }}>
        {course.modules.map((mod, modIdx) => {
          const isExpanded = expandedModules[modIdx];
          return (
            <div key={modIdx}>
              {/* Module header */}
              <button
                onClick={() => toggleModule(modIdx)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  width: "100%",
                  padding: "0.6rem 1rem",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  textAlign: "left",
                  color: "var(--text-primary)",
                  fontFamily: "inherit",
                  gap: "0.5rem",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "var(--bg-hover)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "none";
                }}
              >
                <span
                  style={{
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    color: "var(--text-secondary)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    flex: 1,
                  }}
                >
                  {modIdx + 1}. {mod.module_title}
                </span>
                <span
                  style={{
                    fontSize: "0.65rem",
                    color: "var(--text-muted)",
                    flexShrink: 0,
                    transition: "transform 0.2s",
                    transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
                  }}
                >
                  ▶
                </span>
              </button>

              {/* Lessons */}
              {isExpanded && (
                <div>
                  {mod.lessons.map((lesson, lesIdx) => {
                    const isActive =
                      modIdx === activeModuleIndex && lesIdx === activeLessonIndex;
                    const key = `${modIdx}-${lesIdx}`;
                    const isVisited = visitedLessons.has(key) && !isActive;

                    return (
                      <button
                        key={lesIdx}
                        onClick={() => onSelectLesson(modIdx, lesIdx)}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "0.5rem",
                          width: "100%",
                          padding: "0.5rem 1rem 0.5rem 1.75rem",
                          background: isActive
                            ? "var(--accent)"
                            : "none",
                          border: "none",
                          cursor: "pointer",
                          textAlign: "left",
                          color: isActive ? "#fff" : "var(--text-secondary)",
                          fontFamily: "inherit",
                          transition: "background 0.15s",
                        }}
                        onMouseEnter={(e) => {
                          if (!isActive)
                            e.currentTarget.style.background = "var(--bg-hover)";
                        }}
                        onMouseLeave={(e) => {
                          if (!isActive)
                            e.currentTarget.style.background = "none";
                        }}
                      >
                        <span style={{ fontSize: "0.75rem", flexShrink: 0 }}>
                          {contentTypeIcon(lesson.content_type)}
                        </span>
                        <span
                          style={{
                            fontSize: "0.8rem",
                            lineHeight: 1.4,
                            flex: 1,
                            overflow: "hidden",
                            display: "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: "vertical",
                          }}
                        >
                          {lesson.lesson_title}
                        </span>
                        {isVisited && (
                          <span
                            style={{
                              fontSize: "0.7rem",
                              color: isActive ? "#fff" : "#22c55e",
                              flexShrink: 0,
                            }}
                          >
                            ✓
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div
        style={{
          padding: "0.875rem 1rem",
          borderTop: "1px solid var(--border)",
          background: "var(--bg-secondary)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "0.4rem",
          }}
        >
          <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
            Progress
          </span>
          <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
            {visitedCount}/{totalLessons}
          </span>
        </div>
        <div
          style={{
            height: "4px",
            background: "var(--bg-hover)",
            borderRadius: "999px",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              height: "100%",
              width: `${progressPct}%`,
              background: "var(--accent)",
              borderRadius: "999px",
              transition: "width 0.4s ease",
            }}
          />
        </div>
      </div>
    </div>
  );
}
