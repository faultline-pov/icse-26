from vuln_agent.tools import Tool
from vuln_agent.helpers import *

class Find(Tool):
    """
    Tool to find files or directories with a name containing a search string.
    """
    def get_name(self):
        return "find"

    def get_description(self):
        return "Finds files or directories with a name containing a search string."

    def get_usage(self):
        return ('<TOOL>\n'
                '{"name": "find",\n'
                ' "query": "search_string",\n'
                ' "path": "/path/to/base_directory_or_file"\n}\n'
                '</TOOL>\n'
                 'Note that the /path/to/base_directory_or_file should be absolute, not relative.\n')

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
            output = run(f"find {path} -not -path '*/.*' -name \"*{query}*\"", logger=self.logger, timeout=5)
            if not output:
                return {"status": "Success", "output": "No results found"}
            return {"status": "Success", "output": truncate(output, 2000)}
        except RunException as e:
            if str(e) == "STDOUT:\n\nSTDERR:\n":
                return {"status": "Success", "output": "No results found"}
            return {"status": "Failure", "output": truncate(str(e), 2000)}