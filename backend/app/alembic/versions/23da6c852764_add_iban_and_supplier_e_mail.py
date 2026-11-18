"""Add IBAN and supplier e-mail: where to pay, whom to write to, and the
bank account check against the supplier's previous invoices

Revision ID: 23da6c852764
Revises: d43280670550
Create Date: 2026-11-18 04:16:21.484227

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '23da6c852764'
down_revision = 'd43280670550'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('document', sa.Column('iban', sqlmodel.sql.sqltypes.AutoString(length=34), nullable=True))
    op.add_column('document', sa.Column('supplier_email', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))
    op.add_column('document', sa.Column('iban_checked', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('document', 'iban_checked')
    op.drop_column('document', 'supplier_email')
    op.drop_column('document', 'iban')
