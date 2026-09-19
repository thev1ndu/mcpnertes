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

from mcpnertes.config import Policy, load_policy


def test_default_allow_star_permits_any_namespace():
    policy = Policy(allow=["*"], deny=[], block=["Secret"])
    assert policy.is_namespace_allowed("default")
    assert policy.is_namespace_allowed("kube-system")


def test_deny_wins_over_allow_star():
    policy = Policy(allow=["*"], deny=["kube-system"], block=[])
    assert not policy.is_namespace_allowed("kube-system")
    assert policy.is_namespace_allowed("default")


def test_explicit_allow_list_restricts_namespaces():
    policy = Policy(allow=["default", "staging"], deny=[], block=[])
    assert policy.is_namespace_allowed("default")
    assert not policy.is_namespace_allowed("production")


def test_resource_block_is_case_insensitive():
    policy = Policy(allow=["*"], deny=[], block=["Secret"])
    assert policy.is_resource_blocked("secret")
    assert policy.is_resource_blocked("Secret")
    assert not policy.is_resource_blocked("Pod")


def test_assert_helpers_raise_permission_error():
    policy = Policy(allow=["default"], deny=[], block=["Secret"])
    try:
        policy.assert_namespace_allowed("other")
        assert False, "expected PermissionError"
    except PermissionError:
        pass

    try:
        policy.assert_resource_allowed("Secret")
        assert False, "expected PermissionError"
    except PermissionError:
        pass


def test_load_policy_env_vars_override_config_toml(tmp_path, monkeypatch):
    """MCP client `env` blocks should be able to set the whole policy with
    no config.toml on disk, or override individual fields of one that is."""
    cfg = tmp_path / "config.toml"
    cfg.write_text('[namespaces]\nallow = ["default"]\ndeny = []\n[resources]\nblock = ["Secret"]\n')
    monkeypatch.setenv("MCPNERTES_CONFIG", str(cfg))
    monkeypatch.setenv("MCPNERTES_NAMESPACE_ALLOW", "*")
    monkeypatch.setenv("MCPNERTES_NAMESPACE_DENY", "kube-system, cert-manager")
    monkeypatch.setenv("MCPNERTES_RESOURCE_BLOCK", "Secret,ConfigMap")

    policy = load_policy()

    assert policy.is_namespace_allowed("staging")  # file said only "default"; env said "*"
    assert not policy.is_namespace_allowed("kube-system")
    assert not policy.is_namespace_allowed("cert-manager")
    assert policy.is_resource_blocked("ConfigMap")
    assert policy.is_resource_blocked("Secret")


def test_load_policy_env_vars_work_with_no_config_toml_at_all(tmp_path, monkeypatch):
    monkeypatch.delenv("MCPNERTES_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)  # no config.toml in this directory
    monkeypatch.setenv("MCPNERTES_NAMESPACE_ALLOW", "default,staging")
    monkeypatch.setenv("MCPNERTES_RESOURCE_BLOCK", "Secret")

    policy = load_policy()

    assert policy.is_namespace_allowed("default")
    assert not policy.is_namespace_allowed("production")
    assert policy.is_resource_blocked("Secret")
