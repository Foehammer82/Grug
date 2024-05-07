"""add assistant thread id to player

Revision ID: 904c05ff7576
Revises: 9d37c464ee02
Create Date: 2024-03-12 10:13:59.979394

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '904c05ff7576'
down_revision = '9d37c464ee02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###

    with op.batch_alter_table('player', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assistant_thread_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True))

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('player', schema=None) as batch_op:
        batch_op.drop_column('assistant_thread_id')

    # ### end Alembic commands ###