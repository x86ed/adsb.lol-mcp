# Main entry point that initializes MCP and imports all tools
from mcp.server.fastmcp import FastMCP

# Import all tool functions from modules
from api_v2 import  register_api_v2
from faa import register_FAA_Reg
from opensky import register_opensky

# Initialize FastMCP server
mcp = FastMCP("adsblol")

# Register all tools with MCP
register_api_v2(mcp)
register_FAA_Reg(mcp)
register_opensky(mcp)

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')