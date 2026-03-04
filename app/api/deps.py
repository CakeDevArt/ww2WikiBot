from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_api_key, get_user_id
from app.db.session import get_session


async def auth_deps(
    api_key: str = Depends(verify_api_key),
    user_id: str = Depends(get_user_id),
) -> str:
    return user_id


async def get_retriever(request: Request):
    return request.app.state.retriever


async def get_db(session: AsyncSession = Depends(get_session)):
    return session
