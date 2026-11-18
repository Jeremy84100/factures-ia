"""Add settlement: disputes the user has settled with the supplier

Revision ID: d7c18dd3236a
Revises: f3c8d2a61b57
Create Date: 2026-11-18 01:04:05.184064

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'd7c18dd3236a'
down_revision = 'f3c8d2a61b57'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('settlement',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('purchase_key', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.Column('issues', sa.JSON(), nullable=False),
    sa.Column('settled_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('owner_id', 'purchase_key')
    )
    op.create_index(op.f('ix_settlement_owner_id'), 'settlement', ['owner_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_settlement_owner_id'), table_name='settlement')
    op.drop_table('settlement')
