# Agent Guide

- **Purpose**: Local FastAPI proxy that exposes an LM Studio–compatible OpenAI API at `http://127.0.0.1:1234/v1` and forwards requests to Azure AI Foundry Responses API using Azure CLI auth.
- **Key file**: `lmstudio_claude_proxy_az.py` (only source file).
- **Endpoints**: `GET /v1/models` returns a single configured model; `POST /v1/chat/completions` supports streaming SSE and non-streaming JSON; bridges simple Void-style tool tags → OpenAI `tool_calls` (streams tool_calls as OpenAI-style deltas with index/id/arguments).
- **Auth**: Obtains bearer via `az account get-access-token --scope https://ai.azure.com/.default`; no key storage. Fails if `az` login/subscription not set.

## Configuration
- Preferred: add `.env` with `FOUNDRY_RESOURCE`, `PROJECT_NAME`, `CLAUDE_MODEL`, `API_VERSION` (env vars override `.env`).
- Foundry URL is built from those constants.
- Uses `requests` for upstream calls; `fastapi`/`uvicorn` for serving.
- Debug logging: set env `PROXY_DEBUG=1` or pass `--proxy-debug` in the process args (silent by default).

## Running
- Install deps: `pip install fastapi uvicorn requests`.
- Start: `uvicorn lmstudio_claude_proxy_az:app --host 127.0.0.1 --port 1234`.
- Requires `az login` beforehand (and `az account set` if multiple subscriptions).

## Request Flow
- Incoming OpenAI-style messages → concatenated prompt (`ROLE: content\n...ASSISTANT:`).
- Payload sent to Foundry: `{model, input, max_output_tokens?, temperature?}`.
- Response parsing:
  - `extract_text` pulls the first message/text content from `output`.
  - `map_usage` maps Foundry `usage` → OpenAI usage fields.
  - Streaming: emits single `chat.completion.chunk` with full text, then a finish chunk, then `[DONE]` (LM Studio/Void style).
  - Non-stream: returns full completion; if `tools` passed, parses `<read_file><path>...</path></read_file>` tags or `<tool_call>{...}</tool_call>` into `tool_calls` (keeps assistant text alongside). Normalizes `read_file` arguments to `{"uri": "<path>"}`.
  - Fallback: also parses Anthropic-style `[{type:'tool_use', name, input:{...}}]` arrays into tool_calls.
  - Stream: sends a first chunk with `delta.tool_calls` (including index/id/name/arguments) and a finish chunk with `finish_reason: tool_calls`; otherwise streams text with stop.

## Caveats / Risks
- Single-shot streaming chunk (no token-level streaming).
- Limited tool bridging: only `read_file` implemented; single-chunk streaming (no token-level tool deltas).
- Prompt is naive concatenation; no safety/role handling.
- No retries, logging, or token caching; upstream errors surfaced as a faux chat message.
- Hard-coded config; changing models requires editing the file.

## Quick Tests
- Non-stream: `curl -s http://127.0.0.1:1234/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"claude-sonnet-4-5","messages":[{"role":"user","content":"Say OK"}]}'`.
- Stream: same body with `"stream": true`; expect SSE chunks ending with `data: [DONE]`.

## Suggestions (if asked to extend)
- Add environment variable config and validation.
- Implement token caching / retry for Azure calls.
- True incremental streaming instead of single chunk.
- Broaden tool tag parsing and allow streaming tool responses.
- Add logging/metrics and optional Dockerfile/service definitions.
