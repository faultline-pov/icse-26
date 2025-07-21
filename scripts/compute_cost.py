import json
from pathlib import Path
import prettytable

if __name__ == '__main__':

    results = {}
    cwd = Path.cwd()

    for folder in Path("logs").iterdir():
        if folder.is_dir():
            log_file = folder / "log.json"

            if not log_file.exists():
                raise ValueError(f"Log file {log_file} does not exist")

            with open(log_file, 'r') as f:
                log_data = json.load(f)

            total_cost = 0.0
            llm_time = 0.0
            tool_time = 0.0
            for entry in log_data.get('actions', []):
                if 'cost' in entry:
                    total_cost += entry['cost']
                if entry['type'] == 'llm_call':
                    llm_time += entry['elapsed_time']
                elif entry['type'] == 'tool_call' or entry['type'] == 'validation':
                    tool_time += entry['elapsed_time']
        
            results[folder.name] = {
                'cost': total_cost,
                'llm_time': llm_time,
                'tool_time': tool_time
            }
    
    with open(cwd / "logs/costs.json", 'w') as f:
        json.dump(results, f, indent=4)

    # Draw an ascii table
    table = prettytable.PrettyTable()
    table.field_names = ["Project", "Cost (USD)", "LLM Time (s)", "Tool Time (s)", "Total Time (s)"]
    for project, metrics in results.items():
        table.add_row([project, f"${metrics['cost']:.4f}", f"{metrics['llm_time']:.4f}",\
            f"{metrics['tool_time']:.4f}", f"{metrics['llm_time'] + metrics['tool_time']:.4f}"])

    total_metrics = {'cost': 0.0, 'llm_time': 0.0, 'tool_time': 0.0}
    for metrics in results.values():
        total_metrics['cost'] += metrics['cost']
        total_metrics['llm_time'] += metrics['llm_time']
        total_metrics['tool_time'] += metrics['tool_time']
    table.add_row(["TOTAL", f"${total_metrics['cost']:.4f}", f"{total_metrics['llm_time']:.4f}",\
        f"{total_metrics['tool_time']:.4f}", f"{total_metrics['llm_time'] + total_metrics['tool_time']:.4f}"])

    print(table)