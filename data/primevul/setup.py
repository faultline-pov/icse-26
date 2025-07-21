import json
import subprocess
import os
from pathlib import Path
import shutil
import re

def extract_function_name(c_code):
    match = re.search(r'([a-zA-Z_]+)\s*\(', c_code)
    if match:
        return match.group(1)
    return None

with open('dataset/primevul_train.jsonl', 'r') as f:
    data = [json.loads(line) for line in f]

# dict_keys(['idx', 'project', 'commit_id', 'project_url', 'commit_url',
#   'commit_message', 'target', 'func', 'func_hash', 'file_name',
#   'file_hash', 'cwe', 'cve', 'cve_desc', 'nvd_url'])

selected_cwes = ['CWE-22', 'CWE-78', 'CWE-79', 'CWE-94']
# These are all massive projects that we have no hope of building
excluded_projects = ['Chrome', 'linux', 'linux-2.6', 'git', 'wpitchoune', 'ceph']

processed_info = {}

count = 0
for item in data:
    if item['target'] == 0:
        # This is a non-vulnerable sample, we can skip it
        continue
    
    if item['cwe'][0] not in selected_cwes or len(item['cwe']) > 1:
        # This is not one of the selected CWEs, we can skip it
        continue

    project_slug = f"{item['project']}_{item['cve']}"
    func_name = extract_function_name(item['func'])
    if project_slug in processed_info:
        print(f"[PrimeVul] Project {project_slug} already processed, skipping.")
        processed_info[project_slug]['vulnerable_funcs'].append({'name': func_name, 'file': item['file_name']})
        continue

    folder_name = f"project-sources/{project_slug}"

    if os.path.exists(folder_name):
        print(f"[PrimeVul] Folder {folder_name} already exists, skipping.")
        continue
    
    if item['project'] in excluded_projects:
        print(f"[PrimeVul] Project {item['project']} is excluded, skipping.")
        continue

    print(f">> [PrimeVul] Cloning repository from `{item['project_url']}`...")
    subprocess.run(["git", "clone", "--depth", "1", item['project_url'], folder_name])

    if not os.path.exists(folder_name):
        print(f"[PrimeVul] Failed to clone repository {item['project_url']}. Skipping.")
        continue

    print(f">> [PrimeVul] Fetching and checking out commit `{item['commit_id']}`...")
    subprocess.run(["git", "fetch", "--depth", "1", "origin", item['commit_id']], cwd=folder_name)
    subprocess.run(["git", "checkout", item['commit_id']], cwd=folder_name)

    print(f">> [PrimeVul] Getting parent commit")
    result = subprocess.run(f"git cat-file -p {item['commit_id']} | awk '/^parent / {{ print $2; exit }}'",
            shell=True, cwd=folder_name, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(f"[PrimeVul] Failed to get parent commit for {item['commit_id']}. Skipping.")
        shutil.rmtree(folder_name)
        continue
        
    parent_commit = result.stdout.decode('utf-8').strip()

    print(f">> [PrimeVul] Fetching and checking out parent commit `{parent_commit}`...")
    subprocess.run(["git", "fetch", "--depth", "1", "origin", parent_commit], cwd=folder_name)
    subprocess.run(["git", "checkout", parent_commit], cwd=folder_name)
    
    dockerfile = """
FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

# Update package lists and install build-essential (which includes gcc, g++, make)
RUN apt-get -y update && \
    apt-get install -y build-essential curl unzip wget && \
    rm -rf /var/lib/apt/lists/*

# Copy the project files into the container
COPY . /project

# Set the working directory inside the container
WORKDIR /project

# Build commands go here
"""
    dockerfile_path = Path(folder_name) / "Dockerfile.vuln"
    dockerfile_path.write_text(dockerfile)

    print(f"[PrimeVul] Project {item['project']} processed successfully.")

    processed_info[project_slug] = {
        'fix_commit' : item['commit_id'],
        'parent_commit': parent_commit,
        'cwe_ids': item['cwe'],
        'cve': item['cve'],
        'cve_desc': item['cve_desc'],
        'vulnerable_funcs': [{'name': func_name, 'file': item['file_name']}]
    }
    with open('processed_info.json', 'w') as f:
        json.dump(processed_info, f, indent=4)

    count += 1
    if count == 40:
        print("[PrimeVul] Processed 40 projects, stopping for now.")
        break
    
