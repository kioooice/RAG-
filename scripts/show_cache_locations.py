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
    report = {
        "cache_environment": {
            name: path_status(os.environ.get(name)) for name in CACHE_VARIABLES
        },
        "disk_space": {"C": disk_status("C:\\"), "D": disk_status("D:\\")},
        "python": {"executable": sys.executable, "prefix": sys.prefix, "base_prefix": sys.base_prefix},
        "jupyter_kernel": kernel_status(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
