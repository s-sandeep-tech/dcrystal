"""Carry design UID from the NIP barcode view into both local tables."""
from alembic import op
import sqlalchemy as sa

revision = 'add_nip_barcode_design_uid'
down_revision = 'add_online_stock_design_uid'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    for table in ('size_level_nip_barcode_snapshot', 'size_level_nip_barcode_staging'):
        if 'design_uid' not in {c['name'] for c in sa.inspect(connection).get_columns(table)}:
            op.add_column(table, sa.Column('design_uid', sa.Text(), nullable=True))


def downgrade():
    for table in ('size_level_nip_barcode_staging', 'size_level_nip_barcode_snapshot'):
        op.drop_column(table, 'design_uid')
