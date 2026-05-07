from pyVmomi import vim, vmodl

from vcenter_mcp.client import vcenter_connection, get_obj
from vcenter_mcp.config import load_config, resolve_target


_VM_PROPERTY_PATHS = [
    "name",
    "config.uuid",
    "config.guestId",
    "config.guestFullName",
    "config.hardware.numCPU",
    "config.hardware.memoryMB",
    "config.hardware.device",
    "runtime.powerState",
    "summary.storage.committed",
    "guest.ipAddress",
    "guest.net",
]


def register_list_tools(mcp) -> None:
    @mcp.tool()
    def list_vms(target: str | None = None, datacenter: str | None = None) -> list[dict] | dict:
        """
        List VMs on a target with rich per-VM details.

        Returns a list of dicts. Each VM includes name, moref, BIOS UUID,
        power state, guest OS, CPU/memory, primary guest IP, every NIC
        (MAC + connected network + guest IPs when VMware Tools is running),
        and every virtual disk (capacity + datastore-relative file path).

        Implementation uses a single PropertyCollector RetrieveContents call,
        so it scales to the largest vCenters and ESXi hosts without per-VM
        round trips.

        - Standalone ESXi: lists all VMs on the host.
        - vCenter: lists all VMs in the specified datacenter (defaults to the
          target's configured datacenter).

        On error, returns a single dict with an "error" key.
        """
        try:
            cfg = load_config()
            target_cfg = resolve_target(cfg, target)
            with vcenter_connection(target_cfg) as si:
                content = si.RetrieveContent()
                if target_cfg["type"] == "esxi":
                    container_root = content.rootFolder
                else:
                    dc_name = datacenter or target_cfg.get("datacenter")
                    dc = get_obj(content, [vim.Datacenter], dc_name)
                    if not dc:
                        return {"error": f"Datacenter '{dc_name}' not found"}
                    container_root = dc
                view = content.viewManager.CreateContainerView(
                    container_root, [vim.VirtualMachine], True
                )
                try:
                    raw = _collect_vm_props(si, view, _VM_PROPERTY_PATHS)
                finally:
                    view.Destroy()
                return [_shape_vm(r) for r in sorted(raw, key=lambda r: r.get("name", ""))]
        except Exception as e:
            return {"error": str(e)}


def _collect_vm_props(si, view_ref, path_set):
    """Batch-fetch VM properties via PropertyCollector in a single RPC.

    Iterating `container.view` and reading `.config.hardware.device` per VM
    triggers one SOAP round-trip per attribute; PropertyCollector pulls
    everything in one call. Pattern mirrors pyvmomi-community-samples
    `samples/tools/pchelper.py:collect_properties`.
    """
    pc = si.content.propertyCollector

    obj_spec = vmodl.query.PropertyCollector.ObjectSpec()
    obj_spec.obj = view_ref
    obj_spec.skip = True

    traversal = vmodl.query.PropertyCollector.TraversalSpec()
    traversal.name = "traverseEntities"
    traversal.path = "view"
    traversal.skip = False
    traversal.type = view_ref.__class__
    obj_spec.selectSet = [traversal]

    prop_spec = vmodl.query.PropertyCollector.PropertySpec()
    prop_spec.type = vim.VirtualMachine
    prop_spec.pathSet = path_set

    filter_spec = vmodl.query.PropertyCollector.FilterSpec()
    filter_spec.objectSet = [obj_spec]
    filter_spec.propSet = [prop_spec]

    out = []
    for obj_content in pc.RetrieveContents([filter_spec]):
        props = {p.name: p.val for p in obj_content.propSet}
        props["_moId"] = obj_content.obj._moId
        out.append(props)
    return out


def _shape_vm(rec: dict) -> dict:
    devices = rec.get("config.hardware.device") or []
    nics_raw, disks_raw = _split_devices(devices)
    guest_ips = _guest_ips_by_mac(rec.get("guest.net"))
    nics = [
        {**nic, "guest_ips": guest_ips.get((nic["mac"] or "").lower(), [])}
        for nic in nics_raw
    ]
    return {
        "name": rec.get("name", ""),
        "moref": rec.get("_moId", ""),
        "uuid": rec.get("config.uuid", "") or "",
        "power_state": rec.get("runtime.powerState", "") or "",
        "guest_id": rec.get("config.guestId", "") or "",
        "guest_full_name": rec.get("config.guestFullName", "") or "",
        "cpu_count": rec.get("config.hardware.numCPU", 0) or 0,
        "memory_mb": rec.get("config.hardware.memoryMB", 0) or 0,
        "storage_used_bytes": int(rec.get("summary.storage.committed", 0) or 0),
        "primary_ip": rec.get("guest.ipAddress", "") or "",
        "nics": nics,
        "disks": disks_raw,
    }


def _split_devices(devices):
    nics, disks = [], []
    for dev in devices:
        if isinstance(dev, vim.vm.device.VirtualEthernetCard):
            nics.append(_nic_summary(dev))
        elif isinstance(dev, vim.vm.device.VirtualDisk):
            disks.append(_disk_summary(dev))
    return nics, disks


def _nic_summary(dev) -> dict:
    backing = getattr(dev, "backing", None)
    net_name = ""
    if backing is not None:
        net_name = getattr(backing, "deviceName", "") or ""
        if not net_name:
            net = getattr(backing, "network", None)
            if net is not None:
                net_name = getattr(net, "name", "") or ""
            else:
                port = getattr(backing, "port", None)
                if port is not None:
                    pg_key = getattr(port, "portgroupKey", "")
                    net_name = f"dvportgroup:{pg_key}" if pg_key else ""
    return {
        "key": int(getattr(dev, "key", 0) or 0),
        "mac": dev.macAddress or "",
        "network": net_name,
    }


def _disk_summary(dev) -> dict:
    capacity_bytes = getattr(dev, "capacityInBytes", 0) or (
        (getattr(dev, "capacityInKB", 0) or 0) * 1024
    )
    backing = getattr(dev, "backing", None)
    file_path = getattr(backing, "fileName", "") if backing is not None else ""
    return {
        "key": int(getattr(dev, "key", 0) or 0),
        "capacity_bytes": int(capacity_bytes),
        "file": file_path or "",
    }


def _guest_ips_by_mac(guest_net) -> dict:
    out = {}
    if not guest_net:
        return out
    for n in guest_net:
        mac = (getattr(n, "macAddress", "") or "").lower()
        if not mac:
            continue
        ips = list(getattr(n, "ipAddress", []) or [])
        if ips:
            out[mac] = ips
    return out
