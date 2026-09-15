"""
Tool: EBS Value Set Inspector & Registration Script Generator
Handles FND_FLEX_VALUE_SETS inspection, validation, and SQL generation for
Independent, Table-validated, and Special value sets.
"""

from typing import Any, Dict, List, Optional
from ..config import get_config
from ..database import get_connection
from ..security import sanitize_program_name, InputValidationError


def inspect_value_set_tool(value_set_name: str) -> Dict[str, Any]:
    """
    Inspect an existing Oracle EBS Value Set.
    Returns validation type, data type, SQL query (for Table types),
    and any existing values (for Independent types).
    """
    clean_name = sanitize_program_name(value_set_name)
    cfg = get_config()

    with get_connection(cfg) as conn:
        with conn.cursor() as cursor:
            vs_sql = """
            SELECT
                fvs.flex_value_set_name,
                fvs.description,
                fvs.validation_type,
                fvs.format_type,
                fvs.maximum_size,
                fvs.alphanumeric_allowed_flag,
                fvs.uppercase_only_flag,
                fvs.numeric_mode_enabled_flag,
                fvs.security_enabled_flag,
                fvs.long_list_flag,
                fvs.flex_value_set_id
            FROM apps.fnd_flex_value_sets fvs
            WHERE UPPER(fvs.flex_value_set_name) = UPPER(:vs_name)
            """
            cursor.execute(vs_sql, {"vs_name": clean_name})
            row = cursor.fetchone()
            if not row:
                return {
                    "status": "not_found",
                    "value_set_name": clean_name,
                    "message": f"Value Set '{clean_name}' not found in FND_FLEX_VALUE_SETS.",
                }

            cols = [c[0].lower() for c in cursor.description]
            vs_data = dict(zip(cols, row))
            vs_id = vs_data["flex_value_set_id"]
            validation_type = vs_data.get("validation_type", "")

            # For Table-validated: get the table validation details
            table_info = None
            if validation_type == "D":
                tbl_sql = """
                SELECT
                    application_table_name,
                    value_column_name,
                    id_column_name,
                    meaning_column_name,
                    additional_where_clause,
                    additional_quickpick_columns,
                    compiled_value_attributes
                FROM apps.fnd_flex_validation_tables
                WHERE flex_value_set_id = :vs_id
                """
                cursor.execute(tbl_sql, {"vs_id": vs_id})
                tbl_row = cursor.fetchone()
                if tbl_row:
                    tbl_cols = [c[0].lower() for c in cursor.description]
                    table_info = dict(zip(tbl_cols, tbl_row))

            # For Independent: get count of values
            value_count = None
            if validation_type == "I":
                cursor.execute(
                    "SELECT COUNT(1) FROM apps.fnd_flex_values WHERE flex_value_set_id = :vs_id",
                    {"vs_id": vs_id},
                )
                value_count = cursor.fetchone()[0]

            validation_type_map = {
                "I": "Independent",
                "D": "Table (Dependent on Application Table)",
                "N": "None",
                "F": "Format Only",
                "P": "Pair",
                "S": "Special (User Exit)",
                "X": "Extra",
                "U": "FND Lookup",
            }

            return {
                "status": "success",
                "value_set": vs_data,
                "validation_type_label": validation_type_map.get(validation_type, validation_type),
                "table_info": table_info,
                "independent_value_count": value_count,
            }


def generate_value_set_sql_tool(
    value_sets: List[Dict[str, Any]],
    application_short_name: str = "XX",
) -> Dict[str, Any]:
    """
    Generate FND_FLEX_VALUE_SETS registration SQL for a list of value set definitions.

    Each value set dict may contain:
      - name (str, required)
      - description (str)
      - validation_type: "I" (Independent), "D" (Table), "N" (None), "F" (Format Only)
      - format_type: "C" (Char), "N" (Number), "D" (Date)
      - maximum_size (int, default 30)
      - table_name (str, for type D)
      - value_column (str, for type D)
      - id_column (str, for type D)
      - where_clause (str, for type D)
      - independent_values (list of str, for type I)
    """
    if not value_sets:
        return {"status": "error", "message": "No value sets provided."}

    scripts = []
    rollback_parts = []

    for vs in value_sets:
        vs_name = vs.get("name", "").upper().strip()
        if not vs_name:
            continue

        description = vs.get("description", vs_name)
        validation_type = vs.get("validation_type", "I")
        format_type = vs.get("format_type", "C")
        max_size = int(vs.get("maximum_size", 30))
        table_name = vs.get("table_name", "")
        value_col = vs.get("value_column", "")
        id_col = vs.get("id_column", "")
        where_clause = vs.get("where_clause", "")
        indep_values = vs.get("independent_values", [])

        block = f"""
-- ============================================================
-- Value Set: {vs_name}
-- Validation Type: {validation_type} | Format: {format_type}
-- ============================================================
DECLARE
  l_vs_id    NUMBER;
  l_exists   NUMBER := 0;
BEGIN
  -- Check if Value Set already exists
  SELECT COUNT(1) INTO l_exists
  FROM apps.fnd_flex_value_sets
  WHERE flex_value_set_name = '{vs_name}';

  IF l_exists = 0 THEN
    -- Create new Value Set
    fnd_flex_val_api.create_flex_value_set(
      p_flex_value_set_name           => '{vs_name}',
      p_description                   => '{description}',
      p_format_type                   => '{format_type}',
      p_maximum_size                  => {max_size},
      p_validation_type               => '{validation_type}',
      p_alphanumeric_allowed_flag     => 'Y',
      p_uppercase_only_flag           => 'N',
      p_numeric_mode_enabled_flag     => '{"Y" if format_type == "N" else "N"}',
      p_security_enabled_flag         => 'N',
      p_long_list_flag                => 'N'
    );
    DBMS_OUTPUT.PUT_LINE('Created Value Set: {vs_name}');
  ELSE
    DBMS_OUTPUT.PUT_LINE('Value Set already exists: {vs_name}');
  END IF;
"""

        # Table-validated: add table info
        if validation_type == "D" and table_name:
            block += f"""
  -- Register Table Validation
  SELECT flex_value_set_id INTO l_vs_id
  FROM apps.fnd_flex_value_sets WHERE flex_value_set_name = '{vs_name}';

  MERGE INTO apps.fnd_flex_validation_tables t
  USING (SELECT 1 AS dummy FROM DUAL) d ON (t.flex_value_set_id = l_vs_id)
  WHEN NOT MATCHED THEN INSERT (
    flex_value_set_id, application_table_name,
    value_column_name, id_column_name,
    additional_where_clause
  ) VALUES (
    l_vs_id, '{table_name}', '{value_col}',
    '{id_col}',
    '{where_clause}'
  );

"""

        # Independent values
        if validation_type == "I" and indep_values:
            block += f"""
  -- Insert Independent Values
  SELECT flex_value_set_id INTO l_vs_id
  FROM apps.fnd_flex_value_sets WHERE flex_value_set_name = '{vs_name}';
"""
            for val in indep_values:
                block += f"""
  INSERT INTO apps.fnd_flex_values (
    flex_value_set_id, flex_value, enabled_flag,
    summary_flag, created_by, creation_date,
    last_updated_by, last_update_date, last_update_login
  )
  SELECT l_vs_id, '{val}', 'Y', 'N',
         0, SYSDATE, 0, SYSDATE, 0
  FROM DUAL
  WHERE NOT EXISTS (
    SELECT 1 FROM apps.fnd_flex_values
    WHERE flex_value_set_id = l_vs_id AND flex_value = '{val}'
  );
"""

        block += "\n  COMMIT;\nEXCEPTION\n  WHEN OTHERS THEN\n    ROLLBACK;\n    DBMS_OUTPUT.PUT_LINE('ERROR creating Value Set {vs_name}: ' || SQLERRM);\n    RAISE;\nEND;\n/\n"
        scripts.append(block)

        rollback_parts.append(f"""
-- Rollback: Remove Value Set {vs_name}
BEGIN
  FOR r IN (SELECT flex_value_set_id FROM apps.fnd_flex_value_sets WHERE flex_value_set_name = '{vs_name}') LOOP
    DELETE FROM apps.fnd_flex_values WHERE flex_value_set_id = r.flex_value_set_id;
    DELETE FROM apps.fnd_flex_validation_tables WHERE flex_value_set_id = r.flex_value_set_id;
    DELETE FROM apps.fnd_flex_value_sets WHERE flex_value_set_id = r.flex_value_set_id;
  END LOOP;
  COMMIT;
  DBMS_OUTPUT.PUT_LINE('Rolled back Value Set: {vs_name}');
END;
/
""")

    header = f"""-- =============================================================================
-- Oracle EBS R12 Value Sets Registration Script
-- Application: {application_short_name}
-- Generated by Oracle EBS R12 MCP Studio
-- =============================================================================
SET SERVEROUTPUT ON SIZE 1000000;
WHENEVER SQLERROR CONTINUE;

"""

    full_script = header + "\n".join(scripts)
    rollback_script = "-- VALUE SETS ROLLBACK\n" + "\n".join(rollback_parts)

    return {
        "status": "success",
        "value_sets_count": len(scripts),
        "deployment_sql": full_script,
        "rollback_sql": rollback_script,
    }
