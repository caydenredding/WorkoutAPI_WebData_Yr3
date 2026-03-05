from __future__ import annotations

from typing import List, Tuple

from app.schemas.insights import Signals, UserState, InsightCard, Action


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _goal_lower(signals: Signals) -> str:
    return (signals.goal_name or "").lower()


def _has_rir(signals: Signals) -> bool:
    return (
        signals.avg_rir_last_7d is not None
        and signals.hard_sets_rate_7d is not None
    )


def recommend_deload_percentage(signals: Signals) -> int:
    """
    Returns an integer % for volume reduction.
    Uses fatigue trend + ACWR + hard-set rate (if available).
    """
    pct = 10

    if signals.fatigue_trend_14d > 0.60:
        pct += 10
    elif signals.fatigue_trend_14d > 0.25:
        pct += 5

    if signals.acwr is not None:
        if signals.acwr > 1.50:
            pct += 10
        elif signals.acwr > 1.25:
            pct += 5

    if signals.hard_sets_rate_7d is not None:
        if signals.hard_sets_rate_7d >= 0.45:
            pct += 5
        elif signals.hard_sets_rate_7d >= 0.35:
            pct += 3

    return int(max(10, min(35, pct)))


def goal_params(goal_name: str | None) -> dict:
    g = (goal_name or "").lower()

    params = {
        "fatigue_trend_elevated": 0.25,
        "fatigue_trend_spike": 0.60,
        "acwr_elevated": 1.30,
        "acwr_spike": 1.55,
        "hard_sets_high": 0.40,
        "avg_rir_too_easy": 3.25,
        "prs_required": True,
    }

    if "strength" in g:
        params.update(
            {
                "fatigue_trend_elevated": 0.20,
                "fatigue_trend_spike": 0.50,
                "acwr_elevated": 1.25,
                "acwr_spike": 1.45,
                "hard_sets_high": 0.35,
                "avg_rir_too_easy": 3.0,
                "prs_required": True,
            }
        )
    elif "hypertrophy" in g:
        params.update(
            {
                "fatigue_trend_elevated": 0.30,
                "fatigue_trend_spike": 0.70,
                "acwr_elevated": 1.35,
                "acwr_spike": 1.65,
                "hard_sets_high": 0.45,
                "avg_rir_too_easy": 3.25,
                "prs_required": True,
            }
        )
    elif "fat loss" in g:
        params.update(
            {
                "fatigue_trend_elevated": 0.35,
                "fatigue_trend_spike": 0.80,
                "acwr_elevated": 1.40,
                "acwr_spike": 1.75,
                "hard_sets_high": 0.45,
                "avg_rir_too_easy": 3.5,
                "prs_required": False,
            }
        )
    elif "endurance" in g:
        params.update(
            {
                "fatigue_trend_elevated": 0.40,
                "fatigue_trend_spike": 0.85,
                "acwr_elevated": 1.45,
                "acwr_spike": 1.80,
                "hard_sets_high": 0.50,
                "avg_rir_too_easy": 3.75,
                "prs_required": False,
            }
        )
    elif "athletic" in g:
        params.update(
            {
                "fatigue_trend_elevated": 0.25,
                "fatigue_trend_spike": 0.60,
                "acwr_elevated": 1.30,
                "acwr_spike": 1.55,
                "hard_sets_high": 0.40,
                "avg_rir_too_easy": 3.25,
                "prs_required": True,
            }
        )

    return params


def _make_adherence_card(signals: Signals) -> InsightCard:
    return InsightCard(
        id="adherence_drop",
        title="Consistency is the main limiter right now",
        severity="warning",
        metrics={
            "workouts_last_30d": signals.workouts_last_30d,
            "workouts_last_7d": getattr(signals, "workouts_last_7d", None),
            "target_days_per_week": signals.target_days_per_week,
            "adherence_ratio_30d": signals.adherence_ratio_30d,
        },
        evidence=["Workout frequency is below your target pace over the last 30 days."],
        actions=[
            Action(type="plan_simplify", label="Use a minimum plan (2 sessions) this week"),
            Action(type="session_short", label="Aim for 35-45 minute sessions"),
        ],
    )


def _cap_confidence_for_missing_signals(base: float, *, has_rir: bool, has_acwr: bool) -> float:
    """
    Small coursework-friendly realism: if key signals are missing, cap confidence.
    """
    cap = 1.0
    if not has_acwr:
        cap = min(cap, 0.80)
    if not has_rir:
        cap = min(cap, 0.85)
    return min(base, cap)


def classify(signals: Signals) -> Tuple[UserState, List[InsightCard]]:
    goal = _goal_lower(signals)
    p = goal_params(signals.goal_name)

    acwr = signals.acwr
    fatigue_trend = signals.fatigue_trend_14d
    has_acwr = acwr is not None

    has_rir = _has_rir(signals)
    avg_rir = signals.avg_rir_last_7d
    hard_rate = signals.hard_sets_rate_7d

    workouts_last_7d = getattr(signals, "workouts_last_7d", None)
    workouts_last_30d = signals.workouts_last_30d

    fatigue_elevated = (
        (acwr is not None and acwr > p["acwr_elevated"])
        or (fatigue_trend > p["fatigue_trend_elevated"])
    )
    fatigue_spike = (
        (acwr is not None and acwr > p["acwr_spike"])
        or (fatigue_trend > p["fatigue_trend_spike"])
    )

    too_many_hard_sets = has_rir and hard_rate is not None and hard_rate >= p["hard_sets_high"]
    not_training_hard = has_rir and avg_rir is not None and avg_rir >= p["avg_rir_too_easy"]

    prs_recent = signals.prs_last_21d >= 1
    stalling = (signals.prs_last_21d == 0) if p["prs_required"] else False

    adherence_ratio = signals.adherence_ratio_30d
    adherence_low = adherence_ratio is not None and adherence_ratio < 0.7
    adherence_high = adherence_ratio is not None and adherence_ratio > 1.15

    adherence_card: InsightCard | None = _make_adherence_card(signals) if adherence_low else None

    candidates: List[tuple[str, float, List[str], List[InsightCard]]] = []

    # -----------------------
    # 0) No recent training data (hard stop)
    # -----------------------
    if workouts_last_30d == 0:
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
                metrics={"workouts_last_30d": workouts_last_30d, "workouts_last_7d": workouts_last_7d},
                evidence=["There are no workouts recorded in the last 30 days."],
                actions=[
                    Action(
                        type="resume_training",
                        label="Start with 2-3 light sessions this week to rebuild consistency",
                        target="overall",
                        params={"recommended_sessions": 3, "intensity": "moderate"},
                    ),
                    Action(
                        type="baseline_week",
                        label="Use this week as a baseline to re-establish training capacity",
                        target="overall",
                        params={},
                    ),
                ],
            )
        ]
        return state, cards

    # -----------------------
    # 0.5) Recent drop-off (NEW)
    # some training exists in last 30d, but none in last 7d
    # -----------------------
    if workouts_last_7d is not None and workouts_last_7d == 0 and workouts_last_30d > 0:
        conf = _cap_confidence_for_missing_signals(0.86, has_rir=has_rir, has_acwr=has_acwr)
        state = UserState(
            id="recent_dropoff",
            confidence=conf,
            reasons=["No workouts logged in the last 7 days, despite some activity in the last 30 days."],
        )
        cards = [
            InsightCard(
                id="recent_dropoff",
                title="You’ve dropped off this week",
                severity="warning",
                metrics={
                    "workouts_last_7d": workouts_last_7d,
                    "workouts_last_30d": workouts_last_30d,
                    "adherence_ratio_30d": adherence_ratio,
                    "target_days_per_week": signals.target_days_per_week,
                },
                evidence=["A short break can quickly reduce momentum; the fastest win is restarting gently."],
                actions=[
                    Action(
                        type="resume_training",
                        label="Do 1 short session in the next 48 hours (30–45 min, easy/moderate effort)",
                        target="overall",
                        params={"recommended_sessions_next_7d": 2, "session_minutes": 40},
                    ),
                    Action(
                        type="keep_simple",
                        label="Repeat your last successful workout to rebuild momentum",
                        target="overall",
                        params={},
                    ),
                ],
            )
        ]
        if adherence_card is not None:
            cards.append(adherence_card)
        return state, cards

    # -----------------------
    # 0.6) Thin data / insufficient signal (NEW)
    # -----------------------
    if 0 < workouts_last_30d < 4:
        conf = _cap_confidence_for_missing_signals(0.84, has_rir=has_rir, has_acwr=has_acwr)
        state = UserState(
            id="insufficient_signal",
            confidence=conf,
            reasons=[f"Only {workouts_last_30d} workouts logged in the last 30 days; signals are noisy."],
        )
        cards = [
            InsightCard(
                id="thin_data",
                title="Not enough recent data for strong recommendations",
                severity="info",
                metrics={
                    "workouts_last_30d": workouts_last_30d,
                    "workouts_last_7d": workouts_last_7d,
                    "target_days_per_week": signals.target_days_per_week,
                    "adherence_ratio_30d": adherence_ratio,
                },
                evidence=["With only a few sessions logged, fatigue/progress signals can be unreliable."],
                actions=[
                    Action(
                        type="baseline_week",
                        label="Log 2–4 sessions over the next 7–10 days to establish a usable baseline",
                        target="overall",
                        params={"recommended_sessions_next_10d": 3},
                    ),
                    Action(
                        type="keep_simple",
                        label="Repeat the same core lifts so progress is measurable",
                        target="overall",
                        params={},
                    ),
                ],
            )
        ]
        if adherence_card is not None:
            cards.append(adherence_card)
        return state, cards

    # -----------------------
    # 0.7) Low training exposure (your short-circuit kept)
    # -----------------------
    if (
        workouts_last_30d > 0
        and adherence_ratio is not None
        and adherence_ratio < 0.5
    ):
        conf = _cap_confidence_for_missing_signals(0.85, has_rir=has_rir, has_acwr=has_acwr)
        state = UserState(
            id="low_training_exposure",
            confidence=conf,
            reasons=["Training frequency is very low relative to target."],
        )
        cards = [
            InsightCard(
                id="low_exposure",
                title="Training frequency is too low for consistent progress",
                severity="warning",
                metrics={
                    "workouts_last_30d": workouts_last_30d,
                    "workouts_last_7d": workouts_last_7d,
                    "adherence_ratio_30d": adherence_ratio,
                    "target_days_per_week": signals.target_days_per_week,
                },
                evidence=["Progress requires consistent stimulus; current frequency is below effective levels."],
                actions=[
                    Action(
                        type="increase_frequency",
                        label="Increase to at least 2–3 sessions per week",
                        target="overall",
                        params={"recommended_sessions": 3},
                    ),
                    Action(
                        type="short_sessions",
                        label="Keep sessions short (30–45 minutes) to build momentum",
                        target="overall",
                        params={},
                    ),
                ],
            )
        ]
        if adherence_card is not None:
            cards.append(adherence_card)
        return state, cards

    # -----------------------
    # 1) Inconsistent adherence (candidate)
    # -----------------------
    if adherence_low:
        score = _clamp01(0.75 + (0.7 - float(adherence_ratio or 0.0)))
        score = _cap_confidence_for_missing_signals(score, has_rir=has_rir, has_acwr=has_acwr)
        reasons = [f"Adherence ratio is {adherence_ratio:.2f}, below target pace."]
        candidates.append(("inconsistent_adherence", score, reasons, [adherence_card]))  # type: ignore[list-item]

    # -----------------------
    # 2) Underrecovered: too many hard sets + elevated fatigue
    # -----------------------
    if has_rir and too_many_hard_sets and fatigue_elevated:
        score = 0.78 + (0.10 if fatigue_spike else 0.0)
        score = _cap_confidence_for_missing_signals(score, has_rir=has_rir, has_acwr=has_acwr)
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
                evidence=["A large share of your sets are very close to failure while workload is rising."],
                actions=[
                    Action(type="cap_failure_sets", label="Cap RIR<=1 sets to ~20–25% of total sets this week"),
                    Action(type="target_rir", label="Aim RIR 2–3 on compounds; save RIR 0–1 for 1–2 isolation moves"),
                    Action(type="deload_volume", label="If joints/sleep feel off: reduce sets by ~15–25% for 1 week"),
                ],
            )
        ]
        candidates.append(("underrecovered_too_many_hard_sets", _clamp01(score), reasons, cards))

    # -----------------------
    # 3) Fatigued and stalling
    # -----------------------
    if fatigue_elevated and stalling:
        score = 0.75 + (0.10 if fatigue_spike else 0.0)
        score = _cap_confidence_for_missing_signals(score, has_rir=has_rir, has_acwr=has_acwr)
        reasons = ["Fatigue is elevated and PR signals are absent recently."]
        actions: List[Action] = [Action(type="deload_volume", label="Reduce total sets by ~20–30% for 1 week")]

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
                metrics={
                    "acwr": acwr,
                    "fatigue_trend_14d": fatigue_trend,
                    "prs_last_21d": signals.prs_last_21d,
                },
                evidence=["Workload is elevated relative to baseline and performance isn't moving up."],
                actions=actions,
            )
        ]
        candidates.append(("fatigued_and_stalling", _clamp01(score), reasons, cards))

    # -----------------------
    # 4) Fatigued but progressing
    # -----------------------
    if fatigue_elevated and prs_recent:
        score = 0.62 + (0.08 if fatigue_spike else 0.0)
        score = _cap_confidence_for_missing_signals(score, has_rir=has_rir, has_acwr=has_acwr)
        reasons = ["Workload is elevated but PR signals are present."]
        deload_pct = recommend_deload_percentage(signals)

        actions = [
            Action(
                type="deload_volume",
                label=f"Reduce total sets by {deload_pct}% for 7 days",
                target="overall",
                params={"percentage": deload_pct, "duration_days": 7, "strategy": "volume_only"},
            ),
            Action(
                type="target_rir",
                label="Aim for RIR 2–3 on most sets this week; save RIR 0–1 for 1–2 sets",
                target="overall",
                params={"recommended_rir_min": 2, "recommended_rir_max": 3, "max_hard_set_share": 0.25},
            ),
        ]

        if adherence_high and fatigue_trend > p["fatigue_trend_elevated"]:
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

    # -----------------------
    # 5) Underloaded / not training hard (requires RIR, low fatigue, stalling)
    # -----------------------
    if has_rir and not_training_hard and (not fatigue_elevated) and stalling:
        score = _cap_confidence_for_missing_signals(0.72, has_rir=has_rir, has_acwr=has_acwr)
        reasons = [f"Avg RIR is {avg_rir:.2f}, suggesting sets are not close enough to failure for progress."]
        cards = [
            InsightCard(
                id="underloaded",
                title="Low fatigue + no progress: you may be underloading",
                severity="warning",
                metrics={"avg_rir_last_7d": avg_rir, "hard_sets_rate_7d": hard_rate, "prs_last_21d": signals.prs_last_21d},
                evidence=["Your recent sets look relatively easy and there aren't recent PR signals."],
                actions=[
                    Action(type="increase_intensity", label="Add load or reps next session (aim RIR 1–2 on top sets)"),
                    Action(type="top_set", label="Add 1 top set on compounds, then 1–2 backoff sets"),
                ],
            )
        ]
        candidates.append(("underloaded_not_training_hard", _clamp01(score), reasons, cards))

    # -----------------------
    # Pick best candidate or fallback
    # -----------------------
    if candidates:
        best_state_id, best_score, best_reasons, best_cards = max(candidates, key=lambda x: x[1])

        # Sticky adherence card: append unless it already won
        if adherence_card is not None and best_state_id != "inconsistent_adherence":
            if not any(c.id == adherence_card.id for c in best_cards):
                best_cards = best_cards + [adherence_card]

        return UserState(id=best_state_id, confidence=best_score, reasons=best_reasons), best_cards

    # Fallback: on track
    conf = _cap_confidence_for_missing_signals(0.60, has_rir=has_rir, has_acwr=has_acwr)
    cards = [
        InsightCard(
            id="on_track",
            title="You're on track",
            severity="success",
            metrics={"acwr": acwr, "fatigue_trend_14d": fatigue_trend, "prs_last_21d": signals.prs_last_21d},
            evidence=["Workload and performance look stable."],
            actions=[Action(type="micro_progression", label="Aim for a small progression next session (+1 rep or +1.25–2.5kg)")],
        )
    ]

    if adherence_card is not None:
        cards.append(adherence_card)

    return UserState(id="on_track", confidence=conf, reasons=["No major risk signals detected."]), cards