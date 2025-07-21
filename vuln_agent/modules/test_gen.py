from vuln_agent.prompts import *
from vuln_agent.tools import *
from vuln_agent.helpers import *
from vuln_agent.conversation import Conversation

class Run(Tool):

    def __init__(self, dataset, project_name, workdir, logger):
        """
        Initializes the Run tool.
        This tool builds and runs the docker image for the project.
        """
        self.dataset = dataset
        self.project_name = project_name
        self.workdir = workdir
        self.logger = logger

    def get_name(self):
        return "run"

    def get_description(self):
        return "Builds and runs the docker image for the project."

    def get_usage(self):
        return ('<TOOL>\n'
                '{"name": "run"}\n'
                '</TOOL>\n')

    def execute(self, param_dict: str):
        CAUTION_MSG=f"""Carefully analyze this output for errors or messages that can help you debug your test.
If it is not the behavior you expected:
1. Step back and reflect on 5-7 different possible sources of the problem
2. Assess the likelihood of each possible cause
3. Methodically address the most likely causes, starting with the highest probability
4. If necessary, add print statements to the source code to debug the issue

If you are having issues with Docker "refsums", remember that you don't need to add any new COPY commands in the Dockerfile.
If your Docker build is timing out, try using the Reset tool to reset the working directory and start from scratch.

Lastly, remember that your test should actually run the vulnerable code in the project.
- It should NOT read the source code to check for the presence of a vulnerability.
- It should NOT \"simulate\" the vulnerability by running some separate code that does not use the project.
"""
        os.chdir(self.workdir)
        context_root = "../.." if self.dataset == 'cwe-bench-java' else "."
        # Check if there are other keys in the param_dict
        for key in param_dict.keys():
            if key not in ["name"]:
                return {"status": "Failure", "output": f"Unknown field '{key}'"}
        try:
            run(f"docker build -f ./Dockerfile.vuln -t {self.project_name.lower()}_vuln {context_root}",
                timeout=300,
                logger=self.logger)
        except RunException as e:
            return {"status": "Success", "output": f"Build failed: {truncate_reverse(str(e), 10000)}\n{CAUTION_MSG}"}
        self.logger.log_status("Docker image built successfully.")
        try:
            stdout = run(f"docker run --rm {self.project_name.lower()}_vuln",
                timeout=200,
                logger=self.logger)
            return {"status": "Success", "output": f"Run succeeded. STDOUT:\n{truncate_reverse(stdout, 10000)}\n{CAUTION_MSG}"}
        except RunException as e:
            return {"status": "Success", "output": f"Run exited with non-zero code.\n{truncate_reverse(str(e), 10000)}\n{CAUTION_MSG}"}

class Reset(Tool):

    def __init__(self, workdir, logger):
        """
        Initializes the Reset tool.
        This tool resets the working directory to the initial state.
        """
        self.workdir = workdir
        self.logger = logger

    def get_name(self):
        return "reset"

    def get_description(self):
        return "Resets the working directory to the initial state."

    def get_usage(self):
        return ('<TOOL>\n'
                '{"name": "reset"}\n'
                '</TOOL>\n')
    
    def execute(self, param_dict: str):
        files_to_preserve = [
            ".build_diff.patch",
            ".Dockerfile.backup",
            "Dockerfile.vuln",
        ]

        # Check if there are other keys in the param_dict
        for key in param_dict.keys():
            if key not in ["name"]:
                return {"status": "Failure", "output": f"Unknown field '{key}'"}

        os.chdir(self.workdir)
        try:
            run("git stash", logger=self.logger)
            result = run("git ls-files --others --exclude-standard", logger=self.logger)
            created_files = result.strip().splitlines()
            created_files = [f for f in created_files if f.strip() not in files_to_preserve]
        except RunException as e:
            return {"status": "Failure", "output": f"Reset failed."}

        for f in created_files:
            Path(self.workdir / f).unlink()

        # Restore Dockerfile from backup
        dockerfile_backup = self.workdir / ".Dockerfile.backup"
        if dockerfile_backup.exists():
            if (self.workdir / "Dockerfile.vuln").exists():
                Path(self.workdir / "Dockerfile.vuln").unlink()
            shutil.copy(dockerfile_backup, self.workdir / "Dockerfile.vuln")
            
        return {"status": "Success", "output": "Working directory reset successfully."}


class TestGen:
    def __init__(self, model, dataset, project_name, workdir, logger, init_conversation, flow, conditions, max_turns=50):
        self.model = model
        self.dataset = dataset
        self.project_name = project_name
        self.workdir = workdir
        self.logger = logger
        self.max_turns = max_turns
        self.conversation = init_conversation
        self.flow = flow
        self.conditions = conditions

        self.tools = [tool_class(self.logger) for tool_class in [ListDir, Read, Grep, Find, Write, Mkdir]]
        self.tools += [Run(dataset, project_name, workdir, logger), Reset(workdir, logger)]
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
                return None, None
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
    
    def run(self):
        """
        Run the test generation module.
        """
        self.logger.log_status("Running test generation module...")

        cwe_ids, issue_desc, issue_summary = self.get_issue_details()
        if not issue_desc:
            self.logger.log_failure("Failed to retrieve issue details.")
            return

        cwe_to_instruction = {
            "CWE-22": ("This is a Path Traversal vulnerability (CWE-22). "
                    "The test case must call an externally accessible API of the project with appropriate inputs, such that "
                    "it reads from or writes to at least one file outside the project directory."),
            "CWE-78": ("This is a Command Injection vulnerability (CWE-78). "
                    "The test case must call an externally accessible API of the project with appropriate inputs, such that "
                    "it executes a shell command that is not intended by the application."),
            "CWE-79": ("This is a Cross-Site Scripting (XSS) vulnerability (CWE-79). "
                    "The test case must call an externally accessible API of the project "
                    "with an input that contains scripting code, and show that this input is not santized properly."),
            "CWE-94": ("This is a Code Injection vulnerability (CWE-94). "
                    "The test case must call an externally accessible API of the project with appropriate inputs, such that "
                    "it executes some code that is not intended by the application."),
        }
        cwe_desc = None
        for cwe in cwe_ids:
            if cwe in cwe_to_instruction:
                cwe_desc = cwe_to_instruction[cwe]
                break
        if cwe_desc is None:
            raise ValueError(f"Unsupported CWE ID(s) {cwe_ids} for project {args.project}. Supported CWE IDs are: {list(cwe_to_instruction.keys())}")

        docker_instructions = construct_docker_instructions(self.dataset, self.workdir)
            
        # Construct the prompt
        prompt = construct_issue_desc_prompt(issue_desc, issue_summary, diff=None)
        prompt += f"""
Now create a test case that FAILS (exits with non-zero code) if the vulnerability EXISTS,
and PASSES (exits with code 0) if the vulnerability DOES NOT EXIST.
{cwe_desc}
This test should actually run the vulnerable code in the project.
- It should NOT read the source code to check for the presence of a vulnerability.
- It should NOT \"simulate\" the vulnerability by running some separate code that does not use the project.

{f"Here is a flow consisting of a sequence of program points to reach the vulnerability:\n{self.flow}" if self.flow else ""}

The test should start from the vulnerability 'source' and reach the 'sink'.
It should be designed such that it passes through all the branch conditions on the way.
{f"This means that the input and method calls should be carefully crafted, satisfying the following conditions:\n{self.conditions}" if self.conditions else ""}

{docker_instructions}

Feel free to create any new files to create the test case.
You are highly encouraged to insert print statements in the existing source files to debug your test.
Remember the branch conditions and flow that you derived earlier, and use them to guide your test generation and debugging process.

Once you verify that the flow has reached the 'sink', you should analyze the observed behavior of the program
to ensure that the test FAILS if the vulnerability exists, and PASSES if it does not exist.
To re-emphasize, this test should NOT be based on reading the source code, but rather on the actual behavior of the program when it is run.
If I fix the vulnerability in the project, the test should PASS.
"""
        prompt += construct_tool_prompt(self.tools)
        prompt += ("If you successfully generate the test case and confirm that it satisfies all the above conditions, "
                   "respond <DONE>.")

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
                    if "File written successfully" in tool_output['output']:
                        self.conversation.add_message("user", "If you have finished generating your test, use the Run tool to check it.")
                        self.logger.log_status("If you have finished generating your test, use the Run tool to check it.")
                else:
                    self.conversation.add_message("user", f"Tool invocation failed: {tool_output['output']}")
                    self.logger.log_status(f"Tool invocation failed: {tool_output['output']}")
            elif "<DONE>" in response:
                self.logger.log_status("Test generation completed.")
                break
            else:
                continue_message = ("Your output doesn't contain a <TOOL>...</TOOL> invocation."
                                    " If you have generated, run and checked your test, respond <DONE>.")
                self.conversation.add_message("user", continue_message)
                self.logger.log_status(continue_message)

        if self.conversation.messages[-1]['role'] != "assistant":
            self.logger.log_failure("Test generation failed to produce a valid response.")
            return "Failure"

        if "<DONE>" in self.conversation.messages[-1]['content']:
            self.logger.log_success("Test generation completed successfully.")
            return "Success"
        else:
            self.logger.log_failure("Test generation failed to produce a valid test case.")
            return "Failure"


    def repair(self, feedback):
        """
        Repair the test case based on feedback.
        """
        if len(self.conversation.messages) == 0:
            self.logger.log_failure("No conversation history to repair.")
            return
        
        prompt = (
            "The test you generated had the following error:\n"
            f"{feedback}\n"
            "Please fix the test case. Carefully analyze this output for errors or messages that can help you debug your test. "
            "Reason step-by-step about what might have gone wrong, and how you can fix it.\n"
            "You can use the <TOOL>...</TOOL> format to invoke tools, and you can also add new files.\n"
            "When you have generated, run and checked your test again, respond with a message containing the string \"<DONE>\".\n"
            "Remember that the test should actually run the vulnerable code in the project, "
            "- It should NOT read the source code to check for the presence of a vulnerability.\n"
            "- It should NOT \"simulate\" the vulnerability by running some separate code that does not use the project.\n"
        )

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
                    if "File written successfully" in tool_output['output']:
                        self.conversation.add_message("user", "If you have finished generating your test, use the Run tool to check it.")
                        self.logger.log_status("If you have finished generating your test, use the Run tool to check it.")
                else:
                    self.conversation.add_message("user", f"Tool invocation failed: {tool_output['output']}")
                    self.logger.log_status(f"Tool invocation failed: {tool_output['output']}")
            elif "<DONE>" in response:
                self.logger.log_status("Repair completed.")
                break
            else:
                continue_message = ("Your output doesn't contain a <TOOL>...</TOOL> invocation."
                                    " If you have generated, run and checked your test, respond <DONE>.")
                self.conversation.add_message("user", continue_message)
                self.logger.log_status(continue_message)

        if self.conversation.messages[-1]['role'] != "assistant":
            self.logger.log_failure("Repair failed to produce a valid response.")
            return
        self.logger.log_success("Repair completed.")
        return