import os
import argparse
import csv
import subprocess
import json
import sys

CWE_BENCH_JAVA_ROOT_DIR = os.path.abspath(os.path.join(__file__, "..", ".."))
MAVEN_VERSIONS = json.load(open(f"{CWE_BENCH_JAVA_ROOT_DIR}/scripts/mvn_version.json"))
GRADLE_VERSIONS = json.load(open(f"{CWE_BENCH_JAVA_ROOT_DIR}/scripts/gradle_version.json"))
JDK_VERSIONS = json.load(open(f"{CWE_BENCH_JAVA_ROOT_DIR}/scripts/jdk_version.json"))

def get_mvn_versions_for_jdk(jdk_version):
  jdk_version = int(jdk_version.split("u")[0]) if "u" in jdk_version else int(jdk_version)
  if jdk_version <= 7:
    return ["3.2.1"]
  else:
    return ["3.5.0", "3.9.10"]

def get_gradle_versions_for_jdk(jdk_version):
  jdk_version = int(jdk_version.split("u")[0]) if "u" in jdk_version else int(jdk_version)
  if jdk_version <= 7:
    return []
  elif jdk_version <= 10:
    return ["6.8.2", "7.6.4"]
  else:
    return ["8.9"]

NEWLY_BUILT = "newly-built"
ALREDY_BUILT = "already-built"
FAILED = "failed"

def build_one_project_with_maven_attempt(project_slug, attempt):
  target_dir = f"{CWE_BENCH_JAVA_ROOT_DIR}/project-sources/{project_slug}"

  print(f">> [CWE-Bench-Java/build_one] Building `{project_slug}` with MAVEN {attempt['mvn']} and JDK {attempt['jdk']}...")
  mvn_build_cmd = [
    "mvn",
    "clean",
    "package",
    "-B",
    "-V",
    "-e",
    "-Dfindbugs.skip",
    "-Dcheckstyle.skip",
    "-Dpmd.skip=true",
    "-Dspotbugs.skip",
    "-Denforcer.skip",
    "-Dmaven.javadoc.skip",
    "-DskipTests",
    "-Dmaven.test.skip.exec",
    "-Dlicense.skip=true",
    "-Drat.skip=true",
    "-Dspotless.check.skip=true",
    "-Dorg.slf4j.simpleLogger.log.org.apache.maven.cli.transfer.Slf4jMavenTransferListener=warn"
  ]
  output = subprocess.run(
    mvn_build_cmd,
    cwd=target_dir,
    env={
      "PATH": (f"{os.environ['PATH']}:"
               f"{CWE_BENCH_JAVA_ROOT_DIR}/java-env/{MAVEN_VERSIONS[attempt['mvn']]['dir']}/bin:"
               f"{CWE_BENCH_JAVA_ROOT_DIR}/java-env/{JDK_VERSIONS[attempt['jdk']]['dir']}/bin"),
      "JAVA_HOME": f"{CWE_BENCH_JAVA_ROOT_DIR}/java-env/{JDK_VERSIONS[attempt['jdk']]['dir']}",
    },
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
  )
  cmd = " ".join(mvn_build_cmd)
  envvar_setup = f"export PATH=$PATH:$WORKSPACE_BASE/java-env/{MAVEN_VERSIONS[attempt['mvn']]['dir']}/bin:" +\
      f"$WORKSPACE_BASE/java-env/{JDK_VERSIONS[attempt['jdk']]['dir']}/bin\n" +\
      f"export JAVA_HOME=$WORKSPACE_BASE/java-env/{JDK_VERSIONS[attempt['jdk']]['dir']}"
    
  if output.returncode != 0:
    print(f">> [CWE-Bench-Java/build_one] Attempting build `{project_slug}` with MAVEN {attempt['mvn']} and JDK {attempt['jdk']} failed with return code {output.returncode}")
    print(f"StdOut:")
    print(output.stdout)
    print(f"Error message:")
    print(output.stderr)
    return FAILED
  else:
    print(f">> [CWE-Bench-Java/build_one] Build succeeded for project `{project_slug}` with MAVEN {attempt['mvn']} and JDK {attempt['jdk']}")
    print(f">> [CWE-Bench-Java/build_one] Dumping build information")
    json.dump(attempt, open(f"{CWE_BENCH_JAVA_ROOT_DIR}/build-info/{project_slug}.json", "w"))
    with open(f"{target_dir}/build-command.sh", "w") as f:
      f.write(cmd)
    with open(f"{target_dir}/envvar-setup.sh", "w") as f:
      f.write(envvar_setup)
    return NEWLY_BUILT

def build_one_project_with_gradle_attempt(project_slug, attempt):
  target_dir = f"{CWE_BENCH_JAVA_ROOT_DIR}/project-sources/{project_slug}"

  print(f">> [CWE-Bench-Java/build_one] Building `{project_slug}` with Gradle {attempt['gradle']} and JDK {attempt['jdk']}...")
  gradle_build_cmd = [
    "gradle",
    "build",
    "--parallel",
  ]
  output = subprocess.run(
    gradle_build_cmd,
    cwd=target_dir,
    env={
      "PATH": (f"{os.environ['PATH']}:"
               f"{CWE_BENCH_JAVA_ROOT_DIR}/java-env/{GRADLE_VERSIONS[attempt['gradle']]['dir']}/bin:"
               f"{CWE_BENCH_JAVA_ROOT_DIR}/java-env/{JDK_VERSIONS[attempt['jdk']]['dir']}/bin"),
      "JAVA_HOME": f"{CWE_BENCH_JAVA_ROOT_DIR}/java-env/{JDK_VERSIONS[attempt['jdk']]['dir']}",
    },
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
  )
  cmd = " ".join(gradle_build_cmd)
  envvar_setup = f"export PATH=$PATH:$WORKSPACE_BASE/java-env/{GRADLE_VERSIONS[attempt['gradle']]['dir']}/bin:" +\
        f"$WORKSPACE_BASE/java-env/{JDK_VERSIONS[attempt['jdk']]['dir']}/bin\n" +\
        f"export JAVA_HOME=$WORKSPACE_BASE/java-env/{JDK_VERSIONS[attempt['jdk']]['dir']}"

  if output.returncode != 0:
    print(f">> [CWE-Bench-Java/build_one] Attempting build `{project_slug}` with Gradle {attempt['gradle']} and JDK {attempt['jdk']} failed with return code {output.returncode}")
    print(f"StdOut:")
    print(output.stdout)
    print(f"Error message:")
    print(output.stderr)
    return FAILED
  else:
    print(f">> [CWE-Bench-Java/build_one] Build succeeded for project `{project_slug}` with Gradle {attempt['gradle']} and JDK {attempt['jdk']}")
    print(f">> [CWE-Bench-Java/build_one] Dumping build information")
    json.dump(attempt, open(f"{CWE_BENCH_JAVA_ROOT_DIR}/build-info/{project_slug}.json", "w"))
    with open(f"{target_dir}/build-command.sh", "w") as f:
      f.write(cmd)
    with open(f"{target_dir}/envvar-setup.sh", "w") as f:
      f.write(envvar_setup)
    return NEWLY_BUILT

def build_one_project_with_gradlew(project_slug, attempt):
  target_dir = f"{CWE_BENCH_JAVA_ROOT_DIR}/project-sources/{project_slug}"
  print(f">> [CWE-Bench-Java/build_one] Attempting build `{project_slug}` with custom gradlew script...")
  print(f">> [CWE-Bench-Java/build_one] Chmod +x on gradlew file...")
  subprocess.run(["chmod", "+x", "./gradlew"], cwd=target_dir)
  print(f">> [CWE-Bench-Java/build_one] Running gradlew...")
  gradlew_cmd = ["./gradlew", "--no-daemon", "-S", "-Dorg.gradle.dependency.verification=off", "clean"]
  output = subprocess.run(
    gradlew_cmd,
    cwd=target_dir,
    env={
      "JAVA_HOME": f"{CWE_BENCH_JAVA_ROOT_DIR}/java-env/{JDK_VERSIONS[attempt['jdk']]['dir']}",
      "PATH": (f"{os.environ['PATH']}:"
               f"{CWE_BENCH_JAVA_ROOT_DIR}/java-env/{JDK_VERSIONS[attempt['jdk']]['dir']}/bin"),
    },
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
  )
  cmd = " ".join(gradlew_cmd)
  envvar_setup = f"export JAVA_HOME=$WORKSPACE_BASE/java-env/{JDK_VERSIONS[attempt['jdk']]['dir']}\n" +\
        f"export PATH=$PATH:$WORKSPACE_BASE/java-env/{JDK_VERSIONS[attempt['jdk']]['dir']}/bin\n"
    
  if output.returncode != 0:
    print(f">> [CWE-Bench-Java/build_one] Attempting build `{project_slug}` with ./gradlew and JDK {attempt['jdk']} failed with return code {output.returncode}")
    print(f"StdOut:")
    print(output.stdout)
    print(f"Error message:")
    print(output.stderr)
    return FAILED
  else:
    print(f">> [CWE-Bench-Java/build_one] Build succeeded for project `{project_slug}` with ./gradlew and JDK {attempt['jdk']}")
    print(f">> [CWE-Bench-Java/build_one] Dumping build information")
    json.dump({"gradlew": 1}, open(f"{CWE_BENCH_JAVA_ROOT_DIR}/build-info/{project_slug}.json", "w"))
    with open(f"{target_dir}/build-command.sh", "w") as f:
      f.write(cmd)
    with open(f"{target_dir}/envvar-setup.sh", "w") as f:
      f.write(envvar_setup)
    return NEWLY_BUILT

def build_one_project_with_attempt(project_slug, attempt):
  # # Checking if the repo has been built already
  # if is_built(project_slug):
  #   print(f">> [CWE-Bench-Java/build_one] {project_slug} is already built...")
  #   return ALREDY_BUILT

  # Otherwise, build it directly
  if "mvn" in attempt:
    return build_one_project_with_maven_attempt(project_slug, attempt)
  elif "gradle" in attempt:
    return build_one_project_with_gradle_attempt(project_slug, attempt)
  elif os.path.exists(f"{CWE_BENCH_JAVA_ROOT_DIR}/project-sources/{project_slug}/gradlew"):
    return build_one_project_with_gradlew(project_slug, attempt)
  else:
    raise Exception("should not happen!")

def is_built(project_slug) -> bool:
  if os.path.exists(f"{CWE_BENCH_JAVA_ROOT_DIR}/build-info/{project_slug}.json"):
    return True
  else:
    return False

def save_build_result(project_slug, result, attempt):
  build_result_dir = f"{CWE_BENCH_JAVA_ROOT_DIR}/data/build_info.csv"

  rows = []
  if os.path.exists(build_result_dir):
    rows = list(csv.reader(open(build_result_dir)))[1:]

  existed_and_mutated = False
  desired_num_columns = 6
  for row in rows:
    if len(row) < desired_num_columns:
      row += ["n/a"] * (desired_num_columns - len(row))
    if row[0] == project_slug:
      existed_and_mutated = True
      row[1] = "success" if result else "failure"
      row[2] = attempt["jdk"]
      row[3] = attempt["mvn"] if "mvn" in attempt else "n/a"
      row[4] = attempt["gradle"] if "gradle" in attempt else "n/a"
      row[5] = attempt["gradlew"] if "gradlew" in attempt else "n/a"

  if not existed_and_mutated:
    rows.append([
      project_slug,
      "success" if result else "failure",
      attempt["jdk"],
      attempt["mvn"] if "mvn" in attempt else "n/a",
      attempt["gradle"] if "gradle" in attempt else "n/a",
      attempt["gradlew"] if "gradlew" in attempt else "n/a",
    ])

  writer = csv.writer(open(build_result_dir, "w"))
  writer.writerow(["project_slug", "status", "jdk_version", "mvn_version", "gradle_version", "use_gradlew"])
  writer.writerows(rows)

def get_jdk_version(project_slug):

  target_dir = f"{CWE_BENCH_JAVA_ROOT_DIR}/project-sources/{project_slug}"
  if not os.path.exists(target_dir):
    print(f">> [CWE-Bench-Java/build_one] Project directory {target_dir} does not exist. Cannot get JDK version.")
    return None

  output = subprocess.run(
    ["bash", f"{CWE_BENCH_JAVA_ROOT_DIR}/scripts/get-jdk-version.sh"],
    cwd=target_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
  )
  if output.returncode != 0:
    print(f">> [CWE-Bench-Java/build_one] Failed to get JDK version for project `{project_slug}`. Error: {output.stderr}")
    return None
  jdk_version = output.stdout.strip()
  if jdk_version == "8":
    jdk_version = "8u202"  # Normalize to the specific version we use
  elif jdk_version == "7":
    jdk_version = "7u80"
  elif int(jdk_version) > 8:
    jdk_version = "17"
  return jdk_version

def build_one_project(project_slug):
  with open(f"{CWE_BENCH_JAVA_ROOT_DIR}/data/build_info.csv", "r") as f:
    reader = csv.reader(f)
    # Find the row corresponding to the project_slug
    for row in reader:
      if row[0] == project_slug:
        _, status,jdk_version,mvn_version,gradle_version,use_gradlew = row
        if status == "success":
          # Get the config that was used to build it
          attempt = {
            "jdk": jdk_version,
          }
          if mvn_version != "n/a":
            attempt["mvn"] = mvn_version
          if gradle_version != "n/a":
            attempt["gradle"] = gradle_version
          if use_gradlew != "n/a":
            attempt["gradlew"] = int(use_gradlew)

          print("Trying build with existing build config: ", attempt)
          result = build_one_project_with_attempt(project_slug, attempt)
          if result == NEWLY_BUILT:
            save_build_result(project_slug, True, attempt)
            return
          elif result == ALREDY_BUILT:
            return

  jdk_versions = []
  attempts = []
  jdk_version = get_jdk_version(project_slug)
  if jdk_version is None:
    print(f">> [CWE-Bench-Java/build_one] Could not determine JDK version for project `{project_slug}`. Trying all.")
    jdk_versions = list(JDK_VERSIONS.keys())
  else:
    jdk_versions = [jdk_version]
  for jdk in jdk_versions:
    mvn_versions = get_mvn_versions_for_jdk(jdk)
    gradle_versions = get_gradle_versions_for_jdk(jdk)
    for mvn in mvn_versions:
      attempts.append({"jdk": jdk, "mvn": mvn})
    for gradle in gradle_versions:
      attempts.append({"jdk": jdk, "gradle": gradle})
    attempts.append({"jdk": jdk, "gradlew": 1})  # Always try gradlew if it exists
  if len(attempts) == 0:
    print(f">> [CWE-Bench-Java/build_one] No valid build attempts found for project `{project_slug}`. Skipping.")
    return
  for attempt in attempts:
    result = build_one_project_with_attempt(project_slug, attempt)
    if result == NEWLY_BUILT:
      # save_build_result(project_slug, True, attempt)
      return
    elif result == ALREDY_BUILT:
      return
  # If we reach here, all attempts failed
  # save_build_result(project_slug, False, {"jdk": "n/a", "mvn": "n/a", "gradle": "n/a"})
  exit(1)

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("project_slug", type=str)
  args = parser.parse_args()
  build_one_project(args.project_slug)
