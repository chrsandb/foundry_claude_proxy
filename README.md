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
  - `fastapi`, `uvicorn`, `requests`, `anthropic`

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

- `POST /v1/chat/completions`  
  - Standard OpenAI chat format (`model`, `messages`, `stream`, `max_tokens`, `temperature`).
  - Tool bridge:
    - `<read_file><path>...</path></read_file>`
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
