"""time

Revision ID: d9eab80a6580
Revises: f688270f03cd
Create Date: 2024-09-17 15:02:46.023878

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'd9eab80a6580'
down_revision = 'f688270f03cd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_admin')
        batch_op.drop_column('disabled')

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('disabled', sa.BOOLEAN(), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('is_admin', sa.BOOLEAN(), autoincrement=False, nullable=False))

    # ### end Alembic commands ###
