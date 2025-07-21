from vuln_agent.tools import Tool
from vuln_agent.helpers import *

class Mkdir(Tool):
    """
    Tool to create a directory.
    """
    def get_name(self):
        return "mkdir"

    def get_description(self):
        return "Create a directory."

    def get_usage(self):
        return ('<TOOL>\n'
                '{"name": "mkdir",\n'
                ' "path": "/path/to/directory"\n}\n'
                '</TOOL>\n'
                "If the directory doesn't exist, it will be created.\n"
                "Note that the /path/to/directory should be absolute, not relative.\n"
                )

    def __init__(self, logger: Logger):
        self.logger = logger
    
    def execute(self, param_dict: str):
        """
        Executes the tool with the given LLM output.
        """
        dirpath = param_dict.get("path")
        if not dirpath:
            return {"status": "Failure", "output": "Missing 'path' field"}
        # Check if there are other keys in the param_dict
        for key in param_dict.keys():
            if key not in ["name", "path"]:
                return {"status": "Failure", "output": f"Unknown field '{key}'"}
        # Check if the parent directory exists
        dirpath = Path(dirpath)
        if not dirpath.parent.exists():
            return {"status": "Failure", "output": f"Directory {dirpath.parent.absolute()} does not exist"}
        # Create the directory
        try:
            dirpath.mkdir(parents=True, exist_ok=True)
            self.logger.log_status(f"Directory {dirpath.absolute()} created successfully.")
            return {"status": "Success", "output": "Directory created successfully"}
        except Exception as e:
            return {"status": "Failure", "output": truncate(str(e), 10000)}