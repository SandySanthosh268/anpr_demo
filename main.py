"""Entry point for running the ANPR API server."""
import uvicorn

from api_service.main import app
from config import get_settings

settings = get_settings()

if __name__ == "__main__":
    uvicorn.run(
        "api_service.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
