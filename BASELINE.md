# Proxy Baseline – Post-Refactor (OpenAI-Compatible Foundry Proxy)

This baseline captures the current architecture and behavior after refactoring into a modular package.

## 1. Architecture overview

1.1 Entry point  
- `foundry_openai_proxy.py` is the main FastAPI entrypoint.  
- It creates the app and includes routers from:
  - `proxy/routes_models.py`
  - `proxy/routes_chat.py`
  - `proxy/routes_completions.py`

1.2 Internal package structure  
- `proxy/__init__.py` – package marker.  
- `proxy/config.py` – debug logging helpers.  
- `proxy/encoding.py` – per-request Foundry settings derivation from `apiKey` + `model`.  
- `proxy/foundry_client.py` – AnthropicFoundry wrapper and usage mapping.  
- `proxy/models.py` – message shaping (`to_anthropic_payload`) and `error_response`.  
- `proxy/tools.py` – tool bridge (`extract_tool_calls_from_text`).  
- `proxy/routes_models.py` – `/v1/models` route.  
- `proxy/routes_chat.py` – `/v1/chat/completions` route.  
- `proxy/routes_completions.py` – `/v1/completions` route.  
- `proxy/webui/` – placeholder for future `/admin` WebUI (not wired into the app).

## 2. Configuration and logging

2.1 Config model  
- The proxy does not maintain any central Foundry configuration.  
- Upstream Foundry `resource`, `model`, and `api_key` are derived per request from:
  - Logical `apiKey` (bearer token).  
  - Logical `model` (request body).

2.2 Debug logging  
- `DEBUG` flag in `proxy/config.py`:
  - Enabled via `--proxy-debug` CLI arg or `PROXY_DEBUG=1`.  
- `dlog(label, data)` pretty-prints JSON (or `str(data)`) with a `[proxy-debug]` prefix when enabled.  
- Routes and client code log:
  - `foundry_payload` and `foundry_response` (truncated/structured).  
  - `incoming_request_chat` / `incoming_request_completions`.  
  - `assistant_text_raw` / `assistant_text_raw_empty`.  
  - `tool_calls_extracted` from the tool bridge.

2.3 Planned extension points  
- Future headers or URL query params could provide additional debugging or routing hints, but the primary interface remains `baseUrl` + `apiKey` + `model`.

## 3. Foundry / Anthropic client

3.1 Wrapper class  
- `FoundryAnthropicClient` in `proxy/foundry_client.py`:
  - Wraps `AnthropicFoundry` SDK.  
  - Requires explicit per-request `api_key`, `resource`, and `model`, typically supplied by `proxy.encoding.derive_foundry_settings`.

3.2 Request method  
- `create_messages(system, messages, max_tokens, temperature)`:
  - Calls `client.messages.create(model, system, messages, max_tokens, stream=False, temperature?)`.  
  - Logs payload and response via `dlog`.  
  - Converts SDK response to a plain `dict` using `_to_dict`:
    - Prefers `model_dump()` / `model_dump_json()` when present.  
    - Falls back to `__dict__` as needed.

3.3 Usage mapping  
- `map_usage(foundry_json)`:
  - Reads `usage` from the response and produces:
    - `prompt_tokens` (from `input_tokens` or `prompt_tokens`).  
    - `completion_tokens` (from `output_tokens` or `completion_tokens`).  
    - `total_tokens` (from `total_tokens` or computed sum).

## 4. Message shaping and error responses

4.1 Anthropic payload shaping  
- `to_anthropic_payload(messages)` in `proxy/models.py`:
  - Aggregates all `system` messages into a single `system` string (newline-separated).  
  - Maps `user`/`assistant` messages into:
    - `{"role": <role>, "content": [{"type": "text", "text": "<content>"}]}`.

4.2 Error responses  
- `error_response(text)` in `proxy/models.py`:
  - Returns an OpenAI-style `chat.completion` error payload with:
    - `object: "chat.completion"`.  
    - Single `choices[0].message` containing the error text.  
    - `finish_reason: "stop"`.  
    - All usage fields set to zero.

## 5. Tool bridge behavior

5.1 Implementation  
- `extract_tool_calls_from_text(text, tools)` in `proxy/tools.py`:
  - Recognized patterns:
    - `<read_file><path>...</path></read_file>`  
    - `<tool_call>{"name":"...", "arguments": {...}}</tool_call>`  
    - Anthropic-style list literal:
      - `[{"type": "tool_use", "id": "...", "name": "read_file", "input": {...}}, ...]`

5.2 Normalization and output  
- Builds `tool_calls` list where each entry is:
  - `{"id": "call_<name>_N", "type": "function", "function": {"name": "<name>", "arguments": "<JSON string>"}}`.  
- Normalizes `read_file` arguments so that:
  - Input `{"path": "..."} or {"uri": "..."}` → stored as `{"uri": "<path>"}` inside the JSON string.  
- Returns `(tool_calls, remaining_text)` with tags stripped from the text.  
- Logs `tool_calls_extracted` via `dlog`.

5.3 Streaming vs non-stream  
- `proxy/routes_chat.py` uses the same tool bridge for:
  - Streaming: first SSE chunk carries `delta.tool_calls` with `index`, `id`, `type`, `function{name, arguments}` and `finish_reason: null`.  
  - Non-stream: `choices[0].message.tool_calls` plus `finish_reason: "tool_calls"` when tool calls are present.

## 6. Routes and OpenAI compatibility

6.1 `/v1/models` (`proxy/routes_models.py`)  
- Returns:
  - `{"data": [{"id": "model-from-client-config", "object": "model", "owned_by": "azure_foundry"}], "object": "list"}`.  
- This is a generic placeholder; the actual model used is determined per request by the client's `model` field and Foundry configuration encoded in `apiKey`/`model`.

6.2 `/v1/chat/completions` (`proxy/routes_chat.py`)  
- Accepts standard OpenAI chat payload:
  - `model`, `messages`, `stream`, `max_tokens`, `temperature`, `tools`/`functions`.  
- Behavior:
  - Uses Anthropic `messages` API via `FoundryAnthropicClient`.  
  - Non-stream:
    - Builds an OpenAI-style `chat.completion` with a single choice and optional `tool_calls`.  
  - Stream:
    - Re-streams the full assistant response as:
      - One `chat.completion.chunk` with `delta.content` or `delta.tool_calls`.  
      - A final `chat.completion.chunk` with `finish_reason: "stop"` or `"tool_calls"`, plus `usage`.  
      - Ends with `data: [DONE]`.  
- Logging:
  - `incoming_request_chat`, `assistant_text_raw`/`assistant_text_raw_empty`, `tool_calls_extracted`.

6.3 `/v1/completions` (`proxy/routes_completions.py`)  
- Accepts legacy completions payload:
  - `prompt` (string or list of strings), `max_tokens`, `temperature`.  
- Maps `prompt` into a single `user` message and uses the same Anthropic client.  
- Returns:
  - OpenAI-style `text_completion` object (`choices[0].text`, `finish_reason: "stop"`, `usage`).

## 7. WebUI and Docker extension points

7.1 WebUI placeholders  
- `proxy/webui/`:
  - `__init__.py` – notes for future `/admin` WebUI.  
  - `routes.py` – defines `router = APIRouter(prefix="/admin")` with TODOs for auth and stats.  
- Not included in the main FastAPI app yet; current API surface remains purely OpenAI-compatible.

7.2 Docker friendliness  
- Entry point remains `foundry_openai_proxy:app`, which is suitable for a future Dockerfile command like:
  - `uvicorn foundry_openai_proxy:app --host 0.0.0.0 --port 18000`.  
- Container deployments primarily configure:
  - `PROXY_DEBUG`, `HOST`, `PORT`, and optionally `DEV_DEFAULT_LOGICAL_API_KEY`.  
- Foundry credentials and routing are provided by clients via `apiKey` + `model`, not by container env.

## 8. Verification status

8.1 Syntax checks  
- `python3 -m py_compile foundry_openai_proxy.py proxy/*.py proxy/webui/*.py` passes with no errors.

8.2 Manual tests (to be run by user)  
- `TEST_RECIPES.md` documents:
  - Non-stream and stream `/v1/chat/completions`.  
  - `/v1/completions` text completions.  
  - Tool call patterns and expected shapes.  
  - Config and error handling checks.  
- Behavior is expected to match the pre-refactor proxy since only internal structure was changed.
