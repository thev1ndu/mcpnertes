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

"""Service-related tools: list_services."""

from typing import Optional

from ..app import mcp, ro
from ..config import get_policy
from ..k8s_client import get_manager
from ..sanitize import filter_namespaced


@mcp.tool(
    description="List all services in a namespace or across all namespaces",
    annotations=ro("List Services"),
)
def list_services(namespace: Optional[str] = None):
    """List services, respecting the namespace allowlist and resource blocklist."""
    try:
        policy = get_policy()
        policy.assert_resource_allowed("Service")
        core = get_manager().get_core_api()
        if namespace:
            policy.assert_namespace_allowed(namespace)
            ret = core.list_namespaced_service(namespace=namespace, watch=False)
            items = ret.items
        else:
            ret = core.list_service_for_all_namespaces(watch=False)
            items = filter_namespaced(ret.items)

        services = []
        for item in items:
            ports = []
            if item.spec.ports:
                for port in item.spec.ports:
                    port_info = {
                        "name": port.name,
                        "port": port.port,
                        "target_port": port.target_port,
                        "protocol": port.protocol,
                    }
                    if port.node_port:
                        port_info["node_port"] = port.node_port
                    ports.append(port_info)

            external_ips = item.spec.external_i_ps if hasattr(item.spec, "external_i_ps") else None

            services.append(
                {
                    "name": item.metadata.name,
                    "namespace": item.metadata.namespace,
                    "type": item.spec.type,
                    "cluster_ip": item.spec.cluster_ip,
                    "external_ips": external_ips,
                    "ports": ports,
                    "selector": item.spec.selector,
                    "creation_timestamp": (
                        item.metadata.creation_timestamp.isoformat()
                        if item.metadata.creation_timestamp
                        else None
                    ),
                }
            )
        return services
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}
