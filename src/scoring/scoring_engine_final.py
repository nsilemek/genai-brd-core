"""
SCORING ENGINE (Wizard / State Based) - FIXED + PRIVACY (No separate score)

- Uses field-based input (no BRD text parsing)
- Compatible with guided wizard + chatbot UI
- Returns weak fields + guided question IDs
- Token-safe (LLM not required here)

Privacy (Minimum):
- One mandatory question:
  "Kişisel veri içeriyor mu / Data Privacy kapsamına giriyor mu? Açıklayınız. (Yoksa ‘Hayır’ yazabilirsiniz)"
- Privacy does NOT affect BRD score.
- Submit is BLOCKED unless privacy is answered.
- If privacy answer indicates "YES", we add a finding:
    "Jira’da Data Privacy task açılması gerekiyor."
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# -------------------------------------------------
# 1) Fields & max scores (BRD total = 100)
# -------------------------------------------------

FIELD_MAX: Dict[str, int] = {
    "Background": 15,
    "Expected Results": 15,
    "Target Customer Group": 5,
    "Impacted Channels": 10,
    "Impacted Journey": 5,
    "Journeys Description": 40,
    "Reports Needed": 5,
    "Traffic Forecast": 5,
}

PRIVACY_FIELD = "Privacy / Compliance"

VAGUE_WORDS_TR = [
    "uygun", "mümkün", "hızlı", "asap", "optimum", "gerektiğinde", "user friendly",
    "makul", "iyileştir", "geliştir", "daha iyi", "kolay", "en kısa", "verimli"
]

# -------------------------------------------------
# 2) Guided Questions (ID-based, UI resolves text)
# -------------------------------------------------

QUESTIONS_TR: Dict[str, str] = {
    "Q_BACKGROUND_EMPTY": "Mevcut durumu ve problemi 1–2 cümle ile anlatabilir misiniz?",
    "Q_BACKGROUND_MORE_DETAIL": "Mevcut süreçteki ana pain point nedir? Biraz daha detay ekleyebilir misiniz?",
    "Q_BACKGROUND_MORE_SPECIFIC": "Problemi daha spesifik ve mümkünse ölçülebilir hale getirebilir misiniz?",

    "Q_EXPECTED_RESULTS_EMPTY": "Bu değişiklikle beklenen somut sonuç nedir?",
    "Q_EXPECTED_RESULTS_MEASURABLE": "Başarıyı nasıl ölçeceğiz? (örn. % / süre / hata oranı / adet)",
    "Q_EXPECTED_RESULTS_ADD_TARGET": "Hedefi ölçülebilir yazabilir misiniz? (örn. X% azalt, Z sn altı)",

    "Q_CUSTOMER_GROUP_EMPTY": "Hangi müşteri segmenti/grubu etkilenecek?",
    "Q_CUSTOMER_GROUP_SPECIFY": "‘Tüm müşteriler’ yerine segment belirtebilir misiniz?",

    "Q_CHANNELS_EMPTY": "Hangi kanallar etkilenecek?",
    "Q_CHANNELS_IMPACT_EXPLAIN": "Bu kanallar nasıl etkilenecek?",
    "Q_CHANNELS_ADD_RATIONALE": "Her kanal için etkiyi 1 cümle ile özetleyebilir misiniz?",

    "Q_JOURNEY_EMPTY": "Hangi journey etkilenecek?",
    "Q_JOURNEY_NEW_EXISTING": "Bu mevcut bir journey mi yoksa yeni mi?",

    "Q_JDESC_EMPTY": "Journey akışını anlatır mısınız? As-is / To-be şeklinde.",
    "Q_JDESC_BEFORE_AFTER": "Mevcut ve hedef akış arasındaki farklar neler?",
    "Q_JDESC_EDGE_CASE": "Önemli edge-case’ler neler?",

    "Q_REPORTS_EMPTY": "Bu değişiklik için rapor ihtiyacı var mı?",
    "Q_REPORTS_DETAIL": "Raporu kim kullanacak ve hangi metrikleri içerecek?",

    "Q_TRAFFIC_EMPTY": "Beklenen trafik/kullanım değişimi var mı?",
    "Q_TRAFFIC_ESTIMATE": "Tahmini sayısal olarak paylaşabilir misiniz?",

    # ✅ Mandatory privacy question (hackathon)
    "Q_PRIVACY_MIN": "Kişisel veri içeriyor mu / Data Privacy kapsamına giriyor mu? Açıklayınız. (Yoksa ‘Hayır’ yazabilirsiniz)",
}

# -------------------------------------------------
# 3) Data models
# -------------------------------------------------

@dataclass
class FieldScore:
    field: str
    score: int
    max_score: int
    findings: List[str]
    question_ids: List[str]

@dataclass
class ScoreResult:
    total_score: int
    max_total: int
    field_scores: List[FieldScore]
    submit_allowed: bool
    submit_blockers: List[str]

# -------------------------------------------------
# 4) Helpers
# -------------------------------------------------

def _s(val: Optional[str]) -> str:
    return (val or "").strip()

def char_len(s: str) -> int:
    return len(_s(s))

def contains_any(text: str, words: List[str]) -> bool:
    t = _s(text).lower()
    return any(w.lower() in t for w in words)

def _looks_like_yes(text: str) -> bool:
    """
    Very small heuristic: if user indicates personal data exists / privacy scope yes.
    """
    low = _s(text).lower()
    yes_markers = [
        "evet", "var", "yes", "pii", "kişisel veri", "personal data", "kvkk kapsamında", "gdpr",
        "telefon", "email", "e-posta", "tc", "kimlik", "adres", "msisdn"
    ]
    no_markers = ["hayır", "yok", "no", "none", "içermiyor", "not in scope"]
    if any(n in low for n in no_markers):
        return False
    return any(y in low for y in yes_markers)

# -------------------------------------------------
# 5) Field scorers (BRD 100)
# -------------------------------------------------

def score_background(val: str) -> Tuple[int, List[str], List[str]]:
    if char_len(val) == 0:
        return 0, ["Background alanı boş."], ["Q_BACKGROUND_EMPTY"]
    if char_len(val) < 50:
        return 5, ["Background çok kısa."], ["Q_BACKGROUND_MORE_DETAIL"]
    if contains_any(val, VAGUE_WORDS_TR):
        return 13, ["Belirsiz ifadeler var."], ["Q_BACKGROUND_MORE_SPECIFIC"]
    return 15, [], []

def score_expected_results(val: str) -> Tuple[int, List[str], List[str]]:
    if char_len(val) == 0:
        return 0, ["Expected Results alanı boş."], ["Q_EXPECTED_RESULTS_EMPTY"]
    measurable = bool(re.search(r"(%|sn|dk|adet|oran|kpi|ms|saniye|latency|throughput)", val.lower()))
    if measurable:
        return 15, [], []
    return 10, ["Ölçülebilir hedef yok."], ["Q_EXPECTED_RESULTS_ADD_TARGET"]

def score_target_customer_group(val: str) -> Tuple[int, List[str], List[str]]:
    if char_len(val) == 0:
        return 0, ["Target Customer Group boş."], ["Q_CUSTOMER_GROUP_EMPTY"]
    low = val.lower()
    if "tüm" in low or "all" in low or "everyone" in low:
        return 2, ["Müşteri grubu çok genel."], ["Q_CUSTOMER_GROUP_SPECIFY"]
    return 5, [], []

def score_impacted_channels(val: str) -> Tuple[int, List[str], List[str]]:
    if char_len(val) == 0:
        return 0, ["Impacted Channels boş."], ["Q_CHANNELS_EMPTY"]
    raw = _s(val)
    if "," in raw:
        return 10, [], []
    if len(raw.split()) < 3:
        return 5, ["Kanal detayları zayıf."], ["Q_CHANNELS_IMPACT_EXPLAIN"]
    return 10, [], []

# def score_impacted_journey(val: str) -> Tuple[int, List[str], List[str]]:
#     print("Impacted Journey value for scoring:", val)
#     if char_len(val) == 0:
#         return 0, ["Impacted Journey boş."], ["Q_JOURNEY_EMPTY"]
#     low = val.lower()
#     print("Impacted Journey value for scoring lower:", low)
#     if any(x in low for x in ["yeni", "new", "mevcut", "existing"]):
#         return 5, [], []
#     return 3, ["Journey tipi net değil."], ["Q_JOURNEY_NEW_EXISTING"]

def score_impacted_journey(val: str) -> Tuple[int, List[str], List[str]]:
    if char_len(val) == 0:
        return 0, ["Impacted Journey boş."], ["Q_JOURNEY_EMPTY"]
 
    low = val.lower()
 
    # journey tipi (mevcut/yeni) varsa tam puan
    if any(x in low for x in ["yeni", "new", "mevcut", "existing"]):
        return 5, [], []
 
    # journey adı var ama tipi yoksa: yine iyi, ama küçük eksik
    # (journey adı gibi duruyor mu?) -> en az 2 kelime vs.
    if len(_s(val).split()) >= 2:
        return 4, ["Journey tipi (mevcut/yeni) belirtilmemiş."], ["Q_JOURNEY_NEW_EXISTING"]
 
    return 3, ["Journey tanımı çok kısa/genel."], ["Q_JOURNEY_NEW_EXISTING"]

def score_journeys_description(val: str) -> Tuple[int, List[str], List[str]]:
    if char_len(val) == 0:
        return 0, ["Journey Description boş."], ["Q_JDESC_EMPTY"]
    if char_len(val) < 120:
        return 20, ["Journey açıklaması zayıf."], ["Q_JDESC_BEFORE_AFTER"]
    if any(x in val.lower() for x in ["edge", "hata", "timeout", "error", "exception", "duplicate", "fail"]):
        return 40, [], []
    return 35, ["Edge-case eksik."], ["Q_JDESC_EDGE_CASE"]

def score_reports_needed(val: str) -> Tuple[int, List[str], List[str]]:
    if char_len(val) == 0:
        return 0, ["Reports Needed boş."], ["Q_REPORTS_EMPTY"]
    low = val.lower()
    if any(x in low for x in ["yok", "no", "none"]):
        return 3, [], []
    if char_len(val) < 25:
        return 3, ["Rapor ihtiyacı belirtilmiş ama detay az."], ["Q_REPORTS_DETAIL"]
    return 5, [], []

def score_traffic_forecast(val: str) -> Tuple[int, List[str], List[str]]:
    if char_len(val) == 0:
        return 0, ["Traffic Forecast boş."], ["Q_TRAFFIC_EMPTY"]
    if re.search(r"\d", val):
        return 5, [], []
    return 3, ["Tahmin sayısal değil."], ["Q_TRAFFIC_ESTIMATE"]

FIELD_SCORERS = {
    "Background": score_background,
    "Expected Results": score_expected_results,
    "Target Customer Group": score_target_customer_group,
    "Impacted Channels": score_impacted_channels,
    "Impacted Journey": score_impacted_journey,
    "Journeys Description": score_journeys_description,
    "Reports Needed": score_reports_needed,
    "Traffic Forecast": score_traffic_forecast,
}

# -------------------------------------------------
# 6) Privacy (mandatory question, no score)
# -------------------------------------------------

def privacy_findings_and_blockers(fields: Dict[str, str]) -> Tuple[List[str], List[str], List[str]]:
    """
    Returns:
      findings (for UI),
      question_ids (if we need to ask),
      blockers (submit blockers)
    """
    findings: List[str] = []
    qids: List[str] = []
    blockers: List[str] = []

    ans = _s(fields.get(PRIVACY_FIELD, ""))
    if not ans:
        qids.append("Q_PRIVACY_MIN")
        blockers.append("Privacy sorusu cevaplanmadan submit/export edilemez.")
        return findings, qids, blockers

    # If YES -> advise Jira privacy task
    if _looks_like_yes(ans):
        findings.append("⚠️ Kişisel veri / Data Privacy kapsamı var görünüyor. Jira’da **Data Privacy** task açılması gerekiyor.")
    else:
        findings.append("✅ Privacy: ‘Hayır’ olarak işaretlendi / kişisel veri yok.")

    return findings, qids, blockers

# -------------------------------------------------
# 7) Final score computation (STATE BASED)
# -------------------------------------------------

def compute_scores_from_fields(fields: Dict[str, str]) -> ScoreResult:
    total = 0
    max_total = sum(FIELD_MAX.values())
    field_scores: List[FieldScore] = []

    # --- BRD fields (0-100) ---
    for field, max_sc in FIELD_MAX.items():
        scorer = FIELD_SCORERS[field]
        val = fields.get(field, "")
        score, findings, qids = scorer(val)
        score = max(0, min(score, max_sc))
        total += score
        field_scores.append(FieldScore(field, score, max_sc, findings, qids))

    # --- Privacy (virtual, no score) ---
    p_findings, p_qids, p_blockers = privacy_findings_and_blockers(fields)
    field_scores.append(FieldScore(PRIVACY_FIELD, 0, 0, p_findings, p_qids))

    # --- Submit gates ---
    blockers: List[str] = []
    submit_allowed = True

    if total < 70:
        submit_allowed = False
        blockers.append("Toplam skor 70'in altında.")

    if p_blockers:
        submit_allowed = False
        blockers.extend(p_blockers)

    return ScoreResult(
        total_score=total,
        max_total=max_total,
        field_scores=field_scores,
        submit_allowed=submit_allowed,
        submit_blockers=blockers,
    )

# -------------------------------------------------
# 8) Helpers: weak fields + question resolver
# -------------------------------------------------

def get_weak_fields(result: ScoreResult, ratio: float = 0.7) -> List[str]:
    """
    Weak fields are evaluated for BRD fields only (0-100 total).
    Privacy is handled as a mandatory question, not scored.
    """
    out: List[str] = []
    for fs in result.field_scores:
        if fs.field in FIELD_MAX:
            if fs.score < fs.max_score * ratio:
                out.append(fs.field)
    return out

def resolve_questions(qids: List[str]) -> List[str]:
    return [QUESTIONS_TR.get(q, q) for q in qids]


def _looks_like_yes(text: str) -> bool:
    low = _s(text).lower()

    no_markers = ["hayır", "hayir", "yok", "no", "none", "içermiyor", "icermiyor", "not in scope"]
    if any(n in low for n in no_markers):
        return False

    strong_yes = ["evet", "var", "yes", "in scope", "kapsamında", "kapsaminda"]
    pii_terms = ["pii", "kişisel veri", "kisisel veri", "personal data", "kvkk", "gdpr", "msisdn", "telefon", "email", "e-posta", "tc", "kimlik", "adres"]

    # güçlü yes varsa True
    if any(y in low for y in strong_yes):
        return True

    # sadece PII term geçti diye True deme; kullanıcı net "var" demediyse false
    return False

