import os
import platform
import subprocess
import json
from datetime import datetime

def run_cmd(cmd):
    try:
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        return result.decode(errors="ignore").strip()
    except Exception as e:
        return str(e)

def get_system_info():
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
    }

def get_wsl_info():
    return run_cmd("wsl -l -v")

def get_docker_info():
    return run_cmd("docker info")

def get_git_info():
    return run_cmd("git --version")

def get_project_tree():
    return run_cmd("find . -maxdepth 4 -type f")

def get_env_vars():
    keys = ["PATH", "VIRTUAL_ENV", "PYTHONPATH"]
    return {k: os.environ.get(k, "") for k in keys}

def scan_project_files():
    files = []
    for root, dirs, filenames in os.walk("."):
        for f in filenames:
            if f.endswith((".py", ".json", ".yml", ".yaml", ".env")):
                files.append(os.path.join(root, f))
    return files

def main():
    report = {
        "timestamp": datetime.now().isoformat(),
        "system": get_system_info(),
        "wsl": get_wsl_info(),
        "docker": get_docker_info(),
        "git": get_git_info(),
        "env": get_env_vars(),
        "project_files": scan_project_files(),
        "tree": get_project_tree(),
    }

    with open("dev_env_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\nRELATÓRIO GERADO: dev_env_report.json")

if __name__ == "__main__":
    main()
