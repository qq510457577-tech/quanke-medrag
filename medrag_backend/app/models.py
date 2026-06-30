from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PatientInfo(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None
    history: Optional[str] = None
    allergies: Optional[str] = None


class Symptom(BaseModel):
    description: str
    duration_years: int = 0
    duration_months: int = 0
    duration_days: int = 0
    severity: int = 1


class DiagnosisRequest(BaseModel):
    patient: PatientInfo
    symptoms: List[Symptom]
    session_id: Optional[str] = None


class FollowUpAnswer(BaseModel):
    question_id: str
    question: str
    answer: Any
    answer_type: str


class FollowUpRequest(BaseModel):
    session_id: str
    answers: List[FollowUpAnswer] = Field(default_factory=list)


@dataclass
class DiagnosisSession:
    session_id: str
    patient_info: PatientInfo
    symptoms: List[Symptom]
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    diagnosis_hypothesis: List[Dict[str, Any]] = field(default_factory=list)
    current_questions: List[Dict[str, Any]] = field(default_factory=list)
    all_answers: List[Dict[str, Any]] = field(default_factory=list)
    round_count: int = 0
    max_rounds: int = 6
    is_diagnosis_clear: bool = False
    is_emergency: bool = False
    emergency_type: Optional[str] = None
    emergency_warning: Optional[str] = None
    stage_label: str = "初始分诊"

