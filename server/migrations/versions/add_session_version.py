"""Add session_version to users table

Revision ID: add_session_version
Revises: manual_security_update
Create Date: 2026-03-18 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_session_version'
down_revision = 'manual_security_update'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns_users = [c['name'] for c in inspector.get_columns('users')]

    # Add session_version to users if missing
    if 'session_version' not in columns_users:
        op.add_column('users', sa.Column('session_version', sa.Integer(), nullable=False, server_default='0'))

def downgrade():
    op.drop_column('users', 'session_version')
