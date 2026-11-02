# bitdefender-mcp

MCP server for [Bitdefender GravityZone](https://www.bitdefender.com/business/) --
lets an Agent review a tenant's endpoint-protection policies and triage
GravityZone security events (incidents): list and inspect policies and
managed endpoints, list and inspect incidents, change incident priority,
(re)assign an incident, and isolate / restore an endpoint during an active
incident.

- Transport: MCP **Streamable HTTP** (`POST /mcp`), stateless.
- Stack: Python 3.12, `uv`, FastMCP, `httpx`.
- License: Apache-2.0. Copyright MSPbots.ai.

Vendor API: Bitdefender Control Center / GravityZone public API, JSON-RPC 2.0
over HTTPS. [API overview](https://www.bitdefender.com/business/support/en/77212-125277-public-api.html) ·
[Control Center API Guide (PDF)](https://www.bitdefender.pl/download/Bitdefender_Control_Center_API_Guide_On-premise_version_enUS.pdf).

---

<div align="center">

## MSPbots Connector

**The MCP Gateway built for MSPs: visible, controlled, and your data stays where it belongs.**

[**Get started at connect.mspbots.ai →**](https://connect.mspbots.ai)

</div>

---

MSPbots Connector gives your AI clients one MCP URL to reach your entire MSP stack (RMM, PSA, documentation, security, finance), and gives you control over who can call which tool and a record of everything that was called.

**Hosted service: [connect.mspbots.ai](https://connect.mspbots.ai)** · Free to use.

### Why Connector

![MSPbots Connector](https://stgoss.mspbots.ai/files/mcp/mspbots-mcp.png)

| | |
|---|---|
| **Visible** | Every tool call is logged: who, which vendor, when. Usage dashboard, CSV export, SIEM streaming. |
| **Controlled** | Role-based, per-tool allowlist. Deny by default. |
| **Protected** | Credentials encrypted per record. AI clients never see your vendor passwords or tokens. |
| **MSP-native** | Built for the MSP stack only: RMM, PSA, documentation, security, finance. |

### Quick start

1. **Sign up** at [connect.mspbots.ai](https://connect.mspbots.ai).
2. **Connect your vendors.** Pick from 150+ connectors and authorize each one on the vendor's own page, or bring your own API keys. No extra vendor accounts needed.
3. **Set access.** Create roles and decide which tools each role may call. Nothing is allowed until you allow it.
4. **Add your MCP URL to your AI client.** Copy the URL from your Connector dashboard into Claude, ChatGPT, Cursor, VS Code, Gemini, Codex, or any MCP-capable client.
5. **Ask your AI to do real work**, and watch every call appear in the audit log.

### Features

**Unified gateway**
- One MCP URL for all your AI clients
- 150+ connectors across the MSP stack
- Custom MCP servers supported, free
- Authorization happens on each vendor's own page; the AI never sees passwords or tokens
- Bring your own credentials: use the vendor API keys you already have
- Multiple accounts per app; connect once, reuse across AI clients
- Tool search: finds the right action for the task
- One sign-in; vendor credentials are injected behind the scenes and OAuth tokens refresh automatically

**Visibility**
- Audit log for every tool call (who, which vendor, when)
- Usage dashboard: call volume, top vendors, error rate, per-user activity
- Export audit logs to CSV, or stream to Loki, Graylog, or LogScale (SIEM)
- Optional recording of tool arguments and result summaries (off by default, enabled per organization)

**Control**
- Per-role, per-tool allowlist, deny by default
- owner / admin / member roles
- SCIM provisioning with Entra ID, Okta, JumpCloud, and Google Workspace

**Security**
- Credentials encrypted one record at a time (AES-256-GCM, per-record key)
- AI clients authenticate with OAuth 2.1 + PKCE
- Vendor responses are scanned for prompt-injection patterns and returned as structured data. This is one layer of defense, not a guarantee against every attack.
- Static egress IP for customer firewall and API allowlisting

### Pricing

**Free.**

Links: [connect.mspbots.ai](https://connect.mspbots.ai) · [mspbots.ai](https://mspbots.ai)

---

## Authentication headers

Every `/mcp` request must carry the tenant's GravityZone API key. Credentials
are read only from these headers -- never from an environment variable, and
never shared between requests.

| Header | Required | Meaning | Where to get it |
|---|---|---|---|
| `X-Bitdefender-Api-Key` | Yes | GravityZone Control Center API key, used as the username in HTTP Basic auth (empty password) | Control Center → My Account → API keys |
| `X-Bitdefender-Base-Url` | No | Control Center Access URL for this tenant. Defaults to `https://cloud.gravityzone.bitdefender.com/api` (Bitdefender's own cloud); set this for on-premise / custom Control Center installs | Control Center → My Account → API keys (the "Access URL" shown next to the key) |

Missing `X-Bitdefender-Api-Key` returns HTTP 401 listing the required header,
never a 500.

## Tools

Ten tools across three GravityZone API categories. Policy authoring /
assignment is out of scope -- GravityZone's public API only documents
policy visibility (`getPoliciesList` / `getPolicyDetails`), not an
assign-to-endpoint method.

| Tool | Category | Description |
|---|---|---|
| `bitdefender_list_policies` | Policies | List the tenant's configured endpoint-protection policies |
| `bitdefender_get_policy_details` | Policies | Get one policy's full configuration by id |
| `bitdefender_list_endpoints` | Network | List the tenant's managed endpoints |
| `bitdefender_get_endpoint_details` | Network | Get one endpoint's assigned policy and protection status |
| `bitdefender_list_incidents` | Incidents | List the tenant's security incidents |
| `bitdefender_get_incident` | Incidents | Get one incident's affected endpoints and timeline |
| `bitdefender_change_incident_priority` | Incidents | Change an incident's priority |
| `bitdefender_assign_incident` | Incidents | Assign an incident to one or more GravityZone users |
| `bitdefender_isolate_endpoint` | Incidents | Isolate an endpoint under active investigation (destructive) |
| `bitdefender_restore_endpoint_from_isolation` | Incidents | Restore a previously isolated endpoint |

All tools return a compact JSON string. Errors use the fixed envelope
`{"error": {"code", "message", "retryable"}}` with `code` in
`not_configured | unauthorized | not_found | invalid_argument | rate_limited | upstream_error`.
`list` tools accept `page` / `per_page` (default 50, capped at 200) and
return GravityZone's own `page` / `per_page` / `pages_count` / `total`
alongside `items`.

## Rate limiting

GravityZone enforces 10 requests/second per API key (HTTP 429 beyond that).
This service backs off with bounded retry honoring `Retry-After` and
surfaces `rate_limited` once retries are exhausted, rather than hanging or
crashing.

## Local development

```bash
uv sync
uv run pytest
uv run python -m bitdefender_mcp   # serves on 0.0.0.0:8080
```

`docker-compose.yml` is for local debugging only; it is not used in
deployment. Provide your own test tenant's `X-Bitdefender-Api-Key` as a
request header, never as an environment variable.

```bash
docker build --platform linux/amd64 -t bitdefender-mcp:dev .
```
