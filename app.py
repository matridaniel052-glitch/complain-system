"""
app.py - Main Application Entry Point
UTAS Student Complaint Management System
Python + Flask equivalent of the original PHP system

Author  : Matri Daniel
ID      : 20220404014
Supervisor: Mr. Dominic Kwasi Adom
"""

import os
import json
import smtplib
from email.message import EmailMessage
from flask import (
    Flask, render_template, request,
    session, redirect, url_for, flash, jsonify
)
import re
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database import get_connection, init_database
from functools import wraps
import datetime

# ── App setup ──────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = "utas_cms_2025_secret_key"
app.config["SESSION_PERMANENT"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads", "letters")
app.config["PASSPORT_UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads", "passports")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB max upload
# Mail settings are read from the environment (see .env.example) so real
# credentials never need to be hardcoded here. Without them, notifications
# are silently skipped (see send_email()).
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "localhost")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "1025"))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "false").lower() in {"1", "true", "yes"}
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "")
app.config["MAIL_FROM"] = os.getenv("MAIL_FROM", "no-reply@utas.edu.gh")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["PASSPORT_UPLOAD_FOLDER"], exist_ok=True)

# Ensure the database schema is ready for the current complaint form.
init_database()

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "doc", "docx"}

# School -> list of departments/programmes offered under that school.
# Used to drive the cascading School / Programme selects on the complaint form
# so a student can identify which programme they are enrolled in.
SCHOOLS = {
    "School of Agriculture": [
        "Department of Crop Science and Biotechnology",
        "Department of Fisheries and Aquaculture",
    ],
    "School of Environment and Life Sciences": [
        "Department of Environmental Science",
        "Department of Applied Biology",
    ],
    "School of Physical Sciences": [
        "Department of Applied Physics",
        "Department of Earth Science",
        "Department of Material Science",
        "Department of Geo-Informatics and Spatial Development",
    ],
    "School of Chemical and Biochemical Sciences": [
        "Department of Applied Chemistry",
        "Department of Biochemistry and Forensic Sciences",
        "Department of Pharmaceutical Technology",
        "Department of Industrial Chemistry & Laboratory Technology",
    ],
    "School of Mathematical Sciences": [
        "Department of Mathematics",
        "Department of Statistics & Actuarial Science",
        "Department of Industrial Mathematics",
        "Department of Biometry",
    ],
    "School of Computing and Information Sciences": [
        "Department of Computer Science",
        "Department of Information Systems and Technology",
        "Department of Business Computing",
        "Department of Cyber Security and Computer Engineering Technology",
        "Professional IT Training and Business Incubation Center (PITTBIC)",
    ],
    "School of Public Health": [
        "Department of Population, Family & Reproductive Health (PFR)",
        "Department of Epidemiology and Biostatistics (EPB)",
    ],
    "School of Science, Mathematics & Technology Education": [
        "Department of Mathematics & ICT Education",
        "Department of Basic Education",
        "Department of Science Education",
    ],
    "School of Medical Sciences": [
        "Department of Anaesthesia & Intensive Care",
        "Department of Clinical Microbiology & Immunology",
    ],
    "School of Nursing & Midwifery": [
        "Department of Maternal and Child Health Nursing",
        "Department of General and Preventive Health Nursing",
    ],
    "School of Graduate Studies & Research": [],
}
FACULTIES = list(SCHOOLS.keys())
NATURE_OF_PROBLEMS = [
    "Academic Affairs",
    "Examinations Office",
    "Finance / Fees",
    "Welfare / Housing",
    "IT / Portal / Login",
    "Security / Safety",
    "Student Representation / SRC",
    "Other"
]
WORKFLOW_PATHS = {
    "Academic Affairs": [
        "Dean of Student Affairs",
        "Registrar",
        "Security"
    ],
    "Examinations Office": [
        "Head of Department",
        "Examination Officer",
        "Course Lecturer",
        "Head of Department (Final Response)"
    ],
    "Examination Office": [
        "Head of Department",
        "Examination Officer",
        "Course Lecturer",
        "Head of Department (Final Response)"
    ],
    "Finance Office": [
        "Head of Finance",
        "Bursar",
        "Registrar"
    ],
    "Welfare / Housing": [
        "Head of Welfare",
        "Facilities Manager",
        "Dean of Students"
    ],
    "IT Directorate": [
        "Director of IT",
        "Systems Administrator",
        "Network Manager"
    ],
    "SRC": [
        "SRC President",
        "SRC Vice President",
        "Student Affairs Liaison"
    ],
    "Security": [
        "Chief Security Officer",
        "Security Operations Manager"
    ]
}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.template_filter('humanize')
def humanize_filter(value):
    """Simple humanize filter: replaces underscores/hyphens, collapses spaces, title-cases."""
    if value is None:
        return ""
    s = str(value)
    s = s.replace("_", " ").replace("-", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s.title()


@app.template_filter('format_datetime')
def format_datetime(value, fmt="%d %b %Y"):
    """Format datetime-like values for templates.

    Accepts datetime objects, date strings from the database, and numeric timestamps.
    Falls back cleanly when the value is missing or invalid.
    """
    if not value:
        return "—"
    if isinstance(value, (int, float)):
        value = datetime.datetime.fromtimestamp(value)
    if isinstance(value, str):
        value = value.strip()
        for parse_fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                value = datetime.datetime.strptime(value, parse_fmt)
                break
            except ValueError:
                continue
    if hasattr(value, "strftime"):
        try:
            return value.strftime(fmt)
        except Exception:
            return str(value)
    return str(value)


def get_workflow_path(department_name):
    if department_name in WORKFLOW_PATHS:
        return WORKFLOW_PATHS[department_name]
    return [department_name] if department_name else []


def next_workflow_stage(department_name, current_stage):
    path = get_workflow_path(department_name)
    if not path:
        return None
    if not current_stage:
        return path[0]
    try:
        current_index = path.index(current_stage)
        return path[current_index + 1] if current_index + 1 < len(path) else None
    except ValueError:
        return path[0]


def send_email(to_address, subject, body):
    if not to_address:
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    mail_from = app.config.get("MAIL_FROM") or os.getenv("MAIL_FROM", "no-reply@utas.edu.gh")
    msg["From"] = mail_from
    msg["To"] = to_address
    msg.set_content(body)
    try:
        mail_server = app.config.get("MAIL_SERVER") or os.getenv("MAIL_SERVER", "localhost")
        mail_port = int(app.config.get("MAIL_PORT", os.getenv("MAIL_PORT", "1025")))
        mail_use_tls = str(app.config.get("MAIL_USE_TLS", os.getenv("MAIL_USE_TLS", "false"))).lower() in {"1", "true", "yes"}
        mail_username = app.config.get("MAIL_USERNAME") or os.getenv("MAIL_USERNAME", "")
        mail_password = app.config.get("MAIL_PASSWORD") or os.getenv("MAIL_PASSWORD", "")
        server = smtplib.SMTP(mail_server, mail_port, timeout=10)
        if mail_use_tls:
            server.starttls()
        if mail_username and mail_password:
            server.login(mail_username, mail_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"[MAIL ERROR] {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════
#  ACCESS DECORATORS  (Section 4.4 - Role-based access control)
# ══════════════════════════════════════════════════════════════════════════

def login_required(f):
    """Redirect to login if user is not in session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Allow admin, registrar, and department-manager users to access admin routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = session.get("user")
        role = user.get("role") if user else None
        if user is None or role not in {"admin", "registrar", "manager"}:
            flash("Access denied. Administrators only.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def roles_required(*roles):
    """Restrict a route to the given set of roles (e.g. Admin/Registrar only)."""
    allowed = set(roles)
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = session.get("user")
            role = user.get("role") if user else None
            if user is None or role not in allowed:
                flash("Access denied. You do not have permission to perform this action.", "danger")
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return decorated
    return decorator


# Department create/edit/delete and sub-admin approval are both restricted to
# Admin + Registrar (not plain sub-admins/managers).
department_admin_required = roles_required("admin", "registrar")
staff_management_required = roles_required("admin", "registrar")

# Editing another sub-admin's account (e.g. resetting their password) is
# reserved for the top-level admin only — even the Registrar cannot do this.
admin_only_required = roles_required("admin")


def get_admin_department_ids(cursor, user):
    """Return the list of department IDs a sub-admin (registrar/manager) may access.

    Full admins are not scoped, so callers should check role == 'admin' first
    and skip filtering entirely in that case.
    """
    cursor.execute(
        """
        SELECT id FROM departments WHERE primary_admin_id=%s OR sub_admin_id=%s
        UNION
        SELECT department_id FROM department_admins WHERE user_id=%s
        """,
        (user["id"], user["id"], user["id"])
    )
    return [row["id"] for row in cursor.fetchall()]


# ══════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES  (Figure 4.1, 4.2, 4.3 in thesis)
# ══════════════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    """
    LOGIN PAGE - Figure 4.1 & 4.2
    Accepts institutional email, password, and role selection.
    Wrong credentials show access denial (Figure 4.2).
    """
    if "user" in session:
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        role     = request.form.get("role", "student")

        conn = get_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            # Merge admin, registrar, and department-manager users into the same login option.
            if role == "admin":
                cursor.execute(
                    "SELECT * FROM users WHERE email=%s AND role IN ('admin','registrar','manager')",
                    (email,)
                )
            else:
                cursor.execute(
                    "SELECT * FROM users WHERE email=%s AND role=%s",
                    (email, role)
                )
            user = cursor.fetchone()
            cursor.close()
            conn.close()

            if user and check_password_hash(user["password"], password):
                user_status = user.get("status") or "active"
                if user_status == "blocked":
                    error = "Your account has been blocked due to a policy violation. Please contact the administration."
                    return render_template("login.html", error=error)
                if role == "admin" and user_status != "active":
                    if user_status == "pending":
                        error = "Your staff account is awaiting approval by a system administrator."
                    else:
                        error = "Invalid email, password, or role. Access denied."
                    return render_template("login.html", error=error)
                session["user"] = {
                    "id":       user["id"],
                    "fullname": user["fullname"],
                    "email":    user["email"],
                    "role":     user["role"],
                    "student_id": user.get("student_id", ""),
                    "passport_photo": user.get("passport_photo"),
                    "phone": user.get("phone",""),
                    "level": user.get("level","")
                }
                flash(f"Welcome back, {user['fullname']}!", "success")
                return redirect(url_for("dashboard"))
            else:
                error = "Invalid email, password, or role. Access denied."

    return render_template("login.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    STUDENT SIGNUP PAGE - Figure 4.3
    New students register with fullname, student ID, email and password.
    """
    error = None
    if request.method == "POST":
        fullname   = request.form.get("fullname", "").strip()
        student_id = request.form.get("student_id", "").strip()
        phone      = request.form.get("phone", "").strip()
        level      = request.form.get("level", "").strip()
        email      = request.form.get("email", "").strip()
        password   = request.form.get("password", "").strip()
        confirm    = request.form.get("confirm_password", "").strip()

        # Validate required
        if not all([fullname, student_id, email, password, confirm]):
            error = "All fields are required."
        # Student ID must be digits between 10 and 12
        elif not student_id.isdigit() or not (10 <= len(student_id) <= 12):
            error = "Student ID must be 10 to 12 digits."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            conn = get_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)
                try:
                    cursor.execute("""
                        INSERT INTO users (fullname, student_id, email, password, role, phone, level)
                        VALUES (%s, %s, %s, %s, 'student', %s, %s)
                    """, (fullname, student_id, email, generate_password_hash(password), phone or None, level or None))
                    conn.commit()
                    flash("Registration successful! Please log in.", "success")
                    return redirect(url_for("login"))
                except Exception as e:
                    error = "Email or Student ID already registered."
                finally:
                    cursor.close()
                    conn.close()

    return render_template("register.html", error=error)


def registrar_slot_taken(cursor):
    """True if a Registrar account already exists (active or awaiting approval).

    The Registrar is a single system-wide office — only one person may hold
    or be requesting it at a time.
    """
    cursor.execute("SELECT COUNT(*) AS c FROM users WHERE role='registrar' AND status IN ('active','pending')")
    return cursor.fetchone()["c"] > 0


@app.route("/register/staff", methods=["GET", "POST"])
def register_staff():
    """
    STAFF / SUB-ADMIN ACCESS REQUEST
    Department staff request either a Registrar account (a single, system-wide
    office with near-admin access — only available while the slot is open) or
    a Department Sub-admin account scoped to one office. Either way the
    account is created with status='pending' and cannot log in until a
    system administrator or the Registrar approves it (see /admin/staff).
    """
    error = None
    conn = get_connection()
    depts = []
    registrar_available = False
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM departments ORDER BY name")
        depts = cursor.fetchall()
        registrar_available = not registrar_slot_taken(cursor)
        cursor.close()
        conn.close()

    if request.method == "POST":
        fullname   = request.form.get("fullname", "").strip()
        email      = request.form.get("email", "").strip()
        password   = request.form.get("password", "").strip()
        confirm    = request.form.get("confirm_password", "").strip()
        requested_role = request.form.get("requested_role", "manager")
        if requested_role not in ("registrar", "manager"):
            requested_role = "manager"
        department_id = request.form.get("department_id") or None

        if not all([fullname, email, password, confirm]):
            error = "All fields are required."
        elif requested_role == "manager" and not department_id:
            error = "Please select the department you support."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            conn = get_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)
                if requested_role == "registrar" and registrar_slot_taken(cursor):
                    error = "The Registrar position is currently filled or already has a pending request. Please register as a Department Sub-admin instead."
                    cursor.close()
                    conn.close()
                else:
                    try:
                        cursor.execute("""
                            INSERT INTO users (fullname, email, password, role, status, requested_department_id)
                            VALUES (%s, %s, %s, %s, 'pending', %s)
                        """, (fullname, email, generate_password_hash(password), requested_role,
                              department_id if requested_role == "manager" else None))
                        conn.commit()
                        flash("Your staff access request has been submitted. A system administrator will review and approve your account before you can log in.", "success")
                        return redirect(url_for("login"))
                    except Exception:
                        error = "Email already registered."
                    finally:
                        cursor.close()
                        conn.close()

    return render_template("register_staff.html", error=error, depts=depts, registrar_available=registrar_available)


@app.route("/logout")
def logout():
    """Clear session and redirect to login."""
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("login"))


# ══════════════════════════════════════════════════════════════════════════
#  DASHBOARD  (Figure 4.4 - Admin | Figure 4.5 - Student)
# ══════════════════════════════════════════════════════════════════════════

@app.route("/dashboard")
@login_required
def dashboard():
    """
    DASHBOARD - Figure 4.4 (Admin) & Figure 4.5 (Student)
    Shows stats summary and recent complaints.
    Admins see all; students see only their own.
    """
    user = session["user"]
    conn = get_connection()
    stats  = {"total": 0, "pending": 0, "notify": 0, "in_progress": 0, "resolved": 0}
    recent = []

    if conn:
        cursor = conn.cursor(dictionary=True)

        if user["role"] in {"admin", "registrar", "manager"}:
            if user["role"] == "manager":
                department_ids = get_admin_department_ids(cursor, user)
                if department_ids:
                    placeholders = ", ".join(["%s"] * len(department_ids))
                    query = f"""
                        SELECT c.*, u.fullname AS student_name, d.name AS dept_name
                        FROM complaints c
                        LEFT JOIN users u ON c.student_id = u.id
                        LEFT JOIN departments d ON c.department_id = d.id
                        WHERE c.department_id IN ({placeholders})
                        ORDER BY c.created_at DESC LIMIT 10
                    """
                    cursor.execute(query, tuple(department_ids))
                    recent = cursor.fetchall()

                    cursor.execute(
                        f"SELECT COUNT(*) AS t FROM complaints WHERE department_id IN ({placeholders})",
                        tuple(department_ids)
                    )
                    stats["total"] = cursor.fetchone()["t"]
                    cursor.execute(
                        f"SELECT COUNT(*) AS t FROM complaints WHERE department_id IN ({placeholders}) AND status='Pending'",
                        tuple(department_ids)
                    )
                    stats["pending"] = cursor.fetchone()["t"]
                    cursor.execute(
                        f"SELECT COUNT(*) AS t FROM complaints WHERE department_id IN ({placeholders}) AND status='Notify'",
                        tuple(department_ids)
                    )
                    stats["notify"] = cursor.fetchone()["t"]
                    cursor.execute(
                        f"SELECT COUNT(*) AS t FROM complaints WHERE department_id IN ({placeholders}) AND status='In Progress'",
                        tuple(department_ids)
                    )
                    stats["in_progress"] = cursor.fetchone()["t"]
                    cursor.execute(
                        f"SELECT COUNT(*) AS t FROM complaints WHERE department_id IN ({placeholders}) AND status='Resolved'",
                        tuple(department_ids)
                    )
                    stats["resolved"] = cursor.fetchone()["t"]
                else:
                    recent = []
                    stats = {"total": 0, "pending": 0, "notify": 0, "in_progress": 0, "resolved": 0}
            else:
                # Unscoped access: admin and registrar both see every complaint.
                cursor.execute("""
                    SELECT c.*, u.fullname AS student_name, d.name AS dept_name
                    FROM complaints c
                    LEFT JOIN users u ON c.student_id = u.id
                    LEFT JOIN departments d ON c.department_id = d.id
                    ORDER BY c.created_at DESC LIMIT 10
                """)
                recent = cursor.fetchall()

                cursor.execute("SELECT COUNT(*) AS t FROM complaints")
                stats["total"] = cursor.fetchone()["t"]
                cursor.execute("SELECT COUNT(*) AS t FROM complaints WHERE status='Pending'")
                stats["pending"] = cursor.fetchone()["t"]
                cursor.execute("SELECT COUNT(*) AS t FROM complaints WHERE status='Notify'")
                stats["notify"] = cursor.fetchone()["t"]
                cursor.execute("SELECT COUNT(*) AS t FROM complaints WHERE status='In Progress'")
                stats["in_progress"] = cursor.fetchone()["t"]
                cursor.execute("SELECT COUNT(*) AS t FROM complaints WHERE status='Resolved'")
                stats["resolved"] = cursor.fetchone()["t"]

        else:
            # Student: only their complaints
            uid = user["id"]
            cursor.execute("""
                SELECT c.*, d.name AS dept_name
                FROM complaints c
                LEFT JOIN departments d ON c.department_id = d.id
                WHERE c.student_id=%s
                ORDER BY c.created_at DESC LIMIT 10
            """, (uid,))
            recent = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) AS t FROM complaints WHERE student_id=%s", (uid,))
            stats["total"] = cursor.fetchone()["t"]
            cursor.execute("SELECT COUNT(*) AS t FROM complaints WHERE student_id=%s AND status='Pending'", (uid,))
            stats["pending"] = cursor.fetchone()["t"]
            cursor.execute("SELECT COUNT(*) AS t FROM complaints WHERE student_id=%s AND status='Notify'", (uid,))
            stats["notify"] = cursor.fetchone()["t"]
            cursor.execute("SELECT COUNT(*) AS t FROM complaints WHERE student_id=%s AND status='In Progress'", (uid,))
            stats["in_progress"] = cursor.fetchone()["t"]
            cursor.execute("SELECT COUNT(*) AS t FROM complaints WHERE student_id=%s AND status='Resolved'", (uid,))
            stats["resolved"] = cursor.fetchone()["t"]

        cursor.close()
        conn.close()

    return render_template("dashboard.html",
                           user=user, stats=stats, recent=recent)


# ══════════════════════════════════════════════════════════════════════════
#  COMPLAINT ROUTES  (Appendix B & C)
# ══════════════════════════════════════════════════════════════════════════

@app.route("/submit", methods=["GET", "POST"])
@login_required
def submit_complaint():
    """
    COMPLAINT SUBMISSION - Appendix B
    Students fill subject, department, priority, description.
    System inserts record with status=Pending and timestamps.
    Pseudocode from Section 3.13 implemented here.
    """
    user  = session["user"]
    depts = []
    error = None

    conn = get_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM departments ORDER BY name")
        depts = cursor.fetchall()
        cursor.close()
        conn.close()

    if request.method == "POST":
        subject    = request.form.get("subject", "").strip()
        complaint  = request.form.get("complaint", "").strip()
        dept_id    = request.form.get("department_id")
        nature_of_problem = request.form.get("nature_of_problem", "").strip()
        priority   = request.form.get("priority", "Normal")
        anonymous  = 1 if request.form.get("anonymous") else 0
        attachment_filename = None
        attachment_file = request.files.get("attachment")

        if attachment_file and attachment_file.filename:
            if allowed_file(attachment_file.filename):
                original_name = secure_filename(attachment_file.filename)
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                attachment_filename = f"{timestamp}_{user['id']}_{original_name}"
                attachment_path = os.path.join(app.config["UPLOAD_FOLDER"], attachment_filename)
                attachment_file.save(attachment_path)
            else:
                error = "Only PDF, JPG, JPEG, PNG, DOC, and DOCX files are allowed for attachments."

        faculty = request.form.get("faculty", "").strip()
        program = request.form.get("program", "").strip()
        dept_name = None
        if dept_id and depts:
            for d in depts:
                if str(d["id"]) == str(dept_id):
                    dept_name = d["name"]
                    break

        office_stage = None
        if dept_name in WORKFLOW_PATHS:
            office_stage = next_workflow_stage(dept_name, None)

        # A school with no listed programmes (e.g. Graduate Studies & Research)
        # has no cascading options, so programme is not required for it.
        program_required = bool(SCHOOLS.get(faculty))

        # VALIDATE - Section 3.13 pseudocode
        if not subject or not complaint or not dept_id or not faculty or not nature_of_problem:
            error = error or "Please complete all required fields."
        elif program_required and not program:
            error = error or "Please select your programme/department."
        else:
            conn = get_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    INSERT INTO complaints
                        (student_id, department_id, faculty, program, subject, complaint, priority, status, anonymous, attachment, office_stage, nature_of_problem)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pending', %s, %s, %s, %s)
                """, (user["id"], dept_id, faculty, program, subject, complaint, priority, anonymous, attachment_filename, office_stage, nature_of_problem))
                conn.commit()
                cursor.close()
                conn.close()
                flash("Complaint submitted successfully! You will be notified of updates.", "success")
                return redirect(url_for("my_complaints"))

    return render_template("dashboard/submit_complaint.html",
                           user=user, depts=depts, faculties=FACULTIES, error=error,
                           schools_json=json.dumps(SCHOOLS), nature_options=NATURE_OF_PROBLEMS)


@app.route("/my-complaints")
@login_required
def my_complaints():
    """
    COMPLAINT VIEWING - Appendix C
    Shows all complaints for the logged-in student with status badges.
    """
    user       = session["user"]
    complaints = []

    search = request.args.get("search", "").strip()
    status = request.args.get("status", "")
    conn = get_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        if user["role"] == "student":
            query = """
                SELECT c.*, d.name AS dept_name,
                       f.reply, f.reply_date
                FROM complaints c
                LEFT JOIN departments d ON c.department_id = d.id
                LEFT JOIN feedback f    ON f.complaint_id  = c.id
                WHERE c.student_id=%s
            """
            params = [user["id"]]
            if status:
                query += " AND c.status=%s"
                params.append(status)
            if search:
                query += " AND (c.subject LIKE %s OR c.complaint LIKE %s)"
                params.extend([f"%{search}%", f"%{search}%"])
            query += " ORDER BY c.created_at DESC"
            cursor.execute(query, tuple(params))
        else:
            # Admin can also view all
            query = """
                SELECT c.*, d.name AS dept_name,
                       u.fullname AS student_name,
                       f.reply, f.reply_date
                FROM complaints c
                LEFT JOIN departments d ON c.department_id = d.id
                LEFT JOIN users u       ON c.student_id    = u.id
                LEFT JOIN feedback f    ON f.complaint_id  = c.id
                ORDER BY c.created_at DESC
            """
            cursor.execute(query)
        complaints = cursor.fetchall()
        cursor.close()
        conn.close()

    return render_template("dashboard/student/my_complaints.html",
                           user=user, complaints=complaints, search=search, status=status)


# ══════════════════════════════════════════════════════════════════════════
#  FEEDBACK ROUTES  (Appendix E - Figure 4.6)
# ══════════════════════════════════════════════════════════════════════════

@app.route("/feedback")
@login_required
def feedback():
    """
    FEEDBACK PAGE - Figure 4.6 & Appendix E
    Students see admin replies on their complaints.
    """
    user    = session["user"]
    entries = []

    conn = get_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.subject, c.status, c.created_at,
                   c.office_stage, f.reply, f.reply_date,
                   u.fullname AS admin_name,
                   d.name AS dept_name
            FROM complaints c
            LEFT JOIN feedback f    ON f.complaint_id = c.id
            LEFT JOIN users u       ON f.admin_id     = u.id
            LEFT JOIN departments d ON c.department_id = d.id
            WHERE c.student_id=%s
            ORDER BY c.created_at DESC
        """, (user["id"],))
        entries = cursor.fetchall()
        cursor.close()
        conn.close()

    return render_template("dashboard/feedback.html",
                           user=user, entries=entries)


@app.route("/admin/respond/<int:complaint_id>", methods=["POST"])
@admin_required
def respond_complaint(complaint_id):
    """
    ADMIN FEEDBACK - Appendix E.3 & E.4
    Admin/registrar/manager writes a reply, updates status/workflow stage,
    and may forward the complaint to a different department/office entirely
    (e.g. SRC -> Dean of Students Affairs) so that office's staff gain
    visibility and can pick it up.
    """
    admin_id     = session["user"]["id"]
    admin_name   = session["user"]["fullname"]
    reply        = request.form.get("reply", "").strip()
    new_status   = request.form.get("status", "In Progress")
    office_stage = request.form.get("office_stage") or None
    forward_department_id = request.form.get("forward_department_id") or None

    conn = get_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.subject, c.department_id, c.office_stage, c.nature_of_problem, u.email, u.fullname
            FROM complaints c
            JOIN users u ON c.student_id = u.id
            WHERE c.id=%s
        """, (complaint_id,))
        complaint_info = cursor.fetchone()

        if session["user"]["role"] == "manager":
            scoped_department_ids = get_admin_department_ids(cursor, session["user"])
            if not complaint_info or complaint_info.get("department_id") not in scoped_department_ids:
                cursor.close()
                conn.close()
                flash("Access denied. That complaint is not assigned to your department.", "danger")
                return redirect(url_for("admin_complaints"))

        current_department_id = complaint_info.get("department_id") if complaint_info else None
        is_forward = bool(forward_department_id) and str(forward_department_id) != str(current_department_id)
        forward_note = None
        new_department_name = None

        if is_forward:
            cursor.execute("SELECT name FROM departments WHERE id=%s", (forward_department_id,))
            target_dept = cursor.fetchone()
            if not target_dept:
                cursor.close()
                conn.close()
                flash("Selected office not found.", "danger")
                return redirect(url_for("admin_complaints"))
            new_department_name = target_dept["name"]

            source_dept_name = None
            if current_department_id:
                cursor.execute("SELECT name FROM departments WHERE id=%s", (current_department_id,))
                source_row = cursor.fetchone()
                source_dept_name = source_row["name"] if source_row else None

            # The receiving office starts its own workflow fresh.
            office_stage = None
            cursor.execute(
                "UPDATE complaints SET department_id=%s, status=%s, office_stage=%s WHERE id=%s",
                (forward_department_id, new_status, office_stage, complaint_id)
            )
            forward_note = f"Forwarded from {source_dept_name or 'Unassigned'} to {new_department_name} by {admin_name}."
        elif office_stage:
            cursor.execute(
                "UPDATE complaints SET status=%s, office_stage=%s WHERE id=%s",
                (new_status, office_stage, complaint_id)
            )
        else:
            cursor.execute(
                "UPDATE complaints SET status=%s WHERE id=%s",
                (new_status, complaint_id)
            )

        history_note = f"{forward_note} {reply}".strip() if forward_note else reply

        if history_note:
            cursor.execute(
                "SELECT id FROM feedback WHERE complaint_id=%s", (complaint_id,)
            )
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    "UPDATE feedback SET reply=%s, admin_id=%s, reply_date=CURRENT_TIMESTAMP WHERE complaint_id=%s",
                    (history_note, admin_id, complaint_id)
                )
            else:
                cursor.execute("""
                    INSERT INTO feedback (complaint_id, admin_id, reply, reply_date)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                """, (complaint_id, admin_id, history_note))
            # record into feedback_history for audit and reply history
            cursor.execute(
                "INSERT INTO feedback_history (complaint_id, admin_id, reply, reply_date) VALUES (%s, %s, %s, CURRENT_TIMESTAMP)",
                (complaint_id, admin_id, history_note)
            )

        conn.commit()

        email_sent = False
        if complaint_info and complaint_info.get("email"):
            department_name = new_department_name
            if not department_name and complaint_info.get("department_id"):
                cursor.execute("SELECT name FROM departments WHERE id=%s", (complaint_info["department_id"],))
                dept_row = cursor.fetchone()
                if dept_row:
                    department_name = dept_row["name"]

            email_body = [
                f"Hello {complaint_info.get('fullname', 'Student')},",
                "",
                f"Your complaint '{complaint_info.get('subject', 'No subject')}' has been updated.",
                f"Current status: {new_status}."
            ]
            if is_forward:
                email_body.append(f"Your complaint has been forwarded to: {new_department_name}.")
            elif office_stage:
                email_body.append(f"Current workflow stage: {office_stage}.")
            elif department_name:
                email_body.append(f"Department: {department_name}.")
            if complaint_info.get("nature_of_problem"):
                email_body.append(f"Nature of problem: {complaint_info['nature_of_problem']}.")
            if reply:
                email_body.append("")
                email_body.append("Admin comment:")
                email_body.append(reply)
            email_body.append("")
            email_body.append("Please log in to your dashboard to view the full details.")
            email_sent = send_email(
                complaint_info["email"],
                f"Complaint Update: {complaint_info.get('subject', 'Your complaint')}",
                "\n".join(email_body)
            )

        cursor.close()
        conn.close()
        message = f"Complaint forwarded to {new_department_name}." if is_forward else "Complaint updated successfully."
        if email_sent:
            message += " An email notification has been sent to the student."
        flash(message, "success")

    return redirect(url_for("admin_complaints"))


@app.route('/admin/feedback_history/<int:complaint_id>')
@admin_required
def feedback_history(complaint_id):
    """Return JSON list of historical replies for a complaint."""
    conn = get_connection()
    items = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT fh.*, u.fullname AS admin_name FROM feedback_history fh LEFT JOIN users u ON fh.admin_id = u.id WHERE fh.complaint_id=%s ORDER BY fh.reply_date DESC", (complaint_id,))
        items = cursor.fetchall()
        cursor.close()
        conn.close()
    return jsonify(items)


@app.route("/admin/complaints")
@admin_required
def admin_complaints():
    """Admin view of ALL complaints with respond controls."""
    user       = session["user"]
    complaints = []
    depts      = []

    conn = get_connection()
    # Pagination parameters to speed up listing
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 10)), 50)

    if conn:
        cursor = conn.cursor(dictionary=True)
        status_filter = request.args.get("status", "")
        department_filter = request.args.get("department_id", "")
        faculty_filter = request.args.get("faculty", "")
        keyword = request.args.get("keyword", "").strip()

        filters = []
        params = []
        if status_filter:
            filters.append("c.status=%s")
            params.append(status_filter)
        if department_filter:
            filters.append("c.department_id=%s")
            params.append(department_filter)
        if faculty_filter:
            filters.append("c.faculty LIKE %s")
            params.append(f"%{faculty_filter}%")
        if keyword:
            filters.append("(c.subject LIKE %s OR c.complaint LIKE %s OR u.fullname LIKE %s)")
            params.extend([f"%{keyword}%"] * 3)

        scoped_department_ids = None
        if user["role"] == "manager":
            scoped_department_ids = get_admin_department_ids(cursor, user)
            if scoped_department_ids:
                placeholders = ", ".join(["%s"] * len(scoped_department_ids))
                filters.append(f"c.department_id IN ({placeholders})")
                params.extend(scoped_department_ids)
            else:
                filters.append("1=0")

        base_query = """
            SELECT c.*, d.name AS dept_name,
                   u.fullname AS student_name, u.student_id AS s_id,
                   f.reply, f.reply_date
            FROM complaints c
            LEFT JOIN departments d ON c.department_id = d.id
            LEFT JOIN users u       ON c.student_id    = u.id
            LEFT JOIN feedback f    ON f.complaint_id  = c.id
        """
        if filters:
            base_query += " WHERE " + " AND ".join(filters)
        base_query += " ORDER BY c.created_at DESC"

        # Count total for pagination
        count_query = "SELECT COUNT(*) AS total FROM (" + base_query + ") AS sub"
        cursor.execute(count_query, tuple(params))
        count_row = cursor.fetchone()
        total = count_row["total"] if count_row else 0

        # Apply limit/offset for pagination
        offset = (page - 1) * per_page
        paged_query = base_query + " LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        cursor.execute(paged_query, tuple(params))
        complaints = cursor.fetchall()
        cursor.execute("SELECT * FROM departments ORDER BY name")
        depts = cursor.fetchall()
        for complaint in complaints:
            complaint["workflow_path"] = get_workflow_path(complaint.get("dept_name"))
            complaint["next_stage"] = next_workflow_stage(complaint.get("dept_name"), complaint.get("office_stage"))
        cursor.close()
        conn.close()

    filter_values = {
        "status": request.args.get("status", ""),
        "department_id": request.args.get("department_id", ""),
        "faculty": request.args.get("faculty", ""),
        "keyword": request.args.get("keyword", "")
    }

    pagination = {
        "page": page,
        "per_page": per_page,
        "total": total if 'total' in locals() else len(complaints)
    }

    return render_template("dashboard/admin/admin_complaints.html",
                           user=user, complaints=complaints, depts=depts, filters=filter_values, pagination=pagination)


@app.route('/admin/complaints/export')
@admin_required
def export_complaints():
    """Export complaints/feedback to CSV or Excel-like HTML table."""
    fmt = request.args.get('format', 'csv')
    status = request.args.get('status', '')
    department_id = request.args.get('department_id', '')
    faculty = request.args.get('faculty', '')
    keyword = request.args.get('keyword', '').strip()

    conn = get_connection()
    rows = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT c.id, c.subject, c.complaint, c.priority, c.status, c.created_at,
                   d.name AS dept_name, u.fullname AS student_name, f.reply, f.reply_date
            FROM complaints c
            LEFT JOIN departments d ON c.department_id = d.id
            LEFT JOIN users u       ON c.student_id    = u.id
            LEFT JOIN feedback f    ON f.complaint_id  = c.id
        """
        filters = []
        params = []
        if status:
            filters.append("c.status=%s")
            params.append(status)
        if department_id:
            filters.append("c.department_id=%s")
            params.append(department_id)
        if faculty:
            filters.append("c.faculty LIKE %s")
            params.append(f"%{faculty}%")
        if keyword:
            filters.append("(c.subject LIKE %s OR c.complaint LIKE %s OR u.fullname LIKE %s)")
            params.extend([f"%{keyword}%"]*3)
        if session["user"]["role"] == "manager":
            scoped_department_ids = get_admin_department_ids(cursor, session["user"])
            if scoped_department_ids:
                placeholders = ", ".join(["%s"] * len(scoped_department_ids))
                filters.append(f"c.department_id IN ({placeholders})")
                params.extend(scoped_department_ids)
            else:
                filters.append("1=0")
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY c.created_at DESC"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

    # CSV export
    import csv
    from io import StringIO
    si = StringIO()
    cw = csv.writer(si)
    headers = ["ID","Subject","Complaint","Priority","Status","Submitted","Department","Student","AdminReply","ReplyDate"]
    cw.writerow(headers)
    for r in rows:
        cw.writerow([r.get('id'), r.get('subject'), r.get('complaint'), r.get('priority'), r.get('status'), r.get('created_at'), r.get('dept_name'), r.get('student_name'), r.get('reply'), r.get('reply_date')])

    output = si.getvalue()
    if fmt == 'excel':
        # Serve as HTML table which Excel can open
        keys = ['id','subject','complaint','priority','status','created_at','dept_name','student_name','reply','reply_date']
        html = ['<table>']
        html.append('<tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr>')
        for r in rows:
            html.append('<tr>' + ''.join(f'<td>{(r.get(k) or "")}</td>' for k in keys) + '</tr>')
        html.append('</table>')
        resp = app.response_class('\n'.join(html), mimetype='application/vnd.ms-excel')
        resp.headers['Content-Disposition'] = 'attachment; filename=complaints.xls'
        return resp

    if fmt == 'pdf':
        # Generate a simple PDF using reportlab. This avoids system wkhtmltopdf deps.
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
            from io import BytesIO

            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            data = [headers]
            for r in rows:
                data.append([r.get('id'), r.get('subject'), r.get('complaint') or '', r.get('priority'), r.get('status'), str(r.get('created_at') or ''), r.get('dept_name') or '', r.get('student_name') or '', r.get('reply') or '', str(r.get('reply_date') or '')])

            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f0f0f0')),
                ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            doc.build([table])
            buffer.seek(0)
            resp = app.response_class(buffer.read(), mimetype='application/pdf')
            resp.headers['Content-Disposition'] = 'attachment; filename=complaints.pdf'
            return resp
        except Exception as e:
            return f'PDF export requires the reportlab package to be installed: {e}', 500

    resp = app.response_class(output, mimetype='text/csv')
    resp.headers['Content-Disposition'] = 'attachment; filename=complaints.csv'
    return resp


@app.route("/admin/update-status/<int:complaint_id>", methods=["POST"])
@admin_required
def update_status(complaint_id):
    """Quick status update from admin complaint table."""
    new_status = request.form.get("status")
    conn = get_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        if session["user"]["role"] == "manager":
            scoped_department_ids = get_admin_department_ids(cursor, session["user"])
            cursor.execute("SELECT department_id FROM complaints WHERE id=%s", (complaint_id,))
            row = cursor.fetchone()
            if not row or row.get("department_id") not in scoped_department_ids:
                cursor.close()
                conn.close()
                flash("Access denied. That complaint is not assigned to your department.", "danger")
                return redirect(url_for("admin_complaints"))
        cursor.execute(
            "UPDATE complaints SET status=%s WHERE id=%s",
            (new_status, complaint_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
    flash("Status updated.", "success")
    return redirect(url_for("admin_complaints"))


# ══════════════════════════════════════════════════════════════════════════
#  DEPARTMENTS  (Figure 4.8)
# ══════════════════════════════════════════════════════════════════════════

@app.route("/admin/departments", methods=["GET", "POST"])
@department_admin_required
def departments():
    """
    DEPARTMENTS PAGE - Figure 4.8
    Admin can view and add departments for complaint routing.
    """
    user  = session["user"]
    depts = []
    admins = []
    error = None

    conn = get_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            primary_admin_id = request.form.get("primary_admin_id") or None
            sub_admin_id = request.form.get("sub_admin_id") or None
            if not name:
                error = "Department name is required."
            else:
                try:
                    cursor.execute(
                        "INSERT INTO departments (name, primary_admin_id, sub_admin_id) VALUES (%s, %s, %s)",
                        (name, primary_admin_id, sub_admin_id)
                    )
                    conn.commit()
                    flash(f"Department '{name}' added successfully.", "success")
                except Exception:
                    error = "Department already exists."

        cursor.execute(
            """
            SELECT d.*, p.fullname AS primary_admin_name, s.fullname AS sub_admin_name
            FROM departments d
            LEFT JOIN users p ON d.primary_admin_id = p.id
            LEFT JOIN users s ON d.sub_admin_id = s.id
            ORDER BY d.name
            """
        )
        depts = cursor.fetchall()
        cursor.execute("SELECT id, fullname, role FROM users WHERE role IN ('admin','registrar','manager') AND status='active' ORDER BY fullname")
        admins = cursor.fetchall()
        cursor.close()
        conn.close()

    return render_template("dashboard/student/departments.html",
                           user=user, depts=depts, admins=admins, error=error)


@app.route("/admin/departments/edit/<int:dept_id>", methods=["GET", "POST"])
@department_admin_required
def edit_department(dept_id):
    conn = get_connection()
    dept = None
    admins = []
    error = None

    if conn:
        cursor = conn.cursor(dictionary=True)
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            primary_admin_id = request.form.get("primary_admin_id") or None
            sub_admin_id = request.form.get("sub_admin_id") or None
            if not name:
                error = "Department name is required."
            else:
                try:
                    cursor.execute(
                        "UPDATE departments SET name=%s, primary_admin_id=%s, sub_admin_id=%s WHERE id=%s",
                        (name, primary_admin_id, sub_admin_id, dept_id)
                    )
                    conn.commit()
                    flash(f"Department updated to '{name}'.", "success")
                    return redirect(url_for("departments"))
                except Exception as exc:
                    error = f"Unable to update department: {exc}"
        cursor.execute(
            """
            SELECT d.*, p.fullname AS primary_admin_name, s.fullname AS sub_admin_name
            FROM departments d
            LEFT JOIN users p ON d.primary_admin_id = p.id
            LEFT JOIN users s ON d.sub_admin_id = s.id
            WHERE d.id=%s
            """,
            (dept_id,)
        )
        dept = cursor.fetchone()
        cursor.execute("SELECT id, fullname, role FROM users WHERE role IN ('admin','registrar','manager') AND status='active' ORDER BY fullname")
        admins = cursor.fetchall()
        cursor.close()
        conn.close()

    if dept is None:
        flash("Department not found.", "warning")
        return redirect(url_for("departments"))

    return render_template("dashboard/student/departments.html",
                           user=session["user"], depts=[], admins=admins, error=error,
                           editing_department=dept, edit_mode=True)


@app.route("/admin/departments/delete/<int:dept_id>", methods=["POST"])
@department_admin_required
def delete_department(dept_id):
    conn = get_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("UPDATE complaints SET department_id=NULL WHERE department_id=%s", (dept_id,))
            cursor.execute("DELETE FROM departments WHERE id=%s", (dept_id,))
            conn.commit()
            flash("Department removed and complaints were unassigned.", "info")
        except Exception as exc:
            conn.rollback()
            flash(f"Unable to delete department: {exc}", "danger")
        finally:
            cursor.close()
            conn.close()
    return redirect(url_for("departments"))


# ══════════════════════════════════════════════════════════════════════════
#  STAFF / SUB-ADMIN ACCESS MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════

@app.route("/admin/staff")
@staff_management_required
def staff_admin():
    """
    Review pending sub-admin (staff) access requests and manage which
    departments each active staff account can view/respond to.
    """
    conn = get_connection()
    pending = []
    active_staff = []
    depts = []

    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT u.*, d.name AS requested_department_name
            FROM users u
            LEFT JOIN departments d ON u.requested_department_id = d.id
            WHERE u.role IN ('registrar','manager') AND u.status='pending'
            ORDER BY u.created_at DESC
            """
        )
        pending = cursor.fetchall()

        cursor.execute(
            """
            SELECT id, fullname, email, role, status
            FROM users
            WHERE role IN ('registrar','manager') AND status='active'
            ORDER BY fullname
            """
        )
        active_staff = cursor.fetchall()
        for staff in active_staff:
            cursor.execute(
                """
                SELECT d.id, d.name FROM department_admins da
                JOIN departments d ON da.department_id = d.id
                WHERE da.user_id=%s
                ORDER BY d.name
                """,
                (staff["id"],)
            )
            staff["assigned_departments"] = cursor.fetchall()

        cursor.execute("SELECT * FROM departments ORDER BY name")
        depts = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) AS c FROM users WHERE role='registrar' AND status='active'")
        registrar_taken = cursor.fetchone()["c"] > 0
        cursor.close()
        conn.close()

    return render_template("dashboard/admin/staff.html",
                           user=session["user"], pending=pending,
                           active_staff=active_staff, depts=depts,
                           registrar_taken=registrar_taken)


@app.route("/admin/staff/approve/<int:user_id>", methods=["POST"])
@staff_management_required
def approve_staff(user_id):
    """Approve a pending sub-admin request and grant access to the chosen department.

    Registrar is a single system-wide office, so approving a second Registrar
    while one is already active is refused.
    """
    department_id = request.form.get("department_id") or None
    conn = get_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id=%s AND role IN ('registrar','manager')", (user_id,))
        target = cursor.fetchone()
        if not target:
            cursor.close()
            conn.close()
            flash("Staff account not found.", "danger")
            return redirect(url_for("staff_admin"))

        approved_by = session["user"]["fullname"]

        if target["role"] == "registrar":
            cursor.execute(
                "SELECT COUNT(*) AS c FROM users WHERE role='registrar' AND status='active' AND id != %s",
                (user_id,)
            )
            if cursor.fetchone()["c"] > 0:
                cursor.close()
                conn.close()
                flash("A Registrar is already active. Only one Registrar account can be active at a time.", "danger")
                return redirect(url_for("staff_admin"))
            cursor.execute("UPDATE users SET status='active' WHERE id=%s", (user_id,))
            conn.commit()
            cursor.close()
            conn.close()
            email_sent = send_email(
                target["email"],
                "Your UTAS Staff Account Has Been Approved",
                f"Hello {target['fullname']},\n\n"
                f"Your request for Registrar access to the UTAS Complaint Management System "
                f"has been approved by {approved_by}.\n\n"
                f"As Registrar you have system-wide access to view and respond to complaints "
                f"across all offices, and to manage departments and staff accounts.\n\n"
                f"You can now log in at any time using your registered email and password.\n\n"
                f"— UTAS Complaint Management System"
            )
            message = f"{target['fullname']} approved as Registrar."
            if email_sent:
                message += " A notification email has been sent."
            flash(message, "success")
            return redirect(url_for("staff_admin"))

        department_id = department_id or target.get("requested_department_id")
        department_name = None
        cursor.execute("UPDATE users SET status='active' WHERE id=%s", (user_id,))
        if department_id:
            try:
                cursor.execute(
                    "INSERT INTO department_admins (department_id, user_id) VALUES (%s, %s)",
                    (department_id, user_id)
                )
            except Exception:
                pass
            cursor.execute("SELECT name FROM departments WHERE id=%s", (department_id,))
            dept_row = cursor.fetchone()
            department_name = dept_row["name"] if dept_row else None
        conn.commit()
        cursor.close()
        conn.close()
        email_sent = send_email(
            target["email"],
            "Your UTAS Staff Account Has Been Approved",
            f"Hello {target['fullname']},\n\n"
            f"Your request for Department Sub-admin access to the UTAS Complaint Management "
            f"System has been approved by {approved_by}.\n\n"
            f"You now have access to view and respond to complaints for: "
            f"{department_name or 'your assigned office'}.\n\n"
            f"You can now log in at any time using your registered email and password.\n\n"
            f"— UTAS Complaint Management System"
        )
        message = f"{target['fullname']} approved and granted department access."
        if email_sent:
            message += " A notification email has been sent."
        flash(message, "success")
    return redirect(url_for("staff_admin"))


@app.route("/admin/staff/reject/<int:user_id>", methods=["POST"])
@staff_management_required
def reject_staff(user_id):
    """Reject a pending sub-admin request; the account cannot log in."""
    conn = get_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "UPDATE users SET status='rejected' WHERE id=%s AND role IN ('registrar','manager')",
            (user_id,)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash("Staff access request rejected.", "info")
    return redirect(url_for("staff_admin"))


@app.route("/admin/staff/assign/<int:user_id>", methods=["POST"])
@staff_management_required
def assign_staff_department(user_id):
    """Grant an already-active staff account access to an additional department."""
    department_id = request.form.get("department_id")
    conn = get_connection()
    if conn and department_id:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "INSERT INTO department_admins (department_id, user_id) VALUES (%s, %s)",
                (department_id, user_id)
            )
            conn.commit()
            flash("Department access granted.", "success")
        except Exception:
            flash("That staff account already has access to this department.", "info")
        cursor.close()
        conn.close()
    return redirect(url_for("staff_admin"))


@app.route("/admin/staff/unassign/<int:user_id>/<int:dept_id>", methods=["POST"])
@staff_management_required
def unassign_staff_department(user_id, dept_id):
    """Revoke a staff account's access to a department."""
    conn = get_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "DELETE FROM department_admins WHERE user_id=%s AND department_id=%s",
            (user_id, dept_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash("Department access revoked.", "info")
    return redirect(url_for("staff_admin"))


@app.route("/admin/staff/reset-password/<int:user_id>", methods=["POST"])
@admin_only_required
def reset_staff_password(user_id):
    """Set a new password for a sub-admin account. Main admin only — even the
    Registrar cannot edit another sub-admin's account details."""
    new_password = request.form.get("new_password", "").strip()
    confirm = request.form.get("confirm_password", "").strip()

    if len(new_password) < 6:
        flash("New password must be at least 6 characters.", "danger")
        return redirect(url_for("staff_admin"))
    if new_password != confirm:
        flash("Passwords do not match.", "danger")
        return redirect(url_for("staff_admin"))

    conn = get_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "UPDATE users SET password=%s WHERE id=%s AND role IN ('registrar','manager')",
            (generate_password_hash(new_password), user_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash("Password reset successfully.", "success")
    return redirect(url_for("staff_admin"))


# ══════════════════════════════════════════════════════════════════════════
#  STUDENT ACCOUNTS  (misconduct blocking)
# ══════════════════════════════════════════════════════════════════════════

@app.route("/admin/students")
@admin_required
def admin_students():
    """Any admin/registrar/manager can review students and block/unblock accounts."""
    search = request.args.get("search", "").strip()
    conn = get_connection()
    students = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, fullname, student_id, email, phone, level, status, created_at FROM users WHERE role='student'"
        params = []
        if search:
            query += " AND (fullname LIKE %s OR student_id LIKE %s OR email LIKE %s)"
            params.extend([f"%{search}%"] * 3)
        query += " ORDER BY fullname"
        cursor.execute(query, tuple(params))
        students = cursor.fetchall()
        cursor.close()
        conn.close()

    return render_template("dashboard/admin/students.html",
                           user=session["user"], students=students, search=search)


@app.route("/admin/students/block/<int:user_id>", methods=["POST"])
@admin_required
def block_student(user_id):
    """Block a student account for misconduct; blocked students cannot log in."""
    conn = get_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("UPDATE users SET status='blocked' WHERE id=%s AND role='student'", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Student account blocked.", "success")
    return redirect(url_for("admin_students"))


@app.route("/admin/students/unblock/<int:user_id>", methods=["POST"])
@admin_required
def unblock_student(user_id):
    """Restore a previously blocked student's access."""
    conn = get_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("UPDATE users SET status='active' WHERE id=%s AND role='student'", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Student account unblocked.", "success")
    return redirect(url_for("admin_students"))


# ══════════════════════════════════════════════════════════════════════════
#  SETTINGS  (Figure 4.7 - Appendix D)
# ══════════════════════════════════════════════════════════════════════════

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """
    SETTINGS PAGE - Figure 4.7 & Appendix D
    Users update fullname, email, password, and upload passport photo.
    """
    user  = session["user"]
    error = None

    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm  = request.form.get("confirm_password", "").strip()
        phone    = request.form.get("phone", "").strip()
        level    = request.form.get("level", "").strip()
        passport_file = request.files.get("passport_photo")

        if not fullname or not email:
            error = "Name and email are required."
        elif password and password != confirm:
            error = "Passwords do not match."
        else:
            # Handle passport photo upload
            passport_photo_path = None
            if passport_file and passport_file.filename:
                if passport_file.filename.lower().split('.')[-1] not in {"png", "jpg", "jpeg"}:
                    error = "Passport photo must be PNG or JPG format."
                else:
                    filename = secure_filename(f"passport_{user['id']}_{os.urandom(4).hex()}.{passport_file.filename.lower().split('.')[-1]}")
                    try:
                        passport_file.save(os.path.join(app.config["PASSPORT_UPLOAD_FOLDER"], filename))
                        passport_photo_path = filename
                    except Exception as e:
                        error = f"Failed to upload passport photo: {str(e)}"
            
            if not error:
                conn = get_connection()
                if conn:
                    cursor = conn.cursor(dictionary=True)
                    
                    if password:
                        if passport_photo_path:
                            cursor.execute("""
                                UPDATE users SET fullname=%s, email=%s, password=%s, passport_photo=%s, phone=%s, level=%s
                                WHERE id=%s
                            """, (fullname, email,
                                  generate_password_hash(password), passport_photo_path, phone or None, level or None, user["id"]))
                        else:
                            cursor.execute("""
                                UPDATE users SET fullname=%s, email=%s, password=%s, phone=%s, level=%s
                                WHERE id=%s
                            """, (fullname, email,
                                  generate_password_hash(password), phone or None, level or None, user["id"]))
                    else:
                        if passport_photo_path:
                            cursor.execute("""
                                UPDATE users SET fullname=%s, email=%s, passport_photo=%s, phone=%s, level=%s WHERE id=%s
                            """, (fullname, email, passport_photo_path, phone or None, level or None, user["id"]))
                        else:
                            cursor.execute("""
                                UPDATE users SET fullname=%s, email=%s, phone=%s, level=%s WHERE id=%s
                            """, (fullname, email, phone or None, level or None, user["id"]))
                    conn.commit()
                    cursor.close()
                    conn.close()

                    # Update session
                    session["user"]["fullname"] = fullname
                    session["user"]["email"]    = email
                    if passport_photo_path:
                        session["user"]["passport_photo"] = passport_photo_path
                    # Update phone/level in session
                    session["user"]["phone"] = phone or session["user"].get("phone", "")
                    session["user"]["level"] = level or session["user"].get("level", "")
                    session.modified = True
                    flash("Profile updated successfully.", "success")
                    return redirect(url_for("settings"))

    return render_template("dashboard/settings.html", user=user, error=error)


# ══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 55)
    print("  UTAS Student Complaint Management System")
    print("  Author : Matri Daniel")
    print("  ID     : 20220404014")
    print("=" * 55)
    init_database()   # Create DB and tables on first run
    print("  Running at: http://127.0.0.1:5000")
    print("  Default admin: admin@utas.edu.gh / admin123")
    print("=" * 55)
    app.run(debug=True, port=5000)

import os
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
