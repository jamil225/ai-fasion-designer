from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from src.config import Settings, get_settings

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(API_KEY_HEADER),
    settings: Settings = Depends(get_settings),
) -> str:
    if not api_key or api_key != settings.app_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key
