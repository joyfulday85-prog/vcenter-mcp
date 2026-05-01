import pytest
from unittest.mock import MagicMock, patch
from vcenter_mcp.client import _is_moref, lookup_vm


def test_is_moref_valid():
    assert _is_moref("vm-42") is True
    assert _is_moref("vm-1") is True
    assert _is_moref("vm-99999") is True


def test_is_moref_invalid():
    assert _is_moref("my-vm") is False
    assert _is_moref("vm-") is False
    assert _is_moref("42") is False
    assert _is_moref("VM-42") is False
    assert _is_moref("vm-42x") is False


def test_lookup_vm_not_found_raises():
    si = MagicMock()
    content = si.RetrieveContent.return_value
    view = content.viewManager.CreateContainerView.return_value
    view.view = []

    with pytest.raises(ValueError, match="No VM found"):
        lookup_vm(si, "ghost-vm")


def test_lookup_vm_duplicate_name_raises():
    si = MagicMock()
    content = si.RetrieveContent.return_value
    view = content.viewManager.CreateContainerView.return_value

    vm1 = MagicMock()
    vm1.name = "test-vm"
    vm1._moId = "vm-1"
    vm2 = MagicMock()
    vm2.name = "test-vm"
    vm2._moId = "vm-2"
    view.view = [vm1, vm2]

    with pytest.raises(ValueError, match="Multiple VMs"):
        lookup_vm(si, "test-vm")


def test_lookup_vm_by_name_returns_match():
    si = MagicMock()
    content = si.RetrieveContent.return_value
    view = content.viewManager.CreateContainerView.return_value

    vm = MagicMock()
    vm.name = "test-vm"
    view.view = [vm]

    result = lookup_vm(si, "test-vm")
    assert result is vm
