# Copyright 2026 thev1ndu
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""End-to-end smoke test over the real stdio transport.

Unlike test_e2e.py (in-process FastMCP client), this spawns
`src/mcpnertes/server.py` as an actual subprocess and speaks MCP over
stdio — the same transport a real client (Claude Desktop, etc.) uses. It
proves the packaged entry point itself works, not just the importable
FastMCP instance.
"""

import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from conftest import CLUSTER_AVAILABLE, CLUSTER_SKIP_REASON

pytestmark = pytest.mark.skipif(not CLUSTER_AVAILABLE, reason=CLUSTER_SKIP_REASON)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


async def test_server_subprocess_lists_all_tools_and_reads_real_namespace(e2e_namespace):
    # Run the packaged entry point exactly as an MCP client would launch it
    # (`python -m mcpnertes.server`), not as a bare script — the package
    # uses relative imports, so `python server.py` breaks on purpose.
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "mcpnertes.server"],
        cwd=str(PROJECT_ROOT),
    )
    async with Client(transport) as client:
        tools = await client.list_tools()
        assert {t.name for t in tools} == {
            "list_pods",
            "list_deployments",
            "get_pod_logs",
            "list_services",
            "list_namespaces",
            "get_events",
            "get_logs",
            "list_nodes",
            "list_resource",
            "get_resource",
            "list_api_resources",
        }

        result = await client.call_tool("list_namespaces", {})
        import json

        names = [ns["name"] for ns in json.loads(result.content[0].text)]
        assert e2e_namespace in names
