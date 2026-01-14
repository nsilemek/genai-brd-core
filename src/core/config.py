from __future__ import annotations
 
import os
from typing import Optional
 
 
def env_bool(key: str, default: str = "0") -> bool:
    """
    Env bool parser.
    Accepts: 1/0, true/false, yes/no (case-insensitive)
    """
    v = os.getenv(key, default)
    if v is None:
        v = default
    return str(v).strip().lower() in ("1", "true", "yes", "y")
 
 
def env_str(key: str, default: str = "") -> str:
    v = os.getenv(key, default)
    if v is None:
        v = default
    return str(v).strip()
 
 
# -------------------------------------------------
# ✅ Runtime getters (preferred in flow.py)
# -------------------------------------------------
def use_llm() -> bool:
    return env_bool("USE_LLM", "0")
 
 
def use_rag() -> bool:
    return env_bool("USE_RAG", "0")
 
 
# -------------------------------------------------
# Backward-compat constants (import-time snapshot)
# Keep these so existing code doesn't break,
# but DO NOT rely on them for runtime toggling.
# -------------------------------------------------
USE_LLM = use_llm()
USE_RAG = use_rag()
 
DATA_DIR = env_str("DATA_DIR", "data")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
EXPORTS_DIR = os.path.join(DATA_DIR, "exports")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
INDEXES_DIR = os.path.join(DATA_DIR, "indexes")