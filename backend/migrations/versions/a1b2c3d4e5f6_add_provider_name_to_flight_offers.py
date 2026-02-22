"""Add provider_name column to flight_offers

Revision ID: a1b2c3d4e5f6
Revises: 6386c72e1d26
Create Date: 2026-02-22 13:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '6386c72e1d26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('flight_offers', sa.Column('provider_name', sa.String(length=50), server_default='amadeus', nullable=False))


def downgrade() -> None:
    op.drop_column('flight_offers', 'provider_name')
