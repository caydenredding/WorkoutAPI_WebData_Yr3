# Gym API – Workout Tracking and Training Insights

A RESTful API for logging workouts, tracking training progress, and generating analytics and insights from workout history.

This project was developed as part of the **COMP3011 – Web Services and Web Data** coursework at the University of Leeds.

The API allows users to:

- Create and manage workout sessions
- Log exercises and sets with weights, reps, and RIR (Reps in Reserve)
- Track body weight over time
- Browse a catalog of exercises, muscles, equipment, and goals
- Generate training analytics and insight signals

The system demonstrates modern API design practices including authentication, structured data modelling, analytics endpoints, and developer documentation.

---

# Architecture Overview

The API follows a layered architecture:

Client (curl / Postman / UI)  
↓  
FastAPI Routers  
↓  
Service Layer (analytics + insights)  
↓  
SQLAlchemy ORM  
↓  
SQL Database  

Key components:

- **FastAPI** for building HTTP endpoints
- **SQLAlchemy** for ORM database interaction
- **Pydantic** for request/response validation
- **JWT Authentication** for secure user access
- **PostgreSQL** for persistent storage

---

# Features

## Core CRUD Functionality

The API supports full CRUD operations for the following entities:

- Users
- Workouts
- Exercise Logs
- Sets
- Weigh-ins

## Reference Catalog

Read-only endpoints are provided for reference data:

- Exercises
- Muscles
- Equipment
- Goals

These catalog endpoints allow the frontend or client applications to discover supported exercises and related metadata.

## Analytics

Several endpoints compute analytics from training history including:

- Weekly workout streaks
- Workouts completed within a time window
- Maximum set volume for each exercise
- Estimated one-repetition maximum (1RM)

## Insight Engine

Higher-level endpoints generate signals and insights derived from user training behaviour including:

- Acute vs chronic workload ratio (ACWR)
- Fatigue trends
- Training adherence to weekly targets
- Progression signals

---

# API Documentation

Full API documentation is included in the repository.

docs/Gym_API_Documentation.pdf

The documentation includes:

- Endpoint descriptions
- Request and response examples
- Authentication details
- Error responses
- Example workflows

When the API is running locally, interactive documentation is also available at:

http://127.0.0.1:8000/docs  
http://127.0.0.1:8000/redoc  

---

# Setup Instructions

## 1. Clone the Repository

git clone https://github.com/YOUR_USERNAME/gym-api.git  
cd gym-api  

---

## 2. Create a Virtual Environment

python -m venv venv

Activate the environment.

Mac / Linux:

source venv/bin/activate

Windows:

venv\Scripts\activate

---

## 3. Install Dependencies

pip install -r requirements.txt

Key dependencies include:

- fastapi
- uvicorn
- sqlalchemy
- pydantic
- python-jose
- passlib[bcrypt]

---

## 4. Configure Environment Variables

Create a `.env` file in the project root.

Example configuration:

DATABASE_URL=sqlite:///./gym.db  
JWT_SECRET_KEY=your_secret_key  
API_KEY=example_key  

---

## 5. Seed Reference Data (if applicable)

Example scripts:

python -m app.seed_goals.py  
python -m app.seed_exercises.py  
python -m app.test_seeds.seed_all.py

These scripts populate the database with reference data such as exercises, muscles, equipment, and goals.

---

## 6. Start the API Server

uvicorn app.main:app --reload

The API will be available at:

http://127.0.0.1:8000

---

# Example Requests

Create a workout:

POST /me/workouts

{
  "date": "2026-03-05"
}

---

Log a set:

POST /me/exercise-logs/{exercise_log_id}/sets

{
  "reps": 8,
  "weight": 80,
  "rir": 2
}

---

Fetch exercise analytics:

GET /me/analytics/exercises/best-1rm

---

# Authentication

Protected endpoints require a JWT token.

Authorization header:

Authorization: Bearer <access_token>

Tokens are obtained via:

POST /auth/register  
POST /auth/login  

---

# Project Structure

Example repository layout:

gym-api/

app/  
├── routers/  
├── services/  
├── models/  
├── schemas/  
└── main.py  

seed_scripts/  

docs/  
└── Gym_API_Documentation.pdf  

requirements.txt  
README.md  

---

# Testing

Endpoints can be tested using:

- Swagger UI (/docs)
- Postman
- curl

Example:

curl http://127.0.0.1:8000/health

---

# Technologies Used

- Python
- FastAPI
- SQLAlchemy
- Pydantic
- JWT Authentication
- PostgreSQL

---

# Coursework Context

This project was developed for:

COMP3011 – Web Services and Web Data  
University of Leeds

The coursework required the design and implementation of a data-driven web API with database integration, documentation, and justification of technical design choices.

---

# Author

Cayden Redding  
University of Leeds – Computer Science
