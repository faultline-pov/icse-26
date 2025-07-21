from vuln_agent.prompts import *
from vuln_agent.tools import *
from vuln_agent.helpers import *
from vuln_agent.conversation import Conversation

class BranchReasoning:
    def __init__(self, model, dataset, project_name, workdir, logger, init_conversation, max_turns=50):
        self.model = model
        self.dataset = dataset
        self.project_name = project_name
        self.workdir = workdir
        self.logger = logger
        self.max_turns = max_turns
        self.conversation = init_conversation

        self.tools = [tool_class(self.logger) for tool_class in [ListDir, Read, Grep, Find]]
        self.tool_manager = Tooling(self.logger)
        for tool in self.tools:
            self.tool_manager.register_tool(tool)

    def get_conversation(self):
        return self.conversation

    def get_issue_details(self):

        if self.dataset == 'cwe-bench-java':
            advisory_path = Path(self.workdir) / "../../../advisory" / f"{self.project_name}.json"
            if not advisory_path.exists():
                self.logger.log_failure(f"Advisory file {advisory_path} does not exist.")
                return None, None, None
            with open(advisory_path, 'r') as f:
                advisory_data = json.load(f)
            if 'details' not in advisory_data:
                self.logger.log_failure(f"No details found in advisory file {advisory_path}.")
            if 'summary' not in advisory_data:
                self.logger.log_failure(f"No summary found in advisory file {advisory_path}.")
            cwe_ids = advisory_data["database_specific"]["cwe_ids"]
            issue_desc = advisory_data['details'] if 'details' in advisory_data else None
            issue_summary = advisory_data['summary'] if 'summary' in advisory_data else None
            return cwe_ids, issue_desc, issue_summary

        elif self.dataset == 'primevul':
            info_path = Path(self.workdir) / "../../../processed_info.json"
            if not info_path.exists():
                self.logger.log_failure(f"Processed info file {info_path} does not exist.")
                return None, None, None
            with open(info_path, 'r') as f:
                processed_info = json.load(f)
            if self.project_name not in processed_info:
                self.logger.log_failure(f"No information found for project {self.project_name} in {info_path}.")
                return None, None, None
            project_info = processed_info[self.project_name]
            cwe_ids = project_info['cwe_ids']
            issue_desc = project_info['cve_desc'] if 'cve_desc' in project_info else None
            return cwe_ids, issue_desc, None
        else:
            raise ValueError(f"Unsupported dataset {self.dataset}. Supported datasets are: ['cwe-bench-java', 'primevul']")
    
    def run(self, flow):
        """
        Run the branch reasoning module.
        """
        self.logger.log_status("Running branch reasoning module...")

        cwe_ids, issue_desc, issue_summary = self.get_issue_details()
        if not issue_desc:
            self.logger.log_failure("Failed to retrieve issue details.")
            return None, None

        # Construct the prompt
        prompt = construct_issue_desc_prompt(issue_desc, issue_summary, diff=None)
        if flow:
            prompt += "Here is a flow consisting of a sequence of program points to reach the vulnerability:\n"
            prompt += flow + "\n"
        prompt += (
            "Could you generate the sequence of branch conditions"
            " encountered on the way to the sink, starting from the source?"
            " Include *every single* if-else, try-except, or switch statement that the program flow will encounter"
            " in the path from the source to the sink.\n"
            " This should take the form of a sequence of program points, each in the following format:\n"
            '{"type": "If-Else | Try-Except | Switch",\n'
            ' "code": "Source code of program point (1-2 lines),\n'
            ' "file": "File path (absolute)",\n'
            ' "outcome": "What should be the outcome of the branch statement in order to reach the vulnerability?"\n}\n'
            ' You can use multiple intermediate steps and tool invocations, but when you are finished,'
            ' your final response should contain the sequence in the above format, within the tags <SEQUENCE> and </SEQUENCE>.\n'
        )
        prompt += construct_tool_prompt(self.tools)

        # self.conversation.add_message("system", "You are an intelligent code assistant.")
        self.conversation.add_message("user", prompt)
        self.logger.log_output(prompt)

        for turn in range(self.max_turns):
            response = self.conversation.generate()
            self.logger.log_output(response)
            if self.tool_manager.has_tool_invocation(response):
                self.logger.log_status("Tool invocation detected.")
                tool_output = self.tool_manager.invoke_tool(response)
                self.logger.log_output(tool_output)
                if tool_output['status'] == "Success":
                    self.conversation.add_message("user", tool_output['output'])
                    self.logger.log_status(tool_output['output'])
                else:
                    self.conversation.add_message("user", f"Tool invocation failed: {tool_output['output']}")
                    self.logger.log_status(f"Tool invocation failed: {tool_output['output']}")
            else:
                break

        if self.conversation.messages[-1]['role'] != "assistant":
            self.logger.log_failure("Branch reasoning failed to produce a valid response.")
            return None, None

        branch_response = self.conversation.messages[-1]['content']
        if "<SEQUENCE>" not in branch_response or "</SEQUENCE>" not in branch_response:
            self.logger.log_failure("Branch reasoning failed to produce a valid branch response.")
            return None, None
        branch_response = branch_response.split("<SEQUENCE>")[1].split("</SEQUENCE>")[0]
        branch_response = branch_response.strip()

        prompt  = ("Based on the above branch conditions that you generated, infer a set of conditions"
                   " that the external input must satisfy in order to reach the vulnerability.\n"
                   "Your final answer should be in the following format:\n"
                   "<CONDITIONS>\n"
                   "1. Condition 1\n"
                   "2. Condition 2\n"
                   "...\n"
                   "</CONDITIONS>\n")

        self.conversation.add_message("user", prompt)
        self.logger.log_output(prompt)
        for turn in range(self.max_turns):
            response = self.conversation.generate()
            self.logger.log_output(response)
            if self.tool_manager.has_tool_invocation(response):
                self.logger.log_status("Tool invocation detected.")
                tool_output = self.tool_manager.invoke_tool(response)
                self.logger.log_output(tool_output)
                if tool_output['status'] == "Success":
                    self.conversation.add_message("user", tool_output['output'])
                    self.logger.log_status(tool_output['output'])
                else:
                    self.conversation.add_message("user", f"Tool invocation failed: {tool_output['output']}")
                    self.logger.log_status(f"Tool invocation failed: {tool_output['output']}")
            else:
                break

        if self.conversation.messages[-1]['role'] != "assistant":
            self.logger.log_failure("Branch reasoning failed to produce valid conditions.")
            return None, None

        conditions = self.conversation.messages[-1]['content']
        if "<CONDITIONS>" not in conditions or "</CONDITIONS>" not in conditions:
            self.logger.log_failure("Branch reasoning failed to produce valid conditions.")
            return None, None
        conditions = conditions.split("<CONDITIONS>")[1].split("</CONDITIONS>")[0]
        conditions = conditions.strip()

        self.logger.log_success("Branch reasoning module completed.")
        return branch_response, conditions

