"use client";

import { useState } from "react";
import PromptInput from "@/components/PromptInput";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import CourseViewer from "@/components/CourseViewer";
import { Course } from "@/types/course";
import { generateCourse } from "@/lib/api";

type AppState = "input" | "loading" | "course" | "error";

export default function Home() {
  const [state, setState] = useState<AppState>("input");
  const [course, setCourse] = useState<Course | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate(topic: string, difficulty: string) {
    setState("loading");
    setError(null);
    try {
      const result = await generateCourse({
        topic,
        difficulty: difficulty as Course["difficulty_level"],
      });
      setCourse(result);
      setState("course");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Course generation failed. Please try again.");
      setState("error");
    }
  }

  function handleReset() {
    setCourse(null);
    setError(null);
    setState("input");
  }

  if (state === "loading") return <LoadingSkeleton />;
  if (state === "course" && course) return <CourseViewer course={course} onReset={handleReset} />;

  return (
    <div>
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
  );
}
