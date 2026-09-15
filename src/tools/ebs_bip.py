"""
Tool: BI Publisher / XML Publisher Inspector & Registration Generator
Handles Data Definitions, RTF/XSL Templates, and XDOLoader deployment syntax.
"""

from typing import Any, Dict, List, Optional
from ..config import get_config
from ..database import get_connection
from ..security import sanitize_program_name, InputValidationError


def get_bip_template_info_tool(template_code: str) -> Dict[str, Any]:
    """
    Inspect an Oracle EBS BI Publisher / XML Publisher template:
    Data Definition, files stored in XDO_LOBS, languages, territories, and default output type.
    """
    clean_code = sanitize_program_name(template_code)
    cfg = get_config()

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            # 1. Query Template Header
            tmpl_sql = """
            SELECT 
                xtb.application_short_name,
                xtb.template_code,
                xtv.template_name,
                xtb.data_source_code,
                xtb.template_type_code,
                xtb.default_output_type,
                xtb.start_date,
                xtb.end_date,
                xtv.description
            FROM 
                apps.xdo_templates_b xtb
                JOIN apps.xdo_templates_vl xtv 
                    ON xtb.template_code = xtv.template_code
                    AND xtb.application_short_name = xtv.application_short_name
            WHERE 
                UPPER(xtb.template_code) = :tmpl_code
            """
            cursor.execute(tmpl_sql, {"tmpl_code": clean_code})
            row = cursor.fetchone()
            if not row:
                return {
                    "status": "not_found",
                    "template_code": clean_code,
                    "message": f"BI Publisher template '{clean_code}' not found in XDO_TEMPLATES_B.",
                }

            cols = [col[0].lower() for col in cursor.description]
            template_data = dict(zip(cols, row))

            # 2. Query Files in XDO_LOBS
            lobs_sql = """
            SELECT 
                lob_type,
                file_name,
                file_status,
                language,
                territory,
                xdo_file_type,
                created_by,
                TO_CHAR(last_update_date, 'YYYY-MM-DD HH24:MI:SS') AS last_update_date
            FROM 
                apps.xdo_lobs
            WHERE 
                UPPER(lob_code) = :tmpl_code
            ORDER BY lob_type, language
            """
            cursor.execute(lobs_sql, {"tmpl_code": clean_code})
            lob_cols = [col[0].lower() for col in cursor.description]
            lobs = [dict(zip(lob_cols, r)) for r in cursor.fetchall()]

            return {
                "status": "success",
                "template": template_data,
                "files_count": len(lobs),
                "files": lobs,
            }


def generate_bip_registration_script_tool(
    template_code: str,
    template_name: str,
    application_short_name: str,
    data_source_code: str,
    template_type: str = "RTF",
    default_output_type: str = "EXCEL",
    rtf_file_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate complete BI Publisher Data Definition and Template registration script,
    including the exact XDOLoader CLI commands for Linux deployment.
    """
    clean_code = sanitize_program_name(template_code)
    clean_ds = sanitize_program_name(data_source_code)
    rtf_name = rtf_file_name or f"{clean_code}.rtf"

    xdo_cmd = f"""# =============================================================================
# BI Publisher XDOLoader Deployment Commands (Linux Shell)
# Run under: applmgr / applsys user on EBS application tier
# =============================================================================

# 1. Upload/Register RTF Template into XDO_LOBS:
java oracle.apps.xdo.oa.util.XDOLoader \\
  UPLOAD \\
  -DB_USERNAME apps \\
  -DB_PASSWORD $APPS_PWD \\
  -JDBC_CONNECTION $JDBC_CONNECTION \\
  -APPS_SHORT_NAME {application_short_name} \\
  -LOB_TYPE TEMPLATE_SOURCE \\
  -LOB_CODE {clean_code} \\
  -LANGUAGE en \\
  -TERRITORY 00 \\
  -XDO_FILE_TYPE RTF \\
  -FILE_NAME {rtf_name} \\
  -NLS_LANG AMERICAN_AMERICA.UTF8 \\
  -CUSTOM_MODE FORCE
"""

    plsql_script = f"""-- =============================================================================
-- BI Publisher Data Definition & Template PL/SQL Registration
-- =============================================================================
DECLARE
  l_exists NUMBER;
BEGIN
  -- Check Data Definition
  SELECT COUNT(1) INTO l_exists 
  FROM apps.xdo_ds_definitions_b 
  WHERE data_source_code = '{clean_ds}';

  IF l_exists = 0 THEN
    -- Insert Data Source Definition
    INSERT INTO apps.xdo_ds_definitions_b (
      application_short_name, data_source_code, data_source_status,
      data_source_type, start_date, created_by, creation_date,
      last_updated_by, last_update_date, last_update_login, object_version_number
    ) VALUES (
      '{application_short_name}', '{clean_ds}', 'E',
      'XML', SYSDATE, 0, SYSDATE, 0, SYSDATE, 0, 1
    );

    INSERT INTO apps.xdo_ds_definitions_tl (
      application_short_name, data_source_code, language, source_lang,
      data_source_name, description, created_by, creation_date,
      last_updated_by, last_update_date, last_update_login
    ) VALUES (
      '{application_short_name}', '{clean_ds}', 'US', 'US',
      '{template_name} Data Definition', '{template_name} Data Definition',
      0, SYSDATE, 0, SYSDATE, 0
    );
    DBMS_OUTPUT.PUT_LINE('Data Definition created: {clean_ds}');
  END IF;

  -- Check Template
  SELECT COUNT(1) INTO l_exists 
  FROM apps.xdo_templates_b 
  WHERE template_code = '{clean_code}';

  IF l_exists = 0 THEN
    INSERT INTO apps.xdo_templates_b (
      application_short_name, template_code, data_source_code,
      template_type_code, default_output_type, mlr_flag, start_date,
      created_by, creation_date, last_updated_by, last_update_date,
      last_update_login, object_version_number
    ) VALUES (
      '{application_short_name}', '{clean_code}', '{clean_ds}',
      '{template_type}', '{default_output_type}', 'N', SYSDATE,
      0, SYSDATE, 0, SYSDATE, 0, 1
    );

    INSERT INTO apps.xdo_templates_tl (
      application_short_name, template_code, language, source_lang,
      template_name, description, created_by, creation_date,
      last_updated_by, last_update_date, last_update_login
    ) VALUES (
      '{application_short_name}', '{clean_code}', 'US', 'US',
      '{template_name}', '{template_name}',
      0, SYSDATE, 0, SYSDATE, 0
    );
    DBMS_OUTPUT.PUT_LINE('Template metadata created: {clean_code}');
  END IF;

  COMMIT;
END;
/
"""

    return {
        "status": "success",
        "template_code": clean_code,
        "data_source_code": clean_ds,
        "xdoloader_command": xdo_cmd,
        "plsql_script": plsql_script,
    }
