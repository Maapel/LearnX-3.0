# LearnX 3.0 — Progress Tracker

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

## Phase 3: The AI Brain ⏳ PENDING
- [ ] `backend/services/llm_router.py` — Groq: user prompt → search queries
- [ ] `backend/services/synthesizer.py` — Gemini: scraped content → Course JSON
- [ ] `backend/routers/course.py` — POST `/api/generate-course` endpoint

---

## Phase 4: The Frontend UI ⏳ PENDING
- [ ] Dark-mode Tailwind layout
- [ ] `PromptInput` component
- [ ] `CourseViewer` with sidebar + markdown renderer + YouTube iframes
- [ ] Connect to backend API with loading skeletons

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
