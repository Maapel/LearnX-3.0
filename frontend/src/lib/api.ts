import { Course, CourseGenerateRequest } from '@/types/course';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function generateCourse(request: CourseGenerateRequest): Promise<Course> {
  const response = await fetch(`${API_URL}/api/generate-course`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
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
