# Manual Test Recipes

This file captures manual test scenarios for the Azure Foundry Claude Proxy (OpenAI‑compatible).

## 1. Basic chat completions

### 1.1 Non‑stream chat

- Start the proxy:
  ```shell
  uvicorn foundry_openai_proxy:app --host 127.0.0.1 --port 18000
  ```
- Send a non‑streaming request:
  ```shell
  curl -s http://127.0.0.1:18000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer myresource:foundry-key-123" \
    -d '{
          "model": "claude-sonnet-4-5",
          "messages": [{"role": "user", "content": "Say OK"}]
        }'
  ```
- Verify:
  - HTTP 200.
  - Response `object` is `chat.completion`.
  - `choices[0].message.role` is `assistant`.
  - `choices[0].message.content` contains `OK`.

### 1.2 Streaming chat

-- With the proxy running, send:
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
- Verify:
  - Stream emits at least one `data: { ... }` line where `object` is `chat.completion.chunk` and `choices[0].delta.content` contains `OK`.
  - A final chunk has `finish_reason: "stop"`.
  - The stream ends with `data: [DONE]`.

## 2. Legacy text completions

### 2.1 /v1/completions

- Send:
  ```shell
  curl -s http://127.0.0.1:18000/v1/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer myresource:foundry-key-123" \
    -d '{
          "model": "claude-sonnet-4-5",
          "prompt": "Say OK"
        }'
  ```
- Verify:
  - HTTP 200.
  - Response `object` is `text_completion`.
  - `choices[0].text` contains `OK`.
  - `usage` includes `prompt_tokens`, `completion_tokens`, `total_tokens`.

## 3. Tool calls

Assume the client declares a `read_file` tool in `tools` or `functions`.

### 3.1 Tag‑based read_file

- Send a non‑streaming chat request where the upstream model is expected to emit:
  ```text
  <read_file><path>/abs/path/to/file.txt</path></read_file>
  ```
- Verify in the proxy response:
  - `choices[0].message.tool_calls` is a non‑empty array.
  - First entry:
    - `type` is `function`.
    - `function.name` is `read_file`.
    - `function.arguments` is a JSON string that parses to `{"uri": "/abs/path/to/file.txt"}`.
  - `finish_reason` is `"tool_calls"`.

### 3.2 <tool_call> JSON block

- Have the model emit something like:
  ```text
  <tool_call>{"name":"read_file","arguments":{"path":"/abs/path/to/file.txt"}}</tool_call>
  ```
- Verify:
  - Same conditions as 3.1 for `tool_calls` and normalized arguments.

### 3.3 Anthropic tool_use list

- Have the model emit an Anthropic‑style Python list literal in the assistant text:
  ```text
  [ {"type": "tool_use", "id": "call_1", "name": "read_file", "input": {"uri": "/abs/path/to/file.txt"} } ]
  ```
- Verify:
  - Proxy parses the list into `tool_calls` and clears the assistant text for that message.
  - `finish_reason` is `"tool_calls"`.

### 3.4 write_file tag

- Have the model emit:
  ```text
  <write_file><path>/abs/path/to/file.txt</path><content>Hello</content></write_file>
  ```
- Verify:
  - `tool_calls[0].function.name` is `write_file`.
  - Arguments JSON parses to `{"uri": "/abs/path/to/file.txt", "contents": "Hello"}`.

### 3.5 search tag

- Have the model emit:
  ```text
  <search><query>important terms</query></search>
  ```
- Verify:
  - `tool_calls[0].function.name` is `search`.
  - Arguments JSON parses to `{"query": "important terms"}`.

## 4. Error handling and config

### 4.1 Missing / invalid per-request config

- Start the proxy without any Foundry-related env (none are needed).  
- Send a chat request without an `Authorization` header or without a `model` field.
- Verify:
  - Proxy returns HTTP 200 with `object: "chat.completion"` containing an error message from `error_response(...)` in `choices[0].message.content`.
  - The error text clearly indicates which parts of the Foundry configuration are missing (API key, resource, or model).

### 4.2 Upstream errors

- Use a syntactically valid but incorrect Foundry key in `Authorization: Bearer resource:bad-key` and send a chat request.
- Verify:
  - Proxy returns HTTP 200 with `object: "chat.completion"` containing an error message from `error_response(...)` in `choices[0].message.content`.
  - When `PROXY_DEBUG=1`, logs show `foundry_response` with details from Anthropic.

## 5. Embeddings

### 5.1 Successful embeddings (if deployment exists)

- Start the proxy and send:
  ```shell
  curl -s http://127.0.0.1:18000/v1/embeddings \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer myresource:foundry-key-123" \
    -d '{
          "model": "text-embedding-3-large",
          "input": "embedding me"
        }'
  ```
- Verify:
  - HTTP 200.
  - Response `object` is `list`.
  - `data[0].object` is `embedding` and has a non-empty `embedding` array.
  - `usage` includes `prompt_tokens` and `total_tokens`.

### 5.2 Embeddings not supported

- Point to a resource/model that does not have an embeddings deployment.
- Verify:
  - HTTP 400.
  - Response `error.type` is `not_supported_error` and message explains embeddings are unavailable for the resource/model.

## 6. Moderations

### 6.1 Moderations unsupported

- Send:
  ```shell
  curl -s http://127.0.0.1:18000/v1/moderations \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer myresource:foundry-key-123" \
    -d '{
          "model": "text-moderation-latest",
          "input": "test content"
        }'
  ```
- Verify:
  - HTTP 400.
  - Response has `error.type` of `not_supported_error` and message explains moderations are not supported by this proxy/Foundry.
