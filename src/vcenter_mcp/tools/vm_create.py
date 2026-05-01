from pyVmomi import vim
from vcenter_mcp.client import vcenter_connection, get_obj, wait_for_task
from vcenter_mcp.config import load_config, resolve_target, resolve_template


def register_create_tools(mcp) -> None:
    @mcp.tool()
    def create_vm(
        name: str,
        vm_type: str,
        target: str | None = None,
        network_profile: str | None = None,
        cpu: int | None = None,
        ram_mb: int | None = None,
        disk_gb: int | None = None,
        disk_provisioning: str | None = None,
    ) -> str:
        """
        Create a VM that network boots first.
        vm_type: esxi, ubuntu, rhel (or any type defined in config templates).
        disk_provisioning: thin (default) or thick.
        network_profile: named profile from target config (e.g. standard, secure-boot).
        """
        try:
            cfg = load_config()
            target_cfg = resolve_target(cfg, target)
            tmpl = resolve_template(
                cfg, vm_type,
                cpu=cpu, ram_mb=ram_mb,
                disk_gb=disk_gb, disk_provisioning=disk_provisioning,
            )
            profile_name = network_profile or target_cfg["default_network"]
            if profile_name not in target_cfg["networks"]:
                return f"Error: network profile '{profile_name}' not in target config"
            portgroup_names = target_cfg["networks"][profile_name]

            with vcenter_connection(target_cfg) as si:
                content = si.RetrieveContent()
                vm = _create_vm(content, target_cfg, name, tmpl, portgroup_names)
                return f"Created VM '{vm.name}' (moref: {vm._moId})"
        except Exception as e:
            return f"Error: {e}"


def _create_vm(content, target_cfg: dict, name: str, tmpl: dict, portgroup_names: list):
    dc = _get_datacenter(content, target_cfg)
    resource_pool = _get_resource_pool(content, target_cfg, dc)
    datastore = get_obj(content, [vim.Datastore], target_cfg["datastore"])
    if not datastore:
        raise ValueError(f"Datastore '{target_cfg['datastore']}' not found")

    vm_folder = dc.vmFolder

    # SCSI controller (key=1000)
    scsi = vim.vm.device.VirtualLsiLogicController()
    scsi.key = 1000
    scsi.busNumber = 0
    scsi.sharedBus = vim.vm.device.VirtualSCSIController.Sharing.noSharing
    scsi_spec = _add_spec(scsi)

    # Disk (key=2000, attached to SCSI key=1000)
    if tmpl["disk_provisioning"] not in ("thin", "thick"):
        raise ValueError(
            f"disk_provisioning must be 'thin' or 'thick', got '{tmpl['disk_provisioning']}'"
        )
    disk_backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
    disk_backing.diskMode = "persistent"
    disk_backing.thinProvisioned = (tmpl["disk_provisioning"] == "thin")

    disk = vim.vm.device.VirtualDisk()
    disk.key = 2000
    disk.unitNumber = 0
    disk.controllerKey = 1000
    disk.capacityInKB = tmpl["disk_gb"] * 1024 * 1024
    disk.backing = disk_backing
    disk_spec = _add_spec(
        disk,
        file_op=vim.vm.device.VirtualDeviceSpec.FileOperation.create,
    )

    # NICs (keys start at 4000)
    if not portgroup_names:
        raise ValueError(f"Network profile has no portgroups defined")
    nic_specs = []
    nic_keys = []
    for i, pg_name in enumerate(portgroup_names):
        key = 4000 + i
        nic_keys.append(key)
        network = get_obj(content, [vim.Network], pg_name)
        if not network:
            raise ValueError(f"Network/portgroup '{pg_name}' not found")

        nic = vim.vm.device.VirtualVmxnet3()
        nic.key = key
        nic.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
        nic.connectable.startConnected = True
        nic.connectable.allowGuestControl = True

        if isinstance(network, vim.dvs.DistributedVirtualPortgroup):
            dvs_uuid = network.config.distributedVirtualSwitch.uuid
            port_backing = vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
            port_backing.port = vim.dvs.PortConnection()
            port_backing.port.switchUuid = dvs_uuid
            port_backing.port.portgroupKey = network.key
            nic.backing = port_backing
        else:
            std_backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
            std_backing.network = network
            std_backing.deviceName = pg_name
            nic.backing = std_backing

        nic_specs.append(_add_spec(nic))

    # Boot order: first NIC
    boot_nic = vim.vm.BootOptions.BootableEthernetDevice()
    boot_nic.deviceKey = nic_keys[0]
    boot_opts = vim.vm.BootOptions()
    boot_opts.bootOrder = [boot_nic]

    # VM config spec
    config = vim.vm.ConfigSpec()
    config.name = name
    config.numCPUs = tmpl["cpu"]
    config.memoryMB = tmpl["ram_mb"]
    config.guestId = tmpl["guest_id"]
    config.files = vim.vm.FileInfo()
    config.files.vmPathName = f"[{target_cfg['datastore']}]"
    config.deviceChange = [scsi_spec, disk_spec] + nic_specs
    config.bootOptions = boot_opts

    if tmpl.get("vhv"):
        config.nestedHVEnabled = True

    task = vm_folder.CreateVM_Task(config=config, pool=resource_pool)
    wait_for_task(task)
    return task.info.result


def _add_spec(device, file_op=None):
    spec = vim.vm.device.VirtualDeviceSpec()
    spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
    if file_op is not None:
        spec.fileOperation = file_op
    spec.device = device
    return spec


def _get_datacenter(content, target_cfg: dict):
    if target_cfg["type"] == "esxi":
        dc = get_obj(content, [vim.Datacenter], "ha-datacenter")
        if not dc:
            raise ValueError("Could not find ha-datacenter on standalone ESXi host")
        return dc
    dc = get_obj(content, [vim.Datacenter], target_cfg["datacenter"])
    if not dc:
        raise ValueError(f"Datacenter '{target_cfg['datacenter']}' not found")
    return dc


def _get_resource_pool(content, target_cfg: dict, dc):
    if target_cfg["type"] == "esxi":
        host_view = content.viewManager.CreateContainerView(
            dc, [vim.HostSystem], True
        )
        hosts = host_view.view
        host_view.Destroy()
        if not hosts:
            raise ValueError("No host found on standalone ESXi target")
        return hosts[0].parent.resourcePool
    cluster = get_obj(content, [vim.ClusterComputeResource], target_cfg["cluster"])
    if not cluster:
        raise ValueError(f"Cluster '{target_cfg['cluster']}' not found")
    return cluster.resourcePool
