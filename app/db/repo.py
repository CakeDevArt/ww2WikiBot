from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DialogMessage


async def save_dialog(session: AsyncSession, user_id: str, question: str, answer: str) -> DialogMessage:
    msg = DialogMessage(user_id=user_id, question=question, answer=answer)
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg
