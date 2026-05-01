from pyVmomi import vim
from vcenter_mcp.client import vcenter_connection, get_obj
from vcenter_mcp.config import load_config, resolve_target


def register_list_tools(mcp) -> None:
    @mcp.tool()
    def list_vms(target: str | None = None, datacenter: str | None = None) -> str:
        """
        List VMs on a target.
        - Standalone ESXi: lists all VMs on the host.
        - vCenter: groups VMs by host within the specified datacenter
          (defaults to the target's configured datacenter).
        """
        try:
            cfg = load_config()
            target_cfg = resolve_target(cfg, target)
            with vcenter_connection(target_cfg) as si:
                content = si.RetrieveContent()
                if target_cfg["type"] == "esxi":
                    return _list_esxi(content)
                dc_name = datacenter or target_cfg.get("datacenter")
                return _list_vcenter(content, dc_name)
        except Exception as e:
            return f"Error: {e}"


def _list_esxi(content) -> str:
    container = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.VirtualMachine], True
    )
    lines = ["VMs:"]
    for vm in container.view:
        state = vm.runtime.powerState
        guest = vm.config.guestId if vm.config else "unknown"
        lines.append(f"  {vm.name} ({vm._moId}) — {state} — {guest}")
    container.Destroy()
    return "\n".join(lines) if len(lines) > 1 else "No VMs found"


def _list_vcenter(content, dc_name: str) -> str:
    dc = get_obj(content, [vim.Datacenter], dc_name)
    if not dc:
        return f"Error: Datacenter '{dc_name}' not found"

    host_view = content.viewManager.CreateContainerView(
        dc, [vim.HostSystem], True
    )
    lines = []
    for host in host_view.view:
        lines.append(f"Host: {host.name}")
        for vm in host.vm:
            state = vm.runtime.powerState
            guest = vm.config.guestId if vm.config else "unknown"
            lines.append(f"  {vm.name} ({vm._moId}) — {state} — {guest}")
    host_view.Destroy()
    return "\n".join(lines) if lines else "No VMs found"
