from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import APP_TITLE, APP_VERSION, MAX_FOLLOW_UP_ROUNDS
from .models import DiagnosisRequest, FollowUpRequest
from .services.diagnosis_service import DiagnosisService


service = DiagnosisService()

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description="面向基层全科医生的分层递进式问诊与辅助诊断系统。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict:
    return {"service": APP_TITLE, "version": APP_VERSION}


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "version": APP_VERSION, "max_follow_up_rounds": MAX_FOLLOW_UP_ROUNDS}


@app.post("/api/diagnosis/start")
async def start_diagnosis(request: DiagnosisRequest) -> dict:
    return service.start(request)


@app.post("/api/diagnosis/follow-up")
async def follow_up(request: FollowUpRequest) -> dict:
    try:
        return service.follow_up(request.session_id, request.answers)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/diagnosis/final")
async def finalize(request: FollowUpRequest) -> dict:
    try:
        return await service.finalize(request.session_id, request.answers)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
