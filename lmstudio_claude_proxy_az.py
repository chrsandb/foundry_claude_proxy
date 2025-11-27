import os
import subprocess
import json
import time
import re
import sys
import ast
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
import requests

# ---------- Config helpers ----------
def load_env_file(path: str = ".env") -> dict:
    """Load simple KEY=VALUE lines from a .env file (no interpolation)."""
    env_path = Path(path)
    if not env_path.is_file():
        return {}

    env: dict[str, str] = {}
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


_ENV_FILE = load_env_file()

def _env(key: str, default: str) -> str:
    # Environment variables override .env, otherwise fall back to defaults.
    return os.environ.get(key, _ENV_FILE.get(key, default))

# Debug flag: default off. Enable via CLI arg "--proxy-debug" or env PROXY_DEBUG=1.
DEBUG = "--proxy-debug" in sys.argv or os.environ.get("PROXY_DEBUG") == "1"

def dlog(label: str, data):
    if not DEBUG:
        return
    try:
        printable = data if isinstance(data, str) else json.dumps(data, indent=2, ensure_ascii=False)
    except Exception:
        printable = str(data)
    print(f"[proxy-debug] {label}: {printable}")


# === CONFIG: EDIT THESE ===
FOUNDRY_RESOURCE = _env("FOUNDRY_RESOURCE", "your-foundry-resource")          # your resource name
PROJECT_NAME     = _env("PROJECT_NAME", "your-foundry-project")               # your Foundry project
CLAUDE_MODEL     = _env("CLAUDE_MODEL", "claude-sonnet-4-5")                  # model or router name
API_VERSION      = _env("API_VERSION", "2025-11-15-preview")

FOUNDRY_URL = (
    f"https://{FOUNDRY_RESOURCE}.services.ai.azure.com/"
    f"api/projects/{PROJECT_NAME}/openai/responses"
    f"?api-version={API_VERSION}"
)

app = FastAPI()


# ---------- Auth via az CLI ----------
def get_token_via_az() -> str:
    result = subprocess.run(
        [
            "az",
            "account",
            "get-access-token",
            "--scope",
            "https://ai.azure.com/.default",
            "--query",
            "accessToken",
            "-o",
            "tsv",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("Empty token from az CLI")
    return token


# ---------- Helper functions ----------
def messages_to_prompt(messages, tools=None):
    parts = []
    if tools:
        tool_names = [t.get("function", {}).get("name") for t in tools if t.get("type") == "function"]
        tool_names = [n for n in tool_names if n]
        if tool_names:
            parts.append(
                "SYSTEM: If tools are needed, respond ONLY with <tool_call>{\"name\":\"tool_name\",\"arguments\":{...}}</tool_call> "
                "blocks (no extra prose). Supported tools: "
                + ", ".join(tool_names)
                + ". Use read_file by providing an absolute file URI/path under the user's workspace."
            )
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        parts.append(f"{role.upper()}: {content}")
    parts.append("ASSISTANT:")
    return "\n".join(parts)


def call_foundry(prompt, max_tokens=None, temperature=None):
    payload = {"model": CLAUDE_MODEL, "input": prompt}

    if max_tokens is not None:
        payload["max_output_tokens"] = max_tokens
    if temperature is not None:
        payload["temperature"] = temperature

    token = get_token_via_az()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    dlog("foundry_payload", payload)
    resp = requests.post(FOUNDRY_URL, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()
    dlog("foundry_response", {"model": data.get("model"), "id": data.get("id"), "usage": data.get("usage")})
    return data


def extract_text(foundry_json: dict) -> str:
    try:
        for item in foundry_json.get("output", []):
            if item.get("type") == "message":
                for c in item.get("content", []):
                    if c.get("type") in ("output_text", "text"):
                        if c.get("text"):
                            return c["text"]
    except Exception:
        pass
    return ""


def map_usage(foundry_json: dict) -> dict:
    usage = foundry_json.get("usage", {})
    prompt = usage.get("input_tokens", usage.get("prompt_tokens", 0))
    comp   = usage.get("output_tokens", usage.get("completion_tokens", 0))
    total  = usage.get("total_tokens", prompt + comp)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": comp,
        "total_tokens": total,
    }


def error_response(text: str):
    return {
        "id": "error",
        "object": "chat.completion",
        "model": CLAUDE_MODEL,
        "created": int(time.time()),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def extract_tool_calls_from_text(text: str, tools: list) -> tuple[list, str]:
    """
    Bridge: parse Void-style tags like
      <read_file> <path>...</path> </read_file>
    and convert them into OpenAI-style tool_calls.

    Currently supports: read_file
    Returns (tool_calls, remaining_text).
    """
    tool_calls: list[dict] = []
    remaining = text

    # Build a set of tool names actually available
    available = set()
    for t in tools:
        if t.get("type") == "function":
            fn = t.get("function") or {}
            name = fn.get("name")
            if name:
                available.add(name)

    def normalize_args(name: str, arguments: dict) -> dict:
        # Void expects read_file -> {"uri": "<path>"} (string), not {"path": ...}
        if name == "read_file":
            path_val = arguments.get("path") or arguments.get("uri")
            if path_val:
                return {"uri": path_val}
        return arguments

    def add_call(name: str, arguments: dict):
        call_id = f"call_{name}_{len(tool_calls)+1}"
        norm_args = normalize_args(name, arguments)
        tool_calls.append(
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(norm_args)},
            }
        )

    # --- read_file ---
    if "read_file" in available:
        pattern = re.compile(
            r"<read_file>\s*<path>(.*?)</path>\s*</read_file>",
            re.DOTALL | re.IGNORECASE,
        )
        matches = list(pattern.finditer(remaining))
        if matches:
            for m in matches:
                path = m.group(1).strip()
                if not path:
                    continue
                add_call("read_file", {"path": path})
            # Remove all read_file tags from remaining text
            remaining = pattern.sub("", remaining)
        # Drop any stray open/close tags that slipped through
        remaining = re.sub(r"</?read_file>", "", remaining, flags=re.IGNORECASE)

    # --- generic <tool_call> JSON blocks ---
    # e.g., <tool_call>{"name": "read_file", "arguments": {"path": "/tmp/a"}}</tool_call>
    block_pattern = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL | re.IGNORECASE)
    block_matches = list(block_pattern.finditer(remaining))
    for m in block_matches:
        payload_raw = m.group(1).strip()
        try:
            payload_json = json.loads(payload_raw)
        except Exception:
            continue
        name = payload_json.get("name")
        args = payload_json.get("arguments", {})
        if name in available and isinstance(args, dict):
            add_call(name, args)
    if block_matches:
        remaining = block_pattern.sub("", remaining)

    # --- Anthropic-style JSON array fallback ---
    # e.g., [{'type': 'tool_use', 'id': 'call', 'name': 'read_file', 'input': {'uri': '...'}}]
    if not tool_calls and "tool_use" in remaining and remaining.strip().startswith("["):
        try:
            payload_list = ast.literal_eval(remaining.strip())
            if isinstance(payload_list, list):
                for item in payload_list:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") != "tool_use":
                        continue
                    name = item.get("name")
                    args = item.get("input") or {}
                    if name in available and isinstance(args, dict):
                        add_call(name, args)
                if tool_calls:
                    remaining = ""
        except Exception:
            pass

    # (You can add write_file / edit_file parsing here later if needed.)

    dlog("tool_calls_extracted", {"found": tool_calls, "remaining": remaining.strip()})
    return tool_calls, remaining.strip()


# ---------- LM Studio–compatible endpoints ----------
@app.get("/v1/models")
async def list_models():
    return JSONResponse(
        {
            "data": [
                {
                    "id": CLAUDE_MODEL,
                    "object": "model",
                    "owned_by": "azure_foundry",
                }
            ],
            "object": "list",
        }
    )


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(error_response(f"Invalid JSON: {e}"))

    messages = body.get("messages", [])
    if not messages:
        return JSONResponse(error_response("No 'messages' field provided"))

    stream = bool(body.get("stream", False))
    # Support both "tools" and legacy "functions" lists; fall back to a single read_file tool so tags can still be bridged.
    tools = body.get("tools") or body.get("functions") or []
    fallback_tools = [{"type": "function", "function": {"name": "read_file"}}]
    tool_defs = tools if tools else fallback_tools
    has_tools = bool(tool_defs)

    prompt = messages_to_prompt(messages, tools=tool_defs)
    dlog("incoming_request", {"stream": stream, "has_tools": has_tools, "tools_keys": [t.get('function', {}).get('name') for t in tool_defs], "prompt": prompt})

    max_tokens = body.get("max_tokens")
    temperature = body.get("temperature")

    try:
        foundry_json = call_foundry(prompt, max_tokens=max_tokens, temperature=temperature)
    except Exception as e:
        return JSONResponse(error_response(str(e)))

    assistant_text = extract_text(foundry_json)
    dlog("assistant_text_raw", assistant_text)
    usage_info = map_usage(foundry_json)

    model_name = foundry_json.get("model", CLAUDE_MODEL)
    created = int(foundry_json.get("created_at", time.time()))
    resp_id = foundry_json.get("id", "resp_local")

    # ---------- TOOL BRIDGE (shared for stream / non-stream) ----------
    tool_calls = []
    remaining_text = assistant_text
    if has_tools:
        tool_calls, remaining_text = extract_tool_calls_from_text(assistant_text, tool_defs)

    # ---------- STREAMING (for LM Studio / Void chat) ----------
    if stream:
        async def event_gen():
            first_delta = {"role": "assistant"}
            if tool_calls:
                # OpenAI streaming tool deltas expect index, id, function{name, arguments}
                delta_tool_calls = []
                for idx, tc in enumerate(tool_calls):
                    delta_tool_calls.append(
                        {
                            "index": idx,
                            "id": tc.get("id", f"call_{idx+1}"),
                            "type": "function",
                            "function": {
                                "name": tc.get("function", {}).get("name"),
                                "arguments": tc.get("function", {}).get("arguments", ""),
                            },
                        }
                    )
                first_delta["tool_calls"] = delta_tool_calls
            else:
                first_delta["content"] = assistant_text

            chunk = {
                "id": resp_id,
                "object": "chat.completion.chunk",
                "model": model_name,
                "created": created,
                "choices": [
                    {
                        "index": 0,
                        "delta": first_delta,
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk)}\n\n"

            done = {
                "id": resp_id,
                "object": "chat.completion.chunk",
                "model": model_name,
                "created": created,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "tool_calls" if tool_calls else "stop",
                    }
                ],
            }
            yield f"data: {json.dumps(done)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    # ---------- NON-STREAMING ----------
    # If tools are present, try to bridge Void-style tags -> tool_calls
    if has_tools and tool_calls:
        return JSONResponse(
            {
                "id": resp_id,
                "object": "chat.completion",
                "model": model_name,
                "created": created,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": remaining_text,
                            "tool_calls": tool_calls,
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": usage_info,
            }
        )

    # Fallback: plain assistant message (no tool calls)
    return JSONResponse(
        {
            "id": resp_id,
            "object": "chat.completion",
            "model": model_name,
            "created": created,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": assistant_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": usage_info,
        }
    )


if __name__ == "__main__":
    # Convenience for local runs: python lmstudio_claude_proxy_az.py --proxy-debug
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "1234"))
    uvicorn.run("lmstudio_claude_proxy_az:app", host=host, port=port, reload=False)
