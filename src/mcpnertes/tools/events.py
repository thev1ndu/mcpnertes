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

"""Event-related tools: get_events."""

from typing import Optional

from ..app import mcp, ro
from ..config import get_policy
from ..k8s_client import get_manager
from ..sanitize import filter_namespaced


@mcp.tool(
    description="Get Kubernetes events from the cluster for a specific namespace or all namespaces",
    annotations=ro("Get Events"),
)
def get_events(namespace: Optional[str] = None, field_selector: Optional[str] = None):
    """Get events, respecting the namespace allowlist and resource blocklist."""
    try:
        policy = get_policy()
        policy.assert_resource_allowed("Event")
        core = get_manager().get_core_api()
        if namespace:
            policy.assert_namespace_allowed(namespace)
            events = core.list_namespaced_event(namespace=namespace, field_selector=field_selector)
            items = events.items
        else:
            events = core.list_event_for_all_namespaces(field_selector=field_selector)
            items = filter_namespaced(events.items)

        event_list = []
        for event in items:
            event_list.append(
                {
                    "type": event.type,
                    "reason": event.reason,
                    "message": event.message,
                    "count": event.count,
                    "first_timestamp": (
                        event.first_timestamp.isoformat() if event.first_timestamp else None
                    ),
                    "last_timestamp": (
                        event.last_timestamp.isoformat() if event.last_timestamp else None
                    ),
                    "involved_object": {
                        "kind": event.involved_object.kind,
                        "name": event.involved_object.name,
                        "namespace": event.involved_object.namespace,
                    },
                    "source": {
                        "component": event.source.component if event.source else None,
                        "host": event.source.host if event.source else None,
                    },
                }
            )

        return {
            "namespace": namespace,
            "field_selector": field_selector,
            "events": event_list,
        }
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Error retrieving events: {str(e)}"}
