"""Check cross-device project recovery without reading secrets or downloading assets."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.machine_config import MachineConfig, load_machine_config


def command_output(args: list[str]) -> tuple[int, str]:
    try:
        process = subprocess.run(args, cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8")
    except OSError as exc:
        return 127, str(exc)
    return process.returncode, process.stdout.strip()


def path_status(path: Path, *, directory: bool | None = None) -> dict[str, Any]:
    exists = path.is_dir() if directory is True else path.is_file() if directory is False else path.exists()
    writable = bool(exists and os.access(path, os.W_OK))
    return {"path": str(path), "exists": exists, "writable": writable}


def asset_status(machine: MachineConfig) -> dict[str, Any]:
    required = {
        "main_venv": machine.main_venv,
        "docling_env": machine.docling_env,
        "docling_artifacts": machine.docling_artifacts,
    }
    optional = {
        "bge_model": machine.bge_model,
        "llama_cpp": machine.llama_cpp,
        "qwen4_model": machine.qwen4_model,
        "qwen9_model": machine.qwen9_model,
    }
    required_status = {name: path_status(path) for name, path in required.items()}
    optional_status = {name: path_status(path) for name, path in optional.items()}
    return {
        "required_for_next_stage": required_status,
        "optional_historical_assets": optional_status,
        "missing_required": [name for name, status in required_status.items() if not status["exists"]],
        "missing_optional": [name for name, status in optional_status.items() if not status["exists"]],
        "official_restore_note": "缺失大型资产时查看 artifacts/EXTERNAL_ASSETS.md；本脚本不下载模型或运行时。",
    }


def main() -> int:
    machine = load_machine_config()
    git_code, branch = command_output(["git", "branch", "--show-current"])
    _, status_text = command_output(["git", "status", "--short"])
    _, remote_text = command_output(["git", "remote"])
    python_path = machine.main_venv / "Scripts" / "python.exe"
    python_code, python_version = command_output([str(python_path), "--version"]) if python_path.exists() else (127, "missing")
    _, ignored_local = command_output(["git", "check-ignore", "config/machine.local.ini"])
    _, ignored_secret = command_output(["git", "check-ignore", "mimo.ini"])

    cache_status = {name: path_status(path, directory=True) for name, path in machine.cache_locations.items()}
    assets = asset_status(machine)
    secret_paths = {
        "mimo_config_exists": machine.mimo_config.exists(),
        "mimo_config_path": str(machine.mimo_config),
        "key_value_read": False,
    }
    notebooks_code, notebooks_status = command_output(["git", "status", "--short", "--", "notebooks/01_dataset_and_rag_structure.ipynb", "Untitled.ipynb"])
    report = {
        "project_root": str(PROJECT_ROOT),
        "git": {
            "branch": branch,
            "branch_check_passed": git_code == 0 and branch == "main",
            "working_tree_status": status_text.splitlines() if status_text else [],
            "remote_names": remote_text.splitlines() if remote_text else [],
            "remote_not_modified": True,
        },
        "machine_config": machine.to_public(),
        "main_environment": {
            **path_status(machine.main_venv, directory=True),
            "python": str(python_path),
            "python_exists": python_path.is_file(),
            "python_version": python_version,
            "python_check_exit": python_code,
        },
        "cache_locations": cache_status,
        "external_assets": assets,
        "secret_files": secret_paths,
        "gitignore_checks": {
            "machine_local_ini_ignored": bool(ignored_local),
            "mimo_ini_ignored": bool(ignored_secret),
            "key_content_read": False,
        },
        "notebooks_read_only_status": {
            "git_status_exit": notebooks_code,
            "status": notebooks_status.splitlines() if notebooks_status else [],
            "read_only_scan": True,
            "changed_by_this_script": False,
            "staged_by_this_script": False,
        },
    }
    report["next_stage_ready"] = bool(
        report["main_environment"]["python_exists"]
        and report["main_environment"]["python_check_exit"] == 0
        and not assets["missing_required"]
        and all(status["exists"] for status in cache_status.values())
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["next_stage_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
