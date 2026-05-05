# vcenter-mcp

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes VMware vCenter / ESXi VM lifecycle tools to [Claude Code](https://claude.com/claude-code) and other MCP clients. Built on [pyVmomi](https://github.com/vmware/pyvmomi).

## What it does

- List VMs on a vCenter datacenter (grouped by host) or on a standalone ESXi host
- Create a VM (network-boot first; thin or thick provisioning; nested-virt option for ESXi targets)
- Power VMs on and off
- Delete VMs (powers off first if running, then destroys from disk)

Lookups accept either a display name or a moref ID (e.g. `vm-42`) — the moref path skips the inventory scan and is faster on large environments.

## Prerequisites

- Python 3.10 or newer
- A vCenter Server or standalone ESXi host you can reach over the network
- A vSphere account with the privileges needed for whatever you plan to do (read-only is enough for `list_vms`; create / delete need the corresponding VM and resource-pool privileges)

## Install

Install into a project-local virtualenv. Using a venv keeps `vcenter-mcp` and its dependencies (notably `pyVmomi`) isolated from your system Python.

From a clone of this repository:

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e .
```

For development (also installs pytest):

```bash
.venv/bin/pip install -e ".[dev]"
```

> Throughout this README, commands use `.venv/bin/...`. You can instead `source .venv/bin/activate` once per shell and drop the prefix — same result.

## Configure a target

Run the interactive setup using the venv's Python:

```bash
.venv/bin/python -m vcenter_mcp setup
```

You'll be prompted for:

1. A target name (e.g. `lab-vcenter`) — used to refer to this target later
2. Host or IP of the vCenter / ESXi
3. Username and password
4. Target type: `vcenter` or `esxi`
5. (vCenter only) Datacenter and cluster names
6. Datastore name
7. One or more network profiles, each a name plus one or more portgroup names

The setup writes a config to `~/.config/vcenter-mcp/config.json` (mode `0600`). Re-run it any time to add another target or update an existing one.

### Config file shape

```json
{
  "default_target": "lab-vcenter",
  "targets": {
    "lab-vcenter": {
      "host": "vcenter.lab.example.com",
      "user": "admin@vsphere.local",
      "password": "...",
      "type": "vcenter",
      "datacenter": "Lab DC",
      "cluster": "Lab Cluster",
      "datastore": "datastore1",
      "networks": {
        "standard": ["VM Network"],
        "secure-boot": ["pg-secure-1", "pg-secure-2"]
      },
      "default_network": "standard"
    }
  },
  "templates": {
    "esxi":   { "cpu": 4, "ram_mb": 16384, "disk_gb": 100, "disk_provisioning": "thin", "guest_id": "vmkernel7Guest", "vhv": true },
    "ubuntu": { "cpu": 2, "ram_mb": 4096,  "disk_gb": 40,  "disk_provisioning": "thin", "guest_id": "ubuntu64Guest",  "vhv": false },
    "rhel":   { "cpu": 2, "ram_mb": 4096,  "disk_gb": 40,  "disk_provisioning": "thin", "guest_id": "rhel9_64Guest",  "vhv": false }
  }
}
```

A network profile is a list of portgroups; the first entry becomes the boot NIC. To add your own VM types, add entries to `templates` — `vm_type` strings passed to `create_vm` are matched against this dict.

## Register with Claude Code

Register the MCP server using the venv's Python by absolute path. Claude Code launches the server in a fresh shell that does **not** inherit your activated venv, so the absolute path is required — pointing at a bare `python` here will fail to import `vcenter_mcp`.

```bash
VCENTER_MCP_DIR="$(pwd)"   # run this from the repo root, after install
claude mcp add --scope user vcenter -- "$VCENTER_MCP_DIR/.venv/bin/python" -m vcenter_mcp
```

Or just inline the absolute path you want:

```bash
claude mcp add --scope user vcenter -- /absolute/path/to/vcenter-mcp/.venv/bin/python -m vcenter_mcp
```

Read tools (`list_vms`) are safe to allow without prompting. Add it to `permissions.allow` in `~/.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "mcp__vcenter__list_vms"
    ]
  }
}
```

The destructive tools (`create_vm`, `power_on_vm`, `power_off_vm`, `delete_vm`) are intentionally not in the default allow-list — Claude will prompt you per call.

## Tools

| Tool | What it does |
|---|---|
| `list_vms` | List VMs on a target. vCenter targets group by host within a datacenter; ESXi targets list everything on the host. |
| `create_vm` | Create a VM that network-boots first. Pick a `vm_type` (template), optional CPU/RAM/disk overrides, optional `network_profile`. |
| `power_on_vm` | Power on a VM by display name or moref ID. |
| `power_off_vm` | Hard power off a VM by display name or moref ID. |
| `delete_vm` | Permanently delete a VM (powers off first if running, then destroys from disk). |

## Notes on TLS

`vcenter-mcp` connects with an unverified SSL context, which is the same default that `govc` and most pyVmomi sample code use because lab vCenters very commonly have self-signed certs. If your target uses a properly-signed certificate and you'd prefer real verification, swap `_ssl_context()` in `src/vcenter_mcp/client.py`.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

Tests run on Python 3.10, 3.11, and 3.12 in CI (see `.github/workflows/test.yml`).

## License

[Apache-2.0](LICENSE)
