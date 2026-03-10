import { z } from 'zod';

export const ContentTypeSchema = z.enum(['video', 'article', 'concept_breakdown']);
export type ContentType = z.infer<typeof ContentTypeSchema>;

export const DifficultySchema = z.enum(['Beginner', 'Intermediate', 'Advanced']);
export type Difficulty = z.infer<typeof DifficultySchema>;

export const LessonSchema = z.object({
  lesson_title: z.string(),
  content_type: ContentTypeSchema,
  source_url: z.string().url().optional().nullable(),
  content_markdown: z.string(),
  key_takeaways: z.array(z.string()),
});
export type Lesson = z.infer<typeof LessonSchema>;

export const ModuleSchema = z.object({
  module_title: z.string(),
  module_description: z.string(),
  lessons: z.array(LessonSchema),
});
export type Module = z.infer<typeof ModuleSchema>;

export const CourseSchema = z.object({
  course_title: z.string(),
  difficulty_level: DifficultySchema,
  estimated_hours: z.number(),
  modules: z.array(ModuleSchema),
});
export type Course = z.infer<typeof CourseSchema>;

export const CourseGenerateRequestSchema = z.object({
  topic: z.string().min(1, 'Topic is required'),
  difficulty: DifficultySchema.optional(),
});
export type CourseGenerateRequest = z.infer<typeof CourseGenerateRequestSchema>;
