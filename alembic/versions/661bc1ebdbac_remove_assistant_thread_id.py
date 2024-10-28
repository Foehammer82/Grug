"""remove assistant thread id

Revision ID: 661bc1ebdbac
Revises: 29bd138608df
Create Date: 2024-10-27 19:17:38.430222

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '661bc1ebdbac'
down_revision = '29bd138608df'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('assistant_thread_id')

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assistant_thread_id', sa.VARCHAR(), autoincrement=False, nullable=True))

    # ### end Alembic commands ###
