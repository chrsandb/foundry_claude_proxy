# Azure Foundry → LM Studio Local API Proxy

Use Claude Sonnet 4.5 (or any Azure AI Foundry model) inside Void, LM Studio, OpenAI SDKs, or any OpenAI‑compatible client, via a local OpenAI-style API:

- Local endpoint: `http://127.0.0.1:1234/v1`
- Implemented routes: `GET /v1/models`, `POST /v1/chat/completions`
- Features: streaming + non‑stream chat, basic tool_calls bridge (`read_file`), Void/LM Studio compatibility

This proxy supports **two auth modes**:

- **Mode A – Azure AD (Responses API, default)**  
  Uses Azure CLI (`az`) to obtain a bearer token and calls the Azure AI Foundry **Responses API**.
- **Mode B – API key (Anthropic endpoint)**  
  Uses an API key and the Anthropic‑compatible endpoint for Claude hosted in Azure AI Foundry.

You choose the mode by whether `FOUNDRY_API_KEY` is set:

- If `FOUNDRY_API_KEY` is **unset** → Mode A (AAD / Responses API).
- If `FOUNDRY_API_KEY` is **set** → Mode B (API key / Anthropic endpoint), no AAD fallback.

If you’re unsure which to use:

- Use **AAD / Responses API** if you already use `az login` and want the “standard” Azure AI Foundry OpenAI‑style Responses endpoint.
- Use **API key / Anthropic** if your organization prefers key‑based auth and you have a Foundry API key for Claude.

---

## Common Setup (Both Modes)

### Requirements

- Python 3.9+ with `pip`
- Packages (installed via `requirements.txt`):
  - `fastapi`, `uvicorn`, `requests`, `anthropic`

### Install

Clone the repo and create a virtualenv:

```shell
git clone https://github.com/chrsandb/foundry_claude_proxy.git
cd foundry_claude_proxy

python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### Base Configuration

Create `.env` (or use environment variables):

```text
FOUNDRY_RESOURCE=myresource          # Azure AI Foundry resource name
PROJECT_NAME=myproject               # Foundry project (used in Responses API mode)
CLAUDE_MODEL=claude-sonnet-4-5       # Model or deployment name
API_VERSION=2025-11-15-preview       # Responses API version (AAD mode only)

# Optional (switch to API key mode)
# FOUNDRY_API_KEY=<your-foundry-api-key>
```

These apply to both modes; which upstream path is used depends on whether `FOUNDRY_API_KEY` is set.

### Run

```shell
uvicorn lmstudio_claude_proxy_az:app --host 127.0.0.1 --port 1234
```

Or with debug logging:

```shell
PROXY_DEBUG=1 uvicorn lmstudio_claude_proxy_az:app --host 127.0.0.1 --port 1234
# or
python lmstudio_claude_proxy_az.py --proxy-debug
```

Local endpoint in both modes:

```text
http://127.0.0.1:1234/v1
```

---

## Mode A – Azure AD / Responses API (Default)

**Use this when**:

- You are comfortable with `az login` and AAD.
- You want to call the Azure AI Foundry **Responses API**.

### Extra Dependencies

- Azure CLI (`az`)

Install (if needed):

- macOS: `brew update && brew install azure-cli`
- Linux (Ubuntu/Debian): `curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash`
- Windows: MSI https://aka.ms/installazurecliwindows or `winget install -e --id Microsoft.AzureCLI`

### Auth Setup

Make sure you’re logged in and on the correct subscription:

```shell
az login
az account set --subscription "<YOUR-SUBSCRIPTION-ID>"   # if needed
az account get-access-token --scope https://ai.azure.com/.default
```

The proxy uses:

- `az account get-access-token --scope https://ai.azure.com/.default`

to obtain a bearer token on each call.

### How Mode A Works

- Proxy takes your OpenAI‑style request (`/v1/chat/completions`).
- It converts messages into a prompt string and POSTs to:

  ```text
  https://<FOUNDRY_RESOURCE>.services.ai.azure.com/
    api/projects/<PROJECT_NAME>/openai/responses?api-version=<API_VERSION>
  ```

- It authenticates with `Authorization: Bearer <token>` from the Azure CLI.
- It maps the Responses API output into OpenAI chat completion JSON and (for `stream:true`) LM‑Studio/Void‑style SSE chunks.
- Tool bridge:
  - Parses `<read_file><path>...</path></read_file>` / `<tool_call>{...}</tool_call>` / Anthropic‑style `[{type:'tool_use',...}]`.
  - Normalizes `read_file` arguments to `{"uri": "<path>"}`.
  - Emits OpenAI `tool_calls` compatible with Void’s LM Studio provider.

### Quick Tests (AAD Mode)

Non‑stream:

```shell
curl -s http://127.0.0.1:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
        "model": "claude-sonnet-4-5",
        "messages": [{"role": "user", "content": "Say OK"}]
      }'
```

Streaming:

```shell
curl -N http://127.0.0.1:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
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

---

## Mode B – API Key / Anthropic Endpoint

**Use this when**:

- You have an Azure AI Foundry API key for Claude.
- You want to avoid Azure CLI / AAD for this proxy.

### Extra Config

In `.env`:

```text
FOUNDRY_RESOURCE=myresource
CLAUDE_MODEL=claude-sonnet-4-5
FOUNDRY_API_KEY=<your-foundry-api-key>
```

Notes:

- `PROJECT_NAME` and `API_VERSION` are ignored in this mode.
- The proxy calls the Anthropic endpoint:

  ```text
  https://<FOUNDRY_RESOURCE>.services.ai.azure.com/anthropic/v1/messages
  ```

via the `AnthropicFoundry` SDK.

### How Mode B Works

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

- For `stream:true`, it uses `client.messages.stream(...)` and transforms Anthropic stream events (`message_start`, `content_block_delta` with `text_delta`) into LM‑Studio/Void SSE chunks:
  - Each `text_delta` becomes a `chat.completion.chunk` with `delta.content`.
  - A final chunk includes `finish_reason:"stop"` and usage, followed by `[DONE]`.
- The response is mapped back to an OpenAI‑style chat completion JSON/SSE stream, so Void/LM Studio don’t need to know it came from Anthropic.

### Quick Tests (API‑Key Mode)

Non‑stream:

```shell
FOUNDRY_API_KEY=... uvicorn lmstudio_claude_proxy_az:app --host 127.0.0.1 --port 1234

curl -s http://127.0.0.1:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
        "model": "claude-sonnet-4-5",
        "messages": [{"role": "user", "content": "Say OK"}]
      }'
```

Streaming:

```shell
curl -N http://127.0.0.1:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
        "model": "claude-sonnet-4-5",
        "stream": true,
        "messages": [{"role": "user", "content": "Say OK"}]
      }'
```

Expected: SSE chunks with assistant text followed by `[DONE]`.

---

## Void / LM Studio Integration (Both Modes)

1. In Void, go to **Settings → Providers → LM Studio**.  
2. Set **Host**: `127.0.0.1`, **Port**: `1234`.  
3. Click **Refresh Models**, then choose `claude-sonnet-4-5`.  
4. Void will:
   - `GET /v1/models`
   - `POST /v1/chat/completions` with `stream:true`
   - Consume `tool_calls` and SSE chunks produced by this proxy.

Mode A vs B only changes how the proxy talks to Azure; Void always sees the same OpenAI‑style API.

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
  - Normalizes `read_file` arguments to `{"uri": "<path>"}` for Void’s built‑in tools.
  - Auth:
    - Mode A: `Authorization: Bearer <az token>` (Responses API).
    - Mode B: `api-key: <FOUNDRY_API_KEY>` (Anthropic endpoint).

---

## Troubleshooting

- **“Response from model was empty” (in Void)**  
  - Ensure you’re using the LM Studio provider with host/port set to `127.0.0.1:1234`.  
  - Run the streaming `curl` test to confirm SSE works.  
  - Enable debug: `PROXY_DEBUG=1` and check for `assistant_text_raw` logs.

- **Invalid or missing AAD token (Mode A)**  
  - Run:
    ```shell
    az login
    az account show
    az account get-access-token --scope https://ai.azure.com/.default
    ```
  - Ensure the correct subscription and tenant are selected and your user has access to the Foundry resource.

- **401/403/404 from Foundry**  
  - Check `FOUNDRY_RESOURCE`, `PROJECT_NAME`, `CLAUDE_MODEL`, and your Foundry permissions.  
  - For API‑key mode, ensure the key is valid and associated with the correct Foundry resource.

- **Anthropic BadRequest errors (Mode B)**  
  - Look for `anthropic_stream_error` / `foundry_response` in debug output.  
  - Errors like “Unexpected role 'system'” or “temperature: Input should be a valid number” indicate payload issues; the proxy already splits `system` correctly and omits `temperature` when unset.

---

## Quick Reference

- Base URL: `http://127.0.0.1:1234/v1`
- Models: `GET /v1/models`
- Chat: `POST /v1/chat/completions` (stream or non‑stream)
- Auth:
  - AAD (default): Azure CLI → Responses API
  - API key: Anthropic endpoint via `AnthropicFoundry`
- Debug: set `PROXY_DEBUG=1` or pass `--proxy-debug`
