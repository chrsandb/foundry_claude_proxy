from fastapi import FastAPI

from proxy.routes_models import router as models_router
from proxy.routes_chat import router as chat_router
from proxy.routes_completions import router as completions_router


app = FastAPI()
app.include_router(models_router)
app.include_router(chat_router)
app.include_router(completions_router)


if __name__ == "__main__":
    # Convenience for local runs: python foundry_openai_proxy.py --proxy-debug
    import uvicorn
    import os

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "18000"))
    uvicorn.run("foundry_openai_proxy:app", host=host, port=port, reload=False)
