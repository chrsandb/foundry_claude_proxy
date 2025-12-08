import os
import json
import sys


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
