# Void LM Studio Integration – Findings

Source reviewed: https://github.com/voideditor/void (Feb 2025 snapshot), key files below.

- **Provider routing** (`src/vs/workbench/contrib/void/electron-main/llmMessage/sendLLMMessage.impl.ts`)
  - `lmStudio` provider uses `_sendOpenAICompatibleChat`, `_sendOpenAICompatibleFIM`, `_openaiCompatibleList`.
  - Client always calls OpenAI SDK with `stream: true`.
  - LM Studio endpoint is expected to be OpenAI-compatible at `<endpoint>/v1`.

- **Tool expectations (OpenAI-compatible path)**
  - In `_sendOpenAICompatibleChat`, streaming response is iterated chunk-by-chunk.
  - It builds `toolName`, `toolParamsStr`, `toolId` from `chunk.choices[0]?.delta?.tool_calls`.
    - It concatenates `tool.function.name`, `tool.function.arguments`, `tool.id` across deltas.
    - It ignores tool_calls with `index !== 0`; include `index: 0`.
  - On completion, it errors with “Void: Response from model was empty” iff **all** are empty: `fullTextSoFar`, `fullReasoningSoFar`, `toolName`.
  - `rawToolCallObjOfParamsStr` JSON-parses the **concatenated arguments string** to produce `rawParams`; the string must be JSON (not already parsed).
  - `finish_reason` is not read during streaming; only final concatenated values matter.

- **Implications for your proxy**
  - Keep **streaming** when tools are present; returning a non-stream JSON breaks the streaming parser.
  - Stream at least one chunk with `choices[0].delta.tool_calls = [{ index: 0, id, type: 'function', function: { name, arguments: "<JSON string>" } }]`.
  - You may optionally stream another chunk with `finish_reason: "tool_calls"`; not strictly required for Void’s parser but is OpenAI-consistent.
  - Ensure `tool.function.arguments` is a stringified JSON object (e.g., `"{"path": "/abs/path"}"`), not an object.
  - Text is optional; the presence of a tool_call (non-empty `toolName`) avoids the “empty response” error.

- **Model listing**
  - LM Studio uses the same `_openaiCompatibleList` (OpenAI SDK, `models.list`).

- **Settings/UI references**
  - Provider definitions in `src/vs/workbench/contrib/void/common/modelCapabilities.ts` and `voidSettingsTypes.ts` set `specialToolFormat: 'openai-style'` for OpenAI-compatible providers, including LM Studio.
  - Onboarding marks LM Studio as a “local” provider and asks for an endpoint URL.

- **Where to adjust if needed (Void side)**
  - Tool stream parsing lives in `_sendOpenAICompatibleChat` (~lines 290–360 in the repo).
  - If extending tool support, adjust `openAITools` and `availableTools` in `prompts.js` / `modelCapabilities` / `voidSettingsTypes`.

Summary: Void expects standard OpenAI streaming tool_call deltas. Provide `delta.tool_calls` with `index: 0`, `id`, and string JSON `arguments`; don’t fall back to non-streaming when `stream: true`. Tool calls without text are fine as long as `tool_calls` are present.***
