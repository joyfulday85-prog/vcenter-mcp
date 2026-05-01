import sys
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("vcenter-mcp")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        from vcenter_mcp.setup_cmd import run_setup
        run_setup()
        return

    from vcenter_mcp.tools.vm_list import register_list_tools
    from vcenter_mcp.tools.vm_create import register_create_tools
    from vcenter_mcp.tools.vm_power import register_power_tools
    from vcenter_mcp.tools.vm_delete import register_delete_tools

    register_list_tools(mcp)
    register_create_tools(mcp)
    register_power_tools(mcp)
    register_delete_tools(mcp)

    mcp.run()


if __name__ == "__main__":
    main()
