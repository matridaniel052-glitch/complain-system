# TECHNICAL SPECIFICATION DOCUMENT
## UTAS Student Complaint Management System

**Document Version**: 1.0  
**Date**: 2025-06-12  
**Author**: Development Team  
**Status**: Final Implementation

---

## 1. EXECUTIVE SUMMARY

This document provides comprehensive technical specifications for the UTAS Student Complaint Management System. The system is a web-based application developed using Python/Flask, implementing a relational MySQL database architecture to manage student complaint submissions, tracking, and administrative responses.

The system architecture follows a three-tier model:
- **Presentation Tier**: Flask templating with HTML5/CSS3/JavaScript
- **Business Logic Tier**: Python Flask application with role-based access control
- **Data Tier**: MySQL relational database with structured schema

---

## 2. SYSTEM ARCHITECTURE

### 2.1 Technology Stack

| **Component** | **Technology** |
|--------------|-----------------|
| Backend Framework | Flask 3.0.0 |
| Server Language | Python 3.x |
| Database | MySQL 5.7+ |
| Template Engine | Jinja2 |
| ORM/Database Driver | mysql-connector-python 8.3.0 |
| Security | Werkzeug 3.0.1 |
| Session Management | flask-session 0.6.0 |
| File Upload | Werkzeug secure filename |

### 2.2 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   CLIENT LAYER                          │
│  (Web Browser: HTML5, CSS3, JavaScript)                │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                PRESENTATION LAYER                        │
│  Flask Routes & Jinja2 Templates                        │
│  - Authentication Pages                                │
│  - Student Dashboard & Forms                           │
│  - Admin Dashboard & Management                        │
│  - Real-time Notifications                             │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│               BUSINESS LOGIC LAYER                       │
│  Flask Application (app.py)                            │
│  - Route Handlers                                      │
│  - Authentication & Authorization                     │
│  - Workflow Management                                │
│  - Email Notifications                                │
│  - File Upload Processing                             │
│  - Session Management                                 │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                DATA ACCESS LAYER                         │
│  MySQL Connector (database.py)                         │
│  - Connection Management                              │
│  - SQL Query Execution                                │
│  - Transaction Handling                               │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              DATABASE LAYER                              │
│  MySQL (srccom_db)                                     │
│  - Users Table                                        │
│  - Departments Table                                  │
│  - Complaints Table                                   │
│  - Feedback Table                                     │
└─────────────────────────────────────────────────────────┘
```

---

## 3. DATABASE SCHEMA

### 3.1 Users Table

**Table Name**: `users`  
**Purpose**: Store user account information for students and administrators

```sql
CREATE TABLE users (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    fullname        VARCHAR(100) NOT NULL,
    student_id      VARCHAR(20) UNIQUE,
    email           VARCHAR(100) NOT NULL UNIQUE,
    password        VARCHAR(255) NOT NULL,
    role            ENUM('student','admin') DEFAULT 'student',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Column Descriptions**:
- `id`: Unique user identifier
- `fullname`: Complete name of the user
- `student_id`: Institutional student identifier (unique)
- `email`: Institutional email address (unique)
- `password`: Bcrypt hashed password (minimum 6 characters)
- `role`: User role determining system access level
- `created_at`: Account creation timestamp

**Security Notes**:
- Passwords stored as bcrypt hashes using Werkzeug
- Email and student_id enforce uniqueness constraints
- Role field determines access control policies

---

### 3.2 Departments Table

**Table Name**: `departments`  
**Purpose**: Store institutional department information for complaint routing

```sql
CREATE TABLE departments (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Column Descriptions**:
- `id`: Unique department identifier
- `name`: Department name
- `created_at`: Record creation timestamp

**Associated Faculties** (Configured in app.py):
- Chemical & Biochemical Sciences
- Applied Chemistry
- Science Education
- Bio-forensic Sciences
- Biomedical Statistics
- Applied Mathematics
- Cyber-Security & Application
- Information Technology
- Computational Mathematics
- Software Engineering
- Public Health
- Nursing & Midwifery

---

### 3.3 Complaints Table

**Table Name**: `complaints`  
**Purpose**: Store student complaints with workflow tracking

```sql
CREATE TABLE complaints (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    student_id    INT NOT NULL,
    department_id INT,
    subject       VARCHAR(200) NOT NULL,
    complaint     TEXT NOT NULL,
    faculty       VARCHAR(100) DEFAULT NULL,
    priority      ENUM('Normal','High','Urgent') DEFAULT 'Normal',
    status        ENUM('Pending','Notify','In Progress','Resolved') DEFAULT 'Pending',
    office_stage  VARCHAR(100) DEFAULT NULL,
    anonymous     TINYINT(1) DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id),
    FOREIGN KEY (department_id) REFERENCES departments(id)
)
```

**Column Descriptions**:
- `id`: Unique complaint identifier
- `student_id`: Submitting student (foreign key)
- `department_id`: Target department (foreign key)
- `subject`: Brief complaint title (200 characters max)
- `complaint`: Full complaint description
- `faculty`: Academic faculty classification
- `priority`: Urgency level (Normal/High/Urgent)
- `status`: Current workflow status
- `office_stage`: Current handling department
- `anonymous`: Boolean flag for anonymous complaints
- `created_at`: Submission timestamp

**Status Workflow**:
1. **Pending**: Initial submission state
2. **Notify**: Student notified of receipt
3. **In Progress**: Currently being addressed
4. **Resolved**: Issue resolved and documented

---

### 3.4 Feedback Table

**Table Name**: `feedback`  
**Purpose**: Store student feedback on complaint resolution

```sql
CREATE TABLE feedback (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    complaint_id    INT NOT NULL,
    rating          INT DEFAULT NULL,
    comments        TEXT,
    submitted_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id)
)
```

---

## 4. APPLICATION ROUTES

### 4.1 Authentication Routes

#### 4.1.1 Login Route
- **Endpoint**: `GET/POST /login`
- **Description**: User authentication (students and administrators)
- **Required Fields**: email, password, role
- **Response**: Redirect to dashboard on success, error message on failure
- **Features**:
  - Role-based login (student/admin)
  - Session management
  - Password validation using bcrypt
  - CSRF protection

#### 4.1.2 Registration Route
- **Endpoint**: `GET/POST /register`
- **Description**: Student self-registration
- **Required Fields**: fullname, student_id, email, password, confirm_password
- **Validation**:
  - Minimum 6-character password
  - Password confirmation matching
  - Unique email and student_id
- **Response**: Registration confirmation and redirect to login

#### 4.1.3 Logout Route
- **Endpoint**: `GET /logout`
- **Description**: Clear session and return to login
- **Authentication**: Required
- **Response**: Redirect to login with logout confirmation message

---

### 4.2 Student Routes

#### 4.2.1 Dashboard Route
- **Endpoint**: `GET /dashboard`
- **Authentication**: Required
- **Description**: Student dashboard showing complaint statistics and recent submissions
- **Features**:
  - Total complaints count
  - Status breakdown (Pending, Notify, In Progress, Resolved)
  - Recent complaint list with status
  - Quick access to submit new complaint

#### 4.2.2 Complaint Submission
- **Endpoint**: `GET/POST /submit`
- **Authentication**: Required (Student)
- **Description**: Form for submitting new complaints
- **Required Fields**:
  - Subject
  - Complaint description
  - Department/Faculty
  - Priority level (Normal/High/Urgent)
  - Anonymous flag
- **File Upload**: Supporting documents (PDF, PNG, JPG, DOC, DOCX)
- **Maximum File Size**: 5MB
- **Response**: Confirmation with complaint ID and tracking information

#### 4.2.3 My Complaints Route
- **Endpoint**: `GET /my-complaints`
- **Authentication**: Required (Student)
- **Description**: List of user's submitted complaints with status tracking
- **Features**:
  - Sortable/filterable complaint list
  - Real-time status updates
  - Complaint details expansion
  - Historical tracking

#### 4.2.4 Feedback Route
- **Endpoint**: `GET /feedback`
- **Authentication**: Required (Student)
- **Description**: Submit feedback on resolved complaints
- **Features**:
  - Rating system (1-5 stars)
  - Comment submission
  - List of resolved complaints for feedback

---

### 4.3 Administrator Routes

#### 4.3.1 Admin Dashboard
- **Endpoint**: `GET /dashboard` (Admin role)
- **Authentication**: Required (Admin)
- **Description**: Administrative dashboard with comprehensive statistics
- **Features**:
  - Total complaints received
  - Status distribution
  - Priority-level breakdown
  - Recent complaints list with student names
  - Trending departments/issues

#### 4.3.2 Admin Complaints Management
- **Endpoint**: `GET /admin/complaints`
- **Authentication**: Required (Admin)
- **Description**: Comprehensive complaint management interface
- **Filtering Options**:
  - Status (all, Pending, Notify, In Progress, Resolved)
  - Priority level
  - Date range
  - Department
  - Student search
- **Bulk Actions**: Status updates, priority changes

#### 4.3.3 Admin Response Handler
- **Endpoint**: `POST /admin/respond/<complaint_id>`
- **Authentication**: Required (Admin)
- **Description**: Submit administrative response to complaint
- **Fields**:
  - Response text
  - Internal notes
  - Next workflow stage
  - Priority adjustment (optional)
- **Features**:
  - Automatic email notification to student
  - Workflow stage advancement
  - Response history tracking

#### 4.3.4 Status Update Route
- **Endpoint**: `POST /admin/update-status/<complaint_id>`
- **Authentication**: Required (Admin)
- **Description**: Update complaint status in workflow
- **Supported Status Changes**:
  - Pending → Notify
  - Pending → In Progress
  - In Progress → Resolved
  - Any status → Resolved (with reason)

#### 4.3.5 Department Management
- **Endpoint**: `GET/POST /admin/departments`
- **Authentication**: Required (Admin)
- **Description**: Manage institutional departments for complaint routing
- **Features**:
  - Create new department
  - View department list
  - Delete department

#### 4.3.6 Department Deletion
- **Endpoint**: `POST /admin/departments/delete/<dept_id>`
- **Authentication**: Required (Admin)
- **Description**: Remove department from system

---

### 4.4 Settings Route

#### 4.4.1 User Settings
- **Endpoint**: `GET/POST /settings`
- **Authentication**: Required
- **Description**: User profile and preference management
- **Features**:
  - Password change
  - Email notification preferences
  - Profile information update
  - Privacy settings

---

## 5. WORKFLOW MANAGEMENT

### 5.1 Complaint Routing System

Complaints are automatically routed through predefined workflow paths based on department classification:

```python
WORKFLOW_PATHS = {
    "Academic Affairs": ["Dean of Student Affairs", "Registrar", "Security"],
    "Examinations Office": ["Head of Department", "Examination Officer", 
                           "Course Lecturer", "Head of Department (Final Response)"],
    "Finance Office": ["Head of Finance", "Bursar", "Registrar"],
    "Welfare / Housing": ["Head of Welfare", "Facilities Manager", "Dean of Students"],
    "IT Directorate": ["Director of IT", "Systems Administrator", "Network Manager"],
    "SRC": ["SRC President", "SRC Vice President", "Student Affairs Liaison"],
    "Security": ["Chief Security Officer", "Security Operations Manager"]
}
```

### 5.2 Workflow State Transitions

```
┌─────────┐
│ Pending │ (Initial Submission)
└────┬────┘
     │
     ▼
┌─────────┐
│  Notify │ (Student Notified)
└────┬────┘
     │
     ▼
┌──────────────┐
│ In Progress  │ (Being Addressed)
└────┬─────────┘
     │
     ▼
┌─────────────┐
│  Resolved   │ (Issue Addressed)
└─────────────┘
```

### 5.3 Multi-Stage Processing

Each complaint progresses through departmental stages:

1. **Initial Reception**: Complaint logged at appropriate office
2. **Investigation**: Department investigates complaint
3. **Coordination**: If needed, complaint routed to next stage
4. **Resolution**: Final response provided to student
5. **Documentation**: Complaint archived with resolution details

---

## 6. SECURITY ARCHITECTURE

### 6.1 Authentication Mechanisms

- **Password Storage**: Bcrypt hashing (minimum 6 characters)
- **Session Management**: Flask-session with secure cookies
- **CSRF Protection**: Flask built-in protection
- **Role-Based Access Control**: Decorator-based enforcement

### 6.2 Access Control Decorators

```python
@login_required       # Redirects to login if not authenticated
@admin_required       # Blocks non-admin users
```

### 6.3 Data Protection

- **File Upload**: Secure filename sanitization, file type validation
- **Input Validation**: Email format, text length constraints
- **SQL Injection Prevention**: Parameterized queries throughout
- **Session Timeout**: Configurable session expiration

### 6.4 Email Notifications

- **Configuration**: SMTP server settings (configurable)
- **Automated Notifications**:
  - Registration confirmation
  - Complaint received acknowledgment
  - Status update notifications
  - Response notifications
- **Email Security**: No sensitive data in plain text emails

---

## 7. FILE MANAGEMENT

### 7.1 Upload Configuration

- **Upload Directory**: `/static/uploads/letters/`
- **Maximum File Size**: 5 MB
- **Allowed Extensions**: PDF, PNG, JPG, JPEG, DOC, DOCX
- **Filename Handling**: Secure filename transformation

### 7.2 File Security

- Extension validation before acceptance
- File size enforcement
- Secure filename generation
- Path traversal prevention

---

## 8. SYSTEM FEATURES

### 8.1 Core Features

1. **Student Registration & Login**
   - Self-service registration
   - Email/password authentication
   - Role-based access differentiation

2. **Complaint Submission**
   - Rich text support
   - File attachment capability
   - Department/faculty categorization
   - Priority level assignment
   - Anonymous complaint option

3. **Complaint Tracking**
   - Real-time status visibility
   - Workflow stage display
   - Historical view of complaint progression

4. **Administrative Dashboard**
   - Comprehensive statistics
   - Complaint distribution by status, priority, department
   - Quick-access complaint management

5. **Response Management**
   - Administrative response submission
   - Workflow stage advancement
   - Automatic student notification
   - Response history tracking

6. **Feedback System**
   - Post-resolution student feedback
   - Rating mechanism (1-5)
   - Comment submission

7. **Department Management**
   - Administrative department creation/deletion
   - Workflow path configuration
   - Complaint routing optimization

---

## 9. PERFORMANCE SPECIFICATIONS

### 9.1 Response Times (Target)

- Page load time: <2 seconds
- Database query response: <500ms
- File upload processing: <5 seconds (5MB)
- Email delivery: <30 seconds

### 9.2 Capacity Planning

- **Concurrent Users**: Designed for 100+ simultaneous users
- **Database Scalability**: Efficient indexing on frequently queried fields
- **Storage**: Growing complaint database with efficient archival

---

## 10. DEPLOYMENT SPECIFICATIONS

### 10.1 System Requirements

**Server Requirements**:
- Python 3.7+
- MySQL 5.7+
- Minimum 1 GB RAM
- 10 GB storage (expandable)

**Client Requirements**:
- Modern web browser (Chrome, Firefox, Safari, Edge)
- JavaScript enabled
- 50 MB free disk space for temporary files

### 10.2 Installation Steps

1. Install Python dependencies: `pip install -r requirements.txt`
2. Configure MySQL database with credentials in `database.py`
3. Initialize database: Call `init_database()` on first run
4. Configure email settings in `app.py` (optional)
5. Run application: `python app.py`
6. Access at `http://localhost:5000`

---

## 11. FUTURE ENHANCEMENTS

- Mobile application development
- Advanced analytics dashboard
- Machine learning for complaint categorization
- Integration with institutional systems (student information system, email system)
- Mobile push notifications
- SMS notifications
- Blockchain for complaint immutability
- Advanced reporting and export capabilities

---

## 12. CONCLUSION

This technical specification provides a comprehensive overview of the UTAS Student Complaint Management System architecture, design, and implementation. The system successfully addresses identified institutional challenges through a well-designed, secure, and user-focused solution.

**Document Approval Date**: 2025-06-12  
**Next Review**: 2025-12-12
