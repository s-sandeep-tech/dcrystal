"""Rename branch_head to business_head in showroom_wise_order_summary_snapshot

Revision ID: rename_branch_head_to_business_head_showroom
Revises: add_session_version
Create Date: 2026-03-18 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'rename_branch_head_to_business_head_showroom'
down_revision = 'add_session_version'
branch_labels = None
depends_on = None

def upgrade():
    # Rename column branch_head to business_head
    op.alter_column('showroom_wise_order_summary_snapshot', 'branch_head', new_column_name='business_head')

def downgrade():
    # Rename column business_head back to branch_head
    op.alter_column('showroom_wise_order_summary_snapshot', 'business_head', new_column_name='branch_head')
