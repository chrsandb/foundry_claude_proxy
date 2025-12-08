#!/bin/sh
source .venv/bin/activate
uvicorn lmstudio_claude_proxy_az:app --host 127.0.0.1 --port 1234
