"""Allow ``python -m compatsentinel`` as an alternative to the ``compatsentinel`` script.

Useful for tool configs (Claude Desktop, MCP Inspector) that invoke a Python
module directly rather than relying on the console script being on PATH.
"""

from compatsentinel.cli import app

if __name__ == "__main__":
    app()
