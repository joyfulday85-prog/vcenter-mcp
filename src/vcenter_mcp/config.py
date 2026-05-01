import json
from pathlib import Path


def config_path() -> Path:
    return Path.home() / ".config" / "vcenter-mcp" / "config.json"


def load_config(path: Path | None = None) -> dict:
    resolved = path or config_path()
    try:
        return json.loads(resolved.read_text())
    except FileNotFoundError:
        raise RuntimeError("No config found. Run: venv/bin/python -m vcenter_mcp setup")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Config is malformed: {e}. Run: venv/bin/python -m vcenter_mcp setup")


def save_config(data: dict, path: Path | None = None) -> None:
    resolved = path or config_path()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(data, indent=2) + "\n")
    resolved.chmod(0o600)


def resolve_target(cfg: dict, target_name: str | None = None) -> dict:
    name = target_name or cfg.get("default_target")
    if not name:
        raise ValueError("No target specified and no default_target set in config")
    target = cfg.get("targets", {}).get(name)
    if not target:
        raise ValueError(f"Target '{name}' not found in config. Available: {list(cfg.get('targets', {}).keys())}")
    return target


def resolve_template(
    cfg: dict,
    vm_type: str,
    cpu: int | None = None,
    ram_mb: int | None = None,
    disk_gb: int | None = None,
    disk_provisioning: str | None = None,
) -> dict:
    templates = cfg.get("templates", {})
    tmpl = templates.get(vm_type)
    if not tmpl:
        raise ValueError(f"Unknown vm_type '{vm_type}'. Available: {list(templates.keys())}")
    result = dict(tmpl)
    if cpu is not None:
        result["cpu"] = cpu
    if ram_mb is not None:
        result["ram_mb"] = ram_mb
    if disk_gb is not None:
        result["disk_gb"] = disk_gb
    if disk_provisioning is not None:
        result["disk_provisioning"] = disk_provisioning
    return result
