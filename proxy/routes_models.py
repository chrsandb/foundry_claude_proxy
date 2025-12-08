from fastapi import APIRouter
from fastapi.responses import JSONResponse


router = APIRouter()


@router.get("/v1/models")
async def list_models():
    # In per-client mode, the actual model is determined by the client's
    # `model` field and Foundry configuration encoded in apiKey/model.
    # This endpoint returns a generic placeholder.
    return JSONResponse(
        {
            "data": [
                {
                    "id": "model-from-client-config",
                    "object": "model",
                    "owned_by": "azure_foundry",
                }
            ],
            "object": "list",
        }
    )

