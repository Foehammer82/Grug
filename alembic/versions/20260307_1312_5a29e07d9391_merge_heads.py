"""merge_heads

Revision ID: 5a29e07d9391
Revises: 20260307_0002_manager_agent_models, 20260307_0004_document_visibility_and_file_path
Create Date: 2026-03-07 13:12:44.001301
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a29e07d9391'
down_revision: Union[str, None] = ('20260307_0002_manager_agent_models', '20260307_0004_document_visibility_and_file_path')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
