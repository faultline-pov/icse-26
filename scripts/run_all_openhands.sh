# Iterate through all the subfolders in data/cwe-bench-java/project-sources
# For each subfolder name, run
# python scripts/run_openhands.py --project <subfolder_name> --dataset $1
#!/bin/bash
if [ -z "$1" ]; then
  echo "Usage: $0 <dataset>"
  exit 1
fi
for dir in data/"$1"/project-sources/*/; do
  subfolder_name=$(basename "$dir")
  # Check if any of the directories in openhands_logs/ start with subfolder_name
  # If so, skip this subfolder
  if ls openhands_logs/"$subfolder_name"* 1> /dev/null 2>&1; then
    echo "Skipping $subfolder_name, already processed."
    continue
  fi
  echo "Running for subfolder: $subfolder_name"
  python scripts/run_openhands.py --project "$subfolder_name" --dataset "$1"
done
echo "All subfolders processed."