"""Invoice becomes document, with a kind, an order reference and lines

Revision ID: e5b1c9a7d402
Revises: d7a3f0b8c215
Create Date: 2026-11-17 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision = 'e5b1c9a7d402'
down_revision = 'd7a3f0b8c215'
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table('invoice', 'document')
    op.execute('ALTER TABLE document RENAME CONSTRAINT invoice_pkey TO document_pkey')
    op.execute('ALTER TABLE document RENAME CONSTRAINT invoice_owner_id_fkey TO document_owner_id_fkey')
    op.execute('ALTER INDEX ix_invoice_status RENAME TO ix_document_status')
    op.alter_column('document', 'invoice_number', new_column_name='number')
    op.alter_column('document', 'invoice_date', new_column_name='document_date')
    op.add_column('document', sa.Column('kind', sa.String(length=20), nullable=False, server_default='invoice'))
    op.alter_column('document', 'kind', server_default=None)
    op.add_column('document', sa.Column('order_reference', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True))
    op.create_index(op.f('ix_document_kind'), 'document', ['kind'], unique=False)
    op.create_index(op.f('ix_document_order_reference'), 'document', ['order_reference'], unique=False)

    op.create_table(
        'documentline',
        sa.Column('reference', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column('unit', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('amount_excl_tax', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['document.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_documentline_document_id'), 'documentline', ['document_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_documentline_document_id'), table_name='documentline')
    op.drop_table('documentline')
    op.execute("DELETE FROM document WHERE kind <> 'invoice'")
    op.drop_index(op.f('ix_document_order_reference'), table_name='document')
    op.drop_index(op.f('ix_document_kind'), table_name='document')
    op.drop_column('document', 'order_reference')
    op.drop_column('document', 'kind')
    op.alter_column('document', 'document_date', new_column_name='invoice_date')
    op.alter_column('document', 'number', new_column_name='invoice_number')
    op.execute('ALTER INDEX ix_document_status RENAME TO ix_invoice_status')
    op.execute('ALTER TABLE document RENAME CONSTRAINT document_owner_id_fkey TO invoice_owner_id_fkey')
    op.execute('ALTER TABLE document RENAME CONSTRAINT document_pkey TO invoice_pkey')
    op.rename_table('document', 'invoice')
