# Mcpnertes

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-6f42c1.svg)](https://modelcontextprotocol.io)
[![Read-only](https://img.shields.io/badge/cluster%20access-read--only-brightgreen.svg)](#tools)

Read-only Kubernetes MCP server. Every tool is GET/LIST-only, and every tool
passes through a config-driven policy (`config.toml`) before it touches the
cluster:

- **Namespace allowlist** — `namespaces.allow` defaults to `["*"]` (every
  namespace). Restrict it to an explicit list to scope the server to specific
  namespaces, and use `namespaces.deny` to carve out exceptions.
- **Resource blocklist** — `resources.block` defaults to `["Secret"]`.
  Blocked kinds are refused by every tool, including the generic
  `list_resource`/`get_resource` dynamic-client tools, so there's no way to
  route around the block by asking a different tool.

Both checks happen in a single chokepoint (`mcpnertes.config.Policy`) before
any Kubernetes API call is made — see [`src/mcpnertes/config.py`](src/mcpnertes/config.py).

## Install

```bash
pip install -e .
```

## Run standalone

```bash
mcpnertes
```

## Use from an MCP client (Claude Desktop, Claude Code, etc.)

Add to the client's MCP server config. The policy (namespace allow/deny,
resource block) is set directly in `env` — no `config.toml` file needed.
Once published to PyPI, `uvx` will fetch and run it without a local install:

```json
{
  "mcpServers": {
    "mcpnertes": {
      "command": "uvx",
      "args": ["mcpnertes@latest"],
      "env": {
        "MCPNERTES_NAMESPACE_ALLOW": "*",
        "MCPNERTES_NAMESPACE_DENY": "kube-system,cert-manager",
        "MCPNERTES_RESOURCE_BLOCK": "Secret"
      }
    }
  }
}
```

All three env vars are optional and comma-separated. Omit any of them to
fall back to `config.toml` (if present) or the built-in default (allow all
namespaces, block `Secret`).

**Not yet on PyPI?** Point `uvx` at this checkout instead:

```json
{
  "mcpServers": {
    "mcpnertes": {
      "command": "uvx",
      "args": ["--from", "/absolute/path/to/Mcpnertes", "mcpnertes"],
      "env": {
        "MCPNERTES_NAMESPACE_ALLOW": "*",
        "MCPNERTES_NAMESPACE_DENY": "kube-system,cert-manager",
        "MCPNERTES_RESOURCE_BLOCK": "Secret"
      }
    }
  }
}
```

## Configuring the policy

Two equivalent ways to set it — pick whichever fits how you're running the
server. If both are present, the env vars win field-by-field.

### Env vars (for `mcpServers` configs — no file needed)

| Variable | Format | Default |
|---|---|---|
| `MCPNERTES_NAMESPACE_ALLOW` | comma-separated, `*` = all | `*` |
| `MCPNERTES_NAMESPACE_DENY` | comma-separated | *(empty)* |
| `MCPNERTES_RESOURCE_BLOCK` | comma-separated, case-insensitive | `Secret` |

```json
"env": {
  "MCPNERTES_NAMESPACE_ALLOW": "default,staging",
  "MCPNERTES_NAMESPACE_DENY": "",
  "MCPNERTES_RESOURCE_BLOCK": "Secret,ConfigMap,Ingress"
}
```

### `config.toml` (for standalone runs)

Resolution order (first match wins): `$MCPNERTES_CONFIG`, `./config.toml`
(current working directory), then the `config.toml` shipped next to the
installed package.

```toml
[namespaces]
# "*" = every namespace (default). Replace with an explicit list to scope
# the server to only those namespaces.
allow = ["*"]

# Namespaces to block even if matched by `allow`. `deny` always wins.
deny = []

[resources]
# Resource kinds always refused, regardless of which tool is called
# (including the generic list_resource/get_resource tools). Case-insensitive.
block = ["Secret"]
```

**Scope to specific namespaces:**

```toml
[namespaces]
allow = ["default", "staging"]
deny = []
```

**Allow everything except a couple of sensitive namespaces:**

```toml
[namespaces]
allow = ["*"]
deny = ["kube-system", "cert-manager"]
```

**Block additional resource kinds** (e.g. also hide ConfigMaps and Ingresses):

```toml
[resources]
block = ["Secret", "ConfigMap", "Ingress"]
```

## Tools

| Tool | Description |
|---|---|
| `list_pods` | List pods in a namespace or across all namespaces |
| `list_deployments` | List deployments in a namespace or across all namespaces |
| `get_pod_logs` | Get logs from a specific pod |
| `list_services` | List services in a namespace or across all namespaces |
| `list_namespaces` | List namespaces (filtered by the allowlist) |
| `get_events` | Get cluster events for a namespace or all namespaces |
| `get_logs` | Get logs from a pod/deployment/job/label selector |
| `list_nodes` | List cluster nodes |
| `list_resource` | List any resource kind (including CRDs) via the dynamic client |
| `get_resource` | Get a single resource of any kind by name |
| `list_api_resources` | Discover listable resource kinds the cluster exposes |

## Testing

```bash
pip install -e ".[dev]"
pytest -q
```

`tests/test_config.py` unit-tests the `Policy` allow/deny/block logic in
isolation. `tests/test_e2e.py` and `tests/test_e2e_stdio.py` are full
end-to-end tests with no mocks: they seed a real namespace/pod/deployment
/service/secret on whatever cluster your current kubeconfig context points
to, then drive the actual MCP server (in-process and as a real stdio
subprocess) against it. They auto-skip if no cluster is reachable.

## License

Apache-2.0 — see [LICENSE](LICENSE).
