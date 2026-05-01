import getpass
from vcenter_mcp.config import load_config, save_config, config_path


def run_setup() -> None:
    print("vcenter-mcp setup\n")

    try:
        cfg = load_config()
        print(f"Existing config found at {config_path()}")
    except RuntimeError:
        cfg = {"targets": {}, "default_target": None, "templates": _default_templates()}

    print("\nAdd or update a target")
    target_name = input("Target name (e.g. lab-vcenter): ").strip()
    host = input("Host/IP: ").strip()
    user = input("Username: ").strip()
    password = getpass.getpass("Password: ")
    target_type = _prompt_choice("Type", ["vcenter", "esxi"])

    target: dict = {
        "host": host,
        "user": user,
        "password": password,
        "type": target_type,
        "networks": {},
        "default_network": "standard",
    }

    if target_type == "vcenter":
        target["datacenter"] = input("Datacenter name: ").strip()
        target["cluster"] = input("Cluster name: ").strip()

    target["datastore"] = input("Datastore name: ").strip()

    print("\nDefine network profiles (press Enter with no name to finish)")
    while True:
        profile_name = input("Network profile name (e.g. standard, secure-boot): ").strip()
        if not profile_name:
            break
        portgroups: list[str] = []
        while True:
            pg = input(f"  Portgroup for '{profile_name}' (Enter to finish): ").strip()
            if not pg:
                break
            portgroups.append(pg)
        if portgroups:
            target["networks"][profile_name] = portgroups

    if not target["networks"]:
        pg = input("Portgroup name (at least one required): ").strip()
        target["networks"]["standard"] = [pg]

    target["default_network"] = _prompt_choice(
        "Default network profile", list(target["networks"].keys())
    )

    cfg.setdefault("targets", {})[target_name] = target

    if not cfg.get("default_target"):
        cfg["default_target"] = target_name
    elif input(f"Set '{target_name}' as default target? [y/N]: ").strip().lower() == "y":
        cfg["default_target"] = target_name

    save_config(cfg)
    print(f"\nConfig saved to {config_path()}")
    print(f"Default target: {cfg['default_target']}")


def _prompt_choice(label: str, options: list[str]) -> str:
    formatted = "/".join(options)
    while True:
        val = input(f"{label} [{formatted}]: ").strip()
        if val in options:
            return val
        print(f"  Please enter one of: {options}")


def _default_templates() -> dict:
    return {
        "esxi": {
            "cpu": 4,
            "ram_mb": 16384,
            "disk_gb": 100,
            "disk_provisioning": "thin",
            "guest_id": "vmkernel7Guest",
            "vhv": True,
        },
        "ubuntu": {
            "cpu": 2,
            "ram_mb": 4096,
            "disk_gb": 40,
            "disk_provisioning": "thin",
            "guest_id": "ubuntu64Guest",
            "vhv": False,
        },
        "rhel": {
            "cpu": 2,
            "ram_mb": 4096,
            "disk_gb": 40,
            "disk_provisioning": "thin",
            "guest_id": "rhel9_64Guest",
            "vhv": False,
        },
    }
