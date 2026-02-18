from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.ai.llm_client import LLMClient
from app.services.ai.summary_facts import build_weekly_facts

router = APIRouter(tags=["ai"])

@router.get(
    "/users/{user_id}/summaries/weekly/facts",
    status_code=status.HTTP_200_OK,
)
def weekly_facts(
    user_id: int,
    date_from: date = Query(...),
    date_to: date = Query(...),
    num_prs: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    return build_weekly_facts(db, user_id, date_from, date_to, pr_count=num_prs)

Tone = Literal["friendly", "direct", "hype", "clinical"]


@router.get("/users/{user_id}/summaries/weekly/ai")
def weekly_ai_summary(
    user_id: int,
    date_from: date = Query(...),
    date_to: date = Query(...),
    tone: Tone = Query("friendly"),
    num_facts: int = Query(8, ge=1, le=30),
    include_facts: bool = Query(True),
    db: Session = Depends(get_db),
):
    # 1) Your existing facts generator (you said you're happy with its richness)
    facts = build_weekly_facts(db, user_id, date_from, date_to, pr_count=num_facts)

    # 2) LLM summary
    llm = LLMClient()
    summary = llm.generate_weekly_summary(facts=facts, tone=tone)

    # 3) Response
    payload = {
        "user_id": user_id,
        "date_from": str(date_from),
        "date_to": str(date_to),
        "tone": tone,
        "summary": summary,
    }
    if include_facts:
        payload["facts"] = facts

    return payload