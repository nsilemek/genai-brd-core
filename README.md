# BRD Core  
### Wizard • Scoring • Preview • Export

This repository contains the **core logic** for a guided **BRD / To-Be Journey creation system**.

It provides:
- Wizard-style dynamic questions
- Field-based scoring & validation
- Optional LLM-powered answer normalization
- Section-based BRD preview generation
- DOCX / TXT export

> UI, database, and LLM infrastructure are expected to be provided by the host tool.

---

## Requirements

- Python **3.10+**
- Install dependencies:

```bash
pip install -r requirements.txt

Environment Configuration

Environment variables control runtime behavior.

Example .env:

USE_LLM=0
PYTHONPATH=.

USE_LLM

USE_LLM=0

LLM disabled

Stub logic is used

Demo-safe mode (no external dependency)

USE_LLM=1

LLM enabled

Uses LLMClient._call_model

Automatic fallback to stub if LLM fails

.env is for local/runtime use and should not be committed.
.env.example documents available variables.

Main Integration Entry Points

External tools or UIs should integrate only via:

src/core/service.py

Available Functions
create_session()
resume(session_id)
message(session_id, current_field, user_text, question_id=None)
preview(session_id)
export(session_id, fmt="docx" | "txt")


These functions handle:

Session state management

Wizard progression

Scoring & validation

Preview generation

File export

Architecture Overview
LLM Integration

Client implementation:

src/llm/client.py


Prompt templates:

src/llm/prompts/


Controlled via USE_LLM environment variable

RAG (Stub)

Located in:

src/rag/


Vector store, ingestion, and retrieval are stubbed

Host tool is expected to plug in its own RAG implementation

Scoring Engine

Located in:

src/scoring/scoring_engine_final.py


Responsible for:

Field completeness checks

Guided follow-up questions

Submit eligibility decisions

Runtime Data Folders

The following directories are created and used at runtime
(ignored by Git):

data/sessions   # session state
data/uploads    # uploaded documents
data/indexes    # RAG vector indexes
data/exports    # generated BRD files

Hackathon / Demo Notes

System works fully without LLM access

Safe fallback behavior is implemented

Designed to be embedded into existing internal tools

Focused on reliability and demo stability


---

# 📄 `.env.example`

```env
# USE_LLM=0 -> LLM disabled (stub mode, demo-safe)
# USE_LLM=1 -> LLM enabled (requires tool-side LLM integration)
USE_LLM=0

# Ensures src.* imports resolve correctly
PYTHONPATH=.