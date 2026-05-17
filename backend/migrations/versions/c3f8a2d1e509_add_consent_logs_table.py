"""add consent_logs table

Revision ID: c3f8a2d1e509
Revises: b7e3f1a2c894
Create Date: 2026-05-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c3f8a2d1e509"
down_revision = "b7e3f1a2c894"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consent_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("consent_given", sa.Boolean(), nullable=False),
        sa.Column("consent_version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column(
            "policy_url", sa.String(500), nullable=False
        ),
        sa.Column("channel", sa.String(50), nullable=False, server_default="whatsapp"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consent_logs_user_id", "consent_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_consent_logs_user_id", table_name="consent_logs")
    op.drop_table("consent_logs")
