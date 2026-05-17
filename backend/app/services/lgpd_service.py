"""LGPD (Brazilian data privacy law) compliance service."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.infrastructure.database.models.consent_log import ConsentLog
from app.infrastructure.database.models.transaction import Transaction
from app.infrastructure.database.models.user import User

logger = get_logger(__name__)

_POLICY_URL = "https://quingo.com.br/privacy.html"
_CONSENT_VERSION = "1.0"


class LGPDService:
    @staticmethod
    async def record_consent(
        user_id: uuid.UUID,
        phone_number: str,
        consent_given: bool,
        db: AsyncSession,
        ip_address: str | None = None,
    ) -> ConsentLog:
        log = ConsentLog(
            user_id=user_id,
            phone_number=phone_number,
            consent_given=consent_given,
            consent_version=_CONSENT_VERSION,
            policy_url=_POLICY_URL,
            channel="whatsapp",
            ip_address=ip_address,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        logger.info(
            "lgpd_consent_recorded",
            user_id=str(user_id),
            consent_given=consent_given,
        )
        return log

    @staticmethod
    async def delete_user_data(user_id: uuid.UUID, db: AsyncSession) -> None:
        """Hard-delete all user data (CASCADE handles related tables)."""
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return
        await db.delete(user)
        await db.commit()
        logger.info("lgpd_user_data_deleted", user_id=str(user_id))

    @staticmethod
    async def get_user_data_summary(user_id: uuid.UUID, db: AsyncSession) -> dict:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return {}

        txn_result = await db.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.date.desc())
            .limit(50)
        )
        transactions = list(txn_result.scalars().all())

        consent_result = await db.execute(
            select(ConsentLog)
            .where(ConsentLog.user_id == user_id)
            .order_by(ConsentLog.created_at.desc())
            .limit(1)
        )
        consent = consent_result.scalar_one_or_none()

        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "phone": user.phone,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
            "transactions_count": len(transactions),
            "consent": {
                "given": consent.consent_given if consent else None,
                "version": consent.consent_version if consent else None,
                "date": consent.created_at.isoformat() if consent else None,
            },
        }

    @staticmethod
    async def export_user_transactions(
        user_id: uuid.UUID, db: AsyncSession
    ) -> list[dict]:
        result = await db.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.date.desc())
            .limit(50)
        )
        transactions = list(result.scalars().all())
        return [
            {
                "date": t.date.strftime("%d/%m/%Y") if t.date else "",
                "type": "Receita" if str(t.type).endswith("INCOME") else "Despesa",
                "amount": str(t.amount),
                "category": t.category or "",
                "description": t.description or "",
            }
            for t in transactions
        ]

    @staticmethod
    def format_data_summary(summary: dict) -> str:
        if not summary:
            return "Não encontrei seus dados."

        u = summary["user"]
        c = summary["consent"]
        txn_count = summary["transactions_count"]

        consent_line = ""
        if c.get("given") is not None:
            consent_word = "Sim" if c["given"] else "Não"
            consent_line = (
                f"\n📋 Consentimento LGPD: *{consent_word}* (v{c['version']})"
            )

        return (
            f"📊 *Seus dados no Hermes:*\n\n"
            f"👤 Nome: *{u['full_name'] or 'não informado'}*\n"
            f"📱 Telefone: *{u['phone'] or 'não informado'}*\n"
            f"📧 E-mail: *{u['email']}*\n"
            f"📅 Conta criada: *{u['created_at'][:10] if u['created_at'] else 'n/d'}*\n"
            f"💳 Transações registradas: *{txn_count}*"
            f"{consent_line}\n\n"
            f"🔒 Seus dados são protegidos pela LGPD.\n"
            f"Política: {_POLICY_URL}"
        )

    @staticmethod
    def format_export(transactions: list[dict]) -> str:
        if not transactions:
            return "📋 Você ainda não tem transações registradas."

        lines = [f"📋 *Suas últimas {len(transactions)} transações:*\n"]
        for t in transactions:
            icon = "💰" if t["type"] == "Receita" else "💸"
            lines.append(
                f"{icon} {t['date']} | {t['type']} | R$ {t['amount']} | {t['category']}"
            )

        lines.append(
            f"\n\n_Para exportar em CSV envie seu e-mail ou acesse {_POLICY_URL}_"
        )
        return "\n".join(lines)
