from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# user: workout_user
# password: password
DB_URL = "postgresql+psycopg2://workout_user:password@localhost:5432/workout_db"

# Connect to Postgres
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()