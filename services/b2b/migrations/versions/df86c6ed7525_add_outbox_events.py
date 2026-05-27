"""add_outbox_events

Revision ID: df86c6ed7525
Revises: eb93ae4b42cf
Create Date: 2026-05-27 12:04:56.312562

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'df86c6ed7525'
down_revision: Union[str, None] = 'eb93ae4b42cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'outbox_events',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('target', sa.String(20), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('headers', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), server_default='PENDING'),
        sa.Column('retry_count', sa.Integer(), server_default='0'),
        sa.Column('error_message', sa.String(1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_outbox_status', 'outbox_events', ['status'])


def downgrade() -> None:
    op.drop_table('outbox_events')