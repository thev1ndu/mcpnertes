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

"""Cross-resource log tool: get_logs (pods, deployments, jobs, label selectors)."""

from typing import Optional

from kubernetes import client

from ..app import mcp, ro
from ..config import get_policy
from ..k8s_client import get_manager
from ..sanitize import filter_namespaced


@mcp.tool(
    description="Get logs from pods, deployments, jobs, or resources matching a label selector",
    annotations=ro("Get Logs"),
)
def get_logs(
    resource_type: str,
    namespace: Optional[str] = None,
    name: Optional[str] = None,
    label_selector: Optional[str] = None,
    container: Optional[str] = None,
    tail: Optional[int] = None,
    since_seconds: Optional[int] = None,
    timestamps: bool = False,
):
    """Get logs from pods/deployments/jobs, respecting the namespace allowlist."""
    try:
        policy = get_policy()
        policy.assert_resource_allowed("Pod")
        manager = get_manager()
        core = manager.get_core_api()

        if not name and not label_selector:
            return {"error": "Either name or label_selector must be provided"}

        if name and not namespace:
            namespace = "default"
        if namespace:
            policy.assert_namespace_allowed(namespace)

        pods_to_get_logs_from = []

        if resource_type.lower() == "pod" and name:
            try:
                pod = core.read_namespaced_pod(name=name, namespace=namespace)
                pods_to_get_logs_from.append(pod)
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    return {"error": f"Pod {name} not found in namespace {namespace}"}
                raise

        elif resource_type.lower() == "deployment" and name:
            policy.assert_resource_allowed("Deployment")
            try:
                deployment = manager.get_apps_api().read_namespaced_deployment(
                    name=name, namespace=namespace
                )
                selector = deployment.spec.selector.match_labels
                label_selector = ",".join(f"{k}={v}" for k, v in selector.items())
                pods = core.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
                pods_to_get_logs_from.extend(pods.items)
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    return {"error": f"Deployment {name} not found in namespace {namespace}"}
                raise

        elif resource_type.lower() == "job" and name:
            policy.assert_resource_allowed("Job")
            try:
                job = manager.get_batch_api().read_namespaced_job(name=name, namespace=namespace)
                selector = job.spec.selector.match_labels
                label_selector = ",".join(f"{k}={v}" for k, v in selector.items())
                pods = core.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
                pods_to_get_logs_from.extend(pods.items)
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    return {"error": f"Job {name} not found in namespace {namespace}"}
                raise

        elif label_selector:
            if namespace:
                pods = core.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
                pods_to_get_logs_from.extend(pods.items)
            else:
                pods = core.list_pod_for_all_namespaces(label_selector=label_selector)
                pods_to_get_logs_from.extend(filter_namespaced(pods.items))

        else:
            return {
                "error": (
                    f"Unsupported resource type: {resource_type} or missing required parameters"
                )
            }

        if not pods_to_get_logs_from:
            return {"error": "No pods found matching the specified criteria"}

        results = []
        for pod in pods_to_get_logs_from:
            pod_name = pod.metadata.name
            pod_namespace = pod.metadata.namespace
            container_names = [c.name for c in pod.spec.containers]

            container_to_use = container
            if not container_to_use and container_names:
                container_to_use = container_names[0]

            try:
                logs = core.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=pod_namespace,
                    container=container_to_use,
                    tail_lines=tail,
                    timestamps=timestamps,
                    since_seconds=since_seconds,
                )
                results.append(
                    {
                        "pod_name": pod_name,
                        "namespace": pod_namespace,
                        "container": container_to_use,
                        "logs": logs.split("\n"),
                        "container_names": container_names,
                        "status": pod.status.phase,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "pod_name": pod_name,
                        "namespace": pod_namespace,
                        "error": str(e),
                    }
                )

        return {
            "resource_type": resource_type,
            "name": name,
            "namespace": namespace,
            "label_selector": label_selector,
            "results": results,
        }
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Error retrieving logs: {str(e)}"}
