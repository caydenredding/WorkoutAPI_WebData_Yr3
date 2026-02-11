from app.database import engine, Base
from app import models  # IMPORTANT: ensures all tables are registered on Base

def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✅ Dropped and recreated all tables.")

if __name__ == "__main__":
    reset_db()