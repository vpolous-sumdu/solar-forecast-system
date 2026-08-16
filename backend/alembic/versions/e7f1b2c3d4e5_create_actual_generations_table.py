"""Create actual_generations table

Revision ID: e7f1b2c3d4e5
Revises: 2a41e5cd6405
Create Date: 2026-08-16 12:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = '471578336f12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'actual_generations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('station_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actual_power_watts', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('actual_power_kw', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('station_id', 'timestamp', name='uq_station_actual_timestamp')
    )
    op.create_index(op.f('ix_actual_generations_id'), 'actual_generations', ['id'], unique=False)
    op.create_index(op.f('ix_actual_generations_station_id'), 'actual_generations', ['station_id'], unique=False)
    op.create_index(op.f('ix_actual_generations_timestamp'), 'actual_generations', ['timestamp'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_actual_generations_timestamp'), table_name='actual_generations')
    op.drop_index(op.f('ix_actual_generations_station_id'), table_name='actual_generations')
    op.drop_index(op.f('ix_actual_generations_id'), table_name='actual_generations')
    op.drop_table('actual_generations')
