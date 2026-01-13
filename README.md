# **V-RAI – AI-Powered BRD & To-Be Journey Wizard**

> Vodafone-grade AI assistant for building **high-quality, compliant, and measurable** Business Requirement Documents.

V-RAI is a guided AI system that helps teams create **clear, structured, and review-ready BRDs** by combining:
- Wizard-based question flow  
- Scoring & validation  
- Privacy & compliance gates  
- PDF slide ingestion  
- Exportable BRD documents  

It is designed for **enterprise environments** where requirements must be:
- measurable  
- complete  
- compliant  
- and reviewable  

---

## 🧠 What V-RAI Does

V-RAI transforms scattered business input into a **high-quality BRD** by guiding users through a structured flow.

It provides:

- 🧭 **Wizard-style guided questions**  
- 📊 **Field-based scoring & weak-point detection**  
- 🔒 **Mandatory Data Privacy / Compliance gate**  
- 📎 **PDF slide ingestion → auto-fills Background**  
- 🧩 **LLM-powered or stub-mode normalization**  
- 📝 **BRD preview (section-based)**  
- 📄 **DOCX / TXT export for Jira, Confluence, etc.**

The system can run **fully offline** in demo mode or be connected to enterprise AI and RAG stacks.

---

## 🧩 System Architecture

[UI / Streamlit]
│
▼
[ service.py ] ← only integration point
│
▼
[ flow.py ] → wizard, intake, PDF, logic
│
▼
[ state.py ] → session, persistence
│
▼
[ scoring_engine_final.py ]
│
▼
[ BRD Generator ]
│
▼
[ DOCX / TXT Export ]

The architecture is **state-driven**, not chat-driven.  
This guarantees predictable behavior, scoring, and compliance.

---

## 🧭 Guided Wizard Flow

1. **PDF Intake Gate**  
   - “Do you have a slide deck?”  
   - If yes → upload PDF → Background auto-filled  
   - If no → proceed manually  

2. **BRD Field Wizard**  
   - Background  
   - Expected Results  
   - Customer Group  
   - Channels  
   - Journeys  
   - Reports  
   - Traffic  

3. **Privacy & Compliance (Mandatory)**  
   - Not scored  
   - But **blocks submit** if unanswered  
   - If “YES” → creates **Data Privacy task warning**  

4. **Scoring & Weak Field Detection**  
   - Fields below quality threshold are re-asked  
   - Vague or missing content is detected  

5. **Preview & Export**  
   - Section-based BRD preview  
   - DOCX / TXT generation  

---

## 🔒 Privacy & Compliance Gate

V-RAI enforces a **mandatory privacy question**:

> “Does this requirement involve personal data?”

Rules:
- Privacy **does not affect score**  
- But **export / submit is blocked** unless answered  
- If YES → system warns:  
  > “A Data Privacy Jira task must be created”  

This makes V-RAI **enterprise-safe by design**.

---

## 📎 PDF Ingestion

Users can upload existing slide decks.

The system:
- extracts text (pypdf if available, stub otherwise)  
- summarizes slides into **Background**  
- appends it to the BRD  
- continues wizard flow automatically  

This makes V-RAI ideal for:
- existing PowerPoint-driven processes  
- workshop outputs  
- management decks  

---

## 🧪 Demo Mode vs LLM Mode

Behavior is controlled via environment variables.

| Mode        | USE_LLM | Behavior |
|-------------|--------:|----------|
| Demo-safe   | `0`     | No external AI, deterministic, hackathon-safe |
| AI-powered | `1`     | Uses LLMClient for normalization & summarization |

If LLM fails → system automatically falls back to stub logic.

---

## 🧠 LLM Integration

Located in:

src/llm/client.py
src/llm/prompts/


Used for:
- Answer normalization  
- PDF → Background summarization  

Fully optional and safe to disable.

---

## 📚 RAG (Planned / Stub)

RAG is prepared but not yet wired.

Location:
src/rag/

The system is designed to read:
- Confluence pages  
- Wiki documents  
- Internal guidelines  

to enrich answers and validation.

---

## 📂 Runtime Data

These folders are created automatically (ignored by Git):
data/sessions # user sessions
data/uploads # uploaded PDFs
data/indexes # RAG indexes
data/exports # generated BRDs


---

## 🚀 How to Run

Install dependencies:
```bash
pip install -r requirements.txt
```
Create .env:

USE_LLM=0
PYTHONPATH=.

Run Streamlit:
streamlit run app.py

🧩 Integration API

External tools must integrate only via:
src/core/service.py

Available functions:
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
🎯 Hackathon & Enterprise Focus

V-RAI is designed for:

corporate environments

restricted networks

no-internet demos

enterprise compliance

It never breaks if AI or RAG is missing and always guarantees:

consistent scoring

mandatory privacy checks

stable demo behavio
