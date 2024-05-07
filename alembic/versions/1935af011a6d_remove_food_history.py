"""remove food history

Revision ID: 1935af011a6d
Revises: 6f32a48327f0
Create Date: 2024-03-11 20:03:38.141517

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '1935af011a6d'
down_revision = '6f32a48327f0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('dndsession', schema=None) as batch_op:
        batch_op.drop_column('food_brought')

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('dndsession', schema=None) as batch_op:
        batch_op.add_column(sa.Column('food_brought', sa.VARCHAR(), nullable=True))

    # ### end Alembic commands ###
