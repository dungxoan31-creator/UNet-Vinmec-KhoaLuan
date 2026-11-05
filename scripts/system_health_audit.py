"""Comprehensive System Health and Integrity Audit for FE, BE, UI/UX, API, and AI."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

results = {
    "backend_syntax": "PENDING",
    "fastapi_routes": "PENDING",
    "database_schema": "PENDING",
    "model_registry": "PENDING",
    "cdss_engine": "PENDING",
}

print("=" * 60)
print("1. CHECKING BACKEND PYTHON SYNTAX")
print("=" * 60)
backend_files = list(Path("backend").rglob("*.py"))
syntax_errors = []
for p in backend_files:
    try:
        with open(p, "r", encoding="utf-8") as f:
            compile(f.read(), str(p), "exec")
    except Exception as e:
        syntax_errors.append((str(p), str(e)))

if not syntax_errors:
    print(f"PASS: {len(backend_files)} backend python files compiled successfully with 0 errors.")
    results["backend_syntax"] = "PASS"
else:
    print(f"FAIL: {len(syntax_errors)} syntax errors found:")
    for p, err in syntax_errors:
        print(f"  {p}: {err}")
    results["backend_syntax"] = "FAIL"


print("\n" + "=" * 60)
print("2. CHECKING FASTAPI APP & ROUTE REGISTRATION")
print("=" * 60)
try:
    from backend.app.main import app
    def _extract_routes(app):
        paths = set()
        for r in app.routes:
            if hasattr(r, 'path'):
                paths.add(r.path)
            elif hasattr(r, 'routes'):
                for sub in r.routes:
                    if hasattr(sub, 'path'):
                        paths.add(sub.path)
            elif hasattr(r, 'original_router'):
                for sub in r.original_router.routes:
                    if hasattr(sub, 'path'):
                        paths.add(sub.path)
        return paths
    routes = _extract_routes(app)
    print(f"PASS: FastAPI app loaded successfully with {len(routes)} registered endpoints.")
    # Check critical endpoints
    critical = [
        "/api/v1/segment",
        "/api/v1/cdss/evaluate",
        "/api/v1/cdss/evaluate-multi",
        "/api/workspace/cases/{study_id}/corrections",
        "/api/stats",
        "/api/admin/users",
        "/api/health/live",
    ]
    missing = [c for c in critical if c not in routes]
    if not missing:
        print(f"PASS: All {len(critical)} critical endpoints are registered.")
        results["fastapi_routes"] = "PASS"
    else:
        print(f"FAIL: Missing critical routes: {missing}")
        results["fastapi_routes"] = "FAIL"
except Exception as e:
    print(f"FAIL: FastAPI initialization failed: {e}")
    results["fastapi_routes"] = "FAIL"


print("\n" + "=" * 60)
print("3. CHECKING DATABASE SCHEMA & IMMUTABILITY TRIGGERS")
print("=" * 60)
try:
    from backend.db.database import SessionLocal, init_db
    from sqlalchemy import text
    init_db()
    with SessionLocal() as db:
        # Check triggers
        triggers = db.execute(text("SELECT name, tbl_name FROM sqlite_master WHERE type='trigger'")).fetchall()
        trigger_names = {t[0] for t in triggers}
        print(f"Found {len(triggers)} triggers in SQLite database.")
        required_triggers = [
            "trg_audit_logs_no_update",
            "trg_audit_logs_no_delete",
            "trg_images_laterality_insert",
            "trg_images_laterality_update",
            "trg_studies_domain_insert",
            "trg_studies_domain_update",
        ]
        missing_trig = [rt for rt in required_triggers if rt not in trigger_names]
        if not missing_trig:
            print("PASS: All required safety and immutability triggers are active.")
            results["database_schema"] = "PASS"
        else:
            print(f"FAIL: Missing triggers: {missing_trig}")
            results["database_schema"] = "FAIL"
except Exception as e:
    print(f"FAIL: Database check error: {e}")
    results["database_schema"] = "FAIL"


print("\n" + "=" * 60)
print("4. CHECKING MODEL REGISTRY & ADAPTER STATUS")
print("=" * 60)
try:
    from backend.app.config import model_registry
    primary = model_registry.get_primary_adapter()
    print(f"Primary Adapter: {primary.name} ({primary.architecture})")
    print(f"  Loaded: {primary.is_loaded}")
    print(f"  Checksum: {getattr(primary.engine, 'model_checksum', None)}")
    print(f"  Device: {primary.device}")

    # Check registered model keys
    registered = list(model_registry.adapters.keys()) if hasattr(model_registry, "adapters") else []
    print(f"Registered adapters: {registered}")
    results["model_registry"] = "PASS" if primary.is_loaded else "NOT_LOADED"
except Exception as e:
    print(f"FAIL: Model registry check error: {e}")
    results["model_registry"] = "FAIL"


print("\n" + "=" * 60)
print("5. CHECKING CDSS ENGINE DETERMINISTIC REASONING")
print("=" * 60)
try:
    from backend.services.cdss_engine import CDSSReasoningEngine
    engine = CDSSReasoningEngine()
    # Test 100mm boundary
    def _test_findings(diam):
        return {
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": True,
            "max_diameter_mm": diam,
            "locules_count": 1,
            "has_solid_component": False,
            "papillary_projections_count": 0,
            "fluid_echogenicity": "anechoic",
            "acoustic_shadowing": False,
            "wall_irregular": False,
            "color_score": 1,
            "has_ascites": False,
            "has_peritoneal_nodules": False,
        }
    res_99 = engine.evaluate_case(vision_findings=_test_findings(99.9))
    res_100 = engine.evaluate_case(vision_findings=_test_findings(100.0))
    cat_99 = res_99.get("orads_stratification", {}).get("category")
    cat_100 = res_100.get("orads_stratification", {}).get("category")

    # Test multi-lesion
    res_multi = engine.evaluate_multi_lesions([
        {"lesion_id": "L1", "findings": _test_findings(45.0)},
        {"lesion_id": "L2", "findings": _test_findings(110.0)},
    ])
    overall = res_multi.get("overall_category")

    if cat_99 == "O-RADS 2" and cat_100 == "O-RADS 3" and overall == "O-RADS 3":
        print(f"PASS: CDSS reasoning verified:")
        print(f"  99.9 mm -> {cat_99}")
        print(f"  100.0 mm -> {cat_100}")
        print(f"  Multi-lesion worst-case -> {overall}")
        results["cdss_engine"] = "PASS"
    else:
        print(f"FAIL: CDSS reasoning mismatch: 99.9={cat_99}, 100={cat_100}, multi={overall}")
        results["cdss_engine"] = "FAIL"
except Exception as e:
    print(f"FAIL: CDSS engine error: {e}")
    results["cdss_engine"] = "FAIL"

print("\n" + "=" * 60)
print("AUDIT SUMMARY:")
for k, v in results.items():
    print(f"  {k}: {v}")
print("=" * 60)
