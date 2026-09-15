# Oracle E-Business Suite (EBS R12) Concurrent Request MCP Server

A production-ready **Model Context Protocol (MCP)** Server written in Python that enables AI assistants (Claude, Cursor, Antigravity) to securely submit, monitor, wait for, and retrieve logs for **Oracle E-Business Suite R12 Concurrent Requests** using the **Global HRMS Manager** responsibility.

---

## 🏛️ Architecture & EBS Context Flow

### Why Standard SQL Is Not Enough
In Oracle E-Business Suite (EBS R12), concurrent programs cannot be submitted by simply inserting rows into `fnd_concurrent_requests`. Doing so bypasses:
1. Multi-Org and Data Security Policies (MOAC, HRMS security profiles).
2. Concurrent Manager scheduling queues and trigger logic.
3. User authorization checks and profile options (`FND_PROFILE`).

### EBS Authentication & Session Context Architecture

The MCP Server maintains a strict boundary between the database connection and the application user context:

```text
┌─────────────────────────────────────────────────────────────┐
│                      AI Assistant                           │
│        ("Run Worker Summary Report for Org 8043")           │
└──────────────────────────────┬──────────────────────────────┘
                               │ MCP Protocol (JSON-RPC)
┌──────────────────────────────▼──────────────────────────────┐
│            Oracle EBS Concurrent MCP Server (Python)        │
│                                                             │
│   1. Security Guardrails & Program Allowlist Verification   │
│      • Validates program is in ALLOWED_CONCURRENT_PROGRAMS  │
│      • Sanitizes all arguments & blocks shell injection     │
│                                                             │
│   2. Dynamic Responsibility Context Resolution             │
│      • Query FND_USER: Resolve USER_ID (e.g. SYSADMIN = 0)  │
│      • Query FND_RESPONSIBILITY_VL: Resolve RESP_ID (21514) │
│        and RESP_APPL_ID (800 / PER)                         │
│      • Verify authorization in FND_USER_RESP_GROUPS_ALL     │
│                                                             │
│   3. PL/SQL Apps Session Initialization                     │
│      • Execute FND_GLOBAL.APPS_INITIALIZE(...)              │
│                                                             │
│   4. Public API Submission                                  │
│      • Execute FND_REQUEST.SUBMIT_REQUEST(...)              │
│      • Commit transaction & return new REQUEST_ID           │
└──────────────────────────────┬──────────────────────────────┘
                               │ Oracle Net (port 1521 / 1532)
┌──────────────────────────────▼──────────────────────────────┐
│                  Oracle Database (EBS R12)                  │
│       Concurrent Managers (Internal Manager / Conflict)     │
└─────────────────────────────────────────────────────────────┘
```

### Entity Distinction in Oracle EBS

| Entity | Role in MCP Server | Example Value |
| :--- | :--- | :--- |
| **Database User** | Establishes the physical database socket connection | `apps` |
| **EBS Application User** | Identity under which the request is audited and logged | `SYSADMIN` (`USER_ID = 0`) |
| **Responsibility** | Defines role, menus, and HRMS security profile permissions | `Global HRMS Manager` (`RESP_ID = 21514`) |
| **Responsibility Application** | Application owning the responsibility | `PER` (Human Resources, `APPL_ID = 800`) |

---

## 🛡️ Security Guardrails

* 🚫 **No Arbitrary SQL Execution**: There is **NO** `execute_sql` tool. The server completely disallows direct DML/DDL (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `MERGE`, `GRANT`, `REVOKE`).
* 🚫 **No OS / Shell Execution**: Never executes arbitrary shell commands. Metacharacters (`` ` ``, `;`, `&`, `|`, `$`, `>`, `<`) are stripped and rejected from all parameters.
* 🔒 **Strict Program Allowlist**: Only programs explicitly configured in `ALLOWED_CONCURRENT_PROGRAMS` can be submitted. Unauthorized requests immediately fail with:
  ```text
  ERROR: Concurrent Program '<NAME>' is not authorized. Only the following approved programs may be executed: [...]
  ```
* 🎭 **Secret & Credential Masking**: Passwords, connection strings, and tokens are automatically redacted from all outputs, error logs, and client messages.
* ⚡ **Connection Pool & Auto-Rollback**: Connections are acquired from a managed pool with timeouts (`QUERY_TIMEOUT_SECONDS`) and uncommitted transactions are rolled back automatically upon release.

---

## 📁 Project Structure

```text
oracle-ebs-mcp/
│
├── src/
│   ├── server.py              # FastMCP Server registering the 5 tools
│   ├── config.py              # Validated environment configuration
│   ├── database.py            # oracledb Thin Mode connection pool & timeouts
│   ├── security.py            # Allowlist validator & parameter sanitization
│   ├── ebs_context.py         # Dynamic resolution & FND_GLOBAL.APPS_INITIALIZE
│   │
│   └── tools/
│       ├── __init__.py
│       ├── concurrent_submit.py  # list_allowed_concurrent_programs & submit_concurrent_request
│       ├── concurrent_status.py  # get_concurrent_request_status (FND_CONCURRENT)
│       ├── concurrent_wait.py    # wait_for_concurrent_request (polling loop)
│       └── concurrent_output.py  # get_concurrent_request_log (sanitized log retrieval)
│
├── tests/
│   ├── test_security.py       # Allowlist, injection filter, secret masking tests
│   ├── test_context.py        # Context resolution & APPS_INITIALIZE tests
│   ├── test_config.py         # Configuration and env parsing tests
│   └── test_concurrent_tools.py # Mocked execution tests for all 5 tools
│
├── .env.example               # Template environment configuration
├── .env                       # Local environment variables
├── .gitignore
├── requirements.txt           # Python dependencies
├── pyproject.toml             # Project metadata
├── run_tests.py               # Test runner
└── README.md                  # Complete documentation
```

---

## ⚙️ Configuration & Environment Variables

Copy `.env.example` to `.env` and fill in your Oracle EBS environment details:

```env
# Oracle Database Connection Details
ORACLE_HOST=10.100.100.104
ORACLE_PORT=1532
ORACLE_SERVICE=HRVIS
ORACLE_USER=apps
ORACLE_PASSWORD=apps

# Oracle EBS Responsibility & Security Context
EBS_USER_ID=0
EBS_USERNAME=SYSADMIN

# Global HRMS Manager Responsibility Context
EBS_RESPONSIBILITY_ID=21514
EBS_RESPONSIBILITY_APPL_ID=800
EBS_RESPONSIBILITY_NAME=Global HRMS Manager

# Concurrent Program Security Allowlist (comma-separated short names)
ALLOWED_CONCURRENT_PROGRAMS=PERRPPSM,PERRPRAA,PERRPRAS,PERRPRBD,PERRPRMS,XX_EMPLOYEE_REPORT,XX_ABSENCE_REPORT,FNDCPPRT

# Connection Pool & Safety Limits
ORACLE_POOL_MIN=1
ORACLE_POOL_MAX=5
QUERY_TIMEOUT_SECONDS=30
POLL_INTERVAL_SECONDS=5
POLL_TIMEOUT_SECONDS=180
LOG_LEVEL=INFO
```

> **Note:** If `EBS_USER_ID`, `EBS_RESPONSIBILITY_ID`, or `EBS_RESPONSIBILITY_APPL_ID` are omitted or left blank, the MCP Server dynamically resolves them by querying `FND_USER` and `FND_RESPONSIBILITY_VL` using `EBS_USERNAME` and `EBS_RESPONSIBILITY_NAME`.

---

## 🚀 Installation & Running

### 1. Requirements
* Python 3.11+
* Network access to Oracle Database port (e.g. 1521 or 1532)
* `oracledb` runs in **Thin Mode** (pure Python, **no Oracle Instant Client required**).

### 2. Setup Virtual Environment
```bash
cd oracle-ebs-mcp

# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Tests
```bash
python run_tests.py
```
Output:
```text
Ran 20 tests in 2.0s
OK
```

### 4. Start the MCP Server Manually
```bash
python -m src.server
```

---

## 🧰 MCP Tools Reference

### 1. `list_allowed_concurrent_programs`
Lists all concurrent programs that the AI assistant is authorized to execute.

**Input:** None

**Example Output:**
```json
[
  {
    "program": "Worker Summary Report",
    "short_name": "PERRPPSM",
    "application": "Human Resources",
    "application_short_name": "PER",
    "description": "Prints worker headcount summary by organization"
  },
  {
    "program": "Absences Report",
    "short_name": "PERRPRAA",
    "application": "Human Resources",
    "application_short_name": "PER",
    "description": "Employee absence listing"
  }
]
```

---

### 2. `submit_concurrent_request`
Submits an authorized concurrent program under `Global HRMS Manager`.

**Inputs:**
* `program_short_name` (string, required): Concurrent program short name (e.g., `PERRPPSM`).
* `parameters` (array of strings/numbers, optional): Arguments to pass to the program (up to 20).
* `application_short_name` (string, optional): E.g., `PER` or `XX`. Auto-detected if omitted.

**Execution Steps:**
1. Validates program against `ALLOWED_CONCURRENT_PROGRAMS`.
2. Validates and sanitizes parameters (rejects shell injection).
3. Initializes EBS context via `FND_GLOBAL.APPS_INITIALIZE`.
4. Submits via `FND_REQUEST.SUBMIT_REQUEST`.
5. Returns the generated numeric `request_id`.

**Example Output:**
```json
{
  "status": "success",
  "request_id": 10125,
  "program": "Worker Summary Report",
  "short_name": "PERRPPSM",
  "application": "PER",
  "responsibility": "Global HRMS Manager",
  "parameters": ["8043", "Y"],
  "phase": "Pending",
  "request_status": "Normal",
  "message": "Concurrent Request submitted successfully. Request ID: 10125"
}
```

---

### 3. `get_concurrent_request_status`
Checks real-time phase, status, and lifecycle timestamps for a concurrent request.

**Inputs:**
* `request_id` (integer, required): The numeric Request ID.

**Example Output:**
```json
{
  "status": "success",
  "request_id": 10125,
  "program_name": "Worker Summary Report",
  "program_short_name": "PERRPPSM",
  "phase": "Completed",
  "request_status": "Normal",
  "phase_code": "C",
  "status_code": "C",
  "developer_phase": "COMPLETE",
  "developer_status": "NORMAL",
  "requested_start_date": "2026-09-14 15:00:00",
  "actual_start_date": "2026-09-14 15:00:02",
  "completion_date": "2026-09-14 15:00:45",
  "duration_minutes": 0.72,
  "completion_text": "Program completed successfully.",
  "requested_by": "SYSADMIN",
  "responsibility": "Global HRMS Manager"
}
```

---

### 4. `wait_for_concurrent_request`
Polls the request until it reaches a terminal state (`COMPLETED_NORMAL`, `ERROR`, `WARNING`, `CANCELLED`) or reaches a timeout.

**Inputs:**
* `request_id` (integer, required): Request ID.
* `poll_interval_seconds` (integer, optional, default: 5): Delay between status checks.
* `timeout_seconds` (integer, optional, default: 180): Maximum seconds to wait.

**Example Output:**
```json
{
  "status": "success",
  "request_id": 10125,
  "terminal_state": "COMPLETED_NORMAL",
  "phase": "Completed",
  "request_status": "Normal",
  "phase_code": "C",
  "status_code": "C",
  "program_name": "Worker Summary Report",
  "completion_text": "Program completed successfully.",
  "completion_date": "2026-09-14 15:00:45",
  "total_wait_seconds": 12.4,
  "attempts": 3,
  "is_completed": true
}
```

---

### 5. `get_concurrent_request_log`
Retrieves execution log or output file text with automatic secret sanitization.

**Inputs:**
* `request_id` (integer, required): Request ID.
* `file_type` (string, optional, default: `'log'`): `'log'` for execution log, `'out'` for report output.
* `max_lines` (integer, optional, default: 100): Maximum tail lines to return.

**Example Output:**
```json
{
  "status": "success",
  "request_id": 10125,
  "file_type": "log",
  "file_accessible_on_host": false,
  "line_count": 4,
  "completion_text": "Program completed successfully.",
  "lines": [
    "Program: Worker Summary Report",
    "Phase: C, Status: C",
    "Remote File Path: /u01/install/APPS/fs2/EBSapps/appl/per/12.0.0/log/l10125.req",
    "Completion Summary: Program completed successfully."
  ]
}
```

---

## 💻 AI Client Configuration

### Claude Desktop Configuration
Add the server to your Claude Desktop configuration file:
* **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
* **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "oracle-ebs-concurrent": {
      "command": "C:\\Users\\RayaIT-Admin\\Downloads\\New folder\\screenshots\\oracle-ebs-mcp\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "src.server"
      ],
      "cwd": "C:\\Users\\RayaIT-Admin\\Downloads\\New folder\\screenshots\\oracle-ebs-mcp",
      "env": {
        "ORACLE_HOST": "10.100.100.104",
        "ORACLE_PORT": "1532",
        "ORACLE_SERVICE": "HRVIS",
        "ORACLE_USER": "apps",
        "ORACLE_PASSWORD": "apps",
        "EBS_USER_ID": "0",
        "EBS_USERNAME": "SYSADMIN",
        "EBS_RESPONSIBILITY_ID": "21514",
        "EBS_RESPONSIBILITY_APPL_ID": "800",
        "EBS_RESPONSIBILITY_NAME": "Global HRMS Manager",
        "ALLOWED_CONCURRENT_PROGRAMS": "PERRPPSM,PERRPRAA,PERRPRAS,PERRPRBD,PERRPRMS,XX_EMPLOYEE_REPORT,XX_ABSENCE_REPORT,FNDCPPRT"
      }
    }
  }
}
```

### Antigravity IDE / Cursor / VS Code Configuration
Add to `.vscode/settings.json` or Antigravity MCP settings:

```json
{
  "mcp": {
    "servers": {
      "oracle-ebs-concurrent": {
        "type": "stdio",
        "command": "python",
        "args": ["-m", "src.server"],
        "cwd": "${workspaceFolder}/oracle-ebs-mcp"
      }
    }
  }
}
```

---

## 💬 Example User Prompts

Once configured, users can interact naturally with the AI assistant:

### Example 1: Discover Allowed Programs
> **User**: What Oracle EBS reports am I allowed to run?
>
> **AI Assistant**: Calls `list_allowed_concurrent_programs` and lists available HRMS reports (Worker Summary Report, Absences Report, etc.).

### Example 2: Submit and Monitor a Request
> **User**: Run the Worker Summary Report for organization 8043.
>
> **AI Assistant**:
> 1. Calls `submit_concurrent_request(program_short_name="PERRPPSM", parameters=["8043", "Y"])`.
> 2. Receives `Request ID: 10125`.
> 3. Calls `wait_for_concurrent_request(request_id=10125)`.
> 4. Informs user: *"Concurrent Request #10125 has completed with status Normal in 12.4 seconds."*

### Example 3: Check Request Log
> **User**: Check the log for request 10125.
>
> **AI Assistant**: Calls `get_concurrent_request_log(request_id=10125)` and presents the sanitized summary.

### Example 4: Security Rejection
> **User**: Run program DROP_DATABASE or submit an unauthorized custom program.
>
> **AI Assistant**: Rejects the action: *"ERROR: Concurrent Program 'DROP_DATABASE' is not authorized. Only allowed HRMS programs can be executed."*

---

## 🖥️ Oracle EBS R12 Development MCP Studio (Web UI)

A dedicated, UI-first development workbench tailored for Oracle EBS R12 Technical Consultants. It allows fast visual configuration and instant code generation across all major EBS technical domains:

1. **Concurrent Program**: Automatic `fnd_program.executable`, `register`, `parameter`, and `add_to_group` PL/SQL scripts + complete standard package specs and bodies.
2. **Report Generator**: Main SQL query builder, dynamic parameter rows, BI Publisher Data Template XML, RTF layout guidelines, and Java XDOLoader shell scripts.
3. **Workflow Studio**: Item Type, Item Key, Process Name, approval routing, and activity handler PL/SQL packages with `wf_engine` lifecycle events (`RUN`, `CANCEL`, `TIMEOUT`).
4. **Alert Manager**: Event & Periodic alerts, table trigger definitions, `:ROWID` bindings, and HTML/text email notification templates.
5. **OAF Studio (OA Framework)**: Full Java Controllers (`OAControllerImpl` with `processRequest`/`processFormRequest`), XMLImporter commands, and OACore service bounce procedures.
6. **SQL & PL/SQL Studio**: Autonomous packages, standard error logging (`FND_LOG`), exception stacks, and wrappers for Oracle Public APIs (`HR_PERSON_ABSENCE_API`, `HR_EMPLOYEE_API`, `FND_USER_PKG`).

### Launching the UI
```bash
python ui/server_launcher.py
```
Or open `ui/index.html` directly in any modern web browser.

