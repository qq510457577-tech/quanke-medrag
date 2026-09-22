from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import APP_TITLE, APP_VERSION, CORS_ORIGINS, MAX_FOLLOW_UP_ROUNDS
from .models import DiagnosisRequest, FollowUpRequest
from .services.diagnosis_service import DiagnosisService, WorkflowError
from .services.llm_service import ClinicalModelError


service = DiagnosisService()

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description="面向基层全科医生的分层递进式问诊与辅助诊断系统。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ClinicalModelError)
async def model_error(request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(WorkflowError)
async def workflow_error(request, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/")
async def root() -> dict:
    return {"service": APP_TITLE, "version": APP_VERSION}


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "version": APP_VERSION, "max_follow_up_rounds": MAX_FOLLOW_UP_ROUNDS, "min_follow_up_rounds": 4, "reasoning_mode": "patient_context_only", "local_graph_enabled": False}


@app.post("/api/diagnosis/start")
async def start_diagnosis(request: DiagnosisRequest) -> dict:
    return await service.start(request)


@app.post("/api/diagnosis/follow-up")
async def follow_up(request: FollowUpRequest) -> dict:
    try:
        return await service.follow_up(request.session_id, request.answers)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/diagnosis/final")
async def finalize(request: FollowUpRequest) -> dict:
    try:
        return await service.finalize(request.session_id, request.answers)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
