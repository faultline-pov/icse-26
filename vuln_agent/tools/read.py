from vuln_agent.tools import Tool
from vuln_agent.helpers import *

class Read(Tool):
    """
    Tool to read the contents of a file.
    """
    def get_name(self):
        return "read"

    def get_description(self):
        return "Read the contents of a file."

    def get_usage(self):
        return ('<TOOL>\n'
                '{"name": "read",\n'
                ' "file": "/path/to/file",\n'
                ' "start_line": <line_num>,\n'
                ' "end_line": <line_num>\n'
                '}\n'
                '</TOOL>\n'
                'Note that the /path/to/file should be absolute, not relative.\n'
                '`start_line` (optional) is the line number to start reading from. Defaults to 1.\n')

    def __init__(self, logger: Logger):
        self.logger = logger

    def execute(self, param_dict: str):
        """
        Executes the tool with the given LLM output.
        """
        fpath = param_dict.get("file")
        if not fpath:
            return {"status": "Failure", "output": "Missing 'file' field"}
        # Check if there are other keys in the param_dict
        for key in param_dict.keys():
            if key not in ["name", "file", "start_line", "end_line"]:
                return {"status": "Failure", "output": f"Unknown field '{key}'"}
        # Check if the fpath is absolute
        if not os.path.isabs(fpath):
            return {"status": "Failure", "output": "File path should be absolute"}
        # Check if the fpath exists
        if not os.path.isfile(fpath):
            return {"status": "Failure", "output": f"File {fpath} does not exist"}
        # Check if it is a hidden file or in a hidden directory
        if is_hidden_directory(fpath):
            return {"status": "Failure", "output": f"File {fpath} is a hidden file and cannot be read"}
        # Read the contents of the file
        try:
            with open(fpath, "r") as file:
                content = file.read()
            start_line = int(param_dict.get("start_line", 1))
            if start_line < 1:
                return {"status": "Failure", "output": "start_line must be >= 1"}
            end_line = int(param_dict.get("end_line", 1e6))
            if end_line < start_line:
                return {"status": "Failure", "output": "end_line must be >= start_line"}
            content = ''.join(content.splitlines(keepends=True)[start_line - 1:end_line])
            if len(content) == 0:
                return {"status": "Failure", "output": f"File is empty or start_line is too high"}
            return {"status": "Success", "output": truncate(content, 3000, start_line)}
        except Exception as e:
            return {"status": "Failure", "output": truncate(str(e), 3000, start_line)}