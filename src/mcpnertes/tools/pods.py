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

from typing import Optional

from kubernetes import client

from ..app import mcp, ro
from ..config import get_policy
from ..k8s_client import get_manager
from ..sanitize import filter_namespaced


@mcp.tool(
    description="List all pods in a namespace or across all namespaces",
    annotations=ro("List Pods"),
)
def list_pods(namespace: Optional[str] = None):
    try:
        policy = get_policy()
        policy.assert_resource_allowed("Pod")
        core = get_manager().get_core_api()
        if namespace:
            policy.assert_namespace_allowed(namespace)
            ret = core.list_namespaced_pod(namespace=namespace, watch=False)
            items = ret.items
        else:
            ret = core.list_pod_for_all_namespaces(watch=False)
            items = filter_namespaced(ret.items)

        pods = []
        for i in items:
            pods.append(
                {
                    "name": i.metadata.name,
                    "namespace": i.metadata.namespace,
                    "ip": i.status.pod_ip,
                    "status": i.status.phase,
                    "labels": i.metadata.labels,
                    "creation_timestamp": (
                        i.metadata.creation_timestamp.isoformat()
                        if i.metadata.creation_timestamp
                        else None
                    ),
                    "node": i.spec.node_name,
                    "containers": [c.name for c in i.spec.containers],
                }
            )
        return pods
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool(
    description="Get logs from a pod in a specified namespace",
    annotations=ro("Get Pod Logs"),
)
def get_pod_logs(
    namespace: str,
    pod_name: str,
    container: Optional[str] = None,
    tail_lines: Optional[int] = None,
    previous: bool = False,
):
    try:
        policy = get_policy()
        policy.assert_resource_allowed("Pod")
        policy.assert_namespace_allowed(namespace)
        core = get_manager().get_core_api()

        pod_info = core.read_namespaced_pod(name=pod_name, namespace=namespace)
        container_names = [c.name for c in pod_info.spec.containers]

        if not container and container_names:
            container = container_names[0]

        logs = core.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container,
            tail_lines=tail_lines,
            previous=previous,
        )

        return {
            "pod_name": pod_name,
            "namespace": namespace,
            "container": container,
            "logs": logs.split("\n"),
            "container_names": container_names,
            "status": pod_info.status.phase,
        }
    except PermissionError as e:
        return {"error": str(e)}
    except client.exceptions.ApiException as e:
        if e.status == 404:
            return {"error": f"Pod {pod_name} not found in namespace {namespace}"}
        return {"error": f"Error retrieving logs: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
