"""adjust how admin is set

Revision ID: 340462ee64d5
Revises: 981988ec6533
Create Date: 2024-06-17 19:35:04.427261

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '340462ee64d5'
down_revision = '981988ec6533'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_admin', sa.Boolean(), nullable=False))
        batch_op.drop_column('role')

    sa.Enum('ADMIN', 'USER', name='userrole').drop(op.get_bind())
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    sa.Enum('ADMIN', 'USER', name='userrole').create(op.get_bind())
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', postgresql.ENUM('ADMIN', 'USER', name='userrole', create_type=False), autoincrement=False, nullable=False))
        batch_op.drop_column('is_admin')

    # ### end Alembic commands ###
