"use client";

import { useState } from "react";

interface PromptInputProps {
  onSubmit: (topic: string, difficulty: string) => void;
  isLoading: boolean;
}

const difficulties = ["Beginner", "Intermediate", "Advanced"];

export default function PromptInput({ onSubmit, isLoading }: PromptInputProps) {
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState("Beginner");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = topic.trim();
    if (!trimmed || isLoading) return;
    onSubmit(trimmed, difficulty);
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem",
        background: "var(--bg-primary)",
      }}
    >
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: "2rem" }}>
        <h1
          style={{
            margin: 0,
            fontSize: "2.5rem",
            fontWeight: 800,
            color: "var(--accent)",
            letterSpacing: "-0.5px",
          }}
        >
          ⚡ LearnX 3.0
        </h1>
        <p
          style={{
            margin: "0.75rem 0 0",
            color: "var(--text-secondary)",
            fontSize: "1.05rem",
          }}
        >
          Transform any topic into a structured course in seconds
        </p>
      </div>

      {/* Card */}
      <form
        onSubmit={handleSubmit}
        style={{
          background: "var(--bg-card)",
          border: "1px solid var(--border)",
          borderRadius: "12px",
          padding: "2rem",
          maxWidth: "640px",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          gap: "1.5rem",
        }}
      >
        {/* Topic input */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <label
            htmlFor="topic"
            style={{
              color: "var(--text-secondary)",
              fontSize: "0.875rem",
              fontWeight: 500,
            }}
          >
            What do you want to learn?
          </label>
          <input
            id="topic"
            type="text"
            disabled={isLoading}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Quantum Computing, Python for Beginners, Machine Learning..."
            style={{
              width: "100%",
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
              borderRadius: "8px",
              color: "var(--text-primary)",
              padding: "0.75rem 1rem",
              fontSize: "1rem",
              outline: "none",
              fontFamily: "inherit",
              opacity: isLoading ? 0.5 : 1,
              cursor: isLoading ? "not-allowed" : "text",
              transition: "border-color 0.2s",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "var(--accent)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "var(--border)";
            }}
          />
        </div>

        {/* Difficulty selector */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <span
            style={{
              color: "var(--text-secondary)",
              fontSize: "0.875rem",
              fontWeight: 500,
            }}
          >
            Difficulty Level
          </span>
          <div style={{ display: "flex", gap: "0.75rem" }}>
            {difficulties.map((level) => {
              const isSelected = difficulty === level;
              return (
                <button
                  key={level}
                  type="button"
                  disabled={isLoading}
                  onClick={() => setDifficulty(level)}
                  style={{
                    flex: 1,
                    padding: "0.6rem 0",
                    borderRadius: "8px",
                    border: "1px solid var(--border)",
                    background: isSelected ? "var(--accent)" : "var(--bg-hover)",
                    color: isSelected ? "#fff" : "var(--text-secondary)",
                    fontWeight: isSelected ? 600 : 400,
                    fontSize: "0.9rem",
                    cursor: isLoading ? "not-allowed" : "pointer",
                    opacity: isLoading ? 0.5 : 1,
                    transition: "all 0.18s",
                    fontFamily: "inherit",
                  }}
                >
                  {level}
                </button>
              );
            })}
          </div>
        </div>

        {/* Submit button */}
        <button
          type="submit"
          disabled={isLoading || !topic.trim()}
          style={{
            width: "100%",
            padding: "0.85rem",
            borderRadius: "8px",
            border: "none",
            background: isLoading || !topic.trim() ? "var(--bg-hover)" : "var(--accent)",
            color: isLoading || !topic.trim() ? "var(--text-muted)" : "#fff",
            fontWeight: 600,
            fontSize: "1rem",
            cursor: isLoading || !topic.trim() ? "not-allowed" : "pointer",
            fontFamily: "inherit",
            transition: "background 0.2s",
          }}
          onMouseEnter={(e) => {
            if (!isLoading && topic.trim()) {
              e.currentTarget.style.background = "var(--accent-hover)";
            }
          }}
          onMouseLeave={(e) => {
            if (!isLoading && topic.trim()) {
              e.currentTarget.style.background = "var(--accent)";
            }
          }}
        >
          {isLoading ? "⏳ Generating your course..." : "Generate Course →"}
        </button>

        {/* Loading indicator */}
        {isLoading && (
          <p
            style={{
              margin: 0,
              textAlign: "center",
              color: "var(--text-muted)",
              fontSize: "0.875rem",
              animation: "pulse 2s ease-in-out infinite",
            }}
          >
            <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }`}</style>
            Sourcing content from the web...
          </p>
        )}
      </form>
    </div>
  );
}
