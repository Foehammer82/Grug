"""simplify attendance join table

Revision ID: ae6f85c46ace
Revises: fe638bcea31e
Create Date: 2024-06-12 19:44:46.179622

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ae6f85c46ace'
down_revision = 'fe638bcea31e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users_events_attendance_link', schema=None) as batch_op:
        batch_op.drop_column('rsvp')

    sa.Enum('YES', 'NO', 'MAYBE', 'NO_RESPONSE', name='rsvp').drop(op.get_bind())
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    sa.Enum('YES', 'NO', 'MAYBE', 'NO_RESPONSE', name='rsvp').create(op.get_bind())
    with op.batch_alter_table('users_events_attendance_link', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rsvp', postgresql.ENUM('YES', 'NO', 'MAYBE', 'NO_RESPONSE', name='rsvp', create_type=False), autoincrement=False, nullable=False))

    # ### end Alembic commands ###
