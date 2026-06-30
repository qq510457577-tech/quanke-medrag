from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional

from ..config import MAX_SESSION_COUNT, SESSION_TTL_MINUTES
from ..models import DiagnosisSession


class SessionStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, DiagnosisSession] = {}

    def cleanup(self) -> None:
        now = datetime.utcnow()
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if now - session.updated_at > timedelta(minutes=SESSION_TTL_MINUTES)
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)

        if len(self._sessions) > MAX_SESSION_COUNT:
            oldest = sorted(self._sessions.values(), key=lambda item: item.updated_at)
            for session in oldest[: len(self._sessions) - MAX_SESSION_COUNT]:
                self._sessions.pop(session.session_id, None)

    def save(self, session: DiagnosisSession) -> DiagnosisSession:
        session.updated_at = datetime.utcnow()
        self._sessions[session.session_id] = session
        self.cleanup()
        return session

    def get(self, session_id: str) -> Optional[DiagnosisSession]:
        self.cleanup()
        session = self._sessions.get(session_id)
        if session:
            session.updated_at = datetime.utcnow()
        return session
