# SYSTEM DESIGN DOCUMENT
## UTAS Student Complaint Management System

**Document Type**: Design Specification  
**Version**: 1.0  
**Date**: 2025-06-12  
**Status**: Complete Implementation

---

## 1. DESIGN PHILOSOPHY

The UTAS Student Complaint Management System is designed around three core principles:

### 1.1 User-Centered Design
The system prioritizes user needs:
- **Students**: Simple, efficient complaint submission and tracking
- **Administrators**: Comprehensive management and analysis capabilities
- **Accessibility**: Intuitive interfaces requiring minimal training

### 1.2 Operational Efficiency
The system streamlines institutional processes:
- Centralized complaint management
- Automated workflow routing
- Reduced manual intervention
- Systematic documentation

### 1.3 Institutional Accountability
The system enables transparency and accountability:
- Complete audit trails for all complaints
- Real-time progress tracking
- Data-driven institutional improvement
- Evidence-based decision making

---

## 2. SYSTEM COMPONENTS

### 2.1 Authentication Module

**Responsibility**: Manage user identity verification and session management

**Components**:
- Login interface for students and administrators
- User registration system (students only)
- Password hashing using bcrypt
- Session management with timeout
- Role-based access control

**Security Features**:
- Password strength enforcement (minimum 6 characters)
- Unique email and student ID constraints
- Secure password hashing (Werkzeug bcrypt)
- CSRF protection on all forms
- Session timeout on inactivity

---

### 2.2 Student Complaint Submission Module

**Responsibility**: Enable students to lodge complaints with rich context

**Process Flow**:

```
1. Student accesses /submit form
   ↓
2. Student provides complaint details
   - Subject (max 200 characters)
   - Full description
   - Department/Faculty selection
   - Priority level
   - Optional file attachments
   - Anonymous flag
   ↓
3. System validates input
   - Required field validation
   - File type/size validation
   - Text length validation
   ↓
4. System stores complaint
   - Database insertion
   - File storage (if applicable)
   - Initial status: "Pending"
   ↓
5. System sends confirmation
   - Email confirmation to student
   - Display complaint ID
   - Show tracking information
```

**Database Operations**:
- INSERT into complaints table
- File storage in /static/uploads/letters/
- User notification via email

---

### 2.3 Complaint Tracking Module

**Responsibility**: Provide real-time complaint status visibility

**Student Capabilities**:
- View all submitted complaints
- Track current status
- View workflow stage
- Receive notifications on updates
- View administrative responses

**Data Display**:
```
Complaint ID      | Subject        | Status        | Priority | Submitted    | Last Updated
────────────────────────────────────────────────────────────────────────────────────────
2025001          | Lab Equipment  | In Progress   | High     | 2025-06-10  | 2025-06-11
2025002          | Accommodation  | Resolved      | Normal   | 2025-06-08  | 2025-06-09
2025003          | Course Timing  | Notify        | Urgent   | 2025-06-11  | 2025-06-11
```

---

### 2.4 Administrative Management Module

**Responsibility**: Provide administrators comprehensive complaint oversight

**Dashboard Features**:
- Complaint statistics and trends
- Status distribution visualization
- Priority level breakdown
- Department-wise distribution
- Recent activity feed

**Management Capabilities**:
- View all institution complaints
- Filter by multiple criteria
- Update complaint status
- Submit formal responses
- Advance workflow stages
- Bulk operations on complaints

**Workflow Management**:
```
Admin receives complaint
   ↓
Admin reviews details and context
   ↓
Admin determines appropriate action
   ├─ Provides response
   ├─ Updates status
   └─ Routes to next stage
   ↓
System notifies student
   ↓
If resolved:
   - Mark as "Resolved"
   - Document resolution
   
If in progress:
   - Mark as "In Progress"
   - Schedule follow-up
   
If needs coordination:
   - Route to next stage
   - Update office_stage field
```

---

### 2.5 Notification Module

**Responsibility**: Maintain timely, accurate communication with all users

**Notification Events**:

| **Event** | **Recipient** | **Trigger** |
|----------|--------------|-----------|
| Registration Confirmation | Student | Registration completion |
| Complaint Received | Student | Complaint submission |
| Status Update | Student | Status change |
| Response Received | Student | Admin response |
| Escalation | Admin | Workflow stage change |

**Notification Methods**:
- Email notifications (primary)
- In-system messages (future)
- SMS notifications (future enhancement)

---

### 2.6 Department Management Module

**Responsibility**: Maintain organizational structure and routing rules

**Capabilities**:
- Create new departments
- View department list
- Delete departments
- Configure workflow paths
- Manage routing rules

**Data Relationships**:
```
Department → Complaints → Workflow Stages
            ↓
            Routes to specific admin team
            ↓
            Predefined workflow path
```

---

### 2.7 Feedback Collection Module

**Responsibility**: Gather student satisfaction metrics

**Features**:
- Feedback on resolved complaints only
- Rating system (1-5 stars)
- Comment field for detailed feedback
- Automatic email invitation
- Historical feedback tracking

---

## 3. DATA FLOW ARCHITECTURE

### 3.1 Complaint Submission Flow

```
┌─────────────┐
│   Student   │
└──────┬──────┘
       │ Completes form
       ▼
┌─────────────────────────┐
│  Input Validation       │
│  - Text format          │
│  - File type/size       │
│  - Required fields      │
└──────┬──────────────────┘
       │ Valid
       ▼
┌─────────────────────────┐
│  File Processing        │
│  - Secure filename      │
│  - Move to storage      │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  Database Storage       │
│  - Insert complaint     │
│  - Store metadata       │
│  - Set initial status   │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  Notification           │
│  - Email confirmation   │
│  - Provide tracking ID  │
└─────────────────────────┘
```

### 3.2 Complaint Resolution Flow

```
┌─────────────┐
│ Admin View  │
└──────┬──────┘
       │ Reviews complaint
       ▼
┌─────────────────────────┐
│  Admin Response Form    │
│  - Submit response      │
│  - Set status           │
│  - Choose next stage    │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  Database Update        │
│  - Update status        │
│  - Store response       │
│  - Update office_stage  │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  Email Notification     │
│  - Alert student        │
│  - Provide response     │
│  - Update tracking      │
└─────────────────────────┘
```

---

## 4. USER INTERFACE DESIGN

### 4.1 Student Interface

**Navigation Structure**:
```
Home (Login/Register)
├── Dashboard
│   ├── Statistics Summary
│   ├── Recent Complaints
│   └── Quick Links
├── Submit Complaint
│   ├── Complaint Form
│   ├── File Upload
│   └── Confirmation
├── My Complaints
│   ├── Filter Options
│   ├── Complaint List
│   └── Detail View
├── Feedback
│   ├── Resolved Complaints List
│   ├── Rating Form
│   └── Comment Submission
└── Settings
    ├── Password Change
    ├── Notification Preferences
    └── Profile Information
```

### 4.2 Administrator Interface

**Navigation Structure**:
```
Admin Dashboard (Login)
├── Overview
│   ├── Statistics
│   ├── Trends
│   └── Recent Activity
├── Complaint Management
│   ├── All Complaints
│   ├── Filter/Search
│   ├── Bulk Actions
│   └── Detail Management
├── Department Management
│   ├── View Departments
│   ├── Create Department
│   └── Delete Department
├── Reports
│   ├── Complaint Statistics
│   ├── Resolution Times
│   └── Department Performance
└── Settings
    ├── System Configuration
    ├── Email Templates
    └── Admin Accounts
```

---

## 5. SECURITY DESIGN

### 5.1 Authentication Architecture

**Login Process**:
```
User enters credentials
        ↓
Input validation
        ↓
Query user in database
        ↓
Check user exists
        ↓
Verify password (bcrypt)
        ↓
Password correct?
    ├─ YES → Create session
    │         Store user data
    │         Redirect to dashboard
    │         ↓
    │         Set session cookie
    │
    └─ NO  → Show error message
             Remain on login page
```

### 5.2 Authorization Model

**Role-Based Access Control**:

```
┌──────────────────────────────────────────┐
│            User Roles                    │
├──────────────────────────────────────────┤
│                                          │
│  STUDENT                 │  ADMIN        │
│  ├─ View own complaints  │  ├─ View all  │
│  ├─ Submit complaints    │  ├─ Manage    │
│  ├─ Track status         │  ├─ Respond   │
│  └─ Provide feedback     │  └─ Report    │
│                          │               │
└──────────────────────────────────────────┘
```

### 5.3 Data Protection

**Input Sanitization**:
- Parameterized SQL queries (SQL injection prevention)
- File type validation (malware prevention)
- Text length constraints (buffer overflow prevention)
- Email format validation

**File Security**:
- Secure filename generation
- File type whitelist enforcement
- File size limitations
- Virus scanning capability (future)

---

## 6. SYSTEM REQUIREMENTS MAPPING

### 6.1 Functional Requirements

| **Req ID** | **Requirement** | **Implementation** |
|-----------|----------------|------------------|
| FR-1 | User registration | `/register` route with validation |
| FR-2 | User authentication | `/login` route with bcrypt verification |
| FR-3 | Role-based access | `@login_required`, `@admin_required` decorators |
| FR-4 | Complaint submission | `/submit` route with form handling |
| FR-5 | Complaint tracking | `/my-complaints` route |
| FR-6 | Admin complaint view | `/admin/complaints` route |
| FR-7 | Admin response | `/admin/respond/<id>` endpoint |
| FR-8 | Status management | `/admin/update-status/<id>` endpoint |
| FR-9 | Feedback collection | `/feedback` route |
| FR-10 | Department management | `/admin/departments` routes |
| FR-11 | Real-time notifications | Email module in `send_email()` |
| FR-12 | Workflow routing | Multi-stage workflow in `WORKFLOW_PATHS` |

### 6.2 Non-Functional Requirements

| **Req ID** | **Requirement** | **Implementation** |
|-----------|----------------|------------------|
| NFR-1 | Security | Bcrypt, parameterized queries, CSRF protection |
| NFR-2 | Performance | Efficient SQL queries, caching ready |
| NFR-3 | Scalability | Modular design, database indexing |
| NFR-4 | Usability | Responsive HTML5 templates |
| NFR-5 | Reliability | Error handling, transaction management |
| NFR-6 | Maintainability | Code documentation, consistent structure |

---

## 7. DATABASE DESIGN DECISIONS

### 7.1 Normalization

The database follows **Third Normal Form (3NF)**:
- **First Normal Form**: All attributes are atomic
- **Second Normal Form**: No partial functional dependencies
- **Third Normal Form**: No transitive dependencies

### 7.2 Indexing Strategy

**Primary Indices**:
- `users.id` (Primary Key)
- `users.email` (UNIQUE)
- `users.student_id` (UNIQUE)
- `complaints.id` (Primary Key)
- `complaints.student_id` (Foreign Key)
- `complaints.status` (Search optimization)
- `complaints.created_at` (Time-based queries)

### 7.3 Scalability Considerations

Future enhancements:
- Database replication for high availability
- Read replicas for reporting queries
- Archive older complaints to separate storage
- Implement caching layer (Redis)
- Vertical/horizontal partitioning

---

## 8. ERROR HANDLING STRATEGY

### 8.1 Error Types and Responses

| **Error Type** | **Handling** | **User Message** |
|---------------|------------|-----------------|
| Database Connection | Log, retry | "System temporarily unavailable" |
| Invalid Input | Validation, re-prompt | Show specific validation error |
| File Upload Error | Log, notify | "File upload failed, try again" |
| Email Failure | Log, queue for retry | Process completed (async email retry) |
| Authentication Failure | Log attempt | "Invalid credentials" |
| Authorization Failure | Log attempt | "Access denied" |

### 8.2 Logging

All critical operations logged:
- Login attempts (success/failure)
- Complaint submissions
- Status updates
- Email delivery attempts
- Error conditions

---

## 9. FUTURE ENHANCEMENT ROADMAP

### Phase 2 Enhancements
- Mobile responsive optimization
- SMS notification support
- Advanced analytics dashboard
- Automated complaint categorization
- Appeal process implementation

### Phase 3 Enhancements
- Machine learning complaint routing
- Predictive resolution time analysis
- Integration with institutional systems
- Mobile app development
- Advanced reporting capabilities

---

## 10. CONCLUSION

This system design document provides the architectural foundation for the UTAS Student Complaint Management System. The design prioritizes user experience, system security, and operational efficiency while maintaining scalability for future growth.

The modular architecture enables straightforward enhancement and adaptation to evolving institutional requirements.

---

**Document Approved**: 2025-06-12  
**Next Review Date**: 2025-12-12  
**Design Lead**: Development Team
