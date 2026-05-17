"""merge lgpd and goals migrations

Revision ID: 96e8aac9ca71
Revises: 5b002e4ff464, c3f8a2d1e509
Create Date: 2026-05-17 11:58:05.354693

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96e8aac9ca71'
down_revision: Union[str, None] = ('5b002e4ff464', 'c3f8a2d1e509')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
