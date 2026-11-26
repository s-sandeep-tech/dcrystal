"""Carry the external design UID through the online-stock snapshots."""
from alembic import op
import sqlalchemy as sa

revision = 'add_online_stock_design_uid'
down_revision = 'add_online_stock_design_no'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    for table in ('online_provision_stock_raw_snapshot', 'online_provision_stock_raw_staging'):
        if 'design_uid' not in {c['name'] for c in sa.inspect(connection).get_columns(table)}:
            op.add_column(table, sa.Column('design_uid', sa.Text(), nullable=True))


def downgrade():
    for table in ('online_provision_stock_raw_staging', 'online_provision_stock_raw_snapshot'):
        op.drop_column(table, 'design_uid')
