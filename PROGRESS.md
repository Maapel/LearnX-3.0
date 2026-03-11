# LearnX 3.0 — Progress Tracker

---

## Phase 5: UI Templatization & Rolling (JIT) Generation ✅ COMPLETE

### Schema Split (backend/models.py + frontend/src/types/course.ts)
- [x] `CourseOutline` — lightweight skeleton: title, difficulty, modules → lessons (lesson_id UUID + title only)
- [x] `LessonDetail` — interactive payload: concept_summary (3-4 sentences), practical_example, exercises (MCQ), key_takeaways, video_url, estimated_time_minutes
- [x] `Exercise` — question, options[], correct_answer (must match option exactly), explanation
- [x] Rich `Field(description=...)` annotations on every field to guide Gemini structured output
- [x] Removed `content_markdown`, `content_type`, `module_description` from outline

### Rolling Generation Endpoints (backend/routers/course.py + services/synthesizer.py)
- [x] `POST /api/generate-outline` — fast (<5s) skeleton generation, disk-cached by topic+difficulty
- [x] `POST /api/generate-lesson` — JIT per-lesson content, sources content scoped to lesson title, disk-cached by lesson_id
- [x] Cascade: Gemini (structured output) → Groq → Ollama → static fallback (both endpoints)
- [x] Correct_answer validation: ensures value exactly matches one of the options strings

### Interactive UI Components (frontend/src/components/)
- [x] `QuizWidget.tsx` — MCQ quiz: click to reveal, green/red correct/incorrect, score tracker
- [x] `VideoEmbed.tsx` — responsive 16:9 YouTube iframe, handles youtu.be + youtube.com URLs

### Just-In-Time Frontend (CourseViewer, CourseSidebar, LessonContent, page.tsx)
- [x] `page.tsx` — calls `/api/generate-outline` (fast), shows skeleton to user immediately
- [x] `CourseViewer.tsx` — renders sidebar from outline instantly; fetches lesson on click with in-memory cache
- [x] `CourseSidebar.tsx` — ⏳ spinner on loading lesson, ✓ checkmark on visited, progress bar
- [x] `LessonContent.tsx` — concept card (indigo gradient), code block, QuizWidget, takeaways checklist

### UX Flow
1. User types topic → outline returns in ~3-5s → sidebar rendered
2. User clicks lesson → loading skeleton shows → lesson fetches in background (~15-30s first time)
3. Subsequent clicks on same lesson: instant (cached in memory + disk)

---

## Phase 1: Environment & Schema Initialization ✅ COMPLETE
- [x] Monorepo structure: `/backend` + `/frontend`
- [x] `.env.example` with Groq, Gemini, Tavily, SerpAPI, Ollama keys
- [x] `backend/models.py` — Pydantic v2: `Lesson`, `Module`, `Course`, `CourseGenerateRequest`
- [x] `backend/main.py` — FastAPI app with CORS + `/health` endpoint
- [x] `backend/requirements.txt` — all deps (Python 3.13 compatible)
- [x] `frontend/src/types/course.ts` — Zod schemas mirroring Pydantic models
- [x] `frontend/src/lib/api.ts` — `generateCourse()` + `healthCheck()` API client
- [x] Both backend (port 8000) and frontend (port 3000) tested and verified ✅

**Notes:** System runs Python 3.14; used `uv` to provision Python 3.13 for compatibility. `venv` lives at `backend/venv/`.

---

## Phase 2: The Sourcing Engine ✅ COMPLETE
- [x] `backend/services/search_service.py` — Tavily API: topic → top 5 URLs
- [x] `backend/services/youtube_service.py` — YouTube URL → full transcript
- [x] `backend/services/scraper_service.py` — Article URL → clean body text
- [x] `backend/test_sourcing.py` — CLI HITL test script

**HITL Status:** Awaiting human verification via `python test_sourcing.py`

---

## Expert Re-Evaluation V2 ✅ COMPLETE (see EXPERT_EVALUATION_REPORT_V2.md)
- Fixes validated: ML 3→6 (+3), Python 4→5 (+1) on successful runs
- Root cause of remaining FAILs: Groq concurrent quota exhaustion (not fix quality)
- Applied: asyncio.Semaphore(1) — serializes LLM calls, prevents concurrent quota burn

## Expert Evaluation ✅ COMPLETE (see EXPERT_EVALUATION_REPORT.md)
- 5 topics tested: Quantum Computing, Python, Machine Learning, React Web Dev, Blockchain
- Average score: 3.4/10 | 0 PASS, 2 PARTIAL, 3 FAIL
- Top issues: shallow content (~130 words/lesson), no code blocks, rate limit fragility
- P0 fixes needed before Phase 4: word count enforcement, code block requirement, Groq retry

## Phase 3: The AI Brain ✅ COMPLETE
- [x] `backend/services/llm_router.py` — Groq (llama-3.3-70b): user prompt → search queries + intent parsing
- [x] `backend/services/synthesizer.py` — Gemini 2.0 Flash (google-genai SDK): scraped content → Course JSON
- [x] `backend/routers/course.py` — POST `/api/generate-course` full pipeline endpoint
- [x] `backend/main.py` — router wired in
- [x] Migrated from deprecated `google-generativeai` → `google-genai` v1.66.0

**HITL Status:** Awaiting cURL test of `/api/generate-course`

---

## Phase 4: The Frontend UI 🚧 IN PROGRESS
- [ ] Dark-mode Tailwind layout (globals.css + layout.tsx)
- [ ] `PromptInput` component — topic input + difficulty selector + submit
- [ ] `CourseViewer` with sidebar (module/lesson nav) + markdown renderer + YouTube iframes
- [ ] Loading skeletons during 30–60s generation
- [ ] Connect to backend `POST /api/generate-course`

## Ollama Local Fallback ✅ COMPLETE
- [x] `synthesizer.py` — cascade extended: Gemini → Groq → **Ollama** → static fallback
- [x] `llm_router.py` — both `generate_search_queries` and `parse_learning_intent` cascade: Groq → **Ollama** → basic fallback
- [x] `.env.example` — added `OLLAMA_MODEL=llama3.2` (configurable)
- Ollama is called via httpx POST to `/api/chat` (no API key, no rate limits)
- Timeout: 300s for synthesis, 120s for query gen (local models can be slow)

**To use Ollama locally:**
```bash
ollama serve          # start the daemon
ollama pull llama3.2  # or: ollama pull mistral
```
Set `OLLAMA_BASE_URL=http://localhost:11434` and `OLLAMA_MODEL=llama3.2` in `.env`.

---

## How to Run
```bash
# Backend
cd backend && source venv/bin/activate
uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Phase 2 test
cd backend && source venv/bin/activate
python test_sourcing.py
```
