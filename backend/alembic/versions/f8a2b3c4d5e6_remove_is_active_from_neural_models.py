"""Remove is_active column from neural_models

Revision ID: f8a2b3c4d5e6
Revises: e7f1b2c3d4e5
Create Date: 2026-08-16 16:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e7f1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('neural_models', 'is_active')


def downgrade() -> None:
    op.add_column('neural_models', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')))
