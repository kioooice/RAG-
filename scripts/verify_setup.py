"""验证第一阶段项目环境、目录、Notebook 与基本安全边界。"""

from __future__ import annotations

import importlib
import json
import nbformat
import os
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VENV = PROJECT_ROOT / ".venv"

REQUIRED_IMPORTS = {
    "jupyter": "jupyter",
    "ipykernel": "ipykernel",
    "numpy": "numpy",
    "pandas": "pandas",
    "scikit-learn": "sklearn",
    "matplotlib": "matplotlib",
    "datasets": "datasets",
}

REQUIRED_PATHS = [
    "README.md",
    "ROADMAP.md",
    "AGENTS.md",
    ".gitignore",
    "requirements.in",
    "requirements.txt",
    "notebooks/01_dataset_and_rag_structure.ipynb",
    "data/raw",
    "data/processed",
    "data/evaluation",
    "src/ingestion",
    "src/embedding",
    "src/retrieval",
    "src/generation",
    "src/evaluation",
    "src/finetuning",
    "experiments/configs",
    "experiments/results",
    "experiments/reports",
    "experiments/reports/migration_to_study.md",
    "scripts/check_environment.py",
    "scripts/show_cache_locations.py",
    "scripts/start_lab.ps1",
    "scripts/verify_setup.py",
    ".vscode/settings.json",
    ".vscode/extensions.json",
    "app",
    "models",
]

WRITABLE_DIRECTORIES = ["data", "experiments", "models"]
IGNORED_DIRECTORY_NAMES = {".git", ".venv", "__pycache__", ".ipynb_checkpoints"}
MODEL_EXTENSIONS = {".bin", ".ckpt", ".gguf", ".onnx", ".pt", ".pth", ".safetensors"}
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    "Hugging Face token": re.compile(r"\bhf_[A-Za-z0-9]{16,}\b"),
    "AWS access key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
}


class Verification:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def check(self, condition: bool, success: str, failure: str) -> None:
        if condition:
            print(f"[PASS] {success}")
        else:
            self.failures.append(failure)
            print(f"[FAIL] {failure}")


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def project_files() -> list[Path]:
    files: list[Path] = []
    for root, directories, filenames in os.walk(PROJECT_ROOT):
        directories[:] = [name for name in directories if name not in IGNORED_DIRECTORY_NAMES]
        files.extend(Path(root) / filename for filename in filenames)
    return files


def verify_notebook(checks: Verification) -> None:
    notebook_path = PROJECT_ROOT / "notebooks/01_dataset_and_rag_structure.ipynb"
    try:
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        nbformat.validate(nbformat.from_dict(notebook))
    except (OSError, json.JSONDecodeError) as exc:
        checks.check(False, "", f"Notebook 不是有效 JSON：{exc}")
        return
    except nbformat.ValidationError as exc:
        checks.check(False, "", f"Notebook 不符合 nbformat：{exc}")
        return
    valid = (
        notebook.get("nbformat") == 4
        and isinstance(notebook.get("cells"), list)
        and len(notebook["cells"]) > 0
        and all(cell.get("cell_type") in {"markdown", "code", "raw"} for cell in notebook["cells"])
    )
    checks.check(valid, "Notebook 存在且通过 nbformat 4 结构验证", "Notebook JSON 结构不完整")


def verify_safety(checks: Verification) -> None:
    misplaced_models: list[str] = []
    large_files: list[str] = []
    secret_hits: list[str] = []

    for path in project_files():
        relative = path.relative_to(PROJECT_ROOT)
        if path.suffix.lower() in MODEL_EXTENSIONS:
            misplaced_models.append(str(relative))
        if path.stat().st_size > 100 * 1024 * 1024:
            large_files.append(str(relative))
        if path.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                secret_hits.append(f"{relative} ({label})")

    checks.check(not misplaced_models, "未发现模型权重格式文件", f"发现疑似模型权重：{misplaced_models}")
    checks.check(not large_files, "未发现超过 100 MB 的项目文件", f"发现大型文件：{large_files}")
    checks.check(not secret_hits, "未发现常见密钥或 Token 模式", f"发现疑似密钥：{secret_hits}")


def main() -> int:
    checks = Verification()

    checks.check(
        sys.prefix != sys.base_prefix and is_inside(Path(sys.executable), EXPECTED_VENV),
        f"Python 来自项目虚拟环境：{sys.executable}",
        f"必须使用 {EXPECTED_VENV} 内的 Python，当前是 {sys.executable}",
    )

    for label, module_name in REQUIRED_IMPORTS.items():
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # 导入失败类型取决于具体二进制依赖
            checks.check(False, "", f"依赖 {label} 导入失败：{exc}")
        else:
            checks.check(True, f"依赖可导入：{label}", "")

    for relative in REQUIRED_PATHS:
        checks.check((PROJECT_ROOT / relative).exists(), f"路径存在：{relative}", f"缺少路径：{relative}")

    verify_notebook(checks)

    for relative in WRITABLE_DIRECTORIES:
        path = PROJECT_ROOT / relative
        checks.check(path.is_dir() and os.access(path, os.W_OK), f"目录可写：{relative}", f"目录不可写：{relative}")

    verify_safety(checks)

    if checks.failures:
        print(f"\n验证失败：{len(checks.failures)} 项。")
        return 1
    print("\n验证通过：项目环境、结构、Notebook 和安全检查均符合第一阶段要求。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
