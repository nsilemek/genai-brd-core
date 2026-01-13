import os
import base64
import streamlit as st
from pathlib import Path
from src.core import service

SHOW_DEBUG = os.getenv("SHOW_DEBUG", "0") == "1"


# MUST be first Streamlit call
st.set_page_config(
    page_title="V-RAI BRD AI Agent",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Paths ----------
ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"
LOGO_PATH = ASSETS / "vrai_logo.png"
BG_PATH = ASSETS / "vrai_bg.png"


def _img_to_data_uri(path: Path) -> str | None:
    if not path.exists():
        return None
    b = path.read_bytes()
    ext = path.suffix.lower().replace(".", "")
    mime = "png" if ext == "png" else ext
    return f"data:image/{mime};base64," + base64.b64encode(b).decode("utf-8")


logo_data = _img_to_data_uri(LOGO_PATH)
bg_data = _img_to_data_uri(BG_PATH)

# ---------- CSS (SAFE) ----------
st.markdown(
    f"""
<style>
/* App background */
.stApp {{
  background:
    radial-gradient(1200px 600px at 50% -10%, rgba(230,0,0,0.20), rgba(11,11,15,0) 60%),
    radial-gradient(900px 500px at 80% 10%, rgba(98,0,255,0.16), rgba(11,11,15,0) 55%),
    radial-gradient(900px 500px at 20% 30%, rgba(0,180,255,0.10), rgba(11,11,15,0) 55%),
    linear-gradient(180deg, #0B0B0F 0%, #07070A 100%);
}}

/* Background hero image */
.stApp::before {{
    content: "";
    position: fixed;
    top: 55px;
    left: 50%;
    transform: translateX(-50%);
    width: 780px;
    height: 780px;
    background: url("{bg_data or ""}") center / contain no-repeat;
    opacity: 0.20;
    filter: blur(1px);
    z-index: 0;
    pointer-events: none;
}}

/* Keep Streamlit layout stable */
.block-container {{
  padding-top: 1.0rem;
  max-width: 1150px;
  position: relative;
  z-index: 1;
}}

/* Sidebar glass */
section[data-testid="stSidebar"] {{
  background: rgba(18, 18, 26, 0.65);
  backdrop-filter: blur(16px);
  border-right: 1px solid rgba(255,255,255,0.08);
}}

hr {{
  border: none !important;
  border-top: 1px solid rgba(255,255,255,0.10) !important;
}}

/* ---------- HERO CARD ---------- */
.vrai-hero {{
  width: 100%;
  display: flex;
  justify-content: center;
  margin: 10px 0 18px 0;
}}
.vrai-hero-inner {{
  width: 100%;
  max-width: 980px;
  padding: 26px 18px 18px 18px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 22px;
  backdrop-filter: blur(14px);
  box-shadow: 0 14px 40px rgba(0,0,0,0.35);
  text-align: center;
}}

/* Bigger centered logo */
.vrai-logo {{
  width: 220px;
  height: 220px;
  margin: 0 auto 10px auto;
  display: block;
  filter: drop-shadow(0 12px 28px rgba(230,0,0,0.20));
}}

.vrai-title p {{
  margin: 9px 0 0 0;
  text-align:center;
  color: rgba(237,237,237,0.72);
  font-size: 14px;
}}
.vrai-accent {{
  width: 240px;
  height: 6px;
  margin: 16px auto 0 auto;
  border-radius: 999px;
  background: linear-gradient(90deg,#E60000, rgba(140,0,255,0.85), rgba(0,180,255,0.55));
}}

/* Tabs as pills */
div[data-testid="stTabs"] button {{
  background: rgba(255,255,255,0.06) !important;
  border: 1px solid rgba(255,255,255,0.10) !important;
  color: #EDEDED !important;
  border-radius: 999px !important;
  padding: 8px 14px !important;
  font-weight: 760 !important;
  margin-right: 8px !important;
}}
div[data-testid="stTabs"] button[aria-selected="true"] {{
  background: rgba(230,0,0,0.22) !important;
  border-color: rgba(230,0,0,0.45) !important;
  box-shadow:
    0 0 0 1px rgba(230,0,0,0.18) inset,
    0 10px 30px rgba(230,0,0,0.14),
    0 0 30px rgba(120,0,255,0.10);
}}

/* Primary buttons  */
button[kind="primary"] {{
  background: linear-gradient(180deg, #E60000 0%, #B30000 100%) !important;
  border: 1px solid rgba(255,255,255,0.10) !important;
  color: #fff !important;
  border-radius: 18px !important;
  padding: 10px 16px !important;
  font-weight: 850 !important;
  box-shadow:
    0 12px 30px rgba(230,0,0,0.22),
    0 0 24px rgba(140,0,255,0.10);
}}
button[kind="primary"]:hover {{ filter: brightness(1.06); }}

/* Remove focus rings (safe) */
button:focus, button:focus-visible {{
  outline: none !important;
  box-shadow: none !important;
}}

/* Chat input container */
div[data-testid="stChatInput"] {{
  background: rgba(255,255,255,0.06) !important;
  border-radius: 999px !important;
  border: 1px solid rgba(255,255,255,0.12) !important;
  box-shadow:
    0 0 0 1px rgba(230,0,0,0.10) inset,
    0 12px 30px rgba(0,0,0,0.42),
    0 0 18px rgba(140,0,255,0.14);
  padding: 6px 10px !important;
}}
div[data-testid="stChatInput"] textarea {{
  background: transparent !important;
  border: none !important;
  color: #EDEDED !important;
  padding: 12px 16px !important;
  font-size: 15px !important;
}}
div[data-testid="stChatInput"] textarea:focus {{
  outline: none !important;
  box-shadow: none !important;
}}

/* Metrics */
[data-testid="stMetricValue"] {{
  color:#E60000;
  font-weight: 900;
}}

/* ============================
   CHAT LAYOUT: LIKE YOUR EXAMPLE
   - assistant left (logo)
   - user right (default svg avatar)
   - bubbles with max width
   ============================ */

/* Remove the "full card" look and let us control bubble */
div[data-testid="stChatMessage"] {{
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin: 14px 0 !important;
}}

/* Base row (assistant default) */
div[data-testid="stChatMessage"] {{
  display: flex !important;
  align-items: flex-start !important;
  justify-content: flex-start !important;
  gap: 10px !important;
}}

/* Bubble container */
div[data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {{
  padding: 12px 14px !important;
  border-radius: 16px !important;
  border: 1px solid rgba(255,255,255,0.10) !important;
  box-shadow: 0 8px 22px rgba(0,0,0,0.25) !important;
  backdrop-filter: blur(14px) !important;
  max-width: 72% !important;
}}

/* Assistant bubble (left) */
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatar"] img)
  [data-testid="stChatMessageContent"] {{
  background: rgba(255,255,255,0.06) !important;
}}

/* User message detection: Streamlit user avatar is usually SVG.
   Put avatar to the RIGHT using row-reverse and align bubble right. */
/* USER: avatar is emoji -> rendered as span -> move to right */
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatar"] span){{
  flex-direction: row-reverse !important;
  justify-content: flex-start !important;
}}

div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatar"] span)
  [data-testid="stChatMessageContent"]{{
  background: rgba(230,0,0,0.12) !important;
  border-color: rgba(230,0,0,0.28) !important;
  box-shadow:
    0 10px 28px rgba(230,0,0,0.14),
    0 0 22px rgba(140,0,255,0.10) !important;
}}

div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatar"] svg)
  [data-testid="stChatMessageContent"] {{
  background: rgba(230,0,0,0.12) !important;
  border-color: rgba(230,0,0,0.28) !important;
  box-shadow:
    0 10px 28px rgba(230,0,0,0.14),
    0 0 22px rgba(140,0,255,0.10) !important;
  text-align: left !important;
}}

/* Avatar sizing (both) */
div[data-testid="stChatMessageAvatar"] img {{
  width: 28px !important;
  height: 28px !important;
  border-radius: 999px !important;
  filter: drop-shadow(0 8px 18px rgba(230,0,0,0.18)) !important;
}}
div[data-testid="stChatMessageAvatar"] {{
  width: 32px !important;
  height: 32px !important;
}}
div[data-testid="stChatMessageAvatar"] svg {{
  width: 28px !important;
  height: 28px !important;
  border-radius: 999px !important;
  filter: drop-shadow(0 8px 18px rgba(230,0,0,0.18)) !important;
}}
</style>
""",
    unsafe_allow_html=True,
)

# ---------- HERO HEADER ----------
st.markdown('<div class="vrai-hero"><div class="vrai-hero-inner">', unsafe_allow_html=True)
if logo_data:
    st.markdown(f'<img class="vrai-logo" src="{logo_data}" />', unsafe_allow_html=True)

st.markdown(
    """
<div class="vrai-title">
  <p>Vodafone AI Requirements Assistant</p>
  <div class="vrai-accent"></div>
</div>
</div></div>
""",
    unsafe_allow_html=True,
)

assistant_avatar = str(LOGO_PATH) if LOGO_PATH.exists() else None

# ---------- Flow constants (must match flow.py) ----------
INTAKE_FIELD = "__INTAKE__"
UPLOAD_PDF_FIELD = "__UPLOAD_PDF__"

PDF_INTRO_Q = (
    "Hazır bir **slayt sunumunuz** var mı?\n\n"
    "- Varsa **Evet** yazın, ardından PDF yükleyin. Ben de önemli noktaları çıkarıp **Background** alanını kısaca doldurayım.\n"
    "- Yoksa **Hayır** yazıp devam edebilirsiniz."
)

PDF_UPLOAD_Q = (
    "PDF dosyanızı şimdi yükleyin. Yükledikten sonra ben özetleyip **Background** alanına ekleyeceğim.\n\n"
    "PDF yoksa **Hayır** yazıp devam edebilirsiniz."
)

INTRO_TEXT = (
    "Merhaba! Ben **V-RAI** 👋 Vodafone için hazırlanmış bir **BRD (Business Requirements Document)** asistanıyım.\n"
    "Sana adım adım sorular sorarak BRD’yi hızlı ve net şekilde doldurmana yardımcı olacağım.\n"
)

# ---------- Helpers ----------
def _init_session():
    payload = service.create_session()
    st.session_state["session_id"] = payload["session_id"]
    st.session_state["payload"] = payload
    st.session_state["preview"] = None
    st.session_state["chat"] = []
    st.session_state["intro_sent"] = False


def _push(role: str, content: str):
    st.session_state["chat"].append({"role": role, "content": content})


def _bot_intro(payload: dict) -> str:
    """
    IMPORTANT RULE:
    - UI mode must be determined ONLY by next_field
    """
    qs = payload.get("next_questions") or []
    next_field = payload.get("next_field")

    # Intake step (ask yes/no)
    if next_field == INTAKE_FIELD:
        question = str(qs[0]) if qs else PDF_INTRO_Q
        # First time: prepend greeting + question in one bubble (like your example)
        if not st.session_state.get("intro_sent", False):
            st.session_state["intro_sent"] = True
            return INTRO_TEXT + "\n\n" + question
        return question

    # Upload step (uploader should show)
    if next_field == UPLOAD_PDF_FIELD:
        return str(qs[0]) if qs else PDF_UPLOAD_Q

    if not next_field:
        return "Tüm alanlar tamam görünüyor. Preview / Export alabilirsin."

    msg = f"Şimdi **{next_field}** alanını dolduralım.\n"
    for i, q in enumerate(qs[:2]):
        msg += f"\n**Soru {i+1}:** {q}"
    return msg


def _refresh_bot_message(payload: dict):
    _push("assistant", _bot_intro(payload))


# ---------- Session init ----------
if "session_id" not in st.session_state:
    _init_session()
    _refresh_bot_message(st.session_state["payload"])

payload = st.session_state.get("payload", {})
session_id = st.session_state["session_id"]

# ---------- Sidebar ----------
with st.sidebar:
    # Debug-only üst kısım (kullanıcı görmesin)
    if SHOW_DEBUG:
        st.header("Status")
        st.write(f"**USE_LLM:** `{os.getenv('USE_LLM','0')}`")
        st.write(f"**Session:** `{session_id}`")
        st.divider()

    # Kullanıcıya açık kısım (kalsın)
    st.subheader("Score")
    st.metric("Total", f"{payload.get('total_score','-')}/{payload.get('max_total','-')}")
    st.write("**Submit Allowed:**", payload.get("submit_allowed", False))

    blockers = payload.get("submit_blockers") or []
    if blockers:
        st.warning("\n".join(blockers))

    st.divider()

    # Butonlar (kalsın)
    if st.button("Restart Session", type="primary"):
        _init_session()
        _refresh_bot_message(st.session_state["payload"])
        st.rerun()

    if st.button("Generate Preview", type="primary"):
        prev = service.preview(session_id)
        st.session_state["preview"] = prev.get("sections", {})
        st.success("Preview generated.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Export DOCX", type="primary"):
            res = service.export(session_id, fmt="docx")
            st.success(f"DOCX: {res['path']}")
    with c2:
        if st.button("Export TXT", type="primary"):
            res = service.export(session_id, fmt="txt")
            st.success(f"TXT: {res['path']}")


# ---------- Tabs ----------
if SHOW_DEBUG:
    tab_chat, tab_fields, tab_preview = st.tabs(["Chat", "Fields", "Preview"])
else:
    tab_chat, tab_preview = st.tabs(["Chat", "Preview"])



with tab_chat:
    # Render chat
    for m in st.session_state.get("chat", []):
        if m["role"] == "assistant":
            with st.chat_message("assistant", avatar=assistant_avatar):
                st.markdown(m["content"])
        else:  
            with st.chat_message("user"):
                st.markdown(m["content"])

    next_field = payload.get("next_field")

    # --- PDF Upload UI ---
    if next_field == UPLOAD_PDF_FIELD:
        st.markdown("### 📎 PDF Yükle (Slides)")

        uploaded = st.file_uploader(
            "PDF dosyanı seç",
            type=["pdf"],
            accept_multiple_files=False,
        )

        col_a, col_b = st.columns([1, 2])
        with col_a:
            btn_skip = st.button("PDF yok, devam et", type="primary")
        with col_b:
            st.caption("PDF yüklersen Background otomatik doldurulacak")

        # Skip flow
        if btn_skip:
            _push("user", "Hayır")
            new_payload = service.message(
                session_id=session_id,
                current_field=UPLOAD_PDF_FIELD,
                user_text="Hayır",
                question_id=None,
            )
            st.session_state["payload"] = new_payload
            payload = new_payload
            _refresh_bot_message(payload)
            st.rerun()

        # Upload flow
        if uploaded is not None:
            _push("user", f"[PDF yüklendi] {uploaded.name}")
            new_payload = service.upload_pdf(session_id, uploaded.getvalue(), uploaded.name)
            st.session_state["payload"] = new_payload
            payload = new_payload
            _refresh_bot_message(payload)
            st.rerun()

        st.stop()

    # --- Normal chat input ---
    user_msg = st.chat_input("Cevabını yaz...")

    if user_msg:
        _push("user", user_msg)

        current_field = payload.get("next_field")
        if not current_field:
            _push("assistant", "Şu an tüm alanlar dolu görünüyor. Preview/Export alabilirsin.")
        else:
            new_payload = service.message(
                session_id=session_id,
                current_field=current_field,
                user_text=user_msg,
                question_id=None,
            )
            st.session_state["payload"] = new_payload
            payload = new_payload
            _refresh_bot_message(payload)

        st.rerun()

if SHOW_DEBUG:
    with tab_fields:
        st.subheader("Current Fields State (Debug)")
        st.json(payload)


with tab_preview:
    st.subheader("BRD Preview")
    sections = st.session_state.get("preview") or {}
    if not sections:
        st.caption("Preview yok. Sidebar’dan **Generate Preview** ile oluştur.")
    else:
        for name, text in sections.items():
            with st.expander(name, expanded=True):
                st.write(text)
