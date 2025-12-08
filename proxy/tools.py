import ast
import json
import re
from typing import Tuple, List, Dict, Any

from .config import dlog


def extract_tool_calls_from_text(text: str, tools: list) -> Tuple[List[Dict[str, Any]], str]:
    """
    Bridge: parse simple tool markers (tags and Anthropic-style tool_use arrays)
    and convert them into OpenAI-style tool_calls.

    Supported patterns:
      - <read_file><path>...</path></read_file>
      - <tool_call>{"name": "...", "arguments": {...}}</tool_call>
      - Anthropic-style list:
        [{'type': 'tool_use', 'id': '...', 'name': '...', 'input': {...}}, ...]

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
        # Normalize read_file arguments to {"uri": "<path>"} (string), not {"path": ...}
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

    dlog("tool_calls_extracted", {"found": tool_calls, "remaining": remaining.strip()})
    return tool_calls, remaining.strip()


