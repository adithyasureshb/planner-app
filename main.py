from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import engine, get_db, Base
import models
from ai_planner import generate_study_plan

from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import datetime
import uuid

# =========================
# INIT
# =========================
Base.metadata.create_all(bind=engine)

app = FastAPI()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app.mount("/static", StaticFiles(directory="static"), name="static")

# =========================
# SESSION STORE (IMPORTANT FIX)
# =========================
session_store = {}


# =========================
# USER MODEL
# =========================
class UserCreate(BaseModel):
    username: str
    password: str


# =========================
# REGISTER
# =========================
@app.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):

    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(400, "User already exists")

    db.add(models.User(
        username=user.username,
        hashed_password=pwd_context.hash(user.password)
    ))

    db.commit()
    return {"message": "registered"}


# =========================
# LOGIN (FIXED)
# =========================
@app.post("/login")
def login(user: UserCreate, response: Response, db: Session = Depends(get_db)):

    db_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()

    if not db_user or not pwd_context.verify(user.password, db_user.hashed_password):
        raise HTTPException(401, "Invalid credentials")

    session_id = str(uuid.uuid4())
    session_store[session_id] = db_user.id

    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True
    )

    return {
        "message": "login success",
        "user_id": db_user.id,
        "username": db_user.username
    }


# =========================
# AUTH CHECK
# =========================
def get_user(request: Request, db: Session):

    sid = request.cookies.get("session_id")

    if not sid or sid not in session_store:
        raise HTTPException(401, "Not logged in")

    user_id = session_store[sid]

    return db.query(models.User).filter(models.User.id == user_id).first()


# =========================
# LOGOUT
# =========================
@app.post("/logout")
def logout(request: Request, response: Response):

    sid = request.cookies.get("session_id")

    if sid in session_store:
        del session_store[sid]

    response.delete_cookie("session_id")

    return {"message": "logged out"}


# =========================
# ROOT
# =========================
@app.get("/")
def root():
    return FileResponse("static/index.html")


# =========================
# CREATE GOAL (STABLE + AI SAFE)
# =========================
@app.post("/goals/")
def create_goal(
    subject: str,
    target_date: str,
    hours_per_day: float,
    db: Session = Depends(get_db)
):

    # =========================
    # SAVE GOAL
    # =========================
    goal = models.Goal(
        subject=subject,
        target_date=target_date,
        hours_per_day=hours_per_day,
    )

    db.add(goal)
    db.commit()
    db.refresh(goal)

    # =========================
    # AI TOPICS
    # =========================
    try:
        plan = generate_study_plan(subject)
    except Exception:
        plan=[["Intro","Basics","Practice"]]
    if not isinstance(plan,list):
        plan=[["Basics","Revision"]]
    topics=[t for group in plan for t in group]

    if not topics:
        topics=["General Study"]         

    # =========================
    # DATE SETUP
    # =========================
    start = datetime.today().date()
    end = datetime.strptime(target_date, "%Y-%m-%d").date()

    total_days = max(1, (end - start).days)

    daily_capacity = max(60, int(hours_per_day * 60))
    per_day = max(1, daily_capacity // 60)

    # =========================
    # BUILD SCHEDULE
    # =========================
    schedule = {i: [] for i in range(total_days)}

    # Learning phase
    idx = 0
    for day in range(total_days):
        if idx < len(topics):
            batch = topics[idx: idx + per_day]
            schedule[day].extend(batch)
            idx += len(batch)

    # Revision fill
    revision_pool = topics if topics else ["Basics"]

    for day in range(total_days):
        if len(schedule[day]) == 0:
            schedule[day] = [
                f"{t} (Revision)" for t in revision_pool[:per_day]
            ]

    # =========================
    # SAVE TO DB (FIXED - ONLY ONCE)
    # =========================
    for day in range(total_days):

        items = schedule[day]
        if not items:
            continue

        per_time = max(20, daily_capacity // len(items))

        for t in items:
            db.add(models.StudySession(
                goal_id=goal.id,
                topic=t,
                day_label=f"Day {day + 1}",
                duration_minutes=per_time
            ))

    db.commit()

    return {
        "goal_id": goal.id,
        "total_topics": len(topics),
        "total_days": total_days,
        "status": "stable scheduler working"
    }


# =========================
# SESSIONS
# =========================
@app.get("/goals/{goal_id}/sessions")
def get_sessions(goal_id: int, db: Session = Depends(get_db)):

    return db.query(models.StudySession).filter(
        models.StudySession.goal_id == goal_id
    ).all()


# =========================
# COMPLETE
# =========================
@app.put("/sessions/{session_id}/complete")
def complete(session_id: int, db: Session = Depends(get_db)):

    s = db.query(models.StudySession).get(session_id)

    if not s:
        raise HTTPException(404, "not found")

    s.completed = True
    db.commit()

    return {"message": "done"}


# =========================
# PROGRESS
# =========================
@app.get("/goals/{goal_id}/progress")
def progress(goal_id: int, db: Session = Depends(get_db)):

    sessions = db.query(models.StudySession).filter(
        models.StudySession.goal_id == goal_id
    ).all()

    total = len(sessions)
    done = sum(1 for s in sessions if s.completed)

    return {
        "total": total,
        "completed": done,
        "percent": round((done / total) * 100, 1) if total else 0
    }