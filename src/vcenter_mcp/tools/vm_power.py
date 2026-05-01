from vcenter_mcp.client import vcenter_connection, lookup_vm, wait_for_task
from vcenter_mcp.config import load_config, resolve_target


def register_power_tools(mcp) -> None:
    @mcp.tool()
    def power_on_vm(name_or_id: str, target: str | None = None) -> str:
        """Power on a VM by display name or moref ID (e.g. 'vm-42')."""
        try:
            cfg = load_config()
            target_cfg = resolve_target(cfg, target)
            with vcenter_connection(target_cfg) as si:
                vm = lookup_vm(si, name_or_id)
                task = vm.PowerOn()
                wait_for_task(task)
                return f"VM '{vm.name}' is now powered on"
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def power_off_vm(name_or_id: str, target: str | None = None) -> str:
        """Hard power off a VM by display name or moref ID (e.g. 'vm-42')."""
        try:
            cfg = load_config()
            target_cfg = resolve_target(cfg, target)
            with vcenter_connection(target_cfg) as si:
                vm = lookup_vm(si, name_or_id)
                task = vm.PowerOff()
                wait_for_task(task)
                return f"VM '{vm.name}' is now powered off"
        except Exception as e:
            return f"Error: {e}"
