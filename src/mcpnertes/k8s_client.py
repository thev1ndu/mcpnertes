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

"""Lazy singleton Kubernetes API client connections (read-only use)."""

from typing import Optional

from kubernetes import client, config, dynamic


class KubernetesManager:
    def __init__(self):
        try:
            config.load_kube_config()
        except Exception:
            config.load_incluster_config()

        self.core_api = client.CoreV1Api()
        self.apps_api = client.AppsV1Api()
        self.batch_api = client.BatchV1Api()
        self.dynamic_api = dynamic.DynamicClient(client.ApiClient())

    def get_core_api(self):
        return self.core_api

    def get_apps_api(self):
        return self.apps_api

    def get_batch_api(self):
        return self.batch_api

    def get_dynamic_api(self):
        return self.dynamic_api


_manager: Optional[KubernetesManager] = None


def get_manager() -> KubernetesManager:
    global _manager
    if _manager is None:
        _manager = KubernetesManager()
    return _manager
