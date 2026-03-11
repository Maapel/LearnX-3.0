import { z } from 'zod';

export const DifficultySchema = z.enum(['Beginner', 'Intermediate', 'Advanced']);
export type Difficulty = z.infer<typeof DifficultySchema>;

// ---------------------------------------------------------------------------
// Course Outline — lightweight skeleton returned by /api/generate-outline
// ---------------------------------------------------------------------------

export const OutlineLessonSchema = z.object({
  lesson_id: z.string(),
  lesson_title: z.string(),
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
// Lesson Detail — rich interactive payload returned by /api/generate-lesson
// ---------------------------------------------------------------------------

export const ExerciseSchema = z.object({
  question: z.string(),
  options: z.array(z.string()),
  correct_answer: z.string(),
  explanation: z.string(),
});
export type Exercise = z.infer<typeof ExerciseSchema>;

export const LessonDetailSchema = z.object({
  lesson_id: z.string(),
  lesson_title: z.string(),
  estimated_time_minutes: z.number(),
  video_url: z.string().url().optional().nullable(),
  concept_summary: z.string(),
  practical_example: z.string().optional().nullable(),
  exercises: z.array(ExerciseSchema),
  key_takeaways: z.array(z.string()),
});
export type LessonDetail = z.infer<typeof LessonDetailSchema>;

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
  course_title: z.string(),
  difficulty: DifficultySchema.default('Beginner'),
});
export type LessonGenerateRequest = z.infer<typeof LessonGenerateRequestSchema>;
