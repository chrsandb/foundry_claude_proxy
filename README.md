# Azure Foundry Claude Proxy (OpenAI-Compatible)

Use Claude Sonnet 4.5 (or any Azure AI Foundry model) from OpenAI SDKs and other OpenAI‑compatible clients via a local OpenAI‑style API:

- Local endpoint: `http://127.0.0.1:1234/v1`
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
CLAUDE_MODEL=claude-sonnet-4-5       # Model or deployment name
FOUNDRY_API_KEY=<your-foundry-api-key>
```

All of these must be set via environment variables or `.env`. On startup, the proxy validates configuration and fails fast if required values are missing.

### Run

```shell
uvicorn foundry_openai_proxy:app --host 127.0.0.1 --port 1234
```

Or with debug logging:

```shell
PROXY_DEBUG=1 uvicorn foundry_openai_proxy:app --host 127.0.0.1 --port 1234
# or
python foundry_openai_proxy.py --proxy-debug
```

Local endpoint:

```text
http://127.0.0.1:1234/v1
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
FOUNDRY_API_KEY=... uvicorn foundry_openai_proxy:app --host 127.0.0.1 --port 1234
```

Non‑stream chat:

```shell
curl -s http://127.0.0.1:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
        "model": "claude-sonnet-4-5",
        "messages": [{"role": "user", "content": "Say OK"}]
      }'
```

Streaming chat:

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

Legacy completions:

```shell
curl -s http://127.0.0.1:1234/v1/completions \
  -H "Content-Type: application/json" \
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

## Troubleshooting

- **401/403/404 from Foundry**  
  - Check `FOUNDRY_RESOURCE`, `CLAUDE_MODEL`, and your Foundry permissions.  
  - Ensure the API key is valid and associated with the correct Foundry resource.

- **Anthropic errors**  
  - Look for `foundry_response` in debug output.  
  - Errors like “Unexpected role 'system'” or “temperature: Input should be a valid number” indicate payload issues; the proxy splits `system` correctly and omits `temperature` when unset.

---

## Quick Reference

- Base URL: `http://127.0.0.1:1234/v1`
- Models: `GET /v1/models`
- Chat: `POST /v1/chat/completions` (stream or non‑stream)
- Legacy text: `POST /v1/completions`
- Auth: API key via Anthropic endpoint on Azure AI Foundry
- Debug: set `PROXY_DEBUG=1` or pass `--proxy-debug`
