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

"""Node-related tools: list_nodes."""

from ..app import mcp, ro
from ..config import get_policy
from ..k8s_client import get_manager


@mcp.tool(
    description="List all nodes in the cluster",
    annotations=ro("List Nodes"),
)
def list_nodes():
    """List cluster nodes (cluster-scoped; no namespace filtering applies)."""
    try:
        get_policy().assert_resource_allowed("Node")
        ret = get_manager().get_core_api().list_node(watch=False)

        nodes = []
        for item in ret.items:
            status = None
            for condition in item.status.conditions:
                if condition.type == "Ready":
                    status = "Ready" if condition.status == "True" else "NotReady"
                    break

            roles = [role for role in item.metadata.labels if "node-role.kubernetes.io" in role]
            if not roles:
                roles = ["<none>"]

            addresses = {address.type: address.address for address in item.status.addresses}

            node_info = item.status.node_info
            nodes.append(
                {
                    "name": item.metadata.name,
                    "status": status,
                    "roles": roles,
                    "addresses": addresses,
                    "capacity": {
                        "cpu": item.status.capacity.get("cpu"),
                        "memory": item.status.capacity.get("memory"),
                        "pods": item.status.capacity.get("pods"),
                    },
                    "allocatable": {
                        "cpu": item.status.allocatable.get("cpu"),
                        "memory": item.status.allocatable.get("memory"),
                        "pods": item.status.allocatable.get("pods"),
                    },
                    "node_info": {
                        "kubelet_version": node_info.kubelet_version,
                        "os_image": node_info.os_image,
                        "container_runtime_version": node_info.container_runtime_version,
                    },
                    "creation_timestamp": (
                        item.metadata.creation_timestamp.isoformat()
                        if item.metadata.creation_timestamp
                        else None
                    ),
                    "labels": item.metadata.labels,
                    "taints": (
                        [
                            {"key": t.key, "value": t.value, "effect": t.effect}
                            for t in item.spec.taints
                        ]
                        if item.spec.taints
                        else []
                    ),
                }
            )
        return nodes
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}
