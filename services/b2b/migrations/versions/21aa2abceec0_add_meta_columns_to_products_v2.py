"""add meta columns to products v2

Revision ID: 21aa2abceec0
Revises: ba52556b129b
Create Date: 2026-03-16 11:41:00.635156

"""
from alembic import op
import sqlalchemy as sa

revision = '81298b809358'
down_revision = 'ba52556b129b'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('products', sa.Column('meta_title', sa.String(length=500), nullable=True))
    op.add_column('products', sa.Column('meta_description', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('meta_keywords', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('moderation_comment', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('published_at', sa.DateTime(timezone=True), nullable=True))
    print("✅ Колонки добавлены")

def downgrade():
    op.drop_column('products', 'meta_title')
    op.drop_column('products', 'meta_description')
    op.drop_column('products', 'meta_keywords')
    op.drop_column('products', 'moderation_comment')
    op.drop_column('products', 'published_at')
    print("⏪ Колонки удалены")