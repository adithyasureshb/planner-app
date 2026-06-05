from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Goal(Base):
    __tablename__ = "goals"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    subject = Column(String)
    target_date = Column(String)
    hours_per_day = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class StudySession(Base):
    __tablename__ = "study_sessions"
    id = Column(Integer, primary_key=True)
    goal_id = Column(Integer)
    topic = Column(String)
    day_label = Column(String)
    duration_minutes = Column(Integer)
    completed = Column(Boolean, default=False)