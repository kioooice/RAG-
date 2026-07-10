"""只读输出本项目关心的环境信息，不执行安装或系统修改。"""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path


PORTS = (6333, 8000, 8501, 8888)


def command_output(command: list[str]) -> dict[str, object]:
    """运行只读版本查询；命令缺失时返回明确状态。"""
    executable = shutil.which(command[0])
    if executable is None:
        return {"available": False, "path": None, "output": "command not found"}
    try:
        if Path(executable).suffix.lower() in {".cmd", ".bat"}:
            actual_command = [
                os.environ.get("ComSpec", "cmd.exe"),
                "/d",
                "/c",
                executable,
                *command[1:],
            ]
        else:
            actual_command = [executable, *command[1:]]
        result = subprocess.run(
            actual_command,
            capture_output=True,
            timeout=15,
            check=False,
        )
        raw_output = result.stdout or result.stderr
        encoding = "utf-16-le" if b"\x00" in raw_output else "utf-8"
        output = raw_output.decode(encoding, errors="replace").strip()
        return {
            "available": result.returncode == 0,
            "path": executable,
            "returncode": result.returncode,
            "output": output,
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "path": executable, "output": str(exc)}


def port_is_free(port: int) -> bool:
    """尝试绑定本机回环地址；成功表示当前端口可用于本地实验。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def drive_usage(path: Path) -> dict[str, float]:
    usage = shutil.disk_usage(path)
    gb = 1024**3
    return {
        "total_gb": round(usage.total / gb, 2),
        "used_gb": round(usage.used / gb, 2),
        "free_gb": round(usage.free / gb, 2),
    }


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    report = {
        "project_root": str(project_root),
        "platform": platform.platform(),
        "windows_version": platform.win32_ver(),
        "configured_command_shell": os.environ.get("ComSpec", "unknown"),
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "prefix": sys.prefix,
            "base_prefix": sys.base_prefix,
        },
        "disk_for_project": drive_usage(project_root),
        "commands": {
            "git": command_output(["git", "--version"]),
            "code": command_output(["code", "--version"]),
            "pwsh": command_output(["pwsh", "--version"]),
            "jupyter": command_output(["jupyter", "--version"]),
            "jupyter_in_current_python": command_output([sys.executable, "-m", "jupyter", "--version"]),
            "docker": command_output(["docker", "--version"]),
            "docker_compose": command_output(["docker", "compose", "version"]),
            "wsl": command_output(["wsl", "--version"]),
            "nvidia_smi": command_output(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,memory.free,driver_version",
                    "--format=csv,noheader",
                ]
            ),
            "nvcc": command_output(["nvcc", "--version"]),
        },
        "ports": {str(port): "free" if port_is_free(port) else "occupied" for port in PORTS},
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
