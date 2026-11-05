"""Audit reproductions. Assertions document observed defects, not desired behavior."""
import uuid
import numpy as np
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.security import create_access_token, hash_password
from backend.db.database import SessionLocal, FacilityModel, UserModel, AuditLogModel
from scripts.ultrasound_preprocessing_enhancement import CaliperInpainter, SpeckleFilter


def test_audit_cross_facility_admin_can_reset_password(monkeypatch):
    monkeypatch.setenv('APP_JWT_SECRET', 'synthetic-audit-key-20261101-at-least-32-characters')
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        a = FacilityModel(id='audit-a-'+suffix, facility_code='a'+suffix, name='Synthetic A')
        b = FacilityModel(id='audit-b-'+suffix, facility_code='b'+suffix, name='Synthetic B')
        db.add_all([a, b]); db.commit()
        admin = UserModel(id='audit-admin-'+suffix, username='aa'+suffix, role='ADMIN', facility_id=a.id, is_active=True, must_change_password=False, password_hash=hash_password('AuditOnly123!'))
        doctor = UserModel(id='audit-doc-'+suffix, username='ab'+suffix, role='DOCTOR', facility_id=b.id, is_active=True, must_change_password=False, password_hash=hash_password('BeforeAudit123!'))
        admin.full_name = 'Synthetic Admin'
        doctor.full_name = 'Synthetic Doctor'
        db.add_all([admin, doctor]); db.commit()
        token = create_access_token({'sub': admin.username, 'role':'ADMIN'})
        previous = doctor.password_hash
        with TestClient(app) as client:
            response = client.post('/api/admin/users/'+doctor.id+'/reset-password', headers={'Authorization':'Bearer '+token}, json={'new_password':'AfterAudit123!'})
        db.refresh(doctor)
        assert response.status_code == 200, response.text
        assert doctor.password_hash != previous
        print('REPRODUCED: facility A admin changed facility B doctor password')


def test_audit_bright_thin_structure_without_caliper_is_removed():
    image = np.full((128,128), 40, dtype=np.uint8)
    image[64,40:80] = 250
    result, mask = CaliperInpainter().inpaint(image)
    assert np.count_nonzero(mask[64,40:80]) == 40
    assert not np.array_equal(image, result)
    print('REPRODUCED: 40-pixel bright anatomical-proxy line classified as marker')


def test_audit_srad_color_input_raises():
    for channels in (3,4):
        try:
            SpeckleFilter.srad_filter(np.zeros((32,32,channels),dtype=np.uint8))
        except ValueError:
            continue
        raise AssertionError('Expected current unsupported RGB/RGBA input')
    print('REPRODUCED: standalone SRAD rejects RGB and RGBA')


def test_audit_logs_can_be_modified_and_deleted():
    with SessionLocal() as db:
        row = AuditLogModel(entity_name='audit_probe', entity_id=uuid.uuid4().hex, action_type='PROBE', actor_id='synthetic-auditor')
        db.add(row); db.commit()
        key = row.id
        row.action_type = 'MODIFIED'; db.commit()
        db.expire_all()
        assert db.get(AuditLogModel,key).action_type == 'MODIFIED'
        db.delete(db.get(AuditLogModel,key)); db.commit()
        assert db.get(AuditLogModel,key) is None
        print('REPRODUCED: application DB role permits audit update and delete')


def test_audit_live_srad_keyword_mismatch():
    from backend.services.preprocessor import UltrasoundPreprocessor
    try:
        UltrasoundPreprocessor().preprocess_for_inference(np.full((128,128),40,dtype=np.uint8), denoise_method='srad')
    except TypeError as exc:
        assert 'num_iter' in str(exc)
        print('REPRODUCED: live preprocessing uses num_iter instead of n_iter')
        return
    raise AssertionError('Expected current SRAD keyword defect')


def test_audit_simple_cyst_100mm_underclassified():
    from backend.services.cdss_engine import CDSSReasoningEngine
    findings = dict(assessment_source='clinician', modality='ultrasound_2d', ultrasound_exam_complete=True, max_diameter_mm=100, locules_count=1, has_solid_component=False, papillary_projections_count=0, fluid_echogenicity='anechoic', acoustic_shadowing=False, wall_irregular=False, color_score=1, has_ascites=False, has_peritoneal_nodules=False)
    result = CDSSReasoningEngine().evaluate_case(findings)
    assert result['orads_stratification']['category'] == 'O-RADS 2', result
    print('REPRODUCED: 100 mm simple cyst returns O-RADS 2 instead of category 3')


def test_audit_split_hashes_paths_not_content(tmp_path):
    from scripts.audit_patient_independence_leakage import audit_splits
    (tmp_path/'a.png').write_bytes(b'identical synthetic image bytes')
    (tmp_path/'b.png').write_bytes(b'identical synthetic image bytes')
    (tmp_path/'train.csv').write_text('image_path\na.png\n')
    (tmp_path/'test.csv').write_text('image_path\nb.png\n')
    result = audit_splits(str(tmp_path))
    assert result['status'] == 'PASS'
    print('REPRODUCED: duplicate bytes under different filenames pass split audit')
