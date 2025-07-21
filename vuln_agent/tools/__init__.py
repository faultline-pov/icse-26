from vuln_agent.helpers import *

class Tool:
    """
    Base class for all tools in the vuln_agent module.
    """

    def get_name(self):
        """
        Returns the name of the tool.
        """
        raise NotImplementedError("Subclasses should implement this method.")

    def get_description(self):
        """
        Returns a description of the tool.
        """
        raise NotImplementedError("Subclasses should implement this method.")

    def get_usage(self):
        """
        Returns the usage instructions for the tool.
        """
        raise NotImplementedError("Subclasses should implement this method.")
    
    def execute(self, llm_output: str):
        """
        Executes the tool with the given LLM output.
        """
        raise NotImplementedError("Subclasses should implement this method.")

from vuln_agent.tools.read import Read
from vuln_agent.tools.write import Write
from vuln_agent.tools.listdir import ListDir
from vuln_agent.tools.grep import Grep
from vuln_agent.tools.find import Find
from vuln_agent.tools.mkdir import Mkdir

class Tooling:

    def __init__(self, logger):
        """
        Initializes the Tooling class.
        This class is responsible for managing tools and their invocations.
        """
        self.tool_name_mapping = {}
        self.logger = logger

    def register_tool(self, tool: Tool):
        """
        Registers a tool class with its name.
        Args:
            tool_class (Tool): The tool class to register.
        """
        tool_name = tool.get_name()
        if tool_name in self.tool_name_mapping:
            raise ValueError(f"Tool with name '{tool_name}' is already registered.")
        self.tool_name_mapping[tool_name] = tool

    def has_tool_invocation(self, llm_output: str) -> bool:
        """
        Checks if the LLM output contains a tool invocation.
        Args:
            llm_output (str): The LLM output to check.
        Returns:
            bool: True if the LLM output contains a tool invocation, False otherwise.
        """
        return "<TOOL>" in llm_output and "</TOOL>" in llm_output

    def invoke_tool(self, llm_output: str) -> dict[str, str]:
        """
        Invokes the tool with the given LLM output.
        Args:
            llm_output (str): The LLM output to check.
        Returns:
            dict[str, str]: The tool invocation output.
        """
        # Get the part between <TOOL> and </TOOL>
        start = llm_output.index("<TOOL>") + len("<TOOL>")
        end = llm_output.index("</TOOL>")
        tool_invocation = llm_output[start:end].strip()
        # Parse the tool invocation as JSON
        try:
            import json
            parsed_output = json.loads(tool_invocation)
        except json.JSONDecodeError:
            return {"status": "Failure", "output": "Invalid JSON"}

        # Get the tool name
        tool_name = parsed_output.get("name")
        if not tool_name:
            return {"status": "Failure", "output": "Missing 'name' field"}
        
        # Get the tool class from the mapping
        tool = self.tool_name_mapping.get(tool_name)

        if not tool:
            return {"status": "Failure", "output": f"Unknown tool: {tool_name}"}
        # Execute the tool with the parsed output
        start_time = time.time()
        start_time_str = f"{datetime.datetime.now()}"
        result = tool.execute(parsed_output)
        elapsed_time = time.time() - start_time
        self.logger.log_action({
            'type': 'tool_call',
            'tool_name': tool_name,
            'start_time': start_time_str,
            'elapsed_time': elapsed_time,
        })
        return result

__all__ = [
    "Tool",
    "Read",
    "Write",
    "ListDir",
    "Grep",
    "Find",
    "Tooling",
    "Mkdir",
]