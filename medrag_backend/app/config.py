from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "app" / "data"
REFERENCE_DIR = DATA_DIR / "references"
GRAPH_DIR = DATA_DIR / "graphs"
VECTOR_STORE_DIR = DATA_DIR / "vector_store"

load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env", override=True)
load_dotenv(BASE_DIR.parent / ".env.local", override=True)
load_dotenv(BASE_DIR / ".env.local", override=True)

APP_TITLE = "全科医生辅助诊断系统"
APP_VERSION = "6.0.0"
SESSION_TTL_MINUTES = 45
MAX_SESSION_COUNT = 500
MAX_FOLLOW_UP_ROUNDS = 6
QUESTIONS_PER_ROUND = 3

DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_ENABLED = bool(DEEPSEEK_API_KEY)
