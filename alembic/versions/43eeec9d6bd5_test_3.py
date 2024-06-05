"""test-3

Revision ID: 43eeec9d6bd5
Revises: b83544a08082
Create Date: 2024-06-02 21:06:29.154134

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '43eeec9d6bd5'
down_revision = 'b83544a08082'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.add_column(sa.Column('food_reminder_time', sa.Time(), nullable=False))
        batch_op.drop_column('attendance_reminder_time_minute')
        batch_op.drop_column('food_reminder_time_hour')
        batch_op.drop_column('food_reminder_time_minute')
        batch_op.drop_column('attendance_reminder_time_hour')

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.add_column(sa.Column('attendance_reminder_time_hour', sa.INTEGER(), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('food_reminder_time_minute', sa.INTEGER(), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('food_reminder_time_hour', sa.INTEGER(), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('attendance_reminder_time_minute', sa.INTEGER(), autoincrement=False, nullable=False))
        batch_op.drop_column('food_reminder_time')

    # ### end Alembic commands ###