import { CourseOutline, LessonDetail, OutlineGenerateRequest, LessonGenerateRequest, SavedCourse } from '@/types/course';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function generateOutline(request: OutlineGenerateRequest): Promise<CourseOutline> {
  const response = await fetch(`${API_URL}/api/generate-outline`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(`Outline generation failed: ${response.status} — ${detail}`);
  }
  return response.json();
}

export async function generateLesson(request: LessonGenerateRequest): Promise<LessonDetail> {
  const response = await fetch(`${API_URL}/api/generate-lesson`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(`Lesson generation failed: ${response.status} — ${detail}`);
  }
  return response.json();
}

export async function listCourses(): Promise<SavedCourse[]> {
  const response = await fetch(`${API_URL}/api/courses`);
  if (!response.ok) return [];
  return response.json();
}

export async function healthCheck(): Promise<boolean> {
  try {
    const response = await fetch(`${API_URL}/health`);
    return response.ok;
  } catch {
    return false;
  }
}
