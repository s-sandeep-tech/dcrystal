"""Add Design No to the independent online-stock snapshots."""
from alembic import op
import sqlalchemy as sa

revision = 'add_online_stock_design_no'
down_revision = 'create_online_provision_stock'
branch_labels = None
depends_on = None


def upgrade():
    # Sync/setup may already have bootstrapped this additive column.
    connection = op.get_bind()
    for table in ('online_provision_stock_raw_snapshot', 'online_provision_stock_raw_staging'):
        if 'design_no' not in {c['name'] for c in sa.inspect(connection).get_columns(table)}:
            op.add_column(table, sa.Column('design_no', sa.String(100), nullable=True))


def downgrade():
    for table in ('online_provision_stock_raw_staging', 'online_provision_stock_raw_snapshot'):
        op.drop_column(table, 'design_no')
