"""Add payment, due date and e-invoice flag: purchases the user has paid, when
invoices are due, and invoices read from their Factur-X data

Revision ID: d43280670550
Revises: d7c18dd3236a
Create Date: 2026-11-18 03:22:28.109485

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'd43280670550'
down_revision = 'd7c18dd3236a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('payment',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('purchase_key', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.Column('invoice_ids', sa.JSON(), nullable=False),
    sa.Column('paid_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('owner_id', 'purchase_key')
    )
    op.create_index(op.f('ix_payment_owner_id'), 'payment', ['owner_id'], unique=False)
    op.add_column('document', sa.Column('due_date', sa.Date(), nullable=True))
    op.add_column('document', sa.Column('payment_terms', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True))
    op.add_column('document', sa.Column('from_einvoice', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('document', 'from_einvoice')
    op.drop_column('document', 'payment_terms')
    op.drop_column('document', 'due_date')
    op.drop_index(op.f('ix_payment_owner_id'), table_name='payment')
    op.drop_table('payment')
