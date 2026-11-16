"""Add started_at to invoice

Revision ID: c41d7e2a9f10
Revises: b29128f795e0
Create Date: 2026-11-16 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision = 'c41d7e2a9f10'
down_revision = 'b29128f795e0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('invoice', sa.Column('started_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True))


def downgrade():
    op.drop_column('invoice', 'started_at')
