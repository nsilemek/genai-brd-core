from .config import SESSIONS_DIR, EXPORTS_DIR, UPLOADS_DIR, INDEXES_DIR
from pathlib import Path

def ensure_data_dirs():
    for p in [SESSIONS_DIR, EXPORTS_DIR, UPLOADS_DIR, INDEXES_DIR]:
        Path(p).mkdir(parents=True, exist_ok=True)