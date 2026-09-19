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

"""Namespace-related tools: list_namespaces."""

from ..app import mcp, ro
from ..config import get_policy
from ..k8s_client import get_manager


@mcp.tool(
    description="List all namespaces in the cluster (filtered by the namespace allowlist)",
    annotations=ro("List Namespaces"),
)
def list_namespaces():
    """List namespaces, filtered by the namespace allowlist/denylist."""
    try:
        policy = get_policy()
        policy.assert_resource_allowed("Namespace")
        ret = get_manager().get_core_api().list_namespace(watch=False)

        namespaces = []
        for item in ret.items:
            if not policy.is_namespace_allowed(item.metadata.name):
                continue
            namespaces.append(
                {
                    "name": item.metadata.name,
                    "status": item.status.phase,
                    "creation_timestamp": (
                        item.metadata.creation_timestamp.isoformat()
                        if item.metadata.creation_timestamp
                        else None
                    ),
                }
            )
        return namespaces
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}
