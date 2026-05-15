from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.transaction import TransactionType
from app.services.report_service import ReportService
from app.services.transaction_service import TransactionService

NOW = datetime.now(timezone.utc)


async def _txn(db, user_id, type, amount, category, description="test"):
    return await TransactionService.create(
        user_id=user_id,
        type=type,
        amount=Decimal(str(amount)),
        description=description,
        category=category,
        date=NOW,
        db=db,
    )


async def test_get_balance_empty(db: AsyncSession, test_user):
    result = await ReportService.get_balance(test_user.id, db)
    assert result["total_income"] == Decimal("0.00")
    assert result["total_expense"] == Decimal("0.00")
    assert result["balance"] == Decimal("0.00")
    assert isinstance(result["last_updated"], datetime)


async def test_get_balance_with_transactions(db: AsyncSession, test_user):
    await _txn(db, test_user.id, TransactionType.INCOME, "5000.00", "Renda", "Salário")
    await _txn(
        db, test_user.id, TransactionType.EXPENSE, "800.00", "Alimentação", "Mercado"
    )
    await _txn(
        db, test_user.id, TransactionType.EXPENSE, "450.00", "Transporte", "Uber"
    )

    result = await ReportService.get_balance(test_user.id, db)
    assert result["total_income"] == Decimal("5000.00")
    assert result["total_expense"] == Decimal("1250.00")
    assert result["balance"] == Decimal("3750.00")


async def test_get_monthly_report(db: AsyncSession, test_user):
    await _txn(db, test_user.id, TransactionType.INCOME, "3000.00", "Renda", "Salário")
    await _txn(
        db, test_user.id, TransactionType.EXPENSE, "200.00", "Alimentação", "Almoço"
    )
    await _txn(
        db, test_user.id, TransactionType.EXPENSE, "100.00", "Alimentação", "Jantar"
    )

    result = await ReportService.get_monthly_report(
        test_user.id, NOW.year, NOW.month, db
    )

    assert result["period"] == f"{NOW.year}-{NOW.month:02d}"
    assert result["total_income"] == Decimal("3000.00")
    assert result["total_expense"] == Decimal("300.00")
    assert result["balance"] == Decimal("2700.00")
    assert len(result["by_category"]) == 1
    assert result["by_category"][0]["category"] == "Alimentação"
    assert result["by_category"][0]["count"] == 2
    assert result["by_category"][0]["percentage"] == 100.0


async def test_get_monthly_report_empty(db: AsyncSession, test_user):
    result = await ReportService.get_monthly_report(test_user.id, 2000, 1, db)
    assert result["total_income"] == Decimal("0.00")
    assert result["total_expense"] == Decimal("0.00")
    assert result["by_category"] == []


async def test_get_by_category(db: AsyncSession, test_user):
    await _txn(db, test_user.id, TransactionType.EXPENSE, "800.00", "Alimentação")
    await _txn(db, test_user.id, TransactionType.EXPENSE, "200.00", "Alimentação")
    await _txn(db, test_user.id, TransactionType.EXPENSE, "450.00", "Transporte")

    result = await ReportService.get_by_category(test_user.id, db)

    assert len(result) == 2
    assert result[0]["category"] == "Alimentação"
    assert result[0]["total"] == Decimal("1000.00")
    assert result[0]["count"] == 2
    assert result[1]["category"] == "Transporte"
    assert result[1]["total"] == Decimal("450.00")
    # Percentages should add up to ~100
    total_pct = sum(item["percentage"] for item in result)
    assert abs(total_pct - 100.0) < 0.2


async def test_get_summary(db: AsyncSession, test_user):
    await _txn(db, test_user.id, TransactionType.INCOME, "5000.00", "Renda", "Salário")
    await _txn(
        db, test_user.id, TransactionType.EXPENSE, "800.00", "Alimentação", "Mercado"
    )
    await _txn(
        db, test_user.id, TransactionType.EXPENSE, "200.00", "Transporte", "Uber"
    )

    result = await ReportService.get_summary(test_user.id, db)

    assert isinstance(result["recent_transactions"], list)
    assert len(result["recent_transactions"]) <= 5
    assert result["total_income"] == Decimal("5000.00")
    assert result["total_expense"] == Decimal("1000.00")
    assert result["balance"] == Decimal("4000.00")
    assert result["largest_expense_this_month"] == Decimal("800.00")
    assert result["largest_income_this_month"] == Decimal("5000.00")
    assert result["daily_average_expense"] > 0


async def test_export_csv_format(db: AsyncSession, test_user):
    await _txn(db, test_user.id, TransactionType.INCOME, "1000.00", "Renda", "Salário")
    await _txn(
        db, test_user.id, TransactionType.EXPENSE, "50.00", "Alimentação", "Almoço"
    )

    csv_str = await ReportService.export_csv(test_user.id, db)

    lines = [line for line in csv_str.strip().split("\n") if line]
    assert lines[0] == "data,tipo,valor,categoria,descricao"
    assert len(lines) == 3  # header + 2 rows
    assert "INCOME" in csv_str
    assert "EXPENSE" in csv_str
    assert "1000.00" in csv_str
    assert "50.00" in csv_str
    assert "Salário" in csv_str
