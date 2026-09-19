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

from .config import get_policy


def sanitize(obj_dict, kind):
    if not isinstance(obj_dict, dict):
        return obj_dict
    metadata = obj_dict.get("metadata")
    if isinstance(metadata, dict):
        metadata.pop("managedFields", None)
    if kind == "Secret":
        # Belt-and-suspenders on top of Policy's block: still strip values
        # even if an operator removes Secret from resources.block. The
        # last-applied-configuration annotation can embed the full manifest
        # (including data/stringData) from a client-side `kubectl apply`.
        obj_dict.pop("data", None)
        obj_dict.pop("stringData", None)
        if isinstance(metadata, dict):
            annotations = metadata.get("annotations")
            if isinstance(annotations, dict):
                annotations.pop("kubectl.kubernetes.io/last-applied-configuration", None)
    return obj_dict


def filter_namespaced(items, namespace_of=lambda item: item.metadata.namespace):
    # Only needed for the "no namespace given" path — the Kubernetes API
    # has no server-side allowlist concept, so cluster-wide lists must be
    # filtered client-side.
    policy = get_policy()
    return [item for item in items if policy.is_namespace_allowed(namespace_of(item))]
