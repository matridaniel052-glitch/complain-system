import os
import sqlite3
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash

# Canonical "nature of problem" categories — these are the departments
# routed by WORKFLOW_PATHS in app.py (Figure 4.8 / Section 2.6).
DEFAULT_DEPARTMENTS = [
    "Academic Affairs",
    "Examinations Office",
    "Finance Office",
    "Welfare / Housing",
    "IT Directorate",
    "SRC",
    "Security",
]

# Try MySQL first, fallback to SQLite
USE_MYSQL = True
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "srccom_db")
SQLITE_DB = "srccom_db.db"  # Local SQLite fallback


class SQLiteConnection:
    """Wrapper to make SQLite behave like MySQL connector"""
    def __init__(self, conn):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
    
    def cursor(self, dictionary=False):
        """Return a cursor that behaves like MySQL cursor"""
        cursor = self.conn.cursor()
        return SQLiteCursor(cursor) if dictionary else cursor
    
    def commit(self):
        return self.conn.commit()
    
    def close(self):
        return self.conn.close()
    
    def is_connected(self):
        try:
            self.conn.execute("SELECT 1")
            return True
        except:
            return False


class SQLiteCursor:
    """Wrapper to make SQLite cursor behave like MySQL cursor"""
    def __init__(self, cursor):
        self.cursor = cursor
    
    def execute(self, query, params=()):
        # Convert MySQL parameter style (%) to SQLite (?)
        if "%s" in query:
            query = query.replace("%s", "?")
        return self.cursor.execute(query, params)
    
    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        # Convert sqlite3.Row to dict
        return dict(row) if row else None
    
    def fetchall(self):
        rows = self.cursor.fetchall()
        # Convert sqlite3.Row objects to dicts
        return [dict(row) if row else None for row in rows]
    
    def close(self):
        return self.cursor.close()


def get_connection():
    global USE_MYSQL
    
    if USE_MYSQL:
        try:
            return mysql.connector.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                auth_plugin="mysql_native_password",
                connection_timeout=5
            )
        except (Error, Exception) as e:
            print(f"[DB ERROR] MySQL unavailable: {e}, switching to SQLite")
            USE_MYSQL = False
            return get_connection()  # Fallback to SQLite
    
    # SQLite fallback - return wrapped connection
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    return SQLiteConnection(conn)


def init_database():
    global USE_MYSQL
    conn = None
    try:
        # Try MySQL first
        if not USE_MYSQL:
            # A previous call already found MySQL unavailable and flipped this
            # flag. Without this, the block below is silently skipped (no
            # exception raised) and the `except` branch — which holds all the
            # SQLite schema/migration logic — never runs, so SQLite installs
            # can be left permanently stuck on an old schema. Raising here
            # routes us into that same, already-correct fallback path.
            raise RuntimeError("USE_MYSQL is False; using SQLite fallback")
        if USE_MYSQL:
            print(f"[DB INIT] Attempting MySQL connection to {DB_HOST}:{DB_PORT}")
            conn = mysql.connector.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                auth_plugin="mysql_native_password",
                connection_timeout=5
            )
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}`")
            conn.database = DB_NAME

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    fullname VARCHAR(100) NOT NULL,
                    student_id VARCHAR(20) UNIQUE,
                    email VARCHAR(100) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    role ENUM('student','admin','registrar','manager') DEFAULT 'student',
                    status VARCHAR(20) DEFAULT 'active',
                    requested_department_id INT DEFAULT NULL,
                    passport_photo VARCHAR(255) DEFAULT NULL,
                    level VARCHAR(20) DEFAULT NULL,
                    phone VARCHAR(20) DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            for column_sql in [
                "ALTER TABLE users ADD COLUMN status VARCHAR(20) DEFAULT 'active'",
                "ALTER TABLE users ADD COLUMN requested_department_id INT DEFAULT NULL",
                # Widen the role enum for installs created before registrar/manager existed —
                # without this, inserting those roles silently truncates to '' under MySQL's
                # default (non-strict) SQL mode instead of raising an error.
                "ALTER TABLE users MODIFY COLUMN role ENUM('student','admin','registrar','manager') DEFAULT 'student'",
            ]:
                try:
                    cursor.execute(column_sql)
                except (Error, Exception):
                    pass

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS departments (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    primary_admin_id INT DEFAULT NULL,
                    sub_admin_id INT DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            for column_sql in [
                "ALTER TABLE departments ADD COLUMN primary_admin_id INT DEFAULT NULL",
                "ALTER TABLE departments ADD COLUMN sub_admin_id INT DEFAULT NULL",
            ]:
                try:
                    cursor.execute(column_sql)
                except (Error, Exception):
                    pass

            # Many-to-many: which staff accounts can view/respond to a department's complaints.
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS department_admins (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    department_id INT NOT NULL,
                    user_id INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uniq_dept_user (department_id, user_id),
                    FOREIGN KEY (department_id) REFERENCES departments(id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS complaints (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    student_id INT NOT NULL,
                    department_id INT,
                    subject VARCHAR(200) NOT NULL,
                    complaint TEXT NOT NULL,
                    faculty VARCHAR(100) DEFAULT NULL,
                    program VARCHAR(150) DEFAULT NULL,
                    priority ENUM('Normal','High','Urgent') DEFAULT 'Normal',
                    status ENUM('Pending','Notify','In Progress','Resolved') DEFAULT 'Pending',
                    office_stage VARCHAR(100) DEFAULT NULL,
                    anonymous TINYINT(1) DEFAULT 0,
                    attachment VARCHAR(255) DEFAULT NULL,
                    nature_of_problem VARCHAR(150) DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES users(id),
                    FOREIGN KEY (department_id) REFERENCES departments(id)
                )
                """
            )
            for column_sql in [
                "ALTER TABLE complaints ADD COLUMN program VARCHAR(150) DEFAULT NULL",
                "ALTER TABLE complaints ADD COLUMN office_stage VARCHAR(100) DEFAULT NULL",
                "ALTER TABLE complaints ADD COLUMN nature_of_problem VARCHAR(150) DEFAULT NULL",
            ]:
                try:
                    cursor.execute(column_sql)
                except (Error, Exception) as exc:
                    if "duplicate column" not in str(exc).lower() and "already exists" not in str(exc).lower():
                        raise
            
            # Add level and phone to users if missing
            for column_sql in [
                "ALTER TABLE users ADD COLUMN level VARCHAR(20) DEFAULT NULL",
                "ALTER TABLE users ADD COLUMN phone VARCHAR(20) DEFAULT NULL",
            ]:
                try:
                    cursor.execute(column_sql)
                except (Error, Exception):
                    pass

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    complaint_id INT NOT NULL,
                    rating INT DEFAULT NULL,
                    comments TEXT,
                    reply TEXT,
                    reply_date TIMESTAMP NULL,
                    admin_id INT DEFAULT NULL,
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (complaint_id) REFERENCES complaints(id)
                )
                """
            )

            # History of admin replies for audit / reply history
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    complaint_id INT NOT NULL,
                    admin_id INT DEFAULT NULL,
                    reply TEXT,
                    reply_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (complaint_id) REFERENCES complaints(id),
                    FOREIGN KEY (admin_id) REFERENCES users(id)
                )
                """
            )

            cursor.execute("SELECT COUNT(*) FROM departments")
            if cursor.fetchone()[0] == 0:
                cursor.executemany(
                    "INSERT INTO departments (name) VALUES (%s)",
                    [(name,) for name in DEFAULT_DEPARTMENTS]
                )

            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE email=%s", ("admin@utas.edu.gh",)
            )
            admin_exists = cursor.fetchone()[0]
            if not admin_exists:
                cursor.execute(
                    "INSERT INTO users (fullname, student_id, email, password, role) VALUES (%s, %s, %s, %s, 'admin')",
                    (
                        "UTAS Admin",
                        "",
                        "admin@utas.edu.gh",
                        generate_password_hash("admin123")
                    )
                )

            conn.commit()
            cursor.close()
            conn.close()
            print("[DB INIT] MySQL database initialized successfully")
        
    except (Error, Exception) as e:
        print(f"[DB INIT WARNING] MySQL failed: {e}")
        print("[DB INIT] Switching to SQLite fallback...")
        USE_MYSQL = False
        
        # Clean up failed MySQL connection
        if conn:
            try:
                if hasattr(conn, 'is_connected') and conn.is_connected():
                    conn.close()
            except:
                pass
        
        # Use SQLite instead
        try:
            conn = sqlite3.connect(SQLITE_DB)
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fullname TEXT NOT NULL,
                    student_id TEXT UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    role TEXT DEFAULT 'student',
                    status TEXT DEFAULT 'active',
                    requested_department_id INTEGER DEFAULT NULL,
                    passport_photo TEXT DEFAULT NULL,
                    level TEXT DEFAULT NULL,
                    phone TEXT DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN requested_department_id INTEGER DEFAULT NULL")
            except Exception:
                pass

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS departments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    primary_admin_id INTEGER DEFAULT NULL,
                    sub_admin_id INTEGER DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            try:
                cursor.execute("ALTER TABLE departments ADD COLUMN primary_admin_id INTEGER DEFAULT NULL")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE departments ADD COLUMN sub_admin_id INTEGER DEFAULT NULL")
            except Exception:
                pass

            # Many-to-many: which staff accounts can view/respond to a department's complaints.
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS department_admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    department_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (department_id, user_id),
                    FOREIGN KEY (department_id) REFERENCES departments(id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS complaints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    department_id INTEGER,
                    subject TEXT NOT NULL,
                    complaint TEXT NOT NULL,
                    faculty TEXT,
                    program TEXT,
                    priority TEXT DEFAULT 'Normal',
                    status TEXT DEFAULT 'Pending',
                    office_stage TEXT,
                    anonymous INTEGER DEFAULT 0,
                    attachment TEXT,
                    nature_of_problem TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES users(id),
                    FOREIGN KEY (department_id) REFERENCES departments(id)
                )
                """
            )
            for column_sql in [
                "ALTER TABLE complaints ADD COLUMN program TEXT",
                "ALTER TABLE complaints ADD COLUMN office_stage TEXT",
                "ALTER TABLE complaints ADD COLUMN nature_of_problem TEXT",
            ]:
                try:
                    cursor.execute(column_sql)
                except sqlite3.OperationalError as exc:
                    if "duplicate column name" not in str(exc).lower():
                        raise

            # Migrate older installs that created the users table before `passport_photo` existed.
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN passport_photo TEXT")
            except Exception:
                pass
            
            # Add level and phone for older installs
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN level TEXT")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT")
            except Exception:
                pass

            # Migrate older installs that created the feedback table before `reply_date` existed.
            try:
                cursor.execute("ALTER TABLE feedback ADD COLUMN reply_date TIMESTAMP")
            except Exception:
                pass

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    complaint_id INTEGER NOT NULL,
                    rating INTEGER,
                    comments TEXT,
                    reply TEXT,
                    reply_date TIMESTAMP,
                    admin_id INTEGER,
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (complaint_id) REFERENCES complaints(id)
                )
                """
            )

            # History of admin replies for audit / reply history (SQLite)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    complaint_id INTEGER NOT NULL,
                    admin_id INTEGER,
                    reply TEXT,
                    reply_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (complaint_id) REFERENCES complaints(id),
                    FOREIGN KEY (admin_id) REFERENCES users(id)
                )
                """
            )

            cursor.execute("SELECT COUNT(*) FROM departments")
            if cursor.fetchone()[0] == 0:
                cursor.executemany(
                    "INSERT INTO departments (name) VALUES (?)",
                    [(name,) for name in DEFAULT_DEPARTMENTS]
                )

            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE email=?", ("admin@utas.edu.gh",)
            )
            admin_exists = cursor.fetchone()[0]
            if not admin_exists:
                cursor.execute(
                    "INSERT INTO users (fullname, student_id, email, password, role) VALUES (?, ?, ?, ?, 'admin')",
                    (
                        "UTAS Admin",
                        "",
                        "admin@utas.edu.gh",
                        generate_password_hash("admin123")
                    )
                )

            conn.commit()
            conn.close()
            print(f"[DB INIT] SQLite database initialized successfully at {SQLITE_DB}")
            
        except Exception as sqlite_error:
            print(f"[DB INIT ERROR] SQLite also failed: {sqlite_error}")
