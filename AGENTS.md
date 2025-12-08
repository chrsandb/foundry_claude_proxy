# Agent Guide

- **Purpose**: Local FastAPI proxy that exposes an OpenAI‑compatible API at `http://127.0.0.1:18000/v1` and forwards requests to Azure AI Foundry Anthropic (messages) API using an API key.
- **Key file**: `foundry_openai_proxy.py` (only source file).
- **Endpoints**: `GET /v1/models` returns a single configured model; `POST /v1/chat/completions` supports streaming SSE and non-streaming JSON; bridges simple tag-based tool markers → OpenAI `tool_calls` (streams tool_calls as OpenAI-style deltas with index/id/arguments).
- **Auth**: Requires `FOUNDRY_API_KEY` and uses the Anthropic endpoint (`https://<resource>.services.ai.azure.com/anthropic/v1/messages`) via the AnthropicFoundry SDK and `api-key` (no AAD/Azure CLI path). Streaming requests are served from a non-stream call and re-streamed.

## Configuration
- Preferred: add `.env` with `FOUNDRY_RESOURCE`, `PROJECT_NAME`, `CLAUDE_MODEL`, `API_VERSION`, `FOUNDRY_API_KEY` (env vars override `.env`; API key preferred when set). Tools are only prompted when the client provides a `tools`/`functions` list.
- Foundry URL is built from those constants.
- Uses `requests` for upstream calls; `fastapi`/`uvicorn` for serving.
- Debug logging: set env `PROXY_DEBUG=1` or pass `--proxy-debug` in the process args (silent by default).

## Running
- Install deps: `pip install fastapi uvicorn requests`.
- Start: `uvicorn foundry_openai_proxy:app --host 127.0.0.1 --port 18000`.

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
- Non-stream: `curl -s http://127.0.0.1:18000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"claude-sonnet-4-5","messages":[{"role":"user","content":"Say OK"}]}'`.
- Stream: same body with `"stream": true`; expect SSE chunks ending with `data: [DONE]`.

## Suggestions (if asked to extend)
- Add environment variable config and validation.
- Implement token caching / retry for Azure calls.
- True incremental streaming instead of single chunk.
- Broaden tool tag parsing and allow streaming tool responses.
- Add logging/metrics and optional Dockerfile/service definitions.
