"""
Tool: Oracle EBS R12 Report Design Validator
Validates every layer of an EBS report design:
  - SQL (aliases, joins, GROUP BY, bind variables, ORA errors)
  - Parameter mapping (SQL ↔ CP ↔ Value Sets)
  - XML Data Template (all fields originate from SQL aliases)
  - Full responsibility chain (Resp → Request Group → CP → Executable)
"""

import re
from typing import Any, Dict, List, Optional
from ..config import get_config
from ..database import get_connection
from ..security import sanitize_program_name


# ─── SQL Validation ──────────────────────────────────────────────────────────

def validate_sql_tool(
    sql_query: str,
    parameters: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Perform static + live analysis on the report SQL query.
    Returns a detailed validation report with errors, warnings, and the
    extracted list of SELECT aliases (used to validate XML Data Template fields).
    """
    issues = []
    warnings = []
    aliases = []

    if not sql_query or not sql_query.strip():
        return {
            "status": "error",
            "issues": ["SQL query is empty."],
            "warnings": [],
            "aliases": [],
        }

    sql_upper = sql_query.upper()

    # 1. Must have SELECT
    if "SELECT" not in sql_upper:
        issues.append("SQL must contain a SELECT statement.")

    # 2. Must have FROM
    if "FROM" not in sql_upper:
        issues.append("SQL must contain a FROM clause.")

    # 3. Detect SELECT * (discouraged in EBS reports)
    if re.search(r"SELECT\s+\*", sql_upper):
        warnings.append("Avoid SELECT * in EBS reports. Explicitly list columns and assign aliases.")

    # 4. Detect missing aliases on expressions
    # Match expressions without AS alias: CASE...END, function(), etc.
    complex_expr_pattern = re.compile(
        r"(CASE\b.*?\bEND|NVL\(|DECODE\(|TO_CHAR\(|TO_DATE\(|SUM\(|COUNT\(|MAX\(|MIN\(|AVG\()",
        re.IGNORECASE | re.DOTALL,
    )
    if complex_expr_pattern.search(sql_query):
        # Check if there's an AS clause for each
        if not re.search(r"\bAS\s+\w+", sql_query, re.IGNORECASE):
            warnings.append("Expressions (CASE, NVL, aggregates, etc.) should have explicit AS aliases for XML mapping.")

    # 5. Validate parameter bind variables match provided parameter list
    bind_vars = set(re.findall(r":(\w+)", sql_query))
    if parameters:
        param_names = {p.get("name", "").upper().lstrip("P_") for p in parameters}
        # EBS bind variable convention: :P_XXX or :p_xxx
        for bv in bind_vars:
            if bv.upper() not in {p.get("name", "").upper() for p in parameters}:
                warnings.append(
                    f"Bind variable ':{bv}' in SQL not found in the Concurrent Program parameter list. "
                    "Ensure parameter name matches exactly."
                )

    # 6. Extract SELECT aliases
    # Find SELECT block (between SELECT and FROM)
    select_match = re.search(r"SELECT\s+(.*?)\s+FROM\b", sql_query, re.IGNORECASE | re.DOTALL)
    if select_match:
        select_block = select_match.group(1)
        # Split by comma at the top level (not inside parentheses)
        depth = 0
        current = ""
        columns = []
        for ch in select_block:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "," and depth == 0:
                columns.append(current.strip())
                current = ""
            else:
                current += ch
        if current.strip():
            columns.append(current.strip())

        for col in columns:
            # Try to find explicit alias: "... AS alias_name" or "... alias_name"
            as_match = re.search(r"\bAS\s+(\w+)\s*$", col, re.IGNORECASE)
            if as_match:
                aliases.append(as_match.group(1).upper())
            else:
                # Last word as implicit alias (e.g., table.column_name)
                last_word = re.search(r"(\w+)\s*$", col)
                if last_word:
                    aliases.append(last_word.group(1).upper())

    # 7. GROUP BY check: if aggregates are present, all non-aggregate SELECT items must be in GROUP BY
    has_aggregates = bool(re.search(r"\b(SUM|COUNT|MAX|MIN|AVG)\s*\(", sql_upper))
    if has_aggregates and "GROUP BY" not in sql_upper:
        issues.append("SQL contains aggregate functions (SUM/COUNT/MAX/MIN/AVG) but no GROUP BY clause.")

    # 8. Check for common dangerous DML patterns
    dml_pattern = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|MERGE|GRANT|REVOKE)\b", re.IGNORECASE)
    if dml_pattern.search(sql_query):
        issues.append("Report SQL must be a SELECT statement only. DML/DDL statements are not allowed.")

    status = "error" if issues else ("warning" if warnings else "pass")

    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "aliases": aliases,
        "bind_variables_found": list(bind_vars),
        "column_count": len(aliases),
    }


# ─── Parameter Mapping Validation ────────────────────────────────────────────

def validate_parameter_mapping_tool(
    sql_bind_vars: List[str],
    cp_parameters: List[Dict[str, Any]],
    value_sets: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Cross-validate SQL bind variables ↔ Concurrent Program parameters ↔ Value Sets.
    Detects: orphaned binds, missing CPs, sequence gaps, missing value sets.
    """
    issues = []
    warnings = []

    cp_names = {p.get("name", "").upper() for p in cp_parameters}
    sql_upper = {v.upper() for v in sql_bind_vars}
    vs_names = {v.get("name", "").upper() for v in (value_sets or [])}

    # 1. Every SQL bind var must have a CP parameter
    for bv in sql_upper:
        if bv not in cp_names:
            issues.append(
                f"SQL bind variable ':{bv}' has no matching Concurrent Program parameter. "
                "Add a CP parameter with the same name."
            )

    # 2. Every CP parameter should appear in SQL (unless it's a hidden/display-only param)
    for p in cp_parameters:
        name = p.get("name", "").upper()
        hidden = str(p.get("hidden", "N")).upper()
        if name not in sql_upper and hidden != "Y":
            warnings.append(
                f"CP parameter '{name}' is not used as a bind variable in the SQL. "
                "Consider removing it or marking it as Hidden if it is a report-level filter."
            )

    # 3. Check required parameters have a Value Set
    for p in cp_parameters:
        vs = p.get("value_set", "").strip()
        required = str(p.get("required", "N")).upper()
        name = p.get("name", "")
        if not vs:
            if required == "Y":
                issues.append(f"Required parameter '{name}' has no Value Set assigned.")
            else:
                warnings.append(f"Parameter '{name}' has no Value Set. Assign one for user-friendly LOV.")
        elif vs_names and vs.upper() not in vs_names:
            warnings.append(
                f"Parameter '{name}' references Value Set '{vs}' which is not in the Value Sets list. "
                "Ensure it exists in EBS."
            )

    # 4. Sequence check
    sequences = sorted([p.get("sequence", 0) for p in cp_parameters])
    if sequences != sorted(set(sequences)):
        issues.append("Duplicate parameter sequences detected. Each parameter must have a unique sequence number.")

    # 5. Token check for Oracle Reports parameters
    for p in cp_parameters:
        token = p.get("token", "")
        name = p.get("name", "")
        if not token:
            warnings.append(f"Parameter '{name}' has no Token defined. For Oracle Reports RDF, the token must match the report parameter name.")

    status = "error" if issues else ("warning" if warnings else "pass")
    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "cp_parameters_count": len(cp_parameters),
        "sql_bind_vars_count": len(sql_upper),
    }


# ─── XML Data Template Validation ────────────────────────────────────────────

def validate_xml_data_template_tool(
    xml_template: str,
    sql_aliases: List[str],
) -> Dict[str, Any]:
    """
    Verify that all XML field tags in the Data Template originate from SQL aliases.
    Detects phantom fields that would produce blank columns in the output.
    """
    issues = []
    warnings = []

    if not xml_template:
        return {"status": "error", "issues": ["XML Data Template is empty."], "warnings": [], "xml_fields": []}
    if not sql_aliases:
        warnings.append("No SQL aliases provided. Cannot cross-validate XML fields against SQL columns.")

    sql_alias_upper = {a.upper() for a in sql_aliases}

    # Extract all element names from the XML (dataQuery rowsets and dataStructure elements)
    xml_fields = re.findall(r'name="([^"]+)"', xml_template)
    xml_elements = re.findall(r'<(\w+)\s*/>', xml_template)
    all_xml_field_names = {f.upper() for f in xml_fields + xml_elements}

    # Check parameters section (those are OK to not be SQL aliases)
    param_tags = set(re.findall(r'<parameter\s+name="([^"]+)"', xml_template, re.IGNORECASE))
    param_names_upper = {p.upper() for p in param_tags}

    phantom_fields = []
    for field in all_xml_field_names:
        if field in param_names_upper:
            continue  # parameter nodes are not data fields
        if field in {"DATAGROUP", "ROWSET", "ROW", "G_1", "CS", "DS"}:
            continue  # structural nodes
        if sql_alias_upper and field not in sql_alias_upper:
            phantom_fields.append(field)

    if phantom_fields:
        for pf in phantom_fields:
            issues.append(
                f"XML field '{pf}' is not found in SQL aliases. "
                "This field will render blank in the output. Remove it or add it to the SQL."
            )

    # Validate XML is well-formed (basic check)
    open_tags = re.findall(r"<(\w+)[\s>]", xml_template)
    close_tags = re.findall(r"</(\w+)>", xml_template)
    if len(open_tags) != len(close_tags):
        warnings.append("XML Data Template may not be well-formed. Open/close tag count mismatch.")

    # Must have dataTemplate root
    if "<dataTemplate" not in xml_template:
        issues.append("XML must have a <dataTemplate> root element.")

    # Must have dataQuery
    if "<dataQuery>" not in xml_template and "<dataQuery" not in xml_template:
        issues.append("XML must contain a <dataQuery> section with the SQL query.")

    # Must have dataStructure
    if "<dataStructure>" not in xml_template and "<dataStructure" not in xml_template:
        issues.append("XML must contain a <dataStructure> section mapping SQL aliases to XML elements.")

    status = "error" if issues else ("warning" if warnings else "pass")
    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "xml_fields": list(all_xml_field_names),
        "phantom_fields": phantom_fields,
    }


# ─── Responsibility Chain Validation ─────────────────────────────────────────

def validate_responsibility_chain_tool(
    responsibility_name: str,
    concurrent_program_name: str,
    application_short_name: str = "PER",
) -> Dict[str, Any]:
    """
    Live database check of the full EBS access chain:
    Responsibility → Request Group → Concurrent Program → Executable.
    """
    clean_resp = responsibility_name.strip()
    clean_prog = sanitize_program_name(concurrent_program_name)
    cfg = get_config()

    chain = {
        "responsibility": {"name": clean_resp, "status": "unknown", "id": None},
        "request_group": {"name": None, "status": "unknown", "id": None},
        "concurrent_program": {"name": clean_prog, "status": "unknown", "id": None},
        "executable": {"name": None, "status": "unknown"},
    }
    issues = []

    try:
        with get_connection(cfg) as conn:
            with conn.cursor() as cursor:
                # 1. Check Responsibility
                cursor.execute(
                    """
                    SELECT r.responsibility_id, r.request_group_id, rg.request_group_name
                    FROM apps.fnd_responsibility_vl r
                    LEFT JOIN apps.fnd_request_groups rg ON r.request_group_id = rg.request_group_id
                    WHERE UPPER(r.responsibility_name) = UPPER(:resp_name)
                    AND r.end_date IS NULL OR r.end_date > SYSDATE
                    """,
                    {"resp_name": clean_resp},
                )
                resp_row = cursor.fetchone()
                if not resp_row:
                    chain["responsibility"]["status"] = "ERROR"
                    issues.append(f"Responsibility '{clean_resp}' not found or is disabled.")
                else:
                    chain["responsibility"]["status"] = "PASS"
                    chain["responsibility"]["id"] = resp_row[0]
                    rg_id = resp_row[1]
                    rg_name = resp_row[2]
                    chain["request_group"]["name"] = rg_name
                    chain["request_group"]["id"] = rg_id

                    if not rg_id:
                        chain["request_group"]["status"] = "ERROR"
                        issues.append(f"Responsibility '{clean_resp}' has no Request Group assigned.")
                    else:
                        chain["request_group"]["status"] = "PASS"

                        # 2. Check Concurrent Program in Request Group
                        cursor.execute(
                            """
                            SELECT cp.concurrent_program_id,
                                   cp.concurrent_program_name,
                                   e.execution_method_code,
                                   e.executable_name
                            FROM apps.fnd_request_group_units rgu
                            JOIN apps.fnd_concurrent_programs_vl cp
                                ON rgu.request_unit_id = cp.concurrent_program_id
                                AND rgu.unit_application_id = cp.application_id
                            JOIN apps.fnd_executables_vl e
                                ON cp.executable_id = e.executable_id
                                AND cp.executable_application_id = e.application_id
                            WHERE rgu.request_group_id = :rg_id
                            AND rgu.request_unit_type = 'P'
                            AND UPPER(cp.user_concurrent_program_name) = UPPER(:prog_name)
                            """,
                            {"rg_id": rg_id, "prog_name": clean_prog},
                        )
                        prog_row = cursor.fetchone()
                        if not prog_row:
                            # Try by short name
                            cursor.execute(
                                """
                                SELECT cp.concurrent_program_id,
                                       cp.concurrent_program_name,
                                       e.execution_method_code,
                                       e.executable_name
                                FROM apps.fnd_request_group_units rgu
                                JOIN apps.fnd_concurrent_programs_vl cp
                                    ON rgu.request_unit_id = cp.concurrent_program_id
                                JOIN apps.fnd_executables_vl e
                                    ON cp.executable_id = e.executable_id
                                WHERE rgu.request_group_id = :rg_id
                                AND rgu.request_unit_type = 'P'
                                AND UPPER(cp.concurrent_program_name) = UPPER(:prog_name)
                                """,
                                {"rg_id": rg_id, "prog_name": clean_prog},
                            )
                            prog_row = cursor.fetchone()

                        if not prog_row:
                            chain["concurrent_program"]["status"] = "ERROR"
                            issues.append(
                                f"Concurrent Program '{clean_prog}' is not in Request Group '{rg_name}'. "
                                "Add it via System Administrator → Security → Responsibility → Request Groups."
                            )
                        else:
                            chain["concurrent_program"]["status"] = "PASS"
                            chain["concurrent_program"]["id"] = prog_row[0]
                            chain["executable"]["name"] = prog_row[3]
                            chain["executable"]["method"] = prog_row[2]
                            chain["executable"]["status"] = "PASS"

    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error during chain validation: {str(e)[:200]}",
            "chain": chain,
            "issues": issues,
        }

    overall = "PASS" if not issues else "ERROR"
    return {
        "status": overall,
        "chain": chain,
        "issues": issues,
        "chain_summary": (
            f"{clean_resp} → {chain['request_group']['name']} → "
            f"{clean_prog} → {chain['executable'].get('name', 'N/A')}"
        ),
    }


# ─── 20-Point Pre-Deployment Checklist ───────────────────────────────────────

def run_full_validation_checklist(report_design: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run all 20 pre-deployment checks against a report design object.
    Returns a structured checklist result for each item.
    """
    checks = []

    def chk(name: str, passed: bool, warn: bool = False, detail: str = "") -> Dict:
        return {
            "name": name,
            "status": "PASS" if passed else ("WARNING" if warn else "ERROR"),
            "detail": detail,
        }

    rd = report_design

    # 1. Application
    checks.append(chk("Application", bool(rd.get("application_short_name")),
                       detail=rd.get("application_short_name", "Missing")))

    # 2. Report Name
    checks.append(chk("Report Name", bool(rd.get("report_name")),
                       detail=rd.get("report_name", "Missing")))

    # 3. Short Name
    sn = rd.get("short_name", "")
    checks.append(chk("Short Name", bool(sn) and sn.startswith("XX_"),
                       warn=bool(sn) and not sn.startswith("XX_"),
                       detail=sn or "Missing"))

    # 4. SQL
    sql = rd.get("sql_query", "")
    sql_ok = bool(sql) and "SELECT" in sql.upper() and "FROM" in sql.upper()
    checks.append(chk("SQL Query", sql_ok, detail="Present and valid" if sql_ok else "Missing or invalid"))

    # 5. Parameters
    params = rd.get("parameters", [])
    checks.append(chk("Parameters", True, warn=len(params) == 0,
                       detail=f"{len(params)} parameter(s) defined"))

    # 6. Value Sets
    vs = rd.get("value_sets", [])
    checks.append(chk("Value Sets", True, warn=len(params) > 0 and len(vs) == 0,
                       detail=f"{len(vs)} value set(s) defined"))

    # 7. XML Data Template
    arch = rd.get("architecture", "")
    xml_tmpl = rd.get("xml_data_template", "")
    if "BIP" in arch.upper() or "XML" in arch.upper() or "PUBLISHER" in arch.upper():
        checks.append(chk("XML Data Template", bool(xml_tmpl) and "<dataTemplate" in xml_tmpl,
                           detail="Present" if xml_tmpl else "Missing for BI Publisher architecture"))
    else:
        checks.append(chk("XML Data Template", True, detail="N/A for RDF architecture"))

    # 8. RTF Template
    rtf = rd.get("rtf_template_name", "")
    if "BIP" in arch.upper() or "XML" in arch.upper() or "PUBLISHER" in arch.upper():
        checks.append(chk("RTF Template", bool(rtf),
                           warn=not rtf,
                           detail=rtf or "Not specified — required for BI Publisher output"))
    else:
        checks.append(chk("RTF Template", True, detail="N/A for RDF architecture"))

    # 9. RDF
    rdf = rd.get("rdf_file_name", "")
    if "RDF" in arch.upper():
        checks.append(chk("RDF File", bool(rdf), detail=rdf or "Missing for RDF architecture"))
    else:
        checks.append(chk("RDF File", True, detail="N/A for BI Publisher architecture"))

    # 10. PL/SQL Package
    pkg = rd.get("plsql_package", "")
    checks.append(chk("PL/SQL Package", True, warn=False,
                       detail=pkg or "N/A — not required"))

    # 11. Executable
    exe = rd.get("executable_short_name", "")
    checks.append(chk("Executable", bool(exe), detail=exe or "Missing"))

    # 12. Concurrent Program
    cp = rd.get("concurrent_program_short_name", sn)
    checks.append(chk("Concurrent Program", bool(cp), detail=cp or "Missing"))

    # 13. Program Parameters registered
    cp_params = rd.get("cp_parameters", params)
    checks.append(chk("Concurrent Parameters",
                       len(cp_params) == len(params),
                       warn=len(params) > 0 and len(cp_params) == 0,
                       detail=f"{len(cp_params)}/{len(params)} parameters registered"))

    # 14. Request Group
    rg = rd.get("request_group", "")
    checks.append(chk("Request Group", bool(rg), detail=rg or "Missing"))

    # 15. Responsibility
    resp = rd.get("responsibility_name", "")
    checks.append(chk("Responsibility", bool(resp), detail=resp or "Missing"))

    # 16. XDO / Data Definition
    if "BIP" in arch.upper() or "XML" in arch.upper() or "PUBLISHER" in arch.upper():
        xdo = rd.get("data_definition_code", "")
        checks.append(chk("XDO Data Definition", bool(xdo), detail=xdo or "Missing for BI Publisher"))
    else:
        checks.append(chk("XDO Data Definition", True, detail="N/A for RDF"))

    # 17. File Paths / Filesystem
    appl_top = rd.get("appl_top", "$APPL_TOP")
    checks.append(chk("File Paths", "$" in appl_top or bool(appl_top),
                       detail=appl_top or "Using $APPL_TOP default"))

    # 18. Security
    security = rd.get("security_profile", "")
    checks.append(chk("Security Profile", True, warn=not security,
                       detail=security or "No HRMS Security Profile specified"))

    # 19. Output Format
    out_fmt = rd.get("output_format", "")
    checks.append(chk("Output Format", bool(out_fmt), detail=out_fmt or "Missing"))

    # 20. Rollback Package
    rollback = rd.get("rollback_script", "")
    checks.append(chk("Rollback Package", True, warn=not rollback,
                       detail="Present" if rollback else "Will be generated during deployment"))

    errors = [c for c in checks if c["status"] == "ERROR"]
    warnings_list = [c for c in checks if c["status"] == "WARNING"]
    passes = [c for c in checks if c["status"] == "PASS"]

    return {
        "status": "ERROR" if errors else ("WARNING" if warnings_list else "PASS"),
        "total": len(checks),
        "passed": len(passes),
        "warnings": len(warnings_list),
        "errors": len(errors),
        "checks": checks,
        "deployment_blocked": len(errors) > 0,
    }
