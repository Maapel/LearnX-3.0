from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.course import router as course_router

app = FastAPI(
    title="LearnX 3.0 API",
    description="AI-powered rapid learning platform backend",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(course_router)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
