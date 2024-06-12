"""make group not null for event

Revision ID: fe638bcea31e
Revises: f3680e87f410
Create Date: 2024-06-10 19:47:42.452015

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'fe638bcea31e'
down_revision = 'f3680e87f410'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.alter_column('group_id',
               existing_type=sa.INTEGER(),
               nullable=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.alter_column('group_id',
               existing_type=sa.INTEGER(),
               nullable=True)

    # ### end Alembic commands ###