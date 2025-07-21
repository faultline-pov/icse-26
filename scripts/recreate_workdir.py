import argparse
import os
import shutil
from pathlib import Path
import subprocess

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recreate the work directory.")
    parser.add_argument("--diffdir", type=str, help="Directory containing diffs for each project")
    parser.add_argument("--dataset", type=str, default="dataset", help="cwe-bench-java or primevul")
    args = parser.parse_args()

    diff_path = Path(args.diffdir).absolute()
    workdir = Path('data', args.dataset, 'workdir').absolute()

    workdir.mkdir(parents=True, exist_ok=True)

    if args.dataset == 'cwe-bench-java':
        java_env_dir = workdir / 'java-env'
        if not java_env_dir.exists():
            shutil.copytree('data/cwe-bench-java/java-env', java_env_dir)
        resources_dir = workdir / 'resources'
        if not resources_dir.exists():
            shutil.copytree('data/cwe-bench-java/resources', resources_dir)

    all_patches = list(diff_path.glob('*.patch'))
    for i, diff_file in enumerate(all_patches):
        project_dir = Path('data', args.dataset, 'project-sources', diff_file.stem)
        if not project_dir.exists():
            print(f"Project directory {project_dir} does not exist. Skipping {diff_file.name}.")
            continue
        project_workdir = workdir / 'project-sources' / diff_file.stem
        if project_workdir.exists():
            print(f"Error: project workdir {project_workdir} already exists. Please remove it first.")
            exit(1)
        shutil.copytree(project_dir, project_workdir)
        print(f"Copied {diff_file.stem} to {project_workdir}")

        # Remove existing files
        (project_workdir / "Dockerfile.vuln").unlink(missing_ok=True)
        (project_workdir / ".Dockerfile.backup").unlink(missing_ok=True)
        (project_workdir / ".build_diff.patch").unlink(missing_ok=True)

        # Apply the diff
        print(f"Applying diff {diff_file} to {project_workdir}")
        try:
            result = subprocess.run(f"git -C {project_workdir} apply --allow-empty --whitespace=fix {diff_path / diff_file.name}",
                shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            print(f"Error applying diff {diff_file} to {project_workdir}: {e}")
            continue

        print(f"[{i+1}/{len(all_patches)}] Work directory for {diff_file.stem} recreated at {project_workdir}")
