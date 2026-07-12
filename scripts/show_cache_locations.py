"""输出项目缓存、磁盘、解释器和 Jupyter Kernel 的实际位置。"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


CACHE_VARIABLES = (
    "HF_HOME",
    "HF_HUB_CACHE",
    "HF_DATASETS_CACHE",
    "TRANSFORMERS_CACHE",
    "TORCH_HOME",
    "PIP_CACHE_DIR",
)
KERNEL_NAME = "retrieval-adaptation-lab"


def path_status(value: str | None) -> dict[str, object]:
    if not value:
        return {"value": None, "path": None, "exists": False, "writable": False}
    path = Path(value).expanduser().resolve()
    writable = False
    if path.is_dir():
        try:
            with tempfile.NamedTemporaryFile(dir=path, prefix=".write-test-", delete=True):
                writable = True
        except OSError:
            writable = False
    return {"value": value, "path": str(path), "exists": path.exists(), "writable": writable}


def disk_status(root: str) -> dict[str, object]:
    path = Path(root)
    if not path.exists():
        return {"path": root, "exists": False}
    usage = shutil.disk_usage(path)
    return {
        "path": root,
        "exists": True,
        "free_bytes": usage.free,
        "free_gib": round(usage.free / 1024**3, 2),
    }


def kernel_status() -> dict[str, object]:
    try:
        from jupyter_client.kernelspec import KernelSpecManager

        manager = KernelSpecManager()
        spec = manager.get_kernel_spec(KERNEL_NAME)
    except Exception as exc:
        return {"name": KERNEL_NAME, "available": False, "error": str(exc)}
    return {
        "name": KERNEL_NAME,
        "available": True,
        "resource_dir": spec.resource_dir,
        "argv": spec.argv,
        "interpreter": spec.argv[0] if spec.argv else None,
    }


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    from src.machine_config import load_machine_config

    machine = load_machine_config()
    drive_roots = {"project_drive": Path(project_root.anchor), "asset_drive": Path(machine.ai_lab_root.anchor)}
    report = {
        "project_root": str(project_root),
        "machine_config": machine.to_public(),
        "cache_environment": {
            name: path_status(os.environ.get(name)) for name in CACHE_VARIABLES
        },
        "configured_cache_locations": {
            name: path_status(str(path)) for name, path in machine.cache_locations.items()
        },
        "disk_space": {name: disk_status(str(path)) for name, path in drive_roots.items()},
        "python": {"executable": sys.executable, "prefix": sys.prefix, "base_prefix": sys.base_prefix},
        "jupyter_kernel": kernel_status(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
