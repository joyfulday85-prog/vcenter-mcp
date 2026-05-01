from pyVmomi import vim
from vcenter_mcp.client import vcenter_connection, lookup_vm, wait_for_task
from vcenter_mcp.config import load_config, resolve_target


def register_delete_tools(mcp) -> None:
    @mcp.tool()
    def delete_vm(name_or_id: str, target: str | None = None) -> str:
        """
        Permanently delete a VM (power off if running, then destroy from disk).
        Accepts display name or moref ID (e.g. 'vm-42').
        """
        try:
            cfg = load_config()
            target_cfg = resolve_target(cfg, target)
            with vcenter_connection(target_cfg) as si:
                vm = lookup_vm(si, name_or_id)
                vm_name = vm.name
                if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
                    wait_for_task(vm.PowerOff())
                wait_for_task(vm.Destroy_Task())
                return f"VM '{vm_name}' has been permanently deleted"
        except Exception as e:
            return f"Error: {e}"
