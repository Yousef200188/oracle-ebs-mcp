import os
import time
import subprocess

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUTPUT_DIR = os.path.abspath(r"images_doc")
os.makedirs(OUTPUT_DIR, exist_ok=True)

screens = [
    ("01_dashboard_overview.png", "http://localhost:8855/index.html?tab=concurrent"),
    ("02_concurrent_module.png", "http://localhost:8855/index.html?tab=concurrent"),
    ("03_report_generator.png", "http://localhost:8855/index.html?tab=report"),
    ("04_workflow_manager.png", "http://localhost:8855/index.html?tab=workflow"),
    ("05_alert_manager.png", "http://localhost:8855/index.html?tab=alert"),
    ("06_oaf_studio.png", "http://localhost:8855/index.html?tab=oaf"),
    ("07_sql_plsql_studio.png", "http://localhost:8855/index.html?tab=sql"),
    ("08_production_safety.png", "http://localhost:8855/index.html?tab=concurrent&env=PROD"),
]

for filename, url in screens:
    out_path = os.path.join(OUTPUT_DIR, filename)
    print(f"Capturing: {filename} from {url}...")
    args = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--window-size=1600,1020",
        f"--screenshot={out_path}",
        url
    ]
    res = subprocess.run(args, capture_output=True, text=True, timeout=30)
    time.sleep(1)
    if os.path.exists(out_path):
        size = os.path.getsize(out_path)
        print(f"  [OK] Saved {out_path} ({size:,} bytes)")
    else:
        print(f"  [FAIL] Could not generate {out_path}: {res.stderr}")

print("\nAll screenshots processed!")
