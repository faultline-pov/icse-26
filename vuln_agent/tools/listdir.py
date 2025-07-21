from vuln_agent.tools import Tool
from vuln_agent.helpers import *

class ListDir(Tool):
    """
    Tool to list the contents of a directory.
    """
    def get_name(self):
        return "listdir"

    def get_description(self):
        return "Lists the contents of a directory."

    def get_usage(self):
        return ('<TOOL>\n'
                '{"name": "listdir",\n'
                ' "directory": "/path/to/directory"\n}\n'
                '</TOOL>\n'
                 'Note that the /path/to/directory should be absolute, not relative.\n')

    def __init__(self, logger: Logger):
        self.logger = logger

    def execute(self, param_dict: str):
        """
        Executes the tool with the given LLM output.
        """
        directory = param_dict.get("directory")
        if not directory:
            return {"status": "Failure", "output": "Missing 'directory' field"}
        # Check if there are other keys in the param_dict
        for key in param_dict.keys():
            if key not in ["name", "directory"]:
                return {"status": "Failure", "output": f"Unknown field '{key}'"}
        # Check if the directory exists
        if not os.path.isdir(directory):
            return {"status": "Failure", "output": f"Directory {directory} does not exist"}
        # List the contents of the directory
        try:
            listing = [f for f in os.listdir(directory) if not f.startswith('.')]
            output = '\n'.join(listing)
            return {"status": "Success", "output": truncate(output, 10000)}
        except Exception as e:
            return {"status": "Failure", "output": truncate(str(e), 10000)}