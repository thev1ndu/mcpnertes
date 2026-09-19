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

"""Deployment-related tools: list_deployments."""

from typing import Optional

from ..app import mcp, ro
from ..config import get_policy
from ..k8s_client import get_manager
from ..sanitize import filter_namespaced

@mcp.tool(
    description="List all deployments in a specified namespace",
    annotations=ro("List Deployments"),
)
def list_deployments(namespace: Optional[str] = None):
    """List deployments, respecting the namespace allowlist and resource blocklist."""
    try:
        policy = get_policy()
        policy.assert_resource_allowed("Deployment")
        apps = get_manager().get_apps_api()
        if namespace:
            policy.assert_namespace_allowed(namespace)
            ret = apps.list_namespaced_deployment(namespace=namespace, watch=False)
            items = ret.items
        else:
            ret = apps.list_deployment_for_all_namespaces(watch=False)
            items = filter_namespaced(ret.items)

        deployments = []
        for item in items:
            deployments.append(
                {
                    "name": item.metadata.name,
                    "namespace": item.metadata.namespace,
                    "replicas": item.spec.replicas,
                    "available_replicas": item.status.available_replicas,
                    "labels": item.metadata.labels,
                    "creation_timestamp": (
                        item.metadata.creation_timestamp.isoformat()
                        if item.metadata.creation_timestamp
                        else None
                    ),
                    "selector": (item.spec.selector.match_labels if item.spec.selector else None),
                }
            )
        return deployments
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}
