"""add food_brought column to dnd_session

Revision ID: c21321e358e3
Revises: 0b2cc423c3cc
Create Date: 2023-01-06 13:47:38.914403

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'c21321e358e3'
down_revision = '0b2cc423c3cc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('dndsession', sa.Column('food_brought', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('dndsession', 'food_brought')
    # ### end Alembic commands ###
