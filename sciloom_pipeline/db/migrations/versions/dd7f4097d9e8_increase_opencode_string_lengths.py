"""increase_opencode_string_lengths

Revision ID: dd7f4097d9e8
Revises: 9ecdec9a508f
Create Date: 2026-06-01 16:14:06.732682

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd7f4097d9e8'
down_revision: Union[str, Sequence[str], None] = '9ecdec9a508f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('jobs') as batch_op:
        batch_op.alter_column('opencode_session_id',
                   existing_type=sa.VARCHAR(length=200),
                   type_=sa.String(length=512),
                   existing_nullable=True)
        batch_op.alter_column('opencode_server_url',
                   existing_type=sa.VARCHAR(length=500),
                   type_=sa.String(length=2048),
                   existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('jobs') as batch_op:
        batch_op.alter_column('opencode_server_url',
                   existing_type=sa.String(length=2048),
                   type_=sa.VARCHAR(length=500),
                   existing_nullable=True)
        batch_op.alter_column('opencode_session_id',
                   existing_type=sa.String(length=512),
                   type_=sa.VARCHAR(length=200),
                   existing_nullable=True)
