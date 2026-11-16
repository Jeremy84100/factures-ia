"""Add credit note flag and VAT exemption to invoice

Revision ID: d7a3f0b8c215
Revises: c41d7e2a9f10
Create Date: 2026-11-16 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision = 'd7a3f0b8c215'
down_revision = 'c41d7e2a9f10'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('invoice', sa.Column('is_credit_note', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('invoice', sa.Column('vat_exemption', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))


def downgrade():
    op.drop_column('invoice', 'vat_exemption')
    op.drop_column('invoice', 'is_credit_note')
