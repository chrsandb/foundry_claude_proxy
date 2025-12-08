#!/bin/sh
source .venv/bin/activate
uvicorn foundry_openai_proxy:app --host 127.0.0.1 --port 1234
