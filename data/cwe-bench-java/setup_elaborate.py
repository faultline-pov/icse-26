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

def run_docker_build_with_timeout(build_cmd, timeout_secs):
    # Start the process in a new process group
    process = subprocess.Popen(
        build_cmd,
        preexec_fn=os.setsid,  # Only works on Unix/Linux/Mac
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        stdout, stderr = process.communicate(timeout=timeout_secs)
        return process.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        print(f"Timeout reached, killing docker build (pid={process.pid})...")
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)  # Send SIGTERM to process group
        try:
            # Give it some time to clean up gracefully
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            print("Forcing kill of docker build...")
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            stdout, stderr = process.communicate()

        return -1, stdout, stderr

def append_text(path, text, encoding="utf-8"):
   with path.open("a", encoding=encoding) as f:
       f.write(text)

def hunk_touches_range(hunk_header, start_line, end_line):
    # Example hunk header: @@ -73,7 +73,11 @@
    match = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', hunk_header)
    if not match:
        return False
    start = int(match.group(1))
    length = int(match.group(2) or "1")
    hunk_range = range(start-1, start + length + 1)
    return any(line in hunk_range for line in range(start_line-1, end_line + 2))

def filter_diff(diff, ranges):
    filtered = ""
    current_hunk = []
    print_hunk = False
    inside = False
    for line in diff.splitlines(keepends=True):
        if not inside:
            if line.startswith('--- ') or line.startswith('+++ '):
                inside = True
            else:
                continue
        if line.startswith('@@'):
            if current_hunk and print_hunk:
                filtered += ''.join(current_hunk)
            current_hunk = [line]
            print_hunk = any(hunk_touches_range(line, start, end) for start, end in ranges)
        elif current_hunk:
            current_hunk.append(line)
        else:
            filtered += line  # headers and such
    # print the last hunk if it matched
    if current_hunk and print_hunk:
        filtered += ''.join(current_hunk)
    return filtered

def get_commit_time(project_dir, hash):
    # Get the commit time of the given hash
    result = subprocess.run(["git", "show", "-s", "--format=%ct", hash], cwd=project_dir, stdout=subprocess.PIPE, text=True)
    if result.returncode == 0:
        return int(result.stdout.strip())
    return None

parser = argparse.ArgumentParser()
parser.add_argument("--filter", nargs="+", type=str)
args = parser.parse_args()

cwe_bench_root = Path().cwd().absolute()

all_projects = pd.read_csv("data/project_info.csv")
all_fixes = pd.read_csv("data/fix_info.csv")

project_slugs = list(set(all_projects['project_slug'].tolist()))

selected_slugs = project_slugs.copy()
if args.filter is not None and len(args.filter) > 0:
    selected_slugs = [slug for slug in selected_slugs if any(f in slug for f in args.filter)]

log_file = Path("prepare_prompt.log")
if not log_file.exists():
    log_file.write_text("project_slug,status\n", encoding='utf-8')
    existing_logs = []
else:
    existing_logs = log_file.read_text(encoding='utf-8').strip().split('\n')[1:]
    existing_logs = [line.split(',')[0] for line in existing_logs]

for project_slug in selected_slugs:
    print(f"Project: {project_slug}")
    project_dir = Path(f"workdir/project-sources/{project_slug}").absolute()
    if project_slug in existing_logs:
        print(f"Project {project_slug} already processed. Skipping...")
        continue
    try:
        subprocess.run(["python", "scripts/setup.py", "--filter", project_slug], timeout=600)
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

    # Check that the build script exists
    build_script_path = project_dir / "build-command.sh"
    if not build_script_path.exists():
        print(f"Build script {build_script_path} does not exist in project {project_slug}. Skipping...")
        shutil.rmtree(project_dir)  # Clean up the directory
        append_text(log_file, f"{project_slug},no build script\n", encoding='utf-8')
        continue
    build_script = build_script_path.read_text(encoding='utf-8').strip()
    build_script_path.unlink()

    envvar_path = project_dir / "envvar-setup.sh"
    if not envvar_path.exists():
        print(f"Environment variable setup script {envvar_path} does not exist in project {project_slug}. Skipping...")
        shutil.rmtree(project_dir)
        append_text(log_file, f"{project_slug},no envvar setup script\n", encoding='utf-8')
        continue
    envvar_script = envvar_path.read_text(encoding='utf-8').strip()
    envvar_path.unlink()

    # Filter the all_fixes DataFrame for the current project
    project_fixes = all_fixes[all_fixes['project_slug'] == project_slug]
    commit_hashes = list(set(project_fixes['commit'].tolist()))
    if len(commit_hashes) == 0:
        print("No commit hashes found")
        shutil.rmtree(project_dir)
        append_text(log_file, f"{project_slug},no commit hashes found\n", encoding='utf-8')
        continue
    success = True
    for fix_commit in commit_hashes:
        print(f"Fetching fix commit {fix_commit} in project {project_slug}")
        result = subprocess.run(["git", "fetch", "origin", fix_commit], cwd=project_dir)
        if result.returncode != 0:
            print(f"Failed to fetch fix commit {fix_commit}")
            success = False
            break
    if not success:
        shutil.rmtree(project_dir)
        append_text(log_file, f"{project_slug},failed to fetch fix commit\n", encoding='utf-8')
        continue

    commit_hashes.sort(key=lambda x: get_commit_time(project_dir, x), reverse=True)
    latest_fix_commit = commit_hashes[0]
    current_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project_dir, stdout=subprocess.PIPE, text=True).stdout.strip()
    
    try:
        subprocess.run(f"git stash && git checkout {latest_fix_commit}", cwd=project_dir, check=True, shell=True)
    except subprocess.CalledProcessError:
        print(f"Failed to check out fix commit {latest_fix_commit} for project {project_slug}. Skipping...")
        shutil.rmtree(project_dir)
        append_text(log_file, f"{project_slug},failed to checkout fix commit\n", encoding='utf-8')
        continue
    print(f"Checked out fix commit {latest_fix_commit} for project {project_slug}")
    try:
        result = subprocess.run(["python", "scripts/build_one.py", project_slug], timeout=600)
    except subprocess.TimeoutExpired:
        print(f"Timeout expired while building project {project_slug} at fix commit {latest_fix_commit}. Skipping...")
        shutil.rmtree(project_dir)
        append_text(log_file, f"{project_slug},timeout\n", encoding='utf-8')
        continue
    if result.returncode != 0:
        print(f"Failed to build project {project_slug} at fix commit {latest_fix_commit}. Skipping...")
        shutil.rmtree(project_dir)
        append_text(log_file, f"{project_slug},failed to build at fix commit\n", encoding='utf-8')
        continue
    print(f"Successfully built project {project_slug} at fix commit {latest_fix_commit}")
    
    # Check that the build script exists again
    build_script_path = project_dir / "build-command.sh"
    if not build_script_path.exists():
        print(f"Build script {build_script_path} does not exist in project {project_slug}. Skipping...")
        shutil.rmtree(project_dir)  # Clean up the directory
        append_text(log_file, f"{project_slug},no build script\n", encoding='utf-8')
        continue
    new_build_script = build_script_path.read_text(encoding='utf-8').strip()
    build_script_path.unlink()

    envvar_path = project_dir / "envvar-setup.sh"
    if not envvar_path.exists():
        print(f"Environment variable setup script {envvar_path} does not exist in project {project_slug}. Skipping...")
        shutil.rmtree(project_dir)
        append_text(log_file, f"{project_slug},no envvar setup script\n", encoding='utf-8')
        continue
    new_envvar_script = envvar_path.read_text(encoding='utf-8').strip()
    envvar_path.unlink()

    # Check out the current commit again
    subprocess.run(["git", "checkout", current_commit], cwd=project_dir, check=True)

    files = set(project_fixes['file'])
    fixes = []
    fixed_methods = []
    # Iterate through each fixed file for the project
    for file in files:
        if 'src/test/' in file.lower():
            print(f"Skipping test file {file} in project {project_slug}")
            continue
        # Get the set of rows for the current file
        file_fixes = project_fixes[project_fixes['file'] == file]
        fix_ranges = []
        for _, fix_info in file_fixes.iterrows():
            if isinstance(fix_info['method'], str) and 'test' in fix_info['method'].lower():
                continue
            fixed_methods.append((fix_info['class'], fix_info['method']))
            start_line = fix_info['method_start']
            end_line = fix_info['method_end']
            if (not math.isnan(start_line)) and (not math.isnan(end_line)):
                start_line = int(start_line)
                end_line = int(end_line)
            else:
                start_line = 0
                end_line = int(1e6)  # use a large number to include all lines
            if start_line > end_line:
                continue
            fix_ranges.append((start_line, end_line))

        file_path = project_dir / file
        if not file_path.exists():
            print(f"File {file_path} does not exist in project {project_slug}. Skipping...")
            continue
        relative_path = file_path.relative_to(project_dir)
        
        print("Running command : git diff", current_commit, latest_fix_commit, "--ignore-all-space", "--", relative_path)
        result = subprocess.run(["git", "diff", current_commit, latest_fix_commit, "--ignore-all-space", "--", relative_path], cwd=project_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            fix = filter_diff(result.stdout, fix_ranges)
            if fix.strip():
                fixes += [fix]
        else:
            print("Error:", result.stderr)

    # Write the fixes to a file
    if fixes:
        generated_info_dir = cwe_bench_root / "data" / "processed" / project_slug
        generated_info_dir.mkdir(parents=True, exist_ok=True)
        fix_file_path = generated_info_dir / ".fix.patch"
        with open(fix_file_path, 'w') as fix_file:
            fix_file.write('\n'.join(fixes))
        print(f"Fixes for {project_slug} written to {fix_file_path}")
    else:
        print(f"No fixes found for {project_slug}")
        append_text(log_file, f"{project_slug},failed to create fix\n", encoding='utf-8')
        shutil.rmtree(project_dir)  # Clean up the directory
        continue
    
    if fixed_methods:
        generated_info_dir = cwe_bench_root / "data" / "processed" / project_slug
        generated_info_dir.mkdir(parents=True, exist_ok=True)
        fixed_methods_path = generated_info_dir / ".method_info.csv"
        with open(fixed_methods_path, 'w') as method_file:
            for class_name, method_name in fixed_methods:
                method_file.write(f"{class_name},{method_name}\n")
        print(f"Fixed methods for {project_slug} written to {fixed_methods_path}")
    else:
        print(f"No fixed methods found for {project_slug}")
        append_text(log_file, f"{project_slug},no fixed methods found\n", encoding='utf-8')
        shutil.rmtree(project_dir)  # Clean up the directory
        continue

    # Get the java-env subfolders used in envvar_script
    java_env_subfolders = set()
    for line in envvar_script.splitlines():
        match = re.search(r'java-env/([^/]+)', line)
        if match:
            java_env_subfolders.add(match.group(1))
    copy_instructions = ["COPY ./java-env/{} $WORKSPACE_BASE/java-env/{}".format(subfolder, subfolder) for subfolder in java_env_subfolders]
    copy_instructions = '\n'.join(copy_instructions)

    envvar_lines = envvar_script.splitlines()
    envvar_lines = '\n'.join([line.replace("export", "ENV") for line in envvar_lines if line.strip()])

    dockerfile = f'''FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt -y update
RUN apt install -y curl unzip wget git build-essential
RUN mkdir -p /java-env
ENV WORKSPACE_BASE="/"
{copy_instructions}
{envvar_lines}
ENV PATH=$PATH:$JAVA_HOME/bin
COPY ./project-sources/{project_slug} /project
COPY ./resources/my-agent/target/agent-fat.jar /project/.agent-fat.jar
ENV JAVA_TOOL_OPTIONS="-javaagent:/project/.agent-fat.jar"
WORKDIR /project
# Do not modify anything above this line
RUN {build_script}
'''
    # Write the Dockerfile to a file
    dockerfile_path = project_dir / "Dockerfile.vuln"
    dockerfile_path.write_text(dockerfile, encoding="utf-8")
    (project_dir / ".Dockerfile.backup").write_text(dockerfile, encoding="utf-8")  # backup original Dockerfile
    print(f"Dockerfile for {project_slug} written to {dockerfile_path}")

    # Get the java-env subfolders used in new_envvar_script
    java_env_subfolders = set()
    for line in new_envvar_script.splitlines():
        match = re.search(r'java-env/([^/]+)', line)
        if match:
            java_env_subfolders.add(match.group(1))
    new_copy_instructions = ["COPY ./java-env/{} $WORKSPACE_BASE/java-env/{}".format(subfolder, subfolder) for subfolder in java_env_subfolders]
    new_copy_instructions = '\n'.join(new_copy_instructions)

    new_envvar_lines = new_envvar_script.splitlines()
    new_envvar_lines = '\n'.join([line.replace("export", "ENV") for line in new_envvar_lines if line.strip()])

    new_dockerfile = f'''FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt -y update
RUN apt install -y curl unzip wget git build-essential
RUN mkdir -p /java-env
ENV WORKSPACE_BASE="/"
{new_copy_instructions}
{new_envvar_lines}
ENV PATH=$PATH:$JAVA_HOME/bin
COPY ./project-sources/{project_slug} /project
COPY ./resources/my-agent/target/agent-fat.jar /project/.agent-fat.jar
ENV JAVA_TOOL_OPTIONS="-javaagent:/project/.agent-fat.jar"
WORKDIR /project
# Do not modify anything above this line
RUN {new_build_script}
'''
    dockerfile_diff = list(difflib.unified_diff(
        dockerfile.splitlines(),
        new_dockerfile.splitlines(),
        fromfile='a/Dockerfile.vuln',
        tofile='b/Dockerfile.vuln',
        lineterm=''
    ))
    if len(dockerfile_diff) > 0:
        dockerfile_diff = [
            f'diff --git a/Dockerfile.vuln b/Dockerfile.vuln',
            f'index {hashlib.md5(dockerfile.encode()).hexdigest()}..{hashlib.md5(new_dockerfile.encode()).hexdigest()} 100644',
            f'--- a/Dockerfile.vuln',
            f'+++ b/Dockerfile.vuln',
            *dockerfile_diff[2:]  # Skip the first two lines which are not needed
        ]
    dockerfile_diff = '\n'.join(dockerfile_diff) + '\n' # This extra newline is important for the diff to be valid

    diff_file_path = project_dir / ".build_diff.patch"
    with open(diff_file_path, 'w') as diff_file:
        diff_file.write(dockerfile_diff)
    print(f"Build diff for {project_slug} written to {diff_file_path}")

    subprocess.run("docker rmi -f vulnerability-test && docker image prune -f", shell=True)

    # Build the Docker image
    build_command = f"docker build -f {dockerfile_path} -t vulnerability-test ./workdir"
    print(f"Building Docker image for {project_slug}...")
    return_code, stdout, stderr = run_docker_build_with_timeout(build_command.split(' '), 600)
    if return_code == -1:
        print(f"Timeout expired while building Docker image for {project_slug}. Skipping...")
        shutil.rmtree(project_dir)
        append_text(log_file, f"{project_slug},timeout\n", encoding='utf-8')
        continue
    if return_code > 0:
        print(f"Failed to build Docker image for {project_slug}. Skipping...")
        shutil.rmtree(project_dir)  # Clean up the directory
        append_text(log_file, f"{project_slug},failed to build docker image\n", encoding='utf-8')
        continue
    
    # Reset to fixed state and try to build the Docker image again
    # We need to stash because gradle modifies some files while building and this can block checkout
    subprocess.run(f"git stash && git checkout {latest_fix_commit}", cwd=project_dir, check=True, shell=True)
    print(f"Applying build diff for {project_slug}...")
    result = subprocess.run(["git", "apply", "--allow-empty", "--whitespace=fix", ".build_diff.patch"], cwd=project_dir)
    if result.returncode != 0:
        print(f"Failed to apply build diff for {project_slug}. Skipping...")
        shutil.rmtree(project_dir)
        append_text(log_file, f"{project_slug},failed to apply build diff\n", encoding='utf-8')
        continue
    print(f"Rebuilding Docker image for {project_slug} in fixed state...")
    return_code, stdout, stderr = run_docker_build_with_timeout(build_command.split(' '), 600)
    if return_code == -1:
        print(f"Timeout expired while rebuilding Docker image for {project_slug}. Skipping...")
        shutil.rmtree(project_dir)
        append_text(log_file, f"{project_slug},timeout\n", encoding='utf-8')
        continue
    if return_code > 0:
        print(f"Failed to rebuild Docker image for {project_slug} after applying build diff. Skipping...")
        shutil.rmtree(project_dir)
        append_text(log_file, f"{project_slug},failed to rebuild docker image after applying build diff\n", encoding='utf-8')
        continue
    print(f"Successfully built Docker image for {project_slug} after applying build diff.")
    # Reversing build diff
    print(f"Resetting {project_slug} to vulnerable state...")
    subprocess.run(f"git stash && git checkout {current_commit}", cwd=project_dir, check=True, shell=True)
    result = subprocess.run(["git", "apply", "--allow-empty", "--whitespace=fix", "-R", ".build_diff.patch"], cwd=project_dir)
    if result.returncode != 0:
        print(f"Failed to reverse build diff for {project_slug}. Skipping...")
        shutil.rmtree(project_dir)
        append_text(log_file, f"{project_slug},failed to reverse build diff\n", encoding='utf-8')
        continue
    print(f"Successfully reset {project_slug} to vulnerable state.")

    commit_info = {
        "vulnerable_commit": current_commit,
        "fix_commit": latest_fix_commit,
    }
    generated_info_dir = cwe_bench_root / "data" / "processed" / project_slug
    generated_info_dir.mkdir(parents=True, exist_ok=True)
    commit_info_path = generated_info_dir / ".commit_info.json"
    with open(commit_info_path, 'w') as commit_file:
        json.dump(commit_info, commit_file, indent=4)
    print(f"Commit info for {project_slug} written to {commit_info_path}")
    
    append_text(log_file, f"{project_slug},success\n", encoding='utf-8')