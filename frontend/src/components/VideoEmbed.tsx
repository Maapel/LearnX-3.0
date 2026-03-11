"use client";

interface VideoEmbedProps {
  url: string;
  title?: string;
}

function getYouTubeId(url: string): string | null {
  try {
    const parsed = new URL(url);
    if (parsed.hostname === "youtu.be") {
      return parsed.pathname.slice(1).split("?")[0] || null;
    }
    if (parsed.hostname.includes("youtube.com")) {
      return parsed.searchParams.get("v");
    }
  } catch {
    // invalid URL
  }
  return null;
}

export default function VideoEmbed({ url, title = "Lesson Video" }: VideoEmbedProps) {
  const videoId = getYouTubeId(url);

  if (!videoId) return null;

  return (
    <div
      style={{
        borderRadius: "12px",
        overflow: "hidden",
        border: "1px solid var(--border)",
        marginBottom: "1.75rem",
        background: "#000",
        boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
      }}
    >
      <div style={{ position: "relative", paddingBottom: "56.25%", height: 0 }}>
        <iframe
          src={`https://www.youtube.com/embed/${videoId}?rel=0&modestbranding=1`}
          title={title}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            border: "none",
          }}
        />
      </div>
    </div>
  );
}
