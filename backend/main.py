"""서울 대기질 AI 비서 — FastAPI 진입점.

로컬 실행 (backend 폴더에서)
  uvicorn main:app --reload
  -> http://127.0.0.1:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import get_settings
from core.errors import AppError
from core.firebase import get_backend, get_db, init_db
from routers import chat, conversations, data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    backend = init_db()
    logger.info("DB backend: %s", backend)
    if backend == "memory":  # 로컬 테스트용: CSV를 메모리 DB에 자동 적재
        from seed import seed_from_csv

        logger.info("메모리 DB에 샘플 데이터 %d건 적재", seed_from_csv(get_db()))
    yield


app = FastAPI(
    title="서울 대기질 AI 비서 API",
    description="서울 일별 초미세먼지·기상 데이터를 요약해 GPT 시스템 프롬프트에 주입하는 데이터 기반 AI 채팅 서비스",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: 프론트(Vercel) 도메인에서 이 API를 호출할 수 있도록 허용 목록을 환경변수로 관리
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": "서버 내부 오류가 발생했어요."})


@app.get("/", tags=["health"])
def root():
    return {"service": "서울 대기질 AI 비서 API", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["health"], summary="상태 확인 (콜드스타트 깨우기용)")
def health():
    return {"status": "ok", "db": get_backend(), "model": settings.openai_model,
            "openai_configured": bool(settings.openai_api_key)}


app.include_router(data.router)
app.include_router(conversations.router)
app.include_router(chat.router)
