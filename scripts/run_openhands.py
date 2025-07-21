import json
import argparse
from pathlib import Path
import os
import subprocess
import datetime
import shutil
import signal

def get_issue_details_java(project_name, root_dir='.'):
    advisory_path = Path(root_dir) / "data" / "cwe-bench-java" / "advisory" / f"{project_name}.json"
    if not advisory_path.exists():
        print(f"Advisory file {advisory_path} does not exist.")
        return None, None, None
    with open(advisory_path, 'r') as f:
        advisory_data = json.load(f)
    if 'details' not in advisory_data:
        print(f"No details found in advisory file {advisory_path}.")
    if 'summary' not in advisory_data:
        print(f"No summary found in advisory file {advisory_path}.")
    cwe_ids = advisory_data["database_specific"]["cwe_ids"]
    issue_desc = advisory_data['details'] if 'details' in advisory_data else None
    issue_summary = advisory_data['summary'] if 'summary' in advisory_data else None
    return cwe_ids, issue_desc, issue_summary

def get_issue_details_primevul(project_name, root_dir='.'):
    info_path = Path(root_dir) / "data" / "primevul" / "processed_info.json"
    if not info_path.exists():
        print(f"Processed info file {info_path} does not exist.")
        return None, None, None
    with open(info_path, 'r') as f:
        processed_info = json.load(f)
    if project_name not in processed_info:
        print(f"No information found for project {project_name} in {info_path}.")
        return None, None, None
    project_info = processed_info[project_name]
    cwe_ids = project_info['cwe_ids']
    issue_desc = project_info['cve_desc'] if 'cve_desc' in project_info else None
    return cwe_ids, issue_desc, None

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='OpenHands for generating vulnerability test cases')
    parser.add_argument('--dataset',    type=str,     default='cwe-bench-java', help='Dataset to use')
    parser.add_argument('--project',    type=str,     required=True,            help='Project to use')
    args = parser.parse_args()

    cwd = Path.cwd().absolute()

    if args.dataset == 'cwe-bench-java':
        workdir = Path('data', 'cwe-bench-java', 'openhands_workdir')
        java_env_dir = workdir / 'java-env'
        if not java_env_dir.exists():
            shutil.copytree('data/cwe-bench-java/java-env', java_env_dir)
        resources_dir = workdir / 'resources'
        if not resources_dir.exists():
            shutil.copytree('data/cwe-bench-java/resources', resources_dir)

        original_project_dir = Path('data', 'cwe-bench-java', 'project-sources', args.project)
        working_project_dir = Path('data', 'cwe-bench-java', 'openhands_workdir', 'project-sources', args.project)
        if working_project_dir.exists():
            print(f"Error: {working_project_dir} already exists. Please remove it first.")
            exit(1)
        if not original_project_dir.exists():
            raise ValueError(f"Original project directory {original_project_dir} does not exist.")
        shutil.copytree(original_project_dir, working_project_dir)
        relative_project_path = Path('project-sources', args.project)
        
    elif args.dataset == 'primevul':
        original_project_dir = Path('data', 'primevul', 'project-sources', args.project)
        working_project_dir = Path('data', 'primevul', 'openhands_workdir', 'project-sources', args.project)
        if working_project_dir.exists():
            print(f"Error: {working_project_dir} already exists. Please remove it first.")
            exit(1)
        if not original_project_dir.exists():
            raise ValueError(f"Original project directory {original_project_dir} does not exist.")
        shutil.copytree(original_project_dir, working_project_dir)
        workdir = Path('data', 'primevul', 'openhands_workdir', 'project-sources', args.project)
        relative_project_path = Path('.')
    else:
        raise ValueError(f"Unknown dataset: {args.dataset}")

    api_key = os.environ["ANTHROPIC_API_KEY"]

    if args.dataset == 'cwe-bench-java':
        cwe_ids, issue_desc, issue_summary = get_issue_details_java(args.project, root_dir=cwd)
    elif args.dataset == 'primevul':
        cwe_ids, issue_desc, issue_summary = get_issue_details_primevul(args.project, root_dir=cwd)

    desc_str = f"\"Summary: {issue_summary}\nDescription: {issue_desc}\"" if issue_summary else issue_desc

    if not issue_desc:
        print("Failed to retrieve issue details.")
        exit(1)
    
    cwe_to_instruction = {
        "CWE-22": ("This is a Path Traversal vulnerability (CWE-22). "
                   "The test case must call an externally accessible API of the project with appropriate inputs, such that "
                   "it reads from or writes to at least one file outside the project directory."),
        "CWE-78": ("This is a Command Injection vulnerability (CWE-78). "
                   "The test case must call an externally accessible API of the project with appropriate inputs, such that "
                   "it executes a shell command that is not intended by the application."),
        "CWE-79": ("This is a Cross-Site Scripting (XSS) vulnerability (CWE-79). "
                   "The test case must call an externally accessible API of the project "
                   "with an input that contains scripting code, and show that this input is not santized properly."),
        "CWE-94": ("This is a Code Injection vulnerability (CWE-94). "
                   "The test case must call an externally accessible API of the project with appropriate inputs, such that "
                   "it executes some code that is not intended by the application."),
    }
    cwe_desc = None
    for cwe in cwe_ids:
        if cwe in cwe_to_instruction:
            cwe_desc = cwe_to_instruction[cwe]
            break
    if cwe_desc is None:
        raise ValueError(f"Unsupported CWE ID(s) {cwe_ids} for project {args.project}. Supported CWE IDs are: {list(cwe_to_instruction.keys())}")
    
    if args.dataset == 'cwe-bench-java':
        docker_instructions = f"""
The project is built and run as a Docker container, and the Dockerfile is at `project-sources/{args.project}/Dockerfile.vuln`.
You may have to install Docker first and start the Docker daemon. After Docker is installed, the project can be built with:
```
cd project-sources/{args.project}
docker build -f ./Dockerfile.vuln -t openhands-test ../..
```
Note the `../..` at the end of the command, for the build context.
All the build dependencies for the project are already installed in `Dockerfile.vuln`.
However, if you need any new dependencies, you can add them to `Dockerfile.vuln`. 
"""
    elif args.dataset == 'primevul':
        docker_instructions = f"""
The project is built and run as a Docker container, and the Dockerfile is at `Dockerfile.vuln`.
You may have to install Docker first and start the Docker daemon. After Docker is installed, the Docker image can be built with:
```
docker build -f ./Dockerfile.vuln -t openhands-test .
```
`Dockerfile.vuln` currently has some build dependencies, but you may need to add more.
Analyze the installation instructions in the project README or other documentation files, and add the necessary build/installation commands to `Dockerfile.vuln`.
Make sure that the project is built successfully when the image is built.
"""

    prompt = f"""
The project in `{relative_project_path}` has a vulnerability, reported as a CWE. The issue description says:
{desc_str}

Create a test case that FAILS (exits with non-zero code) if the vulnerability EXISTS,
and PASSES (exits with code 0) if the vulnerability DOES NOT EXIST.
{cwe_desc}

Note that the test should actually run the vulnerable code in the project.
It should NOT read the source code to check for the presence of a vulnerability.
It should NOT \"simulate\" the vulnerability by running some separate code that does not use the project.

{docker_instructions}

Feel free to create any new files to create the test case.
The command to run the test should be the `CMD` command in `Dockerfile.vuln`, so that the test can be run with `docker run --rm -t openhands-test`.
Do NOT use any web resources during the process of creating the test, including all tool calls. Do not use "curl", "wget", etc.
Do NOT attempt to fetch Github links referenced in the advisory or online CVE reports. Do not read Github commit logs or checkout any commits.
All the information you use to create this test must come from the project source code and this prompt.
""".strip()

    with open(cwd/"openhands_prompt.txt", 'w') as f:
        f.write(prompt)

    print("Prompt:\n", prompt)
    timestr = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

    config_toml = f"""
[core]
workspace_base = "{workdir.absolute()}"
debug = true
max_budget_per_task = 5.0
max_iterations = 300
save_trajectory_path = "/scratch/vuln_agent/openhands_logs/{args.project}_{timestr}.log"
enable_browser = false

[llm]
model = "anthropic/claude-3-7-sonnet-20250219"
api_key = "{api_key}"

[agent]
enable_browsing = false
enable_mcp = false

[sandbox]
docker_runtime_kwargs = {{ privileged = true }}
use_host_network = false
runtime_extra_build_args = []

[kubernetes]
privileged = true
""".strip()
    config_file = cwd / "OpenHands" / "config.toml"
    with open(config_file, "w") as f:
        f.write(config_toml)

    openhands_cmd = f"LOG_ALL_EVENTS=true poetry run python -m openhands.core.main -f {cwd.absolute()}/openhands_prompt.txt"
    print("Running OpenHands with command:\n", openhands_cmd)
    os.chdir(cwd / "OpenHands")

    try:
        proc = subprocess.Popen(
            openhands_cmd,
            shell=True,
            preexec_fn=os.setsid  # Start the process in a new process group
        )
        proc.wait(timeout=3600)
    except subprocess.TimeoutExpired:
        print("OpenHands command timed out.")
        os.killpg(proc.pid, signal.SIGTERM)  # Kill the whole process group
        exit(1)