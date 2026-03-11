"use client";

import { useState, useCallback } from "react";
import { CourseOutline, LessonDetail } from "@/types/course";
import CourseSidebar from "./CourseSidebar";
import LessonContent from "./LessonContent";
import LoadingSkeleton from "./LoadingSkeleton";
import { generateLesson } from "@/lib/api";

interface CourseViewerProps {
  outline: CourseOutline;
  onReset: () => void;
}

export default function CourseViewer({ outline, onReset }: CourseViewerProps) {
  const [activeLesson, setActiveLesson] = useState<{ moduleIdx: number; lessonIdx: number } | null>(null);
  const [lessonCache, setLessonCache] = useState<Record<string, LessonDetail>>({});
  const [loadingLessonId, setLoadingLessonId] = useState<string | null>(null);
  const [lessonError, setLessonError] = useState<string | null>(null);
  const [visitedLessonIds, setVisitedLessonIds] = useState<Set<string>>(new Set());

  const activeLessonData = activeLesson
    ? outline.modules[activeLesson.moduleIdx]?.lessons[activeLesson.lessonIdx]
    : null;
  const activeDetail = activeLessonData ? lessonCache[activeLessonData.lesson_id] : null;
  const isLoadingLesson = loadingLessonId !== null;

  const fetchLesson = useCallback(
    async (moduleIdx: number, lessonIdx: number) => {
      const lesson = outline.modules[moduleIdx]?.lessons[lessonIdx];
      if (!lesson) return;

      setActiveLesson({ moduleIdx, lessonIdx });
      setLessonError(null);

      // Already cached — show instantly
      if (lessonCache[lesson.lesson_id]) {
        setVisitedLessonIds((prev) => new Set(prev).add(lesson.lesson_id));
        return;
      }

      setLoadingLessonId(lesson.lesson_id);
      try {
        const detail = await generateLesson({
          lesson_id: lesson.lesson_id,
          lesson_title: lesson.lesson_title,
          lesson_context: lesson.lesson_context,
          target_search_queries: lesson.target_search_queries,
          course_title: outline.course_title,
          difficulty: outline.difficulty_level,
        });
        setLessonCache((prev) => ({ ...prev, [lesson.lesson_id]: detail }));
        setVisitedLessonIds((prev) => new Set(prev).add(lesson.lesson_id));
      } catch (err) {
        setLessonError(err instanceof Error ? err.message : "Lesson generation failed.");
      } finally {
        setLoadingLessonId(null);
      }
    },
    [outline, lessonCache]
  );

  // Flat lesson list for prev/next
  const flatLessons = outline.modules.flatMap((mod, mIdx) =>
    mod.lessons.map((_, lIdx) => ({ moduleIdx: mIdx, lessonIdx: lIdx }))
  );
  const currentFlatIdx = activeLesson
    ? flatLessons.findIndex(
        (fl) => fl.moduleIdx === activeLesson.moduleIdx && fl.lessonIdx === activeLesson.lessonIdx
      )
    : -1;
  const isFirst = currentFlatIdx <= 0;
  const isLast = currentFlatIdx >= flatLessons.length - 1;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        overflow: "hidden",
        background: "var(--bg-primary)",
      }}
    >
      {/* Navbar */}
      <header
        style={{
          position: "sticky",
          top: 0,
          zIndex: 100,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 1.25rem",
          height: "52px",
          background: "var(--bg-secondary)",
          borderBottom: "1px solid var(--border)",
          flexShrink: 0,
        }}
      >
        <span style={{ fontWeight: 800, fontSize: "1rem", color: "var(--accent)", whiteSpace: "nowrap" }}>
          ⚡ LearnX 3.0
        </span>
        <span
          style={{
            flex: 1,
            textAlign: "center",
            fontSize: "0.875rem",
            fontWeight: 600,
            color: "var(--text-secondary)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            padding: "0 1rem",
          }}
        >
          {outline.course_title}
        </span>
        <button
          onClick={onReset}
          style={{
            background: "var(--bg-hover)",
            border: "1px solid var(--border)",
            borderRadius: "8px",
            color: "var(--text-secondary)",
            padding: "0.4rem 0.85rem",
            fontSize: "0.8rem",
            fontWeight: 500,
            cursor: "pointer",
            fontFamily: "inherit",
            whiteSpace: "nowrap",
            transition: "all 0.15s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--accent)";
            e.currentTarget.style.color = "#fff";
            e.currentTarget.style.borderColor = "var(--accent)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "var(--bg-hover)";
            e.currentTarget.style.color = "var(--text-secondary)";
            e.currentTarget.style.borderColor = "var(--border)";
          }}
        >
          ← New Course
        </button>
      </header>

      {/* Body */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <CourseSidebar
          outline={outline}
          activeLesson={activeLesson}
          loadingLessonId={loadingLessonId}
          visitedLessonIds={visitedLessonIds}
          onSelectLesson={fetchLesson}
        />

        <main style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column" }}>
          {/* Welcome state */}
          {!activeLesson && !isLoadingLesson && (
            <div
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: "1rem",
                color: "var(--text-muted)",
                padding: "2rem",
                textAlign: "center",
              }}
            >
              <span style={{ fontSize: "2.5rem" }}>👈</span>
              <p style={{ margin: 0, fontSize: "1rem", fontWeight: 500 }}>
                Select a lesson from the sidebar to begin
              </p>
              <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)" }}>
                Each lesson is generated on demand — your first click may take 15–30 seconds
              </p>
            </div>
          )}

          {/* Loading skeleton */}
          {isLoadingLesson && (
            <div style={{ flex: 1 }}>
              <LoadingSkeleton />
            </div>
          )}

          {/* Error */}
          {lessonError && !isLoadingLesson && (
            <div
              style={{
                margin: "2rem auto",
                maxWidth: "480px",
                background: "#7f1d1d",
                border: "1px solid #ef4444",
                color: "#fca5a5",
                padding: "1rem 1.5rem",
                borderRadius: "10px",
                fontSize: "0.9rem",
              }}
            >
              ⚠️ {lessonError}
            </div>
          )}

          {/* Lesson content */}
          {activeDetail && !isLoadingLesson && (
            <>
              <div style={{ flex: 1 }}>
                <LessonContent lesson={activeDetail} />
              </div>

              {/* Prev/Next nav */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "1rem 2rem 1.5rem",
                  borderTop: "1px solid var(--border)",
                  background: "var(--bg-primary)",
                  gap: "1rem",
                }}
              >
                <button
                  onClick={() => {
                    if (!isFirst) {
                      const prev = flatLessons[currentFlatIdx - 1];
                      fetchLesson(prev.moduleIdx, prev.lessonIdx);
                    }
                  }}
                  disabled={isFirst}
                  style={{
                    padding: "0.6rem 1.25rem",
                    borderRadius: "8px",
                    border: "1px solid var(--border)",
                    background: isFirst ? "var(--bg-hover)" : "var(--bg-card)",
                    color: isFirst ? "var(--text-muted)" : "var(--text-primary)",
                    fontWeight: 500,
                    fontSize: "0.875rem",
                    cursor: isFirst ? "not-allowed" : "pointer",
                    fontFamily: "inherit",
                    opacity: isFirst ? 0.5 : 1,
                  }}
                >
                  ← Previous
                </button>
                <button
                  onClick={() => {
                    if (!isLast) {
                      const next = flatLessons[currentFlatIdx + 1];
                      fetchLesson(next.moduleIdx, next.lessonIdx);
                    }
                  }}
                  disabled={isLast}
                  style={{
                    padding: "0.6rem 1.25rem",
                    borderRadius: "8px",
                    border: "none",
                    background: isLast ? "var(--bg-hover)" : "var(--accent)",
                    color: isLast ? "var(--text-muted)" : "#fff",
                    fontWeight: 600,
                    fontSize: "0.875rem",
                    cursor: isLast ? "not-allowed" : "pointer",
                    fontFamily: "inherit",
                    opacity: isLast ? 0.5 : 1,
                  }}
                >
                  Next →
                </button>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
