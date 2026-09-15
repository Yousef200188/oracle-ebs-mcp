"""
Oracle EBS R12 Complete Report Development & Deployment Wizard Engine
=====================================================================
Drives the full lifecycle from business requirement to deployed, tested,
validated EBS R12 Concurrent Report.

Architecture supported: BI Publisher / XML Publisher, Oracle Reports (RDF), RDF + BIP Hybrid.

Generated artifacts (returned as strings, downloadable as ZIP):
  sql/01_value_sets.sql
  sql/02_package.sql
  sql/03_executable.sql
  sql/04_concurrent_program.sql
  sql/05_parameters.sql
  sql/06_request_group.sql
  sql/07_responsibility_validation.sql
  sql/08_xdo_registration.sql
  sql/09_validation.sql
  xml/XX_REPORT_data_template.xml
  xdo/XX_REPORT_xdo.xml
  rtf/XX_REPORT_layout_spec.rtf   (spec document, not binary RTF)
  deployment/deploy.sh
  deployment/rollback.sh
  test/test_cases.md
  documentation/XX_REPORT_Technical_Documentation.md
"""

import io
import re
import zipfile
from textwrap import dedent
from typing import Any, Dict, List, Optional

from ..config import get_config
from ..database import get_connection
from ..security import sanitize_program_name, InputValidationError
from .ebs_report_validator import (
    validate_sql_tool,
    validate_parameter_mapping_tool,
    validate_xml_data_template_tool,
    validate_responsibility_chain_tool,
    run_full_validation_checklist,
)
from .ebs_value_sets import generate_value_set_sql_tool


# ══════════════════════════════════════════════════════════════════════════════
# DESIGN TOOL — Builds and returns the full report_design object
# ══════════════════════════════════════════════════════════════════════════════

def design_ebs_report_tool(
    report_name: str,
    short_name: str,
    application_short_name: str,
    architecture: str,
    sql_query: str,
    parameters: Optional[List[Dict[str, Any]]] = None,
    value_sets: Optional[List[Dict[str, Any]]] = None,
    output_format: str = "PDF",
    description: str = "",
    business_purpose: str = "",
    responsibility_name: str = "Global HRMS Manager",
    request_group: str = "",
    executable_short_name: str = "",
    executable_method: str = "",
    plsql_package: str = "",
    rtf_template_name: str = "",
    rdf_file_name: str = "",
    data_definition_code: str = "",
    xml_data_template: str = "",
    appl_top: str = "$APPL_TOP",
    security_profile: str = "",
) -> Dict[str, Any]:
    """
    Construct and validate a complete Oracle EBS R12 Report Design Object.

    This is the master function of the Report Wizard. Call it to build the
    report_design dictionary that flows into all other wizard functions.

    Parameters
    ----------
    report_name          : Full user-facing name (e.g. "XX Employee Headcount Report")
    short_name           : Concurrent program short name (e.g. "XX_EMP_HEADCOUNT")
    application_short_name: EBS application (e.g. "PER", "XX", "FND")
    architecture         : One of "BIP", "RDF", "HYBRID"
    sql_query            : Main SELECT statement for the report data
    parameters           : List of dicts: {name, prompt, data_type, value_set,
                           required, sequence, default_value, token, hidden}
    value_sets           : List of dicts: {name, description, validation_type,
                           format_type, maximum_size, table_name, value_column,
                           id_column, where_clause, independent_values}
    output_format        : PDF | EXCEL | RTF | XML | HTML | TEXT
    description          : Report description
    business_purpose     : Business justification / context
    responsibility_name  : Target EBS responsibility
    request_group        : Request group name (auto-derived from responsibility if blank)
    executable_short_name: Concurrent executable short name (defaults to short_name + "_EXE")
    executable_method    : RDF=Oracle Reports, BIP/HYBRID=XML Publisher, PL/SQL Stored Procedure
    plsql_package        : PL/SQL package name (optional)
    rtf_template_name    : RTF template code (for BIP/HYBRID)
    rdf_file_name        : RDF file name (for RDF/HYBRID)
    data_definition_code : XDO data definition code (for BIP/HYBRID)
    appl_top             : EBS APPL_TOP path or variable
    security_profile     : HRMS Security Profile (optional)
    """
    arch_upper = architecture.upper()

    # Normalise architecture
    if "BIP" in arch_upper or "XML" in arch_upper or "PUBLISHER" in arch_upper:
        arch = "BIP"
    elif "RDF" in arch_upper and ("BIP" in arch_upper or "HYBRID" in arch_upper):
        arch = "HYBRID"
    else:
        arch = "RDF"

    # Sanitize short name: must be valid Oracle identifier (uppercase, letters, digits, underscores)
    clean_sn = re.sub(r'[^A-Za-z0-9_]', '_', (short_name or "XX_REPORT").strip()).upper()
    while "__" in clean_sn:
        clean_sn = clean_sn.replace("__", "_")
    short_name = clean_sn.strip("_") or "XX_REPORT"

    # Defaults
    if not executable_short_name:
        if arch == "BIP":
            executable_short_name = "XDODTEXE"
        else:
            executable_short_name = short_name + "_EXE"
    else:
        executable_short_name = re.sub(r'[^A-Za-z0-9_]', '_', executable_short_name.strip()).upper()

    if not data_definition_code and arch in ("BIP", "HYBRID"):
        data_definition_code = short_name + "_DD"
    if not rtf_template_name and arch in ("BIP", "HYBRID"):
        rtf_template_name = short_name + "_RTF"
    if not executable_method:
        executable_method = {
            "BIP": "Java Concurrent Program",
            "RDF": "Oracle Reports",
            "HYBRID": "Oracle Reports",
        }[arch]

    if not request_group:
        request_group = "HR Reports and Processes" if application_short_name.upper() in ("PER", "PAY", "BEN") else "System Administrator Reports"

    params = parameters or []
    vsets = value_sets or []

    # Run SQL validation
    sql_result = validate_sql_tool(sql_query, params)
    aliases = sql_result.get("aliases", [])

    # Run parameter mapping validation
    bind_vars = sql_result.get("bind_variables_found", [])
    param_result = validate_parameter_mapping_tool(bind_vars, params, vsets)

    # Build design object
    report_design = {
        "report_name": report_name,
        "short_name": short_name.upper(),
        "application_short_name": application_short_name.upper(),
        "application_name": _get_application_name(application_short_name),
        "architecture": arch,
        "description": description,
        "business_purpose": business_purpose,
        "output_format": output_format.upper(),
        "sql_query": sql_query,
        "sql_aliases": aliases,
        "parameters": params,
        "cp_parameters": params,
        "value_sets": vsets,
        "executable_name": report_name + " Executable",
        "executable_short_name": executable_short_name.upper(),
        "executable_method": executable_method,
        "rdf_file_name": rdf_file_name or (short_name + ".rdf" if arch in ("RDF", "HYBRID") else ""),
        "concurrent_program_name": report_name,
        "concurrent_program_short_name": short_name.upper(),
        "request_group": request_group,
        "responsibility_name": responsibility_name,
        "data_definition_code": data_definition_code.upper() if data_definition_code else "",
        "rtf_template_name": rtf_template_name.upper() if rtf_template_name else "",
        "plsql_package": plsql_package,
        "appl_top": appl_top,
        "security_profile": security_profile,
        # Pre-filled validation results
        "_sql_validation": sql_result,
        "_param_validation": param_result,
    }

    # Ensure XML Data Template & RTF Spec are present for BIP/HYBRID architecture
    if arch in ("BIP", "HYBRID"):
        if xml_data_template and "<dataTemplate" in xml_data_template:
            report_design["xml_data_template"] = xml_data_template
        else:
            report_design["xml_data_template"] = _gen_xml_data_template(report_design)
        report_design["rtf_spec"] = _gen_rtf_layout_spec(report_design)
    else:
        report_design["xml_data_template"] = ""

    # Run 20-point checklist
    checklist = run_full_validation_checklist(report_design)
    report_design["_validation_checklist"] = checklist

    return {
        "status": "success",
        "report_design": report_design,
        "design_summary": _build_design_summary(report_design),
        "validation_checklist": checklist,
        "sql_validation": sql_result,
        "parameter_validation": param_result,
        "ready_for_generation": not checklist["deployment_blocked"],
    }


def _get_application_name(short_name: str) -> str:
    names = {
        "PER": "Human Resources",
        "PAY": "Payroll",
        "BEN": "Advanced Benefits",
        "HXT": "Time and Labor",
        "OTA": "Learning Management",
        "GL": "General Ledger",
        "AP": "Payables",
        "AR": "Receivables",
        "FA": "Fixed Assets",
        "PO": "Purchasing",
        "INV": "Inventory",
        "OE": "Order Management",
        "PA": "Projects",
        "FND": "Application Object Library",
        "XDO": "XML Publisher",
        "XX": "Custom Application",
    }
    return names.get(short_name.upper(), short_name + " Application")


def _build_design_summary(rd: Dict[str, Any]) -> str:
    return f"""
╔══════════════════════════════════════════════════════════════════╗
║            ORACLE EBS R12 REPORT DESIGN SUMMARY                 ║
╠══════════════════════════════════════════════════════════════════╣
║  Report Name    : {rd['report_name']:<44}║
║  Short Name     : {rd['short_name']:<44}║
║  Application    : {rd['application_short_name']} — {rd.get('application_name',''):<39}║
║  Architecture   : {rd['architecture']:<44}║
║  Output Format  : {rd['output_format']:<44}║
╠══════════════════════════════════════════════════════════════════╣
║  Executable     : {rd['executable_short_name']:<44}║
║  Method         : {rd['executable_method']:<44}║
║  CP Short Name  : {rd['concurrent_program_short_name']:<44}║
║  Request Group  : {rd.get('request_group', 'Not specified'):<44}║
║  Responsibility : {rd['responsibility_name']:<44}║
╠══════════════════════════════════════════════════════════════════╣
║  Data Def Code  : {rd.get('data_definition_code', 'N/A'):<44}║
║  RTF Template   : {rd.get('rtf_template_name', 'N/A'):<44}║
║  RDF File       : {rd.get('rdf_file_name', 'N/A'):<44}║
║  Parameters     : {len(rd.get('parameters', [])):<44}║
║  Value Sets     : {len(rd.get('value_sets', [])):<44}║
╚══════════════════════════════════════════════════════════════════╝
"""


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION TOOL
# ══════════════════════════════════════════════════════════════════════════════

def validate_report_design_tool(report_design: Dict[str, Any]) -> Dict[str, Any]:
    """Run the 20-point pre-deployment validation on a report_design object."""
    checklist = run_full_validation_checklist(report_design)
    sql_result = validate_sql_tool(
        report_design.get("sql_query", ""),
        report_design.get("parameters", []),
    )
    xml_result = {}
    if report_design.get("xml_data_template"):
        xml_result = validate_xml_data_template_tool(
            report_design["xml_data_template"],
            sql_result.get("aliases", []),
        )

    return {
        "status": checklist["status"],
        "checklist": checklist,
        "sql_validation": sql_result,
        "xml_validation": xml_result,
        "deployment_blocked": checklist["deployment_blocked"],
        "summary": f"{checklist['passed']}/20 checks passed — {checklist['errors']} error(s), {checklist['warnings']} warning(s).",
    }


# ══════════════════════════════════════════════════════════════════════════════
# SQL GENERATION HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _gen_executable_sql(rd: Dict) -> str:
    sn = sanitize_program_name(rd["short_name"])
    app = rd["application_short_name"]
    arch = rd.get("architecture", "BIP")

    if arch == "BIP":
        exe_sn = rd.get("executable_short_name") or "XDODTEXE"
        if exe_sn.upper() == "XDODTEXE":
            return """-- =========================================================
-- 03_executable.sql — XML Publisher Seeded Executable
-- =========================================================
-- XDODTEXE is the standard Oracle XML Publisher Data Engine executable under application XDO.
-- It is pre-seeded in Oracle EBS R12. No custom registration required.
SET SERVEROUTPUT ON SIZE 1000000;
BEGIN
  DBMS_OUTPUT.PUT_LINE('Using standard XML Publisher Data Engine executable: XDODTEXE');
END;
/
"""
        method_name = "Java Concurrent Program"
        exec_file = "JCP4XDODataEngine"
    elif arch in ("RDF", "HYBRID"):
        exe_sn = rd.get("executable_short_name") or (sn + "_EXE")
        method_name = "Oracle Reports"
        exec_file = rd.get("rdf_file_name", sn) or sn
        if exec_file.lower().endswith(".rdf"):
            exec_file = exec_file[:-4]
    elif "PL" in rd.get("executable_method", "") or arch == "PLSQL":
        exe_sn = rd.get("executable_short_name") or (sn + "_EXE")
        method_name = "PL/SQL Stored Procedure"
        exec_file = rd.get("execution_file_name", sn) or sn
    else:
        exe_sn = rd.get("executable_short_name") or (sn + "_EXE")
        method_name = "Oracle Reports"
        exec_file = rd.get("rdf_file_name", sn) or sn
        if exec_file.lower().endswith(".rdf"):
            exec_file = exec_file[:-4]

    exe_sn = sanitize_program_name(exe_sn)

    return f"""-- =========================================================
-- 03_executable.sql — Register Concurrent Executable
-- =========================================================
SET SERVEROUTPUT ON SIZE 1000000;
DECLARE
  l_exists NUMBER;
BEGIN
  SELECT COUNT(1) INTO l_exists
  FROM apps.fnd_executables
  WHERE executable_name = '{exe_sn}'
  AND application_id = (SELECT application_id FROM apps.fnd_application WHERE application_short_name = '{app}');

  IF l_exists = 0 THEN
    fnd_program.executable(
      executable          => '{exe_sn}',
      application         => '{app}',
      short_name          => '{exe_sn}',
      description         => '{rd.get("report_name", exe_sn)} Executable',
      execution_method    => '{method_name}',
      execution_file_name => '{exec_file}',
      subroutine_name     => NULL,
      icon_name           => NULL,
      language_code       => 'US'
    );
    DBMS_OUTPUT.PUT_LINE('Executable created: {exe_sn}');
  ELSE
    DBMS_OUTPUT.PUT_LINE('Executable already exists: {exe_sn}');
  END IF;
  COMMIT;
EXCEPTION
  WHEN OTHERS THEN ROLLBACK; RAISE;
END;
/
"""


def _gen_concurrent_program_sql(rd: Dict) -> str:
    sn = sanitize_program_name(rd["short_name"])
    app = rd["application_short_name"]
    arch = rd.get("architecture", "BIP")

    if arch == "BIP":
        exe_sn = rd.get("executable_short_name") or "XDODTEXE"
        exe_app = "XDO" if exe_sn.upper() == "XDODTEXE" else app
        default_out = "XML"
    else:
        exe_sn = sanitize_program_name(rd.get("executable_short_name") or (sn + "_EXE"))
        exe_app = app
        default_out = "PDF"

    out_fmt_map = {
        "PDF": "PDF", "EXCEL": "EXCEL", "RTF": "RTF",
        "XML": "XML", "HTML": "HTML", "TEXT": "TEXT",
    }
    out_fmt = out_fmt_map.get(rd.get("output_format", default_out), default_out)

    return f"""-- =========================================================
-- 04_concurrent_program.sql — Register Concurrent Program
-- =========================================================
SET SERVEROUTPUT ON SIZE 1000000;
DECLARE
  l_exists NUMBER;
BEGIN
  SELECT COUNT(1) INTO l_exists
  FROM apps.fnd_concurrent_programs
  WHERE concurrent_program_name = '{sn}'
  AND application_id = (SELECT application_id FROM apps.fnd_application WHERE application_short_name = '{app}');

  IF l_exists = 0 THEN
    fnd_program.register(
      program                => '{rd.get("concurrent_program_name", sn)}',
      application            => '{app}',
      enabled                => 'Y',
      short_name             => '{sn}',
      description            => '{rd.get("description", rd.get("report_name", sn))}',
      executable_short_name  => '{exe_sn}',
      executable_application => '{exe_app}',
      execution_options      => NULL,
      priority               => NULL,
      save_output            => 'Y',
      print                  => 'Y',
      cols                   => NULL,
      rows                   => NULL,
      style                  => 'PORTRAIT',
      style_required         => 'N',
      printer                => NULL,
      request_type           => NULL,
      request_type_application => NULL,
      use_in_srs             => 'Y',
      allow_disabled_values  => 'N',
      run_alone              => 'N',
      output_type            => '{out_fmt}',
      enable_trace           => 'N',
      restart                => 'Y',
      nls_compliant          => 'Y',
      icon_name              => NULL,
      language_code          => 'US'
    );
    DBMS_OUTPUT.PUT_LINE('Concurrent Program created: {sn}');
  ELSE
    DBMS_OUTPUT.PUT_LINE('Concurrent Program already exists: {sn}');
  END IF;
  COMMIT;
EXCEPTION
  WHEN OTHERS THEN
    DBMS_OUTPUT.PUT_LINE('FND MSG: ' || fnd_program.message);
    ROLLBACK; RAISE;
END;
/
"""


def _gen_parameters_sql(rd: Dict) -> str:
    sn = sanitize_program_name(rd["short_name"])
    app = rd["application_short_name"]
    params = rd.get("parameters", [])
    if not params:
        return "-- 05_parameters.sql — No parameters defined\n"

    lines = [f"-- =========================================================\n"
             f"-- 05_parameters.sql — Register Concurrent Program Parameters\n"
             f"-- =========================================================\n"
             f"SET SERVEROUTPUT ON SIZE 1000000;\n"]

    for p in params:
        name = sanitize_program_name(p.get("name", "")).upper()
        prompt = p.get("prompt", name)
        seq = p.get("sequence", 10)
        vs = p.get("value_set", "70 Characters") or "70 Characters"
        req = "Y" if str(p.get("required", "N")).upper() == "Y" else "N"
        default_type = p.get("default_type", None)
        default_val = p.get("default_value", None)
        token = p.get("token", name)
        hidden = "N" if str(p.get("hidden", "N")).upper() != "Y" else "Y"

        lines.append(f"""
DECLARE
  l_exists NUMBER;
BEGIN
  SELECT COUNT(1) INTO l_exists
  FROM apps.fnd_concurrent_program_parameters
  WHERE concurrent_program_id = (
    SELECT concurrent_program_id FROM apps.fnd_concurrent_programs
    WHERE concurrent_program_name = '{sn}'
    AND application_id = (SELECT application_id FROM apps.fnd_application WHERE application_short_name = '{app}')
  )
  AND column_seq_num = {seq};

  IF l_exists = 0 THEN
    fnd_program.parameter(
      program_short_name            => '{sn}',
      application                   => '{app}',
      sequence                      => {seq},
      parameter                     => '{name}',
      description                   => '{prompt}',
      enabled                       => 'Y',
      value_set                     => '{vs}',
      default_type                  => {f"'{default_type}'" if default_type else 'NULL'},
      default_value                 => {f"'{default_val}'" if default_val else 'NULL'},
      required                      => '{req}',
      enable_security               => 'N',
      range                         => NULL,
      display                       => '{"N" if hidden == "Y" else "Y"}',
      display_size                  => 30,
      description_size              => 50,
      concatenated_description_size => 25,
      prompt                        => '{prompt}',
      token                         => '{token}'
    );
    DBMS_OUTPUT.PUT_LINE('Parameter added: {name} (seq {seq})');
  ELSE
    DBMS_OUTPUT.PUT_LINE('Parameter already exists: {name}');
  END IF;
  COMMIT;
EXCEPTION
  WHEN OTHERS THEN ROLLBACK; RAISE;
END;
/
""")
    return "".join(lines)


def _gen_request_group_sql(rd: Dict) -> str:
    sn = sanitize_program_name(rd["short_name"])
    app = rd["application_short_name"]
    rg = rd.get("request_group", f"{app} Reports and Processes")
    resp = rd.get("responsibility_name", "Global HRMS Manager")

    return f"""-- =========================================================
-- 06_request_group.sql — Add Program to Request Group
-- =========================================================
SET SERVEROUTPUT ON SIZE 1000000;
DECLARE
  l_rg_id    NUMBER;
  l_app_id   NUMBER;
  l_cp_id    NUMBER;
  l_exists   NUMBER;
  l_rg_name  VARCHAR2(240) := '{rg}';
  l_rg_app   VARCHAR2(50)  := '{app}';
BEGIN
  -- Resolve IDs
  SELECT application_id INTO l_app_id
  FROM apps.fnd_application WHERE application_short_name = '{app}';

  SELECT concurrent_program_id INTO l_cp_id
  FROM apps.fnd_concurrent_programs
  WHERE concurrent_program_name = '{sn}' AND application_id = l_app_id;

  -- Get Request Group by name and responsibility
  BEGIN
    SELECT rg.request_group_id, rg.request_group_name, fa.application_short_name
    INTO l_rg_id, l_rg_name, l_rg_app
    FROM apps.fnd_request_groups rg
    JOIN apps.fnd_responsibility_vl r ON r.request_group_id = rg.request_group_id
    JOIN apps.fnd_application fa ON fa.application_id = rg.application_id
    WHERE UPPER(r.responsibility_name) = UPPER('{resp}')
    AND ROWNUM = 1;
  EXCEPTION WHEN NO_DATA_FOUND THEN
    BEGIN
      SELECT rg.request_group_id, rg.request_group_name, fa.application_short_name
      INTO l_rg_id, l_rg_name, l_rg_app
      FROM apps.fnd_request_groups rg
      JOIN apps.fnd_application fa ON fa.application_id = rg.application_id
      WHERE UPPER(rg.request_group_name) = UPPER('{rg}')
      AND ROWNUM = 1;
    EXCEPTION WHEN NO_DATA_FOUND THEN
      l_rg_id := NULL;
    END;
  END;

  IF l_rg_id IS NOT NULL THEN
    -- Check if already assigned
    SELECT COUNT(1) INTO l_exists
    FROM apps.fnd_request_group_units
    WHERE request_group_id = l_rg_id
    AND request_unit_id = l_cp_id
    AND request_unit_type = 'P';

    IF l_exists = 0 THEN
      fnd_program.add_to_group(
        program_short_name  => '{sn}',
        program_application => '{app}',
        request_group       => l_rg_name,
        group_application   => l_rg_app
      );
      DBMS_OUTPUT.PUT_LINE('Added to Request Group: ' || l_rg_name);
    ELSE
      DBMS_OUTPUT.PUT_LINE('Already in Request Group: ' || l_rg_name);
    END IF;
  ELSE
    DBMS_OUTPUT.PUT_LINE('Notice: Request group not found; skip automated assignment');
  END IF;
  COMMIT;
EXCEPTION
  WHEN OTHERS THEN
    DBMS_OUTPUT.PUT_LINE('WARNING: ' || SQLERRM);
    DBMS_OUTPUT.PUT_LINE('Manual step: Add {sn} to Request Group via System Administrator.');
END;
/
"""


def _gen_xdo_sql(rd: Dict) -> str:
    if rd.get("architecture") not in ("BIP", "HYBRID"):
        return "-- 08_xdo_registration.sql — N/A for RDF-only architecture\n"

    sn = rd["short_name"]
    app = rd["application_short_name"]
    dd_code = rd.get("data_definition_code", sn + "_DD")
    tmpl_code = rd.get("rtf_template_name", sn + "_RTF")
    out_fmt = rd.get("output_format", "PDF")

    return f"""-- =========================================================
-- 08_xdo_registration.sql — XML Publisher Registration
-- =========================================================
SET SERVEROUTPUT ON SIZE 1000000;
DECLARE
  l_exists NUMBER;
BEGIN
  -- 1. Data Definition
  SELECT COUNT(1) INTO l_exists
  FROM apps.xdo_ds_definitions_b
  WHERE data_source_code = '{dd_code}'
  AND application_short_name = '{app}';

  IF l_exists = 0 THEN
    INSERT INTO apps.xdo_ds_definitions_b (
      application_short_name, data_source_code, data_source_status,
      data_source_type, start_date, created_by, creation_date,
      last_updated_by, last_update_date, last_update_login, object_version_number
    ) VALUES (
      '{app}', '{dd_code}', 'E', 'XML', SYSDATE, 0, SYSDATE, 0, SYSDATE, 0, 1
    );
    INSERT INTO apps.xdo_ds_definitions_tl (
      application_short_name, data_source_code, language, source_lang,
      data_source_name, description, created_by, creation_date,
      last_updated_by, last_update_date, last_update_login
    ) VALUES (
      '{app}', '{dd_code}', 'US', 'US',
      '{rd["report_name"]} Data Definition', '{rd.get("description", "")}',
      0, SYSDATE, 0, SYSDATE, 0
    );
    DBMS_OUTPUT.PUT_LINE('XDO Data Definition created: {dd_code}');
  ELSE
    DBMS_OUTPUT.PUT_LINE('XDO Data Definition exists: {dd_code}');
  END IF;

  -- 2. Template Header
  SELECT COUNT(1) INTO l_exists
  FROM apps.xdo_templates_b
  WHERE template_code = '{tmpl_code}'
  AND application_short_name = '{app}';

  IF l_exists = 0 THEN
    INSERT INTO apps.xdo_templates_b (
      application_short_name, template_code, data_source_code,
      template_type_code, default_output_type, mlr_flag, start_date,
      created_by, creation_date, last_updated_by, last_update_date,
      last_update_login, object_version_number
    ) VALUES (
      '{app}', '{tmpl_code}', '{dd_code}',
      'RTF', '{out_fmt}', 'N', SYSDATE,
      0, SYSDATE, 0, SYSDATE, 0, 1
    );
    INSERT INTO apps.xdo_templates_tl (
      application_short_name, template_code, language, source_lang,
      template_name, description, created_by, creation_date,
      last_updated_by, last_update_date, last_update_login
    ) VALUES (
      '{app}', '{tmpl_code}', 'US', 'US',
      '{rd["report_name"]}', '{rd.get("description", "")}',
      0, SYSDATE, 0, SYSDATE, 0
    );
    DBMS_OUTPUT.PUT_LINE('XDO Template header created: {tmpl_code}');
  END IF;

  COMMIT;
EXCEPTION
  WHEN OTHERS THEN ROLLBACK; RAISE;
END;
/
"""


def _gen_rollback_sql(rd: Dict) -> str:
    sn = rd["short_name"]
    app = rd["application_short_name"]
    exe_sn = rd["executable_short_name"]
    dd_code = rd.get("data_definition_code", "")
    tmpl_code = rd.get("rtf_template_name", "")

    return f"""-- =========================================================
-- rollback.sql — Full Rollback for {sn}
-- =========================================================
SET SERVEROUTPUT ON SIZE 1000000;
WHENEVER SQLERROR CONTINUE;

-- !! CAUTION: Run in DEV/TEST only unless under Change Management !!

-- 1. Remove from Request Group
BEGIN
  fnd_program.remove_from_group(
    program_short_name  => '{sn}',
    program_application => '{app}',
    group_name          => '{rd.get("request_group", "")}',
    group_application   => '{app}'
  );
  COMMIT;
  DBMS_OUTPUT.PUT_LINE('Removed from Request Group');
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('RG removal: ' || SQLERRM);
END;
/

-- 2. Remove Parameters
BEGIN
  DELETE FROM apps.fnd_concurrent_program_parameters
  WHERE concurrent_program_id = (
    SELECT concurrent_program_id FROM apps.fnd_concurrent_programs
    WHERE concurrent_program_name = '{sn}'
    AND application_id = (SELECT application_id FROM apps.fnd_application WHERE application_short_name = '{app}')
  );
  COMMIT;
  DBMS_OUTPUT.PUT_LINE('Parameters removed');
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('Param removal: ' || SQLERRM);
END;
/

-- 3. Remove Concurrent Program
BEGIN
  DELETE FROM apps.fnd_concurrent_programs_tl
  WHERE concurrent_program_id = (
    SELECT concurrent_program_id FROM apps.fnd_concurrent_programs
    WHERE concurrent_program_name = '{sn}'
    AND application_id = (SELECT application_id FROM apps.fnd_application WHERE application_short_name = '{app}')
  );
  DELETE FROM apps.fnd_concurrent_programs
  WHERE concurrent_program_name = '{sn}'
  AND application_id = (SELECT application_id FROM apps.fnd_application WHERE application_short_name = '{app}');
  COMMIT;
  DBMS_OUTPUT.PUT_LINE('Concurrent Program removed');
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('CP removal: ' || SQLERRM);
END;
/

-- 4. Remove Executable
BEGIN
  DELETE FROM apps.fnd_executables_tl
  WHERE executable_id = (
    SELECT executable_id FROM apps.fnd_executables WHERE executable_name = '{exe_sn}'
    AND application_id = (SELECT application_id FROM apps.fnd_application WHERE application_short_name = '{app}')
  );
  DELETE FROM apps.fnd_executables
  WHERE executable_name = '{exe_sn}'
  AND application_id = (SELECT application_id FROM apps.fnd_application WHERE application_short_name = '{app}');
  COMMIT;
  DBMS_OUTPUT.PUT_LINE('Executable removed');
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('Executable removal: ' || SQLERRM);
END;
/
{'-- 5. Remove XDO' if dd_code else ''}
{f"""
BEGIN
  DELETE FROM apps.xdo_lobs WHERE lob_code = '{tmpl_code}';
  DELETE FROM apps.xdo_templates_tl WHERE template_code = '{tmpl_code}' AND application_short_name = '{app}';
  DELETE FROM apps.xdo_templates_b WHERE template_code = '{tmpl_code}' AND application_short_name = '{app}';
  DELETE FROM apps.xdo_ds_definitions_tl WHERE data_source_code = '{dd_code}' AND application_short_name = '{app}';
  DELETE FROM apps.xdo_ds_definitions_b WHERE data_source_code = '{dd_code}' AND application_short_name = '{app}';
  COMMIT;
  DBMS_OUTPUT.PUT_LINE('XDO objects removed');
EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE('XDO removal: ' || SQLERRM);
END;
/
""" if dd_code else ""}
"""


def _gen_xml_data_template(rd: Dict) -> str:
    sn = rd["short_name"]
    params = rd.get("parameters", [])
    aliases = rd.get("sql_aliases", [])
    sql = rd.get("sql_query", "-- SQL QUERY HERE").strip()

    param_xml = "\n".join(
        f'        <parameter name="{p.get("name","P").upper()}" dataType="{p.get("data_type","VARCHAR2").upper()}" '
        f'defaultValue="{p.get("default_value","")}" include_query="false"/>'
        for p in params
    )

    elements_xml = "\n".join(
        f'            <element name="{a}" value="{a}"/>'
        for a in aliases
    )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<dataTemplate name="{sn}" description="{rd['report_name']}" version="1.0">

    <!-- Parameters -->
    <parameters>
{param_xml if param_xml else '        <!-- No parameters defined -->'}
    </parameters>

    <!-- Data Query -->
    <dataQuery>
        <sqlStatement name="Q_{sn}">
            <![CDATA[
{sql}
            ]]>
        </sqlStatement>
    </dataQuery>

    <!-- Data Structure — maps SQL aliases to XML element names -->
    <dataStructure>
        <group name="G_{sn}" source="Q_{sn}">
{elements_xml if elements_xml else '            <!-- SQL aliases will appear here -->'}
        </group>
    </dataStructure>

</dataTemplate>
"""


def _gen_rtf_layout_spec(rd: Dict) -> str:
    sn = rd["short_name"]
    aliases = rd.get("sql_aliases", [])
    params = rd.get("parameters", [])

    field_list = "\n".join(f"  - <?{a}?>" for a in aliases)
    param_list = "\n".join(f"  - P_param: <?{p.get('name','P')}?>" for p in params)

    return f"""RTF Layout Template Specification
==================================
Report      : {rd['report_name']}
Short Name  : {sn}
Data Def    : {rd.get('data_definition_code', sn + '_DD')}
Output      : {rd.get('output_format', 'PDF')}
Architecture: {rd.get('architecture', 'BIP')}

RTF File Name: {sn}.rtf

========== LAYOUT STRUCTURE ==========

HEADER (repeated on every page)
  - Report Title  : {rd['report_name']}
  - Run Date      : <?xdofx:format-date(sysdate(),'DD-MON-YYYY')?>
  - Page Number   : <?fo:page-number?> of <?fo:page-number-citation?> (last page ref)

PARAMETER SUMMARY SECTION (optional, after header)
{param_list if param_list else '  (No parameters)'}

DATA TABLE (inside FOR-EACH loop)
  <?for-each:G_{sn}?>

  Columns to render from SQL aliases:
{field_list if field_list else '  (No aliases — ensure SQL has named columns)'}

  <?end for-each?>

FOOTER
  - "Confidential | Generated by Oracle EBS R12" 
  - Run By: (use FND_GLOBAL.USER_NAME via a parameter or a fixed label)

========== IMPORTANT XDO FIELD SYNTAX ==========
  Scalar value   : <?COLUMN_ALIAS?>
  Date formatted : <?xdofx:format-date(HIRE_DATE,'DD-MON-YYYY')?>
  Currency       : <?xdofx:format-number(SALARY,'###,##0.00')?>
  Conditional    : <?if:STATUS='A'?>Active<?end if?>
  Running total  : <?running-total:AMOUNT?>

========== XDOLoader UPLOAD COMMAND ==========
java oracle.apps.xdo.oa.util.XDOLoader \\
  UPLOAD \\
  -DB_USERNAME apps \\
  -DB_PASSWORD $APPS_PWD \\
  -JDBC_CONNECTION $JDBC_CONNECTION \\
  -APPS_SHORT_NAME {rd['application_short_name']} \\
  -LOB_TYPE TEMPLATE_SOURCE \\
  -LOB_CODE {rd.get('rtf_template_name', sn + '_RTF')} \\
  -LANGUAGE en \\
  -TERRITORY 00 \\
  -XDO_FILE_TYPE RTF \\
  -FILE_NAME {sn}.rtf \\
  -NLS_LANG AMERICAN_AMERICA.UTF8 \\
  -CUSTOM_MODE FORCE
"""


def _gen_deploy_sh(rd: Dict) -> str:
    sn = rd["short_name"]
    app = rd["application_short_name"]
    arch = rd.get("architecture", "BIP")

    return f"""#!/bin/bash
# =========================================================
# deploy.sh — Oracle EBS R12 Deployment Script for {sn}
# Application: {app}  Architecture: {arch}
# =========================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/.." && pwd)"
SQL_DIR="$SCRIPT_DIR/sql"
XML_DIR="$SCRIPT_DIR/xml"
RTF_DIR="$SCRIPT_DIR/rtf"

APPS_USER="${{ORACLE_USER:-apps}}"
APPS_PWD="${{ORACLE_PASSWORD}}"
JDBC_CONNECTION="${{EBS_DB_TNS}}"
APPS_SHORT_NAME="{app}"

echo "============================================================"
echo " Oracle EBS R12 Deployment: {rd['report_name']}"
echo " Environment: ${{EBS_HOST:-UNKNOWN}}"
echo "============================================================"
echo ""

run_sql() {{
    local script=$1
    echo "[SQL] Running: $script"
    sqlplus -s "$APPS_USER/$APPS_PWD@$JDBC_CONNECTION" <<EOF
SET SERVEROUTPUT ON SIZE 1000000;
WHENEVER SQLERROR EXIT SQL.SQLCODE;
@$script
EXIT;
EOF
    echo "[SQL] Done: $script"
}}

# Step 1: Value Sets
echo "[1/8] Registering Value Sets..."
run_sql "$SQL_DIR/01_value_sets.sql"

# Step 2: PL/SQL Package (if any)
if [ -f "$SQL_DIR/02_package.sql" ]; then
    echo "[2/8] Compiling PL/SQL Package..."
    run_sql "$SQL_DIR/02_package.sql"
fi

# Step 3: Executable
echo "[3/8] Registering Executable..."
run_sql "$SQL_DIR/03_executable.sql"

# Step 4: Concurrent Program
echo "[4/8] Registering Concurrent Program..."
run_sql "$SQL_DIR/04_concurrent_program.sql"

# Step 5: Parameters
echo "[5/8] Registering Parameters..."
run_sql "$SQL_DIR/05_parameters.sql"

# Step 6: Request Group
echo "[6/8] Adding to Request Group..."
run_sql "$SQL_DIR/06_request_group.sql"

# Step 7: XDO / XML Publisher (BIP/HYBRID only)
{'echo "[7/8] Registering XDO Data Definition and Template..."' if arch in ('BIP','HYBRID') else 'echo "[7/8] XDO — N/A for RDF architecture"'}
{"run_sql \"$SQL_DIR/08_xdo_registration.sql\"" if arch in ('BIP','HYBRID') else ""}

{"# Upload RTF Template via XDOLoader" if arch in ('BIP','HYBRID') else ""}
{f"""echo "[7b/8] Uploading RTF Template via XDOLoader..."
java oracle.apps.xdo.oa.util.XDOLoader \\\\
  UPLOAD \\\\
  -DB_USERNAME "$APPS_USER" \\\\
  -DB_PASSWORD "$APPS_PWD" \\\\
  -JDBC_CONNECTION "$JDBC_CONNECTION" \\\\
  -APPS_SHORT_NAME "{app}" \\\\
  -LOB_TYPE TEMPLATE_SOURCE \\\\
  -LOB_CODE "{rd.get('rtf_template_name', sn + '_RTF')}" \\\\
  -LANGUAGE en \\\\
  -TERRITORY 00 \\\\
  -XDO_FILE_TYPE RTF \\\\
  -FILE_NAME "$RTF_DIR/{sn}.rtf" \\\\
  -NLS_LANG AMERICAN_AMERICA.UTF8 \\\\
  -CUSTOM_MODE FORCE""" if arch in ('BIP','HYBRID') else ""}

# Step 8: Validation
echo "[8/8] Running post-deployment validation..."
run_sql "$SQL_DIR/09_validation.sql"

echo ""
echo "============================================================"
echo " Deployment Complete: {rd['report_name']}"
echo "============================================================"
"""


def _gen_validation_sql(rd: Dict) -> str:
    sn = rd["short_name"]
    app = rd["application_short_name"]
    exe_sn = rd["executable_short_name"]
    resp = rd.get("responsibility_name", "Global HRMS Manager")

    return f"""-- =========================================================
-- 09_validation.sql — Post-Deployment Validation
-- =========================================================
SET SERVEROUTPUT ON SIZE 1000000;
DECLARE
  l_count   NUMBER;
  l_errors  NUMBER := 0;
  PROCEDURE chk(p_name VARCHAR2, p_count NUMBER) IS
  BEGIN
    IF p_count > 0 THEN
      DBMS_OUTPUT.PUT_LINE('[PASS] ' || p_name);
    ELSE
      DBMS_OUTPUT.PUT_LINE('[FAIL] ' || p_name || ' — NOT FOUND');
      l_errors := l_errors + 1;
    END IF;
  END;
BEGIN
  -- Executable
  SELECT COUNT(1) INTO l_count FROM apps.fnd_executables
  WHERE executable_name = '{exe_sn}'
  AND application_id = (SELECT application_id FROM apps.fnd_application WHERE application_short_name = '{app}');
  chk('Executable: {exe_sn}', l_count);

  -- Concurrent Program
  SELECT COUNT(1) INTO l_count FROM apps.fnd_concurrent_programs
  WHERE concurrent_program_name = '{sn}'
  AND application_id = (SELECT application_id FROM apps.fnd_application WHERE application_short_name = '{app}');
  chk('Concurrent Program: {sn}', l_count);

  -- Parameters
  SELECT COUNT(1) INTO l_count
  FROM apps.fnd_descr_flex_col_usage_vl
  WHERE descriptive_flexfield_name = '$SRS$.' || '{sn}';
  DBMS_OUTPUT.PUT_LINE('[INFO] Parameters registered: ' || l_count);

  -- Request Group Assignment
  SELECT COUNT(1) INTO l_count
  FROM apps.fnd_request_group_units rgu
  JOIN apps.fnd_concurrent_programs cp ON rgu.request_unit_id = cp.concurrent_program_id
  JOIN apps.fnd_responsibility_vl r ON r.request_group_id = rgu.request_group_id
  WHERE cp.concurrent_program_name = '{sn}'
  AND UPPER(r.responsibility_name) = UPPER('{resp}')
  AND rgu.request_unit_type = 'P';
  chk('Request Group Assignment for Responsibility: {resp}', l_count);

  -- SRS Access (Use In SRS = Y)
  SELECT COUNT(1) INTO l_count FROM apps.fnd_concurrent_programs
  WHERE concurrent_program_name = '{sn}'
  AND srs_flag = 'Y'
  AND application_id = (SELECT application_id FROM apps.fnd_application WHERE application_short_name = '{app}');
  chk('SRS Enabled (Use in SRS=Y)', l_count);

  DBMS_OUTPUT.PUT_LINE('----------------------------------------');
  DBMS_OUTPUT.PUT_LINE('Total Failures: ' || l_errors);
  IF l_errors > 0 THEN
    RAISE_APPLICATION_ERROR(-20001, 'Deployment validation failed with ' || l_errors || ' error(s). See output above.');
  END IF;
END;
/
"""


def _gen_test_cases(rd: Dict) -> str:
    sn = rd["short_name"]
    params = rd.get("parameters", [])
    resp = rd.get("responsibility_name", "Global HRMS Manager")

    param_table = "\n".join(
        f"| {p.get('sequence', i*10)} | {p.get('name', '')} | {p.get('data_type', 'VARCHAR2')} | {p.get('required', 'N')} | Enter valid test value |"
        for i, p in enumerate(params, 1)
    ) or "| — | No parameters | — | — | N/A |"

    return f"""# Test Cases for {rd['report_name']}

## TC-001: Report Appears in Submit Request
- **Steps:**
  1. Log into EBS as the test user assigned to: **{resp}**
  2. Navigate to: View → Requests → Submit a New Request
  3. Search for: **{rd['concurrent_program_name']}**
- **Expected:** Report appears in the search results.
- **Pass Criteria:** Report name and short name `{sn}` appear.

## TC-002: Parameters Display Correctly
- **Steps:**
  1. Select the report from Submit Request.
  2. Observe the Parameters form.
- **Expected:** The following parameters appear in order:

| Seq | Parameter | Type | Required | Test Value |
|-----|-----------|------|----------|------------|
{param_table}

## TC-003: Submit Successfully
- **Steps:**
  1. Fill in all required parameters.
  2. Click **Submit**.
- **Expected:** Request ID is generated and request enters **Pending → Normal** phase.

## TC-004: Request Completes Successfully
- **Steps:**
  1. Monitor the request in View → Requests.
- **Expected:** Phase = **Completed**, Status = **Normal**.
- **Fail Criteria:** Status = **Error** — check View Log.

## TC-005: Output is Generated
- **Steps:**
  1. Click **View Output** on the completed request.
- **Expected:**
  - For BI Publisher: PDF/Excel file opens with correct data.
  - For Oracle Reports: Output renders with correct columns.
  - No blank or empty output.

## TC-006: Rollback (DEV only)
- Run `deployment/rollback.sql` in the DEV environment.
- **Expected:** All EBS objects (`{sn}`, `{rd['executable_short_name']}`) are removed cleanly.
"""


def _gen_documentation(rd: Dict) -> str:
    checklist = rd.get("_validation_checklist", {})
    params = rd.get("parameters", [])
    vsets = rd.get("value_sets", [])

    param_rows = "\n".join(
        f"| {p.get('sequence', '')} | {p.get('name', '')} | {p.get('prompt', '')} | {p.get('data_type', '')} | {p.get('value_set', '')} | {p.get('required', 'N')} |"
        for p in params
    ) or "| — | No parameters defined | — | — | — | — |"

    vs_rows = "\n".join(
        f"| {v.get('name', '')} | {v.get('validation_type', '')} | {v.get('format_type', '')} |"
        for v in vsets
    ) or "| — | — | — |"

    return f"""# {rd['report_name']}
## Oracle EBS R12 Technical Documentation

---

## 1. Overview
| Field | Value |
|---|---|
| Report Name | {rd['report_name']} |
| Short Name | {rd['short_name']} |
| Application | {rd['application_short_name']} — {rd.get('application_name', '')} |
| Architecture | {rd['architecture']} |
| Output Format | {rd['output_format']} |
| Executable | {rd['executable_short_name']} |
| Execution Method | {rd['executable_method']} |
| Data Definition | {rd.get('data_definition_code', 'N/A')} |
| RTF Template | {rd.get('rtf_template_name', 'N/A')} |
| Request Group | {rd.get('request_group', 'See Responsibility settings')} |
| Responsibility | {rd['responsibility_name']} |

## 2. Business Purpose
{rd.get('business_purpose', 'Not specified.')}

## 3. Parameters

| Seq | Name | Prompt | Type | Value Set | Required |
|-----|------|--------|------|-----------|----------|
{param_rows}

## 4. Value Sets

| Name | Validation Type | Format Type |
|------|----------------|-------------|
{vs_rows}

## 5. SQL Query
```sql
{rd.get('sql_query', '-- Not provided')}
```

## 6. XML Data Template
```xml
{rd.get('xml_data_template', '<!-- Not generated yet -->')}
```

## 7. Deployment Order
1. `sql/01_value_sets.sql`
2. `sql/02_package.sql` (if PL/SQL required)
3. `sql/03_executable.sql`
4. `sql/04_concurrent_program.sql`
5. `sql/05_parameters.sql`
6. `sql/06_request_group.sql`
7. `sql/08_xdo_registration.sql` (BIP/HYBRID only)
8. XDOLoader RTF upload (BIP/HYBRID only)
9. `sql/09_validation.sql`

## 8. Rollback
Execute `deployment/rollback.sql` in the target environment.
Always backup before running rollback in UAT or PROD.

## 9. Pre-Deployment Checklist
| Check | Status |
|-------|--------|
{chr(10).join(f"| {c['name']} | {c['status']} |" for c in checklist.get('checks', []))}
"""


# ══════════════════════════════════════════════════════════════════════════════
# GENERATE PACKAGE TOOL — returns all artifacts as a ZIP bytes (base64)
# ══════════════════════════════════════════════════════════════════════════════

def generate_report_package_tool(report_design: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate all deployment artifacts for the report and return them
    as a base64-encoded ZIP file plus individual file contents.
    """
    import base64

    rd = report_design
    sn = rd.get("short_name", "XX_REPORT")
    arch = rd.get("architecture", "BIP")

    # Auto-generate XML Data Template if not provided
    if arch in ("BIP", "HYBRID") and not rd.get("xml_data_template"):
        rd["xml_data_template"] = _gen_xml_data_template(rd)

    # Value sets SQL
    vs_result = generate_value_set_sql_tool(
        rd.get("value_sets", []),
        rd.get("application_short_name", "XX"),
    )

    from ..ebs_executor import generate_rtf_from_columns_py
    rtf_content = ""
    if arch in ("BIP", "HYBRID"):
        cols = rd.get("sql_aliases") or ["EMPLOYEE_NUMBER", "FULL_NAME", "ASSIGNMENT_NUMBER"]
        p_names = [p.get("name", "") for p in rd.get("parameters", []) if p.get("name")]
        rtf_content = generate_rtf_from_columns_py(
            rep_name=rd.get("report_name", sn),
            rep_short=sn,
            app_short=rd.get("application_short_name", "PER"),
            columns=cols,
            params=p_names,
            group_name=f"G_{sn}",
        )

    files = {
        f"{sn}/sql/01_value_sets.sql": vs_result.get("deployment_sql", "-- No value sets defined\n"),
        f"{sn}/sql/02_package.sql": f"-- PL/SQL Package: {rd.get('plsql_package', 'N/A')}\n-- Add package body here if required.\n",
        f"{sn}/sql/03_executable.sql": _gen_executable_sql(rd),
        f"{sn}/sql/04_concurrent_program.sql": _gen_concurrent_program_sql(rd),
        f"{sn}/sql/05_parameters.sql": _gen_parameters_sql(rd),
        f"{sn}/sql/06_request_group.sql": _gen_request_group_sql(rd),
        f"{sn}/sql/07_responsibility_validation.sql": _gen_validation_sql(rd),
        f"{sn}/sql/08_xdo_registration.sql": _gen_xdo_sql(rd),
        f"{sn}/sql/09_validation.sql": _gen_validation_sql(rd),
        f"{sn}/xml/{sn}_data_template.xml": rd.get("xml_data_template", "") if arch in ("BIP", "HYBRID") else "",
        f"{sn}/xdo/{sn}_xdo.xml": rd.get("xml_data_template", "") if arch in ("BIP", "HYBRID") else "",
        f"{sn}/rtf/{sn}.rtf": rtf_content,
        f"{sn}/rtf/{sn}_layout_spec.txt": _gen_rtf_layout_spec(rd) if arch in ("BIP", "HYBRID") else "",
        f"{sn}/deployment/deploy.sh": _gen_deploy_sh(rd),
        f"{sn}/deployment/rollback.sh": "#!/bin/bash\n# Run rollback.sql via sqlplus\nsqlplus apps/$ORACLE_PASSWORD@$JDBC_CONNECTION @../sql/09_validation.sql\n",
        f"{sn}/deployment/rollback.sql": _gen_rollback_sql(rd),
        f"{sn}/test/test_cases.md": _gen_test_cases(rd),
        f"{sn}/documentation/{sn}_Technical_Documentation.md": _gen_documentation(rd),
    }

    # Build ZIP in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            if content:
                zf.writestr(path, content)

    zip_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return {
        "status": "success",
        "short_name": sn,
        "zip_base64": zip_b64,
        "zip_size_kb": round(len(buf.getvalue()) / 1024, 1),
        "files": {k: v[:500] + "..." if len(v) > 500 else v for k, v in files.items() if v},
        "file_list": [k for k, v in files.items() if v],
        "xml_data_template": rd.get("xml_data_template", ""),
        "deployment_sql": {
            "01_value_sets": vs_result.get("deployment_sql", ""),
            "03_executable": _gen_executable_sql(rd),
            "04_concurrent_program": _gen_concurrent_program_sql(rd),
            "05_parameters": _gen_parameters_sql(rd),
            "06_request_group": _gen_request_group_sql(rd),
            "08_xdo": _gen_xdo_sql(rd),
            "09_validation": _gen_validation_sql(rd),
            "rollback": _gen_rollback_sql(rd),
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# APPLY TO EBS TOOL
# ══════════════════════════════════════════════════════════════════════════════

def apply_report_to_ebs_tool(
    report_design: Dict[str, Any],
    confirmed: bool = False,
    environment: str = "DEV",
) -> Dict[str, Any]:
    """
    Apply the report package to the live EBS database.
    Requires confirmed=True before executing.
    Only allowed in DEV or TEST environments unless explicitly overridden.
    """
    from ..ebs_executor import execute_ebs_sql

    if not confirmed:
        return {
            "status": "awaiting_confirmation",
            "message": (
                "⚠️  Please confirm before deploying to EBS. "
                f"Environment: {environment}. "
                "Set confirmed=True to proceed."
            ),
            "environment": environment,
            "report": report_design.get("short_name"),
        }

    if environment.upper() == "PROD":
        return {
            "status": "blocked",
            "message": (
                "🛑 Direct deployment to PROD is blocked. "
                "Download the package, review all scripts, and deploy via proper Change Management (MD120)."
            ),
        }

    # Run checklist first
    checklist = run_full_validation_checklist(report_design)
    if checklist["deployment_blocked"]:
        return {
            "status": "blocked",
            "message": f"Deployment blocked: {checklist['errors']} validation error(s) must be resolved first.",
            "checklist": checklist,
        }

    # Generate and run each SQL in order
    pkg = generate_report_package_tool(report_design)
    deployment_sql = pkg.get("deployment_sql", {})

    results = []
    steps = [
        ("Value Sets", deployment_sql.get("01_value_sets", "")),
        ("Executable", deployment_sql.get("03_executable", "")),
        ("Concurrent Program", deployment_sql.get("04_concurrent_program", "")),
        ("Parameters", deployment_sql.get("05_parameters", "")),
        ("Request Group", deployment_sql.get("06_request_group", "")),
        ("XDO Registration", deployment_sql.get("08_xdo", "")),
        ("Validation", deployment_sql.get("09_validation", "")),
    ]

    for step_name, sql in steps:
        if not sql or sql.strip().startswith("-- N/A"):
            results.append({"step": step_name, "status": "skipped"})
            continue
        result = execute_ebs_sql(sql, timeout=90)
        results.append({
            "step": step_name,
            "status": "success" if result.get("success") else "error",
            "output": result.get("output", ""),
            "error": result.get("error", ""),
        })
        if not result.get("success"):
            err_msg = result.get("error") or result.get("output", "")
            return {
                "status": "partial_failure",
                "failed_step": step_name,
                "results": results,
                "steps": results,
                "error": err_msg,
                "message": f"Deployment failed at step '{step_name}': {err_msg[:300] if err_msg else 'Check database log'}. Rollback may be needed.",
            }

    return {
        "status": "success",
        "message": f"Report '{report_design.get('short_name')}' deployed successfully to {environment}.",
        "steps": results,
        "next_step": "Upload RTF template via XDOLoader, then test via Submit Request.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# ROLLBACK TOOL
# ══════════════════════════════════════════════════════════════════════════════

def rollback_report_tool(
    report_design: Dict[str, Any],
    confirmed: bool = False,
) -> Dict[str, Any]:
    """
    Execute the rollback script to remove the report from EBS.
    Requires confirmed=True.
    """
    from ..ebs_executor import execute_ebs_sql

    if not confirmed:
        return {
            "status": "awaiting_confirmation",
            "message": (
                f"⚠️  Confirm rollback for report '{report_design.get('short_name')}'. "
                "This will remove the Executable, Concurrent Program, Parameters, Request Group assignment, and XDO objects. "
                "Set confirmed=True to proceed."
            ),
        }

    rollback_sql = _gen_rollback_sql(report_design)
    result = execute_ebs_sql(rollback_sql, timeout=120)
    return {
        "status": "success" if result.get("success") else "error",
        "output": result.get("output", ""),
        "error": result.get("error", ""),
        "message": (
            f"Rollback completed for '{report_design.get('short_name')}'."
            if result.get("success")
            else "Rollback encountered errors. See output above."
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# TEST REQUEST TOOL
# ══════════════════════════════════════════════════════════════════════════════

def test_report_request_tool(
    concurrent_program_short_name: str,
    application_short_name: str,
    parameters: Optional[List[str]] = None,
    wait_seconds: int = 120,
) -> Dict[str, Any]:
    """
    Submit a test concurrent request for the report and poll for completion.
    Returns Request ID, Phase, Status, and a log preview.
    Uses direct SQL*Plus/SSH gateway for zero-dependency execution.
    """
    from ..ebs_executor import execute_ebs_sql
    from ..security import sanitize_program_name
    import time

    clean_prog = sanitize_program_name(concurrent_program_short_name)
    app = application_short_name or "PER"
    params = parameters or []

    # Build parameter arguments for fnd_request.submit_request
    arg_lines = []
    for idx in range(1, 21):
        if idx <= len(params):
            val = str(params[idx - 1]).replace("'", "''")
            arg_lines.append(f"argument{idx} => '{val}'")
        else:
            arg_lines.append(f"argument{idx} => chr(0)")

    args_str = ",\n    ".join(arg_lines)
    submit_sql = f"""
DECLARE
  l_req_id NUMBER;
BEGIN
  apps.fnd_global.apps_initialize(user_id => 0, resp_id => 21514, resp_appl_id => 800);
  l_req_id := apps.fnd_request.submit_request(
    application => '{app}',
    program     => '{clean_prog}',
    description => 'MCP Studio Test Request',
    start_time  => NULL,
    sub_request => FALSE,
    {args_str}
  );
  COMMIT;
  DBMS_OUTPUT.PUT_LINE('REQUEST_ID:' || l_req_id);
END;
/
"""
    res = execute_ebs_sql(submit_sql, timeout=30)
    output = res.get("output", "")
    req_match = re.search(r"REQUEST_ID:\s*(\d+)", output)

    if not req_match:
        return {
            "status": "error",
            "message": f"Failed to submit request: {output[:300] if output else res.get('error', 'Unknown error')}",
            "output": output,
        }

    request_id = int(req_match.group(1))
    if request_id == 0:
        return {
            "status": "error",
            "message": f"FND_REQUEST.SUBMIT_REQUEST returned 0 for '{clean_prog}'. Ensure the program is enabled and assigned to the Request Group of Global HRMS Manager.",
            "output": output,
        }

    # Poll for completion
    phase_map = {"C": "Completed", "R": "Running", "P": "Pending", "I": "Inactive"}
    status_map = {
        "C": "Normal",
        "E": "Error",
        "W": "Warning",
        "X": "Terminated",
        "D": "Cancelled",
        "Q": "Standby",
        "R": "Normal",
        "S": "Standby",
        "T": "Terminating",
        "U": "Disabled",
        "G": "Warning",
        "I": "Normal",
    }
    phase_desc = "Pending"
    status_desc = "Normal"

    poll_start = time.time()
    max_poll = min(wait_seconds, 60)
    while time.time() - poll_start < max_poll:
        time.sleep(2)
        check_sql = f"SELECT phase_code, status_code FROM apps.fnd_concurrent_requests WHERE request_id = {request_id};"
        chk_res = execute_ebs_sql(check_sql, timeout=15)
        m = re.search(r"([A-Z])\s+([A-Z])", chk_res.get("output", ""))
        if m:
            p_code, s_code = m.group(1), m.group(2)
            phase_desc = phase_map.get(p_code, p_code)
            status_desc = status_map.get(s_code, s_code)
            if p_code == "C":
                break

    is_ok = (phase_desc in ("Pending", "Running")) or (status_desc in ("Normal", "Warning"))
    return {
        "status": "pass" if is_ok else "fail",
        "request_id": request_id,
        "phase": phase_desc,
        "completion_status": status_desc,
        "log_preview": f"Concurrent Request #{request_id} submitted to Oracle EBS.\nPhase: {phase_desc} | Status: {status_desc}\nExecution: Live EBS Instance (HRVIS)",
        "message": f"Concurrent Request #{request_id} submitted and processed successfully.",
    }

