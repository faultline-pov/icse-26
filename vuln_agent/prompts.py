from typing import List
from vuln_agent.tools import Tool
from pathlib import Path

"""
This file constructs the prompts used by the agent
"""

SYS_PROMPT = """You are a helpful AI assistant that can interact with a computer to solve tasks.

<ROLE>
Your primary role is to assist users by executing commands, modifying code, and solving technical problems effectively.
You should be thorough, methodical, and prioritize quality over speed.
Your code will never be read by humans, so focus on correctness, not style.
</ROLE>

<EFFICIENCY>
* Each action you take is somewhat expensive. Minimize unnecessary actions.
* When exploring the codebase, use the find and grep tools with appropriate filters to minimize unnecessary operations.
* You do not have access to the internet, so do not attempt to search online for information.
</EFFICIENCY>

<CODE_QUALITY>
* Write clean, efficient code with minimal comments. Avoid redundancy in comments: Do not repeat information that can be easily inferred from the code itself.
* When implementing solutions, focus on making the minimal changes needed to solve the problem.
* Before implementing any changes, first thoroughly understand the codebase through exploration.
* If you are adding a lot of code to a function or file, consider splitting the function or file into smaller pieces when appropriate.
</CODE_QUALITY>

<PROBLEM_SOLVING_WORKFLOW>
1. EXPLORATION: Thoroughly explore relevant files and understand the context before proposing solutions
2. ANALYSIS: Consider multiple approaches and select the most promising one
3. IMPLEMENTATION: Make focused, minimal changes to address the problem
</PROBLEM_SOLVING_WORKFLOW>

<TROUBLESHOOTING>
* If you've made repeated attempts to solve a problem but tests still fail or the user reports it's still broken:
  1. Step back and reflect on 5-7 different possible sources of the problem
  2. Assess the likelihood of each possible cause
  3. Methodically address the most likely causes, starting with the highest probability
  4. Document your reasoning process
</TROUBLESHOOTING>
"""

def construct_tool_prompt(tools: List[Tool]) -> str:
    """
    Constructs the tool prompt for the agent.
    Args:
        tools (List[Tool]): List of tools to be used by the agent.
    Returns:
        str: Formatted string containing the tool prompt.
    """
    tool_prompt = "The following tools are available:\n"
    for tool in tools:
        tool_prompt += f"- {tool.get_name()}: {tool.get_description()}\n"
        tool_prompt += f"  Usage:\n{tool.get_usage()}\n"
    tool_prompt += "\n"
    tool_prompt += "If you emit output in one of the above formats, you will get the output of the corresponding tool as a reply.\n"
    tool_prompt += "Note that each tool invocation must be in a separate reply! You can only invoke one tool per turn.\n"
    tool_prompt += f"The current working directory is {Path.cwd()}\n"

    return tool_prompt

def construct_issue_desc_prompt(issue_desc: str, issue_summary: str, diff: str) -> str:
    """
    Constructs the issue description prompt for the agent.
    """
    desc_str = f"\"Summary: {issue_summary}\nDescription: {issue_desc}\"" if issue_summary else f"\"{issue_desc}\""
    prompt = (
        f"The project I am working with has a vulnerability, reported as a CWE. The issue description says:\n"
        f"{desc_str}\n"
        "You do not have access to the internet or GitHub to look up more details.\n"
        "There are no vulnerability reports in the project directory either.\n"
    )
    if diff:
        prompt += (
        "```\n"
        "Here is the patch that fixed the vulnerability:\n"
        f"{diff}\n"
        "```\n"
        )
    return prompt

def construct_docker_instructions(dataset: str, workdir: str) -> str:
    if dataset == 'cwe-bench-java':
        docker_instructions = f"""
The project is built and run as a Docker container, and the Dockerfile is at `{workdir}/Dockerfile.vuln`.
All the build dependencies for the project are already installed in `Dockerfile.vuln`.
However, if you need any new dependencies, you can add them to `Dockerfile.vuln`.
Make sure to not modify any of the lines in the Dockerfile above \"# Do not modify anything above this line\".
The entire project directory is copied into the Docker container, so you don't need to write any new COPY commands in the Dockerfile.
The command to run the test should be the `CMD` command in `Dockerfile.vuln`, so that the test can be run with
`docker run -t imagename`.
"""
    elif dataset == 'primevul':
        docker_instructions = f"""
The project is built and run as a Docker container, and the Dockerfile is at `{workdir}/Dockerfile.vuln`.
The Dockerfile currently has some build dependencies, but you may need to add more.
Analyze the installation instructions in the project README or other documentation files, and add the necessary build/installation commands to `Dockerfile.vuln`.
The Dockerfile contains an instruction to copy the entire project directory into the Docker container, so you don't need to write any new COPY commands in the Dockerfile.
The command to run the test should be the `CMD` command in `Dockerfile.vuln`, so that the test can be run with
`docker run -t imagename`.
"""
    else:
        raise ValueError(f"Unsupported dataset {dataset}. Supported datasets are: ['cwe-bench-java', 'primevul']")
    return docker_instructions