from typing import List, Dict, Any, Optional
import time


def to_anthropic_payload(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Split system vs user/assistant and shape to Anthropic format."""
    system_parts: list[str] = []
    chat_msgs: list[dict] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            if isinstance(content, str):
                system_parts.append(content)
            else:
                system_parts.append(str(content))
            continue
        text = content if isinstance(content, str) else str(content)
        chat_msgs.append({"role": role, "content": [{"type": "text", "text": text}]})

    # AnthropicFoundry messages API expects `system` to be a list.
    system_blocks: list[dict] = []
    if system_parts:
        system_blocks.append({"type": "text", "text": "\n".join(system_parts)})

    return {"system": system_blocks, "messages": chat_msgs}


def error_response(text: str, model: Optional[str] = None) -> Dict[str, Any]:
    model_id = model or "unknown-model"
    return {
        "id": "error",
        "object": "chat.completion",
        "model": model_id,
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
