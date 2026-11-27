"""Store current supplier capacity used for backlog balances."""
from alembic import op
import sqlalchemy as sa

revision = 'add_party_current_capacity'
down_revision = 'add_nip_barcode_design_uid'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    table = 'party_make_capacity_details_snapshot'
    if 'current_capacity' not in {c['name'] for c in sa.inspect(connection).get_columns(table)}:
        op.add_column(table, sa.Column('current_capacity', sa.Numeric(15, 3), nullable=True))


def downgrade():
    op.drop_column('party_make_capacity_details_snapshot', 'current_capacity')
