#!/usr/bin/env python3
"""
Oracle EBS R12 Development MCP Studio
Live Deployment Gateway Server
  - Serves the UI on http://localhost:8855/index.html
  - /api/status   : Test EBS connection
  - /api/deploy   : Deploy any EBS object (concurrent/workflow/alert/oaf/rdf/rtf/sql)
  - /api/verify   : Verify an EBS object exists in the database
  - /api/upload   : Upload a binary file (RDF/RTF) to EBS server via SFTP

Deployment routing table:
  object_type = concurrent  → fnd_program + executable + params + request group
  object_type = workflow    → wf_load.upload_item_type + upload_activity + wf_engine
  object_type = alert       → alr_alerts API
  object_type = oaf         → ak_regions API + optional jar upload
  object_type = rdf         → SFTP binary upload to $AU_TOP/reports/US/ + XDO catalog
  object_type = rtf         → SFTP upload to $XDO_TOP/reports/ + xdo_lobs registration
  object_type = sql|plsql   → direct sqlplus execution
"""

import http.server
import json
import os
import re
import base64
import socket
import socketserver
import sys
import urllib.parse
import webbrowser

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR  = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from src.ebs_executor import (
    execute_ebs_sql,
    verify_ebs_object,
    deploy_to_ebs,
    sftp_upload_content,
    EBS_HOST,
    EBS_USER,
)

DEFAULT_PORT = 8855
UI_DIR       = CURRENT_DIR


class EBSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=UI_DIR, **kwargs)

    def log_message(self, fmt, *args):
        # Suppress noisy access logs — only print API calls
        if "/api/" in self.path or "ERROR" in str(args):
            print(f"[{self.address_string()}] {fmt % args}")

    # ─── Routing ────────────────────────────────────────────────────────────

    def do_OPTIONS(self):
        self._cors_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/status":
            self.handle_status()
        elif parsed.path == "/api/ping":
            self.send_json({"alive": True, "gateway": "Oracle EBS MCP Studio"})
        elif parsed.path == "/api/download_rdf":
            self.handle_download_rdf(parsed)
        elif parsed.path == "/api/download_rtf":
            self.handle_download_rtf(parsed)
        elif parsed.path == "/api/download_sample_xml":
            self.handle_download_sample_xml(parsed)
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/deploy":
            self.handle_deploy()
        elif parsed.path == "/api/verify":
            self.handle_verify()
        elif parsed.path == "/api/upload":
            self.handle_upload()
        elif parsed.path == "/api/download_rdf":
            self.handle_download_rdf_post()
        elif parsed.path == "/api/download_rtf":
            self.handle_download_rtf_post()
        elif parsed.path == "/api/download_sample_xml":
            self.handle_download_sample_xml_post()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error":"Endpoint not found"}')

    # ─── Handlers ───────────────────────────────────────────────────────────

    def handle_status(self):
        """Test live connection to Oracle EBS instance."""
        print("[API] Testing EBS connection...")
        res = execute_ebs_sql(
            "SELECT instance_name, host_name, status, version FROM v$instance;",
            timeout=15
        )
        if res.get("success"):
            self.send_json({
                "connected": True,
                "instance": "HRVIS",
                "host": EBS_HOST,
                "user": EBS_USER,
                "output": res.get("output", ""),
            })
        else:
            self.send_json({
                "connected": False,
                "error": res.get("error", "Connection failed"),
                "output": res.get("output", ""),
                "stderr": res.get("stderr", ""),
            })

    def handle_download_rdf(self, parsed):
        """Serve genuine Oracle Reports 10g/11g binary RDF compiled dynamically or from template."""
        query = urllib.parse.parse_qs(parsed.query)
        rep_name = query.get("name", ["XX_REPORT"])[0].strip().upper()
        sql_text = query.get("sql", [""])[0].strip()
        app_short = query.get("app", ["PER"])[0].strip().upper()

        data = None
        if sql_text:
            try:
                from src.ebs_executor import compile_dynamic_rdf_from_sql
                res = compile_dynamic_rdf_from_sql(sql_text, rep_name, f"{rep_name} Report", app_short=app_short)
                if res.get("rdf_b64"):
                    data = base64.b64decode(res["rdf_b64"])
                    print(f"[API] Compiled dynamic RDF for {rep_name} ({len(data)} bytes) from SQL query")
            except Exception as e:
                print(f"[API RDF Compile Note] {e}")

        if not data:
            tpl_path = os.path.join(CURRENT_DIR, "templates", "base_template.rdf")
            if os.path.exists(tpl_path):
                with open(tpl_path, "rb") as f:
                    data = f.read()
            else:
                data = b""

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{rep_name}.rdf"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def handle_download_rtf(self, parsed):
        """Serve companion BI Publisher RTF template matching dynamic SQL columns."""
        query = urllib.parse.parse_qs(parsed.query)
        rep_name = query.get("name", ["XX_REPORT"])[0].strip().upper()
        sql_text = query.get("sql", [""])[0].strip()
        app_short = query.get("app", ["PER"])[0].strip().upper()

        if sql_text:
            try:
                from src.ebs_executor import parse_sql_columns_py, generate_rtf_from_columns_py
                cols = parse_sql_columns_py(sql_text)
                params = [p.upper() for p in re.findall(r':([a-zA-Z0-9_]+)', sql_text) if p.upper() not in ('MI', 'SS', 'HH24')]
                rtf_content = generate_rtf_from_columns_py(f"{rep_name} Report", rep_name, app_short, cols, params)
            except Exception as e:
                print(f"[API RTF Note] {e}")
                from src.ebs_executor import generate_rtf_from_columns_py
                rtf_content = generate_rtf_from_columns_py(f"{rep_name} Report", rep_name, app_short, ["RECORD_ID", "RECORD_NAME"])
        else:
            from src.ebs_executor import generate_rtf_from_columns_py
            rtf_content = generate_rtf_from_columns_py(
                f"{rep_name} Report", rep_name, app_short,
                ["EMPLOYEE_NUMBER", "FULL_NAME", "DEPARTMENT_NAME", "JOB_TITLE", "HIRE_DATE"],
                ["P_EFFECTIVE_DATE", "P_ORG_ID", "P_DEPARTMENT"]
            )

        data = rtf_content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/rtf; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{rep_name}.rtf"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def handle_download_sample_xml(self, parsed):
        """Serve companion sample XML data file matching dynamic SQL columns."""
        query = urllib.parse.parse_qs(parsed.query)
        rep_name = query.get("name", ["XX_REPORT"])[0].strip().upper()
        sql_text = query.get("sql", [""])[0].strip()

        from src.ebs_executor import parse_sql_columns_py
        if sql_text:
            cols = parse_sql_columns_py(sql_text)
            params = [p.upper() for p in re.findall(r':([a-zA-Z0-9_]+)', sql_text) if p.upper() not in ('MI', 'SS', 'HH24')]
        else:
            cols = ["EMPLOYEE_NUMBER", "FULL_NAME", "DEPARTMENT_NAME", "JOB_TITLE", "HIRE_DATE"]
            params = ["P_EFFECTIVE_DATE", "P_ORG_ID", "P_DEPARTMENT"]

        sample_rows = [
            {"name": "Ahmed Mohamed Ali", "dept": "Human Resources", "job": "HR Specialist", "num": "1001", "date": "2020-01-15", "amt": "5000.00", "status": "Active"},
            {"name": "Mahmoud Hassan Ibrahim", "dept": "Finance & Accounting", "job": "Senior Accountant", "num": "1002", "date": "2021-03-20", "amt": "7500.00", "status": "Active"},
            {"name": "Fatima Youssef Al-Sayed", "dept": "IT Operations", "job": "Database Administrator", "num": "1003", "date": "2019-07-10", "amt": "9200.00", "status": "Active"},
            {"name": "Tarek Khaled Mansour", "dept": "Supply Chain", "job": "Logistics Coordinator", "num": "1004", "date": "2022-11-05", "amt": "4800.00", "status": "Pending"}
        ]

        xml_lines = [f'<?xml version="1.0" encoding="UTF-8"?>', f'<{rep_name}>']
        for p in params:
            val = "2026-09-15" if "DATE" in p else ("204" if "ORG" in p else "1001")
            xml_lines.append(f'    <{p}>{val}</{p}>')

        for idx, row in enumerate(sample_rows):
            xml_lines.append('    <G_MAIN>')
            for c in cols:
                cu = c.upper()
                if "NAME" in cu and not any(k in cu for k in ("DEPT", "ORG")):
                    val = row["name"]
                elif any(k in cu for k in ("DEPT", "ORG")):
                    val = row["dept"]
                elif any(k in cu for k in ("JOB", "TITLE")):
                    val = row["job"]
                elif any(k in cu for k in ("ID", "NUM")):
                    val = str(1000 + idx + 1)
                elif "DATE" in cu:
                    val = row["date"]
                elif any(k in cu for k in ("AMT", "AMOUNT", "SALARY")):
                    val = row["amt"]
                elif "STATUS" in cu:
                    val = row["status"]
                else:
                    val = f"{c}_VAL_{idx+1}"
                xml_lines.append(f'        <{c}>{val}</{c}>')
            xml_lines.append('    </G_MAIN>')
        xml_lines.append(f'</{rep_name}>')

        xml_content = "\n".join(xml_lines)
        data = xml_content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{rep_name}_sample_data.xml"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def handle_download_rdf_post(self):
        """Serve genuine Oracle Reports binary RDF compiled dynamically from POST JSON."""
        try:
            payload = self._read_json_body()
            rep_name = payload.get("name", "XX_REPORT").strip().upper()
            sql_text = payload.get("sql", "").strip()
            app_short = payload.get("app", "PER").strip().upper()

            data = None
            if sql_text:
                try:
                    from src.ebs_executor import compile_dynamic_rdf_from_sql
                    res = compile_dynamic_rdf_from_sql(sql_text, rep_name, f"{rep_name} Report", app_short=app_short)
                    if res.get("rdf_b64"):
                        data = base64.b64decode(res["rdf_b64"])
                        print(f"[API POST] Compiled dynamic RDF for {rep_name} ({len(data)} bytes) from SQL query")
                except Exception as e:
                    print(f"[API RDF Compile Note] {e}")

            if not data:
                tpl_path = os.path.join(CURRENT_DIR, "templates", "base_template.rdf")
                if os.path.exists(tpl_path):
                    with open(tpl_path, "rb") as f:
                        data = f.read()
                else:
                    data = b""

            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{rep_name}.rdf"')
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_json({"success": False, "error": str(e)}, 500)

    def handle_download_rtf_post(self):
        """Serve BI Publisher RTF template matching dynamic SQL columns from POST JSON."""
        try:
            payload = self._read_json_body()
            rep_name = payload.get("name", "XX_REPORT").strip().upper()
            sql_text = payload.get("sql", "").strip()
            app_short = payload.get("app", "PER").strip().upper()

            from src.ebs_executor import parse_sql_columns_py, generate_rtf_from_columns_py
            if sql_text:
                cols = parse_sql_columns_py(sql_text)
                params = [p.upper() for p in re.findall(r':([a-zA-Z0-9_]+)', sql_text) if p.upper() not in ('MI', 'SS', 'HH24')]
                rtf_content = generate_rtf_from_columns_py(f"{rep_name} Report", rep_name, app_short, cols, params)
            else:
                rtf_content = generate_rtf_from_columns_py(
                    f"{rep_name} Report", rep_name, app_short,
                    ["EMPLOYEE_NUMBER", "FULL_NAME", "DEPARTMENT_NAME", "JOB_TITLE", "HIRE_DATE"],
                    ["P_EFFECTIVE_DATE", "P_ORG_ID", "P_DEPARTMENT"]
                )

            data = rtf_content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/rtf; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{rep_name}.rtf"')
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_json({"success": False, "error": str(e)}, 500)

    def handle_download_sample_xml_post(self):
        """Serve companion sample XML data file matching dynamic SQL columns from POST JSON."""
        try:
            payload = self._read_json_body()
            rep_name = payload.get("name", "XX_REPORT").strip().upper()
            sql_text = payload.get("sql", "").strip()

            from src.ebs_executor import parse_sql_columns_py
            if sql_text:
                cols = parse_sql_columns_py(sql_text)
                params = [p.upper() for p in re.findall(r':([a-zA-Z0-9_]+)', sql_text) if p.upper() not in ('MI', 'SS', 'HH24')]
            else:
                cols = ["EMPLOYEE_NUMBER", "FULL_NAME", "DEPARTMENT_NAME", "JOB_TITLE", "HIRE_DATE"]
                params = ["P_EFFECTIVE_DATE", "P_ORG_ID", "P_DEPARTMENT"]

            sample_rows = [
                {"name": "Ahmed Mohamed Ali", "dept": "Human Resources", "job": "HR Specialist", "num": "1001", "date": "2020-01-15", "amt": "5000.00", "status": "Active"},
                {"name": "Mahmoud Hassan Ibrahim", "dept": "Finance & Accounting", "job": "Senior Accountant", "num": "1002", "date": "2021-03-20", "amt": "7500.00", "status": "Active"},
                {"name": "Fatima Youssef Al-Sayed", "dept": "IT Operations", "job": "Database Administrator", "num": "1003", "date": "2019-07-10", "amt": "9200.00", "status": "Active"},
                {"name": "Tarek Khaled Mansour", "dept": "Supply Chain", "job": "Logistics Coordinator", "num": "1004", "date": "2022-11-05", "amt": "4800.00", "status": "Pending"}
            ]

            xml_lines = [f'<?xml version="1.0" encoding="UTF-8"?>', f'<{rep_name}>']
            for p in params:
                val = "2026-09-15" if "DATE" in p else ("204" if "ORG" in p else "1001")
                xml_lines.append(f'    <{p}>{val}</{p}>')

            for idx, row in enumerate(sample_rows):
                xml_lines.append('    <G_MAIN>')
                for c in cols:
                    cu = c.upper()
                    if "NAME" in cu and not any(k in cu for k in ("DEPT", "ORG")):
                        val = row["name"]
                    elif any(k in cu for k in ("DEPT", "ORG")):
                        val = row["dept"]
                    elif any(k in cu for k in ("JOB", "TITLE")):
                        val = row["job"]
                    elif any(k in cu for k in ("ID", "NUM")):
                        val = str(1000 + idx + 1)
                    elif "DATE" in cu:
                        val = row["date"]
                    elif any(k in cu for k in ("AMT", "AMOUNT", "SALARY")):
                        val = row["amt"]
                    elif "STATUS" in cu:
                        val = row["status"]
                    else:
                        val = f"{c}_VAL_{idx+1}"
                    xml_lines.append(f'        <{c}>{val}</{c}>')
                xml_lines.append('    </G_MAIN>')
            xml_lines.append(f'</{rep_name}>')

            xml_content = "\n".join(xml_lines)
            data = xml_content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/xml; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{rep_name}_sample_data.xml"')
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_json({"success": False, "error": str(e)}, 500)

    def handle_deploy(self):
        """
        Main deployment endpoint — routes to correct handler by object_type.

        Request body (JSON):
          {
            "script":        "<SQL/PL-SQL text>",
            "object_name":   "XX_EMP_REPORT",
            "object_type":   "concurrent|workflow|alert|oaf|rdf|rtf|sql",
            "app_short":     "PER",
            "file_content":  "<base64 encoded binary>",   // for rdf/rtf
            "file_name":     "XX_EMP_REPORT.rdf",
            "template_code": "XX_EMP_REPORT",             // for rtf
            "env":           "DEV"
          }
        """
        try:
            payload = self._read_json_body()
            env = payload.get("env", "DEV")

            # Production safety lock
            if env == "PROD" and not payload.get("confirm_prod"):
                self.send_json({
                    "success": False,
                    "error": "🔒 PROD deployment requires explicit confirmation (confirm_prod: true)."
                }, 403)
                return

            obj_type = payload.get("object_type", "sql")
            obj_name = payload.get("object_name", "")
            print(f"[DEPLOY] → type={obj_type} | name={obj_name} | env={env}")

            result = deploy_to_ebs(payload)
            self.send_json(result)

        except Exception as e:
            import traceback
            self.send_json({
                "success": False,
                "error": str(e),
                "trace": traceback.format_exc()
            }, 500)

    def handle_verify(self):
        """Check if an EBS object exists in the database."""
        try:
            payload  = self._read_json_body()
            obj_name = payload.get("object_name", "").strip()
            obj_type = payload.get("object_type", "concurrent")
            print(f"[VERIFY] type={obj_type} name={obj_name}")
            result = verify_ebs_object(obj_type, obj_name)
            self.send_json(result)
        except Exception as e:
            self.send_json({"success": False, "error": str(e)}, 500)

    def handle_upload(self):
        """
        Upload a binary file to the EBS server via SFTP.

        Request body (JSON):
          {
            "file_content":  "<base64 encoded content>",
            "remote_path":   "/u01/.../reports/US/XX_EMP.rdf",
            "file_type":     "rdf|rtf"
          }
        """
        try:
            payload      = self._read_json_body()
            file_b64     = payload.get("file_content", "")
            remote_path  = payload.get("remote_path", "")
            file_type    = payload.get("file_type", "rdf")

            if not file_b64 or not remote_path:
                self.send_json({
                    "success": False,
                    "error": "file_content and remote_path are required."
                }, 400)
                return

            print(f"[UPLOAD] type={file_type} → {remote_path}")
            result = sftp_upload_content(remote_path, file_b64, timeout=90)
            result["remote_path"] = remote_path
            self.send_json(result)

        except Exception as e:
            self.send_json({"success": False, "error": str(e)}, 500)

    def handle_raw_sql(self):
        """Execute a raw SQL/PL-SQL block directly (no routing)."""
        try:
            payload = self._read_json_body()
            script  = payload.get("script", "").strip()
            timeout = int(payload.get("timeout", 90))
            if not script:
                self.send_json({"success": False, "error": "No script provided."}, 400)
                return
            result = execute_ebs_sql(script, timeout=timeout)
            self.send_json(result)
        except Exception as e:
            self.send_json({"success": False, "error": str(e)}, 500)

    # ─── Helpers ────────────────────────────────────────────────────────────

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode("utf-8")
        return json.loads(body) if body else {}

    def _cors_headers(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def send_json(self, data: dict, status_code: int = 200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type",   "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)


# ─── Server Startup ─────────────────────────────────────────────────────────

def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0

def find_free_port(start: int = DEFAULT_PORT) -> int:
    for p in range(start, start + 50):
        if is_port_free(p):
            return p
    return start

def run_server(port: int = None, open_browser: bool = True):
    if port is None:
        port = find_free_port(DEFAULT_PORT)

    os.chdir(UI_DIR)

    banner = f"""
=============================================================================
  ORACLE EBS R12 DEVELOPMENT MCP STUDIO - LIVE DEPLOYMENT GATEWAY
=============================================================================
  UI URL         : http://localhost:{port}/index.html
  Target EBS     : HRVIS ({EBS_HOST})
  EBS User       : {EBS_USER}
=============================================================================
  ENDPOINTS:
    GET  /api/status   -> Test EBS DB connection
    POST /api/deploy   -> Deploy any EBS object (concurrent/wf/alert/oaf/rdf/rtf)
    POST /api/verify   -> Verify object exists in EBS
    POST /api/upload   -> Upload binary file to EBS server (RDF/RTF via SFTP)
    POST /api/sql      -> Execute raw SQL/PL-SQL
=============================================================================
Press Ctrl+C to stop.
"""
    print(banner)

    if open_browser:
        try:
            webbrowser.open(f"http://localhost:{port}/index.html")
        except Exception:
            pass

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), EBSRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[SERVER] Shutting down...")
            httpd.shutdown()

if __name__ == "__main__":
    open_b = "--no-browser" not in sys.argv
    p = None
    for arg in sys.argv[1:]:
        if arg.isdigit():
            p = int(arg)
    run_server(port=p, open_browser=open_b)
