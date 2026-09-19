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

"""Loads config.toml (env vars can override individual fields) into a
Policy every tool consults before touching the cluster."""

import os
import sys
from pathlib import Path
from typing import Iterable, List, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

_ENV_VAR = "MCPNERTES_CONFIG"
_ENV_NAMESPACE_ALLOW = "MCPNERTES_NAMESPACE_ALLOW"
_ENV_NAMESPACE_DENY = "MCPNERTES_NAMESPACE_DENY"
_ENV_RESOURCE_BLOCK = "MCPNERTES_RESOURCE_BLOCK"
_DEFAULT_ALLOW = ["*"]
_DEFAULT_DENY: List[str] = []
_DEFAULT_BLOCK = ["Secret"]


def _split_csv_env(name: str) -> Optional[List[str]]:
    raw = os.environ.get(name)
    if raw is None:
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


def _resolve_config_path() -> Path | None:
    env_path = os.environ.get(_ENV_VAR)
    if env_path and Path(env_path).is_file():
        return Path(env_path)

    cwd_path = Path.cwd() / "config.toml"
    if cwd_path.is_file():
        return cwd_path

    # Ships inside the package itself (see [tool.setuptools.package-data] in
    # pyproject.toml) so this also works for a real install, not just an
    # editable checkout.
    package_path = Path(__file__).resolve().parent / "config.toml"
    if package_path.is_file():
        return package_path

    return None


class Policy:
    def __init__(self, allow: Iterable[str], deny: Iterable[str], block: Iterable[str]):
        self._allow = list(allow)
        self._deny = list(deny)
        self._block = [kind.lower() for kind in block]

    def is_namespace_allowed(self, namespace: str) -> bool:
        if namespace in self._deny:
            return False
        return "*" in self._allow or namespace in self._allow

    def assert_namespace_allowed(self, namespace: str) -> None:
        if not self.is_namespace_allowed(namespace):
            raise PermissionError(f"Namespace '{namespace}' is not allowed by policy")

    def is_resource_blocked(self, kind: str) -> bool:
        return kind.lower() in self._block

    def assert_resource_allowed(self, kind: str) -> None:
        if self.is_resource_blocked(kind):
            raise PermissionError(f"Resource kind '{kind}' is blocked by policy")


def load_policy() -> Policy:
    # Env vars win over config.toml field-by-field, so an mcpServers `env`
    # block can set the whole policy with no config.toml on disk.
    path = _resolve_config_path()
    if path is None:
        allow, deny, block = _DEFAULT_ALLOW, _DEFAULT_DENY, _DEFAULT_BLOCK
    else:
        with path.open("rb") as f:
            raw = tomllib.load(f)
        namespaces = raw.get("namespaces", {})
        resources = raw.get("resources", {})
        allow = namespaces.get("allow", _DEFAULT_ALLOW)
        deny = namespaces.get("deny", _DEFAULT_DENY)
        block = resources.get("block", _DEFAULT_BLOCK)

    env_allow = _split_csv_env(_ENV_NAMESPACE_ALLOW)
    env_deny = _split_csv_env(_ENV_NAMESPACE_DENY)
    env_block = _split_csv_env(_ENV_RESOURCE_BLOCK)

    return Policy(
        allow=env_allow if env_allow is not None else allow,
        deny=env_deny if env_deny is not None else deny,
        block=env_block if env_block is not None else block,
    )


_policy: Optional[Policy] = None


def get_policy() -> Policy:
    global _policy
    if _policy is None:
        _policy = load_policy()
    return _policy
