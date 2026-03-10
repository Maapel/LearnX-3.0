"use client";

import { useState } from "react";
import { Course } from "@/types/course";
import CourseSidebar from "./CourseSidebar";
import LessonContent from "./LessonContent";

interface CourseViewerProps {
  course: Course;
  onReset: () => void;
}

export default function CourseViewer({ course, onReset }: CourseViewerProps) {
  const [activeModuleIndex, setActiveModuleIndex] = useState(0);
  const [activeLessonIndex, setActiveLessonIndex] = useState(0);

  const activeLesson =
    course.modules[activeModuleIndex]?.lessons[activeLessonIndex];

  // Compute flat list of (moduleIdx, lessonIdx) for prev/next navigation
  const flatLessons: { moduleIdx: number; lessonIdx: number }[] = [];
  for (let m = 0; m < course.modules.length; m++) {
    for (let l = 0; l < course.modules[m].lessons.length; l++) {
      flatLessons.push({ moduleIdx: m, lessonIdx: l });
    }
  }

  const currentFlatIndex = flatLessons.findIndex(
    (fl) =>
      fl.moduleIdx === activeModuleIndex && fl.lessonIdx === activeLessonIndex
  );
  const isFirst = currentFlatIndex <= 0;
  const isLast = currentFlatIndex >= flatLessons.length - 1;

  function goToPrev() {
    if (isFirst) return;
    const prev = flatLessons[currentFlatIndex - 1];
    setActiveModuleIndex(prev.moduleIdx);
    setActiveLessonIndex(prev.lessonIdx);
  }

  function goToNext() {
    if (isLast) return;
    const next = flatLessons[currentFlatIndex + 1];
    setActiveModuleIndex(next.moduleIdx);
    setActiveLessonIndex(next.lessonIdx);
  }

  function handleSelectLesson(moduleIdx: number, lessonIdx: number) {
    setActiveModuleIndex(moduleIdx);
    setActiveLessonIndex(lessonIdx);
  }

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
      {/* Sticky top navbar */}
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
        {/* Left: brand */}
        <span
          style={{
            fontWeight: 800,
            fontSize: "1rem",
            color: "var(--accent)",
            whiteSpace: "nowrap",
          }}
        >
          ⚡ LearnX 3.0
        </span>

        {/* Center: course title */}
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
          {course.course_title}
        </span>

        {/* Right: new course button */}
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

      {/* Body: sidebar + main content */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Sidebar */}
        <CourseSidebar
          course={course}
          activeModuleIndex={activeModuleIndex}
          activeLessonIndex={activeLessonIndex}
          onSelectLesson={handleSelectLesson}
        />

        {/* Main content area */}
        <main
          style={{
            flex: 1,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {activeLesson ? (
            <>
              <div style={{ flex: 1 }}>
                <LessonContent lesson={activeLesson} />
              </div>

              {/* Navigation buttons */}
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
                  onClick={goToPrev}
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
                    transition: "all 0.15s",
                  }}
                  onMouseEnter={(e) => {
                    if (!isFirst) {
                      e.currentTarget.style.background = "var(--bg-hover)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isFirst) {
                      e.currentTarget.style.background = "var(--bg-card)";
                    }
                  }}
                >
                  ← Previous Lesson
                </button>

                <button
                  onClick={goToNext}
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
                    transition: "all 0.15s",
                  }}
                  onMouseEnter={(e) => {
                    if (!isLast) {
                      e.currentTarget.style.background = "var(--accent-hover)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isLast) {
                      e.currentTarget.style.background = "var(--accent)";
                    }
                  }}
                >
                  Next Lesson →
                </button>
              </div>
            </>
          ) : (
            <div
              style={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--text-muted)",
                fontSize: "1rem",
              }}
            >
              Select a lesson to begin
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
