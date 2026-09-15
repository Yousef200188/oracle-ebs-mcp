"""
Tool: EBS Concurrent Programs & Executables Administrator
Inspects metadata and generates certified FND_PROGRAM deployment scripts.
"""

from typing import Any, Dict, List, Optional
from ..config import get_config
from ..database import get_connection
from ..security import sanitize_program_name, InputValidationError


def get_concurrent_program_definition_tool(program_short_name: str) -> Dict[str, Any]:
    """
    Retrieve full technical metadata for an Oracle EBS Concurrent Program:
    Executable details, execution method, parameters with value sets, and assigned request groups.
    """
    clean_prog = sanitize_program_name(program_short_name)
    cfg = get_config()

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            # 1. Program & Executable Header
            header_sql = """
            SELECT 
                fcp.concurrent_program_id,
                fcp.concurrent_program_name AS short_name,
                fcp.user_concurrent_program_name AS program_name,
                fa.application_short_name,
                fa.application_name,
                fcp.description,
                fcp.enabled_flag,
                fcp.srs_flag,
                fcp.output_file_type,
                fcp.save_output_flag,
                fcp.print_flag,
                fe.executable_name,
                fe.execution_method_code,
                fl_meth.meaning AS execution_method,
                fe.execution_file_name,
                fe.execution_file_path
            FROM 
                apps.fnd_concurrent_programs_vl fcp
                JOIN apps.fnd_application_vl fa ON fcp.application_id = fa.application_id
                JOIN apps.fnd_executables fe ON fcp.executable_id = fe.executable_id
                LEFT JOIN apps.fnd_lookups fl_meth 
                    ON fl_meth.lookup_type = 'CP_EXECUTION_METHOD_CODE'
                    AND fl_meth.lookup_code = fe.execution_method_code
            WHERE 
                fcp.concurrent_program_name = :prog
            """
            cursor.execute(header_sql, {"prog": clean_prog})
            row = cursor.fetchone()
            if not row:
                return {
                    "status": "not_found",
                    "program_short_name": clean_prog,
                    "message": f"Concurrent program '{clean_prog}' was not found in Oracle EBS.",
                }

            cols = [col[0].lower() for col in cursor.description]
            header_data = dict(zip(cols, row))

            # 2. Parameters & Value Sets
            param_sql = """
            SELECT 
                fcu.column_seq_num AS sequence,
                fcu.end_user_column_name AS parameter_name,
                fcu.form_left_prompt AS prompt,
                fcu.application_column_name AS token,
                fvs.flex_value_set_name AS value_set,
                fcu.default_type,
                fcu.default_value,
                fcu.required_flag,
                fcu.display_flag,
                fcu.enabled_flag,
                fcu.description
            FROM 
                apps.fnd_descr_flex_col_usage_vl fcu
                LEFT JOIN apps.fnd_flex_value_sets fvs 
                    ON fcu.flex_value_set_id = fvs.flex_value_set_id
            WHERE 
                fcu.descriptive_flexfield_name = '$SRS$.' || :prog
            ORDER BY 
                fcu.column_seq_num
            """
            cursor.execute(param_sql, {"prog": clean_prog})
            param_cols = [col[0].lower() for col in cursor.description]
            parameters = [dict(zip(param_cols, r)) for r in cursor.fetchall()]

            # 3. Assigned Request Groups
            rg_sql = """
            SELECT 
                frg.request_group_name,
                fa.application_short_name AS group_application,
                fr.responsibility_name
            FROM 
                apps.fnd_request_group_units frgu
                JOIN apps.fnd_request_groups frg ON frgu.request_group_id = frg.request_group_id
                JOIN apps.fnd_application fa ON frg.application_id = fa.application_id
                LEFT JOIN apps.fnd_responsibility_vl fr ON frg.request_group_id = fr.request_group_id
            WHERE 
                frgu.request_unit_id = :prog_id
                AND frgu.unit_type = 'P'
            ORDER BY frg.request_group_name
            """
            cursor.execute(rg_sql, {"prog_id": header_data["concurrent_program_id"]})
            rg_cols = [col[0].lower() for col in cursor.description]
            request_groups = [dict(zip(rg_cols, r)) for r in cursor.fetchall()]

            return {
                "status": "success",
                "program": header_data,
                "parameters_count": len(parameters),
                "parameters": parameters,
                "request_groups_count": len(request_groups),
                "request_groups": request_groups,
            }


def generate_concurrent_program_script_tool(
    program_name: str,
    program_short_name: str,
    application_short_name: str,
    executable_name: str,
    execution_method: str,
    execution_file_name: str,
    parameters: Optional[List[Dict[str, Any]]] = None,
    request_group_name: Optional[str] = None,
    output_format: str = "TEXT",
) -> Dict[str, Any]:
    """
    Generate an idempotent, production-ready PL/SQL registration script using FND_PROGRAM API
    (Executable, Program, Parameters, and Request Group Assignment).
    """
    clean_prog_short = sanitize_program_name(program_short_name)
    clean_exec_name = sanitize_program_name(executable_name)
    method_map = {
        "PL/SQL Stored Procedure": "PL/SQL Stored Procedure",
        "PLSQL": "PL/SQL Stored Procedure",
        "Oracle Reports": "Oracle Reports",
        "RDF": "Oracle Reports",
        "Host": "Host",
        "SHELL": "Host",
        "SQL*Plus": "SQL*Plus",
        "Java Stored Procedure": "Java Stored Procedure",
        "Java Concurrent Program": "Java Concurrent Program",
    }
    std_method = method_map.get(execution_method, execution_method)

    params_code = []
    if parameters:
        for idx, p in enumerate(parameters, start=1):
            p_name = p.get("name", f"Parameter_{idx}")
            p_valset = p.get("value_set", "70 Characters")
            p_prompt = p.get("prompt", p_name)
            p_req = "Y" if p.get("required", False) else "N"
            p_disp = "Y" if p.get("displayed", True) else "N"
            params_code.append(f"""
  -- Parameter {idx}: {p_name}
  fnd_program.parameter(
    program_short_name => '{clean_prog_short}',
    application        => '{application_short_name}',
    sequence           => {idx * 10},
    parameter          => '{p_name}',
    description        => '{p_name} parameter',
    value_set          => '{p_valset}',
    default_type       => NULL,
    default_value      => NULL,
    required           => '{p_req}',
    enable_flag        => 'Y',
    displayed          => '{p_disp}',
    display_size       => 30,
    description_size   => 50,
    concatenated_description_size => 50,
    prompt             => '{p_prompt}'
  );""")

    params_block = "\n".join(params_code) if params_code else "  -- No parameters defined"
    rg_block = ""
    if request_group_name:
        rg_block = f"""
  -- Add to Request Group
  fnd_program.add_to_group(
    program_short_name => '{clean_prog_short}',
    program_application=> '{application_short_name}',
    request_group      => '{request_group_name}',
    group_application  => '{application_short_name}'
  );"""

    script = f"""-- =============================================================================
-- EBS R12 Concurrent Program Registration Script
-- Generated by: Oracle EBS Technical MCP Assistant
-- Program: {program_name} ({clean_prog_short})
-- =============================================================================
SET SERVEROUTPUT ON SIZE 1000000
SET DEFINE OFF

DECLARE
  l_exists NUMBER;
BEGIN
  DBMS_OUTPUT.PUT_LINE('Starting registration for: {clean_prog_short}...');

  -- 1. Register Executable
  SELECT COUNT(1) INTO l_exists 
  FROM apps.fnd_executables 
  WHERE executable_name = '{clean_exec_name}';

  IF l_exists = 0 THEN
    fnd_program.executable(
      executable          => '{clean_exec_name}',
      application         => '{application_short_name}',
      short_name          => '{clean_exec_name}',
      description         => '{program_name} Executable',
      execution_method    => '{std_method}',
      execution_file_name => '{execution_file_name}'
    );
    DBMS_OUTPUT.PUT_LINE('Executable created: {clean_exec_name}');
  ELSE
    DBMS_OUTPUT.PUT_LINE('Executable already exists: {clean_exec_name}');
  END IF;

  -- 2. Register Concurrent Program
  SELECT COUNT(1) INTO l_exists 
  FROM apps.fnd_concurrent_programs 
  WHERE concurrent_program_name = '{clean_prog_short}';

  IF l_exists = 0 THEN
    fnd_program.register(
      program                => '{program_name}',
      application            => '{application_short_name}',
      enabled                => 'Y',
      short_name             => '{clean_prog_short}',
      description            => '{program_name}',
      executable_short_name  => '{clean_exec_name}',
      executable_application => '{application_short_name}',
      execution_options      => NULL,
      priority               => NULL,
      save_output            => 'Y',
      print                  => 'N',
      cols                   => NULL,
      rows                   => NULL,
      style                  => NULL,
      style_required         => 'N',
      printer                => NULL,
      request_type           => NULL,
      request_type_application => NULL,
      use_in_srs             => 'Y',
      allow_disabled         => 'N',
      print_together         => 'N',
      run_alone              => 'N',
      output_type            => '{output_format}',
      enable_trace           => 'N',
      restart                => 'Y',
      nls_compliant          => 'Y'
    );
    DBMS_OUTPUT.PUT_LINE('Concurrent Program created: {clean_prog_short}');
  ELSE
    DBMS_OUTPUT.PUT_LINE('Concurrent Program already exists: {clean_prog_short}');
  END IF;

  -- 3. Register Parameters
{params_block}

  -- 4. Attach to Request Group
{rg_block}

  COMMIT;
  DBMS_OUTPUT.PUT_LINE('Registration completed successfully and committed.');
EXCEPTION
  WHEN OTHERS THEN
    ROLLBACK;
    DBMS_OUTPUT.PUT_LINE('ERROR during registration: ' || SQLERRM);
    RAISE;
END;
/
"""
    return {
        "status": "success",
        "program_short_name": clean_prog_short,
        "executable_name": clean_exec_name,
        "script": script,
        "instructions": "Execute script under APPS schema via SQL*Plus or Toad/PLSQL Developer.",
    }
