
"""
SCORING ENGINE (Wizard / State Based)

- Uses field-based input (no BRD text parsing)
- Compatible with guided wizard + chatbot UI
- Returns weak fields + guided question IDs
- Token-safe (LLM not required here)

Author: Hackathon Team
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

# -------------------------------------------------
# 1) Fields & max scores
# -------------------------------------------------

FIELD_MAX = {
    "Background": 15,
    "Expected Results": 15,
    "Target Customer Group": 5,
    "Impacted Channels": 10,
    "Impacted Journey": 5,
    "Journeys Description": 40,
    "Reports Needed": 5,
    "Traffic Forecast": 5,
}

VAGUE_WORDS_TR = [
    "uygun", "mümkün", "hızlı", "asap", "optimum", "gerektiğinde", "user friendly",
    "makul", "iyileştir", "geliştir", "daha iyi", "kolay", "en kısa", "verimli"
]

# -------------------------------------------------
# 2) Guided Questions (ID-based, UI resolves text)
# -------------------------------------------------

QUESTIONS_TR = {
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

    "Q_PRIVACY_PROTECTION": "Kişisel veri nasıl korunacak?",
    "Q_PRIVACY_CLARIFY": "KVKK / data privacy önlemlerini netleştirir misiniz?",
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

def char_len(s: str) -> int:
    return len((s or "").strip())

def contains_any(text: str, words: List[str]) -> bool:
    t = (text or "").lower()
    return any(w.lower() in t for w in words)

# -------------------------------------------------
# 5) Field scorers
# -------------------------------------------------

def score_background(val: str):
    if char_len(val) == 0:
        return 0, ["Background alanı boş."], ["Q_BACKGROUND_EMPTY"]
    if char_len(val) < 50:
        return 5, ["Background çok kısa."], ["Q_BACKGROUND_MORE_DETAIL"]
    if contains_any(val, VAGUE_WORDS_TR):
        return 13, ["Belirsiz ifadeler var."], ["Q_BACKGROUND_MORE_SPECIFIC"]
    return 15, [], []

def score_expected_results(val: str):
    if char_len(val) == 0:
        return 0, ["Expected Results alanı boş."], ["Q_EXPECTED_RESULTS_EMPTY"]
    measurable = bool(re.search(r"(%|sn|dk|adet|oran|kpi)", val.lower()))
    if measurable:
        return 15, [], []
    return 10, ["Ölçülebilir hedef yok."], ["Q_EXPECTED_RESULTS_ADD_TARGET"]

def score_target_customer_group(val: str):
    if char_len(val) == 0:
        return 0, ["Target Customer Group boş."], ["Q_CUSTOMER_GROUP_EMPTY"]
    if "tüm" in val.lower():
        return 2, ["Müşteri grubu çok genel."], ["Q_CUSTOMER_GROUP_SPECIFY"]
    return 5, [], []

def score_impacted_channels(val: str):
    if char_len(val) == 0:
        return 0, ["Impacted Channels boş."], ["Q_CHANNELS_EMPTY"]
    if len(val.split()) < 3:
        return 5, ["Kanal detayları zayıf."], ["Q_CHANNELS_IMPACT_EXPLAIN"]
    return 10, [], []

def score_impacted_journey(val: str):
    if char_len(val) == 0:
        return 0, ["Impacted Journey boş."], ["Q_JOURNEY_EMPTY"]
    if any(x in val.lower() for x in ["yeni", "new", "mevcut", "existing"]):
        return 5, [], []
    return 3, ["Journey tipi net değil."], ["Q_JOURNEY_NEW_EXISTING"]

def score_journeys_description(val: str):
    if char_len(val) == 0:
        return 0, ["Journey Description boş."], ["Q_JDESC_EMPTY"]
    if char_len(val) < 120:
        return 20, ["Journey açıklaması zayıf."], ["Q_JDESC_BEFORE_AFTER"]
    if any(x in val.lower() for x in ["edge", "hata", "timeout", "error"]):
        return 40, [], []
    return 35, ["Edge-case eksik."], ["Q_JDESC_EDGE_CASE"]

def score_reports_needed(val: str):
    if char_len(val) == 0:
        return 0, ["Reports Needed boş."], ["Q_REPORTS_EMPTY"]
    if "yok" in val.lower():
        return 3, [], []
    return 5, [], []

def score_traffic_forecast(val: str):
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
# 6) Final score computation (STATE BASED)
# -------------------------------------------------

def compute_scores_from_fields(fields: Dict[str, str]) -> ScoreResult:
    total = 0
    max_total = sum(FIELD_MAX.values())
    field_scores = []

    for field, max_sc in FIELD_MAX.items():
        scorer = FIELD_SCORERS[field]
        val = fields.get(field, "")
        score, findings, qids = scorer(val)
        score = max(0, min(score, max_sc))
        total += score
        field_scores.append(FieldScore(field, score, max_sc, findings, qids))

    submit_allowed = total >= 70
    blockers = [] if submit_allowed else ["Toplam skor 70'in altında."]

    return ScoreResult(
        total_score=total,
        max_total=max_total,
        field_scores=field_scores,
        submit_allowed=submit_allowed,
        submit_blockers=blockers
    )

def get_weak_fields(result: ScoreResult, ratio: float = 0.7) -> List[str]:
    return [
        fs.field for fs in result.field_scores
        if fs.field in FIELD_MAX and fs.score < fs.max_score * ratio
    ]

def resolve_questions(qids: List[str]) -> List[str]:
    return [QUESTIONS_TR.get(q, q) for q in qids]
