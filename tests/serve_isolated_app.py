import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "artifacts" / "review-e2e-runtime"
RUNTIME.mkdir(parents=True, exist_ok=True)

os.environ["APP_DATA_DIR"] = str(RUNTIME)
os.environ["APP_DB_PATH"] = str(RUNTIME / "technical_test.sqlite3")
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")
os.environ.setdefault("APP_DOCTOR_PASSWORD", "doctor-local-test-2026")
os.environ.setdefault("APP_ADMIN_PASSWORD", "admin-local-test-2026")

from backend.db import database
from backend.app import config

database.DB_PATH = str(RUNTIME / "technical_test.sqlite3")
database.DATABASE_URL = f"sqlite:///{database.DB_PATH}"
database.engine = create_engine(database.DATABASE_URL, connect_args={"check_same_thread": False})
database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)

config.DATA_DIR = str(RUNTIME)
config.UPLOAD_DIR = str(RUNTIME / "uploads")
config.REPORTS_DIR = str(RUNTIME / "reports")
Path(config.UPLOAD_DIR).mkdir(exist_ok=True)
Path(config.REPORTS_DIR).mkdir(exist_ok=True)

from backend.app.main import app

database.init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8027, log_level="warning")
