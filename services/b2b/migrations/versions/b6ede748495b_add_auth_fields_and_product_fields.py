"""add_auth_fields_and_product_fields

Revision ID: b6ede748495b
Revises: d61fce28aeb4
Create Date: 2026-05-07 11:10:42.989781

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b6ede748495b'
down_revision: Union[str, None] = 'd61fce28aeb4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем поля в таблицу products (только если их нет)
    op.add_column('products', sa.Column('characteristics_json', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('products', sa.Column('deleted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('products', sa.Column('blocked', sa.Boolean(), nullable=False, server_default='false'))
    
    # Добавляем поля в таблицу sellers (только те, которых нет)
    op.add_column('sellers', sa.Column('hashed_password', sa.String(255), nullable=False, server_default=''))
    op.add_column('sellers', sa.Column('first_name', sa.String(100), nullable=False, server_default=''))
    op.add_column('sellers', sa.Column('last_name', sa.String(100), nullable=False, server_default=''))
    op.add_column('sellers', sa.Column('middle_name', sa.String(100), nullable=True))
    op.add_column('sellers', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    
    # НЕ ДОБАВЛЯЕМ email - он уже существует!


def downgrade() -> None:
    # Удаляем добавленные поля
    op.drop_column('sellers', 'is_active')
    op.drop_column('sellers', 'middle_name')
    op.drop_column('sellers', 'last_name')
    op.drop_column('sellers', 'first_name')
    op.drop_column('sellers', 'hashed_password')
    
    op.drop_column('products', 'blocked')
    op.drop_column('products', 'deleted')
    op.drop_column('products', 'characteristics_json')