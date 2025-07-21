from vuln_agent.helpers import *
from vuln_agent.modules import *
from vuln_agent.models import get_model_from_name
from vuln_agent.conversation import Conversation
from vuln_agent.prompts import *

class AgentEngine:

    def __init__(self,
                dataset: str,
                project: str,
                model: str,
                workdir: str,
                logger: Logger,
                budget: float = 5.0,
                timeout: int = 3600,
                use_patch: bool = False,
                no_flow: bool = False,
                no_branch: bool = False):
        
        self.dataset = dataset
        self.project = project
        self.model = get_model_from_name(model, logger)
        self.workdir = Path(workdir)
        self.logger = logger
        self.budget = budget
        self.timeout = timeout
        self.use_patch = use_patch
        self.no_flow = no_flow
        self.no_branch = no_branch
        self.setup() # Sets up source_manager and target_manager

    def setup(self):

        assert Path(self.workdir).exists(), f"Code directory {self.workdir} does not exist"
        os.chdir(self.workdir)
        self.logger.log_status("Working in directory: {}".format(self.workdir.absolute()))
        run("docker rmi -f vulnerability-test && docker image prune -f", timeout=300, logger=self.logger)

    def reset(self):

        files_to_preserve = [
            ".build_diff.patch",
            ".Dockerfile.backup",
            "Dockerfile.vuln",
        ]
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
        
        self.logger.log_status("Reset working directory to clean state.")

    def run(self):

        self.reset()
        conversation = Conversation(self.model, self.logger, temperature=0.3, budget=self.budget, timeout=self.timeout)
        conversation.add_message("system", SYS_PROMPT)


        if not self.no_flow:
            flow_reasoning = FlowReasoning(self.model,
                                        self.dataset,
                                        self.project,
                                        self.workdir,
                                        self.logger,
                                        init_conversation=conversation,
                                        use_patch=self.use_patch,
                                        max_turns=100)
            flow = flow_reasoning.run()
            if not flow:
                self.logger.log_failure("Flow reasoning failed.")
                self.logger.log_result({f"flow_reasoning": "failure"})
                return
            self.logger.log_result({f"flow_reasoning": "success"})
        else:
            self.logger.log_status("Flow reasoning is disabled, skipping flow analysis.")
            flow = None

        if not self.no_branch:
            self.reset()
            conversation = Conversation(self.model, self.logger, temperature=0.3, budget=self.budget, timeout=self.timeout)
            conversation.add_message("system", SYS_PROMPT)

            branch_reasoning = BranchReasoning(self.model,
                                            self.dataset,
                                            self.project,
                                            self.workdir,
                                            self.logger,
                                            init_conversation=conversation,
                                            max_turns=100)
            branches, conditions = branch_reasoning.run(flow)
            if not branches:
                self.logger.log_failure("Branch reasoning failed.")
                self.logger.log_result({f"branch_reasoning": "failure"})
                return
            self.logger.log_result({f"branch_reasoning": "success"})
        else:
            self.logger.log_status("Branch reasoning is disabled, skipping branch analysis.")
            branches = None
            conditions = None

        self.reset()
        conversation = Conversation(self.model, self.logger, temperature=0.3, budget=self.budget, timeout=self.timeout)
        conversation.add_message("system", SYS_PROMPT)

        test_gen = TestGen(self.model,
                        self.dataset,
                        self.project,
                        self.workdir,
                        self.logger,
                        init_conversation=conversation,
                        flow=flow,
                        conditions=conditions,
                        max_turns=100)
        status = test_gen.run()

        if status == "Failure":
            self.logger.log_failure("Test generation failed.")
            self.logger.log_result({f"test_gen": "failure"})
            return
        self.logger.log_result({f"test_gen": "success"})

        validation = Validation(self.dataset, self.project, self.workdir, self.logger)

        for repair_attempt in range(5):
            start_time = time.time()
            start_time_str = f"{datetime.datetime.now()}"
            feedback = validation.validate()
            elapsed_time = time.time() - start_time
            self.logger.log_action({
                'type': 'validation',
                'start_time': start_time_str,
                'elapsed_time': elapsed_time,
            })
            if feedback['status'] == "Correct":
                self.logger.log_success("Validation passed.")
                self.logger.log_result({"validation": "success"})
                return
            elif feedback['status'] == "Incorrect":
                self.logger.log_status("Giving feedback to test generation module...")
                self.logger.log_result({"validation": "incorrect"})
                test_gen.repair(feedback['error'])
            elif feedback['status'] == "Failed":
                self.logger.log_failure("Validation failed due to an internal error.")
                self.logger.log_result({"validation": "failure"})
                break
        
        start_time = time.time()
        start_time_str = f"{datetime.datetime.now()}"
        feedback = validation.validate()
        elapsed_time = time.time() - start_time
        self.logger.log_action({
            'type': 'validation',
            'start_time': start_time_str,
            'elapsed_time': elapsed_time,
        })
        if feedback['status'] == "Correct":
            self.logger.log_success("Validation passed.")
            self.logger.log_result({"validation": "success"})
            return
        elif feedback['status'] == "Incorrect":
            self.logger.log_status("Validation incorrect...")
            self.logger.log_result({"validation": "incorrect"})
        elif feedback['status'] == "Failed":
            self.logger.log_failure("Validation failed due to an internal error.")
            self.logger.log_result({"validation": "failure"})
                    

    def print_results(self):
        pass
