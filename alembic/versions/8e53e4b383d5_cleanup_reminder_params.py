"""cleanup reminder params

Revision ID: 8e53e4b383d5
Revises: f66843e1a0e8
Create Date: 2024-06-20 19:07:48.771950

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8e53e4b383d5'
down_revision = 'f66843e1a0e8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('event_occurrence', schema=None) as batch_op:
        batch_op.drop_column('attendance_reminder')
        batch_op.drop_column('food_reminder')

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('event_occurrence', schema=None) as batch_op:
        batch_op.add_column(sa.Column('food_reminder', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('attendance_reminder', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))

    # ### end Alembic commands ###