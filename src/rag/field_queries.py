from __future__ import annotations

# Field -> retrieval query expansion keywords
# Goal: increase recall from Confluence by using domain + field intent keywords.
# If a field is not here, retriever falls back to the field name itself.

FIELD_TO_QUERY = {
    # Core context
    "Background": (
        "background problem statement current situation pain point context "
        "legacy existing system integration sync entegrasyon manuel otomatik "
        "root cause constraint dependency assumption scope"
    ),
    "Problem Statement": (
        "problem statement pain point issue current situation root cause "
        "customer complaint incident defect limitation"
    ),
    "Objective": (
        "objective goal purpose aim business objective hedef amaç "
        "what we want to achieve"
    ),
    "Scope": (
        "scope in scope out of scope kapsam dahil haric "
        "boundaries assumptions dependencies"
    ),

    # Users / customers
    "Target Customer Group": (
        "customer segment target group persona prepaid postpaid SME consumer "
        "faturalı ön ödemeli kurumsal bireysel eligibility"
    ),
    "Stakeholders": (
        "stakeholder business owner product owner sponsor approval "
        "IT architecture security legal compliance"
    ),

    # Solution / journey
    "Impacted Channels": (
        "channels impacted channels app web call center store dealer "
        "self service mobile application portal API backend integration"
    ),
    "Impacted Journey": (
        "journey name customer journey flow process lifecycle activation "
        "cancellation upgrade downgrade onboarding"
    ),
    "Journeys Description": (
        "as-is to-be before after flow diagram step by step "
        "edge case validation error handling retry timeout "
        "batch real-time sync integration"
    ),
    "As-Is": (
        "as-is current process existing workflow today "
        "manual steps bottleneck pain points"
    ),
    "To-Be": (
        "to-be future state target process new workflow "
        "automation proposed solution"
    ),

    # Requirements
    "Functional Requirements": (
        "functional requirements user story acceptance criteria "
        "business rules validation rules feature behavior"
    ),
    "Non-Functional Requirements": (
        "non functional requirements NFR performance scalability availability "
        "security latency throughput capacity resiliency monitoring logging"
    ),
    "Data Requirements": (
        "data requirements data sources fields mapping schema "
        "PII GDPR KVKK retention encryption data quality"
    ),
    "API / Integration": (
        "API integration interface contract endpoint payload "
        "Kenan CCS VIBE CRM billing charging provisioning "
        "SOAP REST event streaming kafka"
    ),

    # Reporting / analytics
    "Reports Needed": (
        "reports dashboard metrics reporting requirements analytics BI "
        "business intelligence performance monitoring KPI"
    ),

    # Volume / traffic
    "Traffic Forecast": (
        "traffic forecast volume daily transactions growth estimate "
        "API calls load capacity planning peak concurrent users"
    ),

    # Success / impact
    "Expected Results": (
        "expected results success metrics KPI target measurable "
        "revenue gelir incremental conversion rate financial impact "
        "EBITDA cost saving churn reduction"
    ),
    "Benefits": (
        "benefits value impact cost saving revenue increase efficiency "
        "customer satisfaction NPS operational improvement"
    ),

    # Risks / dependencies / timeline
    "Risks": (
        "risks risk assessment mitigation dependency blocker "
        "security risk compliance risk operational risk"
    ),
    "Dependencies": (
        "dependencies prerequisite upstream downstream "
        "system dependency vendor dependency"
    ),
    "Timeline": (
        "timeline milestone delivery plan release date "
        "UAT SIT production cutover rollout"
    ),

    # Testing / rollout
    "Testing": (
        "testing strategy SIT UAT regression test cases "
        "test data execution evidence"
    ),
    "Rollout": (
        "rollout deployment cutover migration rollback plan "
        "feature toggle phased rollout communication"
    ),
}

# Optional: generic fallback enrichment if you want to use it in retriever
GENERIC_RAG_HINT = (
    "Vodafone telecom billing charging CRM customer journey "
    "integration API requirement"
)
