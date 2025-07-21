import pandas as pd
from pathlib import Path
import os
import subprocess
import requests
import random
import math
import shutil
import argparse
import json
import difflib
import hashlib
import signal

import sys
import re

def append_text(path, text, encoding="utf-8"):
   with path.open("a", encoding=encoding) as f:
       f.write(text)

parser = argparse.ArgumentParser()
parser.add_argument("--filter", nargs="+", type=str)
args = parser.parse_args()

cwe_bench_root = Path().cwd().absolute()

project_slugs = [proj.name for proj in (cwe_bench_root / "data" / "processed").iterdir()]

selected_slugs = project_slugs.copy()
if args.filter is not None and len(args.filter) > 0:
    selected_slugs = [slug for slug in selected_slugs if any(f in slug for f in args.filter)]

log_file = Path("setup_projects.log")
if not log_file.exists():
    log_file.write_text("project_slug,status\n", encoding='utf-8')
    existing_logs = []
else:
    existing_logs = log_file.read_text(encoding='utf-8').strip().split('\n')[1:]
    existing_logs = [line.split(',')[0] for line in existing_logs]

for project_slug in selected_slugs:
    print(f"Project: {project_slug}")
    project_dir = Path(f"project-sources/{project_slug}").absolute()
    try:
        subprocess.run(["python", "scripts/setup.py", "--no-build", "--filter", project_slug], timeout=600)
    except subprocess.TimeoutExpired:
        print(f"Timeout expired while setting up project {project_slug}. Skipping...")
        if project_dir.exists():
            shutil.rmtree(project_dir)
        append_text(log_file, f"{project_slug},timeout\n", encoding='utf-8')
        continue
    if not project_dir.exists():
        print(f"Project directory {project_dir} does not exist after setup. Skipping...")
        append_text(log_file, f"{project_slug},failed to setup project dir\n", encoding='utf-8')
        continue

    print(f"Successfully setup project {project_slug}")
    
    # Write the Dockerfile to a file
    dockerfile_path = cwe_bench_root / "data" / "processed" / project_slug / "Dockerfile.vuln"
    if not dockerfile_path.exists():
        print(f"Dockerfile {dockerfile_path} does not exist. Skipping...")
        append_text(log_file, f"{project_slug},dockerfile not found\n", encoding='utf-8')
        continue
    shutil.copy(dockerfile_path, project_dir / "Dockerfile.vuln")
    shutil.copy(dockerfile_path, project_dir / ".Dockerfile.backup")
    print(f"Dockerfile for {project_slug} written to {project_dir / "Dockerfile.vuln"}")

    append_text(log_file, f"{project_slug},success\n", encoding='utf-8')