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

"""End-to-end tests: real MCP protocol calls, real Kubernetes API, no mocks.

Each test drives the actual mcpnertes.server.mcp instance through a FastMCP
Client (full tool-call dispatch + schema validation, same code path a real
MCP client uses) against the objects tests/conftest.py seeded on the
reachable cluster. This proves the whole stack — tool registration, Policy
enforcement, and the Kubernetes client — works together, not just each
piece in isolation.
"""

import json

import pytest
from fastmcp import Client

from mcpnertes.server import mcp

from conftest import CLUSTER_AVAILABLE, CLUSTER_SKIP_REASON

pytestmark = pytest.mark.skipif(not CLUSTER_AVAILABLE, reason=CLUSTER_SKIP_REASON)


def tool_json(result):
    """FastMCP only auto-parses object-shaped tool results into `.data`;
    list-shaped results (most of our `list_*` tools) land in `.content`
    as text instead, so fall back to decoding that."""
    if result.data is not None:
        return result.data
    return json.loads(result.content[0].text)


@pytest.fixture
async def mcp_client():
    async with Client(mcp) as c:
        yield c


async def test_list_namespaces_includes_seeded_namespace(mcp_client, e2e_namespace):
    result = await mcp_client.call_tool("list_namespaces", {})
    names = [ns["name"] for ns in tool_json(result)]
    assert e2e_namespace in names


async def test_list_pods_finds_seeded_pod(mcp_client, e2e_namespace):
    result = await mcp_client.call_tool("list_pods", {"namespace": e2e_namespace})
    pods = tool_json(result)
    assert any(p["name"] == "e2e-pod" for p in pods)


async def test_get_pod_logs_returns_real_container_output(mcp_client, e2e_namespace):
    result = await mcp_client.call_tool(
        "get_pod_logs", {"namespace": e2e_namespace, "pod_name": "e2e-pod"}
    )
    data = tool_json(result)
    assert any("hello-mcpnertes-e2e" in line for line in data["logs"])


async def test_list_deployments_finds_seeded_deployment(mcp_client, e2e_namespace):
    result = await mcp_client.call_tool("list_deployments", {"namespace": e2e_namespace})
    deployments = tool_json(result)
    assert any(d["name"] == "e2e-deploy" for d in deployments)


async def test_list_services_finds_seeded_service(mcp_client, e2e_namespace):
    result = await mcp_client.call_tool("list_services", {"namespace": e2e_namespace})
    services = tool_json(result)
    assert any(s["name"] == "e2e-svc" for s in services)


async def test_get_logs_by_deployment_name_reaches_real_pod(mcp_client, e2e_namespace):
    result = await mcp_client.call_tool(
        "get_logs",
        {"resource_type": "deployment", "namespace": e2e_namespace, "name": "e2e-deploy"},
    )
    data = tool_json(result)
    assert data["results"], "expected at least one pod's logs from the deployment"


async def test_get_events_does_not_error_for_seeded_namespace(mcp_client, e2e_namespace):
    result = await mcp_client.call_tool("get_events", {"namespace": e2e_namespace})
    data = tool_json(result)
    assert "error" not in data


async def test_get_resource_blocks_secret_even_though_it_really_exists(mcp_client, e2e_namespace):
    result = await mcp_client.call_tool(
        "get_resource",
        {"kind": "Secret", "name": "e2e-secret", "namespace": e2e_namespace},
    )
    data = tool_json(result)
    assert "blocked by policy" in data["error"]


async def test_list_resource_configmap_is_not_blocked(mcp_client, e2e_namespace):
    result = await mcp_client.call_tool(
        "list_resource", {"kind": "ConfigMap", "namespace": e2e_namespace}
    )
    configmaps = tool_json(result)
    assert any(cm["metadata"]["name"] == "e2e-configmap" for cm in configmaps)


async def test_list_api_resources_omits_blocked_secret_kind(mcp_client):
    result = await mcp_client.call_tool("list_api_resources", {})
    kinds = {r["kind"] for r in tool_json(result)}
    assert "Secret" not in kinds
    assert "Pod" in kinds


async def test_namespace_denylist_filters_a_real_namespace(e2e_namespace, tmp_path, monkeypatch):
    """Point at a config.toml that denies the seeded (real, currently-existing)
    namespace and confirm every cross-namespace tool call actually filters
    it out of live cluster data, not just a mocked one."""
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        f'[namespaces]\nallow = ["*"]\ndeny = ["{e2e_namespace}"]\n'
        '[resources]\nblock = ["Secret"]\n'
    )
    monkeypatch.setenv("MCPNERTES_CONFIG", str(cfg))

    import mcpnertes.config as config_module

    config_module._policy = None
    try:
        async with Client(mcp) as client:
            result = await client.call_tool("list_pods", {})
            pods = tool_json(result)
            assert not any(p["namespace"] == e2e_namespace for p in pods)

            result = await client.call_tool("list_namespaces", {})
            names = [ns["name"] for ns in tool_json(result)]
            assert e2e_namespace not in names

            result = await client.call_tool(
                "get_pod_logs", {"namespace": e2e_namespace, "pod_name": "e2e-pod"}
            )
            data = tool_json(result)
            assert "not allowed by policy" in data["error"]
    finally:
        config_module._policy = None
