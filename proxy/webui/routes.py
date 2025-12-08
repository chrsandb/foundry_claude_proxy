from fastapi import APIRouter

# Reserved router for a future password-protected WebUI at /admin.
# Not included in the main app yet; adding it later must preserve
# OpenAI API compatibility for existing clients.

router = APIRouter(prefix="/admin")

# TODO: Add authenticated WebUI endpoints for configuration and usage stats.

