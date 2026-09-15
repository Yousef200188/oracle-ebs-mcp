#!/usr/bin/env python3
"""
Oracle EBS R12 Hybrid Report Automation Script
Builds and deploys in one shot:
  1. Oracle Reports (.rdf) binary deployed to $PER_TOP & $AU_TOP (chmod 755)
  2. FND Executable for 'Oracle Reports'
  3. Concurrent Program configured with Output Type = XML
  4. SRS Parameters registered
  5. Program attached to Request Group
  6. BI Publisher RTF Template registered in XDO_DS_DEFINITIONS, XDO_TEMPLATES, & XDO_LOBS
  7. Verification against Oracle EBS Data Dictionary
"""

import sys, os, argparse, json

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.ebs_executor import deploy_hybrid_report

def main():
    parser = argparse.ArgumentParser(description="Oracle EBS Hybrid Report Builder (RDF + RTF)")
    parser.add_argument("--name", default="XX Employee Details & Absence Report", help="Report User Name")
    parser.add_argument("--short", default="XX_EMP_ABS_REP", help="Report Short Name (Code)")
    parser.add_argument("--app", default="PER", help="Application Short Name (e.g. PER, GL, PO)")
    parser.add_argument("--group", default="HR Reports and Processes", help="Request Group Name")
    parser.add_argument("--rdf-file", default=None, help="Optional path to local binary .rdf file (ROS.60050)")
    parser.add_argument("--rtf-file", default=None, help="Optional path to local .rtf file")
    parser.add_argument("--sql", default=None, help="Optional custom SQL query to compile dynamically")
    parser.add_argument("--sql-file", default=None, help="Optional path to .sql file containing query")
    args = parser.parse_args()

    print("=" * 80)
    print(" ORACLE EBS R12 HYBRID REPORT BUILDER & DEPLOYMENT PIPELINE")
    print("=" * 80)
    print(f" Report Name : {args.name}")
    print(f" Short Name  : {args.short}")
    print(f" Application : {args.app}")
    print(f" Req Group   : {args.group}")
    print("=" * 80)

    sql_text = None
    if args.sql:
        sql_text = args.sql.strip()
    elif args.sql_file and os.path.exists(args.sql_file):
        with open(args.sql_file, "r", encoding="utf-8") as f:
            sql_text = f.read().strip()

    import base64
    rdf_b64 = None
    if args.rdf_file and os.path.exists(args.rdf_file):
        with open(args.rdf_file, "rb") as f:
            rdf_b64 = base64.b64encode(f.read()).decode("ascii")

    rtf_b64 = None
    if args.rtf_file and os.path.exists(args.rtf_file):
        with open(args.rtf_file, "rb") as f:
            rtf_b64 = base64.b64encode(f.read()).decode("ascii")

    payload = {
        "object_name": args.short,
        "rep_name": args.name,
        "rep_short_name": args.short,
        "app_short": args.app,
        "req_group": args.group,
        "rdf_content": rdf_b64,
        "file_content": rtf_b64,
        "sql": sql_text,
        "params": [
            {
                "name": "P_ORG_ID",
                "prompt": "Organization",
                "vset": "HR_ORGANIZATIONS",
                "req": "N",
                "seq": 10
            },
            {
                "name": "P_EFFECTIVE_DATE",
                "prompt": "Effective Date",
                "vset": "FND_STANDARD_DATE",
                "req": "Y",
                "seq": 20
            }
        ]
    }

    result = deploy_hybrid_report(payload)

    print("\n" + result.get("output", ""))
    print("\n" + "=" * 80)
    print(" PIPELINE EXECUTION STATUS:", "[SUCCESS]" if result.get("success") else "[FAILED]")
    print("=" * 80)

    if not result.get("success"):
        sys.exit(1)

if __name__ == "__main__":
    main()
