import calendar
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.goal import Goal


class GoalService:
    @staticmethod
    async def create(
        user_id: uuid.UUID,
        target_amount: Decimal,
        db: AsyncSession,
    ) -> Goal:
        """Deactivate any existing active goal and create a new one for the current month."""
        now = datetime.now(timezone.utc)
        last_day = calendar.monthrange(now.year, now.month)[1]
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = now.replace(
            day=last_day, hour=23, minute=59, second=59, microsecond=999999
        )

        # Deactivate existing active goals
        existing = await GoalService._get_active_row(user_id, db)
        if existing:
            existing.is_active = False
            db.add(existing)

        goal = Goal(
            user_id=user_id,
            target_amount=target_amount,
            period_start=period_start,
            period_end=period_end,
            is_active=True,
        )
        db.add(goal)
        await db.commit()
        await db.refresh(goal)
        return goal

    @staticmethod
    async def get_active(user_id: uuid.UUID, db: AsyncSession) -> Goal | None:
        return await GoalService._get_active_row(user_id, db)

    @staticmethod
    async def calculate_progress(user_id: uuid.UUID, db: AsyncSession) -> dict:
        """Return {target, saved, remaining, pct, on_track, period_end} or {} if no goal."""
        goal = await GoalService._get_active_row(user_id, db)
        if not goal:
            return {}

        from app.services.report_service import ReportService

        now = datetime.now(timezone.utc)
        monthly = await ReportService.get_monthly_report(
            user_id, goal.period_start.year, goal.period_start.month, db
        )

        saved = monthly["balance"]  # income - expense this month
        target = Decimal(str(goal.target_amount))
        remaining = max(Decimal("0"), target - saved)
        pct = min(100, int(saved / target * 100)) if target > 0 else 0

        days_total = (goal.period_end.date() - goal.period_start.date()).days or 1
        days_elapsed = (now.date() - goal.period_start.date()).days
        expected_pct = min(100, int(days_elapsed / days_total * 100))
        on_track = pct >= expected_pct

        return {
            "target": target,
            "saved": saved,
            "remaining": remaining,
            "pct": pct,
            "on_track": on_track,
            "period_end": goal.period_end,
        }

    @staticmethod
    async def deactivate(user_id: uuid.UUID, db: AsyncSession) -> bool:
        goal = await GoalService._get_active_row(user_id, db)
        if not goal:
            return False
        goal.is_active = False
        db.add(goal)
        await db.commit()
        return True

    @staticmethod
    async def _get_active_row(user_id: uuid.UUID, db: AsyncSession) -> Goal | None:
        result = await db.execute(
            select(Goal)
            .where(Goal.user_id == user_id, Goal.is_active.is_(True))
            .order_by(Goal.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
