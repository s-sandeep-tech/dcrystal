"""Add password reset fields to users table

Revision ID: add_password_reset_fields
Revises: rename_branch_head_to_business_head_showroom
Create Date: 2026-03-28 14:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_password_reset_fields'
down_revision = 'rename_branch_head_to_business_head_showroom'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns_users = [c['name'] for c in inspector.get_columns('users')]

    if 'must_reset_password' not in columns_users:
        op.add_column('users', sa.Column('must_reset_password', sa.Boolean(), nullable=False, server_default='false'))
    
    if 'last_reset_initiated_at' not in columns_users:
        op.add_column('users', sa.Column('last_reset_initiated_at', sa.DateTime(), nullable=True))

def downgrade():
    op.drop_column('users', 'last_reset_initiated_at')
    op.drop_column('users', 'must_reset_password')
