from sqlalchemy import Column, Integer, String
from database import Base

# Table of all exercises
class Exercise(Base):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    # Can be updated in future to be many-to-many table for muscle groups
    primary_muscle = Column(String)
    secondary_muscle = Column(String)
    equipment = Column(String)