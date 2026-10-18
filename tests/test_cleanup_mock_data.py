import sqlite3

from scripts.cleanup_mock_data import cleanup


def test_cleanup_backs_up_synthetic_cases_and_preserves_real_cases(tmp_path):
    database = tmp_path / "runtime.sqlite3"
    with sqlite3.connect(database) as db:
        db.executescript("""
            CREATE TABLE patients (id TEXT PRIMARY KEY, anonymized_pid TEXT);
            CREATE TABLE studies (id TEXT PRIMARY KEY, patient_id TEXT REFERENCES patients(id));
            CREATE TABLE images (id TEXT PRIMARY KEY, study_id TEXT REFERENCES studies(id), raw_path TEXT);
            CREATE TABLE predictions (id TEXT, image_id TEXT REFERENCES images(id));
            CREATE TABLE reviews (id TEXT, image_id TEXT REFERENCES images(id));
            INSERT INTO patients VALUES ('fake', 'TEST-001'), ('real', 'BN-001');
            INSERT INTO studies VALUES ('fake-study', 'fake'), ('real-study', 'real');
            INSERT INTO images VALUES ('fake-image', 'fake-study', 'fake.png'), ('real-image', 'real-study', 'real.png');
            INSERT INTO predictions VALUES ('fake-prediction', 'fake-image');
            INSERT INTO reviews VALUES ('fake-review', 'fake-image');
        """)
    preview = cleanup(database, tmp_path / 'backups')
    assert not preview['applied']
    assert preview['records']['patients'] == 1
    result = cleanup(database, tmp_path / 'backups', apply=True)
    assert result['applied']
    with sqlite3.connect(database) as db:
        assert db.execute('SELECT id FROM patients').fetchall() == [('real',)]
        assert db.execute('SELECT id FROM studies').fetchall() == [('real-study',)]
        assert db.execute('SELECT id FROM images').fetchall() == [('real-image',)]
        assert db.execute('SELECT COUNT(*) FROM reviews').fetchone()[0] == 0
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    with sqlite3.connect(result['backup']) as db:
        assert db.execute('SELECT COUNT(*) FROM patients').fetchone()[0] == 2
    assert not cleanup(database, tmp_path / 'backups', apply=True)['applied']
