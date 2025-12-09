# Azure Foundry Claude Proxy (OpenAI-Compatible)

Use Claude Sonnet 4.5 (or any Azure AI Foundry model) from OpenAI SDKs and other OpenAI‑compatible clients via a local OpenAI‑style API:

- Local endpoint: `http://127.0.0.1:18000/v1`
- Implemented routes: `GET /v1/models`, `POST /v1/chat/completions`, `POST /v1/completions`
- Features: streaming + non‑stream chat, basic `tool_calls` bridge (`read_file`), OpenAI‑compatible JSON/SSE responses

This proxy uses a single auth mode:

- **API key (Anthropic endpoint on Azure AI Foundry)**  
  Uses an Azure AI Foundry API key for Claude with the Anthropic‑compatible endpoint.

---

## Setup

### Requirements

- Python 3.9+ with `pip`
- Packages (installed via `requirements.txt`):
  - `fastapi`, `uvicorn`, `requests`, `anthropic`, `bcrypt`

### Install

Clone the repo and check out the `generic-openai-foundry-proxy` branch (until it is merged to `main`), then create a virtualenv:

```shell
git clone https://github.com/chrsandb/foundry_claude_proxy.git
cd foundry_claude_proxy
git checkout generic-openai-foundry-proxy

python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### Configuration

The proxy does not store any central Foundry configuration. All upstream Foundry settings are derived per request from:

- The logical `apiKey` (from `Authorization: Bearer <token>`), and  
- The logical `model` field in the request body.

To talk to Azure AI Foundry, you must know:

- Your Foundry **resource name** (call it `<RESOURCE_NAME>`), which appears in the endpoint URL in the Azure portal, e.g.:  
  `https://<RESOURCE_NAME>.services.ai.azure.com/...`  
- A **Foundry API key** for that resource with access to Claude (`<FOUNDRY_API_KEY>`).

You then encode those into `apiKey` and/or `model`:

- Recommended simplest form (resource in `apiKey`):  
  - Header: `Authorization: Bearer <RESOURCE_NAME>:<FOUNDRY_API_KEY>`  
  - Body: `"model": "claude-sonnet-4-5"`
- Alternative (resource in `model`):  
  - Header: `Authorization: Bearer <FOUNDRY_API_KEY>`  
  - Body: `"model": "<RESOURCE_NAME>/claude-sonnet-4-5"`

You may still use environment variables for:

- `PROXY_DEBUG=1` to enable debug logging.  
- `DEV_DEFAULT_LOGICAL_API_KEY` for local development when your client cannot set `Authorization`.  
- `HOST` / `PORT` if you run via `python foundry_openai_proxy.py`.

### Run

```shell
uvicorn foundry_openai_proxy:app --host 127.0.0.1 --port 18000
```

Or with debug logging:

```shell
PROXY_DEBUG=1 uvicorn foundry_openai_proxy:app --host 127.0.0.1 --port 18000
# or
python foundry_openai_proxy.py --proxy-debug
```

Local endpoint:

```text
http://127.0.0.1:18000/v1
```

### Optional admin interface (`/admin`)

- Disabled by default. Enable via `ENABLE_ADMIN=1` (or `ADMIN_ENABLED=1`) **and** a credential:
  - Preferred: `ADMIN_PASSWORD_HASH` (bcrypt hash).
  - Dev-only fallback: `ADMIN_PASSWORD` (plaintext).
  - Optional: `ADMIN_USERNAME` (default `admin`).
- Generate a bcrypt hash:

```shell
python3 - <<'PY'
import bcrypt
print(bcrypt.hashpw(b"change-me", bcrypt.gensalt()).decode())
PY
```

- Other admin toggles:
  - `ENABLE_ADMIN_RESET=1` (or `ADMIN_ALLOW_RESET=1`) to allow `/admin/metrics/reset`.
  - `ENABLE_ADMIN_CONFIG_EDIT=1` (or `ADMIN_ALLOW_CONFIG_EDIT=1`) to allow `/admin/config` POST.
  - `ENABLE_ADMIN_USER_MGMT=1` (or `ADMIN_ALLOW_USER_MGMT=1`) to allow `/admin/users` CRUD.
- Persistence:
  - Metrics: set `METRICS_FILE` (or `PROXY_METRICS_FILE`) to persist metrics between runs (versioned JSON, atomic writes). Example: `METRICS_FILE=./data/metrics.json`.
  - Admin config (safe fields only): set `ADMIN_CONFIG_FILE` (or `PROXY_CONFIG_FILE`). Example: `ADMIN_CONFIG_FILE=./data/admin_config.json`.
  - Proxy auth tokens: set `PROXY_AUTH_FILE` (or `PROXY_USER_FILE`) to store hashed tokens. Example: `PROXY_AUTH_FILE=./data/proxy_tokens.json`.
  - Paths can be relative to the working directory or absolute; directories are created if needed. Do not commit these files to git.
- Admin endpoints (all Basic-auth protected):
  - `/admin/health`, `/admin/overview`, `/admin/dashboard` (HTML), `/admin/metrics`, `/admin/metrics/reset`
  - `/admin/config` GET/POST (if enabled)
  - `/admin/users` GET/POST and `/admin/users/{user}` DELETE (if enabled)
- Security tips: bind to localhost or front with a firewall/reverse proxy; prefer `ADMIN_PASSWORD_HASH`; do not commit metric/config/token files to git.

### Optional proxy auth tokens (protect `/v1/*`)

- Enable enforcement: `ENABLE_PROXY_AUTH=1` (or `PROXY_REQUIRE_AUTH=1`).
- Provide token store: `PROXY_AUTH_FILE` (or `PROXY_USER_FILE`) to persist hashed tokens.
- Add/delete tokens via admin `/admin/users` endpoints (if `ENABLE_ADMIN_USER_MGMT` is enabled). Tokens are stored as bcrypt hashes and never returned once stored.
- Client usage:
  - Header: `X-Proxy-Token: <token>`
  - Or prefix the model: `"model": "<token>:claude-sonnet-4-5"` (proxy strips the token and forwards the clean model).
- Per-request user tracking in metrics uses the validated proxy user ID when present.

## How it works

- Proxy converts OpenAI messages into Anthropic format:
  - All `system` messages → concatenated into the top‑level `system` string.
  - `user`/`assistant` messages → `{"role": ..., "content": [{"type":"text","text": "..."}]}`.
- It calls:

  ```python
  from anthropic import AnthropicFoundry
  client = AnthropicFoundry(
      api_key=FOUNDRY_API_KEY,
      base_url=f"https://{FOUNDRY_RESOURCE}.services.ai.azure.com/anthropic/"
  )
  client.messages.create(
      model=CLAUDE_MODEL,
      system=...,
      messages=...,
      max_tokens=...,
      # temperature only if provided
  )
  ```

The proxy calls the Anthropic endpoint:

```text
https://<FOUNDRY_RESOURCE>.services.ai.azure.com/anthropic/v1/messages
```

via the `AnthropicFoundry` SDK.

- For non‑stream requests, it calls `client.messages.create(...)` and maps the result into an OpenAI‑style `chat.completion` JSON.
- For `stream:true`, it currently performs a single non‑stream upstream call and re‑streams the full assistant message as:
  - One `chat.completion.chunk` with `delta.content` (or `delta.tool_calls` when tools are used).
  - A final `chat.completion.chunk` with `finish_reason` (`"stop"` or `"tool_calls"`), followed by `data: [DONE]`.

### Quick tests

Start the proxy:

```shell
uvicorn foundry_openai_proxy:app --host 127.0.0.1 --port 18000
```

Non‑stream chat:

```shell
curl -s http://127.0.0.1:18000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer myresource:foundry-key-123" \
  -d '{
        "model": "claude-sonnet-4-5",
        "messages": [{"role": "user", "content": "Say OK"}]
      }'
```

Streaming chat:

```shell
curl -N http://127.0.0.1:18000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer myresource:foundry-key-123" \
  -d '{
        "model": "claude-sonnet-4-5",
        "stream": true,
        "messages": [{"role": "user", "content": "Say OK"}]
      }'
```

Expected:

```text
data: {"object":"chat.completion.chunk", ...}
data: {"object":"chat.completion.chunk", "finish_reason":"stop"}
data: [DONE]
```

Embeddings (if your Foundry resource exposes an embeddings deployment):

```shell
curl -s http://127.0.0.1:18000/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer myresource:foundry-key-123" \
  -d '{
        "model": "text-embedding-3-large",
        "input": "embedding me"
      }'
```

Legacy completions:

```shell
curl -s http://127.0.0.1:18000/v1/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer myresource:foundry-key-123" \
  -d '{
        "model": "claude-sonnet-4-5",
        "prompt": "Say OK"
      }'
```

---

## API Surface

- `GET /v1/models`  
  Returns a single configured model:
  ```json
  {
    "data": [
      { "id": "claude-sonnet-4-5", "object": "model", "owned_by": "azure_foundry" }
    ],
    "object": "list"
  }
  ```

- `POST /v1/embeddings`  
  - OpenAI-compatible embeddings request (`model`, `input`, optional `user`).  
  - Uses the same per-request `apiKey` + `model` decoding to reach the Foundry embeddings deployment (`/openai/deployments/{model}/embeddings`).  
  - Returns `object: "list"` with `data` items, `embedding` vectors, and `usage`.  
  - If the resource/model does not expose embeddings, returns an explicit `not_supported_error`.

- `POST /v1/moderations`  
  - Not supported by default; returns an OpenAI-style `not_supported_error` explaining that Azure AI Foundry does not expose a compatible moderation endpoint.

- `POST /v1/chat/completions`  
  - Standard OpenAI chat format (`model`, `messages`, `stream`, `max_tokens`, `temperature`).
  - Tool bridge:
    - `<read_file><path>...</path></read_file>`
    - `<write_file><path>...</path><content>...</content></write_file>`
    - `<search><query>...</query></search>`
    - `<tool_call>{"name":"read_file","arguments":{"path":"/path"}}</tool_call>`
    - Anthropic‑style `[{ "type": "tool_use", "name": "read_file", "input": {...} }]`
  - Normalizes `read_file` arguments to `{"uri": "<path>"}` for file tools that expect a URI‑style parameter.
  - Emits OpenAI‑compatible `tool_calls` and SSE `chat.completion.chunk` events.

- `POST /v1/completions`  
  - Basic support for the legacy text completions endpoint.
  - Maps `prompt` (string or array of strings) into a single user message and forwards to Anthropic.
  - Returns an OpenAI‑style `text_completion` object with `choices[0].text`, `finish_reason`, and `usage`.

---

## Per-client Foundry configuration via apiKey + model

The proxy derives the upstream Foundry `resource`, `model`, and `api_key` from the logical `apiKey` and `model` that OpenAI-compatible clients already expose. There is no central Foundry config; the client must encode everything needed into these two fields.

### Logical `apiKey` formats

- **Plain key mode**  
  - `apiKey` is just the Foundry API key.  
  - The Foundry resource must then be encoded in the `model` (see below) so the proxy can route correctly.

- **Structured mode**  
  - `apiKey = "<foundry_resource>:<foundry_api_key>"`  
  - Example: `myresource:foundry-key-123`  
  - The proxy splits this into:
    - `foundry_resource = "myresource"`
    - `foundry_api_key = "foundry-key-123"`

### Logical `model` behavior

- **Plain model**  
  - `model` is treated as the Foundry model/deployment name, e.g. `"claude-sonnet-4-5"`.

- **Structured model**  
  - `model = "<foundry_resource>/<foundry_model>"`  
  - Example: `"myresource/claude-sonnet-4-5"`  
  - The proxy decodes this as:
    - `foundry_resource_override = "myresource"`
    - `foundry_model = "claude-sonnet-4-5"`

### Precedence and validation

For each request, the proxy uses:

- API key:
  - From structured `apiKey` (`resource:key`) if present.  
  - Else from plain `apiKey` (treated as the Foundry key).
- Resource:
  - From structured `apiKey` if present.  
  - Else from structured `model` (`resource/model`) if present.
- Model:
  - From structured `model` if present.  
  - Else from the raw `model` field.

If the proxy cannot derive a complete configuration (missing resource/key/model), it returns an OpenAI-style error payload explaining what is missing.

For local development where your client cannot set headers, you can define `DEV_DEFAULT_LOGICAL_API_KEY` so that the proxy has a logical `apiKey` even when `Authorization` is absent.

### VS Code Copilot `customOAIModels` examples

Example config with resource encoded in `model` and a plain Foundry key:

```json
"github.copilot.chat.customOAIModels": [
  {
    "id": "foundry-claude",
    "model": "myresource/claude-sonnet-4-5",
    "apiKey": "FOUNDry-KEY-123",
    "baseUrl": "http://127.0.0.1:18000/v1"
  }
]
```

Example structured `apiKey` per client (resource + key encoded together):

```json
"github.copilot.chat.customOAIModels": [
  {
    "id": "foundry-tenant-a",
    "model": "claude-sonnet-4-5",
    "apiKey": "myresource-a:foundry-key-a",
    "baseUrl": "http://127.0.0.1:18000/v1"
  }
]
```

Example structured `model` (resource + model encoded in the model field):

```json
"github.copilot.chat.customOAIModels": [
  {
    "id": "foundry-tenant-b",
    "model": "myresource-b/claude-sonnet-4-5",
    "apiKey": "foundry-key-b",
    "baseUrl": "http://127.0.0.1:18000/v1"
  }
]
```

In all cases Copilot only needs `baseUrl`, `apiKey`, and `model`; the proxy handles mapping to Foundry.

### Continue extension `config.yaml` examples

Example `models` block for Continue’s OpenAI-compatible provider:

```yaml
models:
  - title: "Foundry (plain key + resource in model)"
    provider: "openai"
    model: "myresource/claude-sonnet-4-5"
    apiKey: "FOUNDry-KEY-123"
    baseUrl: "http://127.0.0.1:18000/v1"

  - title: "Foundry (structured apiKey)"
    provider: "openai"
    model: "claude-sonnet-4-5"
    apiKey: "myresource-a:foundry-key-a"
    baseUrl: "http://127.0.0.1:18000/v1"

  - title: "Foundry (structured model)"
    provider: "openai"
    model: "myresource-b/claude-sonnet-4-5"
    apiKey: "foundry-key-b"
    baseUrl: "http://127.0.0.1:18000/v1"
```

Each logical Continue model (`title`) uses only `baseUrl`, `apiKey`, and `model`, and the proxy routes to the appropriate Foundry resource/model based on the encoding rules above.

---

## Troubleshooting

- **401/403/404 from Foundry**  
  - Check that the Foundry resource name you encode (either as the left side of `apiKey = "resource:key"` or as the `resource/` prefix in `model`) matches the resource name from the Azure portal endpoint URL.  
  - Ensure the API key is valid for that resource and has access to the Anthropic/Claude deployment you are calling.
- **Proxy auth errors (`proxy auth required` / `token invalid`)**  
  - Ensure `ENABLE_PROXY_AUTH`/`PROXY_REQUIRE_AUTH` is set only when you intend to require tokens.  
  - Add tokens via `/admin/users` (with user management enabled) and pass them with `X-Proxy-Token` or `token:model` prefix.

- **Anthropic errors**  
  - Look for `foundry_response` in debug output.  
  - Errors like “Unexpected role 'system'” or “temperature: Input should be a valid number” indicate payload issues; the proxy splits `system` correctly and omits `temperature` when unset.

---

## Quick Reference

- Base URL: `http://127.0.0.1:18000/v1`
- Models: `GET /v1/models`
- Chat: `POST /v1/chat/completions` (stream or non‑stream)
- Legacy text: `POST /v1/completions`
- Auth: API key via Anthropic endpoint on Azure AI Foundry
- Debug: set `PROXY_DEBUG=1` or pass `--proxy-debug`
