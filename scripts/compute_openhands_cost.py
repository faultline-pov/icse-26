import json
from pathlib import Path
import prettytable
from datetime import datetime

def get_elapsed_time(time_str1, time_str2):
    fmt = "%Y-%m-%dT%H:%M:%S.%f"
    dt1 = datetime.strptime(time_str1, fmt)
    dt2 = datetime.strptime(time_str2, fmt)

    # Compute the time difference in seconds
    elapsed_seconds = (dt2 - dt1).total_seconds()
    return elapsed_seconds

if __name__ == '__main__':

    results = {}
    cwd = Path.cwd()

    for log_file in Path("openhands_logs").iterdir():
        if log_file.is_file():
            with open(log_file, 'r') as f:
                try:
                    log_data = json.load(f)
                except json.JSONDecodeError as e:
                    print(f"Warning: Failed to parse JSON in {log_file}, skipping. Error: {e}")
                    continue
            
            if len(log_data) == 0:
                print(f"Warning: Log file {log_file} is empty, skipping")
                continue

            if not isinstance(log_data, list):
                print(f"Warning: Log file {log_file} does not contain a list of log entries, skipping")
                continue
            
            cost = None
            for entry in log_data[::-1]:
                if "llm_metrics" in entry:
                    cost = entry["llm_metrics"]["accumulated_cost"]
                    break
            if cost is None:
                print(f"Warning: No cost found in {log_file}, skipping")
                continue

            elapsed_time = get_elapsed_time(log_data[0]["timestamp"], log_data[-1]["timestamp"])
            project_name = '_'.join(log_file.stem.split('_')[:-2])

            num_iters = log_data[-1]["id"]

            results[project_name] = {
                'cost': cost,
                'elapsed_time': elapsed_time,
                'num_iters': num_iters
            }
    
    with open(cwd / "openhands_logs/costs.tsv", 'w') as f:
        f.write("Project\tCost (USD)\tElapsed Time (s)\tNum Iterations\n")
        for project, metrics in results.items():
            f.write(f"{project}\t{metrics['cost']:.4f}\t{metrics['elapsed_time']:.4f}\t{metrics['num_iters']}\n")

    # Draw an ascii table
    table = prettytable.PrettyTable()
    table.field_names = ["Project", "Cost (USD)", "Elapsed Time (s)", "Num Iterations"]
    for project, metrics in results.items():
        table.add_row([project, f"${metrics['cost']:.4f}", f"{metrics['elapsed_time']:.4f}", metrics['num_iters']])

    total_metrics = {'cost': 0.0, 'elapsed_time': 0.0, 'num_iters': 0}
    for metrics in results.values():
        total_metrics['cost'] += metrics['cost']
        total_metrics['elapsed_time'] += metrics['elapsed_time']
        total_metrics['num_iters'] += metrics['num_iters']
    table.add_row(["TOTAL", f"${total_metrics['cost']:.4f}", f"{total_metrics['elapsed_time']:.4f}", total_metrics['num_iters']])

    print(table)