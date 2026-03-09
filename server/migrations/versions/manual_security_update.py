"""Add security fields and login logs

Revision ID: manual_security_update
Revises: 
Create Date: 2026-03-09 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'manual_security_update'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Only add columns to 'users' if they don't exist
    # And create 'login_attempt_logs' table
    
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    columns_users = [c['name'] for c in inspector.get_columns('users')]

    # Add columns to users if missing
    if 'failed_attempt_count' not in columns_users:
        op.add_column('users', sa.Column('failed_attempt_count', sa.Integer(), nullable=True, server_default='0'))
    if 'last_failed_at' not in columns_users:
        op.add_column('users', sa.Column('last_failed_at', sa.DateTime(), nullable=True))
    if 'lockout_until' not in columns_users:
        op.add_column('users', sa.Column('lockout_until', sa.DateTime(), nullable=True))
    if 'last_login_at' not in columns_users:
        op.add_column('users', sa.Column('last_login_at', sa.DateTime(), nullable=True))
    if 'last_login_ip' not in columns_users:
        op.add_column('users', sa.Column('last_login_ip', sa.String(length=45), nullable=True))
    
    # Create login_attempt_logs if missing
    if 'login_attempt_logs' not in tables:
        op.create_table('login_attempt_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.String(length=50), nullable=True),
            sa.Column('username_submitted', sa.String(length=80), nullable=False),
            sa.Column('ip_address', sa.String(length=45), nullable=False),
            sa.Column('user_agent', sa.String(length=255), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('failure_reason', sa.String(length=50), nullable=True),
            sa.Column('timestamp', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )

def downgrade():
    op.drop_table('login_attempt_logs')
    op.drop_column('users', 'last_login_ip')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'lockout_until')
    op.drop_column('users', 'last_failed_at')
    op.drop_column('users', 'failed_attempt_count')
