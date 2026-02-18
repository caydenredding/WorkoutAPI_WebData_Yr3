from datetime import date
from sqlalchemy.orm import Session

from app.schemas.insights import Signals, SignalsResponse, InsightsResponse
from app.services.insights.signals import build_signals
from app.services.insights.state_machine import classify


def get_signals_response(db: Session, user_id: int, as_of: date) -> SignalsResponse:
    raw = build_signals(db, user_id, as_of)
    signals = Signals(**raw)
    return SignalsResponse(user_id=user_id, signals=signals)


def get_insights_response(db: Session, user_id: int, as_of: date) -> InsightsResponse:
    raw = build_signals(db, user_id, as_of)
    signals = Signals(**raw)

    state, cards = classify(signals)

    return InsightsResponse(
        user_id=user_id,
        signals=signals,
        state=state,
        cards=cards,
    )
