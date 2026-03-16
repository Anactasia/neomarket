"""Initial migration with proper table order to avoid FK cycles"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ba52556b129b'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------- Parent tables --------------------
    op.create_table(
        'sellers',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('inn', sa.String(length=12), nullable=False, unique=True),
        sa.Column('kpp', sa.String(length=9)),
        sa.Column('ogrn', sa.String(length=15)),
        sa.Column('legal_address', sa.String(length=500)),
        sa.Column('actual_address', sa.String(length=500)),
        sa.Column('phone', sa.String(length=20)),
        sa.Column('email', sa.String(length=255)),
        sa.Column('status', sa.String(length=20)),
        sa.Column('rating', sa.DECIMAL(3,2)),
        sa.Column('verified_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False, unique=True),
        sa.Column('description', sa.Text()),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('categories.id')),
        sa.Column('level', sa.Integer()),
        sa.Column('image_url', sa.String(length=500)),
        sa.Column('is_active', sa.Boolean()),
        sa.Column('sort_order', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    op.create_table(
        'characteristics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False, unique=True),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('is_global', sa.Boolean()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    # -------------------- Products (without main_image_id) --------------------
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('seller_id', sa.String(length=36), sa.ForeignKey('sellers.id'), nullable=False),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('slug', sa.String(length=500), nullable=False, unique=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    # -------------------- Dependent tables --------------------
    op.create_table(
        'product_images',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE')),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('thumbnail_url', sa.String(length=500)),
        sa.Column('sort_order', sa.Integer()),
        sa.Column('is_main', sa.Boolean()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    # Add main_image_id to products AFTER product_images exists
    op.add_column('products', sa.Column('main_image_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_products_main_image', 'products', 'product_images', ['main_image_id'], ['id'])

    # Other dependent tables
    op.create_table(
        'category_characteristics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id', ondelete='CASCADE')),
        sa.Column('characteristic_id', sa.Integer(), sa.ForeignKey('characteristics.id', ondelete='CASCADE')),
        sa.Column('is_filter', sa.Boolean()),
        sa.Column('sort_order', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    op.create_table(
        'characteristic_values',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('characteristic_id', sa.Integer(), sa.ForeignKey('characteristics.id', ondelete='CASCADE')),
        sa.Column('value', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    op.create_table(
        'invoices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('seller_id', sa.String(length=36), sa.ForeignKey('sellers.id')),
        sa.Column('invoice_number', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20)),
        sa.Column('warehouse_id', sa.Integer()),
        sa.Column('received_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('seller_id', 'invoice_number', name='unique_seller_invoice'),
    )

    op.create_table(
        'product_status_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE')),
        sa.Column('old_status', sa.String(length=20)),
        sa.Column('new_status', sa.String(length=20), nullable=False),
        sa.Column('changed_by', sa.String(length=36)),
        sa.Column('reason', sa.Text()),
        sa.Column('comment', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    op.create_table(
        'skus',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE')),
        sa.Column('seller_sku', sa.String(length=100)),
        sa.Column('barcode', sa.String(length=100)),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.Column('compare_at_price', sa.Integer()),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean()),
        sa.Column('main_image_id', sa.Integer(), sa.ForeignKey('product_images.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    op.create_table(
        'invoice_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('invoice_id', sa.Integer(), sa.ForeignKey('invoices.id', ondelete='CASCADE')),
        sa.Column('sku_id', sa.Integer(), sa.ForeignKey('skus.id')),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price', sa.Integer()),
        sa.Column('accepted_quantity', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    op.create_table(
        'product_characteristics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE')),
        sa.Column('characteristic_id', sa.Integer(), sa.ForeignKey('characteristics.id', ondelete='CASCADE')),
        sa.Column('value_string', sa.Text()),
        sa.Column('value_int', sa.Integer()),
        sa.Column('value_float', sa.DECIMAL(10,2)),
        sa.Column('value_bool', sa.Boolean()),
        sa.Column('characteristic_value_id', sa.Integer(), sa.ForeignKey('characteristic_values.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    op.create_table(
        'sku_characteristics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('sku_id', sa.Integer(), sa.ForeignKey('skus.id', ondelete='CASCADE')),
        sa.Column('characteristic_id', sa.Integer(), sa.ForeignKey('characteristics.id', ondelete='CASCADE')),
        sa.Column('value_string', sa.Text()),
        sa.Column('value_int', sa.Integer()),
        sa.Column('value_float', sa.DECIMAL(10,2)),
        sa.Column('value_bool', sa.Boolean()),
        sa.Column('characteristic_value_id', sa.Integer(), sa.ForeignKey('characteristic_values.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    op.create_table(
        'sku_reservations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('sku_id', sa.Integer(), sa.ForeignKey('skus.id', ondelete='CASCADE')),
        sa.Column('order_id', sa.String(length=36), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20)),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    # drop tables in reverse order
    op.drop_table('sku_reservations')
    op.drop_table('sku_characteristics')
    op.drop_table('product_characteristics')
    op.drop_table('invoice_items')
    op.drop_table('skus')
    op.drop_table('product_status_history')
    op.drop_table('invoices')
    op.drop_table('characteristic_values')
    op.drop_table('category_characteristics')
    op.drop_table('product_images')
    op.drop_table('products')
    op.drop_table('characteristics')
    op.drop_table('categories')
    op.drop_table('sellers')