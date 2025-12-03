# Azure Foundry → LM Studio Local API Proxy
Use Claude Sonnet 4.5 (or any Azure Foundry model) inside Void, LM Studio, OpenAI SDKs, or any OpenAI‑compatible client.

- Local endpoint: `http://127.0.0.1:1234/v1`
- Auth paths: Azure CLI (Responses API) or API key (Anthropic endpoint)
- Upstream: Azure AI Foundry Responses API (AAD) or Anthropic endpoint (api-key)

## Features
- OpenAI-compatible: `/v1/models`, `/v1/chat/completions`
- Streaming + non-stream chat completions (LM Studio SSE)
- Streaming tool calls (`tool_calls` deltas) with `read_file` bridge
- Works with Void (LM Studio provider), LM Studio-style clients, OpenAI SDKs, curl
- Auth paths: Azure CLI (Responses API, default) or Anthropic endpoint with API key

## External Dependencies
- Python 3.9+ with `pip`
- Python packages: `fastapi`, `uvicorn`, `requests`, `anthropic` (installed via `pip install -r requirements.txt`)
- Azure CLI (`az`) **only if you use AAD auth** (`az account get-access-token --scope https://ai.azure.com/.default`)

### Install Azure CLI (AAD path only)
- macOS: `brew update && brew install azure-cli`
- Linux (Ubuntu/Debian): `curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash`
- Windows: MSI https://aka.ms/installazurecliwindows or `winget install -e --id Microsoft.AzureCLI`

## Contents
- `lmstudio_claude_proxy_az.py` — main proxy server
- `README.md` — this file

## Install
1) Create a directory and copy the script
```shell
mkdir azure-lmstudio-proxy
cd azure-lmstudio-proxy
# copy lmstudio_claude_proxy_az.py into this folder
```
2) Create virtual environment
```shell
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
```
3) Install dependencies
```shell
pip install -r requirements.txt
```
4) Configure via `.env` (or environment variables)
```
FOUNDRY_RESOURCE=myresource
PROJECT_NAME=myproject
CLAUDE_MODEL=claude-sonnet-4-5
# Optional
API_VERSION=2025-11-15-preview
# Optional (use Anthropic endpoint with API key instead of AAD)
FOUNDRY_API_KEY=<your-foundry-api-key>
```
5) Auth choice
- AAD (default, no `FOUNDRY_API_KEY`):  
  ```shell
  az login
  az account set --subscription "<YOUR-SUBSCRIPTION-ID>"   # if needed
  ```
  Ensure `az account get-access-token --scope https://ai.azure.com/.default` succeeds.
- API key: set `FOUNDRY_API_KEY` and skip Azure CLI.
   - Endpoint used: `https://<FOUNDRY_RESOURCE>.services.ai.azure.com/anthropic/v1/messages`
   - No AAD fallback when `FOUNDRY_API_KEY` is set.

## Run
```shell
uvicorn lmstudio_claude_proxy_az:app --host 127.0.0.1 --port 1234
```
Debug (optional):
```shell
PROXY_DEBUG=1 uvicorn lmstudio_claude_proxy_az:app --host 127.0.0.1 --port 1234
# or
python lmstudio_claude_proxy_az.py --proxy-debug
```

## Test Quickly
Non-stream:
```shell
curl -s http://127.0.0.1:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
        "model": "claude-sonnet-4-5",
        "messages": [{"role": "user", "content": "Say OK"}]
      }'
```
Expected:
```json
{
  "choices": [
    { "message": { "role": "assistant", "content": "OK" } }
  ]
}
```

Streaming (SSE):
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
```
data: {"object":"chat.completion.chunk", ...}
data: {"object":"chat.completion.chunk", "finish_reason":"stop"}
data: [DONE]
```

## Void (LM Studio Provider)
1) Settings → Providers → LM Studio  
2) Host: `127.0.0.1`, Port: `1234`  
3) Refresh Models → select `claude-sonnet-4-5`  
4) Void calls `GET /v1/models` and streaming `POST /v1/chat/completions`; streaming `tool_calls` (read_file) are supported.

## API Endpoints
- `GET /v1/models` — returns one configured model
- `POST /v1/chat/completions`
  - Standard OpenAI chat format
  - Optional: `stream`, `max_tokens`, `temperature`
  - Tool bridge: `<read_file>` tags, `<tool_call>{...}</tool_call>`, and Anthropic-style `[{type:'tool_use',...}]` normalized to OpenAI `tool_calls` (`{"uri": "<path>"}` for read_file)
  - Auth:
    - AAD path: `Authorization: Bearer <az token>` (Responses API)
    - API key path: `api-key` (Anthropic endpoint) — no AAD fallback when set

## How It Works
- Client sends OpenAI-style chat to `localhost:1234`.
- If no API key: proxy builds a prompt, gets a bearer via Azure CLI, and POSTs to Foundry Responses API.
- If API key set: proxy converts messages to Anthropic format and calls `https://<resource>.services.ai.azure.com/anthropic/v1/messages`.
- Maps upstream output to OpenAI chat completions:
  - Streaming: SSE chunks (with tool_call deltas when present)
  - Non-stream: single JSON
- Tool bridge emits OpenAI `tool_calls` compatible with Void’s LM Studio provider.

## Troubleshooting
- “Response from model was empty”  
  - Confirm LM Studio provider, host/port, and run the streaming curl test.
- Unauthorized / invalid token  
  - `az login`, `az account show`, ensure correct subscription/tenant.
- Foundry 401/403/404  
  - Check resource name, project name, and Foundry permissions.

## Optional Enhancements
- Dockerfile deployment
- Token caching / retries
- Multi-model routing
- Logging + metrics
- Windows/macOS/systemd service scaffolding
- Combined OpenAI + LM Studio + Ollama endpoints

## Quick Reference
- Base URL: `http://127.0.0.1:1234/v1`
- Models: `GET /v1/models`
- Chat: `POST /v1/chat/completions` (stream or non-stream)
- Tool calls: OpenAI `tool_calls` streaming supported
- Debug: `PROXY_DEBUG=1` or `--proxy-debug`
