#!/usr/bin/env python3
"""
Run BillDesk app with correct PYTHONPATH (works on Windows and Unix).
Usage: python scripts/run_app.py [args...]
Example: python scripts/run_app.py --resources-dir resources
         python scripts/run_app.py --employee IIIPL-1000_naveen_oct_amex --category commute
"""
import os
import subprocess
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
src = os.path.join(project_root, "src")
app_script = os.path.join(src, "app.py")

env = os.environ.copy()
env["PYTHONPATH"] = src

sys.exit(
    subprocess.run(
        [sys.executable, app_script] + sys.argv[1:],
        cwd=project_root,
        env=env,
    ).returncode
)
