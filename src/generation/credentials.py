"""Local credential loading for the MiMo Round 8 adapter.

The loader intentionally keeps the secret out of public representations. It
accepts a process environment variable for automation, and otherwise reads a
local INI file outside the repository. No value, length, prefix, suffix, or
hash of the key is ever returned by this module.
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from src.machine_config import load_machine_config


DEFAULT_CONFIG_PATH = Path(os.environ.get("AI_LAB_ROOT", "D:/AI-Lab")) / "secrets" / "retrieval-adaptation-lab" / "mimo.ini"
DEFAULT_BASE_URL = "https://api.xiaomimimo.com/v1"
DEFAULT_MODEL = "mimo-v2.5-pro"
MAX_REQUESTS_CAP = 70
MAX_COST_USD_CAP = 2.0


def config_template() -> str:
    """Return a secret-free local configuration template."""

    return (
        "[mimo]\n"
        "api_key=\n"
        f"base_url={DEFAULT_BASE_URL}\n"
        f"model={DEFAULT_MODEL}\n\n"
        "[limits]\n"
        f"max_requests={MAX_REQUESTS_CAP}\n"
        f"max_cost_usd={MAX_COST_USD_CAP}\n"
    )


@dataclass(frozen=True)
class CredentialConfig:
    """Resolved configuration with the secret kept private to the process."""

    api_key: str | None
    base_url: str
    model: str
    max_requests: int
    max_cost_usd: float
    credential_source: str | None
    config_path: Path
    config_exists: bool
    config_created: bool = False
    status: str = "ready"
    issues: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    @property
    def endpoint(self) -> str:
        return self.base_url.rstrip("/") + "/chat/completions"

    def to_public(self) -> dict[str, object]:
        """Return a safe representation suitable for console/report output."""

        return {
            "status": self.status,
            "credential_source": self.credential_source,
            "config_path": str(self.config_path),
            "config_exists": self.config_exists,
            "config_created": self.config_created,
            "base_url": self.base_url,
            "model": self.model,
            "max_requests": self.max_requests,
            "max_cost_usd": self.max_cost_usd,
            "issues": list(self.issues),
        }


def resolve_config_path() -> Path:
    override = os.environ.get("MIMO_SECRET_FILE", "").strip()
    if override:
        return Path(override).expanduser()
    # Resolve the ignored machine-local config so a second computer can use
    # its own secrets_root without exporting AI_LAB_ROOT first.
    return load_machine_config().mimo_config


def ensure_config_template(path: Path) -> bool:
    """Create the external template if it is absent; return whether created."""

    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(config_template())
    except FileExistsError:
        return False
    return True


def _parse_limits(parser: configparser.ConfigParser) -> tuple[int, float, list[str]]:
    issues: list[str] = []
    try:
        max_requests = parser.getint("limits", "max_requests", fallback=MAX_REQUESTS_CAP)
        max_cost_usd = parser.getfloat("limits", "max_cost_usd", fallback=MAX_COST_USD_CAP)
    except (ValueError, configparser.Error):
        return MAX_REQUESTS_CAP, MAX_COST_USD_CAP, ["invalid_limits"]
    if not 1 <= max_requests <= MAX_REQUESTS_CAP:
        issues.append("max_requests_out_of_range")
    if not 0 < max_cost_usd <= MAX_COST_USD_CAP:
        issues.append("max_cost_usd_out_of_range")
    return max_requests, max_cost_usd, issues


def _valid_https_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.query and not parsed.fragment


def _credential_kind(value: str | None) -> str:
    """Classify only in memory for endpoint policy checks; never expose it."""

    if value and value.startswith("tp-"):
        return "token_plan"
    if value and value.startswith("sk-"):
        return "payg"
    return "unknown"


def _endpoint_policy_issues(api_key: str | None, base_url: str) -> list[str]:
    """Prevent mixing the two official credential/base-URL families."""

    kind = _credential_kind(api_key)
    host = urlsplit(base_url).hostname or ""
    is_token_plan_host = host.endswith(".xiaomimimo.com") and host.startswith("token-plan-")
    is_payg_host = host == "api.xiaomimimo.com"
    if kind == "token_plan" and not is_token_plan_host:
        return ["token_plan_base_url_mismatch"]
    if kind == "payg" and is_token_plan_host:
        return ["payg_base_url_mismatch"]
    if kind == "token_plan" and is_token_plan_host:
        # MiMo's official Token Plan policy limits package use to supported
        # programming tools and disallows automated scripts/custom backends.
        return ["token_plan_automation_policy_requires_review"]
    if kind == "unknown" and not (is_token_plan_host or is_payg_host):
        return ["unrecognized_mimo_base_url"]
    return []


def load_credentials(*, create_template: bool = True) -> CredentialConfig:
    """Resolve credentials without logging or returning the key publicly."""

    config_path = resolve_config_path()
    created = ensure_config_template(config_path) if create_template else False
    config_exists = config_path.exists()
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str.lower
    issues: list[str] = []

    if config_exists:
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                parser.read_file(handle)
        except (OSError, UnicodeError, configparser.Error):
            issues.append("invalid_config")
    elif create_template:
        issues.append("missing_config")

    env_key = os.environ.get("MIMO_API_KEY", "").strip()
    file_key = parser.get("mimo", "api_key", fallback="").strip()
    api_key = env_key or file_key or None
    credential_source = "environment" if env_key else ("file" if file_key else None)

    base_url = parser.get("mimo", "base_url", fallback=DEFAULT_BASE_URL).strip()
    model = parser.get("mimo", "model", fallback=DEFAULT_MODEL).strip()
    max_requests, max_cost_usd, limit_issues = _parse_limits(parser)
    issues.extend(limit_issues)

    if not base_url or not _valid_https_url(base_url):
        issues.append("invalid_base_url")
    if model != DEFAULT_MODEL:
        issues.append("model_must_be_mimo_v2_5_pro")
    if not api_key:
        issues.append("missing_credentials")
    issues.extend(_endpoint_policy_issues(api_key, base_url))

    if "invalid_config" in issues:
        status = "invalid_config"
    elif "missing_config" in issues and not config_exists:
        status = "missing_config"
    elif "missing_credentials" in issues:
        status = "missing_credentials"
    elif any(issue in issues for issue in ("invalid_limits", "max_requests_out_of_range", "max_cost_usd_out_of_range")):
        status = "invalid_limits"
    elif "invalid_base_url" in issues or "unrecognized_mimo_base_url" in issues:
        status = "invalid_configuration"
    elif any(issue.endswith("mismatch") or "policy_requires_review" in issue for issue in issues):
        status = "policy_blocked"
    else:
        status = "ready"

    return CredentialConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_requests=max_requests,
        max_cost_usd=max_cost_usd,
        credential_source=credential_source,
        config_path=config_path,
        config_exists=config_exists,
        config_created=created,
        status=status,
        issues=tuple(dict.fromkeys(issues)),
    )


__all__ = [
    "CredentialConfig",
    "DEFAULT_BASE_URL",
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_MODEL",
    "MAX_COST_USD_CAP",
    "MAX_REQUESTS_CAP",
    "config_template",
    "ensure_config_template",
    "load_credentials",
    "resolve_config_path",
]
