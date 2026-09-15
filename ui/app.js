/**
 * Oracle EBS R12 Development MCP Studio - Core Controller
 * Handles tab switching, dynamic form interactions, and multi-artifact code generation.
 */

// ==================== STATE MANAGEMENT ====================
const state = {
  currentModule: 'concurrent',
  activeOutputTab: 'code',
  currentEnv: 'DEV',
  uploadedRdf: null, // { name: '', b64: '' }
  uploadedRtf: null, // { name: '', b64: '' }
  outputData: {
    code: '',
    deploy: '',
    rollback: '',
    doc: '',
    fileName: 'XX_CONCURRENT_PROGRAM.sql'
  }
};

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
  // Generate initial default output
  generateConcurrentScript();
  updateSqlColumnPreview();

  // Support URL query parameters for deep linking (?tab=report&env=PROD)
  const urlParams = new URLSearchParams(window.location.search);
  const envParam = urlParams.get('env');
  if (envParam) {
    const envSelect = document.getElementById('envSelect');
    if (envSelect) {
      envSelect.value = envParam;
      handleEnvChange();
    }
  }
  const tabParam = urlParams.get('tab');
  if (tabParam) {
    switchModule(tabParam);
    if (tabParam === 'report' && typeof generateReportPackage === 'function') generateReportPackage();
    else if (tabParam === 'workflow' && typeof generateWorkflowDefinitionScript === 'function') generateWorkflowDefinitionScript();
    else if (tabParam === 'alert' && typeof generateAlertScripts === 'function') generateAlertScripts();
    else if (tabParam === 'oaf' && typeof generateOAFPageXML === 'function') generateOAFPageXML();
    else if (tabParam === 'sql' && typeof generatePLSQLCode === 'function') generatePLSQLCode();
  }
});

// ==================== ENVIRONMENT SELECTOR ====================
function handleEnvChange() {
  const envSelect = document.getElementById('envSelect');
  state.currentEnv = envSelect.value;
  const prodBanner = document.getElementById('prodWarningBanner');
  const targetPill = document.getElementById('targetInstance');

  if (state.currentEnv === 'PROD') {
    prodBanner.classList.remove('hidden');
    targetPill.innerHTML = '<span class="status-dot error"></span><span class="status-text">PROD_VIS (10.100.100.10) - LOCKED</span>';
  } else if (state.currentEnv === 'UAT') {
    prodBanner.classList.add('hidden');
    targetPill.innerHTML = '<span class="status-dot warning"></span><span class="status-text">UAT_VIS (10.100.100.102)</span>';
  } else if (state.currentEnv === 'TEST') {
    prodBanner.classList.add('hidden');
    targetPill.innerHTML = '<span class="status-dot warning"></span><span class="status-text">TEST_VIS (10.100.100.103)</span>';
  } else {
    prodBanner.classList.add('hidden');
    targetPill.innerHTML = '<span class="status-dot online"></span><span class="status-text">HRVIS (10.100.100.104)</span>';
  }
}

// ==================== NAVIGATION TABS ====================
function switchModule(moduleName) {
  state.currentModule = moduleName;

  // Update tab buttons
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-module') === moduleName);
  });

  // Update panels
  document.querySelectorAll('.module-panel').forEach(panel => {
    panel.classList.toggle('active', panel.id === `panel-${moduleName}`);
  });
}

function switchOutputTab(tabKey) {
  state.activeOutputTab = tabKey;

  // Update subtab buttons
  document.querySelectorAll('.subtab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('onclick').includes(`'${tabKey}'`));
  });

  // Display content
  const codeArea = document.getElementById('outputCodeArea');
  const content = state.outputData[tabKey] || '-- No content generated for this tab.';
  codeArea.textContent = content;

  // Update stats
  updateStats(content);
}

function updateStats(content) {
  const lines = content.split('\n').length;
  const bytes = new Blob([content]).size;
  const kb = (bytes / 1024).toFixed(1);
  const statsEl = document.getElementById('outputStats');
  if (statsEl) {
    statsEl.textContent = `Lines: ${lines} | Size: ${kb} KB | Certified for Oracle EBS R12 (${state.currentEnv})`;
  }
}

function renderOutput(fileName, code, deploy, rollback, doc) {
  state.outputData = {
    code: code.trim(),
    deploy: deploy.trim(),
    rollback: rollback.trim(),
    doc: doc.trim(),
    fileName: fileName
  };

  document.getElementById('currentOutputFile').textContent = fileName;
  switchOutputTab(state.activeOutputTab || 'code');
}

// ==================== DYNAMIC PARAMETER TABLES ====================
function addParameterRow(tbodyId) {
  const tbody = document.getElementById(tbodyId);
  const rows = tbody.querySelectorAll('tr');
  let nextSeq = 10;
  if (rows.length > 0) {
    const lastSeqInput = rows[rows.length - 1].querySelector('.seq');
    if (lastSeqInput && !isNaN(parseInt(lastSeqInput.value))) {
      nextSeq = parseInt(lastSeqInput.value) + 10;
    }
  }

  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><input type="number" class="tbl-input seq" value="${nextSeq}" step="10"></td>
    <td><input type="text" class="tbl-input param-name" value="P_PARAM_${nextSeq}" oninput="this.value = this.value.toUpperCase()"></td>
    <td><input type="text" class="tbl-input param-prompt" value="Parameter ${nextSeq}"></td>
    <td><input type="text" class="tbl-input param-vset" value="FND_STANDARD_CHAR"></td>
    <td>
      <select class="tbl-input param-req">
        <option value="Y">Y</option>
        <option value="N" selected>N</option>
      </select>
    </td>
    <td><button type="button" class="btn-icon delete-btn" onclick="removeRow(this)">âœ•</button></td>
  `;
  tbody.appendChild(tr);
}

function removeRow(btn) {
  const tr = btn.closest('tr');
  if (tr) {
    const tbody = tr.parentElement;
    if (tbody.querySelectorAll('tr').length > 1) {
      tr.remove();
    } else {
      alert('At least one parameter row is required. Clear the values instead of deleting the last row.');
    }
  }
}

function getParametersFromTable(tbodyId) {
  const tbody = document.getElementById(tbodyId);
  const rows = tbody.querySelectorAll('tr');
  const params = [];
  rows.forEach(r => {
    const seq = r.querySelector('.seq')?.value.trim() || '10';
    const name = r.querySelector('.param-name')?.value.trim() || '';
    const prompt = r.querySelector('.param-prompt')?.value.trim() || name;
    const vset = r.querySelector('.param-vset')?.value.trim() || 'FND_STANDARD_CHAR';
    const req = r.querySelector('.param-req')?.value || 'N';
    if (name) {
      params.push({ seq, name, prompt, vset, req });
    }
  });
  return params;
}

// ==================== FORM HINTS & TOGGLES ====================
function updateExecMethodHints() {
  const method = document.getElementById('cp_exec_method').value;
  const fileInput = document.getElementById('cp_exec_file');
  const hintEl = document.getElementById('cp_exec_hint');
  const outputType = document.getElementById('cp_output_type');

  if (method === 'PL/SQL Stored Procedure') {
    hintEl.textContent = 'Enter package.procedure name (e.g., xx_emp_pkg.run_report).';
    fileInput.value = 'xx_emp_pkg.run_report';
    outputType.value = 'TEXT';
  } else if (method === 'Oracle Reports') {
    hintEl.textContent = 'Enter report file name WITHOUT .rdf extension (e.g., XX_EMP_REPORT).';
    fileInput.value = 'XX_EMP_REPORT';
    outputType.value = 'XML';
  } else if (method === 'Host') {
    hintEl.textContent = 'Enter shell script filename located under $APPL_TOP/<appl>/bin (e.g., xx_emp_sync.prog).';
    fileInput.value = 'xx_emp_sync.prog';
    outputType.value = 'TEXT';
  } else if (method === 'Java Concurrent Program') {
    hintEl.textContent = 'Enter Java class path (e.g., oracle.apps.xxcus.cp.EmployeeBatchCp).';
    fileInput.value = 'oracle.apps.xxcus.cp.EmployeeBatchCp';
    outputType.value = 'TEXT';
  } else if (method === 'SQL*Plus') {
    hintEl.textContent = 'Enter SQL script filename (e.g., xx_emp_export.sql).';
    fileInput.value = 'xx_emp_export.sql';
    outputType.value = 'TEXT';
  }
}

function toggleAlertEventFields() {
  const type = document.getElementById('alr_type').value;
  const tblGroup = document.getElementById('alr_table_group');
  if (type === 'E') {
    tblGroup.style.display = 'block';
  } else {
    tblGroup.style.display = 'none';
  }
}

function toggleSqlFields() {
  const type = document.getElementById('sql_obj_type').value;
  const apiSelect = document.getElementById('sql_api_select');
  if (type === 'API_WRAPPER') {
    apiSelect.closest('.form-group').style.display = 'block';
  } else {
    apiSelect.closest('.form-group').style.display = 'none';
  }
}

function resetForm(formId) {
  if (confirm('Are you sure you want to reset this form to default values?')) {
    document.getElementById(formId).reset();
  }
}

// ==================== VALIDATION ====================
function validateCurrentForm(module) {
  let errors = [];

  if (module === 'concurrent') {
    const cpName = document.getElementById('cp_name').value.trim();
    const cpShort = document.getElementById('cp_short_name').value.trim();
    const cpAppl = document.getElementById('cp_appl').value.trim();
    const cpExec = document.getElementById('cp_exec_name').value.trim();
    const cpFile = document.getElementById('cp_exec_file').value.trim();

    if (!cpName) errors.push('Program User Name is required.');
    if (!cpShort) errors.push('Program Short Name is required.');
    if (cpShort && !/^[A-Z0-9_]+$/.test(cpShort)) errors.push('Program Short Name must contain only uppercase letters, numbers, and underscores.');
    if (cpShort.length > 30) errors.push('Program Short Name cannot exceed 30 characters.');
    if (!cpAppl) errors.push('Application Short Name is required.');
    if (!cpExec) errors.push('Executable Name is required.');
    if (!cpFile) errors.push('Execution File Name is required.');
  } else if (module === 'report') {
    const repName = document.getElementById('rep_name').value.trim();
    const repShort = document.getElementById('rep_short_name').value.trim();
    const repAppl = document.getElementById('rep_appl').value.trim();
    const repSql = document.getElementById('rep_sql').value.trim();

    if (!repName) errors.push('Report Name is required.');
    if (!repShort) errors.push('Report Short Name is required.');
    if (!repAppl) errors.push('Application Short Name is required.');
    if (!repSql) errors.push('Main SQL query is required.');
  } else if (module === 'workflow') {
    const wfItem = document.getElementById('wf_item_type').value.trim();
    const wfProcess = document.getElementById('wf_process_name').value.trim();
    const wfPkg = document.getElementById('wf_pkg_name').value.trim();

    if (!wfItem) errors.push('Workflow Item Type is required.');
    if (wfItem.length > 8) errors.push('Workflow Item Type must be 8 characters or fewer (Oracle EBS Workflow standard).');
    if (!wfProcess) errors.push('Workflow Process Name is required.');
    if (!wfPkg) errors.push('Workflow PL/SQL Package Name is required.');
  } else if (module === 'alert') {
    const alrName = document.getElementById('alr_name').value.trim();
    const alrAppl = document.getElementById('alr_appl').value.trim();
    const alrSql = document.getElementById('alr_sql').value.trim();

    if (!alrName) errors.push('Alert Name is required.');
    if (!alrAppl) errors.push('Application Short Name is required.');
    if (!alrSql) errors.push('Alert Select SQL is required.');
  } else if (module === 'oaf') {
    const oafAppl = document.getElementById('oaf_appl').value.trim();
    const oafPkg = document.getElementById('oaf_pkg').value.trim();
    const oafPage = document.getElementById('oaf_page_name').value.trim();

    if (!oafAppl) errors.push('OAF Application Short Name is required.');
    if (!oafPkg) errors.push('Base Package Path is required.');
    if (!oafPage) errors.push('Page Name (.xml) is required.');
  } else if (module === 'sql') {
    const sqlName = document.getElementById('sql_pkg_name').value.trim();
    if (!sqlName) errors.push('Object / Package Name is required.');
  }

  if (errors.length === 0) {
    alert('âœ“ VALIDATION SUCCESSFUL: All fields comply with Oracle EBS R12 standards.');
    return true;
  } else {
    alert('âŒ VALIDATION ISSUES FOUND:\n\nâ€¢ ' + errors.join('\nâ€¢ '));
    return false;
  }
}

// =========================================================================
// MODULE 1: CONCURRENT PROGRAM GENERATOR
// =========================================================================
function generateConcurrentScript() {
  const cpName = document.getElementById('cp_name').value.trim();
  const cpShort = document.getElementById('cp_short_name').value.trim();
  const cpAppl = document.getElementById('cp_appl').value.trim();
  const reqGroup = document.getElementById('cp_request_group').value.trim() || 'System Administrator Reports';
  const execName = document.getElementById('cp_exec_name').value.trim();
  const execMethod = document.getElementById('cp_exec_method').value;
  const execFile = document.getElementById('cp_exec_file').value.trim();
  const outputType = document.getElementById('cp_output_type').value;
  const saveOutput = document.getElementById('cp_save_output').value;
  const params = getParametersFromTable('cp-params-body');

  let paramScripts = '';
  params.forEach(p => {
    paramScripts += `
    -- Parameter: ${p.name}
    fnd_program.parameter(
        program_short_name => '${cpShort}',
        application        => '${cpAppl}',
        sequence           => ${p.seq},
        parameter          => '${p.name}',
        description        => '${p.prompt}',
        enabled            => 'Y',
        value_set          => '${p.vset}',
        default_type       => NULL,
        default_value      => NULL,
        required           => '${p.req}',
        enable_security    => 'N',
        display            => 'Y',
        display_size       => 30,
        description_size   => 50,
        concatenated_description_size => 30,
        prompt             => '${p.prompt}'
    );
`;
  });

  const code = `/********************************************************************************
 * SCRIPT: ${cpShort}_registration.sql
 * PURPOSE: Automated FND_PROGRAM Registration for ${cpName}
 * AUTHOR: Oracle EBS Technical MCP Studio
 * CREATED: ${new Date().toISOString().split('T')[0]}
 * ENVIRONMENT: ${state.currentEnv}
 ********************************************************************************/
SET SERVEROUTPUT ON SIZE 1000000;
SET DEFINE OFF;

DECLARE
    l_app_short_name   VARCHAR2(50)  := '${cpAppl}';
    l_cp_name          VARCHAR2(240) := '${cpName}';
    l_cp_short_name    VARCHAR2(30)  := '${cpShort}';
    l_exec_name        VARCHAR2(30)  := '${execName}';
    l_exec_method      VARCHAR2(80)  := '${execMethod}';
    l_exec_file        VARCHAR2(240) := '${execFile}';
    l_req_group        VARCHAR2(240) := '${reqGroup}';
BEGIN
    DBMS_OUTPUT.PUT_LINE('=== [START] Registering Concurrent Program: ' || l_cp_short_name || ' ===');

    -- Initialize EBS Context for System Administrator (Required for flexfields/SRS)
    BEGIN
        fnd_global.apps_initialize(user_id => 0, resp_id => 20420, resp_appl_id => 1);
    EXCEPTION WHEN OTHERS THEN NULL;
    END;

    ----------------------------------------------------------------------------
    -- 1. Delete Prior Program & Executable (Reverse Dependency Order)
    ----------------------------------------------------------------------------
    IF fnd_program.program_exists(program => l_cp_short_name, application => l_app_short_name) THEN
        DBMS_OUTPUT.PUT_LINE('Prior program exists. Deleting: ' || l_cp_short_name);
        fnd_program.delete_program(program_short_name => l_cp_short_name, application => l_app_short_name);
    END IF;

    IF fnd_program.executable_exists(executable_short_name => l_exec_name, application => l_app_short_name) THEN
        DBMS_OUTPUT.PUT_LINE('Prior executable exists. Deleting: ' || l_exec_name);
        fnd_program.delete_executable(executable_short_name => l_exec_name, application => l_app_short_name);
    END IF;

    ----------------------------------------------------------------------------
    -- 2. Register Executable
    ----------------------------------------------------------------------------
    fnd_program.executable(
        executable          => l_cp_name || ' Executable',
        application         => l_app_short_name,
        short_name          => l_exec_name,
        description         => l_cp_name || ' Executable',
        execution_method    => l_exec_method,
        execution_file_name => l_exec_file,
        subroutine_name     => NULL,
        icon_name           => NULL,
        language_code       => 'US',
        execution_file_path => NULL
    );
    DBMS_OUTPUT.PUT_LINE('Executable registered successfully: ' || l_exec_name);

    ----------------------------------------------------------------------------
    -- 3. Register Concurrent Program
    ----------------------------------------------------------------------------

    fnd_program.register(
        program                => l_cp_name,
        application            => l_app_short_name,
        enabled                => 'Y',
        short_name             => l_cp_short_name,
        description            => l_cp_name,
        executable_short_name  => l_exec_name,
        executable_application => l_app_short_name,
        save_output            => '${saveOutput}',
        print                  => 'Y',
        use_in_srs             => 'Y',
        output_type            => '${outputType}',
        language_code          => 'US'
    );
    DBMS_OUTPUT.PUT_LINE('Program registered successfully: ' || l_cp_short_name);

    ----------------------------------------------------------------------------
    -- 3. Register Parameters
    ----------------------------------------------------------------------------
${paramScripts}
    DBMS_OUTPUT.PUT_LINE('Parameters registered successfully.');

    ----------------------------------------------------------------------------
    -- 4. Attach Program to Request Group
    ----------------------------------------------------------------------------
    BEGIN
        fnd_program.add_to_group(
            program_short_name  => l_cp_short_name,
            program_application => l_app_short_name,
            request_group       => l_req_group,
            group_application   => l_app_short_name
        );
        DBMS_OUTPUT.PUT_LINE('Successfully attached to Request Group: ' || l_req_group);
    EXCEPTION
        WHEN OTHERS THEN
            DBMS_OUTPUT.PUT_LINE('Notice: Request group attachment note: ' || SQLERRM);
    END;

    COMMIT;
    DBMS_OUTPUT.PUT_LINE('=== [SUCCESS] Concurrent Program Registration Complete ===');
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        DBMS_OUTPUT.PUT_LINE('âŒ [ERROR] Registration failed: ' || SQLERRM);
        RAISE;
END;
/
COMMIT;
`;

  const deploy = `#!/bin/bash
# ==============================================================================
# DEPLOYMENT GUIDE: Concurrent Program ${cpShort}
# ==============================================================================
# Step 1: Upload and compile underlying PL/SQL Package or report file
# Step 2: Run the automated registration script under APPS schema
# ==============================================================================

echo "Deploying Concurrent Program: ${cpShort}..."
sqlplus apps/\$APPS_PWD @${cpShort}_registration.sql

# Verification Step:
sqlplus -s apps/\$APPS_PWD <<EOF
SET LINESIZE 200;
COL USER_CONCURRENT_PROGRAM_NAME FORMAT A40;
COL CONCURRENT_PROGRAM_NAME FORMAT A25;
COL EXECUTION_METHOD_CODE FORMAT A10;
SELECT fcp.concurrent_program_name, 
       fcpt.user_concurrent_program_name, 
       fe.execution_method_code, 
       fe.execution_file_name
FROM   fnd_concurrent_programs fcp,
       fnd_concurrent_programs_tl fcpt,
       fnd_executables fe
WHERE  fcp.concurrent_program_id = fcpt.concurrent_program_id
  AND  fcpt.language = 'US'
  AND  fcp.executable_id = fe.executable_id
  AND  fcp.concurrent_program_name = '${cpShort}';
EOF
echo "Deployment verification finished."
`;

  const rollback = `/********************************************************************************
 * ROLLBACK SCRIPT: ${cpShort}_rollback.sql
 * PURPOSE: Unregister Concurrent Program & Executable from EBS Instance
 ********************************************************************************/
SET SERVEROUTPUT ON SIZE 1000000;
DECLARE
    l_appl  VARCHAR2(50) := '${cpAppl}';
    l_cp    VARCHAR2(30) := '${cpShort}';
    l_exec  VARCHAR2(30) := '${execName}';
    l_grp   VARCHAR2(240) := '${reqGroup}';
BEGIN
    DBMS_OUTPUT.PUT_LINE('Removing Program from Request Group...');
    BEGIN
        fnd_program.remove_from_group(
            program_short_name  => l_cp,
            program_application => l_appl,
            request_group       => l_grp,
            group_application   => l_appl
        );
    EXCEPTION WHEN OTHERS THEN NULL; END;

    DBMS_OUTPUT.PUT_LINE('Deleting Concurrent Program: ' || l_cp);
    IF fnd_program.program_exists(l_cp, l_appl) THEN
        fnd_program.delete_program(l_cp, l_appl);
    END IF;

    DBMS_OUTPUT.PUT_LINE('Deleting Executable: ' || l_exec);
    IF fnd_program.executable_exists(l_exec, l_appl) THEN
        fnd_program.delete_executable(l_exec, l_appl);
    END IF;

    COMMIT;
    DBMS_OUTPUT.PUT_LINE('Rollback completed successfully.');
END;
/
COMMIT;
`;

  const doc = `# Technical Specification Document (MD070)
## Concurrent Program: ${cpName} (${cpShort})

### 1. Overview
- **User Program Name**: ${cpName}
- **Short Name**: \`${cpShort}\`
- **Application**: \`${cpAppl}\`
- **Executable Name**: \`${execName}\`
- **Execution Method**: ${execMethod}
- **Execution File**: \`${execFile}\`
- **Output Format**: ${outputType}
- **Attached Request Group**: ${reqGroup}

### 2. Parameters Specification
| Sequence | Parameter Name | Prompt | Value Set | Required? |
| :--- | :--- | :--- | :--- | :--- |
${params.map(p => `| ${p.seq} | \`${p.name}\` | ${p.prompt} | \`${p.vset}\` | ${p.req} |`).join('\n')}

### 3. Execution & Verification Checklist
1. Verify executable file \`${execFile}\` is present in database or server \`$APPL_TOP\`.
2. Execute registration script under \`APPS\`.
3. Switch responsibility to one containing Request Group \`${reqGroup}\`.
4. Submit SRS request and verify output log under \`$APPLCSF/$APPLLOG\`.
`;

  renderOutput(`${cpShort}_registration.sql`, code, deploy, rollback, doc);
}

function generateConcurrentPLSQLPackage() {
  const cpName = document.getElementById('cp_name').value.trim();
  const cpShort = document.getElementById('cp_short_name').value.trim();
  const execFile = document.getElementById('cp_exec_file').value.trim();
  const params = getParametersFromTable('cp-params-body');

  let pkgName = 'xx_' + cpShort.toLowerCase() + '_pkg';
  let procName = 'main';
  if (execFile.includes('.')) {
    const parts = execFile.split('.');
    pkgName = parts[0].toLowerCase();
    procName = parts[1].toLowerCase();
  }

  const paramSignature = params.map(p => `        ${p.name.toLowerCase().padEnd(25)} IN VARCHAR2 DEFAULT NULL`).join(',\n');
  const paramPrint = params.map(p => `    fnd_file.put_line(fnd_file.log, 'Param ${p.name}: ' || ${p.name.toLowerCase()});`).join('\n');

  const spec = `CREATE OR REPLACE PACKAGE ${pkgName} AS
/********************************************************************************
 * PACKAGE: ${pkgName}
 * PURPOSE: Concurrent Program Handler for ${cpName}
 ********************************************************************************/
    PROCEDURE ${procName} (
        errbuf                    OUT NOCOPY VARCHAR2,
        retcode                   OUT NOCOPY VARCHAR2${params.length > 0 ? ',\n' + paramSignature : ''}
    );
END ${pkgName};
/
`;

  const body = `CREATE OR REPLACE PACKAGE BODY ${pkgName} AS
/********************************************************************************
 * PACKAGE BODY: ${pkgName}
 ********************************************************************************/

    PROCEDURE ${procName} (
        errbuf                    OUT NOCOPY VARCHAR2,
        retcode                   OUT NOCOPY VARCHAR2${params.length > 0 ? ',\n' + paramSignature : ''}
    ) IS
        l_request_id NUMBER := fnd_global.conc_request_id;
        l_user_id    NUMBER := fnd_global.user_id;
        l_login_id   NUMBER := fnd_global.login_id;
        l_count      NUMBER := 0;
    BEGIN
        -- Default to SUCCESS
        retcode := '0';
        errbuf  := 'Completed Successfully.';

        fnd_file.put_line(fnd_file.log, '================================================');
        fnd_file.put_line(fnd_file.log, 'Starting Concurrent Request ID: ' || l_request_id);
        fnd_file.put_line(fnd_file.log, 'Execution Timestamp           : ' || TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS'));
        fnd_file.put_line(fnd_file.log, 'User ID                       : ' || l_user_id);
        fnd_file.put_line(fnd_file.log, '================================================');
        fnd_file.put_line(fnd_file.log, 'Input Parameters:');
${paramPrint}
        fnd_file.put_line(fnd_file.log, '================================================');

        -- Output Report Header
        fnd_file.put_line(fnd_file.output, '${cpName}');
        fnd_file.put_line(fnd_file.output, 'Report Date: ' || TO_CHAR(SYSDATE, 'DD-MON-YYYY HH24:MI:SS'));
        fnd_file.put_line(fnd_file.output, 'Request ID : ' || l_request_id);
        fnd_file.put_line(fnd_file.output, '--------------------------------------------------------------------------------');

        -- Main Business Processing Logic
        -- TODO: Implement business cursors and record processing here
        l_count := 1;

        fnd_file.put_line(fnd_file.log, 'Total records processed: ' || l_count);
        fnd_file.put_line(fnd_file.output, 'Processing finished. Total records: ' || l_count);
        fnd_file.put_line(fnd_file.log, 'Program completed successfully.');

    EXCEPTION
        WHEN OTHERS THEN
            retcode := '2'; -- 2 = ERROR, 1 = WARNING
            errbuf  := 'Fatal Error in ' || '${pkgName}.${procName}' || ': ' || SQLERRM;
            fnd_file.put_line(fnd_file.log, 'âŒ [FATAL EXCEPTION]: ' || SQLERRM);
            fnd_file.put_line(fnd_file.log, DBMS_UTILITY.FORMAT_ERROR_BACKTRACE);
    END ${procName};

END ${pkgName};
/
SHOW ERRORS PACKAGE BODY ${pkgName};
`;

  const code = spec + '\n' + body;
  const deploy = `-- Compile Package in APPS Schema
sqlplus apps/\$APPS_PWD @${pkgName}.pks
sqlplus apps/\$APPS_PWD @${pkgName}.pkb
`;
  const rollback = `DROP PACKAGE ${pkgName};`;
  const doc = `### PL/SQL Concurrent Handler Package
Package: \`${pkgName}\`
Main Procedure: \`${procName}\`
Signature matches standard Oracle EBS SRS Concurrent Manager conventions (ERRBUF, RETCODE).
`;

  renderOutput(`${pkgName}.sql`, code, deploy, rollback, doc);
}

// =========================================================================
// =========================================================================
// MODULE 2: REPORT GENERATOR (DYNAMIC SQL, BI PUBLISHER & RDF)
// =========================================================================

/**
 * Robust SQL Column & Alias Extractor:
 * Parses ANY SELECT statement, respects subqueries/parentheses, handles AS aliases,
 * implicit aliases, expressions, and qualified column names.
 */
function parseSqlColumns(sqlText) {
  if (!sqlText || typeof sqlText !== 'string') {
    return ['RECORD_ID', 'RECORD_NAME'];
  }
  
  // Strip single-line and multi-line comments
  const clean = sqlText.replace(/--.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '');
  
  // Find top-level SELECT ... FROM (handles SELECT DISTINCT / ALL)
  const match = clean.match(/^\s*SELECT\s+(?:DISTINCT\s+|ALL\s+)?([\s\S]+?)\s+FROM\b/i) || 
                clean.match(/\bSELECT\s+(?:DISTINCT\s+|ALL\s+)?([\s\S]+?)\s+FROM\b/i);
  if (!match) {
    return ['RECORD_ID', 'RECORD_NAME'];
  }
  
  const rawCols = match[1].trim();
  
  // Split columns by comma outside parentheses
  const columns = [];
  let current = '';
  let parenDepth = 0;
  for (let i = 0; i < rawCols.length; i++) {
    const ch = rawCols[i];
    if (ch === '(') {
      parenDepth++;
      current += ch;
    } else if (ch === ')') {
      parenDepth = Math.max(0, parenDepth - 1);
      current += ch;
    } else if (ch === ',' && parenDepth === 0) {
      if (current.trim()) columns.push(current.trim());
      current = '';
    } else {
      current += ch;
    }
  }
  if (current.trim()) columns.push(current.trim());
  
  const parsed = [];
  columns.forEach((col, idx) => {
    col = col.trim();
    if (!col) return;
    
    // Explicit alias: "AS alias" or "AS 'alias'" or 'AS "alias"'
    const asMatch = col.match(/\bAS\s+["']?([a-zA-Z0-9_#$]+)["']?$/i);
    if (asMatch) {
      parsed.push(asMatch[1].replace(/[^a-zA-Z0-9_#$]/g, '').toUpperCase());
      return;
    }
    
    // Implicit alias: "expression alias"
    const words = col.split(/\s+/);
    if (words.length >= 2) {
      const last = words[words.length - 1].replace(/["']/g, '').toUpperCase();
      if (/^[A-Z0-9_#$]+$/.test(last) && !['NULL', 'SYSDATE', 'DESC', 'ASC', 'DISTINCT', 'OVER', 'THEN', 'ELSE', 'END', 'AS'].includes(last)) {
        parsed.push(last);
        return;
      }
    }
    
    // Fallback: table.column -> column
    const dotParts = col.split('.');
    const base = dotParts[dotParts.length - 1].replace(/[^a-zA-Z0-9_#$]/g, '').toUpperCase();
    if (base && !['NULL', 'SYSDATE'].includes(base)) {
      parsed.push(base);
    } else {
      parsed.push(`COL_${idx + 1}`);
    }
  });
  
  return parsed.length > 0 ? parsed : ['RECORD_ID', 'RECORD_NAME'];
}

/**
 * Extract bind variables from SQL (e.g. :P_ORG_ID, :P_EFFECTIVE_DATE)
 */
function parseSqlParameters(sqlText) {
  if (!sqlText) return [];
  const clean = sqlText.replace(/--.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '');
  const matches = clean.match(/:([a-zA-Z0-9_]+)/g) || [];
  const unique = [];
  matches.forEach(m => {
    const p = m.replace(':', '').toUpperCase();
    if (!unique.includes(p) && !['MI', 'SS', 'HH24', 'MI', 'SS'].includes(p)) {
      unique.push(p);
    }
  });
  return unique;
}

/**
 * Format column name into elegant Title Case header label
 */
function formatColumnLabel(col) {
  if (!col) return '';
  let str = col.replace(/_/g, ' ').toLowerCase();
  str = str.replace(/\b\w/g, c => c.toUpperCase());
  str = str.replace(/\bId\b/g, 'ID')
           .replace(/\bNum\b/g, 'Number')
           .replace(/\bEmp\b/g, 'Employee')
           .replace(/\bOrg\b/g, 'Organization')
           .replace(/\bDept\b/g, 'Department')
           .replace(/\bCd\b/g, 'Code')
           .replace(/\bQty\b/g, 'Quantity')
           .replace(/\bAmt\b/g, 'Amount');
  return str;
}

/**
 * Real-time SQL Preview Handler: updates column badges as user types
 */
function updateSqlColumnPreview() {
  const sqlEl = document.getElementById('rep_sql');
  const previewEl = document.getElementById('detected_cols_text');
  if (!sqlEl || !previewEl) return;

  const cols = parseSqlColumns(sqlEl.value);
  const params = parseSqlParameters(sqlEl.value);

  const paramNote = params.length > 0 ? ` | Params: [${params.join(', ')}]` : '';
  previewEl.textContent = `${cols.length} Columns Detected: [${cols.join(', ')}]${paramNote}`;
}

/**
 * Auto-Sync Parameters from SQL into the parameters table
 */
function syncSqlParametersToTable() {
  const sqlEl = document.getElementById('rep_sql');
  if (!sqlEl) return;
  const params = parseSqlParameters(sqlEl.value);
  if (params.length === 0) {
    alert('No bind parameters (e.g. :P_ORG_ID) found in the SQL query.');
    return;
  }

  const tbody = document.getElementById('rep-params-body');
  if (!tbody) return;
  tbody.innerHTML = '';

  params.forEach((p, idx) => {
    const seq = (idx + 1) * 10;
    const prompt = formatColumnLabel(p.replace(/^P_/, ''));
    let vset = '70 Characters';
    if (p.includes('DATE')) vset = 'FND_STANDARD_DATE';
    else if (p.includes('ID') || p.includes('NUM')) vset = '70 Characters';

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input type="number" class="tbl-input seq" value="${seq}" step="10"></td>
      <td><input type="text" class="tbl-input param-name" value="${p}"></td>
      <td><input type="text" class="tbl-input param-prompt" value="${prompt}"></td>
      <td><input type="text" class="tbl-input param-vset" value="${vset}"></td>
      <td>
        <select class="tbl-input param-req">
          <option value="Y">Y</option>
          <option value="N" selected>N</option>
        </select>
      </td>
      <td><button type="button" class="btn-icon delete-btn" onclick="removeRow(this)">✕</button></td>
    `;
    tbody.appendChild(tr);
  });

  alert(`✅ Auto-synced ${params.length} parameters from SQL into table:\n${params.join(', ')}`);
}

/**
 * Dynamic RTF Layout Generator for BI Publisher:
 * Builds full corporate-styled table matching EVERY column from the SQL query dynamically.
 */
function generateDynamicRtfContent(repName, repShort, repAppl, columns, params) {
  const totalW = 10080;
  const n = Math.max(1, columns.length);
  const colW = Math.floor(totalW / n);

  const cellxList = [];
  for (let i = 0; i < n; i++) {
    cellxList.push(i === n - 1 ? totalW : Math.min(totalW, (i + 1) * colW));
  }

  const cellxHeaders = cellxList.map(cx => 
    `\\clbrdrt\\brdrs\\brdrw15\\brdrcf2\\clbrdrl\\brdrs\\brdrw15\\brdrcf2\\clbrdrb\\brdrs\\brdrw20\\brdrcf2\\clbrdrr\\brdrs\\brdrw15\\brdrcf2\\clcbpat2\\cellx${cx}\n`
  ).join('');

  const headerCells = columns.map(c => 
    `\\pard\\intbl\\qc\\cf4\\b\\fs17 ${formatColumnLabel(c)}\\cell `
  ).join('');

  const cellxData = cellxList.map(cx => 
    `\\clbrdrt\\brdrs\\brdrw10\\brdrcf6\\clbrdrl\\brdrs\\brdrw10\\brdrcf6\\clbrdrb\\brdrs\\brdrw10\\brdrcf6\\clbrdrr\\brdrs\\brdrw10\\brdrcf6\\cellx${cx}\n`
  ).join('');

  const dataCells = columns.map((c, i) => {
    if (i === 0) {
      return `\\pard\\intbl\\qc\\cf1\\b0\\fs17 <?for-each@row:G_MAIN?><?${c}?>\\cell `;
    } else {
      return `\\pard\\intbl\\ql\\cf1\\b0\\fs17 <?${c}?>\\cell `;
    }
  }).join('');

  const paramStr = params && params.length > 0 
    ? params.map(p => `\\cf5 ${p}: \\cf1 <?${p}?>`).join('\\tab\\tab ')
    : '\\cf5 All Records';

  const firstCol = columns[0] || 'RECORD_ID';

  return `{\\rtf1\\ansi\\ansicpg1252\\deff0\\deflang1033{\\fonttbl{\\f0\\fswiss\\fcharset0 Arial;}{\\f1\\fswiss\\fcharset0 Calibri;}{\\f2\\fnil\\fcharset0 Tahoma;}}
{\\colortbl ;\\red15\\green23\\blue42;\\red30\\green58\\blue138;\\red238\\green242\\blue255;\\red255\\green255\\blue255;\\red100\\green116\\blue139;\\red226\\green232\\blue240;\\red16\\green185\\blue129;}
\\viewkind4\\uc1
\\paperw12240\\paperh15840\\margl1080\\margr1080\\margt1080\\margb1080
\\pard\\qc\\b\\f0\\fs30\\cf2 ORACLE E-BUSINESS SUITE R12\\par
\\fs24\\cf1 ${repName || 'Report'}\\b0\\fs18\\cf5\\par
Application: ${repAppl}  |  Report Code: ${repShort}  |  Dynamic BI Publisher Template\\par
\\pard\\brdrb\\brdrs\\brdrw15\\brdrcf2\\par\\pard
\\par
\\pard\\cf1\\b\\fs18 Parameters Applied:\\b0\\fs17\\par
${paramStr}\\par
\\par
\\trowd\\trgaph108\\trleft-108
${cellxHeaders}
${headerCells}\\row
\\trowd\\trgaph108\\trleft-108
${cellxData}
${dataCells}\\row
\\trowd\\trgaph108\\trleft-108
\\clbrdrt\\brdrs\\brdrw15\\brdrcf2\\clbrdrl\\brdrs\\brdrw15\\brdrcf2\\clbrdrb\\brdrs\\brdrw15\\brdrcf2\\clbrdrr\\brdrs\\brdrw15\\brdrcf2\\clcbpat3\\cellx${Math.max(1000, totalW - 2800)}
\\clbrdrt\\brdrs\\brdrw15\\brdrcf2\\clbrdrl\\brdrs\\brdrw15\\brdrcf2\\clbrdrb\\brdrs\\brdrw15\\brdrcf2\\clbrdrr\\brdrs\\brdrw15\\brdrcf2\\clcbpat3\\cellx${totalW}
\\pard\\intbl\\qr\\cf2\\b\\fs17 Total Records Count:\\cell\\qc\\cf2 <?count(${firstCol})?>\\cell\\row
\\pard\\par
\\pard\\ql\\cf5\\fs16 Confidential - Oracle EBS Generated\\qr Page <?page_number?> of <?total_pages?>\\par
}`;
}

/**
 * Dynamic Sample XML Data Generator matching ANY column list
 */
function generateSampleXmlFromColumns(repShort, columns, params) {
  let xml = `<?xml version="1.0" encoding="UTF-8"?>\n<${repShort}>\n`;
  if (params && params.length > 0) {
    params.forEach(p => {
      let val = '1001';
      const pu = p.toUpperCase();
      if (pu.includes('DATE')) val = '2026-09-15';
      else if (pu.includes('ORG')) val = '204';
      xml += `    <${p}>${val}</${p}>\n`;
    });
  }

  const sampleValues = [
    { name: 'Ahmed Mohamed Ali', dept: 'Human Resources', job: 'HR Specialist', num: '1001', code: 'A100', amt: '5000.00', status: 'Active', date: '2020-01-15' },
    { name: 'Mahmoud Hassan Ibrahim', dept: 'Finance & Accounting', job: 'Senior Accountant', num: '1002', code: 'B200', amt: '7500.00', status: 'Active', date: '2021-03-20' },
    { name: 'Fatima Youssef Al-Sayed', dept: 'IT Operations', job: 'Database Administrator', num: '1003', code: 'C300', amt: '9200.00', status: 'Active', date: '2019-07-10' },
    { name: 'Tarek Khaled Mansour', dept: 'Supply Chain', job: 'Logistics Coordinator', num: '1004', code: 'D400', amt: '4800.00', status: 'Pending', date: '2022-11-05' }
  ];

  sampleValues.forEach((sample, idx) => {
    xml += `    <G_MAIN>\n`;
    columns.forEach(c => {
      let v = `${c}_VAL_${idx + 1}`;
      const cu = c.toUpperCase();
      if (cu.includes('NAME') && !cu.includes('DEPT') && !cu.includes('ORG')) v = sample.name;
      else if (cu.includes('DEPT') || cu.includes('ORG')) v = sample.dept;
      else if (cu.includes('JOB') || cu.includes('TITLE')) v = sample.job;
      else if (cu.includes('ID') || cu.includes('NUM')) v = (1000 + idx + 1).toString();
      else if (cu.includes('DATE')) v = sample.date;
      else if (cu.includes('EMAIL')) v = `employee${idx + 1}@company.com`;
      else if (cu.includes('AMT') || cu.includes('AMOUNT') || cu.includes('SALARY')) v = sample.amt;
      else if (cu.includes('STATUS')) v = sample.status;
      else if (cu.includes('DAYS') || cu.includes('COUNT') || cu.includes('QTY')) v = (idx + 2).toString();
      else if (cu.includes('TYPE')) v = idx % 2 === 0 ? 'Annual Leave' : 'Sick Leave';

      xml += `        <${c}>${v}</${c}>\n`;
    });
    xml += `    </G_MAIN>\n`;
  });

  xml += `</${repShort}>\n`;
  return xml;
}

function generateReportPackage() {
  const repName = document.getElementById('rep_name').value.trim();
  const repShort = document.getElementById('rep_short_name').value.trim();
  const repAppl = document.getElementById('rep_appl').value.trim();
  const repType = document.getElementById('rep_type').value;
  const repSql = document.getElementById('rep_sql').value.trim();
  const params = getParametersFromTable('rep-params-body');

  const pkgName = 'xx_' + repShort.toLowerCase() + '_pkg';

  const code = `/********************************************************************************
 * PACKAGE: ${pkgName}
 * PURPOSE: Report Data Provider & Triggers for ${repName}
 * ARCHITECTURE: ${repType}
 ********************************************************************************/
CREATE OR REPLACE PACKAGE ${pkgName} AS
    -- Global bind parameters
${params.map(p => `    ${p.name.padEnd(25)} VARCHAR2(240);`).join('\n')}

    -- Report Triggers
    FUNCTION before_report RETURN BOOLEAN;
    FUNCTION after_report RETURN BOOLEAN;
END ${pkgName};
/

CREATE OR REPLACE PACKAGE BODY ${pkgName} AS

    FUNCTION before_report RETURN BOOLEAN IS
    BEGIN
        fnd_file.put_line(fnd_file.log, '=== Starting Report: ${repName} ===');
        fnd_file.put_line(fnd_file.log, 'Request ID: ' || fnd_global.conc_request_id);
        RETURN TRUE;
    EXCEPTION
        WHEN OTHERS THEN
            fnd_file.put_line(fnd_file.log, 'Error in before_report: ' || SQLERRM);
            RETURN FALSE;
    END before_report;

    FUNCTION after_report RETURN BOOLEAN IS
    BEGIN
        fnd_file.put_line(fnd_file.log, '=== Finished Report: ${repName} ===');
        RETURN TRUE;
    END after_report;

END ${pkgName};
/
SHOW ERRORS;
`;

  const deploy = `# 1. Compile PL/SQL Package
sqlplus apps/\$APPS_PWD @${pkgName}.sql

# 2. Register Concurrent Program for XML Publisher
sqlplus apps/\$APPS_PWD <<EOF
BEGIN
  fnd_program.executable(
    executable          => '${repShort}_EXEC',
    application         => '${repAppl}',
    short_name          => '${repShort}_EXEC',
    description         => '${repName} Executable',
    execution_method    => 'Oracle Reports',
    execution_file_name => '${repShort}',
    language_code       => 'US'
  );
  fnd_program.register(
    program                => '${repName}',
    application            => '${repAppl}',
    enabled                => 'Y',
    short_name             => '${repShort}',
    description            => '${repName}',
    executable_short_name  => '${repShort}_EXEC',
    executable_application => '${repAppl}',
    save_output            => 'Y',
    output_type            => 'XML'
  );
  COMMIT;
END;
/
EOF
`;

  const rollback = `DROP PACKAGE ${pkgName};`;
  const doc = `# MD070 Report Specification: ${repName}
Architecture: ${repType}
Application: ${repAppl}
Parameters count: ${params.length}
`;

  renderOutput(`${pkgName}.sql`, code, deploy, rollback, doc);
}

function generateBipDataTemplate() {
  const repName = document.getElementById('rep_name').value.trim();
  const repShort = document.getElementById('rep_short_name').value.trim();
  const repAppl = document.getElementById('rep_appl').value.trim();
  const repSql = document.getElementById('rep_sql').value.trim();
  const params = getParametersFromTable('rep-params-body');

  const columns = parseSqlColumns(repSql);
  const paramXml = params.map(p => `        <parameter name="${p.name}" dataType="character"/>`).join('\n');
  const elementsXml = columns.map(c => `            <element name="${c}" value="${c}" />`).join('\n');

  const xml = `<?xml version="1.0" encoding="UTF-8" ?>
<dataTemplate name="${repShort}" description="${repName}" dataSourceRef="APPS" defaultPackage="xx_${repShort.toLowerCase()}_pkg" version="1.0">
    <properties>
        <property name="include_parameters" value="true" />
        <property name="include_null_Element" value="true" />
        <property name="xml_tag_case" value="upper" />
    </properties>

    <parameters>
${paramXml}
    </parameters>

    <dataQuery>
        <sqlStatement name="Q_MAIN">
            <![CDATA[
${repSql}
            ]]>
        </sqlStatement>
    </dataQuery>

    <dataStructure>
        <group name="G_MAIN" source="Q_MAIN">
            <!-- Child elements dynamically generated from Q_MAIN query columns (${columns.length} columns) -->
${elementsXml}
        </group>
    </dataStructure>
</dataTemplate>
`;

  const deploy = `# Upload Data Template using XDOLoader
java oracle.apps.xdo.oa.util.XDOLoader UPLOAD \\
    -DB_USERNAME apps \\
    -DB_PASSWORD \$APPS_PWD \\
    -JDBC_CONNECTION \$EBS_JDBC_URL \\
    -LOB_TYPE DATA_TEMPLATE \\
    -APPS_SHORT_NAME ${repAppl} \\
    -LOB_CODE ${repShort} \\
    -LANGUAGE 00 \\
    -TERRITORY 00 \\
    -FILE_NAME ${repShort}.xml
`;

  const rollback = `-- Rollback / delete Data Template from XDO_LOBS
DELETE FROM apps.xdo_lobs 
WHERE lob_code = '${repShort}' 
  AND lob_type = 'DATA_TEMPLATE' 
  AND application_short_name = '${repAppl}';
COMMIT;
`;

  const doc = `### BI Publisher Data Template Specification
Data Template XML definition for \`${repShort}\`.
Enables modern, high-performance Data Engine execution without classic RDF dependencies.
Dynamic Columns (${columns.length}): \`${columns.join('`, `')}\`.
`;

  renderOutput(`${repShort}_data_template.xml`, xml, deploy, rollback, doc);
}

function generateXDOLoaderCommands() {
  const repShort = document.getElementById('rep_short_name').value.trim();
  const repAppl = document.getElementById('rep_appl').value.trim();

  const sh = `#!/bin/bash
# ==============================================================================
# ORACLE BI PUBLISHER XDO LOADER MIGRATION SUITE
# ==============================================================================
# Use this script to upload or download Data Templates and RTF layouts.
# ==============================================================================

export APPS_USER="apps"
export APPS_PWD="\$APPS_PWD"
export JDBC_URL="jdbc:oracle:thin:@(DESCRIPTION=(ADDRESS=(PROTOCOL=tcp)(HOST=10.100.100.104)(PORT=1521))(CONNECT_DATA=(SERVICE_NAME=HRVIS)))"

echo "=== 1. Uploading Data Template XML ==="
java oracle.apps.xdo.oa.util.XDOLoader UPLOAD \\
    -DB_USERNAME \$APPS_USER \\
    -DB_PASSWORD \$APPS_PWD \\
    -JDBC_CONNECTION "\$JDBC_URL" \\
    -LOB_TYPE DATA_TEMPLATE \\
    -APPS_SHORT_NAME ${repAppl} \\
    -LOB_CODE ${repShort} \\
    -LANGUAGE 00 \\
    -TERRITORY 00 \\
    -XDO_FILE_TYPE XML \\
    -FILE_NAME ${repShort}_data_template.xml

echo "=== 2. Uploading RTF Layout Template ==="
java oracle.apps.xdo.oa.util.XDOLoader UPLOAD \\
    -DB_USERNAME \$APPS_USER \\
    -DB_PASSWORD \$APPS_PWD \\
    -JDBC_CONNECTION "\$JDBC_URL" \\
    -LOB_TYPE TEMPLATE \\
    -APPS_SHORT_NAME ${repAppl} \\
    -LOB_CODE ${repShort} \\
    -LANGUAGE en \\
    -TERRITORY US \\
    -XDO_FILE_TYPE RTF \\
    -FILE_NAME ${repShort}.rtf \\
    -NLS_CHECKS false

echo "=== 3. Validating XDO LOBs in Database ==="
sqlplus -s apps/\$APPS_PWD <<EOF
SET LINESIZE 160;
COL LOB_CODE FORMAT A25;
COL LOB_TYPE FORMAT A20;
COL FILE_NAME FORMAT A30;
SELECT application_short_name, lob_code, lob_type, file_name, last_update_date 
FROM apps.xdo_lobs 
WHERE lob_code = '${repShort}';
EOF
`;

  renderOutput(`deploy_${repShort}_xdo.sh`, sh, sh, `-- Delete XDO\nDELETE FROM apps.xdo_lobs WHERE lob_code = '${repShort}';\nCOMMIT;`, `XDOLoader deployment documentation.`);
}

function generateRtfTemplate() {
  const repName = document.getElementById('rep_name').value.trim();
  const repShort = document.getElementById('rep_short_name').value.trim();
  const repAppl = document.getElementById('rep_appl').value.trim();
  const repSql = document.getElementById('rep_sql')?.value.trim() || '';

  // Extract columns dynamically from the SQL query!
  const columns = parseSqlColumns(repSql);
  const params = parseSqlParameters(repSql);

  const rtf = generateDynamicRtfContent(repName, repShort, repAppl, columns, params);

  const deploy = `# Steps to register RTF Template in XML Publisher Administrator:
# 1. Responsibility: XML Publisher Administrator
# 2. Templates -> Create Template
# 3. Code: ${repShort}
# 4. Application: ${repAppl}
# 5. Data Definition: ${repShort}
# 6. Type: RTF
# 7. File: Upload ${repShort}.rtf
# Detected Columns: ${columns.join(', ')}
`;

  const rollback = `-- Remove template from XDO_LOBS
DELETE FROM apps.xdo_lobs 
WHERE lob_code = '${repShort}' AND lob_type = 'TEMPLATE';
COMMIT;
`;

  const doc = `# BI Publisher RTF Template Specification
- **Template Code**: \`${repShort}\`
- **Application**: \`${repAppl}\`
- **Dynamic Columns (${columns.length})**: \`${columns.join('`, `')}\`
- **Repeating Group**: \`G_MAIN\`
- **Compatible with**: Microsoft Word BI Publisher Desktop Plug-in & EBS R12 XML Publisher Engine.
`;

  renderOutput(`${repShort}.rtf`, rtf, deploy, rollback, doc);
}

function generateRdfSpecs() {
  const repName = document.getElementById('rep_name')?.value.trim() || 'Report';
  const repShort = document.getElementById('rep_short_name')?.value.trim() || 'XX_REPORT';
  const repAppl = document.getElementById('rep_appl')?.value.trim() || 'PER';
  const repSql = document.getElementById('rep_sql')?.value.trim() || '';
  const params = getParametersFromTable('rep-params-body');
  const columns = parseSqlColumns(repSql);

  const code = `/********************************************************************************
 * ORACLE REPORTS (RDF) SPECIFICATION & COMPILATION GUIDE
 * REPORT NAME : ${repName}
 * SHORT NAME  : ${repShort}
 * APPLICATION : ${repAppl}
 * CREATED BY  : Oracle EBS Technical MCP Studio
 * DETECTED COLS (${columns.length}): ${columns.join(', ')}
 ********************************************************************************/

-- 1. Oracle Reports Data Model Structure
-- Data Source Query: Q_MAIN
/*
${repSql}
*/

-- 2. Report Columns Mapping (Q_MAIN -> G_MAIN)
${columns.map((c, i) => `-- Column ${i + 1}: ${c.padEnd(25)} (Data Item: ${c})`).join('\n')}

-- 3. Report Parameters Specification
${params.map(p => `-- Parameter: ${p.name.padEnd(20)} | Prompt: ${p.prompt.padEnd(25)} | Value Set: ${p.vset}`).join('\n')}

-- 4. Reports Triggers Code (Embed in Report Properties)
--------------------------------------------------------------------------------
-- BEFORE REPORT TRIGGER
--------------------------------------------------------------------------------
FUNCTION BeforeReport RETURN BOOLEAN IS
BEGIN
    SRW.MESSAGE(1001, '=== [START] Report: ${repName} ===');
    SRW.MESSAGE(1002, 'Request ID: ' || TO_CHAR(:P_CONC_REQUEST_ID));
    RETURN (TRUE);
EXCEPTION
    WHEN OTHERS THEN
        SRW.MESSAGE(9999, 'Error in BeforeReport: ' || SQLERRM);
        RETURN (FALSE);
END;

--------------------------------------------------------------------------------
-- AFTER REPORT TRIGGER
--------------------------------------------------------------------------------
FUNCTION AfterReport RETURN BOOLEAN IS
BEGIN
    SRW.MESSAGE(1003, '=== [SUCCESS] Report Completed ===');
    RETURN (TRUE);
END;

-- 5. Server-Side RDF Binary Compilation Commands:
/*
# Ensure Oracle Reports environment is sourced:
source /u01/HRVIS/fs1/EBSapps/appl/APPSHRVIS_fusion01.env 2>/dev/null

# A. Compile XML report definition into binary .rdf (ROS.60050):
\$ORACLE_HOME/bin/rwconverter.sh \\
    batch=yes \\
    source=/tmp/${repShort}.xml \\
    dest=\$PER_TOP/reports/US/${repShort}.rdf \\
    stype=xmlfile \\
    dtype=rdffile \\
    userid=apps/\$APPS_PWD

# B. Compile .rdf binary into executable .rep:
\$ORACLE_HOME/bin/rwconverter.sh \\
    batch=yes \\
    source=\$PER_TOP/reports/US/${repShort}.rdf \\
    dest=\$PER_TOP/reports/US/${repShort}.rep \\
    dtype=repfile \\
    userid=apps/\$APPS_PWD
*/
`;

  const deploy = `#!/bin/bash
# ==============================================================================
# DEPLOYMENT SCRIPT: Oracle Reports ${repShort}.rdf
# ==============================================================================
export APPL_TOP_REP="\$PER_TOP/reports/US"

echo "Deploying ${repShort}.rdf to \$APPL_TOP_REP and \$AU_TOP/reports/US..."
cp /tmp/${repShort}.rdf \$APPL_TOP_REP/${repShort}.rdf
cp /tmp/${repShort}.rdf \$AU_TOP/reports/US/${repShort}.rdf
chmod 755 \$APPL_TOP_REP/${repShort}.rdf \$AU_TOP/reports/US/${repShort}.rdf

echo "Compiling ${repShort}.rdf to ${repShort}.rep..."
rwconverter.sh batch=yes source=\$APPL_TOP_REP/${repShort}.rdf dest=\$APPL_TOP_REP/${repShort}.rep dtype=repfile userid=apps/\$APPS_PWD
chmod 755 \$APPL_TOP_REP/${repShort}.rep 2>/dev/null

echo "Verifying compiled .rep file..."
ls -l \$APPL_TOP_REP/${repShort}.*
`;

  const rollback = `rm -f \$PER_TOP/reports/US/${repShort}.rdf \$PER_TOP/reports/US/${repShort}.rep \$AU_TOP/reports/US/${repShort}.rdf`;
  const doc = `# Oracle Reports 10g/11g/12c (RDF) Specification: ${repName}
- **Short Name**: \`${repShort}\`
- **File**: \`${repShort}.rdf\`
- **Dynamic Columns (${columns.length})**: \`${columns.join('`, `')}\`
- **Deploy Path**: \`\$PER_TOP/reports/US/\` & \`\$AU_TOP/reports/US/\`
- **Execution Method**: \`Oracle Reports\`
`;

  renderOutput(`${repShort}_rdf_spec.sql`, code, deploy, rollback, doc);
}

// =========================================================================
// MODULE 3: WORKFLOW GENERATOR
// =========================================================================
function generateWorkflowDefinitionScript() {
  const itemType    = document.getElementById('wf_item_type').value.trim();
  const displayName = document.getElementById('wf_display_name').value.trim();
  const processName = document.getElementById('wf_process_name').value.trim();
  const timeout     = document.getElementById('wf_timeout').value.trim() || '48';

  const code =
`/******************************************************************************
 * SCRIPT : register_${itemType.toLowerCase()}_definition.sql
 * PURPOSE: Register Oracle Workflow Item Type & Process via WF_LOAD package
 * METHOD : WF_LOAD in FORCE Mode (Official Oracle Workflow Builder Engine)
 ******************************************************************************/
SET SERVEROUTPUT ON SIZE 1000000;
SET DEFINE OFF;

DECLARE
    l_item_type        VARCHAR2(8)   := '${itemType}';
    l_display_name     VARCHAR2(80)  := '${displayName}';
    l_process_name     VARCHAR2(30)  := '${processName}';
    l_description      VARCHAR2(240) := '${displayName} - Custom Approval Workflow';
    l_protection_level NUMBER        := 20;
    l_custom_level     NUMBER        := 20;
    l_level_error      NUMBER;
    l_version          NUMBER;
    l_instance_id      NUMBER        := 0;
BEGIN
    DBMS_OUTPUT.PUT_LINE('=== [START] Registering via WF_LOAD in FORCE mode: ' || l_item_type || ' ===');

    -- Crucial: set FORCE mode and session_level = 0 to allow user custom levels
    wf_core.upload_mode   := 'FORCE';
    wf_core.session_level := 0;

    ---------------------------------------------------------------------------
    -- STEP 1: Register Item Type
    ---------------------------------------------------------------------------
    wf_load.upload_item_type(
        x_name              => l_item_type,
        x_display_name      => l_display_name,
        x_description       => l_description,
        x_protect_level     => l_protection_level,
        x_custom_level      => l_custom_level,
        x_wf_selector       => NULL,
        x_read_role         => NULL,
        x_write_role        => NULL,
        x_execute_role      => NULL,
        x_persistence_type  => 'TEMP',
        x_persistence_days  => '${timeout}',
        x_level_error       => l_level_error
    );
    DBMS_OUTPUT.PUT_LINE('  [OK] Item Type registered. (Code=' || l_level_error || ')');

    ---------------------------------------------------------------------------
    -- STEP 2: Register Process Activity
    ---------------------------------------------------------------------------
    wf_load.upload_activity(
        x_item_type         => l_item_type,
        x_name              => l_process_name,
        x_display_name      => l_display_name || ' Process',
        x_description       => l_description,
        x_type              => 'PROCESS',
        x_rerun             => 'RESET',
        x_protect_level     => l_protection_level,
        x_custom_level      => l_custom_level,
        x_effective_date    => SYSDATE - 1,
        x_function          => NULL,
        x_function_type     => NULL,
        x_result_type       => '*NONE*',
        x_cost              => 0,
        x_read_role         => NULL,
        x_write_role        => NULL,
        x_execute_role      => NULL,
        x_icon_name         => 'PROCESS.ICO',
        x_message           => NULL,
        x_error_process     => 'DEFAULT_ERROR',
        x_expand_role       => 'N',
        x_error_item_type   => 'WFERROR',
        x_runnable_flag     => 'Y',
        x_version           => l_version,
        x_level_error       => l_level_error
    );
    DBMS_OUTPUT.PUT_LINE('  [OK] Process Activity registered: ' || l_process_name || ' (Version=' || l_version || ')');

    ---------------------------------------------------------------------------
    -- STEP 3: Register Item Attributes
    ---------------------------------------------------------------------------
    wf_load.upload_item_attribute(
        x_item_type         => l_item_type,
        x_name              => 'TRANSACTION_ID',
        x_display_name      => 'Transaction ID',
        x_description       => 'Unique Transaction ID',
        x_sequence          => 10,
        x_type              => 'VARCHAR2',
        x_protect_level     => l_protection_level,
        x_custom_level      => l_custom_level,
        x_subtype           => 'SEND',
        x_format            => NULL,
        x_default           => NULL,
        x_level_error       => l_level_error
    );
    DBMS_OUTPUT.PUT_LINE('  [OK] Attribute TRANSACTION_ID registered.');

    wf_load.upload_item_attribute(
        x_item_type         => l_item_type,
        x_name              => 'APPROVER_ROLE',
        x_display_name      => 'Approver Role',
        x_description       => 'Role of the Approver',
        x_sequence          => 20,
        x_type              => 'ROLE',
        x_protect_level     => l_protection_level,
        x_custom_level      => l_custom_level,
        x_subtype           => 'SEND',
        x_format            => NULL,
        x_default           => NULL,
        x_level_error       => l_level_error
    );
    DBMS_OUTPUT.PUT_LINE('  [OK] Attribute APPROVER_ROLE registered.');

    ---------------------------------------------------------------------------
    -- STEP 4: Register Process Node
    ---------------------------------------------------------------------------
    l_instance_id := 0;
    wf_load.upload_process_activity(
        x_process_item_type => l_item_type,
        x_process_name      => l_process_name,
        x_process_version   => NVL(l_version, 1),
        x_activity_item_type=> l_item_type,
        x_activity_name     => l_process_name,
        x_instance_id       => l_instance_id,
        x_instance_label    => l_process_name,
        x_protect_level     => l_protection_level,
        x_custom_level      => l_custom_level,
        x_start_end         => 'START',
        x_default_result    => NULL,
        x_icon_geometry     => '0,0',
        x_perform_role      => NULL,
        x_perform_role_type => 'CONSTANT',
        x_user_comment      => NULL,
        x_level_error       => l_level_error
    );
    DBMS_OUTPUT.PUT_LINE('  [OK] Process Activity Node registered: ' || l_process_name || ' (Node=' || l_instance_id || ')');

    COMMIT;
    DBMS_OUTPUT.PUT_LINE('=== [SUCCESS] Workflow registered in Oracle EBS WF_LOAD! ===');
    DBMS_OUTPUT.PUT_LINE('Visible in Oracle Workflow Builder: Item Type ' || l_item_type);
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        DBMS_OUTPUT.PUT_LINE('[FATAL] ' || SQLERRM);
        DBMS_OUTPUT.PUT_LINE(DBMS_UTILITY.FORMAT_ERROR_BACKTRACE);
        RAISE;
END;
/

-- Verification Queries
SET LINESIZE 150;
COL name FORMAT A10;
COL display_name FORMAT A35;
COL persistence_type FORMAT A8;
SELECT t.name, tl.display_name, t.persistence_type, t.persistence_days
FROM apps.wf_item_types t, apps.wf_item_types_tl tl
WHERE t.name = tl.name AND tl.language = 'US' AND t.name = '${itemType}';

SELECT a.name AS activity_name, a.type, tl.display_name, a.runnable_flag
FROM apps.wf_activities a, apps.wf_activities_tl tl
WHERE a.item_type = tl.item_type AND a.name = tl.name AND a.version = tl.version
AND tl.language = 'US' AND a.item_type = '${itemType}';
`;

  const deploy =
`#!/bin/bash
# ============================================================
# DEPLOYMENT: Oracle Workflow Registration - ${itemType}
# ============================================================
echo "[1] Registering Workflow Definition via WF_LOAD..."
sqlplus apps/$APPS_PWD @register_${itemType.toLowerCase()}_definition.sql

echo "[2] Verifying in Oracle Workflow Builder:"
echo "    1. Open Oracle Workflow Builder"
echo "    2. File -> Open -> Database (APPS credentials)"
echo "    3. Select Item Type: ${itemType}"
`;

  const rollback =
`-- Rollback: Remove Workflow definition
DECLARE
    l_item_type VARCHAR2(8) := '${itemType}';
BEGIN
    FOR r IN (SELECT item_key FROM apps.wf_items WHERE item_type = l_item_type) LOOP
        wf_engine.AbortProcess(l_item_type, r.item_key);
    END LOOP;
    DELETE FROM apps.wf_item_attributes_tl WHERE item_type = l_item_type;
    DELETE FROM apps.wf_item_attributes    WHERE item_type = l_item_type;
    DELETE FROM apps.wf_activities_tl      WHERE item_type = l_item_type;
    DELETE FROM apps.wf_activities         WHERE item_type = l_item_type;
    DELETE FROM apps.wf_item_types_tl      WHERE name = l_item_type;
    DELETE FROM apps.wf_item_types         WHERE name = l_item_type;
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('Rollback complete for: ' || l_item_type);
EXCEPTION WHEN OTHERS THEN ROLLBACK; RAISE;
END;
/
`;

  const doc =
`# Workflow Registration: ${itemType}
Uses official **WF_LOAD** package in FORCE mode for full Oracle Workflow Builder compatibility.
`;

  renderOutput(`register_${itemType.toLowerCase()}_definition.sql`, code, deploy, rollback, doc);
}


function generateWorkflowPLSQL() {
  const itemType = document.getElementById('wf_item_type').value.trim();
  const processName = document.getElementById('wf_process_name').value.trim();
  const pkgName = document.getElementById('wf_pkg_name').value.trim();
  const apprType = document.getElementById('wf_appr_type').value;

  const code = `/********************************************************************************
 * WORKFLOW PACKAGE: ${pkgName}
 * ITEM TYPE       : ${itemType}
 * PROCESS         : ${processName}
 * APPROVAL TYPE   : ${apprType}
 ********************************************************************************/
CREATE OR REPLACE PACKAGE ${pkgName} AS

    -- Activity: Determine Approver
    PROCEDURE get_approver (
        itemtype  IN VARCHAR2,
        itemkey   IN VARCHAR2,
        actid     IN NUMBER,
        funcmode  IN VARCHAR2,
        resultout OUT NOCOPY VARCHAR2
    );

    -- Activity: Post-Approval Update
    PROCEDURE process_approval (
        itemtype  IN VARCHAR2,
        itemkey   IN VARCHAR2,
        actid     IN NUMBER,
        funcmode  IN VARCHAR2,
        resultout OUT NOCOPY VARCHAR2
    );

    -- Activity: Rejection Handler
    PROCEDURE process_rejection (
        itemtype  IN VARCHAR2,
        itemkey   IN VARCHAR2,
        actid     IN NUMBER,
        funcmode  IN VARCHAR2,
        resultout OUT NOCOPY VARCHAR2
    );

END ${pkgName};
/

CREATE OR REPLACE PACKAGE BODY ${pkgName} AS

    PROCEDURE get_approver (
        itemtype  IN VARCHAR2,
        itemkey   IN VARCHAR2,
        actid     IN NUMBER,
        funcmode  IN VARCHAR2,
        resultout OUT NOCOPY VARCHAR2
    ) IS
        l_trans_id   VARCHAR2(100);
        l_approver   VARCHAR2(320);
    BEGIN
        IF (funcmode = 'RUN') THEN
            l_trans_id := wf_engine.GetItemAttrText(itemtype, itemkey, 'TRANSACTION_ID');
            
            -- Lookup logic for approver role/user
            -- Default fallback to supervisor or HR admin
            l_approver := 'SYSADMIN';

            -- Set Approver Attribute
            wf_engine.SetItemAttrText(itemtype, itemkey, 'APPROVER_ROLE', l_approver);
            
            resultout := 'COMPLETE:T';
            RETURN;
        END IF;

        IF (funcmode = 'CANCEL') THEN
            resultout := 'COMPLETE:';
            RETURN;
        END IF;

        IF (funcmode = 'TIMEOUT') THEN
            resultout := 'COMPLETE:TIMEOUT';
            RETURN;
        END IF;
    EXCEPTION
        WHEN OTHERS THEN
            wf_core.context('${pkgName}', 'get_approver', itemtype, itemkey, actid, funcmode);
            RAISE;
    END get_approver;

    PROCEDURE process_approval (
        itemtype  IN VARCHAR2,
        itemkey   IN VARCHAR2,
        actid     IN NUMBER,
        funcmode  IN VARCHAR2,
        resultout OUT NOCOPY VARCHAR2
    ) IS
    BEGIN
        IF (funcmode = 'RUN') THEN
            -- Implement business logic on final approval
            resultout := 'COMPLETE:APPROVED';
            RETURN;
        END IF;
    EXCEPTION
        WHEN OTHERS THEN
            wf_core.context('${pkgName}', 'process_approval', itemtype, itemkey, actid);
            RAISE;
    END process_approval;

    PROCEDURE process_rejection (
        itemtype  IN VARCHAR2,
        itemkey   IN VARCHAR2,
        actid     IN NUMBER,
        funcmode  IN VARCHAR2,
        resultout OUT NOCOPY VARCHAR2
    ) IS
    BEGIN
        IF (funcmode = 'RUN') THEN
            -- Implement business logic on rejection
            resultout := 'COMPLETE:REJECTED';
            RETURN;
        END IF;
    EXCEPTION
        WHEN OTHERS THEN
            wf_core.context('${pkgName}', 'process_rejection', itemtype, itemkey, actid);
            RAISE;
    END process_rejection;

END ${pkgName};
/
SHOW ERRORS;
`;

  const deploy = `-- Compile workflow handler
sqlplus apps/\$APPS_PWD @${pkgName}.sql
`;

  const rollback = `DROP PACKAGE ${pkgName};`;

  const doc = `# Workflow Technical Specification: ${itemType}
Item Type: \`${itemType}\`
Process Name: \`${processName}\`
Activity functions adhere strictly to \`wf_engine\` conventions with funcmode handling (\`RUN\`, \`CANCEL\`, \`TIMEOUT\`).
`;

  renderOutput(`${pkgName}.sql`, code, deploy, rollback, doc);
}

function generateWorkflowStarterScript() {
  const itemType = document.getElementById('wf_item_type').value.trim();
  const processName = document.getElementById('wf_process_name').value.trim();

  const code = `/********************************************************************************
 * SCRIPT: launch_${itemType.toLowerCase()}_wf.sql
 * PURPOSE: Launch Oracle Workflow Process Programmatically
 ********************************************************************************/
SET SERVEROUTPUT ON SIZE 1000000;
SET DEFINE OFF;

DECLARE
    l_item_type   VARCHAR2(8)   := '${itemType}';
    l_item_key    VARCHAR2(240) := '${itemType}_' || TO_CHAR(SYSDATE, 'YYYYMMDDHH24MISS') || '_' || TRUNC(DBMS_RANDOM.VALUE(100, 999));
    l_process     VARCHAR2(30)  := '${processName}';
    l_trans_id    NUMBER        := 1001;
    l_user        VARCHAR2(100) := 'SYSADMIN';
BEGIN
    DBMS_OUTPUT.PUT_LINE('Creating Workflow Process: ' || l_item_type || ' / ' || l_item_key);

    -- 1. Initialize Workflow Process
    wf_engine.CreateProcess(
        itemtype => l_item_type,
        itemkey  => l_item_key,
        process  => l_process
    );

    -- 2. Set Item User Key (Visible in Notifications and Status Monitor)
    wf_engine.SetItemUserKey(
        itemtype => l_item_type,
        itemkey  => l_item_key,
        userkey  => 'Transaction #' || l_trans_id
    );

    -- 3. Set Item Attributes
    wf_engine.SetItemAttrText(l_item_type, l_item_key, 'TRANSACTION_ID', TO_CHAR(l_trans_id));
    wf_engine.SetItemAttrText(l_item_type, l_item_key, 'APPROVER_ROLE', l_user);

    -- 4. Set Item Owner
    wf_engine.SetItemOwner(
        itemtype => l_item_type,
        itemkey  => l_item_key,
        owner    => l_user
    );

    -- 5. Start Process
    wf_engine.StartProcess(
        itemtype => l_item_type,
        itemkey  => l_item_key
    );

    COMMIT;
    DBMS_OUTPUT.PUT_LINE('=== [SUCCESS] Workflow Process Launched! Item Key: ' || l_item_key || ' ===');
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        DBMS_OUTPUT.PUT_LINE('Failed to start workflow: ' || SQLERRM);
        RAISE;
END;
/
`;

  renderOutput(`launch_${itemType.toLowerCase()}.sql`, code, `-- Execute script\nsqlplus apps/\$APPS_PWD @launch_${itemType.toLowerCase()}.sql`, `-- Workflow instances can be aborted via wf_engine.abortprocess()`, `Starter documentation.`);
}

// =========================================================================
// MODULE 4: ALERT MANAGER GENERATOR
// =========================================================================
function generateAlertScripts() {
  const alrName = document.getElementById('alr_name').value.trim();
  const alrAppl = document.getElementById('alr_appl').value.trim();
  const alrType = document.getElementById('alr_type').value;
  const alrTable = document.getElementById('alr_table').value.trim();
  const alrSql = document.getElementById('alr_sql').value.trim();
  const recipient = document.getElementById('alr_recipient').value.trim();
  const subject = document.getElementById('alr_subject').value.trim();

  const code = `/********************************************************************************
 * SCRIPT: register_${alrName.toLowerCase()}.sql
 * PURPOSE: Register and Enable Oracle Alert in ALR_ALERTS
 * TYPE: ${alrType === 'E' ? 'Event Alert' : 'Periodic Alert'}
 * APPLICATION: ${alrAppl}
 * CREATED BY: Oracle EBS Technical MCP Studio
 ********************************************************************************/
SET SERVEROUTPUT ON SIZE 1000000;
SET DEFINE OFF;

DECLARE
    l_app_id     NUMBER;
    l_alert_id   NUMBER;
    l_count      NUMBER;
    l_table_id   NUMBER := NULL;
    l_table_app  NUMBER := NULL;
BEGIN
    DBMS_OUTPUT.PUT_LINE('=== [START] Registering Alert: ${alrName} ===');

    -- Get Application ID
    SELECT application_id INTO l_app_id
    FROM apps.fnd_application
    WHERE application_short_name = '${alrAppl}';

    -- Resolve Table info for Event Alert
    IF '${alrType}' = 'E' THEN
        BEGIN
            SELECT table_id, application_id INTO l_table_id, l_table_app
            FROM apps.fnd_tables
            WHERE table_name = '${alrTable.toUpperCase()}';
        EXCEPTION WHEN NO_DATA_FOUND THEN
            l_table_id := NULL;
        END;
    END IF;

    SELECT COUNT(1) INTO l_count
    FROM apps.alr_alerts
    WHERE application_id = l_app_id AND UPPER(alert_name) = '${alrName.toUpperCase()}';

    IF l_count = 0 THEN
        INSERT INTO apps.alr_alerts (
            application_id, alert_id, alert_name,
            last_update_date, last_updated_by,
            creation_date, created_by, last_update_login,
            alert_condition_type, enabled_flag,
            start_date_active, table_id, table_application_id,
            description, table_name,
            insert_flag, update_flag, delete_flag,
            sql_statement_text
        ) VALUES (
            l_app_id, apps.alr_alerts_s.NEXTVAL, '${alrName.toUpperCase()}',
            SYSDATE, 0,
            SYSDATE, 0, 0,
            '${alrType}', 'Y',
            SYSDATE, l_table_id, l_table_app,
            '${alrName} registered via Oracle EBS MCP Studio', '${alrTable.toUpperCase()}',
            'Y', 'Y', 'N',
            '${alrSql.replace(/'/g, "''")}'
        );
        DBMS_OUTPUT.PUT_LINE('  [OK] Alert created in ALR_ALERTS: ${alrName.toUpperCase()}');
    ELSE
        UPDATE apps.alr_alerts
        SET    enabled_flag       = 'Y',
               sql_statement_text = '${alrSql.replace(/'/g, "''")}',
               last_update_date   = SYSDATE,
               last_updated_by    = 0
        WHERE  application_id = l_app_id AND UPPER(alert_name) = '${alrName.toUpperCase()}';
        DBMS_OUTPUT.PUT_LINE('  [OK] Alert updated & enabled in ALR_ALERTS: ${alrName.toUpperCase()}');
    END IF;

    COMMIT;
    DBMS_OUTPUT.PUT_LINE('=== [SUCCESS] Alert ${alrName} is active in Oracle Alert Manager! ===');
EXCEPTION WHEN OTHERS THEN
    ROLLBACK;
    DBMS_OUTPUT.PUT_LINE('[ERROR] ' || SQLERRM);
    RAISE;
END;
/

-- Verification
SET LINESIZE 180;
COL alert_name FORMAT A35;
COL alert_type FORMAT A10;
COL enabled_flag FORMAT A8;
COL table_name FORMAT A30;
SELECT alert_name, alert_condition_type AS alert_type, enabled_flag, table_name
FROM   apps.alr_alerts
WHERE  UPPER(alert_name) = '${alrName.toUpperCase()}';
`;

  const deploy = `# Steps to verify in Oracle EBS:
# 1. Log in to EBS with responsibility: Alert Manager
# 2. Navigate to: Alert -> Define
# 3. Application: ${alrAppl}
# 4. Find Alert: ${alrName}
`;

  const rollback = `-- Disable alert:
UPDATE apps.alr_alerts SET enabled_flag = 'N' WHERE alert_name = '${alrName}';
COMMIT;
`;

  const doc = `# Alert Specification: ${alrName}
- **Type**: ${alrType}
- **Table**: ${alrTable}
- **Recipient**: ${recipient}
- **Subject**: ${subject}
`;

  renderOutput(`${alrName}.sql`, code, deploy, rollback, doc);
}

function generateAlertMessageBody() {
  const subject = document.getElementById('alr_subject').value.trim();
  const recipient = document.getElementById('alr_recipient').value.trim();

  const body = `To: ${recipient}
Subject: ${subject}
MIME-Version: 1.0
Content-Type: text/html; charset=UTF-8

<!DOCTYPE html>
<html>
<head>
<style>
  body { font-family: Arial, sans-serif; color: #333; margin: 20px; }
  .alert-box { border: 2px solid #0284c7; border-radius: 6px; padding: 15px; background: #f0f9ff; }
  .title { font-size: 16px; font-weight: bold; color: #0369a1; }
  table { width: 100%; border-collapse: collapse; margin-top: 15px; }
  th, td { padding: 8px 12px; border: 1px solid #cbd5e1; text-align: left; }
  th { background: #e2e8f0; }
</style>
</head>
<body>
  <div class="alert-box">
    <div class="title">Oracle E-Business Suite Notification</div>
    <p>An automated alert condition has been triggered in the system.</p>
    
    <table>
      <tr><th>Field</th><th>Value</th></tr>
      <tr><td>Employee Name</td><td>&FULL_NAME</td></tr>
      <tr><td>Employee Number</td><td>&EMP_NO</td></tr>
      <tr><td>Department</td><td>&DEPT_NAME</td></tr>
      <tr><td>Triggered Time</td><td>\${DATE} \${TIME}</td></tr>
    </table>

    <p style="margin-top: 20px; font-size: 12px; color: #64748b;">
      This email was generated automatically by Oracle Alert Manager. Please do not reply directly to this message.
    </p>
  </div>
</body>
</html>
`;

  renderOutput(`alert_notification_template.html`, body, `Paste template into Alert Manager Action Details.`, `-- N/A`, `Notification Template Doc`);
}

// =========================================================================
// MODULE 5: OAF STUDIO GENERATOR
// =========================================================================

function generateOAFPageXML() {
  const oafAppl = document.getElementById('oaf_appl')?.value.trim() || 'XXCUS';
  const oafPkg  = document.getElementById('oaf_pkg')?.value.trim() || 'xxcus.oracle.apps.per.employee.webui';
  const pageName = document.getElementById('oaf_page_name')?.value.trim() || 'EmpDetailsPG';
  const controller = document.getElementById('oaf_controller')?.value.trim() || 'EmpDetailsCO';
  const am = document.getElementById('oaf_am')?.value.trim() || 'EmpDetailsAM';
  const vo = document.getElementById('oaf_vo')?.value.trim() || 'EmpDetailsVO';

  const amPath = `${oafPkg.replace('.webui', '.server')}.${am}`;
  const coPath = `${oafPkg}.${controller}`;

  const xml = `<?xml version = '1.0' encoding = 'UTF-8'?>
<page xmlns:jrad="http://xmlns.oracle.com/jrad" xmlns:oa="http://xmlns.oracle.com/oa" xmlns:ui="http://xmlns.oracle.com/uix/ui" version="9.0.3.8.0_1556" xml:lang="en-US">
   <content>
      <oa:pageLayout id="PageLayoutRN" windowTitle="${pageName}" title="${pageName} - Official EBS Page" amDefName="${amPath}" controllerClass="${coPath}">
         <ui:corporateBranding>
            <oa:image id="CorporateBrandingImage" source="/OA_MEDIA/FNDSSCORP.gif"/>
         </ui:corporateBranding>
         <ui:contents>
            <oa:header id="HeaderRN" text="Details Section">
               <ui:contents>
                  <oa:table id="${vo}Table" amDefName="${amPath}">
                     <ui:contents>
                        <oa:messageStyledText id="EmpNumber" dataType="VARCHAR2" prompt="Employee Number" viewName="${vo}" viewAttr="EmployeeNumber"/>
                        <oa:messageStyledText id="FullName" dataType="VARCHAR2" prompt="Full Name" viewName="${vo}" viewAttr="FullName"/>
                        <oa:messageStyledText id="Department" dataType="VARCHAR2" prompt="Department" viewName="${vo}" viewAttr="DepartmentName"/>
                     </ui:contents>
                     <ui:tableActions>
                        <oa:submitButton id="SaveBtn" text="Save Changes" prompt="Save" event="save"/>
                        <oa:submitButton id="BackBtn" text="Back" prompt="Back" event="back" unvalidated="true"/>
                     </ui:tableActions>
                  </oa:table>
               </ui:contents>
            </oa:header>
         </ui:contents>
      </oa:pageLayout>
   </content>
</page>`;

  const deploy = `#!/bin/bash
# Import Page XML into MDS Repository
java -Dfile.encoding=UTF-8 oracle.jrad.tools.xml.importer.XMLImporter \
    $JAVA_TOP/${oafPkg.replace(/\./g, '/')}/${pageName}.xml \
    -username apps \
    -password $APPS_PWD \
    -dbconnection "(DESCRIPTION=(ADDRESS=(PROTOCOL=tcp)(HOST=10.100.100.104)(PORT=1532))(CONNECT_DATA=(SID=HRVIS)))" \
    -rootdir $JAVA_TOP
`;

  const rollback = `BEGIN jdr_utils.deletedocument('/${oafPkg.replace(/\./g, '/')}/${pageName}'); COMMIT; END; /`;
  const doc = `# OAF Page Specification: ${pageName}\n- AM: ${amPath}\n- Controller: ${coPath}`;

  renderOutput(`${pageName}.xml`, xml, deploy, rollback, doc);
}

function generateOAFController() {
  const oafPkg = document.getElementById('oaf_pkg').value.trim();
  const coName = document.getElementById('oaf_controller').value.trim() || 'EmpDetailsCO';
  const amName = document.getElementById('oaf_am').value.trim() || 'EmpDetailsAM';
  const voName = document.getElementById('oaf_vo').value.trim() || 'EmpDetailsVO';
  const action = document.getElementById('oaf_action').value;

  const java = `package ${oafPkg};

import java.io.Serializable;
import oracle.apps.fnd.common.VersionInfo;
import oracle.apps.fnd.framework.OAApplicationModule;
import oracle.apps.fnd.framework.OAException;
import oracle.apps.fnd.framework.OAViewObject;
import oracle.apps.fnd.framework.webui.OAControllerImpl;
import oracle.apps.fnd.framework.webui.OAPageContext;
import oracle.apps.fnd.framework.webui.OAWebBeanConstants;
import oracle.apps.fnd.framework.webui.beans.OAWebBean;

/**
 * Controller: ${coName}
 * Package   : ${oafPkg}
 * Generated by Oracle EBS R12 Development MCP Studio
 */
public class ${coName} extends OAControllerImpl {

    public static final String RCS_ID = "$Header$";
    public static final boolean RCS_ID_RECORDED = VersionInfo.recordClassVersion(RCS_ID, "%packagename%");

    /**
     * Layout and page initialization
     */
    @Override
    public void processRequest(OAPageContext pageContext, OAWebBean webBean) {
        super.processRequest(pageContext, webBean);

        OAApplicationModule am = pageContext.getApplicationModule(webBean);
        
        // Execute initial VO query if not back-navigation
        if (!pageContext.isBackNavigationFired(false)) {
            OAViewObject vo = (OAViewObject) am.findViewObject("${voName}");
            if (vo != null) {
                // Ensure VO is executed
                if (!vo.isExecuted()) {
                    vo.executeQuery();
                }
            }
        }
    }

    /**
     * Form and button event processing
     */
    @Override
    public void processFormRequest(OAPageContext pageContext, OAWebBean webBean) {
        super.processFormRequest(pageContext, webBean);

        String event = pageContext.getParameter(EVENT_PARAM);
        String source = pageContext.getParameter(SOURCE_PARAM);
        OAApplicationModule am = pageContext.getApplicationModule(webBean);

        if ("submitAction".equals(event) || pageContext.getParameter("SubmitBtn") != null) {
            try {
                // Commit transaction through Application Module
                am.invokeMethod("applyChanges");

                OAException confirmMessage = new OAException("Changes have been successfully saved.", OAException.CONFIRMATION);
                pageContext.putDialogMessage(confirmMessage);
            } catch (Exception ex) {
                throw new OAException("Error saving record: " + ex.getMessage(), OAException.ERROR);
            }
        } else if ("cancelAction".equals(event) || pageContext.getParameter("CancelBtn") != null) {
            // Rollback and navigate back
            am.invokeMethod("rollbackChanges");
            pageContext.forwardImmediate(
                "OA.jsp?page=/oracle/apps/fnd/framework/navigate/webui/NewHomePG",
                null,
                OAWebBeanConstants.KEEP_MENU_CONTEXT,
                null,
                null,
                true,
                OAWebBeanConstants.ADD_BREAD_CRUMB_NO
            );
        }
    }
}
`;

  const deploy = `# 1. Copy ${coName}.java to server under $JAVA_TOP/${oafPkg.replace(/\./g, '/')}
# 2. Compile on server:
cd \$JAVA_TOP/${oafPkg.replace(/\./g, '/')}
javac -cp \$CLASSPATH ${coName}.java
`;

  const rollback = `rm -f \$JAVA_TOP/${oafPkg.replace(/\./g, '/')}/${coName}.class`;
  const doc = `# OAF Controller Specification: ${coName}
Package: \`${oafPkg}\`
Application Module: \`${amName}\`
View Object: \`${voName}\`
`;

  renderOutput(`${coName}.java`, java, deploy, rollback, doc);
}

function generateOAFXMLImporter() {
  const oafAppl = document.getElementById('oaf_appl').value.trim();
  const oafPkg = document.getElementById('oaf_pkg').value.trim();
  const pageName = document.getElementById('oaf_page_name').value.trim();

  const mdsPath = `/${oafPkg.replace(/\./g, '/')}/${pageName}.xml`;

  const sh = `#!/bin/bash
# ==============================================================================
# OAF XMLIMPORTER SCRIPT: ${pageName}
# ==============================================================================

export APPS_USER="apps"
export APPS_PWD="\$APPS_PWD"
export DB_HOST="10.100.100.104"
export DB_PORT="1521"
export DB_SID="HRVIS"

echo "=== [1] Importing Page XML into MDS Repository ==="
java oracle.jrad.tools.xml.importer.XMLImporter \\
    \$JAVA_TOP${mdsPath} \\
    -username \$APPS_USER \\
    -password \$APPS_PWD \\
    -dbconnection "(DESCRIPTION=(ADDRESS=(PROTOCOL=tcp)(HOST=\$DB_HOST)(PORT=\$DB_PORT))(CONNECT_DATA=(SID=\$DB_SID)))"

echo "=== [2] Verifying MDS Content in JDR Tables ==="
sqlplus -s apps/\$APPS_PWD <<EOF
SET LINESIZE 160;
SELECT path_name, path_docid 
FROM jdr_paths 
WHERE path_name = '${pageName}';
EOF

echo "=== [3] Clearing OAF Apache/JRAD Cache ==="
# In browser, navigate to Functional Administrator -> Core Services -> Caching Framework -> Clear All Cache
`;

  const rollback = `-- Remove page from MDS
BEGIN
    jdr_utils.deletedocument('${mdsPath.replace('.xml', '')}');
    COMMIT;
END;
/
`;

  renderOutput(`import_${pageName}.sh`, sh, sh, rollback, `XMLImporter documentation for ${pageName}`);
}

function generateOACoreBounceSteps() {
  const sh = `#!/bin/bash
# ==============================================================================
# OACORE SAFE RESTART & CACHE PURGE SCRIPT
# ==============================================================================
# Use when deploying new OAF Controllers, BC4J substitutions, or JAR files.
# ==============================================================================

echo "=== 1. Checking OACORE Service Status ==="
\$ADMIN_SCRIPTS_HOME/adoacorectl.sh status

echo "=== 2. Gracefully Stopping OACORE ==="
\$ADMIN_SCRIPTS_HOME/adoacorectl.sh stop

echo "=== 3. Purging JSP and Cabo Web Caches ==="
# Remove compiled JSP classes
if [ -d "\$COMMON_TOP/_pages" ]; then
    echo "Purging \$COMMON_TOP/_pages..."
    rm -rf \$COMMON_TOP/_pages/*
fi

# Remove Cabo image caches
if [ -d "\$OA_HTML/cabo/images/cache" ]; then
    echo "Purging Cabo UI image cache..."
    rm -rf \$OA_HTML/cabo/images/cache/*
fi

echo "=== 4. Starting OACORE ==="
\$ADMIN_SCRIPTS_HOME/adoacorectl.sh start

echo "=== 5. Verifying Port Availability ==="
netstat -an | grep 7212
echo "OACORE restart cycle complete."
`;

  renderOutput(`bounce_oacore.sh`, sh, sh, `-- Stop and restart if needed`, `OACORE lifecycle procedure.`);
}

// =========================================================================
// MODULE 6: SQL & PL/SQL GENERATOR
// =========================================================================
function generatePLSQLCode() {
  const objType = document.getElementById('sql_obj_type').value;
  const pkgName = document.getElementById('sql_pkg_name').value.trim();
  const schema = document.getElementById('sql_schema').value.trim() || 'APPS';
  const logic = document.getElementById('sql_requirement').value.trim();

  const code = `/********************************************************************************
 * SCRIPT  : ${pkgName}.sql
 * SCHEMA  : ${schema}
 * TYPE    : ${objType}
 * LOGIC   : ${logic}
 * STANDARD: Oracle EBS R12 Autonomous Transaction & Logging
 ********************************************************************************/

CREATE OR REPLACE PACKAGE ${schema}.${pkgName} AS
    -- Global Constants
    gc_pkg_name CONSTANT VARCHAR2(30) := '${pkgName}';

    -- Main entrypoint
    PROCEDURE process_transaction (
        p_transaction_id IN NUMBER,
        p_user_id        IN NUMBER DEFAULT fnd_global.user_id,
        x_status         OUT NOCOPY VARCHAR2,
        x_message        OUT NOCOPY VARCHAR2
    );

    FUNCTION get_version RETURN VARCHAR2;
END ${pkgName};
/

CREATE OR REPLACE PACKAGE BODY ${schema}.${pkgName} AS

    FUNCTION get_version RETURN VARCHAR2 IS
    BEGIN
        RETURN '1.0.0';
    END get_version;

    PROCEDURE log_message (
        p_module IN VARCHAR2,
        p_msg    IN VARCHAR2
    ) IS
        PRAGMA AUTONOMOUS_TRANSACTION;
    BEGIN
        -- Writes to standard FND logging framework
        IF fnd_log.test(fnd_log.level_statement, gc_pkg_name || '.' || p_module) THEN
            fnd_log.string(fnd_log.level_statement, gc_pkg_name || '.' || p_module, p_msg);
        END IF;
    END log_message;

    PROCEDURE process_transaction (
        p_transaction_id IN NUMBER,
        p_user_id        IN NUMBER DEFAULT fnd_global.user_id,
        x_status         OUT NOCOPY VARCHAR2,
        x_message        OUT NOCOPY VARCHAR2
    ) IS
        l_api_name CONSTANT VARCHAR2(30) := 'process_transaction';
    BEGIN
        x_status := 'S'; -- Success
        x_message := 'Transaction ' || p_transaction_id || ' processed successfully.';

        log_message(l_api_name, 'Processing transaction ' || p_transaction_id || ' for user ' || p_user_id);

        -- TODO: Implement business processing logic here
        -- ${logic.replace(/\n/g, ' ')}

    EXCEPTION
        WHEN OTHERS THEN
            x_status := 'E';
            x_message := 'Error in ' || gc_pkg_name || '.' || l_api_name || ': ' || SQLERRM;
            log_message(l_api_name, 'EXCEPTION: ' || SQLERRM || ' | Trace: ' || DBMS_UTILITY.FORMAT_ERROR_BACKTRACE);
    END process_transaction;

END ${pkgName};
/
SHOW ERRORS;
`;

  const deploy = `sqlplus apps/\$APPS_PWD @${pkgName}.sql`;
  const rollback = `DROP PACKAGE ${schema}.${pkgName};`;
  const doc = `# Specification: ${pkgName}\nSchema: \`${schema}\`\nType: \`${objType}\``;

  renderOutput(`${pkgName}.sql`, code, deploy, rollback, doc);
}

function generateApiInvokerCode() {
  const apiSelect = document.getElementById('sql_api_select').value;
  const pkgName = document.getElementById('sql_pkg_name').value.trim();

  let apiCall = '';
  if (apiSelect.includes('ABSENCE')) {
    apiCall = `
    -- Initialize EBS environment
    fnd_global.apps_initialize(
        user_id      => 1001,
        resp_id      => 50555,
        resp_appl_id => 800
    );

    hr_person_absence_api.create_person_absence (
        p_validate                    => FALSE,
        p_effective_date              => TRUNC(SYSDATE),
        p_person_id                   => l_person_id,
        p_business_group_id           => l_bg_id,
        p_absence_attendance_type_id  => l_absence_type_id,
        p_date_start                  => TRUNC(SYSDATE),
        p_date_end                    => TRUNC(SYSDATE),
        p_absence_attendance_id       => l_absence_attendance_id,
        p_object_version_number       => l_ovn,
        p_occurrence                  => l_occurrence,
        p_dur_dys_less_warning        => l_warning
    );
`;
  } else if (apiSelect.includes('CREATEUSER')) {
    apiCall = `
    fnd_user_pkg.createuser (
        x_user_name            => 'JOHN.DOE',
        x_owner                => 'SEED',
        x_unencrypted_password => 'Welcome123',
        x_email                => 'john.doe@company.com'
    );
`;
  } else {
    apiCall = `
    hr_employee_api.create_us_employee (
        p_validate          => FALSE,
        p_hire_date         => TRUNC(SYSDATE),
        p_business_group_id => l_bg_id,
        p_last_name         => 'DOE',
        p_sex               => 'M',
        p_person_type_id    => l_person_type_id,
        p_person_id         => l_person_id,
        p_assignment_id     => l_assignment_id,
        p_per_object_version_number => l_ovn,
        p_asg_object_version_number => l_asg_ovn,
        p_per_effective_start_date  => l_start_date,
        p_per_effective_end_date    => l_end_date,
        p_full_name                 => l_full_name,
        p_per_comment_id            => l_comment_id,
        p_assignment_sequence       => l_asg_seq,
        p_name_combination_warning  => l_warn,
        p_assign_payroll_warning    => l_warn2
    );
`;
  }

  const code = `/********************************************************************************
 * SCRIPT: invoke_${apiSelect.toLowerCase().replace(/[^a-z0-9_]/g, '_')}.sql
 * PURPOSE: Wrapper to invoke Oracle Public API ${apiSelect}
 ********************************************************************************/
SET SERVEROUTPUT ON SIZE 1000000;

DECLARE
    l_person_id               NUMBER := 1001;
    l_bg_id                   NUMBER := 204;
    l_absence_type_id         NUMBER := 61;
    l_absence_attendance_id   NUMBER;
    l_ovn                     NUMBER;
    l_occurrence              NUMBER;
    l_warning                 BOOLEAN;
BEGIN
    DBMS_OUTPUT.PUT_LINE('=== [START] Invoking API: ${apiSelect} ===');

${apiCall}

    COMMIT;
    DBMS_OUTPUT.PUT_LINE('=== [SUCCESS] Public API executed successfully! ===');
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        DBMS_OUTPUT.PUT_LINE('âŒ API Execution Failed: ' || SQLERRM);
        -- Display FND Message Stack
        FOR i IN 1..fnd_msg_pub.count_msg LOOP
            DBMS_OUTPUT.PUT_LINE('FND MSG [' || i || ']: ' || fnd_msg_pub.get(i, fnd_api.g_false));
        END LOOP;
        RAISE;
END;
/
`;

  renderOutput(`invoke_${apiSelect.toLowerCase().replace(/[^a-z0-9_]/g, '_')}.sql`, code, `-- Run wrapper\nsqlplus apps/\$APPS_PWD @script.sql`, `-- Rollback via API delete procedures`, `API documentation.`);
}

// =========================================================================
// UTILITY FUNCTIONS: CLIPBOARD & DOWNLOAD
// =========================================================================
function copyOutputToClipboard() {
  const content = state.outputData[state.activeOutputTab] || '';
  if (!content) {
    alert('No content to copy.');
    return;
  }

  navigator.clipboard.writeText(content).then(() => {
    alert('âœ“ Content copied to clipboard!');
  }).catch(() => {
    // Fallback
    const textarea = document.createElement('textarea');
    textarea.value = content;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    alert('âœ“ Content copied to clipboard!');
  });
}

function downloadOutputFile() {
  const content = state.outputData[state.activeOutputTab] || '';
  if (!content) {
    alert('No content to download.');
    return;
  }

  let extension = '.sql';
  if (state.activeOutputTab === 'deploy') extension = '.sh';
  else if (state.activeOutputTab === 'doc') extension = '.md';
  else if (state.outputData.fileName) {
    const parts = state.outputData.fileName.split('.');
    if (parts.length > 1) extension = '.' + parts[parts.length - 1];
  }

  const baseName = state.outputData.fileName ? state.outputData.fileName.split('.')[0] : 'output';
  const finalFileName = `${baseName}_${state.activeOutputTab}${extension}`;

  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = finalFileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// =========================================================================
// LIVE DEPLOYMENT & EBS EXECUTION ENGINE
// =========================================================================
// If loaded via file:// protocol, target localhost:8855 explicitly
const API_BASE = window.location.protocol === 'file:' ? 'http://localhost:8855' : '';

// ── File Upload Handlers ──
function handleRdfFileChange(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(e) {
    const raw = e.target.result;
    const b64 = raw.includes(',') ? raw.split(',')[1] : raw;
    state.uploadedRdf = { name: file.name, b64: b64 };
    const label = document.getElementById('rdf_selected_filename');
    if (label) label.textContent = `✅ Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
  };
  reader.readAsDataURL(file);
}

function handleRtfFileChange(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(e) {
    const raw = e.target.result;
    const b64 = raw.includes(',') ? raw.split(',')[1] : raw;
    state.uploadedRtf = { name: file.name, b64: b64 };
    const label = document.getElementById('rtf_selected_filename');
    if (label) label.textContent = `✅ Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
  };
  reader.readAsDataURL(file);
}

async function testEBSConnection() {
  const targetPill = document.getElementById('targetInstance');
  const originalHtml = targetPill.innerHTML;
  targetPill.innerHTML = '<span class="status-dot warning"></span><span class="status-text">Checking EBS...</span>';

  try {
    const res = await fetch(`${API_BASE}/api/status`);
    const data = await res.json();
    if (data.connected) {
      targetPill.innerHTML = '<span class="status-dot online"></span><span class="status-text">HRVIS (Connected)</span>';
      alert(`✅ CONNECTED TO ORACLE EBS:

• Instance: ${data.instance}
• Host: ${data.host}
• User: ${data.user}

Status: Online & Ready to receive deployments.`);
    } else {
      targetPill.innerHTML = '<span class="status-dot error"></span><span class="status-text">HRVIS (Offline)</span>';
      alert(`❌ EBS CONNECTION FAILED:

${data.error || 'Unknown error'}`);
    }
  } catch (err) {
    targetPill.innerHTML = originalHtml;
    alert(`⚠️ Could not reach local MCP Gateway at ${API_BASE || 'http://localhost:8855'}/api/status.

Please ensure server_launcher.py is running:
python ui/server_launcher.py`);
  }
}

function closeDeployModal() {
  const modal = document.getElementById('deployModal');
  modal.classList.add('hidden');
}

// ── Generic Deployment Executor ──
async function executeDeploymentPayload(payload) {
  if (state.currentEnv === 'PROD') {
    const ok = confirm(`⚠️ CRITICAL SAFETY WARNING:\nYou have selected the PRODUCTION environment!\n\nExecuting this script will alter live Oracle EBS objects.\nDo you have an approved MD120 and want to proceed?`);
    if (!ok) return;
    payload.confirm_prod = true;
  }

  const modal = document.getElementById('deployModal');
  const modalEnv = document.getElementById('deployModalEnv');
  const modalObj = document.getElementById('deployModalObject');
  const spinner = document.getElementById('deploySpinner');
  const progressText = document.getElementById('deployProgressText');
  const outputLog = document.getElementById('deployOutputLog');
  const verifyBox = document.getElementById('deployVerifyBox');
  const verifyLog = document.getElementById('deployVerifyLog');

  const objName = payload.object_name || 'EBS_OBJECT';
  modalEnv.textContent = state.currentEnv;
  modalObj.textContent = `${payload.object_type.toUpperCase()}: ${objName}`;
  spinner.style.display = 'block';
  progressText.textContent = `Deploying ${objName} to Oracle EBS HRVIS (10.100.100.104)...`;
  outputLog.textContent = 'Connecting via SSH and applying to Oracle EBS...\nPlease wait...';
  verifyBox.classList.add('hidden');
  modal.classList.remove('hidden');

  try {
    const response = await fetch(`${API_BASE}/api/deploy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const result = await response.json();
    spinner.style.display = 'none';

    if (result.success) {
      progressText.innerHTML = `<strong style="color: #10b981;">✅ DEPLOYMENT SUCCEEDED!</strong> Successfully applied to Oracle EBS instance HRVIS.`;
      outputLog.textContent = result.output || 'Procedure completed successfully.';
      
      if (result.verified) {
        verifyBox.classList.remove('hidden');
        verifyLog.textContent = result.verified;
      }
    } else {
      progressText.innerHTML = `<strong style="color: #ef4444;">❌ DEPLOYMENT FAILED</strong> (See details below)`;
      outputLog.textContent = (result.output || '') + '\n\n[ERROR DETAILS]:\n' + (result.error || result.stderr || 'Execution failed.');
    }
  } catch (e) {
    spinner.style.display = 'none';
    progressText.innerHTML = `<strong style="color: #ef4444;">⚠️ GATEWAY SERVER OFFLINE:</strong> Could not connect to deployment API.`;
    outputLog.textContent = `Error: ${e.message}\n\nPlease ensure server_launcher.py is running on http://localhost:8855.`;
  }
}

// ── Per-Module Direct Deployment Functions ──
async function deployConcurrentDirectly() {
  generateConcurrentScript();
  const cpShort = document.getElementById('cp_short_name')?.value.trim() || 'XX_CONCURRENT';
  await executeDeploymentPayload({
    script: state.outputData.code,
    object_name: cpShort,
    object_type: 'concurrent',
    app_short: document.getElementById('cp_appl')?.value.trim() || 'PER',
    env: state.currentEnv
  });
}

async function deployRdfToServer() {
  const repShort = document.getElementById('rep_short_name')?.value.trim() || 'XX_REPORT';
  const appShort = document.getElementById('rep_appl')?.value.trim() || 'PER';
  
  let b64 = state.uploadedRdf?.b64 || '';
  let fname = state.uploadedRdf?.name || `${repShort}.rdf`;

  await executeDeploymentPayload({
    script: `-- Deploy RDF for ${repShort}`,
    object_name: repShort,
    object_type: 'rdf',
    app_short: appShort,
    file_name: fname,
    file_content: b64,
    env: state.currentEnv
  });
}

async function deployRtfToEBS() {
  const repShort = document.getElementById('rep_short_name')?.value.trim() || 'XX_REPORT';
  const appShort = document.getElementById('rep_appl')?.value.trim() || 'PER';

  let b64 = '';
  let fname = `${repShort}.rtf`;
  if (state.uploadedRtf?.b64) {
    b64 = state.uploadedRtf.b64;
    fname = state.uploadedRtf.name;
  } else {
    generateRtfTemplate();
    const rtfText = state.outputData.code;
    b64 = btoa(unescape(encodeURIComponent(rtfText)));
  }

  await executeDeploymentPayload({
    script: `-- Deploy RTF for ${repShort}`,
    object_name: repShort,
    object_type: 'rtf',
    app_short: appShort,
    file_name: fname,
    template_code: repShort,
    file_content: b64,
    env: state.currentEnv
  });
}

/**
 * One-Click Hybrid Report Build & Deployment:
 *   1. Deploys genuine binary .rdf (ROS.60050) to $PER_TOP & $AU_TOP (chmod 755)
 *   2. Registers FND Executable for 'Oracle Reports'
 *   3. Registers Concurrent Program with Output Type = XML, Parameters with Tokens, & Request Group
 *   4. Registers BI Publisher RTF Template in XDO_DS_DEFINITIONS, XDO_TEMPLATES & XDO_LOBS
 *   5. Verifies data dictionary registration in real-time
 */
async function deployHybridReportToEBS() {
  const repShort = document.getElementById('rep_short_name')?.value.trim() || 'XX_EMP_ABS_REP';
  const repName  = document.getElementById('rep_name')?.value.trim() || `${repShort} Report`;
  const appShort = document.getElementById('rep_appl')?.value.trim() || 'PER';
  const reqGroup = document.getElementById('rep_req_group')?.value.trim() || 'HR Reports and Processes';
  const repSql   = document.getElementById('rep_sql')?.value.trim() || '';

  // Parse columns dynamically from the active SQL query
  const columns = parseSqlColumns(repSql);

  // Read parameters from UI table
  const params = [];
  const rows = document.querySelectorAll('#rep-params-body tr');
  rows.forEach((tr, idx) => {
    const seq    = parseInt(tr.querySelector('.seq')?.value || (idx + 1) * 10);
    const name   = tr.querySelector('.param-name')?.value.trim();
    const prompt = tr.querySelector('.param-prompt')?.value.trim() || name;
    const vset   = tr.querySelector('.param-vset')?.value.trim() || '70 Characters';
    const req    = tr.querySelector('.param-req')?.value || 'N';
    if (name) {
      params.push({ seq, name, prompt, vset, req, token: name });
    }
  });

  // Check if custom RTF file selected, or generate standard RTF template
  let rtfB64 = null;
  if (state.uploadedRtf?.b64) {
    rtfB64 = state.uploadedRtf.b64;
  } else {
    generateRtfTemplate();
    const rtfText = state.outputData.code;
    if (rtfText) {
      rtfB64 = btoa(unescape(encodeURIComponent(rtfText)));
    }
  }

  const payload = {
    object_name: repShort,
    rep_short_name: repShort,
    rep_name: repName,
    app_short: appShort,
    req_group: reqGroup,
    object_type: 'hybrid_report',
    file_content: rtfB64,
    sql: repSql,
    columns: columns,
    params: params,
    env: state.currentEnv
  };

  await executeDeploymentPayload(payload);
}

function downloadSampleXmlOnly() {
  const repShort = document.getElementById('rep_short_name')?.value.trim() || 'XX_REPORT';
  const repSql   = document.getElementById('rep_sql')?.value.trim() || '';
  const columns  = parseSqlColumns(repSql);
  const params   = parseSqlParameters(repSql);

  const xmlContent = generateSampleXmlFromColumns(repShort, columns, params);

  const blob = new Blob([xmlContent], { type: 'application/xml;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href  = url;
  link.download = `${repShort}_sample_data.xml`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);

  const statsEl = document.getElementById('outputStats');
  if (statsEl) {
    statsEl.textContent = `✅ Downloaded: ${repShort}_sample_data.xml (${columns.length} columns: ${columns.join(', ')}) — Load into MS Word via BI Publisher > Sample XML`;
  }
}

async function deployReportPackageToEBS() {
  generateReportPackage();
  const repShort = document.getElementById('rep_short_name')?.value.trim() || 'XX_REPORT';
  const appShort = document.getElementById('rep_appl')?.value.trim() || 'PER';
  const repName = document.getElementById('rep_name')?.value.trim() || repShort;
  const repFormat = document.getElementById('rep_output_format')?.value === 'PDF' ? 'PDF' : 'XML';

  const combinedScript = `${state.outputData.code}

-- Register Executable and Program
BEGIN
  IF fnd_program.executable_exists(executable_short_name => '${repShort}_EXEC', application => '${appShort}') THEN
    fnd_program.delete_executable(executable_short_name => '${repShort}_EXEC', application => '${appShort}');
  END IF;

  fnd_program.executable(
    executable          => '${repShort} Executable',
    application         => '${appShort}',
    short_name          => '${repShort}_EXEC',
    description         => '${repShort} Report Executable',
    execution_method    => 'Oracle Reports',
    execution_file_name => '${repShort}',
    language_code       => 'US'
  );

  IF fnd_program.program_exists(program => '${repShort}', application => '${appShort}') THEN
    fnd_program.delete_program(program_short_name => '${repShort}', application => '${appShort}');
  END IF;

  fnd_program.register(
    program                => '${repName}',
    application            => '${appShort}',
    enabled                => 'Y',
    short_name             => '${repShort}',
    description            => '${repShort} Report',
    executable_short_name  => '${repShort}_EXEC',
    executable_application => '${appShort}',
    save_output            => 'Y',
    output_type            => '${repFormat}'
  );
  COMMIT;
  DBMS_OUTPUT.PUT_LINE('[OK] Report Concurrent Program and Executable registered: ${repShort}');
END;
/
`;

  await executeDeploymentPayload({
    script: combinedScript,
    object_name: repShort,
    object_type: 'concurrent',
    app_short: appShort,
    env: state.currentEnv
  });
}

async function deployWorkflowDirectly() {
  generateWorkflowDefinitionScript();
  const itemType = document.getElementById('wf_item_type')?.value.trim() || 'XXHRWF';
  await executeDeploymentPayload({
    script: state.outputData.code,
    object_name: itemType,
    object_type: 'workflow',
    env: state.currentEnv
  });
}

async function deployAlertDirectly() {
  generateAlertScripts();
  const alrName = document.getElementById('alr_name')?.value.trim() || 'XX_ALERT';
  const alrAppl = document.getElementById('alr_appl')?.value.trim() || 'PER';
  const alrType = document.getElementById('alr_type')?.value || 'E';
  const alrTable = document.getElementById('alr_table')?.value.trim() || 'PER_ALL_ASSIGNMENTS_F';
  await executeDeploymentPayload({
    script: state.outputData.code,
    object_name: alrName,
    object_type: 'alert',
    app_short: alrAppl,
    alert_type: alrType,
    table_name: alrTable,
    env: state.currentEnv
  });
}

async function deployOafPageDirectly() {
  generateOAFPageXML();
  const pageName = document.getElementById('oaf_page_name')?.value.trim() || 'EmpDetailsPG';
  const pkgPath = document.getElementById('oaf_pkg')?.value.trim() || 'xxcus.oracle.apps.per.employee.webui';
  await executeDeploymentPayload({
    script: state.outputData.code,
    object_name: pageName,
    object_type: 'oaf',
    pkg_path: pkgPath,
    env: state.currentEnv
  });
}

async function deploySqlDirectly() {
  generatePLSQLCode();
  const pkgName = document.getElementById('sql_pkg_name')?.value.trim() || 'XX_PACKAGE';
  await executeDeploymentPayload({
    script: state.outputData.code,
    object_name: pkgName,
    object_type: 'sql',
    env: state.currentEnv
  });
}

// ── Main Deploy Button Handler (routes by active module and content) ──
async function deployCurrentScriptToEBS(isRetry = false) {
  const mod = state.currentModule;
  const fileName = state.outputData.fileName || '';

  if (mod === 'concurrent') {
    await deployConcurrentDirectly();
  } else if (mod === 'report') {
    if (fileName.endsWith('.rtf')) {
      await deployRtfToEBS();
    } else if (fileName.includes('rdf')) {
      await deployRdfToServer();
    } else {
      await deployReportPackageToEBS();
    }
  } else if (mod === 'workflow') {
    await deployWorkflowDirectly();
  } else if (mod === 'alert') {
    await deployAlertDirectly();
  } else if (mod === 'oaf') {
    if (fileName.endsWith('.xml')) {
      await deployOafPageDirectly();
    } else {
      await deploySqlDirectly();
    }
  } else if (mod === 'sql') {
    await deploySqlDirectly();
  } else {
    const scriptToDeploy = state.outputData.code || state.outputData[state.activeOutputTab];
    await executeDeploymentPayload({
      script: scriptToDeploy,
      object_name: 'SQL_SCRIPT',
      object_type: 'sql',
      env: state.currentEnv
    });
  }
}


// =========================================================================
// REPORT: DIRECT FILE DOWNLOADS (RTF & RDF)
// =========================================================================

/**
 * Generates the RTF layout template and immediately triggers file downloads
 * for BOTH the .rtf template and the companion .xml sample data file.
 */
function generateAndDownloadRtf() {
  generateRtfTemplate(); // renders content into state.outputData.code

  const repShort = document.getElementById('rep_short_name')?.value.trim() || 'XX_REPORT';
  const repSql   = document.getElementById('rep_sql')?.value.trim() || '';
  const content  = state.outputData.code;
  if (!content) {
    alert('No RTF content generated. Please fill the Report fields.');
    return;
  }

  // 1. Download RTF layout matching SQL query columns
  const blob = new Blob([content], { type: 'application/rtf' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `${repShort}.rtf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  // 2. Download Companion Sample XML data generated dynamically from SQL columns
  const columns = parseSqlColumns(repSql);
  const params  = parseSqlParameters(repSql);
  const xmlContent = generateSampleXmlFromColumns(repShort, columns, params);

  setTimeout(() => {
    const xmlBlob = new Blob([xmlContent], { type: 'application/xml;charset=utf-8' });
    const xmlUrl  = URL.createObjectURL(xmlBlob);
    const linkXml = document.createElement('a');
    linkXml.href  = xmlUrl;
    linkXml.download = `${repShort}_sample_data.xml`;
    document.body.appendChild(linkXml);
    linkXml.click();
    document.body.removeChild(linkXml);
    URL.revokeObjectURL(xmlUrl);
  }, 400);

  const statsEl = document.getElementById('outputStats');
  if (statsEl) {
    statsEl.textContent = `✅ Downloaded: ${repShort}.rtf + ${repShort}_sample_data.xml (${columns.length} columns: ${columns.join(', ')}) — Open in MS Word with BI Publisher Desktop Add-in`;
  }
}

/**
 * Downloads a genuine, valid binary Oracle Reports (.rdf) file (ROS.60050)
 * compiled dynamically from the SQL query on EBS or serving template,
 * along with the companion SQL spec file.
 */
async function generateAndDownloadRdf() {
  generateRdfSpecs(); // renders content into state.outputData

  const repShort    = document.getElementById('rep_short_name')?.value.trim() || 'XX_REPORT';
  const repAppl     = document.getElementById('rep_appl')?.value.trim() || 'PER';
  const repSql      = document.getElementById('rep_sql')?.value.trim() || '';
  const specContent = state.outputData.code;
  const columns     = parseSqlColumns(repSql);

  const statsEl = document.getElementById('outputStats');
  if (statsEl) {
    statsEl.textContent = `⏳ Compiling genuine binary .rdf on EBS server (${columns.length} columns via rwconverter.sh)...`;
  }

  // 1. Fetch genuine binary .rdf compiled dynamically from SQL query
  try {
    const res = await fetch('/api/download_rdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: repShort,
        sql: repSql,
        app: repAppl
      })
    });

    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${repShort}.rdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      if (statsEl) {
        statsEl.textContent = `✅ Downloaded: ${repShort}.rdf (${blob.size.toLocaleString()} bytes binary ROS.60050, ${columns.length} columns) + ${repShort}_rdf_spec.sql`;
      }
    } else {
      throw new Error(`Server returned status ${res.status}`);
    }
  } catch (err) {
    console.warn('POST download failed, using fallback link:', err);
    const linkRdf = document.createElement('a');
    linkRdf.href = `/api/download_rdf?name=${encodeURIComponent(repShort)}&sql=${encodeURIComponent(repSql)}&app=${encodeURIComponent(repAppl)}`;
    linkRdf.download = `${repShort}.rdf`;
    document.body.appendChild(linkRdf);
    linkRdf.click();
    document.body.removeChild(linkRdf);
  }

  // 2. Download SQL spec companion after slight delay
  if (specContent) {
    setTimeout(() => {
      const blob1 = new Blob([specContent], { type: 'text/plain;charset=utf-8' });
      const url1  = URL.createObjectURL(blob1);
      const a1    = document.createElement('a');
      a1.href     = url1;
      a1.download = `${repShort}_rdf_spec.sql`;
      document.body.appendChild(a1);
      a1.click();
      document.body.removeChild(a1);
      URL.revokeObjectURL(url1);
    }, 400);
  }
}


// =========================================================================
// WORKFLOW: COMBINED DEFINITION + LAUNCH BUNDLE (Fixes ORA-20002)
// =========================================================================

/**
 * Generates a single Oracle EBS Workflow script that:
 *  1. Registers Item Type + Process Activity in WF_ tables (idempotent)
 *  2. Launches the Workflow process via wf_engine.CreateProcess / StartProcess
 *
 * This prevents ORA-20002 "Activity not found" which occurs when
 * wf_engine.StartProcess is called before the definition is registered.
 */
function generateWorkflowFullBundle() {
  const itemType    = document.getElementById('wf_item_type').value.trim();
  const displayName = document.getElementById('wf_display_name').value.trim();
  const processName = document.getElementById('wf_process_name').value.trim();
  const pkgName     = document.getElementById('wf_pkg_name').value.trim();
  const timeout     = document.getElementById('wf_timeout').value.trim() || '48';

  if (!itemType || !processName) {
    alert('Please fill in Item Type and Process Name before generating the bundle.');
    return;
  }

  const code =
`/******************************************************************************
 * ORACLE WORKFLOW - COMBINED DEFINITION + LAUNCH BUNDLE (WF_LOAD Method)
 * ITEM TYPE : ${itemType}
 * PROCESS   : ${processName}
 * PACKAGE   : ${pkgName}
 *
 * FIXES:
 *   - ORA-12899: PERSISTENCE_TYPE too large â†’ uses 'TEMP' not 'TEMPORARY'
 *   - ORA-00904: DEFAULT_VALUE â†’ uses TEXT_DEFAULT/NUMBER_DEFAULT
 *   - ORA-20002: Activity not found â†’ registers via WF_LOAD before wf_engine
 *   - Workflow Builder compatibility â†’ WF_LOAD syncs with wfbuilder
 *
 * USAGE: sqlplus apps/$APPS_PWD @${itemType.toLowerCase()}_wf_bundle.sql
 ******************************************************************************/
SET SERVEROUTPUT ON SIZE 1000000;
SET DEFINE OFF;

DECLARE
    l_item_type    VARCHAR2(8)   := '${itemType}';
    l_display_name VARCHAR2(80)  := '${displayName}';
    l_process_name VARCHAR2(30)  := '${processName}';
    l_description  VARCHAR2(240) := '${displayName} Approval Workflow';
    l_item_key     VARCHAR2(240);
    l_trans_id     NUMBER        := 1001;
    l_owner        VARCHAR2(100) := 'SYSADMIN';
    l_count        NUMBER;
BEGIN

    -- Initialize EBS Applications Context
    fnd_global.apps_initialize(user_id => 0, resp_id => 20420, resp_appl_id => 1);

    DBMS_OUTPUT.PUT_LINE('=================================================================');
    DBMS_OUTPUT.PUT_LINE('[STEP 1] Registering Workflow via WF_LOAD (Builder-compatible)');
    DBMS_OUTPUT.PUT_LINE('=================================================================');

    ---------------------------------------------------------------------------
    -- 1A. Register Item Type via WF_LOAD.UPLOAD_ITEM_TYPE
    --     persistence_type = 'TEMP' (NOT 'TEMPORARY' â€” max 8 chars â†’ ORA-12899)
    ---------------------------------------------------------------------------
    SELECT COUNT(1) INTO l_count FROM apps.wf_item_types WHERE name = l_item_type;
    IF l_count = 0 THEN
        wf_load.upload_item_type(
            x_name              => l_item_type,
            x_display_name      => l_display_name,
            x_description       => l_description,
            x_protect_level     => 20,
            x_custom_level      => 20,
            x_wf_selector       => NULL,
            x_read_role         => NULL,
            x_write_role        => NULL,
            x_execute_role      => NULL,
            x_persistence_type  => 'TEMP',
            x_persistence_days  => ${timeout}
        );
        DBMS_OUTPUT.PUT_LINE('  [OK] Item Type registered via WF_LOAD: ' || l_item_type);
    ELSE
        DBMS_OUTPUT.PUT_LINE('  [SKIP] Item Type already exists: ' || l_item_type);
    END IF;

    ---------------------------------------------------------------------------
    -- 1B. Register Process/Activity via WF_LOAD.UPLOAD_ACTIVITY
    --     CRITICAL: Process must be in WF_ACTIVITIES before wf_engine.CreateProcess
    ---------------------------------------------------------------------------
    SELECT COUNT(1) INTO l_count
    FROM apps.wf_activities
    WHERE item_type = l_item_type AND name = l_process_name AND type = 'PROCESS';
    IF l_count = 0 THEN
        wf_load.upload_activity(
            x_item_type         => l_item_type,
            x_name              => l_process_name,
            x_display_name      => l_display_name || ' Process',
            x_description       => l_description,
            x_type              => 'PROCESS',
            x_rerun             => 'RESET',
            x_protect_level     => 20,
            x_custom_level      => 20,
            x_effective_date    => SYSDATE - 1,
            x_cost              => 0,
            x_error_item_type   => 'WFERROR',
            x_error_process     => 'DEFAULT_ERROR',
            x_function          => NULL,
            x_function_type     => NULL,
            x_result_type       => '#NULL',
            x_icon_name         => 'PROCESS.ICO',
            x_message           => NULL,
            x_expand_roles      => 'N',
            x_event_filter      => NULL,
            x_direction         => NULL
        );
        DBMS_OUTPUT.PUT_LINE('  [OK] Process Activity registered: ' || l_process_name);
    ELSE
        DBMS_OUTPUT.PUT_LINE('  [SKIP] Process Activity already exists: ' || l_process_name);
    END IF;

    ---------------------------------------------------------------------------
    -- 1C. Register Item Attributes via WF_LOAD.UPLOAD_ITEM_ATTRIBUTE
    --     (no DEFAULT_VALUE â†’ uses x_default parameter correctly)
    ---------------------------------------------------------------------------
    BEGIN
        wf_load.upload_item_attribute(
            x_item_type      => l_item_type,
            x_name           => 'TRANSACTION_ID',
            x_display_name   => 'Transaction ID',
            x_description    => 'Unique transaction identifier for this workflow instance',
            x_sequence       => 10,
            x_type           => 'VARCHAR2',
            x_subtype        => 'SEND',
            x_format         => NULL,
            x_default        => TO_CHAR(l_trans_id),
            x_protect_level  => 20,
            x_custom_level   => 20
        );
        DBMS_OUTPUT.PUT_LINE('  [OK] Attribute TRANSACTION_ID registered.');
    EXCEPTION WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('  [SKIP] TRANSACTION_ID: ' || SQLERRM);
    END;

    BEGIN
        wf_load.upload_item_attribute(
            x_item_type      => l_item_type,
            x_name           => 'APPROVER_ROLE',
            x_display_name   => 'Approver Role',
            x_description    => 'Oracle Workflow Role of the approver',
            x_sequence       => 20,
            x_type           => 'ROLE',
            x_subtype        => 'SEND',
            x_format         => NULL,
            x_default        => l_owner,
            x_protect_level  => 20,
            x_custom_level   => 20
        );
        DBMS_OUTPUT.PUT_LINE('  [OK] Attribute APPROVER_ROLE registered.');
    EXCEPTION WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('  [SKIP] APPROVER_ROLE: ' || SQLERRM);
    END;

    BEGIN
        wf_load.upload_item_attribute(
            x_item_type      => l_item_type,
            x_name           => 'EMP_NAME',
            x_display_name   => 'Employee Name',
            x_description    => 'Full name of the employee in approval request',
            x_sequence       => 30,
            x_type           => 'VARCHAR2',
            x_subtype        => 'SEND',
            x_format         => NULL,
            x_default        => NULL,
            x_protect_level  => 20,
            x_custom_level   => 20
        );
        DBMS_OUTPUT.PUT_LINE('  [OK] Attribute EMP_NAME registered.');
    EXCEPTION WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('  [SKIP] EMP_NAME: ' || SQLERRM);
    END;

    -- Commit the WF_LOAD registration BEFORE calling wf_engine
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('  [OK] WF_LOAD registration committed.');

    ---------------------------------------------------------------------------
    DBMS_OUTPUT.PUT_LINE('=================================================================');
    DBMS_OUTPUT.PUT_LINE('[STEP 2] Launching Workflow Process Instance via wf_engine');
    ---------------------------------------------------------------------------

    l_item_key := l_item_type || '_' || TO_CHAR(SYSDATE, 'YYYYMMDDHH24MISS') || '_'
                  || TRUNC(DBMS_RANDOM.VALUE(100, 999));
    DBMS_OUTPUT.PUT_LINE('  Item Key: ' || l_item_key);

    -- Create and configure the workflow process instance
    wf_engine.CreateProcess(
        itemtype => l_item_type,
        itemkey  => l_item_key,
        process  => l_process_name
    );
    wf_engine.SetItemUserKey(
        itemtype => l_item_type,
        itemkey  => l_item_key,
        userkey  => 'Transaction #' || l_trans_id
    );
    wf_engine.SetItemAttrText(l_item_type, l_item_key, 'TRANSACTION_ID', TO_CHAR(l_trans_id));
    wf_engine.SetItemAttrText(l_item_type, l_item_key, 'APPROVER_ROLE',  l_owner);
    wf_engine.SetItemAttrText(l_item_type, l_item_key, 'EMP_NAME',       'Test Employee');
    wf_engine.SetItemOwner(
        itemtype => l_item_type,
        itemkey  => l_item_key,
        owner    => l_owner
    );
    wf_engine.StartProcess(
        itemtype => l_item_type,
        itemkey  => l_item_key
    );

    COMMIT;
    DBMS_OUTPUT.PUT_LINE('=================================================================');
    DBMS_OUTPUT.PUT_LINE('[SUCCESS] Workflow Process Launched!');
    DBMS_OUTPUT.PUT_LINE('  Item Key   : ' || l_item_key);
    DBMS_OUTPUT.PUT_LINE('  To verify  : Workflow > Status Monitor > Find Processes');
    DBMS_OUTPUT.PUT_LINE('  Item Type  : ' || l_item_type);
    DBMS_OUTPUT.PUT_LINE('=================================================================');

EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        DBMS_OUTPUT.PUT_LINE('[FATAL] ' || SQLERRM);
        DBMS_OUTPUT.PUT_LINE(DBMS_UTILITY.FORMAT_ERROR_BACKTRACE);
        RAISE;
END;
/

-- Post-run verification query
SET LINESIZE 180;
COL item_type FORMAT A10;
COL item_key  FORMAT A40;
COL begin_date FORMAT A22;
SELECT item_type, item_key, begin_date
FROM apps.wf_items
WHERE item_type = '${itemType}'
ORDER BY begin_date DESC
FETCH FIRST 5 ROWS ONLY;
`;

  const deploy =
`#!/bin/bash
# Run the combined bundle:
sqlplus apps/$APPS_PWD @${itemType.toLowerCase()}_wf_bundle.sql

# Then verify in Workflow Builder:
# 1. Open Oracle Workflow Builder
# 2. Connect â†’ APPS schema
# 3. Item Types â†’ ${itemType} â†’ you should see process: ${processName}
`;

  const rollback =
`-- Abort all instances then remove the WF definition
DECLARE
    l_item_type VARCHAR2(8) := '${itemType}';
BEGIN
    FOR r IN (SELECT item_key FROM apps.wf_items WHERE item_type = l_item_type) LOOP
        wf_engine.AbortProcess(l_item_type, r.item_key);
    END LOOP;
    DELETE FROM apps.wf_item_attributes_tl  WHERE item_type = l_item_type;
    DELETE FROM apps.wf_item_attributes      WHERE item_type = l_item_type;
    DELETE FROM apps.wf_activities_tl        WHERE item_type = l_item_type;
    DELETE FROM apps.wf_activities           WHERE item_type = l_item_type;
    DELETE FROM apps.wf_item_types_tl        WHERE name = l_item_type;
    DELETE FROM apps.wf_item_types           WHERE name = l_item_type;
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('Rollback complete for: ' || l_item_type);
EXCEPTION WHEN OTHERS THEN ROLLBACK; RAISE;
END;
/
`;

  const doc =
`# Workflow Bundle: ${itemType} / ${processName}

## Errors Fixed by This Script
| Error | Root Cause | Fix Applied |
| --- | --- | --- |
| ORA-12899 PERSISTENCE_TYPE | 'TEMPORARY' = 9 chars, max 8 | Uses 'TEMP' via WF_LOAD |
| ORA-00904 DEFAULT_VALUE | Column doesn't exist | WF_LOAD.upload_item_attribute(x_default) |
| ORA-20002 Activity not found | Process not in WF_ACTIVITIES | WF_LOAD.upload_activity() before wf_engine |
| Workflow Builder not showing | Raw INSERTs bypass Builder sync | WF_LOAD package syncs with Builder |

## Verification
- **Workflow Builder**: Connect â†’ Item Types â†’ \`${itemType}\`
- **Status Monitor**: EBS â†’ Workflow â†’ Find Processes â†’ Item Type: \`${itemType}\`
- **SQL**: \`SELECT item_type, item_key FROM apps.wf_items WHERE item_type = '${itemType}';\`
`;

  renderOutput(`${itemType.toLowerCase()}_wf_bundle.sql`, code, deploy, rollback, doc);
}

