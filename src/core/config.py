import os

def env_bool(key: str, default: str = "0") -> bool:
    return os.getenv(key, default).strip() in ("1", "true", "True", "yes", "YES")

USE_LLM = env_bool("USE_LLM", "0")
USE_RAG = env_bool("USE_RAG", "0")

DATA_DIR = os.getenv("DATA_DIR", "data")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
EXPORTS_DIR = os.path.join(DATA_DIR, "exports")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
INDEXES_DIR = os.path.join(DATA_DIR, "indexes")