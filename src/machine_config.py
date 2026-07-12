"""Portable, non-secret machine path configuration.

The repository contains the example only.  Each computer may create
``config/machine.local.ini`` (ignored by Git) or set ``MACHINE_CONFIG_PATH``.
No credential value is read here; secret loaders remain responsible for that.
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "machine.local.ini"
DEFAULT_AI_LAB_ROOT = Path("D:/AI-Lab")


def _path(value: str | None, fallback: Path, base: Path) -> Path:
    candidate = Path(value.strip()) if value and value.strip() else fallback
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate


@dataclass(frozen=True)
class MachineConfig:
    config_path: Path
    config_exists: bool
    ai_lab_root: Path
    cache_root: Path
    data_root: Path
    models_root: Path
    envs_root: Path
    runtimes_root: Path
    secrets_root: Path
    docling_artifacts: Path
    bge_model: Path
    llama_cpp: Path
    qwen4_model: Path
    qwen9_model: Path
    docling_env: Path
    bge_env: Path
    llama_env: Path
    round6_env: Path
    round7_env: Path

    @property
    def cache_locations(self) -> dict[str, Path]:
        return {
            "HF_HOME": self.cache_root / "huggingface",
            "HF_HUB_CACHE": self.cache_root / "huggingface" / "hub",
            "HF_DATASETS_CACHE": self.cache_root / "huggingface" / "datasets",
            "TRANSFORMERS_CACHE": self.cache_root / "huggingface" / "transformers",
            "TORCH_HOME": self.cache_root / "torch",
            "PIP_CACHE_DIR": self.cache_root / "pip",
        }

    @property
    def main_venv(self) -> Path:
        return PROJECT_ROOT / ".venv"

    @property
    def mimo_config(self) -> Path:
        return self.secrets_root / "retrieval-adaptation-lab" / "mimo.ini"

    @property
    def round5_runtime(self) -> Path:
        return self.llama_env

    @property
    def round6_runtime(self) -> Path:
        return self.round6_env

    @property
    def round7_runtime(self) -> Path:
        return self.round7_env

    def to_public(self) -> dict[str, object]:
        return {
            "config_path": str(self.config_path),
            "config_exists": self.config_exists,
            "ai_lab_root": str(self.ai_lab_root),
            "cache_root": str(self.cache_root),
            "data_root": str(self.data_root),
            "models_root": str(self.models_root),
            "envs_root": str(self.envs_root),
            "runtimes_root": str(self.runtimes_root),
            "secrets_root": str(self.secrets_root),
            "docling_artifacts": str(self.docling_artifacts),
            "bge_model": str(self.bge_model),
            "llama_cpp": str(self.llama_cpp),
            "qwen4_model": str(self.qwen4_model),
            "qwen9_model": str(self.qwen9_model),
            "docling_env": str(self.docling_env),
            "bge_env": str(self.bge_env),
            "llama_env": str(self.llama_env),
            "round6_env": str(self.round6_env),
            "round7_env": str(self.round7_env),
        }


def resolve_config_path() -> Path:
    override = os.environ.get("MACHINE_CONFIG_PATH", "").strip()
    return Path(override).expanduser() if override else DEFAULT_CONFIG_PATH


def load_machine_config() -> MachineConfig:
    config_path = resolve_config_path()
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str.lower
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                parser.read_file(handle)
        except (OSError, UnicodeError, configparser.Error):
            parser = configparser.ConfigParser(interpolation=None)
            parser.optionxform = str.lower

    configured_root = parser.get("machine", "ai_lab_root", fallback="").strip()
    root_value = os.environ.get("AI_LAB_ROOT", "").strip() or configured_root
    ai_lab_root = _path(root_value, DEFAULT_AI_LAB_ROOT, PROJECT_ROOT)
    paths = parser["paths"] if parser.has_section("paths") else {}
    assets = parser["assets"] if parser.has_section("assets") else {}
    environments = parser["environments"] if parser.has_section("environments") else {}

    cache_root = _path(os.environ.get("AI_LAB_CACHE") or paths.get("cache_root"), ai_lab_root / "cache", PROJECT_ROOT)
    data_root = _path(paths.get("data_root"), ai_lab_root / "data", PROJECT_ROOT)
    models_root = _path(paths.get("models_root"), ai_lab_root / "models", PROJECT_ROOT)
    envs_root = _path(paths.get("envs_root"), ai_lab_root / "envs", PROJECT_ROOT)
    runtimes_root = _path(paths.get("runtimes_root"), ai_lab_root / "runtimes", PROJECT_ROOT)
    secrets_root = _path(paths.get("secrets_root"), ai_lab_root / "secrets", PROJECT_ROOT)

    return MachineConfig(
        config_path=config_path,
        config_exists=config_path.exists(),
        ai_lab_root=ai_lab_root,
        cache_root=cache_root,
        data_root=data_root,
        models_root=models_root,
        envs_root=envs_root,
        runtimes_root=runtimes_root,
        secrets_root=secrets_root,
        docling_artifacts=_path(assets.get("docling_artifacts"), models_root / "docling" / "2.111.0", PROJECT_ROOT),
        bge_model=_path(assets.get("bge_model"), models_root / "bge-m3" / "5617a9f61b028005a4858fdac845db406aefb181", PROJECT_ROOT),
        llama_cpp=_path(assets.get("llama_cpp"), runtimes_root / "llama.cpp" / "b9968" / "llama-server.exe", PROJECT_ROOT),
        qwen4_model=_path(assets.get("qwen4_model"), models_root / "qwen3-4b-instruct-2507", PROJECT_ROOT),
        qwen9_model=_path(assets.get("qwen9_model"), models_root / "qwen3.5-9b", PROJECT_ROOT),
        docling_env=_path(environments.get("docling_env"), envs_root / "retrieval-adaptation-lab-docling", PROJECT_ROOT),
        bge_env=_path(environments.get("bge_env"), envs_root / "retrieval-adaptation-lab-bge-m3", PROJECT_ROOT),
        llama_env=_path(environments.get("llama_env"), envs_root / "retrieval-adaptation-lab-llama-cpp", PROJECT_ROOT),
        round6_env=_path(environments.get("round6_env"), envs_root / "retrieval-adaptation-lab-llama-cpp-round6", PROJECT_ROOT),
        round7_env=_path(environments.get("round7_env"), envs_root / "retrieval-adaptation-lab-llama-cpp-round7", PROJECT_ROOT),
    )


__all__ = ["DEFAULT_CONFIG_PATH", "MachineConfig", "load_machine_config", "resolve_config_path"]
