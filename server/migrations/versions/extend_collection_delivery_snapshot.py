"""Extend collection delivery snapshot fields.

Revision ID: extend_collection_delivery
Revises: add_password_reset_fields
Create Date: 2026-07-30 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'extend_collection_delivery'
down_revision = 'add_password_reset_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'snapshot_collection_wise_average_delivery_days',
        'is_hand',
        new_column_name='by_hand',
        existing_type=sa.Boolean(),
    )
    op.add_column(
        'snapshot_collection_wise_average_delivery_days',
        sa.Column('supplier_id', sa.BigInteger(), nullable=True),
    )
    op.add_column(
        'snapshot_collection_wise_average_delivery_days',
        sa.Column('supplier_name', sa.Text(), nullable=True),
    )
    op.add_column(
        'snapshot_collection_wise_average_delivery_days',
        sa.Column('delivery_days', sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column('snapshot_collection_wise_average_delivery_days', 'delivery_days')
    op.drop_column('snapshot_collection_wise_average_delivery_days', 'supplier_name')
    op.drop_column('snapshot_collection_wise_average_delivery_days', 'supplier_id')
    op.alter_column(
        'snapshot_collection_wise_average_delivery_days',
        'by_hand',
        new_column_name='is_hand',
        existing_type=sa.Boolean(),
    )
