from __future__ import annotations
from typing import List, Tuple, Optional

from app.schemas.insights import Signals, UserState, InsightCard, Action
from app.services.insights import signals


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _goal_lower(signals: Signals) -> str:
    return (signals.goal_name or "").lower()


def _has_rir(signals: Signals) -> bool:
    # If avg_rir is None, we effectively have no RIR data in last 7d
    return signals.avg_rir_last_7d is not None and signals.hard_sets_rate_7d is not None

def recommend_deload_percentage(signals: Signals) -> int:
    """
    Returns an integer % for volume reduction.
    Uses fatigue trend + ACWR + hard-set rate (if available).
    """
    pct = 10

    # Workload spike / high recent increase
    if signals.fatigue_trend_14d > 0.60:
        pct += 10
    elif signals.fatigue_trend_14d > 0.25:
        pct += 5

    # ACWR is "acute vs average chronic week" in your updated version
    if signals.acwr is not None:
        if signals.acwr > 1.50:
            pct += 10
        elif signals.acwr > 1.25:
            pct += 5

    # Lots of near-failure sets adds recovery cost
    if signals.hard_sets_rate_7d is not None:
        if signals.hard_sets_rate_7d >= 0.45:
            pct += 5
        elif signals.hard_sets_rate_7d >= 0.35:
            pct += 3

    # Clamp to sane bounds
    if pct < 10:
        pct = 10
    if pct > 35:
        pct = 35

    return int(pct)

def goal_params(goal_name: str | None) -> dict:
    g = (goal_name or "").lower()

    # defaults (general fitness)
    params = {
        "fatigue_trend_elevated": 0.25,
        "fatigue_trend_spike": 0.60,
        "acwr_elevated": 1.30,
        "acwr_spike": 1.55,
        "hard_sets_high": 0.40,
        "avg_rir_too_easy": 3.25,
        "prs_required": True,   # whether "stalling" should consider PR absence strongly
    }

    if "strength" in g:
        params.update({
            "fatigue_trend_elevated": 0.20,
            "fatigue_trend_spike": 0.50,
            "acwr_elevated": 1.25,
            "acwr_spike": 1.45,
            "hard_sets_high": 0.35,
            "avg_rir_too_easy": 3.0,
            "prs_required": True,
        })
    elif "hypertrophy" in g:
        params.update({
            "fatigue_trend_elevated": 0.30,
            "fatigue_trend_spike": 0.70,
            "acwr_elevated": 1.35,
            "acwr_spike": 1.65,
            "hard_sets_high": 0.45,
            "avg_rir_too_easy": 3.25,
            "prs_required": True,
        })
    elif "fat loss" in g:
        params.update({
            "fatigue_trend_elevated": 0.35,
            "fatigue_trend_spike": 0.80,
            "acwr_elevated": 1.40,
            "acwr_spike": 1.75,
            "hard_sets_high": 0.45,
            "avg_rir_too_easy": 3.5,
            "prs_required": False,
        })
    elif "endurance" in g:
        params.update({
            "fatigue_trend_elevated": 0.40,
            "fatigue_trend_spike": 0.85,
            "acwr_elevated": 1.45,
            "acwr_spike": 1.80,
            "hard_sets_high": 0.50,
            "avg_rir_too_easy": 3.75,
            "prs_required": False,
        })
    elif "athletic" in g:
        params.update({
            "fatigue_trend_elevated": 0.25,
            "fatigue_trend_spike": 0.60,
            "acwr_elevated": 1.30,
            "acwr_spike": 1.55,
            "hard_sets_high": 0.40,
            "avg_rir_too_easy": 3.25,
            "prs_required": True,
        })

    return params




def classify(signals: Signals) -> Tuple[UserState, List[InsightCard]]:
    goal = _goal_lower(signals)

    # --- Derived flags ---
    acwr = signals.acwr
    fatigue_trend = signals.fatigue_trend_14d

    # "fatigue elevated" = either acute above baseline or sharp recent increase
    fatigue_elevated = (acwr is not None and acwr > 1.25) or (fatigue_trend > 0.25)
    fatigue_spike = (acwr is not None and acwr > 1.5) or (fatigue_trend > 0.6)

    prs_recent = signals.prs_last_21d >= 1
    p = goal_params(signals.goal_name)
    
    # RIR-derived
    has_rir = _has_rir(signals)
    avg_rir = signals.avg_rir_last_7d
    hard_rate = signals.hard_sets_rate_7d  # fraction RIR<=1

    fatigue_elevated = ((signals.acwr is not None and signals.acwr > p["acwr_elevated"])
                        or (signals.fatigue_trend_14d > p["fatigue_trend_elevated"]))

    fatigue_spike = ((signals.acwr is not None and signals.acwr > p["acwr_spike"])
                    or (signals.fatigue_trend_14d > p["fatigue_trend_spike"]))

    too_many_hard_sets = (has_rir and hard_rate is not None and hard_rate >= p["hard_sets_high"])
    not_training_hard = (has_rir and avg_rir is not None and avg_rir >= p["avg_rir_too_easy"])

    stalling = (signals.prs_last_21d == 0) if p["prs_required"] else False


    adherence_ratio = signals.adherence_ratio_30d
    adherence_low = (adherence_ratio is not None and adherence_ratio < 0.7)
    adherence_high = (adherence_ratio is not None and adherence_ratio > 1.15)
    
    # --- Candidate evaluation (simple scoring) ---
    candidates: List[tuple[str, float, List[str], List[InsightCard]]] = []
    
    # 0) No recent training data
    if signals.workouts_last_30d == 0:
        state = UserState(
            id="no_recent_data",
            confidence=0.95,
            reasons=["No workouts logged in the last 30 days."],
        )

        cards = [
            InsightCard(
                id="no_data",
                title="No recent training data",
                severity="warning",
                metrics={
                    "workouts_last_30d": signals.workouts_last_30d
                },
                evidence=["There are no workouts recorded in the last 30 days."],
                actions=[
                    Action(
                        type="resume_training",
                        label="Start with 2-3 light sessions this week to rebuild consistency",
                        target="overall",
                        params={"recommended_sessions": 3, "intensity": "moderate"}
                    ),
                    Action(
                        type="baseline_week",
                        label="Use this week as a baseline to re-establish training capacity",
                        target="overall",
                        params={}
                    ),
                ],
            )
        ]
        return state, cards # short-circuit other rules since we have no data to apply them to
    
    # Low but non-zero exposure
    if (
        signals.workouts_last_30d > 0
        and signals.adherence_ratio_30d is not None
        and signals.adherence_ratio_30d < 0.5
    ):
        state = UserState(
            id="low_training_exposure",
            confidence=0.85,
            reasons=["Training frequency is very low relative to target."],
        )

        cards = [
            InsightCard(
                id="low_exposure",
                title="Training frequency is too low for consistent progress",
                severity="warning",
                metrics={
                    "workouts_last_30d": signals.workouts_last_30d,
                    "adherence_ratio_30d": signals.adherence_ratio_30d,
                    "target_days_per_week": signals.target_days_per_week,
                },
                evidence=[
                    "Progress requires consistent stimulus; current frequency is below effective levels."
                ],
                actions=[
                    Action(
                        type="increase_frequency",
                        label="Increase to at least 2-3 sessions per week",
                        target="overall",
                        params={"recommended_sessions": 3},
                    ),
                    Action(
                        type="short_sessions",
                        label="Keep sessions short (30-45 minutes) to build momentum",
                        target="overall",
                        params={},
                    ),
                ],
            )
        ]

        return state, cards


    # 1) Inconsistent adherence
    if adherence_low:
        score = _clamp01(0.75 + (0.7 - float(adherence_ratio or 0.0)))
        reasons = [f"Adherence ratio is {adherence_ratio:.2f}, below target pace."]
        cards = [
            InsightCard(
                id="adherence_drop",
                title="Consistency is the main limiter right now",
                severity="warning",
                metrics={
                    "workouts_last_30d": signals.workouts_last_30d,
                    "target_days_per_week": signals.target_days_per_week,
                    "adherence_ratio_30d": adherence_ratio,
                },
                evidence=["Workout frequency is below your target pace over the last 30 days."],
                actions=[
                    Action(type="plan_simplify", label="Use a minimum plan (2 sessions) this week"),
                    Action(type="session_short", label="Aim for 35-45 minute sessions"),
                ],
            )
        ]
        candidates.append(("inconsistent_adherence", score, reasons, cards))

    # 2) Underrecovered: too many hard sets
    # Only meaningful if we have RIR and fatigue is elevated
    if has_rir and too_many_hard_sets and fatigue_elevated:
        score = 0.78
        if fatigue_spike:
            score += 0.10
        reasons = [
            f"Hard set rate is {hard_rate:.2f} (RIR<=1), which is high.",
            "Fatigue is elevated based on workload trend/baseline.",
        ]
        cards = [
            InsightCard(
                id="too_many_hard_sets",
                title="Too many hard sets while fatigue is rising",
                severity="warning",
                metrics={
                    "hard_sets_rate_7d": hard_rate,
                    "avg_rir_last_7d": avg_rir,
                    "acwr": acwr,
                    "fatigue_trend_14d": fatigue_trend,
                },
                evidence=[
                    "A large share of your sets are very close to failure while workload is rising."
                ],
                actions=[
                    Action(type="cap_failure_sets", label="Cap RIR<=1 sets to ~20-25% of total sets this week"),
                    Action(type="target_rir", label="Aim RIR 2-3 on compounds; save RIR 0-1 for 1-2 isolation moves"),
                    Action(type="deload_volume", label="If joints/sleep feel off: reduce sets by ~15-25% for 1 week"),
                ],
            )
        ]
        candidates.append(("underrecovered_too_many_hard_sets", _clamp01(score), reasons, cards))

    # 3) Fatigued and stalling
    if fatigue_elevated and stalling:
        score = 0.75
        if fatigue_spike:
            score += 0.10
        reasons = ["Fatigue is elevated and PR signals are absent recently."]
        actions: List[Action] = [Action(type="deload_volume", label="Reduce total sets by ~20-30% for 1 week")]

        if "strength" in goal:
            actions.insert(0, Action(type="rep_range_shift", label="Reduce reps, keep load intent (e.g., 4x8 → 5x4)"))
        elif "fat" in goal:
            actions.insert(0, Action(type="keep_consistent", label="Keep training consistent; avoid big workload spikes"))
        else:
            actions.insert(0, Action(type="keep_load_reduce_sets", label="Keep load similar; reduce sets on big lifts"))

        cards = [
            InsightCard(
                id="fatigue_stall",
                title="Fatigue is up and progress has stalled",
                severity="warning",
                metrics={"acwr": acwr, "fatigue_trend_14d": fatigue_trend, "prs_last_21d": signals.prs_last_21d},
                evidence=["Workload is elevated relative to baseline and performance isn't moving up."],
                actions=actions,
            )
        ]
        candidates.append(("fatigued_and_stalling", _clamp01(score), reasons, cards))

    # 4) Fatigued but progressing
    if fatigue_elevated and prs_recent:
        score = 0.62
        if fatigue_spike:
            score += 0.08
        reasons = ["Workload is elevated but PR signals are present."]
        deload_pct = recommend_deload_percentage(signals)

        actions = [
            Action(
                type="deload_volume",
                label=f"Reduce total sets by {deload_pct}% for 7 days",
                target="overall",
                params={
                    "percentage": deload_pct,
                    "duration_days": 7,
                    "strategy": "volume_only",
                },
            ),
            Action(
                type="target_rir",
                label="Aim for RIR 2-3 on most sets this week; save RIR 0-1 for 1-2 sets",
                target="overall",
                params={"recommended_rir_min": 2, "recommended_rir_max": 3, "max_hard_set_share": 0.25},
            ),
        ]

        # If adherence is very high + fatigue rising, suggest pulling back slightly
        if adherence_high and fatigue_trend > 0.25:
            actions.insert(0, Action(type="add_rest", label="Consider 1 fewer session this week to stabilise fatigue"))

        cards = [
            InsightCard(
                id="fatigue_progress",
                title="Progressing, but fatigue is climbing",
                severity="info",
                metrics={"acwr": acwr, "fatigue_trend_14d": fatigue_trend, "prs_last_21d": signals.prs_last_21d},
                evidence=["You're improving, but workload is trending up—manage recovery to keep it sustainable."],
                actions=actions,
            )
        ]
        candidates.append(("fatigued_but_progressing", _clamp01(score), reasons, cards))

    # 5) Underloaded / not training hard (only if RIR data exists and fatigue is low-ish)
    if has_rir and not_training_hard and (not fatigue_elevated) and stalling:
        score = 0.72
        reasons = [f"Avg RIR is {avg_rir:.2f}, suggesting sets are not close enough to failure for progress."]
        cards = [
            InsightCard(
                id="underloaded",
                title="Low fatigue + no progress: you may be underloading",
                severity="warning",
                metrics={"avg_rir_last_7d": avg_rir, "hard_sets_rate_7d": hard_rate, "prs_last_21d": signals.prs_last_21d},
                evidence=["Your recent sets look relatively easy and there aren't recent PR signals."],
                actions=[
                    Action(type="increase_intensity", label="Add load or reps next session (aim RIR 1-2 on top sets)"),
                    Action(type="top_set", label="Add 1 top set on compounds, then 1-2 backoff sets"),
                ],
            )
        ]
        candidates.append(("underloaded_not_training_hard", _clamp01(score), reasons, cards))

    # --- Pick best candidate or fallback ---
    if candidates:
        best = max(candidates, key=lambda x: x[1])
        state_id, score, reasons, cards = best
        return UserState(id=state_id, confidence=score, reasons=reasons), cards

    # Fallback: on track
    state = UserState(id="on_track", confidence=0.6, reasons=["No major risk signals detected."])
    cards = [
        InsightCard(
            id="on_track",
            title="You're on track",
            severity="success",
            metrics={"acwr": acwr, "prs_last_21d": signals.prs_last_21d},
            evidence=["Workload and performance look stable."],
            actions=[
                Action(type="micro_progression", label="Aim for a small progression next session (+1 rep or +1.25-2.5kg)")
            ],
        )
    ]
    return state, cards
