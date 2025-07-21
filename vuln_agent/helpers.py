import argparse
import shutil
import os
from pathlib import Path
import subprocess
import json
import networkx as nx
import datetime
from typing import List, Dict, Tuple
import textwrap
import docker
import socket
import pathlib
import time
import signal

def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
def prGreen(skk): print("\033[92m {}\033[00m" .format(skk))
def prCyan(skk): print("\033[96m {}\033[00m" .format(skk))
def prYellow(skk): print("\033[93m {}\033[00m" .format(skk))
def prLightPurple(skk): print("\033[94m {}\033[00m" .format(skk))
def prLightGray(skk): print("\033[97m {}\033[00m" .format(skk))

class CompileException(Exception):
    pass

class RunException(Exception):
    pass

class Logger:

    def __init__(self, output_dir, args, verbose=False):
        self.output_dir = Path(output_dir)
        self.args = args
        self.verbose = verbose
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)
        self.output_file = Path(self.output_dir)/'output.txt'
        if self.output_file.exists():
            self.output_file.unlink()
        self.output_file.touch()
        self.log_file = Path(self.output_dir, 'log.json')
        self.log = {'date': f"{datetime.datetime.now()}",
                    'args': vars(args),
                    'actions': [],
                    'results': []}
        with open(self.log_file, 'w') as f:
            f.write(json.dumps(self.log, indent=4))
        self.total_cost = 0.0
        self.total_time = 0.0
    
    def log_action(self, action):
        if 'cost' in action:
            self.total_cost += action['cost']
        if 'elapsed_time' in action:
            self.total_time += action['elapsed_time']
        action['accumulated_cost'] = self.total_cost
        action['accumulated_time'] = self.total_time
        self.log['actions'].append(action)
        with open(self.log_file, 'w') as f:
            f.write(json.dumps(self.log, indent=4))
    
    def log_result(self, result):
        self.log['results'].append(result)
        with open(self.log_file, 'w') as f:
            f.write(json.dumps(self.log, indent=4))
    
    def log_status(self, output):
        prCyan(output)
        with open(self.output_file, 'a') as f:
            f.write(f"{output}\n")
    
    def log_failure(self, output):
        prRed(output)
        with open(self.output_file, 'a') as f:
            f.write(f"{output}\n")
    
    def log_success(self, output):
        prGreen(output)
        with open(self.output_file, 'a') as f:
            f.write(f"{output}\n")
    
    def log_output(self, output):
        if self.verbose:
            prLightGray(output)
        with open(self.output_file, 'a') as f:
            f.write(f"{output}\n")

    def get_results(self):
        return self.log['results']
    
    def get_cost_and_time(self):
        return self.total_cost, self.total_time
        

class DummyLogger(Logger):
    def __init__(self):
        self.output_file = None
        self.log_file = None
        self.log = {'date': f"{datetime.datetime.now()}",
                    'args': {},
                    'actions': [],
                    'results': []}
    
    def log_action(self, action):
        print(action)
    
    def log_result(self, result):
        pass

    def get_results(self):
        return []
    
    def log_status(self, output):
        print(output)
    
    def log_failure(self, output):
        print(output)
    
    def log_success(self, output):
        print(output)
    
    def log_output(self, output):
        print(output)
    
    def get_cost_and_time(self):
        return 0.0, 0.0

def truncate(text: str, max_length: int, start_line: int = 1) -> str:
    if len(text) > max_length:
        trunc_text = text[:max_length]
        trunc_start = start_line + len(text[:max_length].split('\n')) - 1
        trunc_end = start_line + len(text.split('\n')) - 1
        trunc_text += f"\n...(Lines {trunc_start} to {trunc_end} truncated)\n"
        return trunc_text
    return text

def truncate_reverse(text: str, max_length: int) -> str:
    if len(text) > max_length:
        trunc_text = text[-max_length:]
        trunc_text = f"(First {len(text[:-max_length].split('\n'))} lines truncated)...\n" + trunc_text
        return trunc_text
    return text

def is_hidden_directory(path):
    """Checks if any part of the path refers to a hidden directory (Unix-like convention)."""
    parts = path.split(os.sep)
    for part in parts:
        if part.startswith('.') and part not in ('.', '..'): # Exclude current and parent directory references
            return True
    return False

def run(command, timeout=120, logger=None):
    if logger:
        logger.log_status(f"Running command: {command}")

    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # Start new process group (Unix only)
        )

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)  # Kill the whole process group
            proc.wait()  # Avoid zombie
            raise RunException("Timeout")

        stdout_decoded = stdout.decode('utf-8', errors='ignore') if stdout else ''
        stderr_decoded = stderr.decode('utf-8', errors='ignore') if stderr else ''

        if proc.returncode != 0:
            # if logger:
                # logger.log_output(f"STDOUT:\n{stdout_decoded}\nSTDERR:\n{stderr_decoded}")
            raise RunException(f"STDOUT:\n{stdout_decoded}\nSTDERR:\n{stderr_decoded}")

        # if logger:
            # logger.log_output(stdout_decoded)

        return stdout_decoded

    except Exception as e:
        raise RunException(str(e))

def to_host_path(path):
    if not os.path.exists('/.dockerenv'):
        return path
    
    # We are inside a Docker container
    client          = docker.DockerClient(base_url='unix:///var/run/docker.sock')
    container_id    = socket.gethostname()
    container       = client.containers.get(container_id)
    mounts          = container.attrs['Mounts']

    mount_path_len = 0
    host_path = None
    # Find the mount that is the longest prefix of path
    for mount in mounts:
        if path.is_relative_to(Path(mount['Destination'])):
            if len(Path(mount['Destination']).parts) > mount_path_len:
                mount_path_len = len(Path(mount['Destination']).parts)
                host_path = Path(mount['Source'])/path.relative_to(Path(mount['Destination']))
    return host_path

def compare_fnames(a, b, base_dir):
    a, b, base_dir = Path(a), Path(b), Path(base_dir)
    if a.is_absolute():
        a = a.relative_to(base_dir)
    if b.is_absolute():
        b = b.relative_to(base_dir)
    return a == b