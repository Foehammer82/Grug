"""fresh start

Revision ID: 9cd29399a009
Revises: 
Create Date: 2024-05-11 21:27:34.951911

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '9cd29399a009'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('discordtextchannel',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('discord_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('assistant_thread_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('discordtextchannel', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_discordtextchannel_discord_id'), ['discord_id'], unique=False)

    op.create_table('groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('bot_name_override', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('bot_instructions_override', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('player',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('discord_member_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('discord_guild_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('discord_username', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('discord_guild_nickname', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('first_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('last_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('phone', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('brings_food', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('assistant_thread_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('first_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('last_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('phone', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('disabled', sa.Boolean(), nullable=False),
    sa.Column('assistant_thread_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('discord_accounts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('discord_member_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('discord_servers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=True),
    sa.Column('discord_guild_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('dndsession',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('discord_guild_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('session_start_datetime', sa.DateTime(), nullable=False),
    sa.Column('food_bringer_player_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['food_bringer_player_id'], ['player.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('group_id', sa.Integer(), nullable=True),
    sa.Column('event_schedule_cron', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('event_schedule_start_date', sa.Date(), nullable=True),
    sa.Column('event_schedule_end_date', sa.Date(), nullable=True),
    sa.Column('track_food', sa.Boolean(), nullable=False),
    sa.Column('food_reminder_days_in_advance', sa.Integer(), nullable=False),
    sa.Column('food_reminder_time', sa.Time(), nullable=False),
    sa.Column('track_attendance', sa.Boolean(), nullable=False),
    sa.Column('attendance_check_days_in_advance', sa.Integer(), nullable=False),
    sa.Column('attendance_check_time', sa.Time(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users_groups_link',
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['groups.id'], ),
    sa.PrimaryKeyConstraint('group_id', 'user_id')
    )
    op.create_table('users_secrets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('hashed_password', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('events_attendance',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_date', sa.Date(), nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=True),
    sa.Column('discord_message_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('events_food',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_date', sa.Date(), nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=True),
    sa.Column('user_assigned_food_id', sa.Integer(), nullable=True),
    sa.Column('food_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('food_description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('discord_message_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.ForeignKeyConstraint(['user_assigned_food_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('foodselectionmessage',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('discord_message_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('dnd_session_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['dnd_session_id'], ['dndsession.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('foodselectionmessage', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_foodselectionmessage_discord_message_id'), ['discord_message_id'], unique=False)

    op.create_table('users_events_attendance_link',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('event_attendance_id', sa.Integer(), nullable=False),
    sa.Column('rsvp', sa.Enum('YES', 'NO', 'MAYBE', 'NO_RESPONSE', name='rsvp'), nullable=False),
    sa.ForeignKeyConstraint(['event_attendance_id'], ['events_attendance.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id', 'event_attendance_id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('users_events_attendance_link')
    with op.batch_alter_table('foodselectionmessage', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_foodselectionmessage_discord_message_id'))

    op.drop_table('foodselectionmessage')
    op.drop_table('events_food')
    op.drop_table('events_attendance')
    op.drop_table('users_secrets')
    op.drop_table('users_groups_link')
    op.drop_table('events')
    op.drop_table('dndsession')
    op.drop_table('discord_servers')
    op.drop_table('discord_accounts')
    op.drop_table('users')
    op.drop_table('player')
    op.drop_table('groups')
    with op.batch_alter_table('discordtextchannel', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_discordtextchannel_discord_id'))

    op.drop_table('discordtextchannel')
    # ### end Alembic commands ###
