import json
import os
import secrets
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RUNTIME = Path(os.environ.get("APP_DATA_DIR", ROOT / "artifacts" / "review-e2e-runtime")).resolve()
RUNTIME.mkdir(parents=True, exist_ok=True)

os.environ["APP_DATA_DIR"] = str(RUNTIME)
os.environ["APP_DB_PATH"] = os.environ.get("APP_DB_PATH", str(RUNTIME / "technical_test.sqlite3"))
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")
os.environ.setdefault("APP_PATIENT_PID_HMAC_SECRET", "test-only-patient-id-hmac-key-2026-10-21")
os.environ.setdefault("APP_DOCTOR_PASSWORD", "doctor-local-test-2026")
os.environ.setdefault("APP_ADMIN_PASSWORD", "admin-local-test-2026")
os.environ.setdefault("APP_DOCTOR_FACILITY_ID", "fac-vinmec-times-city")

from backend.app import config
from backend.db import database

database.DB_PATH = str(Path(os.environ["APP_DB_PATH"]).resolve())
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

# Test-only account: do not add example identities to the application's real database.
from backend.app.security import hash_password

with database.SessionLocal() as db:
    if not db.query(database.UserModel).filter_by(username="dungnh").first():
        db.add(database.UserModel(
            id=str(uuid.uuid4()),
            username="dungnh",
            full_name="Nguyễn Hữu Dũng (tổng hợp)",
            role="DOCTOR",
            password_hash=hash_password(secrets.token_urlsafe(32)),
        ))
        db.commit()
    if not db.query(database.UserModel).filter_by(username="reviewer").first():
        reviewer_password = os.environ.get("APP_E2E_REVIEWER_PASSWORD", "synthetic-safety-reviewer-2026")
        db.add(database.UserModel(
            id=str(uuid.uuid4()),
            username="reviewer",
            full_name="Synthetic Senior Reviewer",
            role="SENIOR",
            facility_id=os.environ.get("APP_DOCTOR_FACILITY_ID", "fac-vinmec-times-city"),
            password_hash=hash_password(reviewer_password),
            is_active=True,
            must_change_password=False,
        ))
        db.commit()

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8027"))
    ready_file = os.environ.get("APP_E2E_READY_FILE")

    class IsolatedTestServer(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            if not self.started or not ready_file:
                return

            ready_path = Path(ready_file).resolve()
            if ready_path.parent != RUNTIME:
                raise RuntimeError("E2E readiness marker must stay inside the isolated runtime.")
            temporary_path = ready_path.with_name(f"{ready_path.name}.{os.getpid()}.tmp")
            temporary_path.write_text(
                json.dumps({
                    "pid": os.getpid(),
                    "host": host,
                    "port": port,
                    "runtime": str(RUNTIME),
                    "instance_token": os.environ.get("APP_E2E_INSTANCE_TOKEN"),
                }),
                encoding="utf-8",
            )
            os.replace(temporary_path, ready_path)

    server = IsolatedTestServer(uvicorn.Config(app, host=host, port=port, log_level="warning", access_log=False))
    server.run()
