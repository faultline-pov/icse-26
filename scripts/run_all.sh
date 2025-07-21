# Iterate through all the subfolders in data/$1/project-sources
# For each subfolder name, run
# bash run.sh $1 <subfolder_name> $2
#!/bin/bash
if [ -z "$1" ]; then
  echo "Usage: $0 <dataset> <arg>"
  exit 1
fi
if [ -z "$2" ]; then
  echo "Usage: $0 <dataset> <arg>"
  exit 1
fi
for dir in data/"$1"/project-sources/*/; do
  subfolder_name=$(basename "$dir")
  # Check if any of the directories in logs/ start with subfolder_name
  # If so, skip this subfolder
  if ls logs/"$subfolder_name"* 1> /dev/null 2>&1; then
    echo "Skipping $subfolder_name, already processed."
    continue
  fi
  echo "Running for subfolder: $subfolder_name"
  bash scripts/run.sh "$1" "$subfolder_name" "$2"
done
echo "All subfolders processed."