"""Stdio entry point for Claude Desktop: `python -m deepfang`."""

from __future__ import annotations


def main() -> None:
    from .mcp_server import create_mcp_server

    mcp = create_mcp_server()
    mcp.run()


if __name__ == "__main__":
    main()
