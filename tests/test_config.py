import json
import pytest
from vcenter_mcp.config import load_config, save_config, resolve_target, resolve_template


SAMPLE_CFG = {
    "default_target": "lab-vcenter",
    "targets": {
        "lab-vcenter": {
            "host": "vcenter.lab.example.com",
            "user": "admin",
            "password": "secret",
            "type": "vcenter",
            "datacenter": "Lab DC",
            "cluster": "Lab Cluster",
            "datastore": "datastore1",
            "networks": {"standard": ["VM Network"]},
            "default_network": "standard",
        }
    },
    "templates": {
        "esxi": {"cpu": 4, "ram_mb": 16384, "disk_gb": 100, "disk_provisioning": "thin", "guest_id": "vmkernel7Guest", "vhv": True},
        "ubuntu": {"cpu": 2, "ram_mb": 4096, "disk_gb": 40, "disk_provisioning": "thin", "guest_id": "ubuntu64Guest", "vhv": False},
    },
}


def test_load_config_missing_raises(tmp_path):
    with pytest.raises(RuntimeError, match="No config found"):
        load_config(tmp_path / "nonexistent.json")


def test_load_config_malformed_raises(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("not json")
    with pytest.raises(RuntimeError, match="malformed"):
        load_config(p)


def test_save_and_load_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    save_config(SAMPLE_CFG, p)
    loaded = load_config(p)
    assert loaded == SAMPLE_CFG


def test_save_config_sets_permissions(tmp_path):
    p = tmp_path / "config.json"
    save_config(SAMPLE_CFG, p)
    assert oct(p.stat().st_mode)[-3:] == "600"


def test_resolve_target_default(tmp_path):
    target = resolve_target(SAMPLE_CFG)
    assert target["host"] == "vcenter.lab.example.com"


def test_resolve_target_explicit(tmp_path):
    target = resolve_target(SAMPLE_CFG, "lab-vcenter")
    assert target["type"] == "vcenter"


def test_resolve_target_missing_raises():
    with pytest.raises(ValueError, match="not found"):
        resolve_target(SAMPLE_CFG, "nonexistent")


def test_resolve_target_no_default_raises():
    with pytest.raises(ValueError, match="No target specified"):
        resolve_target({})


def test_resolve_template_no_overrides():
    tmpl = resolve_template(SAMPLE_CFG, "ubuntu")
    assert tmpl["cpu"] == 2
    assert tmpl["disk_provisioning"] == "thin"


def test_resolve_template_with_overrides():
    tmpl = resolve_template(SAMPLE_CFG, "ubuntu", cpu=8, ram_mb=8192)
    assert tmpl["cpu"] == 8
    assert tmpl["ram_mb"] == 8192
    assert tmpl["disk_gb"] == 40  # unchanged


def test_resolve_template_unknown_raises():
    with pytest.raises(ValueError, match="Unknown vm_type"):
        resolve_template(SAMPLE_CFG, "windows")


def test_resolve_template_does_not_mutate_original():
    resolve_template(SAMPLE_CFG, "ubuntu", cpu=99)
    assert SAMPLE_CFG["templates"]["ubuntu"]["cpu"] == 2
