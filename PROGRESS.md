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
