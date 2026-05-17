import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.conversation_state import ConversationState

_TTL = timedelta(minutes=5)
_TTL_NAME = timedelta(minutes=30)


class StateManager:
    @staticmethod
    async def get(user_id: uuid.UUID, db: AsyncSession) -> ConversationState | None:
        result = await db.execute(
            select(ConversationState).where(
                ConversationState.user_id == user_id,
                ConversationState.expires_at > datetime.now(timezone.utc),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def set(
        user_id: uuid.UUID,
        intent: str,
        data: dict[str, Any],
        db: AsyncSession,
        ttl: timedelta | None = None,
    ) -> ConversationState:
        await db.execute(
            delete(ConversationState).where(ConversationState.user_id == user_id)
        )
        state = ConversationState(
            user_id=user_id,
            current_intent=intent,
            pending_data=data,
            expires_at=datetime.now(timezone.utc) + (ttl if ttl is not None else _TTL),
        )
        db.add(state)
        await db.flush()
        return state

    @staticmethod
    async def clear(user_id: uuid.UUID, db: AsyncSession) -> None:
        await db.execute(
            delete(ConversationState).where(ConversationState.user_id == user_id)
        )
