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

"""Shared e2e fixtures: seed real objects on the reachable Kubernetes cluster.

These are true end-to-end tests: no mocks. Fixture setup uses the
`kubernetes` client directly (independent of the code under test) to create
a throwaway namespace with a Pod, Deployment, Service, ConfigMap, and
Secret, then the tests drive the actual mcpnertes MCP server against them.
"""

import time
import uuid

import pytest
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config


def _cluster_reachable() -> bool:
    try:
        k8s_config.load_kube_config()
        k8s_client.CoreV1Api().list_namespace(_request_timeout=5)
        return True
    except Exception:
        return False


CLUSTER_AVAILABLE = _cluster_reachable()
CLUSTER_SKIP_REASON = "no reachable Kubernetes cluster (checked current kubeconfig context)"


def _wait_for_pod_running(core: k8s_client.CoreV1Api, namespace: str, name: str, timeout: float = 90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pod = core.read_namespaced_pod(name=name, namespace=namespace)
        if pod.status.phase == "Running":
            return pod
        time.sleep(2)
    raise TimeoutError(f"Pod {name} in {namespace} did not reach Running within {timeout}s")


@pytest.fixture(scope="session")
def e2e_namespace():
    """Create a real namespace with a Pod, Deployment, Service, ConfigMap, and
    Secret on the cluster from the current kubeconfig context, and delete it
    when the test session ends."""
    if not CLUSTER_AVAILABLE:
        pytest.skip(CLUSTER_SKIP_REASON)

    k8s_config.load_kube_config()
    core = k8s_client.CoreV1Api()
    apps = k8s_client.AppsV1Api()

    ns_name = f"mcpnertes-e2e-{uuid.uuid4().hex[:8]}"
    core.create_namespace(
        k8s_client.V1Namespace(metadata=k8s_client.V1ObjectMeta(name=ns_name))
    )

    core.create_namespaced_config_map(
        ns_name,
        k8s_client.V1ConfigMap(
            metadata=k8s_client.V1ObjectMeta(name="e2e-configmap"),
            data={"key": "value"},
        ),
    )
    core.create_namespaced_secret(
        ns_name,
        k8s_client.V1Secret(
            metadata=k8s_client.V1ObjectMeta(name="e2e-secret"),
            string_data={"password": "hunter2"},
        ),
    )
    core.create_namespaced_pod(
        ns_name,
        k8s_client.V1Pod(
            metadata=k8s_client.V1ObjectMeta(name="e2e-pod", labels={"app": "e2e-pod"}),
            spec=k8s_client.V1PodSpec(
                containers=[
                    k8s_client.V1Container(
                        name="main",
                        image="busybox:1.36",
                        command=["sh", "-c", "echo hello-mcpnertes-e2e; sleep 3600"],
                    )
                ]
            ),
        ),
    )
    apps.create_namespaced_deployment(
        ns_name,
        k8s_client.V1Deployment(
            metadata=k8s_client.V1ObjectMeta(name="e2e-deploy"),
            spec=k8s_client.V1DeploymentSpec(
                replicas=1,
                selector=k8s_client.V1LabelSelector(match_labels={"app": "e2e-deploy"}),
                template=k8s_client.V1PodTemplateSpec(
                    metadata=k8s_client.V1ObjectMeta(labels={"app": "e2e-deploy"}),
                    spec=k8s_client.V1PodSpec(
                        containers=[
                            k8s_client.V1Container(
                                name="main",
                                image="busybox:1.36",
                                command=["sh", "-c", "sleep 3600"],
                            )
                        ]
                    ),
                ),
            ),
        ),
    )
    core.create_namespaced_service(
        ns_name,
        k8s_client.V1Service(
            metadata=k8s_client.V1ObjectMeta(name="e2e-svc"),
            spec=k8s_client.V1ServiceSpec(
                selector={"app": "e2e-deploy"},
                ports=[k8s_client.V1ServicePort(port=80, target_port=8080)],
            ),
        ),
    )

    _wait_for_pod_running(core, ns_name, "e2e-pod")

    yield ns_name

    core.delete_namespace(ns_name)
