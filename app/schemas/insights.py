from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ----------------------------
# Shared types
# ----------------------------

Severity = Literal["info", "success", "warning"]


class Action(BaseModel):
    type: str
    label: str
    target: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)


class InsightCard(BaseModel):
    id: str
    title: str
    severity: Severity
    metrics: Dict[str, Any] = Field(default_factory=dict)
    evidence: List[str] = Field(default_factory=list)
    actions: List[Action] = Field(default_factory=list)


class UserState(BaseModel):
    id: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: List[str] = Field(default_factory=list)


# ----------------------------
# Signals Model
# ----------------------------

class Signals(BaseModel):
    # Date range for query
    date_from: date
    date_to: date

    # Workload / Fatigue
    session_load_total: float
    acute_load_7d: float
    chronic_load_28d: float
    acwr: Optional[float] = None
    fatigue_trend_14d: float

    # Attendance / Adherence
    workouts_in_range: int
    workouts_last_7d: int
    workouts_last_30d: int
    adherence_ratio_30d: Optional[float] = None
    target_days_per_week: int

    # Effort
    avg_rir_last_7d: Optional[float] = None
    hard_sets_rate_7d: Optional[float] = None

    # Performance
    prs_last_21d: int
    last_pr_date: Optional[date] = None

    # Context
    goal_name: Optional[str] = None


# ----------------------------
# API Response Wrappers
# ----------------------------

class SignalsResponse(BaseModel):
    user_id: int
    signals: Signals


class InsightsResponse(BaseModel):
    user_id: int
    signals: Signals
    state: UserState
    cards: List[InsightCard]
