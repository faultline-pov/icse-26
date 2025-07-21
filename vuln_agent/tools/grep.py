from vuln_agent.tools import Tool
from vuln_agent.helpers import *

class Grep(Tool):
    """
    Tool to search for a string in the contents of a single file or all files in a directory.
    """
    def get_name(self):
        return "grep"

    def get_description(self):
        return "Searches for a string in the contents of a single file or all files in a directory."

    def get_usage(self):
        return ('<TOOL>\n'
                '{"name": "grep",\n'
                ' "query": "search_string",\n'
                ' "path": "/path/to/directory_or_file"\n}\n'
                '</TOOL>\n'
                 'Note that the /path/to/directory_or_file should be absolute, not relative.\n')

    def __init__(self, logger: Logger):
        self.logger = logger

    def execute(self, param_dict: str):
        """
        Executes the tool with the given LLM output.
        """
        query = param_dict.get("query")
        path = param_dict.get("path")
        if not query:
            return {"status": "Failure", "output": "Missing 'query' field"}
        if not path:
            return {"status": "Failure", "output": "Missing 'path' field"}
        # Check if there are other keys in the param_dict
        for key in param_dict.keys():
            if key not in ["name", "query", "path"]:
                return {"status": "Failure", "output": f"Unknown field '{key}'"}
        # Check if the path exists
        if not os.path.exists(path):
            return {"status": "Failure", "output": f"Path {path} does not exist"}
        # Search for the query in the specified path
        try:
            output = run(f"grep -nr -F --exclude='.?*' \"{query}\" {path}", logger=self.logger, timeout=5)
            if not output:
                return {"status": "Success", "output": "No results found"}
            return {"status": "Success", "output": truncate(output, 2000)}
        except RunException as e:
            if str(e) == "STDOUT:\n\nSTDERR:\n":
                return {"status": "Success", "output": "No results found"}
            return {"status": "Failure", "output": truncate(str(e), 2000)}