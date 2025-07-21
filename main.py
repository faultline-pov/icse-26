from vuln_agent.core.engine import AgentEngine
from vuln_agent.helpers import *

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Vuln Agent - generating vulnerability test cases')
    parser.add_argument('--dataset',    type=str,     default='cwe-bench-java', help='Dataset to use')
    parser.add_argument('--project',    type=str,     required=True,            help='Project to use')
    parser.add_argument('--model',      type=str,     default='claude37',       help='Model to use')
    parser.add_argument('--budget',     type=float,   default=5.0,              help='Budget in dollars')
    parser.add_argument('--timeout',    type=int,     default=2400,             help='Time budget in seconds')
    parser.add_argument('--use_patch',  action='store_true',                    help='Use patch file if available')
    parser.add_argument('--no_flow',   action='store_true',                    help='Disable flow analysis')
    parser.add_argument('--no_branch', action='store_true',                    help='Disable branch analysis')
    parser.add_argument('--verbose',    action='store_true',                    help='Enable verbose output')
    args = parser.parse_args()

    workdir_suffix = "_no_flow" if args.no_flow else ""
    workdir_suffix += "_no_branch" if args.no_branch else ""

    if args.dataset == 'cwe-bench-java' or args.dataset == 'primevul':
        project_dir = Path('data') / args.dataset / 'project-sources' / args.project
        workdir = Path('data') / args.dataset / f'workdir{workdir_suffix}'
        if not workdir.exists():
            workdir.mkdir(parents=True, exist_ok=True)
        if args.dataset == 'cwe-bench-java':
            java_env_dir = workdir / 'java-env'
            if not java_env_dir.exists():
                shutil.copytree('data/cwe-bench-java/java-env', java_env_dir)
            resources_dir = workdir / 'resources'
            if not resources_dir.exists():
                shutil.copytree('data/cwe-bench-java/resources', resources_dir)
        project_workdir = workdir / 'project-sources' / args.project
        if project_workdir.exists():
            print(f"Error: project workdir {project_workdir} already exists. Please remove it first.")
            exit(1)
        if not project_dir.exists():
            raise ValueError(f"Project {args.project} does not exist in {project_dir}")
        shutil.copytree(project_dir, project_workdir)
        project_workdir = Path(project_workdir).absolute()
        if not project_workdir.exists():
            raise ValueError(f"{project_workdir} does not exist after copying from {project_dir}")
    else:
        raise ValueError(f"Unknown dataset: {args.dataset}")
    
    timestr = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_folder = Path("logs") / f"{args.project}_{timestr}"
    if not log_folder.exists():
        log_folder.mkdir(parents=True, exist_ok=True)

    logger = Logger(log_folder.absolute(), args, verbose=args.verbose)

    engine = AgentEngine(dataset=args.dataset,
                        project=args.project,
                        model=args.model,
                        workdir=project_workdir,
                        logger=logger,
                        budget=args.budget,
                        timeout=args.timeout,
                        use_patch=args.use_patch,
                        no_flow=args.no_flow,
                        no_branch=args.no_branch)

    engine.run()
 
    engine.print_results()