"use client";

import { useEffect, useState } from "react";

const steps = [
  "🔍 Searching the web...",
  "📄 Scraping articles...",
  "🤖 Synthesizing with AI...",
];

export default function LoadingSkeleton() {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setStepIndex((prev) => (prev + 1) % steps.length);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        background: "var(--bg-primary)",
        color: "var(--text-primary)",
        overflow: "hidden",
      }}
    >
      {/* Main layout: sidebar + content */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Sidebar skeleton */}
        <div
          style={{
            width: "240px",
            flexShrink: 0,
            borderRight: "1px solid var(--border)",
            background: "var(--bg-secondary)",
            padding: "1.5rem 1rem",
            display: "flex",
            flexDirection: "column",
            gap: "1rem",
          }}
        >
          <div className="skeleton" style={{ height: "18px", width: "70%" }} />
          <div className="skeleton" style={{ height: "18px", width: "90%" }} />
          <div className="skeleton" style={{ height: "18px", width: "55%" }} />
          <div className="skeleton" style={{ height: "18px", width: "80%" }} />
        </div>

        {/* Main content skeleton */}
        <div
          style={{
            flex: 1,
            padding: "2rem",
            display: "flex",
            flexDirection: "column",
            gap: "1rem",
            overflowY: "auto",
          }}
        >
          {/* Title block */}
          <div className="skeleton" style={{ height: "36px", width: "55%", marginBottom: "0.5rem" }} />

          {/* Paragraph lines */}
          <div className="skeleton" style={{ height: "16px", width: "100%" }} />
          <div className="skeleton" style={{ height: "16px", width: "95%" }} />
          <div className="skeleton" style={{ height: "16px", width: "88%" }} />

          {/* Code block */}
          <div
            className="skeleton"
            style={{ height: "140px", width: "100%", marginTop: "0.5rem", marginBottom: "0.5rem", borderRadius: "8px" }}
          />

          {/* More paragraph lines */}
          <div className="skeleton" style={{ height: "16px", width: "100%" }} />
          <div className="skeleton" style={{ height: "16px", width: "92%" }} />
          <div className="skeleton" style={{ height: "16px", width: "80%" }} />
        </div>
      </div>

      {/* Status bar */}
      <div
        style={{
          borderTop: "1px solid var(--border)",
          padding: "1rem 2rem",
          background: "var(--bg-secondary)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "0.5rem",
        }}
      >
        <span
          style={{
            color: "var(--accent-light)",
            fontSize: "0.95rem",
            fontWeight: 500,
            transition: "opacity 0.5s",
          }}
        >
          {steps[stepIndex]}
        </span>
      </div>
    </div>
  );
}
