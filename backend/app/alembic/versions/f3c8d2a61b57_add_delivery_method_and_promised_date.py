"""Add delivery method, delivery mode and promised delivery date

Revision ID: f3c8d2a61b57
Revises: e5b1c9a7d402
Create Date: 2026-11-17 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision = 'f3c8d2a61b57'
down_revision = 'e5b1c9a7d402'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('document', sa.Column('delivery_method', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True))
    op.add_column('document', sa.Column('delivery_mode', sa.String(length=20), nullable=True))
    op.add_column('document', sa.Column('expected_delivery_date', sa.Date(), nullable=True))


def downgrade():
    op.drop_column('document', 'expected_delivery_date')
    op.drop_column('document', 'delivery_mode')
    op.drop_column('document', 'delivery_method')
