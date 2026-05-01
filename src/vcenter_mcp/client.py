import re
import ssl
from contextlib import contextmanager

from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect
from pyVim.task import WaitForTask


def _ssl_context() -> ssl.SSLContext:
    return ssl._create_unverified_context()


@contextmanager
def vcenter_connection(target_cfg: dict):
    """Context manager: yields a connected ServiceInstance, disconnects on exit."""
    si = SmartConnect(
        host=target_cfg["host"],
        user=target_cfg["user"],
        pwd=target_cfg["password"],
        sslContext=_ssl_context(),
    )
    try:
        yield si
    finally:
        Disconnect(si)


def get_obj(content, vimtypes: list, name: str):
    """Search the full inventory for a managed object by name. Returns None if not found."""
    container = content.viewManager.CreateContainerView(
        content.rootFolder, vimtypes, True
    )
    result = None
    for obj in container.view:
        if obj.name == name:
            result = obj
            break
    container.Destroy()
    return result


def _is_moref(value: str) -> bool:
    return bool(re.match(r"^vm-\d+$", value))


def lookup_vm(si, name_or_id: str):
    """
    Find a VM by moref ID (e.g. 'vm-42') or display name.
    Raises ValueError if not found or if multiple VMs share the same display name.
    """
    content = si.RetrieveContent()

    if _is_moref(name_or_id):
        ref = vim.VirtualMachine(name_or_id)
        ref._stub = si._stub
        return ref

    container = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.VirtualMachine], True
    )
    matches = [vm for vm in container.view if vm.name == name_or_id]
    container.Destroy()

    if not matches:
        raise ValueError(f"No VM found with name '{name_or_id}'")
    if len(matches) > 1:
        morefs = [vm._moId for vm in matches]
        raise ValueError(
            f"Multiple VMs named '{name_or_id}': {morefs}. Use a moref ID instead."
        )
    return matches[0]


def wait_for_task(task) -> None:
    """Wait for a vSphere task to complete. Raises on task error."""
    WaitForTask(task)
