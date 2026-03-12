"use client";

import { useState, useEffect } from "react";
import PromptInput from "@/components/PromptInput";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import CourseViewer from "@/components/CourseViewer";
import { CourseOutline, SavedCourse } from "@/types/course";
import { generateOutline, listCourses } from "@/lib/api";

type AppState = "input" | "loading" | "course" | "error";

export default function Home() {
  const [state, setState] = useState<AppState>("input");
  const [outline, setOutline] = useState<CourseOutline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedCourses, setSavedCourses] = useState<SavedCourse[]>([]);

  useEffect(() => {
    listCourses().then(setSavedCourses).catch(() => {});
  }, []);

  async function handleGenerate(topic: string, difficulty: string) {
    setState("loading");
    setError(null);
    try {
      const result = await generateOutline({
        topic,
        difficulty: difficulty as CourseOutline["difficulty_level"],
      });
      setOutline(result);
      setState("course");
      listCourses().then(setSavedCourses).catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Course generation failed. Please try again.");
      setState("error");
    }
  }

  function handleLoadSaved(course: SavedCourse) {
    setOutline(course.outline);
    setState("course");
  }

  function handleReset() {
    setOutline(null);
    setError(null);
    setState("input");
  }

  if (state === "loading") return <LoadingSkeleton />;
  if (state === "course" && outline) return <CourseViewer outline={outline} onReset={handleReset} />;

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "2rem",
          minHeight: savedCourses.length > 0 ? "auto" : "100vh",
          paddingTop: savedCourses.length > 0 ? "4rem" : "0",
        }}
      >
        <PromptInput onSubmit={handleGenerate} isLoading={false} />

        {state === "error" && error && (
          <div
            style={{
              position: "fixed",
              bottom: "2rem",
              left: "50%",
              transform: "translateX(-50%)",
              background: "#7f1d1d",
              border: "1px solid #ef4444",
              color: "#fca5a5",
              padding: "1rem 1.5rem",
              borderRadius: "0.75rem",
              maxWidth: "480px",
              width: "90%",
              textAlign: "center",
              fontSize: "0.9rem",
              zIndex: 1000,
            }}
          >
            ⚠️ {error}
          </div>
        )}
      </div>

      {savedCourses.length > 0 && (
        <div
          style={{
            maxWidth: "860px",
            margin: "0 auto",
            padding: "0 2rem 4rem",
          }}
        >
          <h2
            style={{
              color: "var(--text-secondary)",
              fontSize: "0.8rem",
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              marginBottom: "1rem",
            }}
          >
            Previously Generated
          </h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
              gap: "0.75rem",
            }}
          >
            {savedCourses.map((course) => (
              <SavedCourseCard
                key={course.course_title + course.difficulty_level}
                course={course}
                onClick={() => handleLoadSaved(course)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function SavedCourseCard({ course, onClick }: { course: SavedCourse; onClick: () => void }) {
  const [hovered, setHovered] = useState(false);
  const date = new Date(course.saved_at * 1000).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
  const difficultyColor: Record<string, string> = {
    Beginner: "#22c55e",
    Intermediate: "#f59e0b",
    Advanced: "#ef4444",
  };

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: hovered ? "var(--bg-hover)" : "var(--bg-card)",
        border: `1px solid ${hovered ? "var(--accent)" : "var(--border)"}`,
        borderRadius: "10px",
        padding: "1rem 1.1rem",
        cursor: "pointer",
        textAlign: "left",
        fontFamily: "inherit",
        transition: "all 0.15s",
        display: "flex",
        flexDirection: "column",
        gap: "0.5rem",
      }}
    >
      <div
        style={{
          color: "var(--text-primary)",
          fontSize: "0.95rem",
          fontWeight: 600,
          lineHeight: 1.3,
        }}
      >
        {course.course_title}
      </div>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <span
          style={{
            fontSize: "0.72rem",
            fontWeight: 600,
            color: difficultyColor[course.difficulty_level] ?? "var(--text-muted)",
            background: `${difficultyColor[course.difficulty_level] ?? "#888"}22`,
            padding: "0.15rem 0.5rem",
            borderRadius: "99px",
          }}
        >
          {course.difficulty_level}
        </span>
        <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
          {course.module_count} modules · {course.lesson_count} lessons
        </span>
        <span style={{ color: "var(--text-muted)", fontSize: "0.75rem", marginLeft: "auto" }}>
          {date}
        </span>
      </div>
    </button>
  );
}
