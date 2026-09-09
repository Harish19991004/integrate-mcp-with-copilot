"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import re

from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
import sqlite3
from pathlib import Path
from pydantic import BaseModel

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

DEFAULT_DATABASE_PATH = Path(__file__).parent / "activities.sqlite"

INITIAL_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


class AccountRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def get_database_path():
    return Path(os.getenv("ACTIVITY_DB_PATH", DEFAULT_DATABASE_PATH))


def get_connection():
    connection = sqlite3.connect(get_database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def normalize_email(email):
    return email.strip().lower()


def validate_email(email):
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=422, detail="Enter a valid email address")


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password, stored_hash):
    salt_hex, digest_hex = stored_hash.split("$", 1)
    candidate = hash_password(password, bytes.fromhex(salt_hex)).split("$", 1)[1]
    return hmac.compare_digest(candidate, digest_hex)


def create_session(connection, email):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    connection.execute(
        "INSERT INTO sessions (token, email, expires_at) VALUES (?, ?, ?)",
        (token, email, expires_at.isoformat()),
    )
    return token


def get_current_user(authorization):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    token = authorization.removeprefix("Bearer ").strip()
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        user = connection.execute(
            """
            SELECT users.email, users.name, users.role
            FROM sessions
            JOIN users ON users.email = sessions.email
            WHERE sessions.token = ? AND sessions.expires_at > ?
            """,
            (token, now),
        ).fetchone()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


def initialize_database():
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS activities (
                name TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                schedule TEXT NOT NULL,
                max_participants INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS participants (
                activity_name TEXT NOT NULL,
                email TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                team_name TEXT,
                PRIMARY KEY (activity_name, email),
                FOREIGN KEY (activity_name) REFERENCES activities(name)
                    ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student'
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (email) REFERENCES users(email) ON DELETE CASCADE
            );
            """
        )
        participant_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(participants)")
        }
        if "name" not in participant_columns:
            connection.execute("ALTER TABLE participants ADD COLUMN name TEXT NOT NULL DEFAULT ''")
        if "team_name" not in participant_columns:
            connection.execute("ALTER TABLE participants ADD COLUMN team_name TEXT")
        for name, activity in INITIAL_ACTIVITIES.items():
            connection.execute(
                """
                INSERT OR IGNORE INTO activities
                    (name, description, schedule, max_participants)
                VALUES (?, ?, ?, ?)
                """,
                (name, activity["description"], activity["schedule"],
                 activity["max_participants"]),
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO participants (activity_name, email, name)
                VALUES (?, ?, ?)
                """,
                [(name, email, email) for email in activity["participants"]],
            )

        admin_email = os.getenv("ADMIN_EMAIL")
        admin_password = os.getenv("ADMIN_PASSWORD")
        if admin_email and admin_password:
            admin_email = normalize_email(admin_email)
            connection.execute(
                """
                INSERT OR IGNORE INTO users (email, name, password_hash, role)
                VALUES (?, ?, ?, 'admin')
                """,
                (admin_email, "Administrator", hash_password(admin_password)),
            )


initialize_database()


@app.post("/auth/signup")
def create_account(request: AccountRequest):
    name = request.name.strip()
    email = normalize_email(request.email)
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="Name must be at least 2 characters")
    validate_email(email)
    if len(request.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    with get_connection() as connection:
        try:
            connection.execute(
                "INSERT INTO users (email, name, password_hash, role) VALUES (?, ?, ?, 'student')",
                (email, name, hash_password(request.password)),
            )
            token = create_session(connection, email)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="An account already exists for this email")
    return {"access_token": token, "token_type": "bearer", "user": {"email": email, "name": name, "role": "student"}}


@app.post("/auth/login")
def login(request: LoginRequest):
    email = normalize_email(request.email)
    with get_connection() as connection:
        user = connection.execute(
            "SELECT email, name, password_hash, role FROM users WHERE email = ?", (email,)
        ).fetchone()
        if user is None or not verify_password(request.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        token = create_session(connection, email)
    return {"access_token": token, "token_type": "bearer", "user": {"email": user["email"], "name": user["name"], "role": user["role"]}}


@app.post("/auth/logout")
def logout(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM sessions WHERE token = ?",
            (authorization.removeprefix("Bearer ").strip(),),
        )
    return {"message": "Logged out"}


@app.get("/auth/me")
def current_account(authorization: str | None = Header(default=None)):
    user = get_current_user(authorization)
    return {"email": user["email"], "name": user["name"], "role": user["role"]}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    with get_connection() as connection:
        activity_rows = connection.execute(
            "SELECT name, description, schedule, max_participants "
            "FROM activities ORDER BY name"
        ).fetchall()
        participant_rows = connection.execute(
            "SELECT activity_name, email FROM participants ORDER BY email"
        ).fetchall()

    participants_by_activity = {}
    for row in participant_rows:
        participants_by_activity.setdefault(row["activity_name"], []).append(row["email"])

    return {
        row["name"]: {
            "description": row["description"],
            "schedule": row["schedule"],
            "max_participants": row["max_participants"],
            "participants": participants_by_activity.get(row["name"], []),
        }
        for row in activity_rows
    }


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(
    activity_name: str,
    email: str | None = None,
    name: str | None = None,
    team_name: str | None = None,
    authorization: str | None = Header(default=None),
):
    """Register the authenticated student for an activity."""
    user = get_current_user(authorization)
    email = normalize_email(email or user["email"])
    if email != user["email"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="You can only register your own account")
    name = (name or user["name"]).strip()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="Name must be at least 2 characters")
    validate_email(email)
    if team_name is not None:
        team_name = team_name.strip() or None
        if team_name and len(team_name) > 100:
            raise HTTPException(status_code=422, detail="Team name is too long")

    with get_connection() as connection:
        activity = connection.execute(
            "SELECT name, max_participants FROM activities WHERE name = ?", (activity_name,)
        ).fetchone()
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")

        participant_count = connection.execute(
            "SELECT COUNT(*) AS count FROM participants WHERE activity_name = ?",
            (activity_name,),
        ).fetchone()["count"]
        if participant_count >= activity["max_participants"]:
            raise HTTPException(status_code=409, detail="This activity is full")

        try:
            connection.execute(
                """
                INSERT INTO participants (activity_name, email, name, team_name)
                VALUES (?, ?, ?, ?)
                """,
                (activity_name, email, name, team_name),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=400,
                detail="Student is already signed up"
            )

    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(
    activity_name: str,
    email: str,
    authorization: str | None = Header(default=None),
):
    """Unregister a student from an activity"""
    user = get_current_user(authorization)
    email = normalize_email(email)
    if email != user["email"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can unregister other students")
    with get_connection() as connection:
        activity = connection.execute(
            "SELECT name FROM activities WHERE name = ?", (activity_name,)
        ).fetchone()
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")

        cursor = connection.execute(
            "DELETE FROM participants WHERE activity_name = ? AND email = ?",
            (activity_name, email),
        )
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=400,
                detail="Student is not signed up for this activity"
            )

    return {"message": f"Unregistered {email} from {activity_name}"}
