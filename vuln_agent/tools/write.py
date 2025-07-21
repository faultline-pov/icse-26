from vuln_agent.tools import Tool
from vuln_agent.helpers import *

class Write(Tool):
    """
    Tool to write the contents to a file.
    """
    def get_name(self):
        return "write"

    def get_description(self):
        return "Write the contents to a file."

    def get_usage(self):
        return ('<TOOL>\n'
                '{"name": "write",\n'
                ' "file": "/path/to/file",\n'
                ' "content": "<contents to write>"\n}\n'
                '</TOOL>\n'
                "If the file doesn't exist, it will be created.\n"
                "Note that the /path/to/file should be absolute, not relative.\n"
                )

    def __init__(self, logger: Logger):
        self.logger = logger
    
    def execute(self, param_dict: str):
        """
        Executes the tool with the given LLM output.
        """
        fpath = param_dict.get("file")
        if not fpath:
            return {"status": "Failure", "output": "Missing 'file' field"}
        if 'content' not in param_dict:
            return {"status": "Failure", "output": "Missing 'content' field"}
        content = param_dict.get("content")
        # Check if there are other keys in the param_dict
        for key in param_dict.keys():
            if key not in ["name", "file", "content"]:
                return {"status": "Failure", "output": f"Unknown field '{key}'"}
        # Check if the parent directory exists
        fpath = Path(fpath)
        if not fpath.parent.exists():
            return {"status": "Failure", "output": f"Directory {fpath.parent.absolute()} does not exist"}
        # Write the content to the file
        try:
            with open(fpath, "w") as file:
                file.write(content)
            self.logger.log_status(content)
            return {"status": "Success", "output": "File written successfully"}
        except Exception as e:
            return {"status": "Failure", "output": truncate(str(e), 10000)}