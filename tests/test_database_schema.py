import sqlite3


def test_init_database_adds_missing_complaints_columns(tmp_path, monkeypatch):
    import database as db

    db_path = tmp_path / "srccom_db.db"
    monkeypatch.setattr(db, "SQLITE_DB", str(db_path))
    monkeypatch.setattr(db, "USE_MYSQL", False)

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            student_id TEXT UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'student',
            passport_photo TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            department_id INTEGER,
            subject TEXT NOT NULL,
            complaint TEXT NOT NULL,
            faculty TEXT DEFAULT NULL,
            priority TEXT DEFAULT 'Normal',
            status TEXT DEFAULT 'Pending',
            anonymous INTEGER DEFAULT 0,
            attachment TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()

    db.init_database()

    conn = sqlite3.connect(str(db_path))
    columns = [row[1] for row in conn.execute("PRAGMA table_info(complaints)")]
    conn.close()

    assert "program" in columns
    assert "office_stage" in columns
    assert "nature_of_problem" in columns


def test_registrar_can_access_department_management():
    import app as app_module

    client = app_module.app.test_client()
    with client.session_transaction() as session:
        session["user"] = {"id": 1, "fullname": "Registrar", "email": "registrar@utas.edu.gh", "role": "registrar"}

    response = client.get("/admin/departments")

    assert response.status_code == 200


def test_edit_department_updates_name(monkeypatch):
    import app as app_module

    class FakeCursor:
        def __init__(self):
            self.executed = []

        def execute(self, query, params=()):
            self.executed.append((query, params))

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_obj

        def commit(self):
            pass

        def close(self):
            pass

    fake_conn = FakeConnection()
    monkeypatch.setattr(app_module, "get_connection", lambda: fake_conn)

    client = app_module.app.test_client()
    with client.session_transaction() as session:
        session["user"] = {"id": 1, "fullname": "Registrar", "email": "registrar@utas.edu.gh", "role": "registrar"}

    response = client.post("/admin/departments/edit/7", data={"name": "Registry Office"})

    assert response.status_code == 302
    assert any("UPDATE departments" in query for query, _ in fake_conn.cursor_obj.executed)
