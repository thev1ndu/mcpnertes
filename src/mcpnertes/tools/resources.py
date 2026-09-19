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

"""Generic dynamic-client tools: list_resource, get_resource, list_api_resources.

These work for built-in kinds and CRDs alike. The resource blocklist check
happens here before any API call, so a blocked kind (e.g. Secret) cannot be
read through this generic path even if it's exposed through a typed tool
elsewhere.
"""

from typing import Optional

from kubernetes.dynamic.resource import ResourceList

from ..app import mcp, ro
from ..config import get_policy
from ..k8s_client import get_manager
from ..sanitize import sanitize


@mcp.tool(
    description=(
        "List resources of any kind (including CRDs) via the dynamic client. "
        "GET/LIST only; never mutates. Blocked kinds (see config.toml) are refused."
    ),
    annotations=ro("List Resource"),
)
def list_resource(
    kind: str,
    api_version: str = "v1",
    namespace: Optional[str] = None,
    label_selector: Optional[str] = None,
    field_selector: Optional[str] = None,
):
    """List resources of an arbitrary kind, enforcing the resource blocklist and
    namespace allowlist. This is the chokepoint a blocked kind (e.g. Secret)
    cannot be routed around: it's checked before any API call is made."""
    try:
        policy = get_policy()
        policy.assert_resource_allowed(kind)
        if namespace:
            policy.assert_namespace_allowed(namespace)

        dyn = get_manager().get_dynamic_api()
        api = dyn.resources.get(api_version=api_version, kind=kind)
        res = api.get(
            namespace=namespace,
            label_selector=label_selector,
            field_selector=field_selector,
        )
        items = [item.to_dict() for item in res.items]
        if not namespace:
            items = [
                item
                for item in items
                if not isinstance(item.get("metadata"), dict)
                or item["metadata"].get("namespace") is None
                or policy.is_namespace_allowed(item["metadata"]["namespace"])
            ]
        return [sanitize(item, kind) for item in items]
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool(
    description=(
        "Get a single resource of any kind (including CRDs) by name via the "
        "dynamic client. GET only; never mutates. Blocked kinds are refused."
    ),
    annotations=ro("Get Resource"),
)
def get_resource(
    kind: str,
    name: str,
    api_version: str = "v1",
    namespace: Optional[str] = None,
):
    """Get a single resource by name, enforcing the resource blocklist and
    namespace allowlist before making the API call."""
    try:
        policy = get_policy()
        policy.assert_resource_allowed(kind)
        if namespace:
            policy.assert_namespace_allowed(namespace)

        dyn = get_manager().get_dynamic_api()
        api = dyn.resources.get(api_version=api_version, kind=kind)
        res = api.get(name=name, namespace=namespace)
        return sanitize(res.to_dict(), kind)
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool(
    description=(
        "Discover which resource kinds (including CRDs) the cluster exposes and "
        "can be listed. Read-only discovery; blocked kinds are omitted."
    ),
    annotations=ro("List API Resources"),
)
def list_api_resources():
    """Enumerate listable resource kinds, omitting anything in the resource blocklist."""
    try:
        policy = get_policy()
        dyn = get_manager().get_dynamic_api()
        resources = []
        seen = set()
        for resource in dyn.resources.search():
            if isinstance(resource, ResourceList):
                continue
            verbs = resource.verbs or []
            if "list" not in verbs:
                continue
            if policy.is_resource_blocked(resource.kind):
                continue
            key = (resource.group_version, resource.kind)
            if key in seen:
                continue
            seen.add(key)
            resources.append(
                {
                    "group_version": resource.group_version,
                    "kind": resource.kind,
                    "namespaced": resource.namespaced,
                    "verbs": list(verbs),
                }
            )
        return resources
    except Exception as e:
        return {"error": str(e)}
