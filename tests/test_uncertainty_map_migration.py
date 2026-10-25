from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def test_legacy_predictions_gain_nullable_heatmap_column_idempotently(tmp_path, monkeypatch):
    from backend.db import database

    db_path = tmp_path / "legacy-uncertainty-map.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setenv("APP_PATIENT_PID_HMAC_SECRET", "uncertainty-map-migration-test-secret-2026")
    monkeypatch.delenv("APP_DOCTOR_PASSWORD", raising=False)
    monkeypatch.delenv("APP_ADMIN_PASSWORD", raising=False)

    database.Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(database.PatientModel(id="patient-map", anonymized_pid="SYN-MAP-001"))
        study = database.StudyModel(
            id="study-map",
            patient_id="patient-map",
            study_date="2026-10-24",
        )
        image = database.ImageModel(
            id="image-map",
            study_id="study-map",
            filename="image-map.png",
            raw_path=str(tmp_path / "image-map.png"),
            laterality="L",
        )
        prediction = database.PredictionModel(
            id="prediction-map",
            image_id="image-map",
            raw_mask_rle={"shape": [512, 512], "first_val": 0, "counts": [262144]},
            measurements={"has_lesion": False},
        )
        db.add_all([study, image, prediction])
        db.commit()

    with engine.begin() as connection:
        columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(predictions)")}
        if "uncertainty_map_png" in columns:
            connection.exec_driver_sql("ALTER TABLE predictions DROP COLUMN uncertainty_map_png")

    try:
        database.init_db()
        database.init_db()

        with engine.connect() as connection:
            column = next(
                row
                for row in connection.exec_driver_sql("PRAGMA table_info(predictions)")
                if row[1] == "uncertainty_map_png"
            )
            assert (column[1], column[2], column[3]) == ("uncertainty_map_png", "BLOB", 0)

        with Session(engine) as db:
            stored = db.get(database.PredictionModel, "prediction-map")
            assert stored is not None
            assert stored.uncertainty_map_png is None
    finally:
        engine.dispose()
