# 🧠 AI Features Implementation Plan

## 🎯 Objective

Add:

- AI-based **Workout Plan Generation**
- AI-based **Weekly Training Summary Generation**
- Persistent storage for both
- Clean modular architecture matching existing router structure

---

# 🏗 Phase 0 — Architecture & Setup

## Folder Structure

- [x] Create `app/routers/ai/`
- [x] Create `app/services/ai/`
- [x] Add AI router group in `main.py`
- [x] Confirm consistent imports (`from app.routers...`)
---

# 🗄 Phase 1 — Database Changes

## Reset Database (if required)

- [x] Delete existing SQLite DB file
- [x] Recreate tables using `Base.metadata.create_all()`
- [x] Confirm schema is clean

## Add New Models

### WorkoutPlan

- [x] `id`
- [x] `user_id`
- [x] `created_at`
- [x] `days_per_week`
- [x] `goal`
- [x] `plan_json` (JSON or Text)
- [x] `plan_text` (optional)
- [x] `is_active` (optional)

### WeeklySummary

- [x] `id`
- [x] `user_id`
- [x] `week_start`
- [x] `week_end`
- [x] `created_at`
- [x] `facts_json`
- [x] `summary_text`

---

# 📊 Phase 2 — Deterministic Weekly Facts Engine

## Create `summary_facts.py`

- [ ] Compute sessions in period
- [ ] Compute unique training days
- [ ] Compute total sets
- [ ] Compute total volume
- [ ] Detect PRs (new best e1RM or max set volume)
- [ ] Detect improvements vs previous week
- [ ] Include weekly streak data
- [ ] Include last 7-day gap data

## Add Debug Endpoint

- [ ] `GET /ai/users/{user_id}/summaries/weekly/facts`
- [ ] Return raw computed JSON
- [ ] Validate correctness before adding AI

---

# ✍️ Phase 3 — Weekly Summary (LLM Integration)

## LLM Infrastructure

- [ ] Create `llm_client.py`
- [ ] Add API key via environment variable
- [ ] Implement `generate_weekly_summary(facts, tone)`

## Prompt Engineering

- [ ] Create structured weekly summary prompt
- [ ] Ensure AI only uses provided facts
- [ ] Add tone parameter (coach / neutral / motivational)

## Weekly Summary Endpoint

- [ ] `POST /ai/users/{user_id}/summaries/weekly`
- [ ] Compute facts
- [ ] Generate AI summary
- [ ] Store in `WeeklySummary`
- [ ] Return response

## Retrieval

- [ ] `GET /ai/users/{user_id}/summaries`
- [ ] `GET /ai/users/{user_id}/summaries/latest`

---

# 🏋️ Phase 4 — Deterministic Workout Plan Builder

## Create `plan_builder.py`

### Core Plan Logic

- [ ] Determine split from `days_per_week`
- [ ] Select exercises from catalog
- [ ] Bias toward previously used exercises
- [ ] Avoid unused exercises (v1)
- [ ] Add progression model (double progression)
- [ ] Add rest times and RIR targets
- [ ] Return structured JSON plan

### Plan Templates

- [ ] 2 days/week → Full Body A/B
- [ ] 3 days/week → Full Body A/B/C or Push/Pull/Legs
- [ ] 4 days/week → Upper/Lower
- [ ] 5–6 days/week → PPL variant

---

# 🧾 Phase 5 — Workout Plan Endpoints

## Plan Generation

- [ ] `POST /ai/users/{user_id}/plans/generate`
- [ ] Accept:
  - [ ] days_per_week
  - [ ] goal
  - [ ] optional constraints
- [ ] Generate deterministic JSON plan
- [ ] Optionally generate AI coaching notes
- [ ] Store in `WorkoutPlan`
- [ ] Return plan

## Plan Retrieval

- [ ] `GET /ai/users/{user_id}/plans`
- [ ] `GET /ai/users/{user_id}/plans/{plan_id}`

## Optional

- [ ] Add `activate plan` endpoint
- [ ] Ensure only one active plan per user

---

# 🔄 Phase 6 — Optional Plan-to-Workout Integration

- [ ] Allow user to start workout from plan
- [ ] Auto-create `WorkoutLog`
- [ ] Auto-create `ExerciseLog`
- [ ] Track adherence

---

# 🧠 AI Safety & Validation

- [ ] AI never computes metrics
- [ ] AI only formats provided data
- [ ] Validate structured outputs
- [ ] Add fallback if AI fails
- [ ] Avoid medical / injury advice

---

# 🚀 Suggested Implementation Timeline

## Day 1
- [ ] Add DB models
- [ ] Build weekly facts engine
- [ ] Add debug endpoint

## Day 2
- [ ] Add LLM weekly summary
- [ ] Add summary storage + retrieval

## Day 3
- [ ] Build deterministic plan builder
- [ ] Add plan generation endpoint

## Day 4
- [ ] Add plan retrieval
- [ ] Add plan activation (optional)

---

# 🔮 Future Enhancements

- [ ] Monthly performance summaries
- [ ] Auto weight progression updates
- [ ] Muscle imbalance detection
- [ ] Deload recommendations
- [ ] Adaptive programming
