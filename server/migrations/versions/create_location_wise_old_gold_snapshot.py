"""create location wise old gold settlement transfer snapshot table

Revision ID: create_location_wise_old_gold
Revises: extend_collection_delivery
Create Date: 2026-08-17 11:25:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'create_location_wise_old_gold'
down_revision = 'extend_collection_delivery'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'location_wise_old_gold_settlement_transfer_snapshot',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column('transdate', sa.Date(), nullable=True),
        sa.Column('locationname', sa.String(length=200), nullable=True),
        sa.Column('office', sa.String(length=100), nullable=True),
        sa.Column('division', sa.String(length=100), nullable=True),
        sa.Column('groupname', sa.String(length=100), nullable=True),
        sa.Column('purity', sa.String(length=50), nullable=True),
        sa.Column('grwt', sa.Numeric(precision=18, scale=4), server_default='0', nullable=True),
        sa.Column('stwt', sa.Numeric(precision=18, scale=4), server_default='0', nullable=True),
        sa.Column('netwt', sa.Numeric(precision=18, scale=4), server_default='0', nullable=True),
        sa.Column('settlementmode', sa.String(length=100), nullable=True),
        sa.Column('transfer_grwt', sa.Numeric(precision=18, scale=4), server_default='0', nullable=True),
        sa.Column('transfer_stwt', sa.Numeric(precision=18, scale=4), server_default='0', nullable=True),
        sa.Column('transfer_netwt', sa.Numeric(precision=18, scale=4), server_default='0', nullable=True),
        sa.Column('locationtype', sa.String(length=100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
    )
    op.create_index(
        'ix_old_gold_transdate',
        'location_wise_old_gold_settlement_transfer_snapshot',
        ['transdate']
    )
    op.create_index(
        'ix_old_gold_office',
        'location_wise_old_gold_settlement_transfer_snapshot',
        ['office']
    )
    op.create_index(
        'ix_old_gold_locationname',
        'location_wise_old_gold_settlement_transfer_snapshot',
        ['locationname']
    )
    op.create_index(
        'ix_old_gold_division',
        'location_wise_old_gold_settlement_transfer_snapshot',
        ['division']
    )
    op.create_index(
        'ix_old_gold_groupname',
        'location_wise_old_gold_settlement_transfer_snapshot',
        ['groupname']
    )
    op.create_index(
        'ix_old_gold_purity',
        'location_wise_old_gold_settlement_transfer_snapshot',
        ['purity']
    )


def downgrade():
    op.drop_table('location_wise_old_gold_settlement_transfer_snapshot')
