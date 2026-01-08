from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


FieldName = str
SessionId = str


@dataclass
class FieldUpdate:
    ts: str                       # ISO-8601 timestamp
    field: FieldName
    value: Any
    source: str                   # "guided" | "pdf" | "rag" | "manual"
    confidence: float = 1.0
    evidence: Optional[str] = None


@dataclass
class SessionState:
    session_id: SessionId
    created_at: str               # ISO-8601 timestamp

    # Canonical fields used for scoring + BRD generation
    fields: Dict[FieldName, Any] = field(default_factory=dict)

    # Raw Q/A (optional but useful)
    answers: Dict[str, str] = field(default_factory=dict)

    # Audit trail
    field_updates: List[FieldUpdate] = field(default_factory=list)

    # Token-safe rolling summary (6–8 lines)
    system_summary: str = ""

    # RAG
    rag_index_id: Optional[str] = None
    uploaded_files: List[Dict[str, Any]] = field(default_factory=list)  # {name,path,type,size}

    # Latest scoring snapshot (store as dict to avoid tight coupling)
    scores: Optional[Dict[str, Any]] = None

    # Optional: current step tracking
    current_field: Optional[FieldName] = None
    last_question_ids: List[str] = field(default_factory=list)
