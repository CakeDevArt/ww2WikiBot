from fastapi import Header, HTTPException

from app.core.config import settings


async def verify_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> str:
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


async def get_user_id(
    x_user_id: str = Header(..., alias="X-User-Id"),
) -> str:
    return x_user_id
