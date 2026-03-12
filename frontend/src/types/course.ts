import { z } from 'zod';

export const DifficultySchema = z.enum(['Beginner', 'Intermediate', 'Advanced']);
export type Difficulty = z.infer<typeof DifficultySchema>;

// ---------------------------------------------------------------------------
// Course Outline — lightweight skeleton returned by /api/generate-outline
// ---------------------------------------------------------------------------

export const OutlineLessonSchema = z.object({
  lesson_id: z.string(),
  lesson_title: z.string(),
  lesson_context: z.string(),
  target_search_queries: z.array(z.string()),
});
export type OutlineLesson = z.infer<typeof OutlineLessonSchema>;

export const OutlineModuleSchema = z.object({
  module_title: z.string(),
  lessons: z.array(OutlineLessonSchema),
});
export type OutlineModule = z.infer<typeof OutlineModuleSchema>;

export const CourseOutlineSchema = z.object({
  course_title: z.string(),
  difficulty_level: DifficultySchema,
  estimated_hours: z.number(),
  modules: z.array(OutlineModuleSchema),
});
export type CourseOutline = z.infer<typeof CourseOutlineSchema>;

// ---------------------------------------------------------------------------
// Lesson Detail — chunked deep-learning payload from /api/generate-lesson
// estimated_time_minutes is calculated server-side from word count
// ---------------------------------------------------------------------------

export const LessonSectionSchema = z.object({
  section_title: z.string(),
  explanation: z.string(),
  code_snippet: z.string().optional().nullable(),
  visual_analogy: z.string().optional().nullable(),
});
export type LessonSection = z.infer<typeof LessonSectionSchema>;

export const ExerciseSchema = z.object({
  question: z.string(),
  options: z.array(z.string()),
  correct_answer: z.string(),
  explanation: z.string(),
});
export type Exercise = z.infer<typeof ExerciseSchema>;

export const LessonSourceSchema = z.object({
  title: z.string(),
  url: z.string().url(),
  snippet: z.string().default(''),
});
export type LessonSource = z.infer<typeof LessonSourceSchema>;

export const LessonDetailSchema = z.object({
  lesson_id: z.string(),
  lesson_title: z.string(),
  estimated_time_minutes: z.number(),
  video_url: z.string().url().optional().nullable(),
  sections: z.array(LessonSectionSchema),
  exercises: z.array(ExerciseSchema),
  key_takeaways: z.array(z.string()),
  sources: z.array(LessonSourceSchema).default([]),
});
export type LessonDetail = z.infer<typeof LessonDetailSchema>;

// ---------------------------------------------------------------------------
// Saved course (from GET /api/courses)
// ---------------------------------------------------------------------------

export const SavedCourseSchema = z.object({
  course_title: z.string(),
  difficulty_level: DifficultySchema,
  estimated_hours: z.number(),
  module_count: z.number(),
  lesson_count: z.number(),
  outline: CourseOutlineSchema,
  saved_at: z.number(),
});
export type SavedCourse = z.infer<typeof SavedCourseSchema>;

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export const OutlineGenerateRequestSchema = z.object({
  topic: z.string().min(1, 'Topic is required'),
  difficulty: DifficultySchema.optional(),
});
export type OutlineGenerateRequest = z.infer<typeof OutlineGenerateRequestSchema>;

export const LessonGenerateRequestSchema = z.object({
  lesson_id: z.string(),
  lesson_title: z.string(),
  lesson_context: z.string(),
  target_search_queries: z.array(z.string()),
  course_title: z.string(),
  difficulty: DifficultySchema.default('Beginner'),
});
export type LessonGenerateRequest = z.infer<typeof LessonGenerateRequestSchema>;
