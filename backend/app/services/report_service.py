import calendar
import csv
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.cache.redis_client import cache_get, cache_set
from app.infrastructure.database.models.transaction import Transaction, TransactionType


class ReportService:
    @staticmethod
    async def get_balance(user_id: uuid.UUID, db: AsyncSession) -> dict:
        cache_key = f"report:balance:{user_id}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        result = await db.execute(
            select(Transaction).where(Transaction.user_id == user_id)
        )
        transactions = list(result.scalars().all())

        total_income = sum(
            (t.amount for t in transactions if t.type == TransactionType.INCOME),
            Decimal("0.00"),
        )
        total_expense = sum(
            (t.amount for t in transactions if t.type == TransactionType.EXPENSE),
            Decimal("0.00"),
        )

        data = {
            "total_income": total_income,
            "total_expense": total_expense,
            "balance": total_income - total_expense,
            "last_updated": datetime.now(timezone.utc),
        }
        await cache_set(cache_key, data)
        return data

    @staticmethod
    async def get_monthly_report(
        user_id: uuid.UUID, year: int, month: int, db: AsyncSession
    ) -> dict:
        cache_key = f"report:monthly:{user_id}:{year}:{month:02d}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        last_day = calendar.monthrange(year, month)[1]
        date_from = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
        date_to = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

        result = await db.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .where(Transaction.date >= date_from)
            .where(Transaction.date <= date_to)
        )
        transactions = list(result.scalars().all())

        total_income = sum(
            (t.amount for t in transactions if t.type == TransactionType.INCOME),
            Decimal("0.00"),
        )
        total_expense = sum(
            (t.amount for t in transactions if t.type == TransactionType.EXPENSE),
            Decimal("0.00"),
        )

        categories: dict[str, dict] = {}
        for t in transactions:
            if t.type != TransactionType.EXPENSE:
                continue
            cat = t.category
            if cat not in categories:
                categories[cat] = {
                    "category": cat,
                    "total": Decimal("0.00"),
                    "count": 0,
                }
            categories[cat]["total"] += t.amount
            categories[cat]["count"] += 1

        by_category = []
        for cat_data in sorted(
            categories.values(), key=lambda x: x["total"], reverse=True
        ):
            pct = (
                float(cat_data["total"] / total_expense * 100)
                if total_expense > 0
                else 0.0
            )
            by_category.append(
                {
                    "category": cat_data["category"],
                    "total": cat_data["total"],
                    "count": cat_data["count"],
                    "percentage": round(pct, 1),
                }
            )

        data = {
            "period": f"{year}-{month:02d}",
            "total_income": total_income,
            "total_expense": total_expense,
            "balance": total_income - total_expense,
            "by_category": by_category,
        }
        await cache_set(cache_key, data)
        return data

    @staticmethod
    async def get_by_category(
        user_id: uuid.UUID,
        db: AsyncSession,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        query = select(Transaction).where(Transaction.user_id == user_id)
        if date_from:
            query = query.where(Transaction.date >= date_from)
        if date_to:
            query = query.where(Transaction.date <= date_to)

        result = await db.execute(query)
        transactions = list(result.scalars().all())

        categories: dict[str, dict] = {}
        for t in transactions:
            cat = t.category
            if cat not in categories:
                categories[cat] = {
                    "category": cat,
                    "total": Decimal("0.00"),
                    "count": 0,
                }
            categories[cat]["total"] += t.amount
            categories[cat]["count"] += 1

        grand_total = sum((c["total"] for c in categories.values()), Decimal("0.00"))

        items = []
        for cat_data in sorted(
            categories.values(), key=lambda x: x["total"], reverse=True
        ):
            pct = (
                float(cat_data["total"] / grand_total * 100) if grand_total > 0 else 0.0
            )
            items.append(
                {
                    "category": cat_data["category"],
                    "total": cat_data["total"],
                    "count": cat_data["count"],
                    "percentage": round(pct, 1),
                }
            )

        return items

    @staticmethod
    async def get_summary(user_id: uuid.UUID, db: AsyncSession) -> dict:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        all_result = await db.execute(
            select(Transaction).where(Transaction.user_id == user_id)
        )
        all_transactions = list(all_result.scalars().all())

        month_transactions = [t for t in all_transactions if t.date >= month_start]

        total_income = sum(
            (t.amount for t in all_transactions if t.type == TransactionType.INCOME),
            Decimal("0.00"),
        )
        total_expense = sum(
            (t.amount for t in all_transactions if t.type == TransactionType.EXPENSE),
            Decimal("0.00"),
        )

        month_expenses = [
            t for t in month_transactions if t.type == TransactionType.EXPENSE
        ]
        month_incomes = [
            t for t in month_transactions if t.type == TransactionType.INCOME
        ]

        largest_expense = max((t.amount for t in month_expenses), default=None)
        largest_income = max((t.amount for t in month_incomes), default=None)

        month_total_expense = sum((t.amount for t in month_expenses), Decimal("0.00"))
        daily_avg = round(month_total_expense / max(now.day, 1), 2)

        recent = sorted(all_transactions, key=lambda t: t.date, reverse=True)[:5]

        return {
            "recent_transactions": [
                {
                    "id": str(t.id),
                    "type": t.type.value,
                    "amount": t.amount,
                    "category": t.category,
                    "description": t.description,
                    "date": t.date.isoformat(),
                }
                for t in recent
            ],
            "largest_expense_this_month": largest_expense,
            "largest_income_this_month": largest_income,
            "daily_average_expense": daily_avg,
            "total_income": total_income,
            "total_expense": total_expense,
            "balance": total_income - total_expense,
        }

    @staticmethod
    async def export_csv(
        user_id: uuid.UUID,
        db: AsyncSession,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> str:
        query = (
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.date.asc())
        )
        if date_from:
            query = query.where(Transaction.date >= date_from)
        if date_to:
            query = query.where(Transaction.date <= date_to)

        result = await db.execute(query)
        transactions = list(result.scalars().all())

        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["data", "tipo", "valor", "categoria", "descricao"])
        for t in transactions:
            writer.writerow(
                [
                    t.date.date().isoformat(),
                    t.type.value,
                    f"{t.amount:.2f}",
                    t.category,
                    t.description,
                ]
            )

        return output.getvalue()

    @staticmethod
    async def get_ai_insights(
        user_id: uuid.UUID,
        db: AsyncSession,
        ai_service,
    ) -> dict:
        return await ai_service.generate_monthly_report(user_id=str(user_id), db=db)
